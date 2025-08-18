"""
Main FastAPI application for IDM-VTON API.
"""

import time
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import structlog
import psutil

from config import get_settings, settings
from api.routes import router as api_router
from api.middleware import RequestLoggingMiddleware, MetricsMiddleware
from core.exceptions import IDMVTONError
from services.model_service import model_service

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting IDM-VTON API server", version=settings.app_version)
    
    try:
        # Initialize model service
        await model_service.initialize()
        logger.info("Model service initialized successfully")
    except Exception as e:
        logger.error("Failed to initialize model service", error=str(e))
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down IDM-VTON API server")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Virtual Try-On API using IDM-VTON",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        lifespan=lifespan
    )
    
    # Add middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(RequestLoggingMiddleware)
    
    if settings.enable_metrics:
        app.add_middleware(MetricsMiddleware)
    
    # Add exception handlers
    app.add_exception_handler(Exception, global_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(IDMVTONError, idmvton_exception_handler)
    
    # Mount static files for the frontend
    app.mount("/static", StaticFiles(directory="static"), name="static")
    
    # Include routers
    app.include_router(api_router, prefix="/api/v1")
    
    return app


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler."""
    logger.error(
        "Unhandled exception",
        exc_info=exc,
        path=request.url.path,
        method=request.method,
        client_ip=request.client.host if request.client else None
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": "An unexpected error occurred",
            "request_id": getattr(request.state, "request_id", "unknown")
        }
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """HTTP exception handler."""
    logger.warning(
        "HTTP exception",
        status_code=exc.status_code,
        detail=exc.detail,
        path=request.url.path,
        method=request.method
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "HTTP error",
            "message": exc.detail,
            "status_code": exc.status_code,
            "request_id": getattr(request.state, "request_id", "unknown")
        }
    )


async def idmvton_exception_handler(request: Request, exc: IDMVTONError) -> JSONResponse:
    """IDM-VTON specific exception handler."""
    logger.error("IDM-VTON error", error=str(exc), path=request.url.path)
    return JSONResponse(
        status_code=400,
        content={
            "error": True,
            "message": str(exc),
            "error_code": getattr(exc, 'error_code', 'UNKNOWN_ERROR'),
            "details": getattr(exc, 'details', {})
        }
    )


# Create app instance
app = create_app()


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    try:
        # Check system resources
        memory_usage = psutil.virtual_memory().percent
        cpu_usage = psutil.cpu_percent(interval=1)
        
        # Check model service status
        model_status = await model_service.get_status()
        
        return {
            "status": "healthy",
            "timestamp": time.time(),
            "version": settings.app_version,
            "system": {
                "memory_usage_percent": memory_usage,
                "cpu_usage_percent": cpu_usage
            },
            "model": model_status
        }
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": time.time()
        }


# Root endpoint - serve the frontend
@app.get("/")
async def root():
    """Serve the main frontend page."""
    return FileResponse("static/index.html")


# API status endpoint
@app.get("/api/status")
async def api_status():
    """API status and information."""
    return {
        "api": "IDM-VTON Virtual Try-On API",
        "version": settings.app_version,
        "status": "running",
        "endpoints": {
            "health": "/health",
            "api_docs": "/docs" if settings.debug else "disabled",
            "tryon": "/api/v1/tryon",
            "status": "/api/v1/status"
        },
        "features": [
            "Virtual try-on with person and garment images",
            "Asynchronous processing with task queue",
            "Real-time progress tracking",
            "Result caching and optimization"
        ]
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "api.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )
