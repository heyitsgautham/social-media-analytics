"""Shared fixtures for tests that run against the real PostgreSQL database."""

import pytest

from app.db import get_session
from app.models import Base


@pytest.fixture
def empty_db():
    """Delete every row, children before parents, so a test starts from an empty schema."""
    with get_session() as db:
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(table.delete())
    yield
