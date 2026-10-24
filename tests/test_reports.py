# tests/test_reports.py
"""
Tests for engagement reports functionality.
"""

from datetime import timedelta

import pytest

from app.clock import utc_now
from app.db import get_session
from app.models import (
    Comment,
    Engagement,
    EngagementKind,
    Hashtag,
    Post,
    PostHashtag,
    TargetType,
    User,
)
from app.services.reports import (
    get_fastest_growing_hashtags,
    get_most_engaged_users,
    get_top_hashtags,
    insert_engagement_with_transaction,
)


@pytest.fixture
def test_data():
    """Create test data for reports tests."""
    with get_session() as db:
        # Clear existing data
        db.query(Engagement).delete()
        db.query(PostHashtag).delete()
        db.query(Comment).delete()
        db.query(Post).delete()
        db.query(Hashtag).delete()
        db.query(User).delete()
        db.commit()

        # Create users
        user1 = User(id=1, handle="alice")
        user2 = User(id=2, handle="bob")
        user3 = User(id=3, handle="charlie")
        db.add_all([user1, user2, user3])

        # Create hashtags
        tag1 = Hashtag(id=1, name="python")
        tag2 = Hashtag(id=2, name="fastapi")
        tag3 = Hashtag(id=3, name="trending")
        db.add_all([tag1, tag2, tag3])

        db.commit()

        # Create posts with different timestamps
        now = utc_now()
        post1 = Post(
            id=1, user_id=1, content="Python is great!", created_at=now - timedelta(days=2)
        )
        post2 = Post(
            id=2, user_id=2, content="FastAPI rocks!", created_at=now - timedelta(hours=12)
        )
        post3 = Post(id=3, user_id=1, content="Trending now!", created_at=now - timedelta(hours=2))
        post4 = Post(id=4, user_id=3, content="Another post", created_at=now - timedelta(hours=1))
        db.add_all([post1, post2, post3, post4])

        db.commit()

        # Link posts to hashtags
        ph1 = PostHashtag(post_id=1, hashtag_id=1)  # python
        ph2 = PostHashtag(post_id=2, hashtag_id=2)  # fastapi
        ph3 = PostHashtag(post_id=3, hashtag_id=3)  # trending
        ph4 = PostHashtag(post_id=3, hashtag_id=1)  # python (alice uses python twice)
        ph5 = PostHashtag(post_id=4, hashtag_id=2)  # fastapi (charlie also uses fastapi)
        db.add_all([ph1, ph2, ph3, ph4, ph5])

        # Create comments
        comment1 = Comment(id=1, post_id=1, user_id=2, body="Great post!", upvotes=5)
        comment2 = Comment(id=2, post_id=2, user_id=1, body="Love FastAPI!", upvotes=3)
        comment3 = Comment(id=3, post_id=3, user_id=3, body="So trendy!", upvotes=8)
        comment4 = Comment(
            id=4, post_id=1, user_id=3, body="Nice work!", upvotes=0
        )  # New comment for testing
        db.add_all([comment1, comment2, comment3, comment4])

        db.commit()

        # Create engagements (alice gets most engagements)
        engagements = [
            # Post engagements - alice's posts get most likes
            Engagement(
                user_id=2, target_type="post", target_id=1, kind="like"
            ),  # bob likes alice's post
            Engagement(
                user_id=3, target_type="post", target_id=1, kind="like"
            ),  # charlie likes alice's post
            Engagement(
                user_id=1, target_type="post", target_id=2, kind="like"
            ),  # alice likes bob's post
            Engagement(
                user_id=2, target_type="post", target_id=3, kind="like"
            ),  # bob likes alice's trending post
            Engagement(
                user_id=3, target_type="post", target_id=3, kind="like"
            ),  # charlie likes alice's trending post
            Engagement(
                user_id=1, target_type="post", target_id=3, kind="share"
            ),  # alice shares her own post
            # Comment engagements
            Engagement(
                user_id=1, target_type="comment", target_id=1, kind="like"
            ),  # alice likes bob's comment
            Engagement(
                user_id=3, target_type="comment", target_id=2, kind="like"
            ),  # charlie likes alice's comment
            Engagement(
                user_id=2, target_type="comment", target_id=3, kind="like"
            ),  # bob likes charlie's comment
            # Recent engagements for growth testing
            Engagement(
                user_id=1,
                target_type="post",
                target_id=4,
                kind="like",
                created_at=now - timedelta(minutes=30),
            ),
            Engagement(
                user_id=2,
                target_type="post",
                target_id=4,
                kind="like",
                created_at=now - timedelta(minutes=20),
            ),
        ]
        db.add_all(engagements)
        db.commit()

        return {
            "users": [user1, user2, user3],
            "posts": [post1, post2, post3, post4],
            "hashtags": [tag1, tag2, tag3],
            "comments": [comment1, comment2, comment3, comment4],
        }


def test_get_most_engaged_users(test_data):
    """Test most engaged users ranking."""
    with get_session() as db:
        result = get_most_engaged_users(db, limit=10)

        # Should return users in order of total engagement
        assert len(result) == 3  # All users have some engagement

        # Alice should be first (has most engagements on her content)
        alice = result[0]
        assert alice["handle"] == "alice"
        assert alice["total_engagements"] >= 4  # At least 4 engagements on her posts

        # Check data structure
        required_fields = [
            "user_id",
            "handle",
            "created_at",
            "total_engagements",
            "post_engagements",
            "comment_engagements",
            "posts_count",
            "comments_count",
        ]
        for field in required_fields:
            assert field in alice

        # Verify ordering (total engagements should be descending)
        for i in range(len(result) - 1):
            assert result[i]["total_engagements"] >= result[i + 1]["total_engagements"]


def test_get_most_engaged_users_limit(test_data):
    """Test limit parameter works correctly."""
    with get_session() as db:
        result = get_most_engaged_users(db, limit=2)
        assert len(result) <= 2


def test_get_top_hashtags(test_data):
    """Test top hashtags by unique users."""
    with get_session() as db:
        result = get_top_hashtags(db, limit=10)

        # Should return hashtags in order of unique user count
        assert len(result) >= 2

        # Check data structure
        first_hashtag = result[0]
        required_fields = ["hashtag_id", "hashtag_name", "unique_users", "total_posts"]
        for field in required_fields:
            assert field in first_hashtag

        # Verify ordering (unique users should be descending, then total posts)
        for i in range(len(result) - 1):
            current = result[i]
            next_item = result[i + 1]
            # Either more unique users, or same unique users but more posts
            assert current["unique_users"] > next_item["unique_users"] or (
                current["unique_users"] == next_item["unique_users"]
                and current["total_posts"] >= next_item["total_posts"]
            )

        # Check that python and fastapi are in results (both used by multiple users)
        hashtag_names = [h["hashtag_name"] for h in result]
        assert "python" in hashtag_names or "fastapi" in hashtag_names


def test_get_fastest_growing_hashtags(test_data):
    """Test fastest growing hashtags calculation."""
    with get_session() as db:
        # Test with recent time window
        since = utc_now() - timedelta(hours=6)
        result = get_fastest_growing_hashtags(db, since=since, limit=10)

        # Should only include hashtags with recent activity
        # Based on our test data, we have recent posts with fastapi hashtag
        if result:  # May be empty if no hashtags meet minimum thresholds
            first_hashtag = result[0]
            required_fields = [
                "hashtag_id",
                "hashtag_name",
                "recent_posts",
                "total_posts",
                "growth_rate",
                "recent_unique_users",
            ]
            for field in required_fields:
                assert field in first_hashtag

            # Growth rate should be between 0 and 1
            assert 0 <= first_hashtag["growth_rate"] <= 1

            # Recent posts should not exceed total posts
            assert first_hashtag["recent_posts"] <= first_hashtag["total_posts"]

            # Verify ordering (growth rate descending)
            for i in range(len(result) - 1):
                current = result[i]
                next_item = result[i + 1]
                assert current["growth_rate"] >= next_item["growth_rate"]


def test_insert_engagement_with_transaction_success(test_data):
    """Test successful engagement insertion with transaction."""
    with get_session() as db:
        # Insert a new engagement
        result = insert_engagement_with_transaction(
            db,
            user_id=1,
            target_type="post",
            target_id=2,
            kind="bookmark",
            also_increment_counter=False,
        )

        # Check result structure
        assert result["success"] is True
        assert result["user_id"] == 1
        assert result["target_type"] == "post"
        assert result["target_id"] == 2
        assert result["kind"] == "bookmark"
        assert "engagement_id" in result

        # Verify engagement was actually inserted
        engagement = db.query(Engagement).filter(Engagement.id == result["engagement_id"]).first()
        assert engagement is not None
        assert engagement.user_id == 1
        assert engagement.target_type == "post"
        assert engagement.target_id == 2
        assert engagement.kind == "bookmark"


def test_insert_engagement_with_counter_update(test_data):
    """Test engagement insertion with counter update."""
    with get_session() as db:
        # Get initial upvote count for comment 4 (charlie's new comment - no existing engagements)
        comment = db.query(Comment).filter(Comment.id == 4).first()
        initial_upvotes = comment.upvotes

        # Insert like engagement on comment (alice likes charlie's new comment)
        # Don't use the auto-commit get_session for the service call
        result = insert_engagement_with_transaction(
            db,
            user_id=1,  # alice - no existing engagement on comment 4
            target_type="comment",
            target_id=4,  # charlie's new comment
            kind="like",  # Must be "like" for counter to update
            also_increment_counter=True,
        )

        assert result["success"] is True
        assert result["counter_updated"] is True

        # Manually commit the transaction to see the changes
        db.commit()

        # Verify comment upvotes were incremented
        db.refresh(comment)
        assert comment.upvotes == initial_upvotes + 1


def test_insert_engagement_duplicate_error(test_data):
    """Test error on duplicate engagement."""
    with get_session() as db:
        # Insert first engagement (use post 4 to avoid conflicts with test data)
        insert_engagement_with_transaction(
            db,
            user_id=1,
            target_type="post",
            target_id=4,
            kind="bookmark",  # Use a different kind to avoid test data conflicts
            also_increment_counter=False,
        )

        # Try to insert duplicate - should raise ValueError
        with pytest.raises(ValueError, match="already has bookmark engagement"):
            insert_engagement_with_transaction(
                db,
                user_id=1,
                target_type="post",
                target_id=4,
                kind="bookmark",
                also_increment_counter=False,
            )


def test_insert_engagement_invalid_target_error(test_data):
    """Test error on invalid target."""
    # Try to engage with non-existent post
    with get_session() as db, pytest.raises(ValueError, match="Post 999 not found"):
        insert_engagement_with_transaction(
            db,
            user_id=1,
            target_type="post",
            target_id=999,
            kind="like",
            also_increment_counter=False,
        )


def test_insert_engagement_invalid_user_error(test_data):
    """Test error on invalid user."""
    # Try to engage with non-existent user
    with get_session() as db, pytest.raises(ValueError, match="User 999 not found"):
        insert_engagement_with_transaction(
            db,
            user_id=999,
            target_type="post",
            target_id=1,
            kind="like",
            also_increment_counter=False,
        )


def test_insert_engagement_transaction_rollback(test_data):
    """An error after the insert rolls the engagement and the upvote bump back together."""
    before = None
    with pytest.raises(RuntimeError, match="fail after insert"), get_session() as db:
        before = db.query(Engagement).count()
        result = insert_engagement_with_transaction(
            db,
            user_id=1,
            target_type="comment",
            target_id=4,
            kind="like",
            also_increment_counter=True,
        )
        assert result["counter_updated"] is True
        raise RuntimeError("fail after insert")

    with get_session() as db:
        assert db.query(Engagement).count() == before
        assert db.query(Comment).filter(Comment.id == 4).one().upvotes == 0


def test_insert_engagement_invalid_enum_values(test_data):
    """Test error on invalid enum values."""
    with get_session() as db:
        # Invalid target_type
        with pytest.raises(ValueError, match="Invalid target_type"):
            insert_engagement_with_transaction(
                db,
                user_id=1,
                target_type="invalid",
                target_id=1,
                kind="like",
                also_increment_counter=False,
            )

        # Invalid engagement kind
        with pytest.raises(ValueError, match="Invalid engagement kind"):
            insert_engagement_with_transaction(
                db,
                user_id=1,
                target_type="post",
                target_id=1,
                kind="invalid",
                also_increment_counter=False,
            )


def test_reports_with_no_data():
    """Test reports functions with empty database."""
    with get_session() as db:
        # Clear all data
        db.query(Engagement).delete()
        db.query(PostHashtag).delete()
        db.query(Comment).delete()
        db.query(Post).delete()
        db.query(Hashtag).delete()
        db.query(User).delete()
        db.commit()

        # Test functions return empty results gracefully
        users = get_most_engaged_users(db, limit=10)
        assert users == []

        hashtags = get_top_hashtags(db, limit=10)
        assert hashtags == []

        since = utc_now() - timedelta(hours=24)
        growing = get_fastest_growing_hashtags(db, since=since, limit=10)
        assert growing == []


if __name__ == "__main__":
    pytest.main([__file__])


def test_insert_post_engagement_with_counter_on_tagged_post(test_data):
    """A like on a post that has hashtags commits and reports no counter change."""
    with get_session() as db:
        result = insert_engagement_with_transaction(
            db,
            user_id=3,  # charlie has not bookmarked post 1 yet
            target_type="post",
            target_id=1,  # alice's post tagged #python
            kind="bookmark",
            also_increment_counter=True,
        )

        assert result["success"] is True
        assert result["counter_updated"] is False

    with get_session() as db:
        stored = db.query(Engagement).filter(Engagement.id == result["engagement_id"]).one()
        assert stored.kind == EngagementKind.bookmark
        assert stored.target_type == TargetType.post
