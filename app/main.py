# main.py
# StockAdvisor Backend - FastAPI Application Entry Point
# Created by Digital COE Gen AI Team

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from loguru import logger
import uvicorn

from app.api import auth, users, stocks, portfolio, recommendations, watchlist, websocket
from app.services.database import DatabaseService
from app.services.cache import CacheService
from app.services.stock_data import StockDataService
from app.config import settings

# Configure logging
logger.add(
    "logs/stockadvisor_{time}.log",
    rotation="500 MB",
    retention="10 days",
    level="INFO"
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown events."""
    # Startup
    logger.info("Starting StockAdvisor Backend...")
    
    # Initialize database connection
    await DatabaseService.connect()
    logger.info("Database connected successfully")
    
    # Initialize cache
    await CacheService.connect()
    logger.info("Cache service initialized")
    
    # Initialize stock data service
    StockDataService.initialize()
    logger.info("Stock data service initialized")
    
    # Start background tasks
    asyncio.create_task(StockDataService.start_price_updater())
    logger.info("Price updater background task started")
    
    yield
    
    # Shutdown
    logger.info("Shutting down StockAdvisor Backend...")
    await DatabaseService.disconnect()
    await CacheService.disconnect()
    StockDataService.shutdown()
    logger.info("Shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="StockAdvisor API",
    description="AI-Powered Stock Recommendation Platform API",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add GZip compression
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Include API routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])
app.include_router(stocks.router, prefix="/api/v1/stocks", tags=["Stocks"])
app.include_router(portfolio.router, prefix="/api/v1/portfolio", tags=["Portfolio"])
app.include_router(recommendations.router, prefix="/api/v1/recommendations", tags=["AI Recommendations"])
app.include_router(watchlist.router, prefix="/api/v1/watchlist", tags=["Watchlist"])
app.include_router(websocket.router, prefix="/api/v1/ws", tags=["WebSocket"])


@app.get("/")
async def root():
    """Root endpoint - Health check."""
    return {
        "name": "StockAdvisor API",
        "version": "1.0.0",
        "status": "healthy",
        "creator": "Digital COE Gen AI Team"
    }


@app.get("/health")
async def health_check():
    """Detailed health check endpoint."""
    db_status = await DatabaseService.check_health()
    cache_status = await CacheService.check_health()
    
    return {
        "status": "healthy" if db_status and cache_status else "degraded",
        "components": {
            "database": "healthy" if db_status else "unhealthy",
            "cache": "healthy" if cache_status else "unhealthy",
            "stock_data": "healthy"
        }
    }


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        workers=4 if not settings.DEBUG else 1
    )

