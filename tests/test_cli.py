"""End-to-end tests for the Typer CLI against PostgreSQL."""

import re

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


def _first_post_with_comments() -> int:
    with get_session() as db:
        return db.query(Comment.post_id).order_by(Comment.post_id).limit(1).scalar()


def test_hello():
    result = runner.invoke(cli.app, ["hello", "--name", "gk"])
    assert result.exit_code == 0
    assert result.output.strip() == "hello, gk"


def test_trending_sync_lists_hashtags_from_fresh_posts(seeded):
    result = runner.invoke(cli.app, ["trending", "--sync", "--k", "3"])

    assert result.exit_code == 0, result.output
    assert "Sync complete" in result.output
    assert "Top 3 trending hashtags" in result.output
    assert len(seeded.counters) == 8


def test_trending_auto_syncs_when_engine_is_empty(seeded):
    result = runner.invoke(cli.app, ["trending"])

    assert result.exit_code == 0, result.output
    assert "Auto-syncing from database" in result.output
    assert "Auto-sync complete" in result.output


def test_trending_reports_nothing_on_an_empty_database(empty_db, fresh_engine):
    result = runner.invoke(cli.app, ["trending", "--window", "5"])

    assert result.exit_code == 0
    assert "No trending hashtags found in the last 5 minutes" in result.output


def test_trending_rejects_an_out_of_range_window():
    result = runner.invoke(cli.app, ["trending", "--window", "0"])
    assert result.exit_code == 2


def test_trending_status_before_and_after_sync(seeded):
    before = runner.invoke(cli.app, ["trending-status"])
    assert "Engine has no active hashtags" in before.output

    runner.invoke(cli.app, ["trending", "--sync"])
    after = runner.invoke(cli.app, ["trending-status"])
    assert after.exit_code == 0
    assert "Total hashtags tracked: 8" in after.output
    assert "Engine is active" in after.output


def test_recommend_strips_the_hash_and_lists_cooccurring_tags(seeded):
    result = runner.invoke(cli.app, ["recommend", "#python", "--max", "2"])

    assert result.exit_code == 0, result.output
    assert "recommendations for #python" in result.output
    assert "co-occurrence" in result.output


def test_recommend_unknown_hashtag(seeded):
    result = runner.invoke(cli.app, ["recommend", "nosuchtag"])

    assert result.exit_code == 0
    assert "No recommendations found for #nosuchtag" in result.output


def test_comments_depth_and_viral_for_a_real_post(seeded):
    post_id = _first_post_with_comments()

    depth = runner.invoke(cli.app, ["comments", "depth", "--post", str(post_id)])
    assert depth.exit_code == 0, depth.output
    assert f"Comment Depth Analysis for Post {post_id}" in depth.output

    viral = runner.invoke(cli.app, ["comments", "viral", "-p", str(post_id)])
    assert viral.exit_code == 0, viral.output
    assert f"Viral Chain Analysis for Post {post_id}" in viral.output


def test_comments_missing_post_exits_with_an_error(empty_db):
    result = runner.invoke(cli.app, ["comments", "depth", "--post", "999999"])

    assert result.exit_code == 1
    assert "Post 999999 not found" in result.output


def test_comments_rejects_an_unknown_action():
    result = runner.invoke(cli.app, ["comments", "shout", "--post", "1"])

    assert result.exit_code == 1
    assert "Action must be either 'depth' or 'viral'" in result.output


def test_reports_users_lists_handles_with_totals(seeded):
    result = runner.invoke(cli.app, ["reports", "users", "--limit", "5"])

    assert result.exit_code == 0, result.output
    assert "Top 5 Most Engaged Users" in result.output
    assert "Total engagements:" in result.output


def test_reports_hashtags_lists_top_and_growing_tags(seeded):
    result = runner.invoke(cli.app, ["reports", "hashtags", "--limit", "3", "--hours", "1"])

    assert result.exit_code == 0, result.output
    assert "Top 3 Hashtags by Unique Users" in result.output
    assert "Fastest Growing Hashtags (last 1 hours)" in result.output


def test_reports_hashtags_keeps_the_percent_sign_next_to_the_growth_rate(seeded):
    result = runner.invoke(cli.app, ["reports", "hashtags", "--limit", "3"])

    header = next(line for line in result.output.splitlines() if "Growth" in line)
    rows = re.findall(r"^\d+\s+#\S+\s+(\S+)\s+\d+\s+\d+\s*$", result.output, re.MULTILINE)
    assert rows, result.output
    assert all(re.fullmatch(r"\d+\.\d%", growth) for growth in rows)
    row = next(line for line in result.output.splitlines() if rows[0] in line)
    assert row.index(rows[0]) == header.index("Growth")


def test_reports_users_on_an_empty_database(empty_db):
    result = runner.invoke(cli.app, ["reports", "users"])

    assert result.exit_code == 0
    assert "No engaged users found" in result.output


def test_reports_rejects_an_unknown_type():
    result = runner.invoke(cli.app, ["reports", "posts"])

    assert result.exit_code == 1
    assert "Report type must be either 'users' or 'hashtags'" in result.output


def test_refresh_adds_posts_to_a_seeded_database(seeded):
    result = runner.invoke(cli.app, ["refresh", "--posts", "12"])

    assert result.exit_code == 0, result.output
    assert "Added 12 fresh posts" in result.output
    with get_session() as db:
        assert db.query(Post).count() == 52


def test_refresh_needs_seed_data_first(empty_db, fresh_engine):
    result = runner.invoke(cli.app, ["refresh"])

    assert "Run 'seed' first" in result.output
    with get_session() as db:
        assert db.query(Post).count() == 0
