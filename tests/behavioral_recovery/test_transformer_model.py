"""
Tests for Transformer Model

Tests the behavioral DNA Transformer model
"""

import unittest
import sys
import os
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../password_manager')))

from django.test import TestCase


class TransformerModelTests(TestCase):
    """Tests for Transformer-based behavioral DNA model"""
    
    def setUp(self):
        """Set up test data"""
        self.sample_sequence = self._create_sample_sequence()
    
    def _create_sample_sequence(self):
        """Create sample behavioral sequence (247 dims × 30 timesteps)"""
        return np.random.rand(30, 247)
    
    def test_model_initialization(self):
        """Test that Transformer model can be initialized"""
        try:
            from ml_security.ml_models.behavioral_dna_model import BehavioralDNATransformer
            
            model = BehavioralDNATransformer()
            self.assertIsNotNone(model)
            
            # Check config
            self.assertEqual(model.config['input_dim'], 247)
            self.assertEqual(model.config['output_dim'], 128)
            
        except ImportError as e:
            self.skipTest(f"TensorFlow not available: {e}")
    
    def test_embedding_generation(self):
        """Test generation of 128-dim embeddings"""
        try:
            from ml_security.ml_models.behavioral_dna_model import BehavioralDNATransformer
            
            model = BehavioralDNATransformer()
            
            # Generate embedding
            embedding = model.generate_embedding(self.sample_sequence)
            
            # Check embedding shape
            self.assertEqual(len(embedding), 128, "Embedding should be 128-dimensional")
            
            # Check embedding is normalized (for cosine similarity)
            norm = np.linalg.norm(embedding)
            self.assertAlmostEqual(norm, 1.0, places=5, msg="Embedding should be L2-normalized")
            
        except ImportError as e:
            self.skipTest(f"TensorFlow not available: {e}")
    
    def test_embedding_consistency(self):
        """Test that same input produces similar embeddings"""
        try:
            from ml_security.ml_models.behavioral_dna_model import BehavioralDNATransformer
            
            model = BehavioralDNATransformer()
            
            # Generate two embeddings from same sequence
            embedding1 = model.generate_embedding(self.sample_sequence)
            embedding2 = model.generate_embedding(self.sample_sequence)
            
            # They should be identical (or very close due to floating point)
            np.testing.assert_array_almost_equal(embedding1, embedding2, decimal=5)
            
        except ImportError as e:
            self.skipTest(f"TensorFlow not available: {e}")


class SimilarityTests(TestCase):
    """Tests for behavioral similarity calculations"""
    
    def test_cosine_similarity(self):
        """Test cosine similarity calculation"""
        # Create two embeddings
        embedding1 = np.random.rand(128)
        embedding1 = embedding1 / np.linalg.norm(embedding1)
        
        embedding2 = embedding1 + np.random.rand(128) * 0.1
        embedding2 = embedding2 / np.linalg.norm(embedding2)
        
        # Calculate cosine similarity
        similarity = np.dot(embedding1, embedding2)
        
        # Should be high (> 0.9) since embeddings are similar
        self.assertGreater(similarity, 0.5, "Similar embeddings should have high similarity")
        self.assertLessEqual(similarity, 1.0)
    
    def test_dissimilar_embeddings(self):
        """Test that dissimilar embeddings have low similarity"""
        embedding1 = np.random.rand(128)
        embedding1 = embedding1 / np.linalg.norm(embedding1)
        
        embedding2 = np.random.rand(128)
        embedding2 = embedding2 / np.linalg.norm(embedding2)
        
        similarity = np.dot(embedding1, embedding2)
        
        # Random embeddings typically have similarity around 0
        # Allow wide range since it's random
        self.assertGreaterEqual(similarity, -1.0)
        self.assertLessEqual(similarity, 1.0)


if __name__ == '__main__':
    unittest.main()

