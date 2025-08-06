"""
Main FastAPI application for the Stock Screener.

This module sets up the FastAPI app with middleware, routers, and exception handlers.
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.api import screener
from app.services.polygon_client import PolygonAPIError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Create a global polygon client instance that will be shared
polygon_client = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifecycle - startup and shutdown events.
    """
    # Startup
    logger.info("Starting Stock Screener API...")
    
    # Initialize Polygon client
    from app.services.polygon_client import PolygonClient
    global polygon_client
    polygon_client = PolygonClient()
    
    # Make client available to endpoints
    app.state.polygon_client = polygon_client
    
    yield
    
    # Shutdown
    logger.info("Shutting down Stock Screener API...")
    if polygon_client:
        await polygon_client.close()


# Create FastAPI app
app = FastAPI(
    title=settings.project_name,
    version="1.0.0",
    description="High-performance stock screener API using Polygon.io data",
    lifespan=lifespan
)

# Configure CORS
# Note: When allow_origins is ["*"], allow_credentials should be False
cors_allow_credentials = not ("*" in settings.cors_origins)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=cors_allow_credentials,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests with timing."""
    start_time = time.time()
    
    # Get request ID for correlation
    request_id = datetime.utcnow().strftime('%Y%m%d%H%M%S%f')
    
    # Log request
    logger.info(
        f"Request {request_id}: {request.method} {request.url.path} "
        f"from {request.client.host if request.client else 'unknown'}"
    )
    
    try:
        # Process request
        response = await call_next(request)
        
        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000
        
        # Log response
        logger.info(
            f"Response {request_id}: {response.status_code} "
            f"completed in {duration_ms:.2f}ms"
        )
        
        # Add custom headers
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = f"{duration_ms:.2f}ms"
        
        return response
        
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            f"Request {request_id} failed after {duration_ms:.2f}ms: {str(e)}",
            exc_info=True
        )
        raise


# Exception handlers
@app.exception_handler(PolygonAPIError)
async def polygon_api_exception_handler(request: Request, exc: PolygonAPIError):
    """Handle Polygon API specific errors."""
    logger.error(f"Polygon API error: {exc}")
    
    return JSONResponse(
        status_code=exc.status_code or 503,
        content={
            "error": "External API Error",
            "message": str(exc),
            "details": exc.response_data if exc.response_data else None
        }
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """Handle validation errors."""
    logger.error(f"Validation error: {exc}")
    
    return JSONResponse(
        status_code=400,
        content={
            "error": "Validation Error",
            "message": str(exc)
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle all other exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred"
        }
    )


# Include routers
app.include_router(
    screener.router,
    prefix=settings.api_v1_str,
    tags=["screener"]
)


# Root endpoint
@app.get("/", tags=["root"])
async def root():
    """Root endpoint with API information."""
    return {
        "name": settings.project_name,
        "version": "1.0.0",
        "status": "healthy",
        "endpoints": {
            "health": f"{settings.api_v1_str}/health",
            "screen": f"{settings.api_v1_str}/screen",
            "symbols": f"{settings.api_v1_str}/symbols",
            "filters": f"{settings.api_v1_str}/filters"
        }
    }