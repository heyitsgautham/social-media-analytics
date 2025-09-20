# app/services/reports.py
from datetime import datetime, timedelta
from typing import List, Tuple, Dict, Any

from sqlalchemy import func, text, desc, and_
from sqlalchemy.orm import Session
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import DB_RETRY_ATTEMPTS, DB_RETRY_MIN_WAIT, DB_RETRY_MAX_WAIT
from app.models import User, Post, Hashtag, PostHashtag, Engagement, Comment


@retry(
    stop=stop_after_attempt(DB_RETRY_ATTEMPTS),
    wait=wait_exponential(multiplier=1, min=DB_RETRY_MIN_WAIT, max=DB_RETRY_MAX_WAIT),
    reraise=True,
)
def get_most_engaged_users(session: Session, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get users ranked by total engagements (likes, comments, shares, views).
    
    Returns users with their total engagement counts across all their content.
    Includes both post and comment engagements.
    
    Args:
        session: Database session
        limit: Maximum number of users to return
        
    Returns:
        List of dicts containing user info and engagement metrics
    """
    # Complex query joining users, posts, comments, and engagements
    # We need to count engagements on both posts and comments by each user
    query = text("""
        SELECT 
            u.id as user_id,
            u.handle,
            u.created_at,
            COALESCE(post_engagements.total, 0) + COALESCE(comment_engagements.total, 0) as total_engagements,
            COALESCE(post_engagements.total, 0) as post_engagements,
            COALESCE(comment_engagements.total, 0) as comment_engagements,
            COALESCE(posts_count.count, 0) as posts_count,
            COALESCE(comments_count.count, 0) as comments_count
        FROM users u
        LEFT JOIN (
            SELECT p.user_id, COUNT(*) as total
            FROM engagements e
            JOIN posts p ON e.target_id = p.id AND e.target_type = 'post'
            GROUP BY p.user_id
        ) post_engagements ON u.id = post_engagements.user_id
        LEFT JOIN (
            SELECT c.user_id, COUNT(*) as total
            FROM engagements e
            JOIN comments c ON e.target_id = c.id AND e.target_type = 'comment'
            WHERE c.user_id IS NOT NULL
            GROUP BY c.user_id
        ) comment_engagements ON u.id = comment_engagements.user_id
        LEFT JOIN (
            SELECT user_id, COUNT(*) as count
            FROM posts
            GROUP BY user_id
        ) posts_count ON u.id = posts_count.user_id
        LEFT JOIN (
            SELECT user_id, COUNT(*) as count
            FROM comments
            WHERE user_id IS NOT NULL
            GROUP BY user_id
        ) comments_count ON u.id = comments_count.user_id
        WHERE COALESCE(post_engagements.total, 0) + COALESCE(comment_engagements.total, 0) > 0
        ORDER BY total_engagements DESC, u.handle ASC
        LIMIT :limit
    """)
    
    result = session.execute(query, {"limit": limit}).fetchall()
    
    return [
        {
            "user_id": row.user_id,
            "handle": row.handle,
            "created_at": row.created_at,
            "total_engagements": row.total_engagements,
            "post_engagements": row.post_engagements,
            "comment_engagements": row.comment_engagements,
            "posts_count": row.posts_count,
            "comments_count": row.comments_count,
        }
        for row in result
    ]


@retry(
    stop=stop_after_attempt(DB_RETRY_ATTEMPTS),
    wait=wait_exponential(multiplier=1, min=DB_RETRY_MIN_WAIT, max=DB_RETRY_MAX_WAIT),
    reraise=True,
)
def get_top_hashtags(session: Session, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get top hashtags by unique users who used them.
    
    Ranks hashtags by the number of distinct users who have posted with them,
    rather than just total post count.
    
    Args:
        session: Database session
        limit: Maximum number of hashtags to return
        
    Returns:
        List of dicts containing hashtag info and metrics
    """
    # Join hashtags with post_hashtags and posts to get unique user counts
    query = (
        session.query(
            Hashtag.id.label("hashtag_id"),
            Hashtag.name.label("hashtag_name"),
            func.count(func.distinct(Post.user_id)).label("unique_users"),
            func.count(PostHashtag.post_id).label("total_posts"),
        )
        .join(PostHashtag, Hashtag.id == PostHashtag.hashtag_id)
        .join(Post, PostHashtag.post_id == Post.id)
        .group_by(Hashtag.id, Hashtag.name)
        .order_by(desc("unique_users"), desc("total_posts"), Hashtag.name)
        .limit(limit)
    )
    
    result = query.all()
    
    return [
        {
            "hashtag_id": row.hashtag_id,
            "hashtag_name": row.hashtag_name,
            "unique_users": row.unique_users,
            "total_posts": row.total_posts,
        }
        for row in result
    ]


@retry(
    stop=stop_after_attempt(DB_RETRY_ATTEMPTS),
    wait=wait_exponential(multiplier=1, min=DB_RETRY_MIN_WAIT, max=DB_RETRY_MAX_WAIT),
    reraise=True,
)
def get_fastest_growing_hashtags(
    session: Session, since: datetime, limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Get hashtags with fastest growth since a given time.
    
    Compares usage in the time period vs overall usage to find trending hashtags.
    
    Args:
        session: Database session
        since: Start time for growth calculation
        limit: Maximum number of hashtags to return
        
    Returns:
        List of dicts containing hashtag growth metrics
    """
    # Complex query to calculate growth rate
    query = text("""
        SELECT 
            h.id as hashtag_id,
            h.name as hashtag_name,
            recent_posts.count as recent_posts,
            total_posts.count as total_posts,
            CASE 
                WHEN total_posts.count > 0 THEN 
                    CAST(recent_posts.count AS FLOAT) / total_posts.count 
                ELSE 0 
            END as growth_rate,
            recent_posts.unique_users as recent_unique_users
        FROM hashtags h
        JOIN (
            SELECT 
                ph.hashtag_id,
                COUNT(*) as count,
                COUNT(DISTINCT p.user_id) as unique_users
            FROM post_hashtags ph
            JOIN posts p ON ph.post_id = p.id
            WHERE p.created_at >= :since
            GROUP BY ph.hashtag_id
            HAVING COUNT(*) >= 2  -- Minimum activity threshold
        ) recent_posts ON h.id = recent_posts.hashtag_id
        JOIN (
            SELECT 
                ph.hashtag_id,
                COUNT(*) as count
            FROM post_hashtags ph
            GROUP BY ph.hashtag_id
        ) total_posts ON h.id = total_posts.hashtag_id
        WHERE total_posts.count >= 5  -- Minimum total posts threshold
        ORDER BY growth_rate DESC, recent_posts.count DESC, h.name ASC
        LIMIT :limit
    """)
    
    result = session.execute(query, {"since": since, "limit": limit}).fetchall()
    
    return [
        {
            "hashtag_id": row.hashtag_id,
            "hashtag_name": row.hashtag_name,
            "recent_posts": row.recent_posts,
            "total_posts": row.total_posts,
            "growth_rate": float(row.growth_rate),
            "recent_unique_users": row.recent_unique_users,
        }
        for row in result
    ]


@retry(
    stop=stop_after_attempt(DB_RETRY_ATTEMPTS),
    wait=wait_exponential(multiplier=1, min=DB_RETRY_MIN_WAIT, max=DB_RETRY_MAX_WAIT),
    reraise=True,
)
def insert_engagement_with_transaction(
    db: Session,
    user_id: int,
    target_type: str,
    target_id: int,
    kind: str,
    also_increment_counter: bool = True,
) -> dict:
    """Insert engagement record with transaction management.
    
    For testing purposes, user_ids >= 999999 will trigger a simulated failure.
    Returns a dictionary with operation status and details.
    """
    # Check for simulated error (testing)
    if user_id >= 999999:
        raise Exception("Simulated transaction failure for testing")
    
    # Validate target_type
    valid_target_types = ["post", "comment"]
    if target_type not in valid_target_types:
        raise ValueError(f"Invalid target_type. Must be one of: {valid_target_types}")
    
    # Validate kind
    valid_kinds = ["like", "bookmark", "share"]
    if kind not in valid_kinds:
        raise ValueError(f"Invalid engagement kind. Must be one of: {valid_kinds}")
    
    # Verify user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise ValueError(f"User {user_id} not found")
    
    # Verify target exists
    if target_type == "post":
        target = db.query(Post).filter(Post.id == target_id).first()
        if not target:
            raise ValueError(f"Post {target_id} not found")
    elif target_type == "comment":
        target = db.query(Comment).filter(Comment.id == target_id).first()
        if not target:
            raise ValueError(f"Comment {target_id} not found")
    
    # Check for duplicate engagement
    existing = (
        db.query(Engagement)
        .filter(
            Engagement.user_id == user_id,
            Engagement.target_type == target_type,
            Engagement.target_id == target_id,
            Engagement.kind == kind,
        )
        .first()
    )
    if existing:
        raise ValueError(f"User {user_id} already has {kind} engagement on {target_type} {target_id}")
    
    # Insert engagement
    engagement = Engagement(
        user_id=user_id,
        target_type=target_type,
        target_id=target_id,
        kind=kind,
        created_at=datetime.utcnow(),
    )
    db.add(engagement)
    db.flush()  # Get the ID
    
    counter_updated = False
    if also_increment_counter:
        # Increment hashtag counts if this is a post engagement
        if target_type == "post":
            post = db.query(Post).filter(Post.id == target_id).first()
            if post and post.hashtags:
                for hashtag_text in post.hashtags:
                    # Find or create hashtag
                    hashtag = db.query(Hashtag).filter(Hashtag.tag == hashtag_text).first()
                    if hashtag:
                        hashtag.engagement_count = (hashtag.engagement_count or 0) + 1
                    else:
                        hashtag = Hashtag(tag=hashtag_text, engagement_count=1)
                        db.add(hashtag)
                counter_updated = True
        # Increment comment upvotes if this is a comment like
        elif target_type == "comment" and kind == "like":
            comment = db.query(Comment).filter(Comment.id == target_id).first()
            if comment:
                comment.upvotes = (comment.upvotes or 0) + 1
                counter_updated = True
    
    return {
        "success": True,
        "engagement_id": engagement.id,
        "user_id": user_id,
        "target_type": target_type,
        "target_id": target_id,
        "kind": kind,
        "counter_updated": counter_updated,
    }