import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Dict, List, Optional, Any

import structlog
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram, generate_latest
from prometheus_client import CONTENT_TYPE_LATEST
from starlette.responses import Response
import uvicorn

from app.core.config import get_settings
from app.core.database import init_db
from app.core.logging import setup_logging
from app.api.v1 import forecasts, data, analytics, admin
from app.services.data_collector import DataCollectorService
from app.services.forecasting import ForecastingService
from app.services.celery_app import celery_app

REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint'])
REQUEST_DURATION = Histogram('http_request_duration_seconds', 'HTTP request duration')

logger = structlog.get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    
    setup_logging(settings.log_level)
    logger.info("Starting Nuclear Forecast Enterprise", version="1.0.0")
    
    await init_db()
    logger.info("Database initialized")
    
    data_collector = DataCollectorService()
    forecasting_service = ForecastingService()
    
    asyncio.create_task(data_collector.start_periodic_collection())
    asyncio.create_task(forecasting_service.start_model_retraining())
    
    logger.info("Background services started")
    
    yield
    
    logger.info("Shutting down Nuclear Forecast Enterprise")

def create_app() -> FastAPI:
    settings = get_settings()
    
    app = FastAPI(
        title="Nuclear Forecast Enterprise",
        description="Nuclear energy forecasting and analytics platform with real-time data integration",
        version="1.0.0",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        lifespan=lifespan
    )
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    
    app.include_router(forecasts.forecasts_router, prefix="/api/v1/forecasts", tags=["forecasts"])
    app.include_router(data.data_router, prefix="/api/v1/data", tags=["data"])
    app.include_router(analytics.analytics_router, prefix="/api/v1/analytics", tags=["analytics"])
    app.include_router(admin.admin_router, prefix="/api/v1/admin", tags=["admin"])
    
    @app.get("/health")
    async def health_check():
        return {"status": "healthy", "version": "1.0.0"}
    
    @app.get("/metrics")
    async def metrics():
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
    
    @app.exception_handler(Exception)
    async def global_exception_handler(request, exc):
        logger.error("Unhandled exception", exc_info=exc, path=request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"}
        )
    
    return app

app = create_app()

if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )
