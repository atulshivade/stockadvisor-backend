# config.py
# StockAdvisor Backend - Configuration Settings
# Created by Digital COE Gen AI Team

from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Application
    APP_NAME: str = "StockAdvisor"
    DEBUG: bool = False
    SECRET_KEY: str = "your-super-secret-key-change-in-production"
    
    # API Keys - Stock Data Providers
    ALPHA_VANTAGE_API_KEY: str = ""
    IEX_CLOUD_API_KEY: str = ""
    FINNHUB_API_KEY: str = ""
    POLYGON_API_KEY: str = ""
    
    # Database
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DATABASE: str = "stockadvisor"
    
    # Redis Cache
    REDIS_URL: str = "redis://localhost:6379"
    CACHE_TTL: int = 300  # 5 minutes
    
    # JWT Authentication
    JWT_SECRET_KEY: str = "your-jwt-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # CORS
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8080",
        "https://stockadvisor.com",
        "https://app.stockadvisor.com"
    ]
    
    # Stock Data Settings
    PRICE_UPDATE_INTERVAL: int = 5  # seconds
    MAX_CONCURRENT_API_CALLS: int = 10
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_PERIOD: int = 60  # seconds
    
    # AI/ML Settings
    AI_MODEL_PATH: str = "models/"
    RECOMMENDATION_CONFIDENCE_THRESHOLD: float = 0.6
    MAX_RECOMMENDATIONS: int = 10
    
    # Security
    PASSWORD_MIN_LENGTH: int = 8
    PASSWORD_HASH_ROUNDS: int = 12
    MAX_LOGIN_ATTEMPTS: int = 5
    LOCKOUT_DURATION_MINUTES: int = 15
    
    # WebSocket
    WS_HEARTBEAT_INTERVAL: int = 30
    WS_MAX_CONNECTIONS: int = 1000
    
    # Supported Stock Exchanges
    SUPPORTED_EXCHANGES: List[str] = [
        "NYSE", "NASDAQ", "LSE", "TSE", "HKEX", "SSE",
        "BSE", "NSE", "ASX", "TSX", "FRA", "SIX"
    ]
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Create settings instance
settings = Settings()


# Exchange-specific configurations
EXCHANGE_CONFIG = {
    "NYSE": {
        "name": "New York Stock Exchange",
        "country": "USA",
        "currency": "USD",
        "timezone": "America/New_York",
        "open_time": "09:30",
        "close_time": "16:00",
        "api_suffix": ""
    },
    "NASDAQ": {
        "name": "NASDAQ",
        "country": "USA",
        "currency": "USD",
        "timezone": "America/New_York",
        "open_time": "09:30",
        "close_time": "16:00",
        "api_suffix": ""
    },
    "LSE": {
        "name": "London Stock Exchange",
        "country": "UK",
        "currency": "GBP",
        "timezone": "Europe/London",
        "open_time": "08:00",
        "close_time": "16:30",
        "api_suffix": ".L"
    },
    "TSE": {
        "name": "Tokyo Stock Exchange",
        "country": "Japan",
        "currency": "JPY",
        "timezone": "Asia/Tokyo",
        "open_time": "09:00",
        "close_time": "15:00",
        "api_suffix": ".T"
    },
    "HKEX": {
        "name": "Hong Kong Stock Exchange",
        "country": "Hong Kong",
        "currency": "HKD",
        "timezone": "Asia/Hong_Kong",
        "open_time": "09:30",
        "close_time": "16:00",
        "api_suffix": ".HK"
    },
    "SSE": {
        "name": "Shanghai Stock Exchange",
        "country": "China",
        "currency": "CNY",
        "timezone": "Asia/Shanghai",
        "open_time": "09:30",
        "close_time": "15:00",
        "api_suffix": ".SS"
    },
    "BSE": {
        "name": "Bombay Stock Exchange",
        "country": "India",
        "currency": "INR",
        "timezone": "Asia/Kolkata",
        "open_time": "09:15",
        "close_time": "15:30",
        "api_suffix": ".BO"
    },
    "NSE": {
        "name": "National Stock Exchange (India)",
        "country": "India",
        "currency": "INR",
        "timezone": "Asia/Kolkata",
        "open_time": "09:15",
        "close_time": "15:30",
        "api_suffix": ".NS"
    },
    "ASX": {
        "name": "Australian Securities Exchange",
        "country": "Australia",
        "currency": "AUD",
        "timezone": "Australia/Sydney",
        "open_time": "10:00",
        "close_time": "16:00",
        "api_suffix": ".AX"
    },
    "TSX": {
        "name": "Toronto Stock Exchange",
        "country": "Canada",
        "currency": "CAD",
        "timezone": "America/Toronto",
        "open_time": "09:30",
        "close_time": "16:00",
        "api_suffix": ".TO"
    },
    "FRA": {
        "name": "Frankfurt Stock Exchange",
        "country": "Germany",
        "currency": "EUR",
        "timezone": "Europe/Berlin",
        "open_time": "09:00",
        "close_time": "17:30",
        "api_suffix": ".F"
    },
    "SIX": {
        "name": "SIX Swiss Exchange",
        "country": "Switzerland",
        "currency": "CHF",
        "timezone": "Europe/Zurich",
        "open_time": "09:00",
        "close_time": "17:30",
        "api_suffix": ".SW"
    }
}

