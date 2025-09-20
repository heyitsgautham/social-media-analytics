"""
Main FastAPI application for Social Media Analytics Platform.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.hashtags import router as hashtags_router


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.
    
    Returns:
        Configured FastAPI app instance
    """
    app = FastAPI(
        title="Social Media Analytics API",
        description="Real-time hashtag trending and engagement analytics platform",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include routers
    app.include_router(hashtags_router)
    
    return app


# Create the application instance
app = create_app()


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "message": "Social Media Analytics API",
        "status": "healthy",
        "version": "1.0.0"
    }


@app.get("/health")
async def health_check():
    """Detailed health check endpoint."""
    from app.services.trending import trending_engine
    
    try:
        engine_status = trending_engine.get_status()
        return {
            "status": "healthy",
            "services": {
                "trending_engine": {
                    "status": "active",
                    "metrics": engine_status
                },
                "database": {
                    "status": "connected"  # TODO: Add actual DB health check
                }
            }
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )