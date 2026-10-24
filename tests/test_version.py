import tomllib
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import app as app_package
from app.main import app

client = TestClient(app)


def test_package_version_matches_pyproject():
    pyproject = tomllib.loads((Path(__file__).parent.parent / "pyproject.toml").read_text())
    assert app_package.__version__ == pyproject["project"]["version"]


def test_api_reports_the_package_version():
    assert app.version == app_package.__version__
    assert client.get("/").json()["version"] == app_package.__version__
    assert client.get("/openapi.json").json()["info"]["version"] == app_package.__version__


def test_health_reports_the_package_version():
    with (
        patch("app.routes.health.check_database_health", return_value={"status": "ok"}),
        patch("app.routes.health.check_redis_health", return_value={"status": "ok"}),
    ):
        assert client.get("/health/").json()["version"] == app_package.__version__
