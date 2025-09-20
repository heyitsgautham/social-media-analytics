"""
FastAPI routes for hashtag trending and recommendations.
"""
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.trending import trending_engine, recommendation_engine


# Response models
class TrendingHashtag(BaseModel):
    """Response model for trending hashtag."""
    hashtag: str = Field(..., description="Hashtag name")
    count: int = Field(..., description="Count within window")


class RecommendedHashtag(BaseModel):
    """Response model for recommended hashtag."""
    hashtag: str = Field(..., description="Hashtag name")
    cooccurrence_rate: float = Field(..., description="Co-occurrence rate (0.0-1.0)")


class TrendingResponse(BaseModel):
    """Response model for trending hashtags endpoint."""
    hashtags: List[TrendingHashtag] = Field(..., description="List of trending hashtags")
    window_minutes: int = Field(..., description="Window size used")
    total_count: int = Field(..., description="Total number of trending hashtags")


class RecommendationResponse(BaseModel):
    """Response model for hashtag recommendations."""
    target_hashtag: str = Field(..., description="Target hashtag")
    recommendations: List[RecommendedHashtag] = Field(..., description="List of recommended hashtags")
    min_cooccurrence_rate: float = Field(..., description="Minimum co-occurrence rate used")


class EngineStatus(BaseModel):
    """Response model for engine status."""
    total_hashtags: int = Field(..., description="Total hashtags in cache")
    total_buckets: int = Field(..., description="Total minute buckets")
    current_minute: int = Field(..., description="Current minute timestamp")
    window_minutes: int = Field(..., description="Window size in minutes")


# Router
router = APIRouter(prefix="/hashtags", tags=["hashtags"])


@router.get("/trending", response_model=TrendingResponse)
async def get_trending_hashtags(
    window: int = Query(60, ge=1, le=1440, description="Window size in minutes (1-1440)"),
    k: int = Query(10, ge=1, le=100, description="Number of top hashtags to return (1-100)")
) -> TrendingResponse:
    """
    Get trending hashtags within specified time window.
    
    Args:
        window: Time window in minutes (default: 60, max: 1440)
        k: Number of top hashtags to return (default: 10, max: 100)
        
    Returns:
        TrendingResponse with list of trending hashtags
    """
    try:
        trending_data = trending_engine.top(k=k, window_minutes=window)
        
        hashtags = [
            TrendingHashtag(hashtag=hashtag, count=count)
            for hashtag, count in trending_data
        ]
        
        return TrendingResponse(
            hashtags=hashtags,
            window_minutes=window,
            total_count=len(hashtags)
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve trending hashtags: {str(e)}"
        )


@router.get("/recommend/{hashtag}", response_model=RecommendationResponse)
async def get_hashtag_recommendations(
    hashtag: str,
    max_recommendations: int = Query(3, ge=1, le=10, description="Maximum recommendations (1-10)")
) -> RecommendationResponse:
    """
    Get hashtag recommendations based on co-occurrence patterns.
    
    Args:
        hashtag: Target hashtag name (without # symbol)
        max_recommendations: Maximum number of recommendations (default: 3, max: 10)
        
    Returns:
        RecommendationResponse with list of recommended hashtags
    """
    if not hashtag or not hashtag.strip():
        raise HTTPException(
            status_code=400,
            detail="Hashtag cannot be empty"
        )
    
    # Remove # if present
    clean_hashtag = hashtag.lstrip('#')
    
    try:
        recommendations_data = recommendation_engine.get_recommendations(
            hashtag=clean_hashtag,
            max_recommendations=max_recommendations
        )
        
        recommendations = [
            RecommendedHashtag(hashtag=rec_hashtag, cooccurrence_rate=rate)
            for rec_hashtag, rate in recommendations_data
        ]
        
        return RecommendationResponse(
            target_hashtag=clean_hashtag,
            recommendations=recommendations,
            min_cooccurrence_rate=recommendation_engine.min_cooccurrence_rate
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve recommendations for #{clean_hashtag}: {str(e)}"
        )


@router.get("/status", response_model=EngineStatus)
async def get_engine_status() -> EngineStatus:
    """
    Get trending engine status for health checks.
    
    Returns:
        EngineStatus with current engine metrics
    """
    try:
        status_data = trending_engine.get_status()
        return EngineStatus(**status_data)
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve engine status: {str(e)}"
        )


@router.post("/sync")
async def sync_from_database(
    minutes_back: int = Query(60, ge=1, le=1440, description="Minutes of data to sync (1-1440)")
) -> dict:
    """
    Sync trending engine with recent database data.
    
    Args:
        minutes_back: How many minutes back to load data (default: 60, max: 1440)
        
    Returns:
        Success message with sync details
    """
    try:
        from app.services.trending import populate_trending_from_db
        
        populate_trending_from_db(minutes_back=minutes_back)
        
        return {
            "message": f"Successfully synced trending data from last {minutes_back} minutes",
            "minutes_back": minutes_back,
            "status": "success"
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to sync trending data: {str(e)}"
        )
