"""
Shamir's Secret Sharing Tests
==============================

Unit tests for the Shamir secret sharing implementation.

@author Password Manager Team
@created 2026-01-22
"""

from django.test import TestCase
from ..services.shamir_service import ShamirSecretSharingService, Share


class ShamirSecretSharingTests(TestCase):
    """Tests for Shamir's Secret Sharing."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.service = ShamirSecretSharingService()
    
    def test_split_and_reconstruct_basic(self):
        """Test basic split and reconstruct."""
        secret = b"my secret password"
        result = self.service.split_secret(secret, k=3, n=5)
        
        self.assertEqual(len(result.shares), 5)
        self.assertIsNotNone(result.original_hash)
        
        # Reconstruct with exactly k shares
        reconstructed = self.service.reconstruct_secret(
            result.shares[:3],
            expected_hash=result.original_hash
        )
        self.assertEqual(reconstructed, secret)
    
    def test_reconstruct_with_more_than_k_shares(self):
        """Test reconstruction with more than k shares."""
        secret = b"hello world"
        result = self.service.split_secret(secret, k=2, n=5)
        
        # Use 4 shares (more than k=2)
        reconstructed = self.service.reconstruct_secret(
            result.shares[:4],
            expected_hash=result.original_hash
        )
        self.assertEqual(reconstructed, secret)
    
    def test_reconstruct_with_any_k_shares(self):
        """Test reconstruction with any k shares."""
        secret = b"test secret"
        result = self.service.split_secret(secret, k=3, n=5)
        
        # Use shares 0, 2, 4 (not consecutive)
        selected = [result.shares[0], result.shares[2], result.shares[4]]
        reconstructed = self.service.reconstruct_secret(
            selected,
            expected_hash=result.original_hash
        )
        self.assertEqual(reconstructed, secret)
    
    def test_insufficient_shares_fails(self):
        """Test that k-1 shares can't reconstruct."""
        secret = b"confidential"
        result = self.service.split_secret(secret, k=3, n=5)
        
        # Try with only 2 shares (less than k=3)
        # This shouldn't raise an error, but the result will be wrong
        reconstructed = self.service.reconstruct_secret(result.shares[:2])
        self.assertNotEqual(reconstructed, secret)
    
    def test_empty_secret_raises(self):
        """Test that empty secret raises ValueError."""
        with self.assertRaises(ValueError):
            self.service.split_secret(b"", k=3, n=5)
    
    def test_k_greater_than_n_raises(self):
        """Test that k > n raises ValueError."""
        with self.assertRaises(ValueError):
            self.service.split_secret(b"secret", k=5, n=3)
    
    def test_k_less_than_2_raises(self):
        """Test that k < 2 raises ValueError."""
        with self.assertRaises(ValueError):
            self.service.split_secret(b"secret", k=1, n=5)
    
    def test_hash_verification(self):
        """Test hash verification on reconstruction."""
        secret = b"verify me"
        result = self.service.split_secret(secret, k=2, n=3)
        
        # Should succeed with correct hash
        reconstructed = self.service.reconstruct_secret(
            result.shares,
            expected_hash=result.original_hash
        )
        self.assertEqual(reconstructed, secret)
        
        # Should fail with wrong hash
        with self.assertRaises(ValueError):
            self.service.reconstruct_secret(
                result.shares,
                expected_hash="wronghash"
            )
    
    def test_feldman_commitment_verification(self):
        """Test Feldman VSS commitment verification."""
        secret = b"verify shares"
        result = self.service.split_secret(secret, k=3, n=5, with_commitments=True)
        
        self.assertEqual(len(result.commitments), 3)  # k commitments
        
        # Verify each share
        for share in result.shares:
            is_valid = self.service.verify_share(share, result.commitments, k=3)
            self.assertTrue(is_valid)
    
    def test_large_secret(self):
        """Test with larger secret."""
        secret = b"x" * 1000  # 1KB secret
        result = self.service.split_secret(secret, k=3, n=5)
        
        reconstructed = self.service.reconstruct_secret(
            result.shares[:3],
            expected_hash=result.original_hash
        )
        self.assertEqual(reconstructed, secret)
    
    def test_share_refresh(self):
        """Test proactive share refresh."""
        secret = b"refresh me"
        result = self.service.split_secret(secret, k=3, n=5)
        
        # Refresh shares
        new_shares = self.service.generate_refresh_shares(result.shares, k=3, n=5)
        
        self.assertEqual(len(new_shares), 5)
        
        # Old shares should now be invalid (different values)
        for old, new in zip(result.shares, new_shares):
            self.assertNotEqual(old.value, new.value)
        
        # But new shares should still reconstruct correctly
        reconstructed = self.service.reconstruct_secret(
            new_shares[:3],
            expected_hash=result.original_hash
        )
        self.assertEqual(reconstructed, secret)
    
    def test_different_thresholds(self):
        """Test various threshold configurations."""
        secret = b"threshold test"
        
        configs = [(2, 3), (3, 5), (4, 7), (5, 10)]
        
        for k, n in configs:
            result = self.service.split_secret(secret, k=k, n=n)
            self.assertEqual(len(result.shares), n)
            
            # Reconstruct with exactly k shares
            reconstructed = self.service.reconstruct_secret(
                result.shares[:k],
                expected_hash=result.original_hash
            )
            self.assertEqual(reconstructed, secret)
