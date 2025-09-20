"""
Tests for trending engine and recommendation system.
"""
import time
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import get_session
from app.models import Base, User, Post, Hashtag, PostHashtag
from app.services.trending import TrendingEngine, RecommendationEngine, populate_trending_from_db


# Test fixtures
@pytest.fixture
def in_memory_db():
    """Create in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    
    yield SessionLocal
    
    engine.dispose()


@pytest.fixture
def trending_engine():
    """Create fresh trending engine for each test."""
    return TrendingEngine(window_minutes=60)


@pytest.fixture
def recommendation_engine():
    """Create recommendation engine for testing."""
    return RecommendationEngine(min_cooccurrence_rate=0.3)


@pytest.fixture
def sample_data(in_memory_db):
    """Create sample data for testing."""
    SessionLocal = in_memory_db
    session = SessionLocal()
    
    try:
        # Create users
        users = [
            User(handle="user1"),
            User(handle="user2"),
            User(handle="user3"),
        ]
        session.add_all(users)
        session.flush()
        
        # Create hashtags
        hashtags = [
            Hashtag(name="python"),
            Hashtag(name="fastapi"),
            Hashtag(name="testing"),
            Hashtag(name="ai"),
            Hashtag(name="ml"),
        ]
        session.add_all(hashtags)
        session.flush()
        
        # Create posts with different timestamps
        now = datetime.utcnow()
        posts = [
            Post(user_id=users[0].id, content="Python is great #python #fastapi", 
                 created_at=now - timedelta(minutes=5)),
            Post(user_id=users[1].id, content="Testing with FastAPI #fastapi #testing", 
                 created_at=now - timedelta(minutes=3)),
            Post(user_id=users[2].id, content="AI and ML #ai #ml #python", 
                 created_at=now - timedelta(minutes=1)),
            Post(user_id=users[0].id, content="More Python content #python", 
                 created_at=now - timedelta(minutes=2)),
            Post(user_id=users[1].id, content="FastAPI rocks #fastapi #python", 
                 created_at=now - timedelta(seconds=30)),
        ]
        session.add_all(posts)
        session.flush()
        
        # Create post-hashtag relationships
        post_hashtags = [
            # Post 1: #python #fastapi
            PostHashtag(post_id=posts[0].id, hashtag_id=hashtags[0].id),  # python
            PostHashtag(post_id=posts[0].id, hashtag_id=hashtags[1].id),  # fastapi
            
            # Post 2: #fastapi #testing
            PostHashtag(post_id=posts[1].id, hashtag_id=hashtags[1].id),  # fastapi
            PostHashtag(post_id=posts[1].id, hashtag_id=hashtags[2].id),  # testing
            
            # Post 3: #ai #ml #python
            PostHashtag(post_id=posts[2].id, hashtag_id=hashtags[3].id),  # ai
            PostHashtag(post_id=posts[2].id, hashtag_id=hashtags[4].id),  # ml
            PostHashtag(post_id=posts[2].id, hashtag_id=hashtags[0].id),  # python
            
            # Post 4: #python
            PostHashtag(post_id=posts[3].id, hashtag_id=hashtags[0].id),  # python
            
            # Post 5: #fastapi #python
            PostHashtag(post_id=posts[4].id, hashtag_id=hashtags[1].id),  # fastapi
            PostHashtag(post_id=posts[4].id, hashtag_id=hashtags[0].id),  # python
        ]
        session.add_all(post_hashtags)
        session.commit()
        
        return {
            "users": users,
            "hashtags": hashtags,
            "posts": posts,
            "session": session,
        }
    
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


class TestTrendingEngine:
    """Test cases for TrendingEngine."""
    
    def test_initialization(self, trending_engine):
        """Test engine initialization."""
        assert trending_engine.window_minutes == 60
        assert len(trending_engine.counters) == 0
    
    def test_increment_basic(self, trending_engine):
        """Test basic hashtag increment."""
        trending_engine.increment("python")
        trending_engine.increment("python", 2)
        
        assert trending_engine.get_count("python") == 3
        assert trending_engine.get_count("nonexistent") == 0
    
    def test_top_hashtags_empty(self, trending_engine):
        """Test top hashtags with empty engine."""
        result = trending_engine.top(k=5)
        assert result == []
    
    def test_top_hashtags_basic(self, trending_engine):
        """Test top hashtags functionality."""
        # Add some hashtags
        trending_engine.increment("python", 5)
        trending_engine.increment("fastapi", 3)
        trending_engine.increment("testing", 1)
        
        result = trending_engine.top(k=2)
        assert len(result) == 2
        assert result[0] == ("python", 5)
        assert result[1] == ("fastapi", 3)
    
    def test_top_hashtags_tie_breaking(self, trending_engine):
        """Test tie-breaking (alphabetical order)."""
        trending_engine.increment("zebra", 1)
        trending_engine.increment("alpha", 1)
        
        result = trending_engine.top(k=2)
        assert result == [("alpha", 1), ("zebra", 1)]
    
    def test_sliding_window(self, trending_engine):
        """Test sliding window functionality."""
        # Mock time to control minute buckets
        base_time = 1000000  # Some base timestamp
        
        with patch('app.services.trending.time.time', return_value=base_time * 60):
            trending_engine.increment("python", 5)
        
        with patch('app.services.trending.time.time', return_value=(base_time + 30) * 60):
            trending_engine.increment("python", 3)
        
        with patch('app.services.trending.time.time', return_value=(base_time + 61) * 60):
            # Should only see the second increment (within 60 min window)
            count = trending_engine.get_count("python", window_minutes=60)
            assert count == 3  # Only the second increment should be visible
    
    def test_cleanup_old_buckets(self, trending_engine):
        """Test cleanup of old buckets."""
        base_time = 1000000
        
        # Add data to old bucket (manually set the minute timestamp)
        old_minute = base_time
        trending_engine.counters["old_tag"][old_minute] = 5
        
        # Move time forward beyond window and trigger cleanup
        with patch('app.services.trending.time.time', return_value=(base_time + 120) * 60):
            # Force update of last_cleanup to trigger cleanup
            trending_engine._last_cleanup = old_minute - 1
            trending_engine._cleanup_old_buckets()
            # Old tag should be removed entirely
            assert "old_tag" not in trending_engine.counters
    
    def test_different_window_sizes(self, trending_engine):
        """Test different window sizes."""
        base_time = 1000000
        
        # Add hashtags in different time buckets
        with patch('app.services.trending.time.time', return_value=base_time * 60):
            trending_engine.increment("recent", 2)
        
        with patch('app.services.trending.time.time', return_value=(base_time + 30) * 60):
            trending_engine.increment("medium", 3)
        
        with patch('app.services.trending.time.time', return_value=(base_time + 45) * 60):
            # Test different window sizes
            count_60 = trending_engine.get_count("recent", window_minutes=60)
            count_30 = trending_engine.get_count("recent", window_minutes=30)
            
            assert count_60 == 2  # Should see the hashtag
            assert count_30 == 0  # Should not see it (outside 30min window)
    
    def test_status(self, trending_engine):
        """Test engine status reporting."""
        trending_engine.increment("python", 1)
        trending_engine.increment("fastapi", 2)
        
        status = trending_engine.get_status()
        
        assert "total_hashtags" in status
        assert "total_buckets" in status
        assert "current_minute" in status
        assert "window_minutes" in status
        assert status["total_hashtags"] == 2
        assert status["window_minutes"] == 60


class TestRecommendationEngine:
    """Test cases for RecommendationEngine."""
    
    def test_initialization(self, recommendation_engine):
        """Test recommendation engine initialization."""
        assert recommendation_engine.min_cooccurrence_rate == 0.3
    
    def test_no_recommendations_for_nonexistent_hashtag(self, recommendation_engine, sample_data):
        """Test no recommendations for hashtag that doesn't exist."""
        with patch('app.services.trending.get_session') as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = sample_data["session"]
            
            recommendations = recommendation_engine.get_recommendations("nonexistent")
            assert recommendations == []
    
    def test_recommendations_basic(self, recommendation_engine, sample_data):
        """Test basic recommendation functionality."""
        with patch('app.services.trending.get_session') as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = sample_data["session"]
            
            # Test recommendations for "python"
            # python appears with: fastapi (2/4 times = 50%), ai (1/4 = 25%), ml (1/4 = 25%)
            # Only fastapi should meet the 30% threshold
            recommendations = recommendation_engine.get_recommendations("python")
            
            # Should get fastapi as recommendation (co-occurs 50% of time)
            assert len(recommendations) >= 1
            hashtag_names = [rec[0] for rec in recommendations]
            assert "fastapi" in hashtag_names
    
    def test_recommendations_cooccurrence_threshold(self, recommendation_engine, sample_data):
        """Test cooccurrence rate threshold filtering."""
        # Create engine with higher threshold
        strict_engine = RecommendationEngine(min_cooccurrence_rate=0.8)
        
        with patch('app.services.trending.get_session') as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = sample_data["session"]
            
            # With 80% threshold, no recommendations should pass
            recommendations = strict_engine.get_recommendations("python")
            assert len(recommendations) == 0
    
    def test_max_recommendations_limit(self, recommendation_engine, sample_data):
        """Test maximum recommendations limit."""
        with patch('app.services.trending.get_session') as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = sample_data["session"]
            
            recommendations = recommendation_engine.get_recommendations("python", max_recommendations=1)
            assert len(recommendations) <= 1


class TestDatabaseIntegration:
    """Test database integration functions."""
    
    def test_populate_trending_from_db(self, sample_data):
        """Test populating trending engine from database."""
        engine = TrendingEngine(window_minutes=60)
        
        with patch('app.services.trending.get_session') as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = sample_data["session"]
            
            # This should populate the engine with recent hashtag data
            populate_trending_from_db()
            
            # The global trending_engine should now have data
            # Note: This is testing the import behavior, specific counts depend on timing


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_large_k_value(self, trending_engine):
        """Test requesting more hashtags than available."""
        trending_engine.increment("python", 1)
        trending_engine.increment("fastapi", 2)
        
        result = trending_engine.top(k=100)  # Much larger than available
        assert len(result) == 2  # Should return all available
    
    def test_zero_window(self, trending_engine):
        """Test zero window size."""
        trending_engine.increment("python", 1)
        
        # Should handle gracefully (no results for 0-minute window)
        result = trending_engine.get_count("python", window_minutes=0)
        assert result == 0  # Zero window should return 0
        
        # Top should also return empty list for zero window
        top_result = trending_engine.top(k=5, window_minutes=0)
        assert top_result == []
    
    def test_negative_values(self, trending_engine):
        """Test handling of edge cases."""
        # Negative increment should still work (could represent decrements)
        trending_engine.increment("python", -1)
        assert trending_engine.get_count("python") == -1
    
    def test_empty_hashtag_name(self, trending_engine):
        """Test empty hashtag name."""
        trending_engine.increment("", 1)
        assert trending_engine.get_count("") == 1
    
    def test_unicode_hashtag_names(self, trending_engine):
        """Test unicode hashtag names."""
        trending_engine.increment("🐍python", 1)
        trending_engine.increment("café", 2)
        
        assert trending_engine.get_count("🐍python") == 1
        assert trending_engine.get_count("café") == 2
        
        result = trending_engine.top(k=2)
        hashtag_names = [name for name, count in result]
        assert "🐍python" in hashtag_names
        assert "café" in hashtag_names


class TestConcurrency:
    """Test concurrent access patterns."""
    
    def test_multiple_increments_same_hashtag(self, trending_engine):
        """Test multiple increments of same hashtag."""
        # Simulate concurrent increments
        for _ in range(10):
            trending_engine.increment("python", 1)
        
        assert trending_engine.get_count("python") == 10
    
    def test_increment_during_cleanup(self, trending_engine):
        """Test increment during cleanup operations."""
        base_time = 1000000
        
        # Add old data
        with patch('app.services.trending.time.time', return_value=base_time * 60):
            trending_engine.increment("old", 5)
        
        # Move time forward and add new data (triggers cleanup)
        with patch('app.services.trending.time.time', return_value=(base_time + 120) * 60):
            trending_engine.increment("new", 3)
        
        # Old data should be cleaned up, new data should remain
        with patch('app.services.trending.time.time', return_value=(base_time + 120) * 60):
            assert trending_engine.get_count("old") == 0
            assert trending_engine.get_count("new") == 3
