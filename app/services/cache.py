# cache.py
# StockAdvisor Backend - Redis Cache Service
# Created by Digital COE Gen AI Team

import json
from typing import Any, Optional
import redis.asyncio as redis
from loguru import logger

from app.config import settings


class CacheService:
    """Redis cache service for high-performance data caching."""
    
    _client: redis.Redis = None
    
    @classmethod
    async def connect(cls):
        """Connect to Redis cache."""
        try:
            cls._client = redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True
            )
            # Test connection
            await cls._client.ping()
            logger.info("Connected to Redis cache")
        except Exception as e:
            logger.warning(f"Redis connection failed, using in-memory cache: {e}")
            cls._client = None
    
    @classmethod
    async def disconnect(cls):
        """Disconnect from Redis cache."""
        if cls._client:
            await cls._client.close()
            logger.info("Disconnected from Redis cache")
    
    @classmethod
    async def check_health(cls) -> bool:
        """Check cache health status."""
        if not cls._client:
            return True  # Using fallback
        try:
            await cls._client.ping()
            return True
        except Exception as e:
            logger.error(f"Cache health check failed: {e}")
            return False
    
    @classmethod
    async def get(cls, key: str) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found
        """
        if not cls._client:
            return None
            
        try:
            value = await cls._client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.warning(f"Cache get error for {key}: {e}")
            return None
    
    @classmethod
    async def set(
        cls, 
        key: str, 
        value: Any, 
        ttl: int = None
    ):
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (default from settings)
        """
        if not cls._client:
            return
            
        try:
            ttl = ttl or settings.CACHE_TTL
            await cls._client.setex(
                key,
                ttl,
                json.dumps(value, default=str)
            )
        except Exception as e:
            logger.warning(f"Cache set error for {key}: {e}")
    
    @classmethod
    async def delete(cls, key: str):
        """
        Delete value from cache.
        
        Args:
            key: Cache key to delete
        """
        if not cls._client:
            return
            
        try:
            await cls._client.delete(key)
        except Exception as e:
            logger.warning(f"Cache delete error for {key}: {e}")
    
    @classmethod
    async def delete_pattern(cls, pattern: str):
        """
        Delete all keys matching a pattern.
        
        Args:
            pattern: Key pattern to match (e.g., "quote:*")
        """
        if not cls._client:
            return
            
        try:
            cursor = 0
            while True:
                cursor, keys = await cls._client.scan(cursor, match=pattern, count=100)
                if keys:
                    await cls._client.delete(*keys)
                if cursor == 0:
                    break
        except Exception as e:
            logger.warning(f"Cache delete pattern error for {pattern}: {e}")
    
    @classmethod
    async def increment(cls, key: str, amount: int = 1) -> int:
        """
        Increment a counter in cache.
        
        Args:
            key: Cache key
            amount: Amount to increment by
            
        Returns:
            New value after increment
        """
        if not cls._client:
            return 0
            
        try:
            return await cls._client.incrby(key, amount)
        except Exception as e:
            logger.warning(f"Cache increment error for {key}: {e}")
            return 0
    
    @classmethod
    async def get_or_set(
        cls, 
        key: str, 
        factory, 
        ttl: int = None
    ) -> Any:
        """
        Get value from cache or set it using factory function.
        
        Args:
            key: Cache key
            factory: Async function to generate value if not cached
            ttl: Time to live in seconds
            
        Returns:
            Cached or newly generated value
        """
        value = await cls.get(key)
        if value is not None:
            return value
            
        value = await factory()
        if value is not None:
            await cls.set(key, value, ttl)
        return value

