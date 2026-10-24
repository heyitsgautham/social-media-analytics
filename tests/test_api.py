"""HTTP tests for the comments, reports and hashtags routes against PostgreSQL."""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.clock import utc_now
from app.db import get_session
from app.main import app
from app.models import Comment, Engagement, Hashtag, Post, PostHashtag, User
from app.routes import hashtags as hashtag_routes
from app.services import trending
from app.services.trending import RedisClient, TrendingEngine

client = TestClient(app)


@pytest.fixture
def engine(monkeypatch):
    fresh = TrendingEngine(window_minutes=60, cache=RedisClient(enabled=False))
    monkeypatch.setattr(trending, "trending_engine", fresh)
    monkeypatch.setattr(hashtag_routes, "trending_engine", fresh)
    return fresh


@pytest.fixture
def data(empty_db):
    """Two users, two posts tagged #python (one also #ai), and a three-deep reply chain."""
    now = utc_now()
    with get_session() as db:
        alice, bob = User(id=1, handle="alice"), User(id=2, handle="bob")
        python, ai = Hashtag(id=1, name="python"), Hashtag(id=2, name="ai")
        db.add_all([alice, bob, python, ai])
        db.flush()

        db.add_all(
            [
                Post(id=1, user_id=1, content="first", created_at=now - timedelta(minutes=10)),
                Post(id=2, user_id=2, content="second", created_at=now - timedelta(minutes=5)),
            ]
        )
        db.flush()
        db.add_all(
            [
                PostHashtag(post_id=1, hashtag_id=1),
                PostHashtag(post_id=1, hashtag_id=2),
                PostHashtag(post_id=2, hashtag_id=1),
            ]
        )
        db.add(Comment(id=1, post_id=1, user_id=2, body="root", upvotes=12))
        db.flush()
        db.add(Comment(id=2, post_id=1, user_id=1, parent_id=1, body="reply", upvotes=11))
        db.flush()
        db.add(Comment(id=3, post_id=1, user_id=2, parent_id=2, body="deeper", upvotes=10))
        db.add_all(
            [
                Engagement(user_id=2, target_type="post", target_id=1, kind="like"),
                Engagement(user_id=1, target_type="post", target_id=2, kind="like"),
                Engagement(user_id=2, target_type="comment", target_id=2, kind="like"),
            ]
        )


class TestCommentRoutes:
    def test_depth(self, data):
        response = client.get("/comments/depth/1")

        assert response.status_code == 200
        body = response.json()
        assert body["post_id"] == 1
        assert body["max_depth"] == 3
        assert body["total_comments"] == 3
        assert body["total_replies"] == 2

    def test_viral_chain_follows_the_upvoted_replies(self, data):
        response = client.get("/comments/viral/1")

        assert response.status_code == 200
        body = response.json()
        assert body["viral_criteria_met"] is True
        assert body["longest_chain_comments"] == [1, 2, 3]
        assert body["longest_chain_length"] == 3
        assert body["criteria"] == {"min_replies": 3, "min_upvotes": 10}

    def test_tree_nests_replies_under_their_parent(self, data):
        response = client.get("/comments/tree/1")

        assert response.status_code == 200
        [root] = response.json()["comments"]
        assert root["id"] == 1
        [reply] = root["children"]
        assert reply["id"] == 2
        assert [c["id"] for c in reply["children"]] == [3]

    @pytest.mark.parametrize("kind", ["depth", "viral", "tree"])
    def test_missing_post_is_404(self, empty_db, kind):
        response = client.get(f"/comments/{kind}/424242")

        assert response.status_code == 404
        assert response.json()["detail"] == "Post 424242 not found"

    def test_non_positive_post_id_is_422(self):
        assert client.get("/comments/depth/0").status_code == 422


class TestReportRoutes:
    def test_most_engaged_users_ranks_by_total_engagements(self, data):
        response = client.get("/reports/most-engaged-users?limit=5")

        assert response.status_code == 200
        body = response.json()
        assert body["total_count"] == 2
        alice, bob = body["users"]
        assert (alice["handle"], alice["total_engagements"]) == ("alice", 2)
        assert (alice["post_engagements"], alice["comment_engagements"]) == (1, 1)
        assert (bob["handle"], bob["total_engagements"]) == ("bob", 1)

    def test_top_hashtags_counts_unique_users(self, data):
        body = client.get("/reports/top-hashtags").json()

        names = [(h["hashtag_name"], h["unique_users"], h["total_posts"]) for h in body["hashtags"]]
        assert names == [("python", 2, 2), ("ai", 1, 1)]
        assert body["total_count"] == 2

    def test_fastest_growing_skips_tags_under_five_posts_in_total(self, data):
        body = client.get("/reports/fastest-growing-hashtags?hours=1").json()

        assert body["period_hours"] == 1
        assert body["hashtags"] == []

    def test_fastest_growing_rates_recent_against_total_posts(self, data):
        old = utc_now() - timedelta(days=2)
        with get_session() as db:
            for post_id in (10, 11, 12):
                db.add(Post(id=post_id, user_id=1, content="old", created_at=old))
                db.flush()
                db.add(PostHashtag(post_id=post_id, hashtag_id=1))

        [python] = client.get("/reports/fastest-growing-hashtags?hours=1").json()["hashtags"]

        assert python["hashtag_name"] == "python"
        assert (python["recent_posts"], python["total_posts"]) == (2, 5)
        assert python["growth_rate"] == 0.4
        assert python["recent_unique_users"] == 2

    @pytest.mark.parametrize(
        "url",
        [
            "/reports/most-engaged-users?limit=0",
            "/reports/top-hashtags?limit=101",
            "/reports/fastest-growing-hashtags?hours=169",
        ],
    )
    def test_out_of_range_query_is_422(self, url):
        assert client.get(url).status_code == 422


class TestHashtagRoutes:
    def test_sync_then_trending(self, data, engine):
        sync = client.post("/hashtags/sync?minutes_back=30")
        assert sync.status_code == 200
        assert sync.json()["status"] == "success"

        body = client.get("/hashtags/trending?window=30&k=5").json()
        assert body["hashtags"] == [
            {"hashtag": "python", "count": 2},
            {"hashtag": "ai", "count": 1},
        ]
        assert body["total_count"] == 2

    def test_status_reflects_synced_hashtags(self, data, engine):
        assert client.get("/hashtags/status").json()["total_hashtags"] == 0

        client.post("/hashtags/sync")
        status = client.get("/hashtags/status").json()
        assert status["total_hashtags"] == 2
        assert status["window_minutes"] == 60

    def test_recommendations_use_cooccurrence_rate(self, data):
        body = client.get("/hashtags/recommend/python").json()

        assert body["target_hashtag"] == "python"
        assert body["recommendations"] == [{"hashtag": "ai", "cooccurrence_rate": 0.5}]
        assert body["min_cooccurrence_rate"] == 0.3

    def test_recommend_strips_a_leading_hash(self, data):
        body = client.get("/hashtags/recommend/%23ai").json()

        assert body["target_hashtag"] == "ai"
        assert body["recommendations"] == [{"hashtag": "python", "cooccurrence_rate": 1.0}]

    def test_trending_rejects_a_window_over_one_day(self):
        assert client.get("/hashtags/trending?window=1441").status_code == 422
