"""
Password Strength Predictor using LSTM/RNN

This module implements an LSTM-based neural network for predicting password strength.
It analyzes character sequences and patterns to evaluate password security.

Performance Optimizations:
- TensorFlow configured for inference mode (reduced memory, faster predictions)
- Model predictions use verbose=0 to avoid logging overhead
- Thread count optimized for CPU inference
"""

import numpy as np
import os
import logging
from typing import Dict, Tuple
import math
import re
from collections import Counter

logger = logging.getLogger(__name__)

# Try to import TensorFlow/Keras, fall back to rule-based if not available
try:
    import tensorflow as tf
    
    # Optimize TensorFlow for inference (reduces startup time and memory)
    # Set before importing keras components
    os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'  # Suppress TF info/warning logs
    
    # Configure TensorFlow for inference optimization
    tf.get_logger().setLevel('ERROR')  # Reduce TF logging verbosity
    
    # Limit GPU memory growth if GPU is available
    gpus = tf.config.experimental.list_physical_devices('GPU')
    if gpus:
        for gpu in gpus:
            tf.config.experimental.set_memory_growth(gpu, True)
    
    # Optimize CPU threading for inference
    tf.config.threading.set_intra_op_parallelism_threads(2)
    tf.config.threading.set_inter_op_parallelism_threads(2)
    
    from tensorflow import keras
    from tensorflow.keras.models import Sequential, load_model
    from tensorflow.keras.layers import LSTM, Dense, Embedding, Dropout, Bidirectional
    from tensorflow.keras.preprocessing.sequence import pad_sequences
    TENSORFLOW_AVAILABLE = True
    logger.info("TensorFlow configured for optimized inference")
except ImportError:
    logger.warning("TensorFlow not available. Using rule-based password strength prediction.")
    TENSORFLOW_AVAILABLE = False


class PasswordStrengthPredictor:
    """
    LSTM-based password strength predictor
    
    Architecture:
    - Embedding layer for character encoding
    - Bidirectional LSTM layers for sequence analysis
    - Dense layers for classification
    - Output: 5 classes (very_weak, weak, moderate, strong, very_strong)
    """
    
    def __init__(self, model_path=None):
        self.model_path = model_path or os.path.join(
            os.path.dirname(__file__), 
            '..', 
            'trained_models', 
            'password_strength_lstm.h5'
        )
        
        # Character vocabulary (printable ASCII characters)
        self.vocab_size = 95  # Printable ASCII
        self.max_length = 50
        self.char_to_idx = {chr(i): i - 32 for i in range(32, 127)}
        self.idx_to_char = {v: k for k, v in self.char_to_idx.items()}
        
        # Strength classes
        self.strength_classes = ['very_weak', 'weak', 'moderate', 'strong', 'very_strong']
        
        self.model = None
        if TENSORFLOW_AVAILABLE:
            try:
                if os.path.exists(self.model_path):
                    self.model = load_model(self.model_path)
                    logger.info(f"Loaded password strength model from {self.model_path}")
                else:
                    logger.info("Creating new LSTM model for password strength")
                    self.model = self._build_model()
            except Exception as e:
                logger.error(f"Error loading password strength model: {e}")
                self.model = None
    
    def _build_model(self):
        """Build the LSTM model architecture"""
        if not TENSORFLOW_AVAILABLE:
            return None
        
        model = Sequential([
            # Embedding layer
            Embedding(input_dim=self.vocab_size + 1, output_dim=64, 
                     input_length=self.max_length),
            
            # Bidirectional LSTM layers
            Bidirectional(LSTM(128, return_sequences=True)),
            Dropout(0.3),
            Bidirectional(LSTM(64)),
            Dropout(0.3),
            
            # Dense layers
            Dense(64, activation='relu'),
            Dropout(0.2),
            Dense(32, activation='relu'),
            
            # Output layer (5 classes)
            Dense(5, activation='softmax')
        ])
        
        model.compile(
            optimizer='adam',
            loss='categorical_crossentropy',
            metrics=['accuracy', 'categorical_crossentropy']
        )
        
        return model
    
    def _encode_password(self, password: str) -> np.ndarray:
        """
        Encode password into numerical sequence
        
        Args:
            password: Password string
        
        Returns:
            Encoded sequence array
        """
        encoded = []
        for char in password[:self.max_length]:
            if char in self.char_to_idx:
                encoded.append(self.char_to_idx[char])
            else:
                encoded.append(0)  # Unknown character
        
        # Pad sequence
        if len(encoded) < self.max_length:
            encoded.extend([0] * (self.max_length - len(encoded)))
        
        return np.array(encoded).reshape(1, -1)
    
    def _calculate_entropy(self, password: str) -> float:
        """
        Calculate Shannon entropy of password
        
        Args:
            password: Password string
        
        Returns:
            Entropy value
        """
        if not password:
            return 0.0
        
        # Count character frequencies
        counter = Counter(password)
        length = len(password)
        
        # Calculate entropy
        entropy = 0.0
        for count in counter.values():
            probability = count / length
            if probability > 0:
                entropy -= probability * math.log2(probability)
        
        # Normalize by password length for better comparison
        return entropy * length
    
    def _calculate_character_diversity(self, password: str) -> float:
        """
        Calculate character diversity score
        
        Args:
            password: Password string
        
        Returns:
            Diversity score (0-1)
        """
        if not password:
            return 0.0
        
        unique_chars = len(set(password))
        return unique_chars / len(password)
    
    def _check_common_patterns(self, password: str) -> bool:
        """
        Check for common password patterns
        
        Args:
            password: Password string
        
        Returns:
            True if common patterns found
        """
        common_patterns = [
            r'12345',
            r'qwerty',
            r'password',
            r'admin',
            r'letmein',
            r'welcome',
            r'monkey',
            r'dragon',
            r'master',
            r'abc123',
            r'(\w)\1{2,}',  # Repeated characters
            r'(?:012|123|234|345|456|567|678|789)',  # Sequential numbers
            r'(?:abc|bcd|cde|def|efg|fgh|ghi|hij)',  # Sequential letters
        ]
        
        password_lower = password.lower()
        for pattern in common_patterns:
            if re.search(pattern, password_lower):
                return True
        
        return False
    
    def _calculate_guessability_score(self, password: str, features: Dict) -> float:
        """
        Calculate password guessability score
        
        Args:
            password: Password string
            features: Extracted features dict
        
        Returns:
            Guessability score (0-100, lower is better)
        """
        score = 100.0  # Start with maximum guessability (worst)
        
        # Length factor
        length = features['length']
        if length >= 16:
            score -= 40
        elif length >= 12:
            score -= 30
        elif length >= 8:
            score -= 20
        else:
            score -= 10
        
        # Character diversity
        if features['has_uppercase']:
            score -= 10
        if features['has_lowercase']:
            score -= 10
        if features['has_numbers']:
            score -= 10
        if features['has_special']:
            score -= 15
        
        # Entropy bonus
        if features['entropy'] > 80:
            score -= 15
        elif features['entropy'] > 60:
            score -= 10
        elif features['entropy'] > 40:
            score -= 5
        
        # Common patterns penalty
        if features['contains_common_patterns']:
            score += 30
        
        return max(0, min(100, score))
    
    def extract_features(self, password: str) -> Dict:
        """
        Extract features from password for analysis
        
        Args:
            password: Password string
        
        Returns:
            Dictionary of features
        """
        features = {
            'length': len(password),
            'has_uppercase': bool(re.search(r'[A-Z]', password)),
            'has_lowercase': bool(re.search(r'[a-z]', password)),
            'has_numbers': bool(re.search(r'\d', password)),
            'has_special': bool(re.search(r'[^A-Za-z0-9]', password)),
            'entropy': self._calculate_entropy(password),
            'character_diversity': self._calculate_character_diversity(password),
            'contains_common_patterns': self._check_common_patterns(password),
        }
        
        features['guessability_score'] = self._calculate_guessability_score(password, features)
        
        return features
    
    def _rule_based_prediction(self, password: str, features: Dict) -> Tuple[str, float]:
        """
        Fallback rule-based prediction when LSTM is not available
        
        Args:
            password: Password string
            features: Extracted features
        
        Returns:
            (strength_class, confidence)
        """
        score = 0
        
        # Length scoring
        length = features['length']
        if length >= 16:
            score += 30
        elif length >= 12:
            score += 25
        elif length >= 8:
            score += 15
        else:
            score += 5
        
        # Character type scoring
        char_types = sum([
            features['has_uppercase'],
            features['has_lowercase'],
            features['has_numbers'],
            features['has_special']
        ])
        score += char_types * 10
        
        # Entropy scoring
        entropy = features['entropy']
        if entropy > 80:
            score += 20
        elif entropy > 60:
            score += 15
        elif entropy > 40:
            score += 10
        
        # Diversity scoring
        diversity = features['character_diversity']
        score += diversity * 10
        
        # Penalty for common patterns
        if features['contains_common_patterns']:
            score -= 25
        
        # Determine strength class
        if score >= 80:
            strength = 'very_strong'
            confidence = 0.9
        elif score >= 60:
            strength = 'strong'
            confidence = 0.85
        elif score >= 40:
            strength = 'moderate'
            confidence = 0.8
        elif score >= 20:
            strength = 'weak'
            confidence = 0.75
        else:
            strength = 'very_weak'
            confidence = 0.7
        
        return strength, confidence
    
    def predict(self, password: str) -> Dict:
        """
        Predict password strength
        
        Args:
            password: Password to analyze
        
        Returns:
            Dictionary with prediction results:
            {
                'strength': str,  # very_weak, weak, moderate, strong, very_strong
                'confidence': float,  # Model confidence (0-1)
                'features': dict,  # Extracted features
                'recommendations': list  # Improvement recommendations
            }
        """
        if not password:
            return {
                'strength': 'very_weak',
                'confidence': 1.0,
                'features': {},
                'recommendations': ['Password cannot be empty']
            }
        
        # Extract features
        features = self.extract_features(password)
        
        # Make prediction
        if self.model is not None and TENSORFLOW_AVAILABLE:
            try:
                # LSTM prediction
                encoded = self._encode_password(password)
                predictions = self.model.predict(encoded, verbose=0)[0]
                
                # Get predicted class and confidence
                predicted_idx = np.argmax(predictions)
                strength = self.strength_classes[predicted_idx]
                confidence = float(predictions[predicted_idx])
            except Exception as e:
                logger.error(f"Error in LSTM prediction: {e}")
                # Fallback to rule-based
                strength, confidence = self._rule_based_prediction(password, features)
        else:
            # Use rule-based prediction
            strength, confidence = self._rule_based_prediction(password, features)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(password, features, strength)
        
        return {
            'strength': strength,
            'confidence': confidence,
            'features': features,
            'recommendations': recommendations
        }
    
    def _generate_recommendations(self, password: str, features: Dict, strength: str) -> list:
        """
        Generate password improvement recommendations
        
        Args:
            password: Password string
            features: Extracted features
            strength: Predicted strength
        
        Returns:
            List of recommendations
        """
        recommendations = []
        
        if strength in ['very_weak', 'weak']:
            if features['length'] < 12:
                recommendations.append("Increase password length to at least 12 characters")
            
            if not features['has_uppercase']:
                recommendations.append("Add uppercase letters")
            
            if not features['has_lowercase']:
                recommendations.append("Add lowercase letters")
            
            if not features['has_numbers']:
                recommendations.append("Add numbers")
            
            if not features['has_special']:
                recommendations.append("Add special characters (!@#$%^&*)")
            
            if features['contains_common_patterns']:
                recommendations.append("Avoid common patterns and dictionary words")
            
            if features['character_diversity'] < 0.5:
                recommendations.append("Use more diverse characters")
        
        elif strength == 'moderate':
            if features['length'] < 14:
                recommendations.append("Consider increasing length for better security")
            
            if not features['has_special']:
                recommendations.append("Adding special characters would improve strength")
            
            if features['contains_common_patterns']:
                recommendations.append("Avoid common patterns for better security")
        
        else:  # strong or very_strong
            if features['length'] < 16:
                recommendations.append("Consider using a passphrase for even better security")
            
            recommendations.append("Excellent password! Ensure you're using unique passwords for each account")
        
        return recommendations
    
    def train(self, training_data, labels, epochs=50, batch_size=32):
        """
        Train the LSTM model
        
        Args:
            training_data: List of passwords
            labels: List of strength labels (one-hot encoded)
            epochs: Number of training epochs
            batch_size: Batch size for training
        """
        if not TENSORFLOW_AVAILABLE or self.model is None:
            logger.error("Cannot train: TensorFlow not available or model not initialized")
            return
        
        # Encode passwords
        X = np.array([self._encode_password(pwd)[0] for pwd in training_data])
        y = np.array(labels)
        
        # Train model
        history = self.model.fit(
            X, y,
            epochs=epochs,
            batch_size=batch_size,
            validation_split=0.2,
            verbose=1
        )
        
        # Save model
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        self.model.save(self.model_path)
        logger.info(f"Model saved to {self.model_path}")
        
        return history

