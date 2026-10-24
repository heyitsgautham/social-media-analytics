from datetime import UTC, datetime, timedelta

from app.clock import utc_now


def test_utc_now_is_naive_utc():
    before = datetime.now(UTC).replace(tzinfo=None)
    now = utc_now()
    after = datetime.now(UTC).replace(tzinfo=None)

    assert now.tzinfo is None
    assert before <= now <= after
    assert abs(now - datetime.now(UTC).replace(tzinfo=None)) < timedelta(seconds=1)
