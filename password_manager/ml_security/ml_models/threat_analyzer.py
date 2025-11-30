"""
Hybrid CNN-LSTM Threat Analyzer

This module implements a hybrid deep learning model combining:
- CNN layers for spatial feature extraction
- LSTM layers for temporal sequence analysis
- Dense layers for threat classification

This model provides continuous authentication and real-time threat detection.
"""

import numpy as np
import os
import logging
from typing import Dict, List, Tuple
from datetime import datetime, timedelta
from collections import deque

logger = logging.getLogger(__name__)

try:
    import tensorflow as tf
    from tensorflow import keras
    from tensorflow.keras.models import Model, load_model
    from tensorflow.keras.layers import (
        Input, Conv1D, MaxPooling1D, LSTM, Dense,
        Dropout, Flatten, Concatenate, BatchNormalization,
        Bidirectional, GlobalAveragePooling1D
    )
    TENSORFLOW_AVAILABLE = True
except ImportError:
    logger.warning("TensorFlow not available. Threat analyzer will use rule-based methods.")
    TENSORFLOW_AVAILABLE = False


class ThreatAnalyzer:
    """
    Hybrid CNN-LSTM model for real-time threat detection
    
    Architecture:
    Input:
    - Spatial features (device, network, session metadata) → CNN
    - Temporal features (behavior sequence over time) → LSTM
    
    CNN Branch:
    - 1D Convolutional layers to extract patterns from spatial features
    - MaxPooling for dimensionality reduction
    
    LSTM Branch:
    - Bidirectional LSTM for temporal sequence analysis
    - Captures long-term behavioral patterns
    
    Fusion:
    - Concatenate CNN and LSTM outputs
    - Dense layers for final classification
    
    Output:
    - Multi-class threat classification
    - Risk score (0-100)
    - Recommended action
    """
    
    def __init__(self, model_path=None):
        self.model_path = model_path or os.path.join(
            os.path.dirname(__file__),
            '..',
            'trained_models',
            'threat_analyzer_cnn_lstm.h5'
        )
        
        # Model parameters
        self.spatial_features_dim = 20  # Number of spatial features
        self.temporal_sequence_length = 50  # Time steps to analyze
        self.temporal_features_dim = 15  # Number of features per time step
        
        # Threat classes
        self.threat_classes = [
            'benign',
            'brute_force',
            'credential_stuffing',
            'account_takeover',
            'bot_activity',
            'data_exfiltration',
            'suspicious_pattern'
        ]
        
        # Behavioral sequence buffer (for temporal analysis)
        self.behavior_sequences = {}  # user_id -> deque of behavior vectors
        
        self.model = None
        if TENSORFLOW_AVAILABLE:
            try:
                if os.path.exists(self.model_path):
                    self.model = load_model(self.model_path)
                    logger.info(f"Loaded threat analyzer model from {self.model_path}")
                else:
                    logger.info("Creating new CNN-LSTM model for threat analysis")
                    self.model = self._build_model()
            except Exception as e:
                logger.error(f"Error loading threat analyzer model: {e}")
                self.model = None
    
    def _build_model(self):
        """
        Build the hybrid CNN-LSTM architecture
        """
        if not TENSORFLOW_AVAILABLE:
            return None
        
        # ==== Spatial Features Branch (CNN) ====
        spatial_input = Input(shape=(self.spatial_features_dim,), name='spatial_input')
        
        # Reshape for Conv1D (add channel dimension) - Use Keras layer instead of TensorFlow function
        from tensorflow.keras.layers import Reshape
        spatial_reshaped = Reshape((self.spatial_features_dim, 1))(spatial_input)
        
        # CNN layers for spatial pattern extraction
        conv1 = Conv1D(filters=64, kernel_size=3, activation='relu', padding='same')(spatial_reshaped)
        conv1 = BatchNormalization()(conv1)
        pool1 = MaxPooling1D(pool_size=2)(conv1)
        
        conv2 = Conv1D(filters=128, kernel_size=3, activation='relu', padding='same')(pool1)
        conv2 = BatchNormalization()(conv2)
        pool2 = MaxPooling1D(pool_size=2)(conv2)
        
        conv3 = Conv1D(filters=256, kernel_size=3, activation='relu', padding='same')(pool2)
        conv3 = BatchNormalization()(conv3)
        
        # Global average pooling to get fixed-size vector
        spatial_features = GlobalAveragePooling1D()(conv3)
        spatial_features = Dropout(0.3)(spatial_features)
        
        # ==== Temporal Features Branch (LSTM) ====
        temporal_input = Input(
            shape=(self.temporal_sequence_length, self.temporal_features_dim),
            name='temporal_input'
        )
        
        # Bidirectional LSTM layers for temporal pattern analysis
        lstm1 = Bidirectional(LSTM(128, return_sequences=True))(temporal_input)
        lstm1 = Dropout(0.3)(lstm1)
        
        lstm2 = Bidirectional(LSTM(64, return_sequences=True))(lstm1)
        lstm2 = Dropout(0.3)(lstm2)
        
        lstm3 = Bidirectional(LSTM(32))(lstm2)
        temporal_features = Dropout(0.3)(lstm3)
        
        # ==== Fusion Layer ====
        # Concatenate spatial and temporal features
        merged = Concatenate()([spatial_features, temporal_features])
        
        # Dense layers for classification
        dense1 = Dense(256, activation='relu')(merged)
        dense1 = BatchNormalization()(dense1)
        dense1 = Dropout(0.4)(dense1)
        
        dense2 = Dense(128, activation='relu')(dense1)
        dense2 = BatchNormalization()(dense2)
        dense2 = Dropout(0.3)(dense2)
        
        dense3 = Dense(64, activation='relu')(dense2)
        dense3 = Dropout(0.2)(dense3)
        
        # Output layer (multi-class classification)
        output = Dense(len(self.threat_classes), activation='softmax', name='output')(dense3)
        
        # Build model
        model = Model(inputs=[spatial_input, temporal_input], outputs=output)
        
        # Compile model
        model.compile(
            optimizer=keras.optimizers.Adam(learning_rate=0.001),
            loss='categorical_crossentropy',
            metrics=['accuracy', 'categorical_crossentropy', keras.metrics.AUC()]
        )
        
        return model
    
    def extract_spatial_features(self, session_data: Dict) -> np.ndarray:
        """
        Extract spatial features from session data
        
        Args:
            session_data: Current session information
        
        Returns:
            Spatial feature array
        """
        features = np.zeros(self.spatial_features_dim)
        
        # Device features (0-4)
        features[0] = session_data.get('device_trust_score', 0.5)
        features[1] = session_data.get('device_age_days', 0) / 365.0  # Normalized
        features[2] = 1.0 if session_data.get('device_known', False) else 0.0
        features[3] = session_data.get('device_fingerprint_similarity', 0.5)
        features[4] = session_data.get('os_trust_score', 0.5)
        
        # Network features (5-9)
        features[5] = session_data.get('ip_trust_score', 0.5)
        features[6] = session_data.get('ip_reputation', 0.5)
        features[7] = 1.0 if session_data.get('vpn_detected', False) else 0.0
        features[8] = 1.0 if session_data.get('tor_detected', False) else 0.0
        features[9] = session_data.get('ip_consistency', 0.5)
        
        # Location features (10-12)
        features[10] = session_data.get('location_distance_km', 0) / 10000.0  # Normalized
        features[11] = session_data.get('location_consistency', 0.5)
        features[12] = session_data.get('timezone_consistency', 1.0)
        
        # Temporal features (13-15)
        hour = datetime.now().hour
        features[13] = np.sin(2 * np.pi * hour / 24)  # Cyclical encoding
        features[14] = np.cos(2 * np.pi * hour / 24)
        features[15] = session_data.get('time_consistency_score', 0.5)
        
        # Session features (16-19)
        features[16] = min(session_data.get('failed_attempts', 0) / 10.0, 1.0)
        features[17] = session_data.get('session_duration', 0) / 3600.0  # Hours
        features[18] = min(session_data.get('api_request_rate', 0) / 100.0, 1.0)
        features[19] = session_data.get('suspicious_actions_count', 0) / 10.0
        
        return features
    
    def extract_temporal_features(self, user_id: str, current_behavior: Dict) -> np.ndarray:
        """
        Extract temporal sequence features
        
        Args:
            user_id: User identifier
            current_behavior: Current behavior vector
        
        Returns:
            Temporal feature sequence array
        """
        # Initialize sequence buffer for user if not exists
        if user_id not in self.behavior_sequences:
            self.behavior_sequences[user_id] = deque(maxlen=self.temporal_sequence_length)
        
        # Create behavior vector from current behavior
        behavior_vector = np.array([
            current_behavior.get('typing_speed', 0) / 100.0,
            current_behavior.get('mouse_speed', 0) / 100.0,
            current_behavior.get('click_frequency', 0) / 10.0,
            current_behavior.get('vault_access_count', 0) / 10.0,
            current_behavior.get('password_view_count', 0) / 10.0,
            current_behavior.get('password_copy_count', 0) / 10.0,
            current_behavior.get('page_navigation_speed', 0) / 10.0,
            current_behavior.get('idle_time', 0) / 300.0,  # Max 5 minutes
            current_behavior.get('error_rate', 0),
            current_behavior.get('api_error_rate', 0),
            1.0 if current_behavior.get('suspicious_clipboard_activity', False) else 0.0,
            1.0 if current_behavior.get('rapid_data_access', False) else 0.0,
            current_behavior.get('session_anomaly_score', 0),
            current_behavior.get('behavior_deviation_score', 0),
            datetime.now().timestamp() / 1e9,  # Normalized timestamp
        ])
        
        # Add to sequence buffer
        self.behavior_sequences[user_id].append(behavior_vector)
        
        # Convert deque to numpy array
        sequence = np.array(list(self.behavior_sequences[user_id]))
        
        # Pad sequence if not enough history
        if len(sequence) < self.temporal_sequence_length:
            padding = np.zeros((
                self.temporal_sequence_length - len(sequence),
                self.temporal_features_dim
            ))
            sequence = np.vstack([padding, sequence])
        
        return sequence
    
    def analyze_threat(self, session_data: Dict, user_id: str, behavior_data: Dict) -> Dict:
        """
        Analyze session for threats using hybrid CNN-LSTM model
        
        Args:
            session_data: Current session information
            user_id: User identifier
            behavior_data: Current behavior data
        
        Returns:
            Threat analysis results
        """
        # Extract features
        spatial_features = self.extract_spatial_features(session_data)
        temporal_features = self.extract_temporal_features(user_id, behavior_data)
        
        # Initialize result
        result = {
            'threat_detected': False,
            'threat_type': 'benign',
            'threat_score': 0.0,
            'confidence': 0.0,
            'risk_level': 0,
            'recommended_action': 'allow',
            'spatial_analysis': {},
            'temporal_analysis': {},
            'reasoning': []
        }
        
        if self.model is not None and TENSORFLOW_AVAILABLE:
            try:
                # Prepare inputs
                spatial_input = spatial_features.reshape(1, -1)
                temporal_input = temporal_features.reshape(1, self.temporal_sequence_length, -1)
                
                # Make prediction
                predictions = self.model.predict([spatial_input, temporal_input], verbose=0)[0]
                
                # Get predicted threat class
                predicted_idx = np.argmax(predictions)
                threat_type = self.threat_classes[predicted_idx]
                confidence = float(predictions[predicted_idx])
                
                result['threat_type'] = threat_type
                result['confidence'] = confidence
                result['threat_detected'] = (threat_type != 'benign' and confidence > 0.6)
                
                # Calculate threat score (0-1)
                result['threat_score'] = float(1 - predictions[0])  # Inverse of benign probability
                
                # Calculate risk level (0-100)
                result['risk_level'] = int(result['threat_score'] * 100)
                
                # Determine recommended action
                if result['risk_level'] >= 90:
                    result['recommended_action'] = 'block'
                elif result['risk_level'] >= 70:
                    result['recommended_action'] = 'require_mfa'
                elif result['risk_level'] >= 50:
                    result['recommended_action'] = 'challenge'
                elif result['risk_level'] >= 30:
                    result['recommended_action'] = 'monitor'
                else:
                    result['recommended_action'] = 'allow'
                
                # Add analysis details
                result['spatial_analysis'] = self._analyze_spatial_features(spatial_features)
                result['temporal_analysis'] = self._analyze_temporal_patterns(temporal_features)
                
                # Generate reasoning
                result['reasoning'] = self._generate_reasoning(
                    result['threat_type'],
                    result['spatial_analysis'],
                    result['temporal_analysis']
                )
                
            except Exception as e:
                logger.error(f"Error in threat analysis: {e}")
                # Fallback to rule-based
                result = self._rule_based_threat_analysis(session_data, behavior_data)
        else:
            # Use rule-based analysis
            result = self._rule_based_threat_analysis(session_data, behavior_data)
        
        return result
    
    def _analyze_spatial_features(self, spatial_features: np.ndarray) -> Dict:
        """Analyze spatial features for anomalies"""
        analysis = {
            'device_suspicious': spatial_features[0] < 0.3,
            'network_suspicious': spatial_features[5] < 0.3,
            'location_anomaly': spatial_features[10] > 0.5,
            'vpn_detected': spatial_features[7] > 0.5,
            'tor_detected': spatial_features[8] > 0.5,
            'high_failure_rate': spatial_features[16] > 0.5,
        }
        return analysis
    
    def _analyze_temporal_patterns(self, temporal_features: np.ndarray) -> Dict:
        """Analyze temporal patterns for anomalies"""
        # Calculate statistics over temporal sequence
        recent_window = temporal_features[-10:]  # Last 10 time steps
        
        analysis = {
            'behavior_variance': float(np.var(recent_window)),
            'rapid_actions': bool(np.mean(recent_window[:, 6]) > 0.7),  # Navigation speed
            'high_vault_access': bool(np.mean(recent_window[:, 3]) > 0.7),
            'suspicious_clipboard': bool(np.any(recent_window[:, 10] > 0.5)),
            'rapid_data_access': bool(np.any(recent_window[:, 11] > 0.5)),
            'pattern_consistency': float(1 - np.std(recent_window)),
        }
        return analysis
    
    def _generate_reasoning(self, threat_type: str, spatial: Dict, temporal: Dict) -> List[str]:
        """Generate human-readable reasoning for threat detection"""
        reasoning = []
        
        if threat_type == 'brute_force':
            reasoning.append("Multiple failed login attempts detected")
            if spatial.get('high_failure_rate'):
                reasoning.append("Abnormally high failure rate")
        
        elif threat_type == 'credential_stuffing':
            reasoning.append("Rapid authentication attempts from multiple IPs")
            if spatial.get('network_suspicious'):
                reasoning.append("Suspicious network characteristics")
        
        elif threat_type == 'account_takeover':
            reasoning.append("Behavior pattern significantly different from user baseline")
            if spatial.get('device_suspicious'):
                reasoning.append("Unknown or suspicious device")
            if spatial.get('location_anomaly'):
                reasoning.append("Login from unusual location")
        
        elif threat_type == 'bot_activity':
            reasoning.append("Automated behavior patterns detected")
            if temporal.get('rapid_actions'):
                reasoning.append("Actions performed too quickly for human")
            if temporal.get('pattern_consistency') > 0.9:
                reasoning.append("Highly consistent timing suggests automation")
        
        elif threat_type == 'data_exfiltration':
            reasoning.append("Unusual data access pattern detected")
            if temporal.get('high_vault_access'):
                reasoning.append("Abnormally high vault access frequency")
            if temporal.get('rapid_data_access'):
                reasoning.append("Rapid sequential data access")
        
        elif threat_type == 'suspicious_pattern':
            if spatial.get('vpn_detected'):
                reasoning.append("VPN usage detected")
            if spatial.get('tor_detected'):
                reasoning.append("Tor network detected")
            if temporal.get('suspicious_clipboard'):
                reasoning.append("Unusual clipboard activity")
        
        return reasoning
    
    def _rule_based_threat_analysis(self, session_data: Dict, behavior_data: Dict) -> Dict:
        """
        Fallback rule-based threat analysis
        
        Args:
            session_data: Session information
            behavior_data: Behavior data
        
        Returns:
            Analysis results
        """
        risk_score = 0
        threat_type = 'benign'
        reasoning = []
        
        # Check for brute force
        failed_attempts = session_data.get('failed_attempts', 0)
        if failed_attempts >= 5:
            risk_score += 40
            threat_type = 'brute_force'
            reasoning.append(f"{failed_attempts} failed login attempts")
        
        # Check for suspicious device
        device_trust = session_data.get('device_trust_score', 1.0)
        if device_trust < 0.3:
            risk_score += 25
            if threat_type == 'benign':
                threat_type = 'account_takeover'
            reasoning.append("Suspicious or unknown device")
        
        # Check for suspicious network
        ip_trust = session_data.get('ip_trust_score', 1.0)
        if ip_trust < 0.3:
            risk_score += 20
            reasoning.append("Suspicious IP address")
        
        # Check for VPN/Tor
        if session_data.get('vpn_detected') or session_data.get('tor_detected'):
            risk_score += 15
            if threat_type == 'benign':
                threat_type = 'suspicious_pattern'
            reasoning.append("Anonymous network detected")
        
        # Check for rapid data access
        if behavior_data.get('rapid_data_access'):
            risk_score += 30
            if threat_type == 'benign':
                threat_type = 'data_exfiltration'
            reasoning.append("Unusually rapid data access")
        
        # Check for bot-like behavior
        if behavior_data.get('api_request_rate', 0) > 50:
            risk_score += 25
            if threat_type == 'benign':
                threat_type = 'bot_activity'
            reasoning.append("High API request rate suggests automation")
        
        return {
            'threat_detected': risk_score >= 50,
            'threat_type': threat_type,
            'threat_score': min(risk_score / 100.0, 1.0),
            'confidence': 0.7,
            'risk_level': min(risk_score, 100),
            'recommended_action': self._get_action_for_risk(risk_score),
            'spatial_analysis': {},
            'temporal_analysis': {},
            'reasoning': reasoning
        }
    
    def _get_action_for_risk(self, risk_score: int) -> str:
        """Determine recommended action based on risk score"""
        if risk_score >= 90:
            return 'block'
        elif risk_score >= 70:
            return 'require_mfa'
        elif risk_score >= 50:
            return 'challenge'
        elif risk_score >= 30:
            return 'monitor'
        else:
            return 'allow'
    
    def train(self, training_data: Dict, epochs=50, batch_size=32):
        """
        Train the hybrid CNN-LSTM model
        
        Args:
            training_data: Dictionary with 'spatial', 'temporal', and 'labels' keys
            epochs: Number of training epochs
            batch_size: Batch size for training
        """
        if not TENSORFLOW_AVAILABLE or self.model is None:
            logger.error("Cannot train: TensorFlow not available or model not initialized")
            return
        
        X_spatial = np.array(training_data['spatial'])
        X_temporal = np.array(training_data['temporal'])
        y = np.array(training_data['labels'])
        
        # Train model
        history = self.model.fit(
            [X_spatial, X_temporal],
            y,
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

