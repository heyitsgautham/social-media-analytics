"""
FastAPI routes for engagement reports and analytics.
"""

from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_session
from app.services.reports import (
    get_most_engaged_users,
    get_top_hashtags,
    get_fastest_growing_hashtags,
)


# Response models
class EngagedUser(BaseModel):
    """Response model for engaged user."""
    
    user_id: int = Field(..., description="User ID")
    handle: str = Field(..., description="User handle")
    created_at: datetime = Field(..., description="User creation timestamp")
    total_engagements: int = Field(..., description="Total engagements across all content")
    post_engagements: int = Field(..., description="Engagements on user's posts")
    comment_engagements: int = Field(..., description="Engagements on user's comments")
    posts_count: int = Field(..., description="Number of posts by user")
    comments_count: int = Field(..., description="Number of comments by user")


class TopHashtag(BaseModel):
    """Response model for top hashtag."""
    
    hashtag_id: int = Field(..., description="Hashtag ID")
    hashtag_name: str = Field(..., description="Hashtag name")
    unique_users: int = Field(..., description="Number of unique users who used this hashtag")
    total_posts: int = Field(..., description="Total posts with this hashtag")


class GrowingHashtag(BaseModel):
    """Response model for fastest growing hashtag."""
    
    hashtag_id: int = Field(..., description="Hashtag ID")
    hashtag_name: str = Field(..., description="Hashtag name")
    recent_posts: int = Field(..., description="Posts in recent period")
    total_posts: int = Field(..., description="Total posts ever")
    growth_rate: float = Field(..., description="Growth rate (recent/total)")
    recent_unique_users: int = Field(..., description="Unique users in recent period")


class MostEngagedUsersResponse(BaseModel):
    """Response model for most engaged users endpoint."""
    
    users: List[EngagedUser] = Field(..., description="List of most engaged users")
    total_count: int = Field(..., description="Total number of users with engagements")


class TopHashtagsResponse(BaseModel):
    """Response model for top hashtags endpoint."""
    
    hashtags: List[TopHashtag] = Field(..., description="List of top hashtags")
    total_count: int = Field(..., description="Total number of hashtags")


class FastestGrowingHashtagsResponse(BaseModel):
    """Response model for fastest growing hashtags endpoint."""
    
    hashtags: List[GrowingHashtag] = Field(..., description="List of fastest growing hashtags")
    period_start: datetime = Field(..., description="Start of growth period")
    period_hours: int = Field(..., description="Length of growth period in hours")


# Router
router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/most-engaged-users", response_model=MostEngagedUsersResponse)
async def get_most_engaged_users_endpoint(
    limit: int = Query(10, ge=1, le=100, description="Maximum number of users to return"),
) -> MostEngagedUsersResponse:
    """
    Get users ranked by total engagements across all their content.
    
    Returns users sorted by the sum of engagements on their posts and comments.
    Includes detailed engagement metrics for each user.
    """
    try:
        with get_session() as db:
            users_data = get_most_engaged_users(db, limit=limit)
            
            # Get total count for metadata
            # This is a simplified count - in production you might want to optimize
            all_users = get_most_engaged_users(db, limit=1000)  # Reasonable max for counting
            total_count = len(all_users)
            
            users = [EngagedUser(**user_data) for user_data in users_data]
            
            return MostEngagedUsersResponse(
                users=users,
                total_count=total_count
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving most engaged users: {str(e)}"
        )


@router.get("/top-hashtags", response_model=TopHashtagsResponse)
async def get_top_hashtags_endpoint(
    limit: int = Query(10, ge=1, le=100, description="Maximum number of hashtags to return"),
) -> TopHashtagsResponse:
    """
    Get hashtags ranked by number of unique users who used them.
    
    Returns hashtags sorted by distinct user count rather than total post count,
    giving insight into hashtag adoption across the user base.
    """
    try:
        with get_session() as db:
            hashtags_data = get_top_hashtags(db, limit=limit)
            
            # Get total count for metadata
            all_hashtags = get_top_hashtags(db, limit=1000)  # Reasonable max for counting
            total_count = len(all_hashtags)
            
            hashtags = [TopHashtag(**hashtag_data) for hashtag_data in hashtags_data]
            
            return TopHashtagsResponse(
                hashtags=hashtags,
                total_count=total_count
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving top hashtags: {str(e)}"
        )


@router.get("/fastest-growing-hashtags", response_model=FastestGrowingHashtagsResponse)
async def get_fastest_growing_hashtags_endpoint(
    hours: int = Query(24, ge=1, le=168, description="Number of hours for growth period (max 1 week)"),
    limit: int = Query(10, ge=1, le=50, description="Maximum number of hashtags to return"),
) -> FastestGrowingHashtagsResponse:
    """
    Get hashtags with fastest growth in recent period.
    
    Calculates growth rate as (recent posts / total posts) to identify trending hashtags.
    Only includes hashtags with minimum activity thresholds.
    """
    try:
        since = datetime.utcnow() - timedelta(hours=hours)
        
        with get_session() as db:
            hashtags_data = get_fastest_growing_hashtags(db, since=since, limit=limit)
            
            hashtags = [GrowingHashtag(**hashtag_data) for hashtag_data in hashtags_data]
            
            return FastestGrowingHashtagsResponse(
                hashtags=hashtags,
                period_start=since,
                period_hours=hours
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving fastest growing hashtags: {str(e)}"
        )