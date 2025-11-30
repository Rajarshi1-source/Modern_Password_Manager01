"""
FHE Computation Cache

Redis-based cache for FHE computation results.
Reduces redundant expensive FHE operations by caching encrypted results.
"""

import logging
import hashlib
import time
import json
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Attempt to import Redis
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("Redis not available. FHE cache will use in-memory fallback.")


@dataclass
class CacheConfig:
    """Configuration for FHE cache."""
    
    # Redis connection
    host: str = 'localhost'
    port: int = 6379
    db: int = 1
    password: Optional[str] = None
    
    # Cache settings
    default_ttl_seconds: int = 3600  # 1 hour
    max_ttl_seconds: int = 86400     # 24 hours
    
    # Key prefix
    key_prefix: str = 'fhe_cache'
    
    # Memory limits
    max_entries: int = 10000
    max_value_size_bytes: int = 1024 * 1024  # 1MB


@dataclass
class CacheEntry:
    """Container for cached FHE computation results."""
    
    key: str
    value: bytes
    operation_type: str
    created_at: float
    expires_at: float
    hit_count: int = 0
    metadata: Dict[str, Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'key': self.key,
            'value': self.value.hex() if isinstance(self.value, bytes) else str(self.value),
            'operation_type': self.operation_type,
            'created_at': self.created_at,
            'expires_at': self.expires_at,
            'hit_count': self.hit_count,
            'metadata': self.metadata or {}
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CacheEntry':
        """Create from dictionary."""
        value = data.get('value', '')
        if isinstance(value, str):
            try:
                value = bytes.fromhex(value)
            except ValueError:
                value = value.encode()
        
        return cls(
            key=data.get('key', ''),
            value=value,
            operation_type=data.get('operation_type', ''),
            created_at=data.get('created_at', 0),
            expires_at=data.get('expires_at', 0),
            hit_count=data.get('hit_count', 0),
            metadata=data.get('metadata', {})
        )


class FHEComputationCache:
    """
    Redis-based cache for FHE computation results.
    
    Features:
    - Efficient caching of expensive FHE computations
    - Automatic expiration management
    - Hit rate tracking
    - Pattern-based invalidation
    """
    
    def __init__(self, config: Optional[CacheConfig] = None):
        self.config = config or CacheConfig()
        self._redis_client: Optional[Any] = None
        self._memory_cache: Dict[str, CacheEntry] = {}
        self._stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'invalidations': 0
        }
        
        if REDIS_AVAILABLE:
            self._initialize_redis()
    
    def _initialize_redis(self):
        """Initialize Redis connection."""
        try:
            self._redis_client = redis.Redis(
                host=self.config.host,
                port=self.config.port,
                db=self.config.db,
                password=self.config.password,
                decode_responses=False,
                socket_timeout=5,
                socket_connect_timeout=5
            )
            
            # Test connection
            self._redis_client.ping()
            logger.info("FHE cache connected to Redis")
            
        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {e}. Using memory cache.")
            self._redis_client = None
    
    @property
    def is_redis_available(self) -> bool:
        """Check if Redis is available."""
        return self._redis_client is not None
    
    def _make_key(self, key: str) -> str:
        """Create prefixed cache key."""
        return f"{self.config.key_prefix}:{key}"
    
    def get(self, key: str) -> Optional[bytes]:
        """
        Get cached FHE computation result.
        
        Args:
            key: Cache key
            
        Returns:
            Cached bytes or None if not found/expired
        """
        full_key = self._make_key(key)
        
        if self.is_redis_available:
            return self._redis_get(full_key)
        else:
            return self._memory_get(full_key)
    
    def _redis_get(self, key: str) -> Optional[bytes]:
        """Get from Redis cache."""
        try:
            # Get the entry data
            data = self._redis_client.get(key)
            
            if data is None:
                self._stats['misses'] += 1
                return None
            
            # Increment hit count
            self._redis_client.hincrby(f"{key}:meta", "hit_count", 1)
            self._stats['hits'] += 1
            
            return data
            
        except Exception as e:
            logger.warning(f"Redis get error: {e}")
            self._stats['misses'] += 1
            return None
    
    def _memory_get(self, key: str) -> Optional[bytes]:
        """Get from memory cache."""
        entry = self._memory_cache.get(key)
        
        if entry is None:
            self._stats['misses'] += 1
            return None
        
        # Check expiration
        if time.time() > entry.expires_at:
            del self._memory_cache[key]
            self._stats['misses'] += 1
            return None
        
        entry.hit_count += 1
        self._stats['hits'] += 1
        
        return entry.value
    
    def set(
        self,
        key: str,
        value: bytes,
        operation_type: str = "unknown",
        ttl: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Cache an FHE computation result.
        
        Args:
            key: Cache key
            value: Result bytes to cache
            operation_type: Type of FHE operation
            ttl: Time-to-live in seconds (default from config)
            metadata: Optional metadata dictionary
            
        Returns:
            True if cached successfully
        """
        # Validate size
        if len(value) > self.config.max_value_size_bytes:
            logger.warning(f"Value too large to cache: {len(value)} bytes")
            return False
        
        full_key = self._make_key(key)
        ttl = min(ttl or self.config.default_ttl_seconds, self.config.max_ttl_seconds)
        
        if self.is_redis_available:
            return self._redis_set(full_key, value, operation_type, ttl, metadata)
        else:
            return self._memory_set(full_key, value, operation_type, ttl, metadata)
    
    def _redis_set(
        self,
        key: str,
        value: bytes,
        operation_type: str,
        ttl: int,
        metadata: Optional[Dict[str, Any]]
    ) -> bool:
        """Set in Redis cache."""
        try:
            pipe = self._redis_client.pipeline()
            
            # Set main value
            pipe.setex(key, ttl, value)
            
            # Set metadata
            meta = {
                'operation_type': operation_type,
                'created_at': time.time(),
                'hit_count': 0
            }
            if metadata:
                meta.update(metadata)
            
            pipe.hset(f"{key}:meta", mapping={
                k: json.dumps(v) if isinstance(v, (dict, list)) else str(v)
                for k, v in meta.items()
            })
            pipe.expire(f"{key}:meta", ttl)
            
            pipe.execute()
            self._stats['sets'] += 1
            
            return True
            
        except Exception as e:
            logger.warning(f"Redis set error: {e}")
            return False
    
    def _memory_set(
        self,
        key: str,
        value: bytes,
        operation_type: str,
        ttl: int,
        metadata: Optional[Dict[str, Any]]
    ) -> bool:
        """Set in memory cache."""
        # Enforce max entries
        if len(self._memory_cache) >= self.config.max_entries:
            self._evict_expired()
            
            # If still over limit, remove oldest
            if len(self._memory_cache) >= self.config.max_entries:
                oldest_key = min(
                    self._memory_cache.keys(),
                    key=lambda k: self._memory_cache[k].created_at
                )
                del self._memory_cache[oldest_key]
        
        now = time.time()
        entry = CacheEntry(
            key=key,
            value=value,
            operation_type=operation_type,
            created_at=now,
            expires_at=now + ttl,
            hit_count=0,
            metadata=metadata or {}
        )
        
        self._memory_cache[key] = entry
        self._stats['sets'] += 1
        
        return True
    
    def invalidate(self, key: str) -> bool:
        """
        Invalidate a specific cache entry.
        
        Args:
            key: Cache key to invalidate
            
        Returns:
            True if entry was found and removed
        """
        full_key = self._make_key(key)
        
        if self.is_redis_available:
            try:
                result = self._redis_client.delete(full_key, f"{full_key}:meta")
                self._stats['invalidations'] += 1
                return result > 0
            except Exception as e:
                logger.warning(f"Redis invalidate error: {e}")
                return False
        else:
            if full_key in self._memory_cache:
                del self._memory_cache[full_key]
                self._stats['invalidations'] += 1
                return True
            return False
    
    def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate cache entries matching a pattern.
        
        Args:
            pattern: Pattern to match (e.g., "user:123:*")
            
        Returns:
            Number of entries invalidated
        """
        full_pattern = self._make_key(pattern)
        count = 0
        
        if self.is_redis_available:
            try:
                # Find matching keys
                keys = self._redis_client.keys(full_pattern)
                
                if keys:
                    # Also get metadata keys
                    meta_keys = [f"{k.decode()}:meta" for k in keys]
                    all_keys = list(keys) + [k.encode() for k in meta_keys]
                    
                    count = self._redis_client.delete(*all_keys)
                
                self._stats['invalidations'] += count
                return count // 2  # Divide by 2 because we count main + meta
                
            except Exception as e:
                logger.warning(f"Redis invalidate pattern error: {e}")
                return 0
        else:
            # Memory cache pattern matching
            import fnmatch
            keys_to_delete = [
                k for k in self._memory_cache.keys()
                if fnmatch.fnmatch(k, full_pattern)
            ]
            
            for key in keys_to_delete:
                del self._memory_cache[key]
                count += 1
            
            self._stats['invalidations'] += count
            return count
    
    def invalidate_user_cache(self, user_id: str) -> int:
        """
        Invalidate all cache entries for a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            Number of entries invalidated
        """
        return self.invalidate_pattern(f"*:user:{user_id}:*")
    
    def _evict_expired(self):
        """Remove expired entries from memory cache."""
        now = time.time()
        expired_keys = [
            k for k, v in self._memory_cache.items()
            if now > v.expires_at
        ]
        
        for key in expired_keys:
            del self._memory_cache[key]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total = self._stats['hits'] + self._stats['misses']
        hit_rate = self._stats['hits'] / total if total > 0 else 0.0
        
        stats = {
            **self._stats,
            'total_requests': total,
            'hit_rate': hit_rate,
            'is_redis': self.is_redis_available
        }
        
        if self.is_redis_available:
            try:
                info = self._redis_client.info('memory')
                stats['redis_memory_used'] = info.get('used_memory', 0)
                stats['redis_memory_human'] = info.get('used_memory_human', 'N/A')
            except:
                pass
        else:
            stats['memory_entries'] = len(self._memory_cache)
        
        return stats
    
    def clear(self) -> int:
        """
        Clear all FHE cache entries.
        
        Returns:
            Number of entries cleared
        """
        pattern = f"{self.config.key_prefix}:*"
        
        if self.is_redis_available:
            try:
                keys = self._redis_client.keys(pattern.encode())
                if keys:
                    return self._redis_client.delete(*keys)
                return 0
            except Exception as e:
                logger.warning(f"Redis clear error: {e}")
                return 0
        else:
            count = len(self._memory_cache)
            self._memory_cache.clear()
            return count
    
    def get_or_compute(
        self,
        key: str,
        compute_fn: callable,
        operation_type: str = "unknown",
        ttl: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bytes:
        """
        Get from cache or compute and cache the result.
        
        Args:
            key: Cache key
            compute_fn: Function to call if not cached
            operation_type: Type of operation
            ttl: Time-to-live
            metadata: Optional metadata
            
        Returns:
            Cached or computed result
        """
        # Try cache first
        result = self.get(key)
        
        if result is not None:
            return result
        
        # Compute result
        result = compute_fn()
        
        # Ensure result is bytes
        if not isinstance(result, bytes):
            if isinstance(result, str):
                result = result.encode()
            else:
                result = json.dumps(result).encode()
        
        # Cache it
        self.set(key, result, operation_type, ttl, metadata)
        
        return result


def generate_cache_key(
    operation_type: str,
    user_id: Optional[str] = None,
    input_data: Any = None
) -> str:
    """
    Generate a deterministic cache key for FHE operations.
    
    Args:
        operation_type: Type of FHE operation
        user_id: Optional user identifier
        input_data: Input data to hash
        
    Returns:
        Cache key string
    """
    parts = [operation_type]
    
    if user_id:
        parts.append(f"user:{user_id}")
    
    if input_data is not None:
        # Hash the input data
        data_str = str(input_data)[:256]  # Limit for performance
        data_hash = hashlib.sha256(data_str.encode()).hexdigest()[:16]
        parts.append(data_hash)
    
    return ":".join(parts)


# Singleton instance
_fhe_cache: Optional[FHEComputationCache] = None


def get_fhe_cache(config: Optional[CacheConfig] = None) -> FHEComputationCache:
    """Get or create the FHE cache singleton."""
    global _fhe_cache
    if _fhe_cache is None:
        _fhe_cache = FHEComputationCache(config)
    return _fhe_cache

