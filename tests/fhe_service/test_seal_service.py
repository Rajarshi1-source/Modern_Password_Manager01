"""
Tests for TenSEAL/SEAL FHE Service

Tests cover:
- Vector encryption
- Password feature encryption
- Batch operations
- SIMD strength evaluation
- Similarity search
- Fallback mode behavior
"""

import pytest
import time
from unittest.mock import Mock, patch

import sys
sys.path.insert(0, '../../password_manager')

from fhe_service.services.seal_service import (
    SEALBatchService,
    SEALConfig,
    SEALCiphertext,
    SEALScheme,
    get_seal_service,
    TENSEAL_AVAILABLE
)


class TestSEALServiceBasic:
    """Basic tests for SEALBatchService."""
    
    def test_service_initialization(self):
        """Test service initializes without error."""
        service = SEALBatchService()
        assert service is not None
        assert service.config is not None
    
    def test_service_with_custom_config(self):
        """Test service with custom configuration."""
        config = SEALConfig(
            poly_modulus_degree=4096,
            security_level=128,
            max_batch_size=64
        )
        service = SEALBatchService(config)
        assert service.config.poly_modulus_degree == 4096
        assert service.config.max_batch_size == 64
    
    def test_is_available_property(self):
        """Test availability check."""
        service = SEALBatchService()
        assert isinstance(service.is_available, bool)
    
    def test_slot_count_property(self):
        """Test slot count property."""
        service = SEALBatchService()
        # Default is 8192, so slot_count should be 4096
        expected = service.config.poly_modulus_degree // 2
        assert service.slot_count == expected
    
    def test_get_status(self):
        """Test status reporting."""
        service = SEALBatchService()
        status = service.get_status()
        
        assert 'available' in status
        assert 'tenseal_installed' in status
        assert 'initialized' in status
        assert 'config' in status


class TestVectorEncryption:
    """Tests for vector encryption."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.service = SEALBatchService()
    
    def test_encrypt_vector(self):
        """Test encrypting a vector of floats."""
        values = [0.5, 0.3, 0.2, 0.1]
        
        result = self.service.encrypt_vector(values)
        
        assert isinstance(result, SEALCiphertext)
        assert result.scheme in ['ckks', 'fallback']
        assert result.ciphertext is not None
    
    def test_encrypt_empty_vector(self):
        """Test encrypting empty vector."""
        result = self.service.encrypt_vector([])
        assert isinstance(result, SEALCiphertext)
    
    def test_encrypt_large_vector(self):
        """Test encrypting large vector."""
        values = [float(i) / 100 for i in range(100)]
        result = self.service.encrypt_vector(values)
        assert isinstance(result, SEALCiphertext)


class TestPasswordFeatureEncryption:
    """Tests for password feature encryption."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.service = SEALBatchService()
    
    def test_encrypt_password_features(self):
        """Test encrypting password features."""
        result = self.service.encrypt_password_features(
            length=16,
            entropy=0.8,
            char_diversity=0.75,
            pattern_score=0.1
        )
        
        assert isinstance(result, SEALCiphertext)
    
    def test_encrypt_password_features_edge_cases(self):
        """Test edge cases for password features."""
        # All zeros
        result = self.service.encrypt_password_features(
            length=0,
            entropy=0.0,
            char_diversity=0.0,
            pattern_score=0.0
        )
        assert isinstance(result, SEALCiphertext)
        
        # All max values
        result = self.service.encrypt_password_features(
            length=100,
            entropy=1.0,
            char_diversity=1.0,
            pattern_score=1.0
        )
        assert isinstance(result, SEALCiphertext)


class TestBatchEncryption:
    """Tests for batch encryption operations."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.service = SEALBatchService()
    
    def test_batch_encrypt_passwords(self):
        """Test batch encrypting password features."""
        features = [
            {'length': 8, 'entropy': 0.5, 'char_diversity': 0.5, 'pattern_score': 0.2},
            {'length': 16, 'entropy': 0.8, 'char_diversity': 0.75, 'pattern_score': 0.0},
            {'length': 4, 'entropy': 0.3, 'char_diversity': 0.25, 'pattern_score': 0.5},
        ]
        
        results = self.service.batch_encrypt_passwords(features)
        
        assert len(results) == 3
        assert all(isinstance(r, SEALCiphertext) for r in results)
    
    def test_batch_encrypt_empty(self):
        """Test batch encrypt with empty list."""
        results = self.service.batch_encrypt_passwords([])
        assert results == []
    
    def test_batch_encrypt_large(self):
        """Test batch encrypt with many passwords."""
        features = [
            {'length': i, 'entropy': 0.5, 'char_diversity': 0.5, 'pattern_score': 0.1}
            for i in range(50)
        ]
        
        results = self.service.batch_encrypt_passwords(features)
        assert len(results) == 50


class TestStrengthEvaluation:
    """Tests for SIMD strength evaluation."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.service = SEALBatchService()
    
    def test_simd_strength_evaluation(self):
        """Test SIMD strength evaluation."""
        encrypted = self.service.encrypt_password_features(
            length=16,
            entropy=0.8,
            char_diversity=0.75,
            pattern_score=0.1
        )
        
        result, score = self.service.simd_strength_evaluation(encrypted)
        
        assert isinstance(result, SEALCiphertext)
        assert score is not None
        assert isinstance(score, (int, float))
    
    def test_simd_strength_with_custom_weights(self):
        """Test strength evaluation with custom weights."""
        encrypted = self.service.encrypt_password_features(
            length=12,
            entropy=0.6,
            char_diversity=0.5,
            pattern_score=0.2
        )
        
        weights = {
            'length': 0.4,
            'entropy': 0.3,
            'diversity': 0.2,
            'pattern': 0.1
        }
        
        result, score = self.service.simd_strength_evaluation(encrypted, weights)
        assert score is not None
    
    def test_batch_strength_evaluation(self):
        """Test batch strength evaluation."""
        encrypted_list = [
            self.service.encrypt_password_features(
                length=l, entropy=0.5, char_diversity=0.5, pattern_score=0.1
            )
            for l in [4, 8, 12, 16, 20]
        ]
        
        scores = self.service.batch_strength_evaluation(encrypted_list)
        
        assert len(scores) == 5
        assert all(isinstance(s, (int, float)) for s in scores)


class TestSimilaritySearch:
    """Tests for encrypted similarity search."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.service = SEALBatchService()
    
    def test_similarity_search_basic(self):
        """Test basic similarity search."""
        query = self.service.encrypt_password_features(
            length=12, entropy=0.7, char_diversity=0.5, pattern_score=0.1
        )
        
        vault = [
            self.service.encrypt_password_features(
                length=12, entropy=0.7, char_diversity=0.5, pattern_score=0.1
            ),
            self.service.encrypt_password_features(
                length=8, entropy=0.4, char_diversity=0.25, pattern_score=0.3
            ),
        ]
        
        results = self.service.encrypted_similarity_search(query, vault, threshold=0.5)
        
        assert isinstance(results, list)
    
    def test_similarity_search_empty_vault(self):
        """Test similarity search with empty vault."""
        query = self.service.encrypt_password_features(
            length=12, entropy=0.7, char_diversity=0.5, pattern_score=0.1
        )
        
        results = self.service.encrypted_similarity_search(query, [], threshold=0.5)
        assert results == []


class TestSerialization:
    """Tests for ciphertext serialization."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.service = SEALBatchService()
    
    def test_serialize_ciphertext(self):
        """Test ciphertext serialization."""
        ct = self.service.encrypt_vector([0.5, 0.3, 0.2])
        
        serialized = self.service.serialize_ciphertext(ct)
        
        # Should return bytes
        assert isinstance(serialized, bytes)
    
    @pytest.mark.skipif(not TENSEAL_AVAILABLE, reason="TenSEAL not available")
    def test_deserialize_ciphertext(self):
        """Test ciphertext deserialization."""
        ct = self.service.encrypt_vector([0.5, 0.3, 0.2])
        serialized = self.service.serialize_ciphertext(ct)
        
        if serialized:
            deserialized = self.service.deserialize_ciphertext(serialized)
            assert deserialized is not None or not self.service.is_available


class TestFallbackBehavior:
    """Tests for fallback mode."""
    
    def test_fallback_encrypt_vector(self):
        """Test fallback vector encryption."""
        service = SEALBatchService()
        
        result = service._fallback_encrypt_vector([0.5, 0.3, 0.2, 0.1])
        
        assert isinstance(result, SEALCiphertext)
        assert result.scheme == 'fallback'
        assert result.metadata.get('fallback') == True
    
    def test_fallback_strength_evaluation(self):
        """Test fallback strength evaluation."""
        service = SEALBatchService()
        
        ct = service._fallback_encrypt_vector([0.5, 0.3, 0.2, 0.1])
        weights = {
            'length': 0.3,
            'entropy': 0.4,
            'diversity': 0.2,
            'pattern': 0.1
        }
        
        result, score = service._fallback_strength_evaluation(ct, weights)
        
        assert score is not None
        assert isinstance(score, (int, float))


class TestSingletonPattern:
    """Tests for singleton pattern."""
    
    def test_get_seal_service_singleton(self):
        """Test singleton returns same instance."""
        service1 = get_seal_service()
        service2 = get_seal_service()
        
        assert service1 is service2


class TestPerformance:
    """Performance tests for SEALBatchService."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.service = SEALBatchService()
    
    def test_vector_encryption_latency(self):
        """Test vector encryption latency."""
        start = time.time()
        
        for _ in range(10):
            self.service.encrypt_vector([0.5, 0.3, 0.2, 0.1])
        
        elapsed = (time.time() - start) * 1000
        avg_latency = elapsed / 10
        
        assert avg_latency < 100, f"Average latency {avg_latency}ms exceeds threshold"
    
    def test_batch_encryption_latency(self):
        """Test batch encryption latency."""
        features = [
            {'length': 12, 'entropy': 0.7, 'char_diversity': 0.5, 'pattern_score': 0.1}
            for _ in range(10)
        ]
        
        start = time.time()
        self.service.batch_encrypt_passwords(features)
        elapsed = (time.time() - start) * 1000
        
        # Should complete in under 500ms for 10 passwords
        assert elapsed < 500, f"Batch encryption took {elapsed}ms"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

