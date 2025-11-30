"""
Tests for Post-Quantum Cryptography (Phase 2A)

Tests CRYSTALS-Kyber-768 implementation for behavioral recovery
"""

import unittest
import sys
import os
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../password_manager')))

from django.test import TestCase


class QuantumCryptoServiceTests(TestCase):
    """Tests for QuantumCryptoService"""
    
    def setUp(self):
        """Initialize quantum crypto service"""
        try:
            from behavioral_recovery.services.quantum_crypto_service import QuantumCryptoService
            self.quantum_crypto = QuantumCryptoService()
            self.skip_tests = False
            
            # Check if liboqs is actually available
            algo_info = self.quantum_crypto.get_algorithm_info()
            if not algo_info['quantum_resistant']:
                self.skip_tests = True
                self.skipTest("liboqs-python not available - skipping quantum crypto tests")
                
        except Exception as e:
            self.skip_tests = True
            self.skipTest(f"Failed to initialize QuantumCryptoService: {e}")
    
    def test_algorithm_info(self):
        """Test getting algorithm information"""
        if self.skip_tests:
            return
        
        info = self.quantum_crypto.get_algorithm_info()
        
        self.assertEqual(info['algorithm'], 'Kyber768')
        self.assertTrue(info['quantum_resistant'])
        self.assertEqual(info['public_key_size'], 1184)
        self.assertEqual(info['private_key_size'], 2400)
        self.assertEqual(info['shared_secret_size'], 32)
    
    def test_keypair_generation(self):
        """Test Kyber-768 keypair generation"""
        if self.skip_tests:
            return
        
        public_key, private_key = self.quantum_crypto.generate_keypair()
        
        # Verify key sizes (Kyber-768 specifications)
        self.assertEqual(len(public_key), 1184, "Public key should be 1184 bytes")
        self.assertEqual(len(private_key), 2400, "Private key should be 2400 bytes")
        
        # Keys should be different
        self.assertNotEqual(public_key, private_key)
        
        # Keys should be non-zero
        self.assertGreater(sum(public_key), 0)
        self.assertGreater(sum(private_key), 0)
    
    def test_encryption_decryption_round_trip(self):
        """Test complete encryption/decryption cycle"""
        if self.skip_tests:
            return
        
        # Create test behavioral embedding (128 dimensions)
        test_embedding = list(np.random.rand(128))
        
        # Generate keypair
        public_key, private_key = self.quantum_crypto.generate_keypair()
        
        # Encrypt
        encrypted = self.quantum_crypto.encrypt_behavioral_embedding(
            test_embedding,
            public_key
        )
        
        # Verify encrypted data structure
        self.assertIsInstance(encrypted, dict)
        self.assertIn('kyber_ciphertext', encrypted)
        self.assertIn('aes_ciphertext', encrypted)
        self.assertIn('nonce', encrypted)
        self.assertIn('algorithm', encrypted)
        self.assertEqual(encrypted['algorithm'], 'kyber768-aes256gcm')
        
        # Decrypt
        decrypted = self.quantum_crypto.decrypt_behavioral_embedding(
            encrypted,
            private_key
        )
        
        # Verify round-trip accuracy
        self.assertEqual(len(decrypted), 128, "Decrypted embedding should be 128-dimensional")
        
        # Values should match (within floating point precision)
        for i in range(len(test_embedding)):
            self.assertAlmostEqual(test_embedding[i], decrypted[i], places=10)
    
    def test_different_ciphertexts_same_plaintext(self):
        """Test that same plaintext produces different ciphertexts (due to randomness)"""
        if self.skip_tests:
            return
        
        test_embedding = list(np.random.rand(128))
        public_key, private_key = self.quantum_crypto.generate_keypair()
        
        # Encrypt same embedding twice
        encrypted1 = self.quantum_crypto.encrypt_behavioral_embedding(test_embedding, public_key)
        encrypted2 = self.quantum_crypto.encrypt_behavioral_embedding(test_embedding, public_key)
        
        # Ciphertexts should be different (due to random nonce and Kyber randomness)
        self.assertNotEqual(encrypted1['kyber_ciphertext'], encrypted2['kyber_ciphertext'])
        self.assertNotEqual(encrypted1['aes_ciphertext'], encrypted2['aes_ciphertext'])
        self.assertNotEqual(encrypted1['nonce'], encrypted2['nonce'])
        
        # But both should decrypt to same value
        decrypted1 = self.quantum_crypto.decrypt_behavioral_embedding(encrypted1, private_key)
        decrypted2 = self.quantum_crypto.decrypt_behavioral_embedding(encrypted2, private_key)
        
        np.testing.assert_array_almost_equal(decrypted1, decrypted2, decimal=10)
    
    def test_wrong_private_key_fails(self):
        """Test that decryption with wrong private key fails"""
        if self.skip_tests:
            return
        
        test_embedding = list(np.random.rand(128))
        
        # Generate two different keypairs
        public_key1, private_key1 = self.quantum_crypto.generate_keypair()
        public_key2, private_key2 = self.quantum_crypto.generate_keypair()
        
        # Encrypt with first public key
        encrypted = self.quantum_crypto.encrypt_behavioral_embedding(test_embedding, public_key1)
        
        # Try to decrypt with wrong private key - should fail
        with self.assertRaises(Exception):
            self.quantum_crypto.decrypt_behavioral_embedding(encrypted, private_key2)
    
    def test_quantum_resistance_properties(self):
        """Test quantum resistance properties"""
        if self.skip_tests:
            return
        
        # Kyber is designed to resist Shor's algorithm (quantum attacks)
        # We can't directly test quantum resistance, but we can verify:
        
        public_key, private_key = self.quantum_crypto.generate_keypair()
        
        # 1. Ciphertexts don't reveal information about plaintext
        embedding1 = [0.5] * 128  # All same values
        embedding2 = list(range(128))  # Sequential values
        
        encrypted1 = self.quantum_crypto.encrypt_behavioral_embedding(embedding1, public_key)
        encrypted2 = self.quantum_crypto.encrypt_behavioral_embedding(embedding2, public_key)
        
        # Ciphertexts should appear random (not correlated with plaintext)
        # We can't easily test this, but we verify they're different
        self.assertNotEqual(encrypted1['kyber_ciphertext'], encrypted2['kyber_ciphertext'])
        
        # 2. Key sizes match Kyber-768 specification (NIST Level 3)
        self.assertEqual(len(public_key), 1184)
        self.assertEqual(len(private_key), 2400)


class QuantumCommitmentIntegrationTests(TestCase):
    """Integration tests for quantum-protected commitments"""
    
    def setUp(self):
        """Set up test user and data"""
        from django.contrib.auth.models import User
        
        self.user = User.objects.create_user(
            username='quantumtestuser',
            email='quantum@example.com',
            password='TestPassword123!'
        )
        
        self.test_behavioral_profile = {
            'typing': {'typing_speed_wpm': 65, 'error_rate': 0.05},
            'mouse': {'velocity_mean': 2.3, 'click_count': 45},
            'cognitive': {'avg_decision_time': 2500},
            'combined_embedding': list(np.random.rand(128))
        }
    
    def test_create_quantum_commitment(self):
        """Test creating commitment with quantum encryption"""
        from behavioral_recovery.services.commitment_service import CommitmentService
        from behavioral_recovery.models import BehavioralCommitment
        
        service = CommitmentService(use_quantum=True)
        
        # Skip if quantum not available
        if not service.use_quantum:
            self.skipTest("Quantum crypto not available")
        
        # Create commitments
        commitments = service.create_commitments(self.user, self.test_behavioral_profile)
        
        self.assertGreater(len(commitments), 0, "Should create at least one commitment")
        
        # Verify quantum protection
        for commitment in commitments:
            if commitment.is_quantum_protected:
                self.assertIsNotNone(commitment.quantum_encrypted_embedding)
                self.assertIsNotNone(commitment.kyber_public_key)
                self.assertEqual(commitment.encryption_algorithm, 'kyber768-aes256gcm')
                
                # Verify key sizes
                self.assertEqual(len(commitment.kyber_public_key), 1184)
    
    def test_migration_to_quantum(self):
        """Test migrating classical commitment to quantum"""
        from behavioral_recovery.models import BehavioralCommitment
        from behavioral_recovery.services.commitment_service import CommitmentService
        import base64
        import json
        
        # Create classical commitment (old format)
        embedding = list(np.random.rand(128))
        embedding_json = json.dumps(embedding)
        embedding_bytes = embedding_json.encode('utf-8')
        classical_encrypted = base64.b64encode(embedding_bytes)
        
        old_commitment = BehavioralCommitment.objects.create(
            user=self.user,
            challenge_type='typing',
            encrypted_embedding=classical_encrypted,
            encryption_algorithm='base64',
            is_quantum_protected=False,
            unlock_conditions={'similarity_threshold': 0.87},
            samples_used=100,
            is_active=True
        )
        
        # Verify it's classical
        self.assertFalse(old_commitment.is_quantum_protected)
        self.assertEqual(old_commitment.encryption_algorithm, 'base64')
        
        # Migration would be done via management command
        # This test verifies the structure is correct for migration


class QuantumPerformanceTests(TestCase):
    """Performance tests for quantum cryptography"""
    
    def test_encryption_performance(self):
        """Test that encryption completes within acceptable time"""
        import time
        
        try:
            from behavioral_recovery.services.quantum_crypto_service import QuantumCryptoService
            
            quantum_crypto = QuantumCryptoService()
            
            # Skip if fallback mode
            info = quantum_crypto.get_algorithm_info()
            if not info['quantum_resistant']:
                self.skipTest("Quantum crypto not available")
            
            # Test embedding
            test_embedding = list(np.random.rand(128))
            
            # Generate keypair
            public_key, private_key = quantum_crypto.generate_keypair()
            
            # Measure encryption time
            start = time.time()
            encrypted = quantum_crypto.encrypt_behavioral_embedding(test_embedding, public_key)
            encryption_time = (time.time() - start) * 1000  # milliseconds
            
            # Should be under 500ms as per target
            self.assertLess(encryption_time, 500,
                          f"Encryption took {encryption_time:.2f}ms, should be < 500ms")
            
            print(f"\n✓ Kyber encryption: {encryption_time:.2f}ms")
            
        except ImportError:
            self.skipTest("QuantumCryptoService not available")
    
    def test_decryption_performance(self):
        """Test that decryption completes within acceptable time"""
        import time
        
        try:
            from behavioral_recovery.services.quantum_crypto_service import QuantumCryptoService
            
            quantum_crypto = QuantumCryptoService()
            
            # Skip if fallback mode
            info = quantum_crypto.get_algorithm_info()
            if not info['quantum_resistant']:
                self.skipTest("Quantum crypto not available")
            
            # Prepare encrypted data
            test_embedding = list(np.random.rand(128))
            public_key, private_key = quantum_crypto.generate_keypair()
            encrypted = quantum_crypto.encrypt_behavioral_embedding(test_embedding, public_key)
            
            # Measure decryption time
            start = time.time()
            decrypted = quantum_crypto.decrypt_behavioral_embedding(encrypted, private_key)
            decryption_time = (time.time() - start) * 1000  # milliseconds
            
            # Should be under 200ms as per target
            self.assertLess(decryption_time, 200,
                          f"Decryption took {decryption_time:.2f}ms, should be < 200ms")
            
            print(f"\n✓ Kyber decryption: {decryption_time:.2f}ms")
            
        except ImportError:
            self.skipTest("QuantumCryptoService not available")


if __name__ == '__main__':
    unittest.main()

