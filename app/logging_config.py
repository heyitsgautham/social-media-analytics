"""Logging setup shared by the API and the CLI.

Every module logs through ``logging.getLogger(__name__)``.
``configure_logging`` attaches one handler to the ``app`` logger that writes
one JSON object per line, or plain text when LOG_FORMAT is "text".
Fields passed through ``extra=`` land as top-level JSON keys.
"""

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

from app.config import LOG_FORMAT, LOG_LEVEL

# Attributes every LogRecord carries, so anything else came from ``extra=``.
_STANDARD_ATTRS = frozenset(vars(logging.makeLogRecord({}))) | {"message", "asctime"}

_TEXT_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


class JsonFormatter(logging.Formatter):
    """Format a record as a single-line JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in vars(record).items():
            if key not in _STANDARD_ATTRS and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str | None = None, fmt: str | None = None) -> None:
    """Point the ``app`` logger at stderr. Safe to call more than once."""
    handler = logging.StreamHandler(sys.stderr)
    if (fmt or LOG_FORMAT) == "text":
        handler.setFormatter(logging.Formatter(_TEXT_FORMAT))
    else:
        handler.setFormatter(JsonFormatter())

    logger = logging.getLogger("app")
    logger.handlers = [handler]
    logger.setLevel((level or LOG_LEVEL).upper())
