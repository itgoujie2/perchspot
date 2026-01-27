"""
Redis cache wrapper for API responses and data caching
"""
import json
import logging
from typing import Optional, Any
from datetime import timedelta
import redis.asyncio as redis

from app.config import settings

logger = logging.getLogger(__name__)


class CacheManager:
    """
    Redis cache manager with JSON serialization
    """

    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.default_ttl = timedelta(hours=settings.CACHE_TTL_HOURS)

    async def connect(self):
        """Connect to Redis"""
        if not self.redis_client:
            self.redis_client = await redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True
            )
            logger.info("Connected to Redis")

    async def disconnect(self):
        """Disconnect from Redis"""
        if self.redis_client:
            await self.redis_client.close()
            self.redis_client = None
            logger.info("Disconnected from Redis")

    async def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache

        Args:
            key: Cache key

        Returns:
            Cached value (deserialized from JSON) or None
        """
        try:
            if not self.redis_client:
                await self.connect()

            value = await self.redis_client.get(key)

            if value:
                logger.debug(f"Cache HIT: {key}")
                return json.loads(value)
            else:
                logger.debug(f"Cache MISS: {key}")
                return None

        except Exception as e:
            logger.error(f"Error getting from cache {key}: {e}")
            return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[timedelta] = None
    ) -> bool:
        """
        Set value in cache

        Args:
            key: Cache key
            value: Value to cache (will be JSON serialized)
            ttl: Time to live (default: settings.CACHE_TTL_HOURS)

        Returns:
            True if successful
        """
        try:
            if not self.redis_client:
                await self.connect()

            if ttl is None:
                ttl = self.default_ttl

            serialized = json.dumps(value, default=str)
            await self.redis_client.setex(
                key,
                int(ttl.total_seconds()),
                serialized
            )

            logger.debug(f"Cache SET: {key} (TTL: {ttl})")
            return True

        except Exception as e:
            logger.error(f"Error setting cache {key}: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """
        Delete key from cache

        Args:
            key: Cache key

        Returns:
            True if successful
        """
        try:
            if not self.redis_client:
                await self.connect()

            await self.redis_client.delete(key)
            logger.debug(f"Cache DELETE: {key}")
            return True

        except Exception as e:
            logger.error(f"Error deleting from cache {key}: {e}")
            return False

    async def exists(self, key: str) -> bool:
        """
        Check if key exists in cache

        Args:
            key: Cache key

        Returns:
            True if key exists
        """
        try:
            if not self.redis_client:
                await self.connect()

            return await self.redis_client.exists(key) > 0

        except Exception as e:
            logger.error(f"Error checking cache existence {key}: {e}")
            return False

    @staticmethod
    def make_key(prefix: str, *args) -> str:
        """
        Create cache key from prefix and arguments

        Args:
            prefix: Key prefix
            *args: Additional key components

        Returns:
            Cache key string

        Example:
            make_key('property', '123 Main St') -> 'property:123_main_st'
        """
        # Clean and join arguments
        parts = [prefix]
        for arg in args:
            # Convert to string and clean
            cleaned = str(arg).lower().replace(' ', '_')
            # Remove special characters
            cleaned = ''.join(c for c in cleaned if c.isalnum() or c == '_')
            parts.append(cleaned)

        return ':'.join(parts)


# Global cache instance
cache = CacheManager()


async def get_cache():
    """
    Dependency for getting cache instance in FastAPI
    """
    if not cache.redis_client:
        await cache.connect()
    return cache
