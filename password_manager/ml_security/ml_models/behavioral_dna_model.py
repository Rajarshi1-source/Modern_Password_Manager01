"""
Behavioral DNA Model (Server-Side Transformer)

Implements a Transformer-based neural network for encoding behavioral patterns
into 128-dimensional behavioral DNA embeddings.

This is the server-side implementation that can be used for:
- Model training on larger datasets
- Validation of client-side predictions
- Backup behavioral verification
"""

import numpy as np
import os
import logging
from typing import Dict, List, Tuple, Optional
import json

logger = logging.getLogger(__name__)

try:
    import tensorflow as tf
    from tensorflow import keras
    from tensorflow.keras import layers
    from tensorflow.keras.models import Model, load_model
    TENSORFLOW_AVAILABLE = True
except ImportError:
    logger.warning("TensorFlow not available for Behavioral DNA model")
    TENSORFLOW_AVAILABLE = False

try:
    import torch
    import torch.nn as nn
    from transformers import PreTrainedModel, PretrainedConfig
    TORCH_AVAILABLE = True
except ImportError:
    logger.warning("PyTorch/Transformers not available")
    TORCH_AVAILABLE = False


class BehavioralDNATransformer:
    """
    Transformer model for behavioral DNA encoding
    
    Architecture:
    - Input: 247 dimensions × 30 timesteps
    - Temporal embedding: 512 dimensions
    - 4 Transformer encoder layers (8-head attention)
    - Output projection: 512 → 256 → 128 dimensions
    """
    
    def __init__(self, config=None):
        self.config = config or {
            'input_dim': 247,
            'embedding_dim': 512,
            'num_heads': 8,
            'num_layers': 4,
            'ff_dim': 2048,
            'output_dim': 128,
            'sequence_length': 30,
            'dropout': 0.1
        }
        
        self.model = None
        self.tokenizer = None
        
        if TENSORFLOW_AVAILABLE:
            self._build_keras_model()
    
    def _build_keras_model(self):
        """
        Build Transformer model using Keras
        """
        logger.info("Building Keras Transformer model for behavioral DNA")
        
        # Input layer
        inputs = layers.Input(shape=(self.config['sequence_length'], self.config['input_dim']))
        
        # Temporal embedding
        x = layers.Dense(self.config['embedding_dim'], activation='relu', name='temporal_embedding')(inputs)
        
        # Positional encoding
        positions = tf.range(start=0, limit=self.config['sequence_length'], delta=1)
        position_embedding = layers.Embedding(
            input_dim=self.config['sequence_length'],
            output_dim=self.config['embedding_dim']
        )(positions)
        
        x = layers.Add()([x, position_embedding])
        
        # Transformer encoder layers
        for i in range(self.config['num_layers']):
            x = self._transformer_encoder_block(x, name=f'transformer_layer_{i}')
        
        # Global pooling
        x = layers.GlobalAveragePooling1D()(x)
        
        # Output projection
        x = layers.Dense(256, activation='relu', name='projection_256')(x)
        x = layers.Dropout(self.config['dropout'])(x)
        x = layers.Dense(self.config['output_dim'], activation='linear', name='behavioral_embedding')(x)
        
        # L2 normalization for cosine similarity
        outputs = layers.Lambda(lambda t: tf.math.l2_normalize(t, axis=-1))(x)
        
        # Create model
        self.model = Model(inputs=inputs, outputs=outputs, name='behavioral_dna_transformer')
        
        # Compile
        self.model.compile(
            optimizer=keras.optimizers.Adam(learning_rate=0.001),
            loss=self._contrastive_loss,
            metrics=['mae']
        )
        
        logger.info("Behavioral DNA Transformer model built successfully")
        logger.info(f"Total parameters: {self.model.count_params():,}")
    
    def _transformer_encoder_block(self, x, name):
        """
        Single transformer encoder block
        """
        # Multi-head attention
        attention_output = layers.MultiHeadAttention(
            num_heads=self.config['num_heads'],
            key_dim=self.config['embedding_dim'] // self.config['num_heads'],
            dropout=self.config['dropout'],
            name=f'{name}_mha'
        )(x, x)
        
        # Skip connection and layer norm
        x1 = layers.Add()([x, attention_output])
        x1 = layers.LayerNormalization(epsilon=1e-6, name=f'{name}_norm1')(x1)
        
        # Feed-forward network
        ff = layers.Dense(self.config['ff_dim'], activation='relu', name=f'{name}_ff1')(x1)
        ff = layers.Dropout(self.config['dropout'])(ff)
        ff = layers.Dense(self.config['embedding_dim'], name=f'{name}_ff2')(ff)
        
        # Skip connection and layer norm
        x2 = layers.Add()([x1, ff])
        x2 = layers.LayerNormalization(epsilon=1e-6, name=f'{name}_norm2')(x2)
        
        return x2
    
    def _contrastive_loss(self, y_true, y_pred):
        """
        Contrastive loss for behavioral similarity learning
        """
        # For self-supervised learning, we want embeddings of similar
        # behavioral patterns to be close in embedding space
        
        # Simplified: MSE loss for now
        # In production, use triplet loss or NT-Xent loss
        return tf.keras.losses.mean_squared_error(y_true, y_pred)
    
    def generate_embedding(self, behavioral_sequence):
        """
        Generate 128-dimensional behavioral DNA embedding
        
        Args:
            behavioral_sequence: numpy array of shape (sequence_length, input_dim)
        
        Returns:
            numpy array of shape (output_dim,) - behavioral DNA vector
        """
        if not TENSORFLOW_AVAILABLE or self.model is None:
            logger.warning("Model not available, using fallback")
            return self._fallback_embedding(behavioral_sequence)
        
        try:
            # Ensure correct shape
            if len(behavioral_sequence.shape) == 2:
                behavioral_sequence = np.expand_dims(behavioral_sequence, axis=0)
            
            # Generate embedding
            embedding = self.model.predict(behavioral_sequence, verbose=0)
            
            return embedding[0]  # Return first batch element
            
        except Exception as e:
            logger.error(f"Error generating embedding: {e}", exc_info=True)
            return self._fallback_embedding(behavioral_sequence)
    
    def _fallback_embedding(self, behavioral_sequence):
        """
        Fallback method when TensorFlow not available
        Uses PCA-like dimensionality reduction
        """
        logger.info("Using fallback embedding generation")
        
        # Flatten sequence
        if len(behavioral_sequence.shape) == 3:
            flat = behavioral_sequence[0].flatten()
        else:
            flat = behavioral_sequence.flatten()
        
        # Simple hash-based dimensionality reduction
        # In production, use actual PCA or autoencoder
        embedding = np.zeros(self.config['output_dim'])
        
        for i in range(min(len(flat), self.config['output_dim'])):
            embedding[i] = flat[i] if i < len(flat) else 0
        
        # Normalize
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm
        
        return embedding
    
    def train_model(self, X_train, y_train, X_val=None, y_val=None, epochs=10, batch_size=32):
        """
        Train the behavioral DNA model
        
        Args:
            X_train: Training sequences (n_samples, sequence_length, input_dim)
            y_train: Training labels/targets (n_samples, output_dim)
            X_val: Validation sequences (optional)
            y_val: Validation labels (optional)
            epochs: Number of training epochs
            batch_size: Batch size
        
        Returns:
            Training history
        """
        if not TENSORFLOW_AVAILABLE or self.model is None:
            raise ValueError("Model not available for training")
        
        logger.info(f"Training behavioral DNA model for {epochs} epochs")
        
        # Prepare validation data
        validation_data = None
        if X_val is not None and y_val is not None:
            validation_data = (X_val, y_val)
        
        # Train
        history = self.model.fit(
            X_train, y_train,
            validation_data=validation_data,
            epochs=epochs,
            batch_size=batch_size,
            callbacks=[
                keras.callbacks.EarlyStopping(patience=3, restore_best_weights=True),
                keras.callbacks.ReduceLROnPlateau(factor=0.5, patience=2)
            ],
            verbose=1
        )
        
        logger.info("Training completed")
        return history
    
    def save_model(self, filepath):
        """Save model to disk"""
        if self.model is None:
            raise ValueError("No model to save")
        
        self.model.save(filepath)
        logger.info(f"Model saved to {filepath}")
    
    def load_model(self, filepath):
        """Load model from disk"""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Model file not found: {filepath}")
        
        self.model = load_model(filepath, custom_objects={
            '_contrastive_loss': self._contrastive_loss
        })
        logger.info(f"Model loaded from {filepath}")
    
    def get_model_summary(self):
        """Get model summary"""
        if self.model:
            return self.model.summary()
        return None


class BehavioralDNAConfig:
    """Configuration for behavioral DNA model"""
    
    def __init__(self):
        self.input_dim = 247
        self.embedding_dim = 512
        self.num_heads = 8
        self.num_layers = 4
        self.ff_dim = 2048
        self.output_dim = 128
        self.sequence_length = 30
        self.dropout = 0.1
        self.similarity_threshold = 0.87


# Singleton instance
_global_model = None

def get_behavioral_dna_model():
    """Get or create global behavioral DNA model instance"""
    global _global_model
    
    if _global_model is None:
        _global_model = BehavioralDNATransformer()
    
    return _global_model

