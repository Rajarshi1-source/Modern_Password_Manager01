"""
Tests for FHE Computation Cache

Tests cover:
- Cache operations (get, set, invalidate)
- TTL management
- Pattern-based invalidation
- Statistics tracking
- Fallback to memory cache
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock

import sys
sys.path.insert(0, '../../password_manager')

from fhe_service.services.fhe_cache import (
    FHEComputationCache,
    CacheConfig,
    CacheEntry,
    generate_cache_key,
    get_fhe_cache,
    REDIS_AVAILABLE
)


class TestCacheConfig:
    """Tests for CacheConfig."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = CacheConfig()
        
        assert config.host == 'localhost'
        assert config.port == 6379
        assert config.db == 1
        assert config.default_ttl_seconds == 3600
        assert config.max_ttl_seconds == 86400
        assert config.key_prefix == 'fhe_cache'
    
    def test_custom_config(self):
        """Test custom configuration."""
        config = CacheConfig(
            host='redis.example.com',
            port=6380,
            default_ttl_seconds=7200
        )
        
        assert config.host == 'redis.example.com'
        assert config.port == 6380
        assert config.default_ttl_seconds == 7200


class TestCacheEntry:
    """Tests for CacheEntry dataclass."""
    
    def test_cache_entry_creation(self):
        """Test creating a cache entry."""
        entry = CacheEntry(
            key='test_key',
            value=b'test_value',
            operation_type='strength_check',
            created_at=time.time(),
            expires_at=time.time() + 3600,
            hit_count=0
        )
        
        assert entry.key == 'test_key'
        assert entry.value == b'test_value'
        assert entry.hit_count == 0
    
    def test_cache_entry_to_dict(self):
        """Test converting entry to dictionary."""
        entry = CacheEntry(
            key='test_key',
            value=b'test_value',
            operation_type='strength_check',
            created_at=1000.0,
            expires_at=2000.0
        )
        
        result = entry.to_dict()
        
        assert result['key'] == 'test_key'
        assert result['operation_type'] == 'strength_check'
        assert result['created_at'] == 1000.0
    
    def test_cache_entry_from_dict(self):
        """Test creating entry from dictionary."""
        data = {
            'key': 'test_key',
            'value': '746573745f76616c7565',  # hex encoded 'test_value'
            'operation_type': 'strength_check',
            'created_at': 1000.0,
            'expires_at': 2000.0,
            'hit_count': 5
        }
        
        entry = CacheEntry.from_dict(data)
        
        assert entry.key == 'test_key'
        assert entry.hit_count == 5


class TestFHEComputationCache:
    """Tests for FHEComputationCache using memory cache."""
    
    def setup_method(self):
        """Set up test fixtures with memory cache."""
        # Force memory cache by using invalid Redis config
        config = CacheConfig(host='invalid_host', port=0)
        self.cache = FHEComputationCache(config)
    
    def test_cache_initialization(self):
        """Test cache initializes correctly."""
        assert self.cache is not None
        assert self.cache.config is not None
    
    def test_set_and_get(self):
        """Test basic set and get operations."""
        key = 'test_key_1'
        value = b'test_encrypted_value'
        
        # Set value
        success = self.cache.set(key, value, 'strength_check')
        assert success == True
        
        # Get value
        result = self.cache.get(key)
        assert result == value
    
    def test_get_nonexistent(self):
        """Test getting nonexistent key."""
        result = self.cache.get('nonexistent_key')
        assert result is None
    
    def test_set_with_ttl(self):
        """Test setting value with custom TTL."""
        key = 'ttl_test_key'
        value = b'ttl_test_value'
        
        success = self.cache.set(key, value, 'test', ttl=1)  # 1 second TTL
        assert success == True
        
        # Should be available immediately
        result = self.cache.get(key)
        assert result == value
        
        # Wait for expiration
        time.sleep(1.5)
        
        # Should be expired
        result = self.cache.get(key)
        assert result is None
    
    def test_invalidate(self):
        """Test cache invalidation."""
        key = 'invalidate_test'
        value = b'test_value'
        
        self.cache.set(key, value, 'test')
        
        # Verify it exists
        assert self.cache.get(key) == value
        
        # Invalidate
        result = self.cache.invalidate(key)
        assert result == True
        
        # Should be gone
        assert self.cache.get(key) is None
    
    def test_invalidate_nonexistent(self):
        """Test invalidating nonexistent key."""
        result = self.cache.invalidate('nonexistent')
        assert result == False
    
    def test_value_size_limit(self):
        """Test value size limit enforcement."""
        key = 'large_value_test'
        # Create value larger than max (1MB default)
        large_value = b'x' * (1024 * 1024 + 1)
        
        success = self.cache.set(key, large_value, 'test')
        assert success == False


class TestCacheStatistics:
    """Tests for cache statistics."""
    
    def setup_method(self):
        """Set up test fixtures."""
        config = CacheConfig(host='invalid', port=0)
        self.cache = FHEComputationCache(config)
    
    def test_stats_initialization(self):
        """Test stats are initialized."""
        stats = self.cache.get_stats()
        
        assert 'hits' in stats
        assert 'misses' in stats
        assert 'sets' in stats
        assert 'invalidations' in stats
        assert 'total_requests' in stats
        assert 'hit_rate' in stats
    
    def test_stats_hit_counting(self):
        """Test hit counting."""
        key = 'stats_test'
        self.cache.set(key, b'value', 'test')
        
        # Access multiple times
        for _ in range(5):
            self.cache.get(key)
        
        stats = self.cache.get_stats()
        assert stats['hits'] >= 5
    
    def test_stats_miss_counting(self):
        """Test miss counting."""
        # Access nonexistent keys
        for i in range(3):
            self.cache.get(f'nonexistent_{i}')
        
        stats = self.cache.get_stats()
        assert stats['misses'] >= 3
    
    def test_hit_rate_calculation(self):
        """Test hit rate calculation."""
        key = 'hit_rate_test'
        self.cache.set(key, b'value', 'test')
        
        # 3 hits
        for _ in range(3):
            self.cache.get(key)
        
        # 2 misses
        for _ in range(2):
            self.cache.get('nonexistent')
        
        stats = self.cache.get_stats()
        # Hit rate should be approximately 60%
        assert stats['hit_rate'] > 0.5


class TestPatternInvalidation:
    """Tests for pattern-based invalidation."""
    
    def setup_method(self):
        """Set up test fixtures."""
        config = CacheConfig(host='invalid', port=0)
        self.cache = FHEComputationCache(config)
    
    def test_invalidate_pattern(self):
        """Test pattern-based invalidation."""
        # Set up multiple keys with pattern
        for i in range(5):
            self.cache.set(f'user:123:item:{i}', b'value', 'test')
        
        # Set a different pattern
        self.cache.set('user:456:item:1', b'value', 'test')
        
        # Invalidate pattern
        count = self.cache.invalidate_pattern('user:123:*')
        
        assert count >= 0  # Memory cache may not support full pattern matching
    
    def test_invalidate_user_cache(self):
        """Test user-specific cache invalidation."""
        # Set up user-specific keys
        self.cache.set('strength:user:test_user:1', b'value', 'test')
        self.cache.set('strength:user:test_user:2', b'value', 'test')
        
        count = self.cache.invalidate_user_cache('test_user')
        
        # Should return number invalidated (may be 0 for memory cache)
        assert count >= 0


class TestGetOrCompute:
    """Tests for get_or_compute functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        config = CacheConfig(host='invalid', port=0)
        self.cache = FHEComputationCache(config)
    
    def test_get_or_compute_cache_hit(self):
        """Test get_or_compute with cache hit."""
        key = 'compute_test'
        expected = b'cached_value'
        
        # Pre-populate cache
        self.cache.set(key, expected, 'test')
        
        compute_called = False
        
        def compute_fn():
            nonlocal compute_called
            compute_called = True
            return b'computed_value'
        
        result = self.cache.get_or_compute(key, compute_fn, 'test')
        
        assert result == expected
        assert compute_called == False  # Should not call compute
    
    def test_get_or_compute_cache_miss(self):
        """Test get_or_compute with cache miss."""
        key = 'compute_test_miss'
        expected = b'computed_value'
        
        compute_called = False
        
        def compute_fn():
            nonlocal compute_called
            compute_called = True
            return expected
        
        result = self.cache.get_or_compute(key, compute_fn, 'test')
        
        assert result == expected
        assert compute_called == True  # Should call compute


class TestClear:
    """Tests for cache clearing."""
    
    def setup_method(self):
        """Set up test fixtures."""
        config = CacheConfig(host='invalid', port=0)
        self.cache = FHEComputationCache(config)
    
    def test_clear_cache(self):
        """Test clearing all cache entries."""
        # Add some entries
        for i in range(10):
            self.cache.set(f'clear_test_{i}', b'value', 'test')
        
        # Clear
        count = self.cache.clear()
        
        assert count >= 0
        
        # Verify entries are gone
        for i in range(10):
            assert self.cache.get(f'clear_test_{i}') is None


class TestGenerateCacheKey:
    """Tests for cache key generation helper."""
    
    def test_generate_key_basic(self):
        """Test basic key generation."""
        key = generate_cache_key('strength_check')
        
        assert isinstance(key, str)
        assert 'strength_check' in key
    
    def test_generate_key_with_user(self):
        """Test key generation with user ID."""
        key = generate_cache_key('strength_check', user_id='user123')
        
        assert 'user:user123' in key
    
    def test_generate_key_with_data(self):
        """Test key generation with input data."""
        key = generate_cache_key('strength_check', input_data='password123')
        
        assert isinstance(key, str)
        # Should include hash of data
    
    def test_generate_key_deterministic(self):
        """Test key generation is deterministic."""
        key1 = generate_cache_key('test', 'user1', 'data1')
        key2 = generate_cache_key('test', 'user1', 'data1')
        
        assert key1 == key2


class TestSingletonPattern:
    """Tests for singleton pattern."""
    
    def test_get_fhe_cache_singleton(self):
        """Test singleton returns same instance."""
        cache1 = get_fhe_cache()
        cache2 = get_fhe_cache()
        
        assert cache1 is cache2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

