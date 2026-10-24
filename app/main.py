"""
Main FastAPI application for Social Media Analytics Platform.
"""

import logging
import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.logging_config import configure_logging
from app.routes.comments import router as comments_router
from app.routes.hashtags import router as hashtags_router
from app.routes.health import router as health_router
from app.routes.reports import router as reports_router

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.

    Returns:
        Configured FastAPI app instance
    """
    configure_logging()

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

    @app.middleware("http")
    async def log_requests(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Log one line per request with its status and duration."""
        start = time.perf_counter()
        response = await call_next(request)
        logger.info(
            "request",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round((time.perf_counter() - start) * 1000, 1),
            },
        )
        return response

    # Global exception handlers
    @app.exception_handler(SQLAlchemyError)
    async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
        """Handle SQLAlchemy database errors."""
        logger.error(
            "database error",
            exc_info=exc,
            extra={"method": request.method, "path": request.url.path},
        )
        return JSONResponse(
            status_code=500,
            content={
                "error_code": "DATABASE_ERROR",
                "message": "Database operation failed",
                "details": str(exc) if app.debug else "Database connection issue",
            },
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Handle all other unhandled exceptions."""
        logger.error(
            "unhandled exception",
            exc_info=exc,
            extra={"method": request.method, "path": request.url.path},
        )

        return JSONResponse(
            status_code=500,
            content={
                "error_code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "details": str(exc) if app.debug else "Internal server error",
            },
        )

    # Include routers
    app.include_router(hashtags_router)
    app.include_router(comments_router)
    app.include_router(reports_router)
    app.include_router(health_router)

    return app


# Create the application instance
app = create_app()


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"message": "Social Media Analytics API", "status": "healthy", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    """Detailed health check endpoint (legacy - redirects to /health/)."""
    from app.routes.health import health_check as detailed_health_check

    return await detailed_health_check()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
