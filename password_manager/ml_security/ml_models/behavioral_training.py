"""
Behavioral DNA Model Training

Training utilities for the behavioral DNA Transformer model
"""

import numpy as np
import logging
from typing import List, Dict, Tuple
import json
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

try:
    import tensorflow as tf
    TENSORFLOW_AVAILABLE = True
except ImportError:
    logger.warning("TensorFlow not available")
    TENSORFLOW_AVAILABLE = False


class BehavioralDataGenerator:
    """
    Generates training data from user behavioral samples
    """
    
    def __init__(self, input_dim=247, sequence_length=30):
        self.input_dim = input_dim
        self.sequence_length = sequence_length
    
    def prepare_training_data(self, behavioral_samples):
        """
        Prepare training data from behavioral samples
        
        Args:
            behavioral_samples: List of behavioral dictionaries
        
        Returns:
            (X, y) tuple of numpy arrays
        """
        logger.info(f"Preparing training data from {len(behavioral_samples)} samples")
        
        X = []
        y = []
        
        for sample in behavioral_samples:
            # Extract features
            features = self._extract_features(sample)
            
            # Pad to input_dim
            padded = self._pad_features(features, self.input_dim)
            
            # Create sequence (temporal dimension)
            sequence = self._create_sequence(padded)
            
            X.append(sequence)
            
            # For autoencoding task, y = x (self-supervised)
            # For temporal prediction, y would be next timestep
            y.append(padded)  # Use the embedding itself as target
        
        X = np.array(X)
        y = np.array(y)
        
        logger.info(f"Training data prepared: X shape = {X.shape}, y shape = {y.shape}")
        
        return X, y
    
    def _extract_features(self, behavioral_sample):
        """Extract numerical features from behavioral sample"""
        features = []
        
        def extract_recursive(obj):
            if isinstance(obj, (int, float)):
                features.append(float(obj))
            elif isinstance(obj, bool):
                features.append(1.0 if obj else 0.0)
            elif isinstance(obj, str):
                # Hash strings to numbers
                features.append(float(hash(obj) % 1000) / 1000.0)
            elif isinstance(obj, dict):
                for value in obj.values():
                    extract_recursive(value)
            elif isinstance(obj, (list, tuple)):
                for item in obj:
                    extract_recursive(item)
        
        # Extract from all behavioral modules
        if isinstance(behavioral_sample, dict):
            for key in ['typing', 'mouse', 'cognitive', 'device', 'semantic']:
                if key in behavioral_sample:
                    extract_recursive(behavioral_sample[key])
        
        return features
    
    def _pad_features(self, features, target_length):
        """Pad or truncate features to target length"""
        features = np.array(features)
        
        if len(features) < target_length:
            # Pad with zeros
            padded = np.zeros(target_length)
            padded[:len(features)] = features
            return padded
        else:
            # Truncate
            return features[:target_length]
    
    def _create_sequence(self, features):
        """
        Create temporal sequence from features
        
        For now, simply repeat the features to create sequence.
        In production, use actual temporal data from multiple time points.
        """
        sequence = np.tile(features, (self.sequence_length, 1))
        return sequence
    
    def augment_data(self, X, y, augmentation_factor=5):
        """
        Augment training data with noise and perturbations
        
        Args:
            X: Input sequences
            y: Target embeddings
            augmentation_factor: How many augmented samples per original
        
        Returns:
            Augmented (X, y) tuple
        """
        logger.info(f"Augmenting data with factor {augmentation_factor}")
        
        X_aug = [X]
        y_aug = [y]
        
        for i in range(augmentation_factor - 1):
            # Add small random noise (simulates natural variation)
            noise_scale = 0.05
            X_noisy = X + np.random.normal(0, noise_scale, X.shape)
            
            X_aug.append(X_noisy)
            y_aug.append(y)  # Targets remain the same
        
        X_augmented = np.concatenate(X_aug, axis=0)
        y_augmented = np.concatenate(y_aug, axis=0)
        
        logger.info(f"Data augmented: {X.shape} → {X_augmented.shape}")
        
        return X_augmented, y_augmented


class BehavioralModelTrainer:
    """
    Training orchestrator for behavioral DNA model
    """
    
    def __init__(self, model, config=None):
        self.model = model
        self.config = config or {}
        self.data_generator = BehavioralDataGenerator()
        self.training_history = []
    
    def train_from_samples(self, user_behavioral_samples, validation_split=0.2, epochs=20):
        """
        Train model from user behavioral samples
        
        Args:
            user_behavioral_samples: List of behavioral samples from users
            validation_split: Fraction of data for validation
            epochs: Number of training epochs
        
        Returns:
            Training history
        """
        logger.info(f"Training from {len(user_behavioral_samples)} behavioral samples")
        
        # Prepare training data
        X, y = self.data_generator.prepare_training_data(user_behavioral_samples)
        
        # Augment data
        X, y = self.data_generator.augment_data(X, y, augmentation_factor=3)
        
        # Split train/validation
        split_idx = int(len(X) * (1 - validation_split))
        X_train, X_val = X[:split_idx], X[split_idx:]
        y_train, y_val = y[:split_idx], y[split_idx:]
        
        logger.info(f"Training set: {len(X_train)}, Validation set: {len(X_val)}")
        
        # Train model
        history = self.model.train_model(
            X_train, y_train,
            X_val, y_val,
            epochs=epochs,
            batch_size=32
        )
        
        # Store history
        self.training_history.append({
            'timestamp': datetime.now().isoformat(),
            'samples': len(user_behavioral_samples),
            'epochs': epochs,
            'final_loss': history.history['loss'][-1],
            'final_val_loss': history.history.get('val_loss', [None])[-1]
        })
        
        return history
    
    def continuous_learning(self, new_samples):
        """
        Continuously update model with new behavioral samples
        
        Args:
            new_samples: New behavioral samples to learn from
        """
        logger.info(f"Continuous learning with {len(new_samples)} new samples")
        
        # Fine-tune model with new data
        X, y = self.data_generator.prepare_training_data(new_samples)
        
        # Train for fewer epochs (fine-tuning)
        history = self.model.train_model(
            X, y,
            epochs=3,
            batch_size=16
        )
        
        return history
    
    def evaluate_model(self, test_samples):
        """
        Evaluate model on test samples
        
        Args:
            test_samples: List of behavioral samples for testing
        
        Returns:
            Evaluation metrics
        """
        logger.info(f"Evaluating model on {len(test_samples)} test samples")
        
        X_test, y_test = self.data_generator.prepare_training_data(test_samples)
        
        if TENSORFLOW_AVAILABLE and self.model.model:
            loss, mae = self.model.model.evaluate(X_test, y_test, verbose=0)
            
            return {
                'loss': float(loss),
                'mae': float(mae),
                'test_samples': len(test_samples)
            }
        
        return {'error': 'Model not available'}

