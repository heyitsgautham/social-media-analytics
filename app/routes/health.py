"""
Health check endpoints for monitoring system status.
"""

from datetime import datetime
from typing import Dict, Any

from fastapi import APIRouter
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db import get_session
from app.services.trending import redis_client

router = APIRouter(prefix="/health", tags=["health"])


def check_database_health() -> Dict[str, str]:
    """
    Check database connectivity and health.
    
    Returns:
        Dict with status and optional error details
    """
    try:
        with get_session() as db:
            # Simple connectivity test
            result = db.execute(text("SELECT 1")).scalar()
            if result == 1:
                return {"status": "ok"}
            else:
                return {"status": "down", "error": "Unexpected query result"}
    except SQLAlchemyError as e:
        return {"status": "down", "error": f"Database error: {str(e)}"}
    except Exception as e:
        return {"status": "down", "error": f"Connection error: {str(e)}"}


def check_redis_health() -> Dict[str, str]:
    """
    Check Redis connectivity and health.
    
    Returns:
        Dict with status and optional error details
    """
    if not redis_client._enabled:
        return {"status": "disabled"}
    
    if not redis_client.is_available:
        return {"status": "down", "error": "Redis client not available"}
    
    try:
        if redis_client.ping():
            return {"status": "ok"}
        else:
            return {"status": "down", "error": "Redis ping failed"}
    except Exception as e:
        return {"status": "down", "error": f"Redis error: {str(e)}"}


@router.get("/")
async def health_check() -> Dict[str, Any]:
    """
    Comprehensive health check endpoint.
    
    Returns system status including database, Redis, and overall health.
    
    Returns:
        Dict containing:
        - status: "ok" | "degraded" | "down"
        - db: database health status
        - redis: Redis health status
        - version: API version
        - timestamp: current UTC timestamp
    """
    # Check database health
    db_health = check_database_health()
    
    # Check Redis health
    redis_health = check_redis_health()
    
    # Determine overall status
    overall_status = "ok"
    
    if db_health["status"] == "down":
        overall_status = "down"  # Database is critical
    elif redis_health["status"] == "down":
        overall_status = "degraded"  # Redis down is degraded, not critical
    
    return {
        "status": overall_status,
        "db": db_health,
        "redis": redis_health,
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/db")
async def database_health() -> Dict[str, Any]:
    """
    Database-specific health check.
    
    Returns:
        Dict with detailed database health information
    """
    health_status = check_database_health()
    
    try:
        with get_session() as db:
            # Additional database checks
            user_count = db.execute(text("SELECT COUNT(*) FROM users")).scalar()
            post_count = db.execute(text("SELECT COUNT(*) FROM posts")).scalar()
            hashtag_count = db.execute(text("SELECT COUNT(*) FROM hashtags")).scalar()
            
            health_status.update({
                "tables": {
                    "users": user_count,
                    "posts": post_count,
                    "hashtags": hashtag_count,
                },
                "timestamp": datetime.utcnow().isoformat(),
            })
    except Exception as e:
        health_status["error"] = f"Extended check failed: {str(e)}"
    
    return health_status


@router.get("/redis")
async def redis_health() -> Dict[str, Any]:
    """
    Redis-specific health check.
    
    Returns:
        Dict with detailed Redis health information
    """
    health_status = check_redis_health()
    
    if redis_client.is_available:
        try:
            # Test Redis operations
            test_key = "health_check_test"
            test_value = "test_value"
            
            # Test SET operation
            set_success = redis_client.set(test_key, test_value, 60)
            
            # Test GET operation
            retrieved_value = redis_client.get(test_key)
            
            # Test DELETE operation
            delete_success = redis_client.delete(test_key)
            
            health_status.update({
                "operations": {
                    "set": set_success,
                    "get": retrieved_value == test_value,
                    "delete": delete_success,
                },
                "timestamp": datetime.utcnow().isoformat(),
            })
        except Exception as e:
            health_status["error"] = f"Redis operations test failed: {str(e)}"
    
    return health_status