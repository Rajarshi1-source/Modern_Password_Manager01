"""
Tests for Concrete-Python FHE Service

Tests cover:
- Password length encryption
- Character count encryption
- Homomorphic comparison
- Strength circuit evaluation
- Fallback mode behavior
"""

import pytest
import time
from unittest.mock import Mock, patch

# Import the service
import sys
sys.path.insert(0, '../../password_manager')

from fhe_service.services.concrete_service import (
    ConcreteService,
    ConcreteConfig,
    EncryptedValue,
    ConcreteOperationType,
    get_concrete_service,
    CONCRETE_AVAILABLE
)


class TestConcreteServiceBasic:
    """Basic tests for ConcreteService."""
    
    def test_service_initialization(self):
        """Test service initializes without error."""
        service = ConcreteService()
        assert service is not None
        assert service.config is not None
    
    def test_service_with_custom_config(self):
        """Test service with custom configuration."""
        config = ConcreteConfig(
            security_level=128,
            enable_parallel=False,
            max_circuit_depth=8
        )
        service = ConcreteService(config)
        assert service.config.security_level == 128
        assert service.config.enable_parallel == False
    
    def test_is_available_property(self):
        """Test availability check."""
        service = ConcreteService()
        # Should return True if concrete is available and initialized
        # or False if not available
        assert isinstance(service.is_available, bool)
    
    def test_get_status(self):
        """Test status reporting."""
        service = ConcreteService()
        status = service.get_status()
        
        assert 'available' in status
        assert 'concrete_installed' in status
        assert 'initialized' in status
        assert 'compiled_circuits' in status
        assert 'config' in status


class TestPasswordLengthEncryption:
    """Tests for password length encryption."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.service = ConcreteService()
    
    def test_encrypt_password_length(self):
        """Test encrypting password length."""
        result = self.service.encrypt_password_length(12)
        
        assert isinstance(result, EncryptedValue)
        assert result.operation_type == "password_length"
        assert result.ciphertext is not None
        assert result.encrypted_at > 0
    
    def test_encrypt_password_length_bounds(self):
        """Test password length bounds handling."""
        # Test minimum
        result_min = self.service.encrypt_password_length(0)
        assert isinstance(result_min, EncryptedValue)
        
        # Test maximum clamping
        result_max = self.service.encrypt_password_length(200)
        assert isinstance(result_max, EncryptedValue)
    
    def test_encrypt_password_length_negative(self):
        """Test negative length handling."""
        result = self.service.encrypt_password_length(-5)
        assert isinstance(result, EncryptedValue)
        # Should clamp to 0


class TestCharacterCountEncryption:
    """Tests for character count encryption."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.service = ConcreteService()
    
    def test_encrypt_character_counts(self):
        """Test encrypting character counts."""
        counts = {
            'lowercase': 5,
            'uppercase': 3,
            'digits': 2,
            'special': 1
        }
        
        result = self.service.encrypt_character_counts(counts)
        
        assert isinstance(result, EncryptedValue)
        assert result.operation_type == "character_count"
    
    def test_encrypt_character_counts_empty(self):
        """Test with empty counts."""
        counts = {}
        result = self.service.encrypt_character_counts(counts)
        assert isinstance(result, EncryptedValue)
    
    def test_encrypt_character_counts_partial(self):
        """Test with partial counts."""
        counts = {'lowercase': 10}
        result = self.service.encrypt_character_counts(counts)
        assert isinstance(result, EncryptedValue)


class TestHomomorphicComparison:
    """Tests for homomorphic comparison operations."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.service = ConcreteService()
    
    def test_homomorphic_compare_greater(self):
        """Test comparison when first value is greater."""
        ct1 = self.service.encrypt_password_length(20)
        ct2 = self.service.encrypt_password_length(10)
        
        result = self.service.homomorphic_compare(ct1, ct2)
        
        assert isinstance(result, EncryptedValue)
        assert result.operation_type == "homomorphic_compare"
    
    def test_homomorphic_compare_less(self):
        """Test comparison when first value is less."""
        ct1 = self.service.encrypt_password_length(5)
        ct2 = self.service.encrypt_password_length(15)
        
        result = self.service.homomorphic_compare(ct1, ct2)
        assert isinstance(result, EncryptedValue)
    
    def test_homomorphic_compare_equal(self):
        """Test comparison when values are equal."""
        ct1 = self.service.encrypt_password_length(10)
        ct2 = self.service.encrypt_password_length(10)
        
        result = self.service.homomorphic_compare(ct1, ct2)
        assert isinstance(result, EncryptedValue)


class TestStrengthCircuit:
    """Tests for strength evaluation circuit."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.service = ConcreteService()
    
    def test_evaluate_strength_strong_password(self):
        """Test strength evaluation for strong password."""
        enc_result, score = self.service.evaluate_strength_circuit(
            length=16,
            char_types=4,
            has_common_pattern=False
        )
        
        assert isinstance(enc_result, EncryptedValue)
        assert score is not None
        assert 0 <= score <= 100
        assert score >= 60  # Strong password should score high
    
    def test_evaluate_strength_weak_password(self):
        """Test strength evaluation for weak password."""
        enc_result, score = self.service.evaluate_strength_circuit(
            length=4,
            char_types=1,
            has_common_pattern=True
        )
        
        assert score is not None
        assert score < 50  # Weak password should score low
    
    def test_evaluate_strength_medium_password(self):
        """Test strength evaluation for medium password."""
        enc_result, score = self.service.evaluate_strength_circuit(
            length=8,
            char_types=2,
            has_common_pattern=False
        )
        
        assert score is not None
        # Medium password


class TestFallbackBehavior:
    """Tests for fallback mode when Concrete is not available."""
    
    def test_fallback_encrypt(self):
        """Test fallback encryption produces valid output."""
        service = ConcreteService()
        
        # Use the fallback method directly
        result = service._fallback_encrypt(12, "password_length")
        
        assert isinstance(result, EncryptedValue)
        assert result.metadata.get('fallback') == True
        assert result.metadata.get('fallback_value') == 12
    
    def test_fallback_strength(self):
        """Test fallback strength calculation."""
        service = ConcreteService()
        
        score = service._fallback_strength(
            length=12,
            char_types=3,
            has_common_pattern=False
        )
        
        assert 0 <= score <= 100


class TestSingletonPattern:
    """Tests for singleton service pattern."""
    
    def test_get_concrete_service_singleton(self):
        """Test singleton returns same instance."""
        service1 = get_concrete_service()
        service2 = get_concrete_service()
        
        assert service1 is service2


class TestPerformance:
    """Performance tests for ConcreteService."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.service = ConcreteService()
    
    def test_encryption_latency(self):
        """Test encryption completes in acceptable time."""
        start = time.time()
        
        for _ in range(10):
            self.service.encrypt_password_length(12)
        
        elapsed = (time.time() - start) * 1000  # ms
        avg_latency = elapsed / 10
        
        # Should complete in under 100ms average (fallback mode)
        assert avg_latency < 100, f"Average latency {avg_latency}ms exceeds threshold"
    
    def test_strength_evaluation_latency(self):
        """Test strength evaluation completes in acceptable time."""
        start = time.time()
        
        for _ in range(10):
            self.service.evaluate_strength_circuit(12, 3, False)
        
        elapsed = (time.time() - start) * 1000
        avg_latency = elapsed / 10
        
        assert avg_latency < 200, f"Average latency {avg_latency}ms exceeds threshold"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

