"""
Vault Optimization Service

Provides optimization utilities for the vault:
- Caching layer for non-sensitive data
- Background task helpers
- Query optimization utilities
- Compression utilities

Zero-Knowledge Architecture:
- Server never receives plaintext passwords
- Only encrypted blobs are stored
- Metadata can be indexed for fast queries

Author: SecureVault Password Manager
Version: 2.0.0
"""

import logging
import hashlib
import json
import gzip
import base64
from typing import Dict, Any, List, Optional
from functools import wraps
from datetime import datetime, timedelta

from django.core.cache import cache
from django.conf import settings
from django.db.models import Prefetch, Count
from django.db import connection

logger = logging.getLogger(__name__)


# =============================================================================
# CACHING LAYER
# =============================================================================

class VaultCacheManager:
    """
    Caching manager for vault non-sensitive data.
    
    Cached items:
    - User salt (short TTL)
    - Item counts and statistics
    - Folder structure
    - Non-sensitive metadata
    
    NOT cached (for security):
    - Encrypted data blobs
    - Authentication tokens
    """
    
    # Cache key prefixes
    PREFIX_SALT = 'vault:salt:'
    PREFIX_STATS = 'vault:stats:'
    PREFIX_FOLDERS = 'vault:folders:'
    PREFIX_ITEM_META = 'vault:meta:'
    PREFIX_AUTH_HASH = 'vault:auth:'
    
    # TTL values (seconds)
    TTL_SALT = 300  # 5 minutes
    TTL_STATS = 60  # 1 minute
    TTL_FOLDERS = 300  # 5 minutes
    TTL_META = 120  # 2 minutes
    TTL_AUTH = 600  # 10 minutes
    
    def __init__(self):
        self._local_cache = {}  # In-memory L1 cache
        self._metrics = {
            'hits': 0,
            'misses': 0,
            'sets': 0
        }
    
    def get_user_salt(self, user_id: int) -> Optional[str]:
        """Get cached user salt."""
        key = f"{self.PREFIX_SALT}{user_id}"
        
        # Check L1 first
        if key in self._local_cache:
            self._metrics['hits'] += 1
            return self._local_cache[key]
        
        # Check L2 (Redis/Django cache)
        value = cache.get(key)
        if value:
            self._metrics['hits'] += 1
            self._local_cache[key] = value
            return value
        
        self._metrics['misses'] += 1
        return None
    
    def set_user_salt(self, user_id: int, salt: str):
        """Cache user salt."""
        key = f"{self.PREFIX_SALT}{user_id}"
        self._local_cache[key] = salt
        cache.set(key, salt, self.TTL_SALT)
        self._metrics['sets'] += 1
    
    def get_user_stats(self, user_id: int) -> Optional[Dict]:
        """Get cached user vault statistics."""
        key = f"{self.PREFIX_STATS}{user_id}"
        return cache.get(key)
    
    def set_user_stats(self, user_id: int, stats: Dict):
        """Cache user vault statistics."""
        key = f"{self.PREFIX_STATS}{user_id}"
        cache.set(key, stats, self.TTL_STATS)
    
    def get_user_folders(self, user_id: int) -> Optional[List]:
        """Get cached user folders."""
        key = f"{self.PREFIX_FOLDERS}{user_id}"
        return cache.get(key)
    
    def set_user_folders(self, user_id: int, folders: List):
        """Cache user folders."""
        key = f"{self.PREFIX_FOLDERS}{user_id}"
        cache.set(key, folders, self.TTL_FOLDERS)
    
    def invalidate_user_cache(self, user_id: int):
        """Invalidate all cache for a user."""
        keys = [
            f"{self.PREFIX_SALT}{user_id}",
            f"{self.PREFIX_STATS}{user_id}",
            f"{self.PREFIX_FOLDERS}{user_id}",
            f"{self.PREFIX_AUTH}{user_id}"
        ]
        
        for key in keys:
            cache.delete(key)
            self._local_cache.pop(key, None)
        
        logger.debug(f"Invalidated cache for user {user_id}")
    
    def get_auth_hash(self, user_id: int) -> Optional[str]:
        """Get cached auth hash for verification."""
        key = f"{self.PREFIX_AUTH}{user_id}"
        return cache.get(key)
    
    def set_auth_hash(self, user_id: int, auth_hash: str):
        """Cache auth hash."""
        key = f"{self.PREFIX_AUTH}{user_id}"
        cache.set(key, auth_hash, self.TTL_AUTH)
    
    def get_metrics(self) -> Dict:
        """Get cache metrics."""
        total = self._metrics['hits'] + self._metrics['misses']
        hit_rate = (self._metrics['hits'] / total * 100) if total > 0 else 0
        
        return {
            **self._metrics,
            'hit_rate': f'{hit_rate:.1f}%',
            'local_cache_size': len(self._local_cache)
        }


# Global cache manager instance
vault_cache = VaultCacheManager()


# =============================================================================
# QUERY OPTIMIZATION
# =============================================================================

class VaultQueryOptimizer:
    """
    Query optimization utilities for vault operations.
    
    Optimizations:
    - Selective field loading
    - Prefetch related objects
    - Pagination
    - Index utilization
    """
    
    @staticmethod
    def get_optimized_queryset(user, item_type=None, favorites_only=False):
        """
        Get optimized queryset for vault items.
        
        Uses:
        - select_related for foreign keys
        - only() for selective field loading
        - Proper index usage
        """
        from vault.models.vault_models import EncryptedVaultItem
        
        queryset = EncryptedVaultItem.objects.filter(
            user=user,
            deleted=False
        ).select_related('folder')
        
        # Apply filters
        if item_type:
            queryset = queryset.filter(item_type=item_type)
        
        if favorites_only:
            queryset = queryset.filter(favorite=True)
        
        # Use indexed ordering
        queryset = queryset.order_by('-updated_at')
        
        return queryset
    
    @staticmethod
    def get_metadata_only_queryset(user):
        """
        Get queryset with metadata only (no encrypted_data for listing).
        This reduces payload size significantly.
        """
        from vault.models.vault_models import EncryptedVaultItem
        
        return EncryptedVaultItem.objects.filter(
            user=user,
            deleted=False
        ).only(
            'id', 'item_id', 'item_type', 'favorite',
            'folder_id', 'created_at', 'updated_at',
            'domain_fuzzy_hash'  # For client-side grouping
        ).select_related('folder')
    
    @staticmethod
    def get_user_statistics(user) -> Dict:
        """
        Get vault statistics with optimized queries.
        """
        from vault.models.vault_models import EncryptedVaultItem
        
        # Check cache first
        cached = vault_cache.get_user_stats(user.id)
        if cached:
            return cached
        
        # Single aggregated query
        stats = EncryptedVaultItem.objects.filter(
            user=user,
            deleted=False
        ).values('item_type').annotate(count=Count('id'))
        
        result = {
            'total': 0,
            'by_type': {},
            'favorites': 0
        }
        
        for stat in stats:
            result['by_type'][stat['item_type']] = stat['count']
            result['total'] += stat['count']
        
        # Favorites count
        result['favorites'] = EncryptedVaultItem.objects.filter(
            user=user,
            deleted=False,
            favorite=True
        ).count()
        
        # Cache result
        vault_cache.set_user_stats(user.id, result)
        
        return result
    
    @staticmethod
    def explain_query(queryset) -> str:
        """
        Get query execution plan (for debugging).
        """
        sql = str(queryset.query)
        
        with connection.cursor() as cursor:
            cursor.execute(f"EXPLAIN ANALYZE {sql}")
            return cursor.fetchall()


# =============================================================================
# COMPRESSION UTILITIES
# =============================================================================

class VaultCompression:
    """
    Compression utilities for vault data transfer.
    
    Methods:
    - Gzip compression for large payloads
    - Base64 encoding for binary data
    """
    
    COMPRESSION_THRESHOLD = 1024  # Compress if > 1KB
    
    @staticmethod
    def compress_data(data: Any) -> Dict:
        """
        Compress data if beneficial.
        
        Returns:
            Dict with compressed data and metadata
        """
        if isinstance(data, (dict, list)):
            json_data = json.dumps(data)
        else:
            json_data = str(data)
        
        original_size = len(json_data)
        
        if original_size < VaultCompression.COMPRESSION_THRESHOLD:
            return {
                'data': json_data,
                'compressed': False,
                'original_size': original_size
            }
        
        # Compress with gzip
        compressed = gzip.compress(json_data.encode('utf-8'), compresslevel=6)
        compressed_b64 = base64.b64encode(compressed).decode('utf-8')
        compressed_size = len(compressed_b64)
        
        # Only use compression if it's actually smaller
        if compressed_size < original_size * 0.9:
            return {
                'data': compressed_b64,
                'compressed': True,
                'original_size': original_size,
                'compressed_size': compressed_size,
                'ratio': f'{(1 - compressed_size/original_size) * 100:.1f}%'
            }
        
        return {
            'data': json_data,
            'compressed': False,
            'original_size': original_size
        }
    
    @staticmethod
    def decompress_data(payload: Dict) -> Any:
        """
        Decompress data if needed.
        """
        if not payload.get('compressed', False):
            data = payload.get('data', payload)
            if isinstance(data, str):
                try:
                    return json.loads(data)
                except json.JSONDecodeError:
                    return data
            return data
        
        # Decompress
        compressed = base64.b64decode(payload['data'])
        decompressed = gzip.decompress(compressed)
        
        try:
            return json.loads(decompressed.decode('utf-8'))
        except json.JSONDecodeError:
            return decompressed.decode('utf-8')


# =============================================================================
# AUTH HASH VERIFICATION
# =============================================================================

class AuthHashService:
    """
    Service for verifying client-side generated auth hashes.
    
    Zero-Knowledge Architecture:
    - Client generates auth hash from master password using Argon2id
    - Server stores hash of auth hash (double hashing)
    - Master password never transmitted or stored
    """
    
    @staticmethod
    def hash_auth_hash(auth_hash: str) -> str:
        """
        Hash the client's auth hash for storage.
        This provides an additional layer of protection.
        """
        return hashlib.sha256(auth_hash.encode()).hexdigest()
    
    @staticmethod
    def verify_auth_hash(user_id: int, client_auth_hash: str) -> bool:
        """
        Verify client's auth hash against stored value.
        """
        from vault.models import UserSalt
        
        # Check cache first
        cached_hash = vault_cache.get_auth_hash(user_id)
        
        if cached_hash:
            server_hash = AuthHashService.hash_auth_hash(client_auth_hash)
            return server_hash == cached_hash
        
        # Get from database
        try:
            user_salt = UserSalt.objects.get(user_id=user_id)
            stored_hash = user_salt.auth_hash
            
            if isinstance(stored_hash, memoryview):
                stored_hash = bytes(stored_hash).hex()
            elif isinstance(stored_hash, bytes):
                stored_hash = stored_hash.hex()
            
            # Hash client's auth hash
            server_hash = AuthHashService.hash_auth_hash(client_auth_hash)
            
            # Cache for future requests
            vault_cache.set_auth_hash(user_id, server_hash)
            
            # Constant-time comparison
            return AuthHashService._constant_time_compare(server_hash, stored_hash)
            
        except UserSalt.DoesNotExist:
            return False
    
    @staticmethod
    def _constant_time_compare(a: str, b: str) -> bool:
        """Constant-time string comparison to prevent timing attacks."""
        if len(a) != len(b):
            return False
        
        result = 0
        for x, y in zip(a, b):
            result |= ord(x) ^ ord(y)
        
        return result == 0


# =============================================================================
# DECORATORS
# =============================================================================

def cache_vault_data(ttl: int = 60, key_prefix: str = 'vault'):
    """
    Decorator to cache vault data.
    
    Usage:
        @cache_vault_data(ttl=300, key_prefix='folders')
        def get_user_folders(user):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key from function name and args
            user = kwargs.get('user') or (args[0] if args else None)
            if hasattr(user, 'id'):
                cache_key = f"{key_prefix}:{func.__name__}:{user.id}"
            else:
                cache_key = f"{key_prefix}:{func.__name__}"
            
            # Check cache
            cached = cache.get(cache_key)
            if cached is not None:
                return cached
            
            # Execute function
            result = func(*args, **kwargs)
            
            # Cache result
            cache.set(cache_key, result, ttl)
            
            return result
        return wrapper
    return decorator


def measure_query_time(func):
    """Decorator to measure and log query execution time."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        import time
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = (time.perf_counter() - start) * 1000
        
        logger.debug(f"{func.__name__} executed in {elapsed:.2f}ms")
        
        return result
    return wrapper

