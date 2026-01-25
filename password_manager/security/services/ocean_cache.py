"""
Ocean Entropy Redis Cache
==========================

Redis caching layer for ocean entropy data.
Provides fast, distributed caching of buoy readings for production scaling.

Usage:
    from security.services.ocean_cache import OceanEntropyCache
    
    cache = OceanEntropyCache()
    
    # Cache a reading
    cache.set_reading('44013', reading)
    
    # Get cached reading
    reading = cache.get_reading('44013')

@author Password Manager Team
@created 2026-01-25
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import asdict

from django.conf import settings

logger = logging.getLogger(__name__)


class OceanEntropyCache:
    """
    Redis cache for ocean entropy data.
    
    Falls back to in-memory caching if Redis is unavailable.
    """
    
    def __init__(self):
        self.config = getattr(settings, 'OCEAN_ENTROPY', {})
        self.use_redis = self.config.get('USE_REDIS', False)
        self.ttl = self.config.get('CACHE_TTL', 300)  # 5 minutes default
        self.prefix = self.config.get('REDIS_KEY_PREFIX', 'ocean_entropy:')
        
        self._redis = None
        self._memory_cache: Dict[str, Dict[str, Any]] = {}
        
        if self.use_redis:
            self._init_redis()
    
    def _init_redis(self):
        """Initialize Redis connection."""
        try:
            import redis
            from django.core.cache import caches
            
            # Try to use Django's cache backend first
            try:
                cache = caches['default']
                if hasattr(cache, 'client'):
                    self._redis = cache.client.get_client()
                    logger.info("Using Django cache's Redis client")
                    return
            except Exception:
                pass
            
            # Fall back to direct Redis connection
            redis_url = getattr(settings, 'REDIS_URL', 'redis://localhost:6379/0')
            self._redis = redis.from_url(redis_url)
            self._redis.ping()  # Test connection
            logger.info("Connected to Redis for ocean entropy caching")
            
        except ImportError:
            logger.warning("redis package not installed, using memory cache")
            self.use_redis = False
        except Exception as e:
            logger.warning(f"Redis unavailable ({e}), using memory cache")
            self.use_redis = False
    
    def _key(self, key_type: str, key_id: str) -> str:
        """Generate a cache key."""
        return f"{self.prefix}{key_type}:{key_id}"
    
    # =========================================================================
    # Buoy Reading Cache
    # =========================================================================
    
    def set_reading(self, buoy_id: str, reading_data: Dict[str, Any], ttl: int = None) -> bool:
        """
        Cache a buoy reading.
        
        Args:
            buoy_id: NOAA buoy ID
            reading_data: Reading data as dict
            ttl: Time-to-live in seconds (default: config value)
            
        Returns:
            True if cached successfully
        """
        ttl = ttl or self.ttl
        key = self._key('reading', buoy_id)
        
        try:
            # Add cache timestamp
            reading_data['cached_at'] = datetime.now().isoformat()
            data = json.dumps(reading_data)
            
            if self._redis:
                self._redis.setex(key, ttl, data)
            else:
                expires_at = datetime.now() + timedelta(seconds=ttl)
                self._memory_cache[key] = {
                    'data': data,
                    'expires_at': expires_at,
                }
            return True
            
        except Exception as e:
            logger.error(f"Failed to cache reading: {e}")
            return False
    
    def get_reading(self, buoy_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a cached buoy reading.
        
        Args:
            buoy_id: NOAA buoy ID
            
        Returns:
            Reading data dict or None if not cached/expired
        """
        key = self._key('reading', buoy_id)
        
        try:
            if self._redis:
                data = self._redis.get(key)
                if data:
                    return json.loads(data)
            else:
                entry = self._memory_cache.get(key)
                if entry and entry['expires_at'] > datetime.now():
                    return json.loads(entry['data'])
                elif entry:
                    # Expired, remove from cache
                    del self._memory_cache[key]
            return None
            
        except Exception as e:
            logger.error(f"Failed to get cached reading: {e}")
            return None
    
    def delete_reading(self, buoy_id: str) -> bool:
        """Delete a cached reading."""
        key = self._key('reading', buoy_id)
        
        try:
            if self._redis:
                self._redis.delete(key)
            else:
                self._memory_cache.pop(key, None)
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete reading: {e}")
            return False
    
    # =========================================================================
    # Buoy Status Cache
    # =========================================================================
    
    def set_buoy_status(self, buoy_id: str, status_data: Dict[str, Any]) -> bool:
        """Cache buoy health status."""
        key = self._key('status', buoy_id)
        ttl = 60  # 1 minute for status
        
        try:
            data = json.dumps(status_data)
            
            if self._redis:
                self._redis.setex(key, ttl, data)
            else:
                expires_at = datetime.now() + timedelta(seconds=ttl)
                self._memory_cache[key] = {
                    'data': data,
                    'expires_at': expires_at,
                }
            return True
            
        except Exception as e:
            logger.error(f"Failed to cache status: {e}")
            return False
    
    def get_buoy_status(self, buoy_id: str) -> Optional[Dict[str, Any]]:
        """Get cached buoy status."""
        key = self._key('status', buoy_id)
        
        try:
            if self._redis:
                data = self._redis.get(key)
                if data:
                    return json.loads(data)
            else:
                entry = self._memory_cache.get(key)
                if entry and entry['expires_at'] > datetime.now():
                    return json.loads(entry['data'])
            return None
            
        except Exception as e:
            logger.error(f"Failed to get status: {e}")
            return None
    
    # =========================================================================
    # Entropy Pool Cache
    # =========================================================================
    
    def set_entropy_batch(self, batch_id: str, entropy_hex: str, metadata: Dict[str, Any]) -> bool:
        """
        Cache an entropy batch.
        
        This is useful for audit trails and replay prevention.
        """
        key = self._key('entropy', batch_id)
        ttl = 3600  # 1 hour for entropy batches
        
        try:
            data = json.dumps({
                'entropy_hex': entropy_hex,
                'metadata': metadata,
                'created_at': datetime.now().isoformat(),
            })
            
            if self._redis:
                self._redis.setex(key, ttl, data)
            else:
                expires_at = datetime.now() + timedelta(seconds=ttl)
                self._memory_cache[key] = {
                    'data': data,
                    'expires_at': expires_at,
                }
            return True
            
        except Exception as e:
            logger.error(f"Failed to cache entropy: {e}")
            return False
    
    def entropy_batch_exists(self, batch_id: str) -> bool:
        """Check if an entropy batch exists (for replay prevention)."""
        key = self._key('entropy', batch_id)
        
        try:
            if self._redis:
                return self._redis.exists(key) > 0
            else:
                entry = self._memory_cache.get(key)
                return entry is not None and entry['expires_at'] > datetime.now()
                
        except Exception as e:
            logger.error(f"Failed to check entropy: {e}")
            return False
    
    # =========================================================================
    # Rate Limiting
    # =========================================================================
    
    def check_rate_limit(self, buoy_id: str, max_requests: int = 60) -> bool:
        """
        Check if we can make another request to this buoy.
        
        Uses a sliding window counter.
        
        Args:
            buoy_id: NOAA buoy ID
            max_requests: Maximum requests per hour
            
        Returns:
            True if request is allowed
        """
        key = self._key('ratelimit', buoy_id)
        window = 3600  # 1 hour
        
        try:
            if self._redis:
                # Use Redis sorted set for sliding window
                now = datetime.now().timestamp()
                window_start = now - window
                
                # Remove old entries
                self._redis.zremrangebyscore(key, 0, window_start)
                
                # Count current entries
                count = self._redis.zcard(key)
                
                if count >= max_requests:
                    return False
                
                # Add new entry
                self._redis.zadd(key, {str(now): now})
                self._redis.expire(key, window)
                return True
                
            else:
                # Simple memory-based rate limiting
                now = datetime.now()
                window_start = now - timedelta(seconds=window)
                
                entries = self._memory_cache.get(key, {'timestamps': []})
                timestamps = [
                    ts for ts in entries.get('timestamps', [])
                    if ts > window_start
                ]
                
                if len(timestamps) >= max_requests:
                    return False
                
                timestamps.append(now)
                self._memory_cache[key] = {
                    'timestamps': timestamps,
                    'expires_at': now + timedelta(seconds=window),
                }
                return True
                
        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")
            return True  # Allow on error
    
    # =========================================================================
    # Utility Methods
    # =========================================================================
    
    def clear_all(self) -> bool:
        """Clear all ocean entropy cache entries."""
        try:
            if self._redis:
                pattern = f"{self.prefix}*"
                keys = self._redis.keys(pattern)
                if keys:
                    self._redis.delete(*keys)
            else:
                self._memory_cache.clear()
            
            logger.info("Cleared ocean entropy cache")
            return True
            
        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        try:
            if self._redis:
                pattern = f"{self.prefix}*"
                keys = self._redis.keys(pattern)
                return {
                    'type': 'redis',
                    'total_keys': len(keys),
                    'reading_keys': len([k for k in keys if b'reading:' in k]),
                    'status_keys': len([k for k in keys if b'status:' in k]),
                    'entropy_keys': len([k for k in keys if b'entropy:' in k]),
                }
            else:
                now = datetime.now()
                valid_keys = [
                    k for k, v in self._memory_cache.items()
                    if v.get('expires_at', now) > now
                ]
                return {
                    'type': 'memory',
                    'total_keys': len(valid_keys),
                    'reading_keys': len([k for k in valid_keys if 'reading:' in k]),
                    'status_keys': len([k for k in valid_keys if 'status:' in k]),
                    'entropy_keys': len([k for k in valid_keys if 'entropy:' in k]),
                }
                
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {'error': str(e)}
    
    def is_healthy(self) -> bool:
        """Check if cache is healthy."""
        try:
            if self._redis:
                return self._redis.ping()
            return True  # Memory cache is always healthy
        except Exception:
            return False


# Singleton instance
_cache_instance: Optional[OceanEntropyCache] = None


def get_ocean_cache() -> OceanEntropyCache:
    """Get the singleton cache instance."""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = OceanEntropyCache()
    return _cache_instance
