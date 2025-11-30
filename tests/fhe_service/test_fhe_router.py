"""
Tests for FHE Operation Router

Tests cover:
- Routing decisions
- Tier selection
- Budget-based routing
- Operation execution
- Cache integration
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock

import sys
sys.path.insert(0, '../../password_manager')

from fhe_service.services.fhe_router import (
    FHEOperationRouter,
    EncryptionTier,
    OperationType,
    ComputationalBudget,
    RoutingDecision,
    get_fhe_router
)


class TestEncryptionTier:
    """Tests for EncryptionTier enum."""
    
    def test_tier_values(self):
        """Test tier enum values."""
        assert EncryptionTier.CLIENT_ONLY.value == 1
        assert EncryptionTier.HYBRID_FHE.value == 2
        assert EncryptionTier.FULL_FHE.value == 3
        assert EncryptionTier.CACHED_FHE.value == 4


class TestOperationType:
    """Tests for OperationType enum."""
    
    def test_operation_types(self):
        """Test all operation types exist."""
        assert OperationType.PASSWORD_SEARCH.value == "password_search"
        assert OperationType.STRENGTH_CHECK.value == "strength_check"
        assert OperationType.BATCH_STRENGTH.value == "batch_strength"
        assert OperationType.BREACH_DETECTION.value == "breach_detection"
        assert OperationType.SIMILARITY_SEARCH.value == "similarity_search"


class TestComputationalBudget:
    """Tests for ComputationalBudget."""
    
    def test_default_budget(self):
        """Test default budget values."""
        budget = ComputationalBudget()
        
        assert budget.max_latency_ms == 1000
        assert budget.max_memory_mb == 512
        assert budget.min_accuracy == 0.9
        assert budget.priority == 5
    
    def test_custom_budget(self):
        """Test custom budget values."""
        budget = ComputationalBudget(
            max_latency_ms=500,
            max_memory_mb=256,
            min_accuracy=0.95,
            priority=8
        )
        
        assert budget.max_latency_ms == 500
        assert budget.min_accuracy == 0.95
    
    def test_allows_full_fhe(self):
        """Test budget full FHE check."""
        # Sufficient budget
        budget1 = ComputationalBudget(max_latency_ms=1000, max_memory_mb=512)
        assert budget1.allows_full_fhe() == True
        
        # Insufficient budget
        budget2 = ComputationalBudget(max_latency_ms=100, max_memory_mb=64)
        assert budget2.allows_full_fhe() == False
    
    def test_allows_hybrid_fhe(self):
        """Test budget hybrid FHE check."""
        # Sufficient budget
        budget1 = ComputationalBudget(max_latency_ms=200, max_memory_mb=128)
        assert budget1.allows_hybrid_fhe() == True
        
        # Insufficient budget
        budget2 = ComputationalBudget(max_latency_ms=50, max_memory_mb=32)
        assert budget2.allows_hybrid_fhe() == False


class TestFHEOperationRouter:
    """Tests for FHEOperationRouter."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.router = FHEOperationRouter()
    
    def test_router_initialization(self):
        """Test router initializes correctly."""
        assert self.router is not None
        assert self.router.COMPLEXITY_RATINGS is not None
        assert self.router.DEFAULT_TIERS is not None
    
    def test_get_status(self):
        """Test status reporting."""
        status = self.router.get_status()
        
        assert 'concrete_available' in status
        assert 'seal_available' in status
        assert 'cache_enabled' in status
        assert 'supported_operations' in status
        assert 'tier_latencies' in status


class TestTierSelection:
    """Tests for tier selection logic."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.router = FHEOperationRouter()
    
    def test_select_tier_for_password_search(self):
        """Test tier selection for password search."""
        budget = ComputationalBudget()
        tier = self.router._select_tier(OperationType.PASSWORD_SEARCH, budget)
        
        # Password search should use HYBRID_FHE by default
        assert tier in [EncryptionTier.HYBRID_FHE, EncryptionTier.CLIENT_ONLY]
    
    def test_select_tier_for_strength_check(self):
        """Test tier selection for strength check."""
        budget = ComputationalBudget(max_latency_ms=2000)
        tier = self.router._select_tier(OperationType.STRENGTH_CHECK, budget)
        
        # Strength check should use FULL_FHE by default
        assert tier in [EncryptionTier.FULL_FHE, EncryptionTier.HYBRID_FHE, EncryptionTier.CLIENT_ONLY]
    
    def test_select_tier_tight_budget_downgrade(self):
        """Test tier selection downgrades with tight budget."""
        # Very tight budget should force CLIENT_ONLY
        budget = ComputationalBudget(max_latency_ms=10, max_memory_mb=16)
        tier = self.router._select_tier(OperationType.STRENGTH_CHECK, budget)
        
        assert tier == EncryptionTier.CLIENT_ONLY


class TestRouteOperation:
    """Tests for route_operation method."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.router = FHEOperationRouter()
    
    def test_route_strength_check(self):
        """Test routing strength check operation."""
        budget = ComputationalBudget(max_latency_ms=1000)
        
        decision, result = self.router.route_operation(
            'strength_check',
            'TestPassword123!',
            budget
        )
        
        assert isinstance(decision, RoutingDecision)
        assert decision.tier is not None
        assert decision.service_name is not None
        assert result is not None
    
    def test_route_encrypted_compare(self):
        """Test routing encrypted compare operation."""
        budget = ComputationalBudget()
        
        decision, result = self.router.route_operation(
            'encrypted_compare',
            (10, 15),
            budget
        )
        
        assert isinstance(decision, RoutingDecision)
    
    def test_route_character_count(self):
        """Test routing character count operation."""
        budget = ComputationalBudget()
        
        decision, result = self.router.route_operation(
            'character_count',
            {'lowercase': 5, 'uppercase': 3, 'digits': 2, 'special': 1},
            budget
        )
        
        assert isinstance(decision, RoutingDecision)
    
    def test_route_invalid_operation(self):
        """Test routing with invalid operation type."""
        budget = ComputationalBudget()
        
        # Should fall back to default handling
        decision, result = self.router.route_operation(
            'unknown_operation',
            'test_data',
            budget
        )
        
        assert isinstance(decision, RoutingDecision)


class TestPasswordFeatureExtraction:
    """Tests for password feature extraction."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.router = FHEOperationRouter()
    
    def test_extract_password_features_strong(self):
        """Test extracting features from strong password."""
        features = self.router._extract_password_features('MyStr0ng!Pass#2024')
        
        assert features['length'] == 18
        assert features['char_types'] == 4  # lower, upper, digit, special
        assert features['char_diversity'] == 1.0
        assert features['has_common_pattern'] == False
    
    def test_extract_password_features_weak(self):
        """Test extracting features from weak password."""
        features = self.router._extract_password_features('password123')
        
        assert features['length'] == 11
        assert features['has_common_pattern'] == True
    
    def test_extract_password_features_dict(self):
        """Test extracting from already-extracted dict."""
        input_features = {
            'length': 12,
            'entropy': 0.7,
            'char_diversity': 0.5,
            'pattern_score': 0.1
        }
        
        features = self.router._extract_password_features(input_features)
        
        assert features['length'] == 12
    
    def test_extract_password_features_empty(self):
        """Test extracting features from empty string."""
        features = self.router._extract_password_features('')
        
        assert features['length'] == 0
        assert features['char_types'] == 0


class TestCacheKeyGeneration:
    """Tests for cache key generation."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.router = FHEOperationRouter()
    
    def test_generate_cache_key(self):
        """Test cache key generation."""
        key = self.router._generate_cache_key('strength_check', 'password123')
        
        assert isinstance(key, str)
        assert key.startswith('fhe:')
    
    def test_cache_key_deterministic(self):
        """Test cache key is deterministic."""
        key1 = self.router._generate_cache_key('strength_check', 'password123')
        key2 = self.router._generate_cache_key('strength_check', 'password123')
        
        assert key1 == key2
    
    def test_cache_key_unique(self):
        """Test cache keys are unique for different inputs."""
        key1 = self.router._generate_cache_key('strength_check', 'password123')
        key2 = self.router._generate_cache_key('strength_check', 'different123')
        
        assert key1 != key2


class TestSingletonPattern:
    """Tests for singleton pattern."""
    
    def test_get_fhe_router_singleton(self):
        """Test singleton returns same instance."""
        router1 = get_fhe_router()
        router2 = get_fhe_router()
        
        assert router1 is router2


class TestPerformance:
    """Performance tests for FHE router."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.router = FHEOperationRouter()
    
    def test_routing_latency(self):
        """Test routing decision latency."""
        budget = ComputationalBudget()
        
        start = time.time()
        
        for _ in range(100):
            self.router.route_operation('strength_check', 'TestPass123!', budget)
        
        elapsed = (time.time() - start) * 1000
        avg_latency = elapsed / 100
        
        # Routing should be very fast (< 50ms average)
        assert avg_latency < 50, f"Average routing latency {avg_latency}ms exceeds threshold"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

