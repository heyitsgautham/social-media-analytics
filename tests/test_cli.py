"""End-to-end tests for the Typer CLI against PostgreSQL."""

import pytest
from typer.testing import CliRunner

from app import cli
from app.db import get_session
from app.models import Base, Comment, Hashtag, Post, User
from app.services import trending
from app.services.trending import RedisClient, TrendingEngine

runner = CliRunner()


def _clear() -> None:
    with get_session() as db:
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(table.delete())


def _snapshot() -> tuple[list[str], list[str], list[str], int]:
    with get_session() as db:
        handles = sorted(h for (h,) in db.query(User.handle))
        tags = sorted(n for (n,) in db.query(Hashtag.name))
        contents = sorted(c for (c,) in db.query(Post.content))
        comments = db.query(Comment).count()
    return handles, tags, contents, comments


@pytest.fixture
def fresh_engine(monkeypatch):
    """Swap the global trending engine for one with no cache and no counters."""
    engine = TrendingEngine(window_minutes=60, cache=RedisClient(enabled=False))
    monkeypatch.setattr(trending, "trending_engine", engine)
    monkeypatch.setattr(cli, "trending_engine", engine)
    return engine


@pytest.fixture
def seeded(empty_db, fresh_engine):
    result = runner.invoke(
        cli.app, ["seed", "--users", "15", "--posts", "40", "--hashtags", "8", "--seed", "7"]
    )
    assert result.exit_code == 0, result.output
    return fresh_engine


def test_seed_writes_the_requested_rows(seeded):
    handles, tags, contents, _ = _snapshot()

    assert len(handles) == 15
    assert tags == sorted(
        ["ai", "ml", "datascience", "python", "fastapi", "django", "cloud", "devops"]
    )
    assert len(contents) == 40


def test_seed_with_the_same_seed_reproduces_the_data(empty_db):
    args = ["seed", "--users", "10", "--posts", "20", "--hashtags", "5", "--seed", "1337"]
    assert runner.invoke(cli.app, args).exit_code == 0
    first = _snapshot()

    _clear()

    assert runner.invoke(cli.app, args).exit_code == 0
    assert _snapshot() == first


def test_seed_without_a_seed_produces_different_data(empty_db):
    args = ["seed", "--users", "10", "--posts", "5", "--hashtags", "5"]
    assert runner.invoke(cli.app, args).exit_code == 0
    first_handles = _snapshot()[0]

    _clear()

    assert runner.invoke(cli.app, args).exit_code == 0
    assert _snapshot()[0] != first_handles
