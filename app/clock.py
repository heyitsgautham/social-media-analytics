"""The one place the app reads the current time."""

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return the current UTC time as a naive datetime.

    Every DateTime column stores naive UTC, so values compared with or written to
    them must be naive UTC too. This replaces datetime.utcnow(), which Python 3.12
    deprecates, without changing any stored or returned value.
    """
    return datetime.now(UTC).replace(tzinfo=None)
