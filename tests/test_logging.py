"""Tests for structured logging in the API, the services and the CLI."""

import json
import logging
import sys

import pytest
from fastapi.testclient import TestClient

from app.logging_config import JsonFormatter, configure_logging
from app.main import create_app
from app.services.trending import RedisClient


def _record(**extra) -> logging.LogRecord:
    record = logging.makeLogRecord({"name": "app.test", "levelname": "INFO", "msg": "hello %s"})
    record.args = ("world",)
    record.__dict__.update(extra)
    return record


def test_json_formatter_emits_one_parseable_object_with_extras():
    line = JsonFormatter().format(_record(path="/health/", status_code=200))

    assert "\n" not in line
    payload = json.loads(line)
    assert payload["message"] == "hello world"
    assert payload["level"] == "INFO"
    assert payload["logger"] == "app.test"
    assert payload["path"] == "/health/"
    assert payload["status_code"] == 200
    assert payload["timestamp"].endswith("+00:00")
    assert "args" not in payload and "msg" not in payload


def test_json_formatter_includes_traceback():
    try:
        raise RuntimeError("boom")
    except RuntimeError:
        record = logging.makeLogRecord({"msg": "failed", "exc_info": sys.exc_info()})

    payload = json.loads(JsonFormatter().format(record))
    assert "RuntimeError: boom" in payload["exc_info"]


def test_configure_logging_is_idempotent_and_honours_format():
    configure_logging(level="debug", fmt="text")
    configure_logging(level="warning", fmt="json")

    logger = logging.getLogger("app")
    assert len(logger.handlers) == 1
    assert isinstance(logger.handlers[0].formatter, JsonFormatter)
    assert logger.level == logging.WARNING

    configure_logging(level="info", fmt="text")
    assert not isinstance(logger.handlers[0].formatter, JsonFormatter)


@pytest.fixture
def app_with_failing_route():
    app = create_app()

    @app.get("/boom")
    async def boom():
        raise RuntimeError("kaboom")

    return app


def test_request_middleware_logs_method_path_status_and_duration(caplog):
    client = TestClient(create_app())
    with caplog.at_level(logging.INFO, logger="app.main"):
        response = client.get("/openapi.json")

    assert response.status_code == 200
    records = [r for r in caplog.records if r.getMessage() == "request"]
    assert len(records) == 1
    assert records[0].method == "GET"
    assert records[0].path == "/openapi.json"
    assert records[0].status_code == 200
    assert records[0].duration_ms >= 0


def test_unhandled_exception_is_logged_with_traceback(app_with_failing_route, caplog):
    client = TestClient(app_with_failing_route, raise_server_exceptions=False)
    with caplog.at_level(logging.ERROR, logger="app.main"):
        response = client.get("/boom")

    assert response.status_code == 500
    assert response.json()["error_code"] == "INTERNAL_ERROR"
    [record] = [r for r in caplog.records if r.getMessage() == "unhandled exception"]
    assert record.path == "/boom"
    assert record.exc_info is not None
    assert "kaboom" in str(record.exc_info[1])


def test_redis_connection_failure_logs_a_warning(caplog):
    with caplog.at_level(logging.WARNING, logger="app.services.trending"):
        client = RedisClient(enabled=True, url="redis://127.0.0.1:1/0")

    assert client.is_available is False
    [record] = [r for r in caplog.records if "Redis connection failed" in r.getMessage()]
    assert record.levelno == logging.WARNING
    assert record.error
