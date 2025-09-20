"""
Trending Engine for Social Media Analytics.

Implements real-time hashtag trending with sliding window counts and
recommendation engine for co-occurring hashtags.
"""

import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Hashtag, Post, PostHashtag


class TrendingEngine:
    """
    Real-time hashtag trending engine using sliding window counters.

    Maintains per-minute counters and rotates buckets to keep last W minutes.
    Provides top(k, window=W) API and hashtag recommendations.
    """

    def __init__(self, window_minutes: int = 60):
        """
        Initialize trending engine.

        Args:
            window_minutes: Size of sliding window in minutes (default: 60)
        """
        self.window_minutes = window_minutes
        # Structure: {hashtag_name: {minute_timestamp: count}}
        self.counters: Dict[str, Dict[int, int]] = defaultdict(lambda: defaultdict(int))
        self._last_cleanup = int(time.time() // 60)

    def _get_minute_timestamp(self) -> int:
        """Get current minute as timestamp (rounded down)."""
        return int(time.time() // 60)

    def _cleanup_old_buckets(self) -> None:
        """Remove buckets older than window_minutes."""
        current_minute = self._get_minute_timestamp()
        cutoff = current_minute - self.window_minutes

        # Only cleanup if we haven't done it recently (avoid excessive work)
        if current_minute > self._last_cleanup:
            for hashtag in list(self.counters.keys()):
                buckets = self.counters[hashtag]
                old_minutes = [minute for minute in buckets if minute < cutoff]
                for minute in old_minutes:
                    del buckets[minute]

                # Remove hashtag entry if no buckets remain
                if not buckets:
                    del self.counters[hashtag]

            self._last_cleanup = current_minute

    def increment(self, hashtag: str, count: int = 1) -> None:
        """
        Increment counter for hashtag in current minute bucket.

        Args:
            hashtag: Name of hashtag (without #)
            count: Count to add (default: 1)
        """
        self._cleanup_old_buckets()
        current_minute = self._get_minute_timestamp()
        self.counters[hashtag][current_minute] += count

    def get_count(self, hashtag: str, window_minutes: Optional[int] = None) -> int:
        """
        Get total count for hashtag within window.

        Args:
            hashtag: Name of hashtag
            window_minutes: Window size (uses instance default if None)

        Returns:
            Total count within window
        """
        self._cleanup_old_buckets()

        if hashtag not in self.counters:
            return 0

        window = window_minutes if window_minutes is not None else self.window_minutes

        # Handle zero or negative window
        if window <= 0:
            return 0

        current_minute = self._get_minute_timestamp()
        cutoff = current_minute - window

        total = 0
        for minute, count in self.counters[hashtag].items():
            if minute >= cutoff:
                total += count

        return total

    def top(self, k: int = 10, window_minutes: Optional[int] = None) -> List[Tuple[str, int]]:
        """
        Get top k hashtags by count within window.

        Args:
            k: Number of top hashtags to return
            window_minutes: Window size (uses instance default if None)

        Returns:
            List of (hashtag, count) tuples, sorted by count descending
        """
        self._cleanup_old_buckets()

        window = window_minutes if window_minutes is not None else self.window_minutes

        # Handle zero or negative window
        if window <= 0:
            return []

        current_minute = self._get_minute_timestamp()
        cutoff = current_minute - window

        hashtag_counts = []

        for hashtag, buckets in self.counters.items():
            total = sum(count for minute, count in buckets.items() if minute >= cutoff)
            if total > 0:
                hashtag_counts.append((hashtag, total))

        # Sort by count descending, then by hashtag name for tie-breaking
        hashtag_counts.sort(key=lambda x: (-x[1], x[0]))

        return hashtag_counts[:k]

    def get_status(self) -> Dict[str, int]:
        """
        Get engine status for health checks.

        Returns:
            Dictionary with status metrics
        """
        self._cleanup_old_buckets()

        total_hashtags = len(self.counters)
        total_buckets = sum(len(buckets) for buckets in self.counters.values())
        current_minute = self._get_minute_timestamp()

        return {
            "total_hashtags": total_hashtags,
            "total_buckets": total_buckets,
            "current_minute": current_minute,
            "window_minutes": self.window_minutes,
        }


class RecommendationEngine:
    """
    Hashtag recommendation engine based on co-occurrence patterns.

    Recommends hashtags that co-occur ≥30% of the time with given hashtag.
    """

    def __init__(self, min_cooccurrence_rate: float = 0.3):
        """
        Initialize recommendation engine.

        Args:
            min_cooccurrence_rate: Minimum co-occurrence rate threshold (default: 0.3)
        """
        self.min_cooccurrence_rate = min_cooccurrence_rate

    def get_recommendations(
        self, hashtag: str, max_recommendations: int = 3
    ) -> List[Tuple[str, float]]:
        """
        Get hashtag recommendations based on co-occurrence.

        Args:
            hashtag: Target hashtag name
            max_recommendations: Maximum number of recommendations

        Returns:
            List of (hashtag, cooccurrence_rate) tuples
        """
        with get_session() as db:
            return self._compute_recommendations(db, hashtag, max_recommendations)

    def _compute_recommendations(
        self, db: Session, hashtag: str, max_recommendations: int
    ) -> List[Tuple[str, float]]:
        """
        Compute recommendations using database co-occurrence analysis.

        Args:
            db: Database session
            hashtag: Target hashtag name
            max_recommendations: Maximum recommendations to return

        Returns:
            List of (hashtag, cooccurrence_rate) tuples
        """
        # Find the target hashtag
        target_hashtag = db.query(Hashtag).filter(Hashtag.name == hashtag).first()
        if not target_hashtag:
            return []

        # Get total posts containing target hashtag
        total_target_posts = (
            db.query(func.count(PostHashtag.post_id))
            .filter(PostHashtag.hashtag_id == target_hashtag.id)
            .scalar()
        )

        if total_target_posts == 0:
            return []

        # Find co-occurring hashtags with their counts
        cooccurrence_query = text(
            """
            SELECT h.name, COUNT(DISTINCT ph1.post_id) as cooccurrence_count
            FROM post_hashtags ph1
            JOIN post_hashtags ph2 ON ph1.post_id = ph2.post_id
            JOIN hashtags h ON ph2.hashtag_id = h.id
            WHERE ph1.hashtag_id = :target_hashtag_id
              AND ph2.hashtag_id != :target_hashtag_id
            GROUP BY h.id, h.name
            ORDER BY cooccurrence_count DESC
        """
        )

        result = db.execute(cooccurrence_query, {"target_hashtag_id": target_hashtag.id}).fetchall()

        recommendations = []
        for row in result:
            hashtag_name, cooccurrence_count = row
            cooccurrence_rate = cooccurrence_count / total_target_posts

            if cooccurrence_rate >= self.min_cooccurrence_rate:
                recommendations.append((hashtag_name, cooccurrence_rate))

        return recommendations[:max_recommendations]


# Global instances for convenience
trending_engine = TrendingEngine()
recommendation_engine = RecommendationEngine()


def populate_trending_from_db(minutes_back: int = 60) -> None:
    """
    Populate trending engine with recent hashtag data from database.

    This is useful for initialization or recovery scenarios.

    Args:
        minutes_back: How many minutes back to load data
    """
    cutoff_time = datetime.utcnow() - timedelta(minutes=minutes_back)

    with get_session() as db:
        # Query posts and their hashtags from the last N minutes
        posts_with_hashtags = (
            db.query(Post.created_at, Hashtag.name)
            .join(PostHashtag, Post.id == PostHashtag.post_id)
            .join(Hashtag, PostHashtag.hashtag_id == Hashtag.id)
            .filter(Post.created_at >= cutoff_time)
            .all()
        )

        # Group by minute and hashtag
        minute_hashtag_counts = Counter()

        for created_at, hashtag_name in posts_with_hashtags:
            # Convert to minute timestamp
            minute_timestamp = int(created_at.timestamp() // 60)
            minute_hashtag_counts[(minute_timestamp, hashtag_name)] += 1

        # Populate trending engine
        for (minute_timestamp, hashtag_name), count in minute_hashtag_counts.items():
            # Set the count directly in the appropriate bucket
            trending_engine.counters[hashtag_name][minute_timestamp] = count


def simulate_realtime_updates() -> None:
    """
    Simulate real-time hashtag updates by processing recent posts.

    In a real system, this would be triggered by post creation events.
    """
    # Get posts from the last minute
    one_minute_ago = datetime.utcnow() - timedelta(minutes=1)

    with get_session() as db:
        recent_posts = (
            db.query(Hashtag.name, func.count(Post.id).label("count"))
            .join(PostHashtag, Hashtag.id == PostHashtag.hashtag_id)
            .join(Post, PostHashtag.post_id == Post.id)
            .filter(Post.created_at >= one_minute_ago)
            .group_by(Hashtag.name)
            .all()
        )

        for hashtag_name, count in recent_posts:
            trending_engine.increment(hashtag_name, count)
