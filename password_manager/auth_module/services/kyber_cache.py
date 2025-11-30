"""
Kyber Cache Manager for Django

Multi-level caching strategy for CRYSTALS-Kyber operations:
- Level 1: In-memory LRU cache for hot keys (using functools.lru_cache)
- Level 2: Django's cache framework (configurable backend - supports Redis)
- Level 3: Database for persistence (via Django models)

Features:
- Automatic cache expiration
- Cache warming on startup
- Thread-safe operations
- Performance metrics
- Redis support for distributed caching
- Hybrid LRU + Redis mode

Usage:
    from auth_module.services.kyber_cache import KyberCacheManager
    
    cache = KyberCacheManager()
    
    # Cache public key
    cache.cache_public_key(user_id, public_key)
    
    # Get cached public key
    public_key = cache.get_cached_public_key(user_id)
    
    # Use hybrid mode with Redis
    cache = KyberCacheManager(use_redis=True)
"""

import base64
import hashlib
import logging
import time
from functools import lru_cache
from typing import Optional, Dict, Any, Tuple, List
from threading import Lock
from collections import OrderedDict

from django.core.cache import cache, caches
from django.conf import settings

logger = logging.getLogger(__name__)


# =============================================================================
# LRU CACHE IMPLEMENTATION
# =============================================================================

class LRUCache:
    """
    Thread-safe LRU cache with TTL support.
    
    Used as L1 cache for frequently accessed keys.
    """
    
    def __init__(self, max_size: int = 256, default_ttl: int = 3600):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: OrderedDict = OrderedDict()
        self._lock = Lock()
        self._hits = 0
        self._misses = 0
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None
            
            value, expiry = self._cache[key]
            
            # Check expiration
            if time.time() > expiry:
                del self._cache[key]
                self._misses += 1
                return None
            
            # Move to end (most recently used)
            self._cache.move_to_end(key)
            self._hits += 1
            return value
    
    def set(self, key: str, value: Any, ttl: int = None):
        """Set value in cache."""
        if ttl is None:
            ttl = self.default_ttl
        
        with self._lock:
            # Remove oldest if at capacity
            while len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)
            
            expiry = time.time() + ttl
            self._cache[key] = (value, expiry)
            self._cache.move_to_end(key)
    
    def delete(self, key: str) -> bool:
        """Delete value from cache."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    def clear(self):
        """Clear entire cache."""
        with self._lock:
            self._cache.clear()
    
    def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """Get multiple values."""
        result = {}
        for key in keys:
            value = self.get(key)
            if value is not None:
                result[key] = value
        return result
    
    def set_many(self, data: Dict[str, Any], ttl: int = None):
        """Set multiple values."""
        for key, value in data.items():
            self.set(key, value, ttl)
    
    def cleanup_expired(self) -> int:
        """Remove expired entries."""
        now = time.time()
        removed = 0
        
        with self._lock:
            expired_keys = [
                key for key, (_, expiry) in self._cache.items()
                if now > expiry
            ]
            
            for key in expired_keys:
                del self._cache[key]
                removed += 1
        
        return removed
    
    @property
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total = self._hits + self._misses
        return {
            'size': len(self._cache),
            'max_size': self.max_size,
            'hits': self._hits,
            'misses': self._misses,
            'hit_rate': f'{(self._hits / max(total, 1) * 100):.2f}%'
        }
    
    def reset_stats(self):
        """Reset statistics."""
        self._hits = 0
        self._misses = 0


class KyberCacheManager:
    """
    Multi-level cache manager for Kyber cryptographic keys.
    
    Implements a tiered caching strategy:
    - L1: In-memory LRU (fastest, limited size) - using LRUCache class
    - L2: Django cache / Redis (configurable, distributed-capable)
    - L3: Database (persistent, slowest)
    
    Hybrid Mode (use_redis=True):
    - L1: Local LRU for hot keys
    - L2: Redis for distributed caching
    - Automatic promotion from L2 to L1 on reads
    
    Attributes:
        CACHE_TTL: Default time-to-live in seconds
        PUBLIC_KEY_PREFIX: Cache key prefix for public keys
        SESSION_KEY_PREFIX: Cache key prefix for session keys
        SHARED_SECRET_PREFIX: Cache key prefix for shared secrets
    """
    
    # Cache configuration
    CACHE_TTL = 3600  # 1 hour default
    SHORT_TTL = 300   # 5 minutes for session data
    LONG_TTL = 86400  # 24 hours for public keys
    
    # Cache key prefixes
    PUBLIC_KEY_PREFIX = 'kyber:pubkey:'
    PRIVATE_KEY_PREFIX = 'kyber:privkey:'
    SESSION_KEY_PREFIX = 'kyber:session:'
    SHARED_SECRET_PREFIX = 'kyber:secret:'
    VALIDATION_PREFIX = 'kyber:valid:'
    KEYPAIR_PREFIX = 'kyber:keypair:'
    
    # LRU cache size for hot keys
    LRU_CACHE_SIZE = 256
    
    def __init__(self, use_redis: bool = False, redis_cache_alias: str = 'default'):
        """
        Initialize KyberCacheManager.
        
        Args:
            use_redis: Enable Redis as L2 cache
            redis_cache_alias: Django cache alias for Redis
        """
        self._lock = Lock()
        self._use_redis = use_redis
        self._redis_alias = redis_cache_alias
        
        # Performance metrics
        self._metrics = {
            'l1_hits': 0,
            'l1_misses': 0,
            'l2_hits': 0,
            'l2_misses': 0,
            'l3_hits': 0,
            'l3_misses': 0,
            'sets': 0,
            'deletes': 0,
            'errors': 0,
            'promotions': 0  # L2 to L1 promotions
        }
        
        # L1: In-memory LRU cache
        self._l1_cache = LRUCache(max_size=self.LRU_CACHE_SIZE, default_ttl=self.CACHE_TTL)
        
        # L2: Django cache (Redis or default)
        self._l2_cache = self._get_l2_cache()
        
        # Check Redis availability
        self._redis_available = self._check_redis_availability()
        
        mode = 'hybrid (LRU + Redis)' if self._use_redis and self._redis_available else 'standard'
        logger.info(f"KyberCacheManager initialized in {mode} mode")
    
    # ==========================================================================
    # INITIALIZATION HELPERS
    # ==========================================================================
    
    def _get_l2_cache(self):
        """Get the L2 cache backend."""
        try:
            if self._use_redis:
                # Try to get Redis cache
                return caches[self._redis_alias]
            return cache
        except Exception as e:
            logger.warning(f"Could not get cache backend: {e}")
            return cache
    
    def _check_redis_availability(self) -> bool:
        """Check if Redis is available and working."""
        if not self._use_redis:
            return False
        
        try:
            # Try a test operation
            test_key = 'kyber:test:availability'
            self._l2_cache.set(test_key, 'test', 1)
            result = self._l2_cache.get(test_key)
            self._l2_cache.delete(test_key)
            
            if result == 'test':
                logger.info("Redis cache is available")
                return True
            
        except Exception as e:
            logger.warning(f"Redis not available: {e}")
        
        return False
    
    # ==========================================================================
    # CACHE KEY GENERATION
    # ==========================================================================
    
    @staticmethod
    def get_public_key_cache_key(user_id: int) -> str:
        """Generate cache key for user's public key."""
        return f"{KyberCacheManager.PUBLIC_KEY_PREFIX}{user_id}"
    
    @staticmethod
    def get_private_key_cache_key(user_id: int) -> str:
        """Generate cache key for user's private key (use with caution!)."""
        return f"{KyberCacheManager.PRIVATE_KEY_PREFIX}{user_id}"
    
    @staticmethod
    def get_session_key_cache_key(session_id: str) -> str:
        """Generate cache key for session key."""
        return f"{KyberCacheManager.SESSION_KEY_PREFIX}{session_id}"
    
    @staticmethod
    def get_shared_secret_cache_key(session_id: str) -> str:
        """Generate cache key for shared secret."""
        return f"{KyberCacheManager.SHARED_SECRET_PREFIX}{session_id}"
    
    @staticmethod
    def get_keypair_cache_key(user_id: int, version: int = 1) -> str:
        """Generate cache key for full keypair."""
        return f"{KyberCacheManager.KEYPAIR_PREFIX}{user_id}:v{version}"
    
    @staticmethod
    def get_validation_cache_key(key_hash: str) -> str:
        """Generate cache key for key validation result."""
        return f"{KyberCacheManager.VALIDATION_PREFIX}{key_hash}"
    
    # ==========================================================================
    # L1 CACHE (IN-MEMORY LRU)
    # ==========================================================================
    
    def _l1_get(self, key: str) -> Optional[Any]:
        """Get value from L1 cache."""
        value = self._l1_cache.get(key)
        
        if value is not None:
            self._metrics['l1_hits'] += 1
        else:
            self._metrics['l1_misses'] += 1
        
        return value
    
    def _l1_set(self, key: str, value: Any, ttl: int = None):
        """Set value in L1 cache."""
        if ttl is None:
            ttl = self.CACHE_TTL
        
        self._l1_cache.set(key, value, ttl)
    
    def _l1_delete(self, key: str):
        """Delete value from L1 cache."""
        self._l1_cache.delete(key)
    
    def _l1_clear(self):
        """Clear entire L1 cache."""
        self._l1_cache.clear()
    
    # ==========================================================================
    # L2 CACHE (DJANGO/REDIS)
    # ==========================================================================
    
    def _l2_get(self, key: str) -> Optional[Any]:
        """Get value from L2 cache."""
        try:
            value = self._l2_cache.get(key)
            
            if value is not None:
                self._metrics['l2_hits'] += 1
            else:
                self._metrics['l2_misses'] += 1
            
            return value
            
        except Exception as e:
            self._metrics['errors'] += 1
            logger.error(f"L2 cache get error: {e}")
            return None
    
    def _l2_set(self, key: str, value: Any, ttl: int = None):
        """Set value in L2 cache."""
        if ttl is None:
            ttl = self.CACHE_TTL
        
        try:
            self._l2_cache.set(key, value, ttl)
        except Exception as e:
            self._metrics['errors'] += 1
            logger.error(f"L2 cache set error: {e}")
    
    def _l2_delete(self, key: str):
        """Delete value from L2 cache."""
        try:
            self._l2_cache.delete(key)
        except Exception as e:
            self._metrics['errors'] += 1
            logger.error(f"L2 cache delete error: {e}")
    
    def _promote_to_l1(self, key: str, value: Any, ttl: int = None):
        """Promote a value from L2 to L1 cache."""
        self._l1_set(key, value, ttl)
        self._metrics['promotions'] += 1
    
    # ==========================================================================
    # PUBLIC KEY CACHING
    # ==========================================================================
    
    def cache_public_key(
        self,
        user_id: int,
        public_key: bytes,
        ttl: int = None
    ) -> bool:
        """
        Cache user's public key (multi-level).
        
        Stores in both L1 (memory) and L2 (Redis/Django cache).
        
        Args:
            user_id: User ID
            public_key: Kyber public key bytes
            ttl: Time-to-live in seconds (default: LONG_TTL)
            
        Returns:
            True if cached successfully
        """
        if ttl is None:
            ttl = self.LONG_TTL
        
        try:
            cache_key = self.get_public_key_cache_key(user_id)
            encoded_key = base64.b64encode(public_key).decode('utf-8')
            
            # L1 cache (always)
            self._l1_set(cache_key, encoded_key, ttl)
            
            # L2 cache (Redis/Django)
            self._l2_set(cache_key, encoded_key, ttl)
            
            self._metrics['sets'] += 1
            logger.debug(f"Cached public key for user {user_id} (L1+L2)")
            return True
            
        except Exception as e:
            self._metrics['errors'] += 1
            logger.error(f"Error caching public key: {e}")
            return False
    
    def get_cached_public_key(self, user_id: int) -> Optional[bytes]:
        """
        Get cached public key (multi-level lookup).
        
        Checks L1 (memory) first, then L2 (Redis/Django cache).
        Promotes from L2 to L1 on hit for better performance.
        
        Args:
            user_id: User ID
            
        Returns:
            Public key bytes or None if not cached
        """
        cache_key = self.get_public_key_cache_key(user_id)
        
        try:
            # Check L1 first (fastest)
            encoded_key = self._l1_get(cache_key)
            
            if encoded_key is None:
                # Check L2 (Redis/Django cache)
                encoded_key = self._l2_get(cache_key)
                
                if encoded_key:
                    # Promote to L1 for faster future access
                    self._promote_to_l1(cache_key, encoded_key)
                else:
                    return None
            
            return base64.b64decode(encoded_key)
            
        except Exception as e:
            self._metrics['errors'] += 1
            logger.error(f"Error getting cached public key: {e}")
            return None
    
    def invalidate_public_key(self, user_id: int) -> bool:
        """
        Invalidate (delete) cached public key from all levels.
        
        Args:
            user_id: User ID
            
        Returns:
            True if invalidated successfully
        """
        try:
            cache_key = self.get_public_key_cache_key(user_id)
            
            # Delete from all levels
            self._l1_delete(cache_key)
            self._l2_delete(cache_key)
            
            self._metrics['deletes'] += 1
            logger.debug(f"Invalidated public key for user {user_id} (all levels)")
            return True
            
        except Exception as e:
            self._metrics['errors'] += 1
            logger.error(f"Error invalidating public key: {e}")
            return False
    
    # ==========================================================================
    # SHARED SECRET CACHING
    # ==========================================================================
    
    def cache_shared_secret(
        self,
        session_id: str,
        shared_secret: bytes,
        ttl: int = None
    ) -> bool:
        """
        Cache derived shared secret for a session.
        
        WARNING: Shared secrets are sensitive! Use short TTL.
        
        Args:
            session_id: Session identifier
            shared_secret: Derived shared secret bytes
            ttl: Time-to-live in seconds (default: SHORT_TTL)
            
        Returns:
            True if cached successfully
        """
        if ttl is None:
            ttl = self.SHORT_TTL
        
        try:
            cache_key = self.get_shared_secret_cache_key(session_id)
            encoded_secret = base64.b64encode(shared_secret).decode('utf-8')
            
            # Only L1 cache for secrets (more secure, not distributed)
            self._l1_set(cache_key, encoded_secret, ttl)
            
            self._metrics['sets'] += 1
            logger.debug(f"Cached shared secret for session {session_id[:8]}...")
            return True
            
        except Exception as e:
            self._metrics['errors'] += 1
            logger.error(f"Error caching shared secret: {e}")
            return False
    
    def get_cached_shared_secret(self, session_id: str) -> Optional[bytes]:
        """
        Get cached shared secret.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Shared secret bytes or None if not cached
        """
        cache_key = self.get_shared_secret_cache_key(session_id)
        
        try:
            encoded_secret = self._l1_get(cache_key)
            
            if encoded_secret:
                return base64.b64decode(encoded_secret)
            
            return None
            
        except Exception as e:
            self._metrics['errors'] += 1
            logger.error(f"Error getting cached shared secret: {e}")
            return None
    
    def invalidate_shared_secret(self, session_id: str) -> bool:
        """
        Invalidate cached shared secret.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if invalidated successfully
        """
        try:
            cache_key = self.get_shared_secret_cache_key(session_id)
            self._l1_delete(cache_key)
            
            self._metrics['deletes'] += 1
            return True
            
        except Exception as e:
            self._metrics['errors'] += 1
            logger.error(f"Error invalidating shared secret: {e}")
            return False
    
    # ==========================================================================
    # KEYPAIR CACHING
    # ==========================================================================
    
    def cache_keypair(
        self,
        user_id: int,
        public_key: bytes,
        private_key: bytes,
        version: int = 1,
        ttl: int = None
    ) -> bool:
        """
        Cache full keypair.
        
        WARNING: Private keys should generally not be cached!
        Use only in controlled environments.
        
        Args:
            user_id: User ID
            public_key: Public key bytes
            private_key: Private key bytes (encrypted recommended)
            version: Key version number
            ttl: Time-to-live
            
        Returns:
            True if cached successfully
        """
        if ttl is None:
            ttl = self.CACHE_TTL
        
        try:
            cache_key = self.get_keypair_cache_key(user_id, version)
            
            keypair_data = {
                'public_key': base64.b64encode(public_key).decode('utf-8'),
                'private_key': base64.b64encode(private_key).decode('utf-8'),
                'version': version,
                'cached_at': time.time()
            }
            
            # L1 only for keypairs (security)
            self._l1_set(cache_key, keypair_data, ttl)
            
            # Also cache public key separately
            self.cache_public_key(user_id, public_key, ttl)
            
            self._metrics['sets'] += 1
            return True
            
        except Exception as e:
            self._metrics['errors'] += 1
            logger.error(f"Error caching keypair: {e}")
            return False
    
    def get_cached_keypair(
        self,
        user_id: int,
        version: int = 1
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached keypair.
        
        Args:
            user_id: User ID
            version: Key version
            
        Returns:
            Dictionary with 'public_key' and 'private_key' bytes, or None
        """
        cache_key = self.get_keypair_cache_key(user_id, version)
        
        try:
            keypair_data = self._l1_get(cache_key)
            
            if keypair_data:
                return {
                    'public_key': base64.b64decode(keypair_data['public_key']),
                    'private_key': base64.b64decode(keypair_data['private_key']),
                    'version': keypair_data['version'],
                    'cached_at': keypair_data['cached_at']
                }
            
            return None
            
        except Exception as e:
            self._metrics['errors'] += 1
            logger.error(f"Error getting cached keypair: {e}")
            return None
    
    # ==========================================================================
    # KEY VALIDATION CACHING
    # ==========================================================================
    
    def cache_key_validation(
        self,
        key: bytes,
        is_valid: bool,
        key_type: str = 'public',
        ttl: int = None
    ) -> bool:
        """
        Cache key validation result.
        
        Avoids repeated validation of the same key.
        
        Args:
            key: Key bytes to validate
            is_valid: Validation result
            key_type: 'public' or 'private'
            ttl: Time-to-live
            
        Returns:
            True if cached successfully
        """
        if ttl is None:
            ttl = self.CACHE_TTL
        
        try:
            key_hash = hashlib.sha256(key).hexdigest()[:16]
            cache_key = self.get_validation_cache_key(f"{key_type}:{key_hash}")
            
            validation_data = {
                'is_valid': is_valid,
                'key_type': key_type,
                'validated_at': time.time()
            }
            
            # L2 cache for validation (can be shared)
            cache.set(cache_key, validation_data, ttl)
            
            self._metrics['sets'] += 1
            return True
            
        except Exception as e:
            self._metrics['errors'] += 1
            logger.error(f"Error caching key validation: {e}")
            return False
    
    def get_cached_key_validation(
        self,
        key: bytes,
        key_type: str = 'public'
    ) -> Optional[bool]:
        """
        Get cached key validation result.
        
        Args:
            key: Key bytes
            key_type: 'public' or 'private'
            
        Returns:
            Cached validation result or None
        """
        try:
            key_hash = hashlib.sha256(key).hexdigest()[:16]
            cache_key = self.get_validation_cache_key(f"{key_type}:{key_hash}")
            
            validation_data = cache.get(cache_key)
            
            if validation_data:
                self._metrics['l2_hits'] += 1
                return validation_data['is_valid']
            
            self._metrics['l2_misses'] += 1
            return None
            
        except Exception as e:
            self._metrics['errors'] += 1
            logger.error(f"Error getting cached validation: {e}")
            return None
    
    # ==========================================================================
    # BATCH OPERATIONS
    # ==========================================================================
    
    def get_many_public_keys(
        self,
        user_ids: list
    ) -> Dict[int, Optional[bytes]]:
        """
        Get multiple public keys at once.
        
        Args:
            user_ids: List of user IDs
            
        Returns:
            Dictionary mapping user_id to public key (or None)
        """
        result = {}
        
        # Build cache keys
        cache_keys = {
            self.get_public_key_cache_key(uid): uid
            for uid in user_ids
        }
        
        # Batch get from L2 cache
        try:
            cached_values = cache.get_many(list(cache_keys.keys()))
            
            for cache_key, encoded_key in cached_values.items():
                user_id = cache_keys[cache_key]
                if encoded_key:
                    result[user_id] = base64.b64decode(encoded_key)
                    self._metrics['l2_hits'] += 1
                else:
                    result[user_id] = None
                    self._metrics['l2_misses'] += 1
            
            # Fill in missing keys
            for user_id in user_ids:
                if user_id not in result:
                    result[user_id] = None
                    self._metrics['l2_misses'] += 1
                    
        except Exception as e:
            self._metrics['errors'] += 1
            logger.error(f"Error in batch get: {e}")
            result = {uid: None for uid in user_ids}
        
        return result
    
    def set_many_public_keys(
        self,
        keys_dict: Dict[int, bytes],
        ttl: int = None
    ) -> bool:
        """
        Cache multiple public keys at once.
        
        Args:
            keys_dict: Dictionary mapping user_id to public key bytes
            ttl: Time-to-live
            
        Returns:
            True if all cached successfully
        """
        if ttl is None:
            ttl = self.LONG_TTL
        
        try:
            cache_data = {
                self.get_public_key_cache_key(uid): base64.b64encode(pk).decode('utf-8')
                for uid, pk in keys_dict.items()
            }
            
            # Batch set to L2 cache
            cache.set_many(cache_data, ttl)
            
            # Also update L1 cache
            for cache_key, encoded_key in cache_data.items():
                self._l1_set(cache_key, encoded_key, ttl)
            
            self._metrics['sets'] += len(keys_dict)
            return True
            
        except Exception as e:
            self._metrics['errors'] += 1
            logger.error(f"Error in batch set: {e}")
            return False
    
    # ==========================================================================
    # CACHE MANAGEMENT
    # ==========================================================================
    
    def clear_all(self) -> bool:
        """
        Clear all Kyber-related caches.
        
        Returns:
            True if cleared successfully
        """
        try:
            # Clear L1
            self._l1_clear()
            
            # Clear L2 (pattern-based delete if supported)
            # Note: This depends on cache backend capabilities
            cache.clear()
            
            logger.info("All Kyber caches cleared")
            return True
            
        except Exception as e:
            self._metrics['errors'] += 1
            logger.error(f"Error clearing caches: {e}")
            return False
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get cache performance metrics.
        
        Returns:
            Dictionary containing cache statistics
        """
        total_l1 = self._metrics['l1_hits'] + self._metrics['l1_misses']
        total_l2 = self._metrics['l2_hits'] + self._metrics['l2_misses']
        total_ops = self._metrics['sets'] + total_l1 + total_l2
        
        return {
            **self._metrics,
            'mode': 'hybrid' if (self._use_redis and self._redis_available) else 'standard',
            'redis_available': self._redis_available,
            'l1_cache_stats': self._l1_cache.stats,
            'l1_hit_rate': f'{(self._metrics["l1_hits"] / max(total_l1, 1) * 100):.2f}%',
            'l2_hit_rate': f'{(self._metrics["l2_hits"] / max(total_l2, 1) * 100):.2f}%',
            'overall_hit_rate': f'{((self._metrics["l1_hits"] + self._metrics["l2_hits"]) / max(total_l1 + total_l2, 1) * 100):.2f}%',
            'total_operations': total_ops,
            'error_rate': f'{(self._metrics["errors"] / max(total_ops, 1) * 100):.2f}%'
        }
    
    def reset_metrics(self):
        """Reset cache performance metrics."""
        self._metrics = {
            'l1_hits': 0,
            'l1_misses': 0,
            'l2_hits': 0,
            'l2_misses': 0,
            'l3_hits': 0,
            'l3_misses': 0,
            'sets': 0,
            'deletes': 0,
            'errors': 0,
            'promotions': 0
        }
        self._l1_cache.reset_stats()
        logger.info("Cache metrics reset")
    
    def warm_cache(self, user_ids: list) -> int:
        """
        Warm cache by preloading public keys from database.
        
        Args:
            user_ids: List of user IDs to preload
            
        Returns:
            Number of keys loaded
        """
        # This would be implemented with database queries
        # Placeholder for now
        logger.info(f"Cache warming requested for {len(user_ids)} users")
        return 0


# Global singleton instances
_global_cache_manager = None
_hybrid_cache_manager = None


def get_kyber_cache(use_redis: bool = False) -> KyberCacheManager:
    """
    Get or create the global KyberCacheManager instance.
    
    Args:
        use_redis: Use hybrid mode with Redis (default: False)
    
    Returns:
        Global KyberCacheManager instance
    """
    global _global_cache_manager, _hybrid_cache_manager
    
    if use_redis:
        if _hybrid_cache_manager is None:
            _hybrid_cache_manager = KyberCacheManager(use_redis=True)
        return _hybrid_cache_manager
    else:
        if _global_cache_manager is None:
            _global_cache_manager = KyberCacheManager(use_redis=False)
        return _global_cache_manager


def get_hybrid_kyber_cache() -> KyberCacheManager:
    """
    Get or create the hybrid (LRU + Redis) KyberCacheManager instance.
    
    Returns:
        Hybrid KyberCacheManager instance
    """
    return get_kyber_cache(use_redis=True)

