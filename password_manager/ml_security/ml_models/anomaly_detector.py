"""
Anomaly Detection for User Behavior Analysis

This module implements anomaly detection using:
- Isolation Forest for unsupervised anomaly detection
- Random Forest for supervised classification
- K-Means clustering for behavior grouping
"""

import numpy as np
import os
import logging
import joblib
import json
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import hashlib

logger = logging.getLogger(__name__)

try:
    from sklearn.ensemble import IsolationForest, RandomForestClassifier
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler
    from sklearn.decomposition import PCA
    SKLEARN_AVAILABLE = True
except ImportError:
    logger.warning("Scikit-learn not available. Anomaly detection will use rule-based methods.")
    SKLEARN_AVAILABLE = False


class AnomalyDetector:
    """
    Multi-model anomaly detector for user behavior analysis
    
    Models:
    - Isolation Forest: Unsupervised anomaly detection
    - Random Forest: Supervised threat classification
    - K-Means: Behavior clustering
    """
    
    def __init__(self, model_dir=None):
        self.model_dir = model_dir or os.path.join(
            os.path.dirname(__file__),
            '..',
            'trained_models'
        )
        
        # Initialize models
        self.isolation_forest = None
        self.random_forest = None
        self.kmeans = None
        self.scaler = StandardScaler()
        self.pca = PCA(n_components=10)
        
        # Feature names for consistency
        self.feature_names = [
            'hour_of_day', 'day_of_week', 'session_duration',
            'typing_speed', 'vault_accesses', 'password_updates',
            'ip_consistency', 'device_consistency', 'location_consistency',
            'time_since_last_login', 'failed_login_attempts',
            'vault_access_frequency', 'unusual_time_score',
            'location_distance', 'device_fingerprint_similarity'
        ]
        
        if SKLEARN_AVAILABLE:
            try:
                self._load_models()
            except Exception as e:
                logger.warning(f"Failed to load anomaly detection models: {e}")
                self._initialize_models()
    
    def _initialize_models(self):
        """Initialize new models with default parameters"""
        if not SKLEARN_AVAILABLE:
            return
        
        # Isolation Forest for unsupervised anomaly detection
        self.isolation_forest = IsolationForest(
            contamination=0.1,  # Expected proportion of anomalies
            max_samples=256,
            random_state=42,
            n_estimators=100
        )
        
        # Random Forest for supervised classification
        self.random_forest = RandomForestClassifier(
            n_estimators=200,
            max_depth=15,
            min_samples_split=5,
            min_samples_leaf=2,
            random_state=42,
            class_weight='balanced'
        )
        
        # K-Means for behavior clustering
        self.kmeans = KMeans(
            n_clusters=5,  # Normal, suspicious, high-risk, bot, legitimate
            random_state=42,
            n_init=10
        )
        
        logger.info("Initialized new anomaly detection models")
    
    def _load_models(self):
        """Load pre-trained models from disk"""
        try:
            isolation_path = os.path.join(self.model_dir, 'isolation_forest.pkl')
            rf_path = os.path.join(self.model_dir, 'random_forest.pkl')
            kmeans_path = os.path.join(self.model_dir, 'kmeans.pkl')
            scaler_path = os.path.join(self.model_dir, 'scaler.pkl')
            
            if os.path.exists(isolation_path):
                self.isolation_forest = joblib.load(isolation_path)
                logger.info("Loaded Isolation Forest model")
            
            if os.path.exists(rf_path):
                self.random_forest = joblib.load(rf_path)
                logger.info("Loaded Random Forest model")
            
            if os.path.exists(kmeans_path):
                self.kmeans = joblib.load(kmeans_path)
                logger.info("Loaded K-Means model")
            
            if os.path.exists(scaler_path):
                self.scaler = joblib.load(scaler_path)
                logger.info("Loaded feature scaler")
            
        except Exception as e:
            logger.error(f"Error loading models: {e}")
            self._initialize_models()
    
    def extract_features(self, session_data: Dict) -> np.ndarray:
        """
        Extract features from session data
        
        Args:
            session_data: Dictionary containing session information
        
        Returns:
            Feature array
        """
        current_time = datetime.now()
        
        features = {
            'hour_of_day': current_time.hour,
            'day_of_week': current_time.weekday(),
            'session_duration': session_data.get('session_duration', 0),
            'typing_speed': session_data.get('typing_speed', 0),
            'vault_accesses': session_data.get('vault_accesses', 0),
            'password_updates': session_data.get('password_updates', 0),
            'ip_consistency': session_data.get('ip_consistency', 1.0),
            'device_consistency': session_data.get('device_consistency', 1.0),
            'location_consistency': session_data.get('location_consistency', 1.0),
            'time_since_last_login': session_data.get('time_since_last_login', 0),
            'failed_login_attempts': session_data.get('failed_login_attempts', 0),
            'vault_access_frequency': session_data.get('vault_access_frequency', 0),
            'unusual_time_score': self._calculate_time_anomaly_score(
                current_time, 
                session_data.get('typical_hours', [])
            ),
            'location_distance': session_data.get('location_distance', 0),
            'device_fingerprint_similarity': session_data.get('device_similarity', 1.0),
        }
        
        # Convert to numpy array in correct order
        feature_array = np.array([features[name] for name in self.feature_names])
        return feature_array.reshape(1, -1)
    
    def _calculate_time_anomaly_score(self, current_time: datetime, typical_hours: List[int]) -> float:
        """
        Calculate anomaly score based on login time
        
        Args:
            current_time: Current datetime
            typical_hours: List of typical login hours
        
        Returns:
            Anomaly score (0-1, higher means more unusual)
        """
        if not typical_hours:
            return 0.5  # No history, neutral score
        
        current_hour = current_time.hour
        
        # Check if current hour is in typical hours
        if current_hour in typical_hours:
            return 0.0  # Normal
        
        # Calculate distance to nearest typical hour
        hour_distances = [min(abs(current_hour - h), 24 - abs(current_hour - h)) for h in typical_hours]
        min_distance = min(hour_distances)
        
        # Normalize to 0-1 (12 hours = maximum distance)
        return min(min_distance / 12.0, 1.0)
    
    def detect_anomaly(self, session_data: Dict, user_profile: Dict = None) -> Dict:
        """
        Detect anomalies in user session
        
        Args:
            session_data: Current session information
            user_profile: User's historical behavior profile
        
        Returns:
            Dictionary with anomaly detection results
        """
        # Extract features
        features = self.extract_features(session_data)
        
        # Initialize result
        result = {
            'is_anomaly': False,
            'anomaly_score': 0.0,
            'confidence': 0.0,
            'anomaly_type': None,
            'severity': 'low',
            'contributing_factors': [],
            'recommended_action': 'monitor'
        }
        
        if SKLEARN_AVAILABLE and self.isolation_forest is not None:
            # Isolation Forest prediction
            try:
                # Scale features
                features_scaled = self.scaler.transform(features)
                
                # Predict anomaly (-1 = anomaly, 1 = normal)
                prediction = self.isolation_forest.predict(features_scaled)[0]
                # Get anomaly score (lower = more anomalous)
                anomaly_score = self.isolation_forest.score_samples(features_scaled)[0]
                
                # Convert to probability (0-1, higher = more anomalous)
                anomaly_probability = 1 / (1 + np.exp(anomaly_score))
                
                result['is_anomaly'] = (prediction == -1)
                result['anomaly_score'] = float(anomaly_probability)
                result['confidence'] = 0.85
                
                # Determine severity
                if anomaly_probability > 0.8:
                    result['severity'] = 'critical'
                    result['recommended_action'] = 'block_and_alert'
                elif anomaly_probability > 0.6:
                    result['severity'] = 'high'
                    result['recommended_action'] = 'require_mfa'
                elif anomaly_probability > 0.4:
                    result['severity'] = 'medium'
                    result['recommended_action'] = 'alert'
                else:
                    result['severity'] = 'low'
                    result['recommended_action'] = 'monitor'
                
            except Exception as e:
                logger.error(f"Error in Isolation Forest prediction: {e}")
        
        # Rule-based analysis
        rule_based_result = self._rule_based_detection(session_data, user_profile)
        
        # Combine ML and rule-based results
        if rule_based_result['is_anomaly']:
            result['is_anomaly'] = True
            result['anomaly_score'] = max(result['anomaly_score'], rule_based_result['anomaly_score'])
            result['contributing_factors'].extend(rule_based_result['factors'])
            result['anomaly_type'] = rule_based_result['anomaly_type']
        
        return result
    
    def _rule_based_detection(self, session_data: Dict, user_profile: Dict = None) -> Dict:
        """
        Rule-based anomaly detection (fallback and enhancement)
        
        Args:
            session_data: Session information
            user_profile: User behavior profile
        
        Returns:
            Detection results
        """
        result = {
            'is_anomaly': False,
            'anomaly_score': 0.0,
            'factors': [],
            'anomaly_type': None
        }
        
        # Check for impossible travel
        if session_data.get('location_distance', 0) > 500:  # 500 km
            time_diff = session_data.get('time_since_last_login', float('inf'))
            if time_diff < 1:  # Less than 1 hour
                result['is_anomaly'] = True
                result['anomaly_score'] = 0.9
                result['factors'].append('Impossible travel velocity')
                result['anomaly_type'] = 'velocity'
        
        # Check for unusual time
        typical_hours = user_profile.get('typical_login_hours', []) if user_profile else []
        current_hour = datetime.now().hour
        if typical_hours and current_hour not in typical_hours:
            result['factors'].append('Unusual login time')
            result['anomaly_score'] = max(result['anomaly_score'], 0.5)
            if not result['anomaly_type']:
                result['anomaly_type'] = 'time'
        
        # Check for unknown device
        if session_data.get('device_consistency', 1.0) < 0.3:
            result['is_anomaly'] = True
            result['anomaly_score'] = max(result['anomaly_score'], 0.7)
            result['factors'].append('Unknown or suspicious device')
            if not result['anomaly_type']:
                result['anomaly_type'] = 'device'
        
        # Check for multiple failed attempts
        if session_data.get('failed_login_attempts', 0) >= 3:
            result['is_anomaly'] = True
            result['anomaly_score'] = max(result['anomaly_score'], 0.8)
            result['factors'].append('Multiple failed login attempts')
            if not result['anomaly_type']:
                result['anomaly_type'] = 'behavior'
        
        # Check for unusual location
        if session_data.get('location_consistency', 1.0) < 0.2:
            result['anomaly_score'] = max(result['anomaly_score'], 0.6)
            result['factors'].append('Unusual login location')
            if not result['anomaly_type']:
                result['anomaly_type'] = 'location'
        
        # Check for rapid vault access
        vault_frequency = session_data.get('vault_access_frequency', 0)
        if vault_frequency > 10:  # More than 10 accesses per minute
            result['is_anomaly'] = True
            result['anomaly_score'] = max(result['anomaly_score'], 0.7)
            result['factors'].append('Unusually high vault access frequency')
            if not result['anomaly_type']:
                result['anomaly_type'] = 'frequency'
        
        return result
    
    def classify_threat(self, features: np.ndarray) -> Dict:
        """
        Classify threat level using Random Forest
        
        Args:
            features: Feature array
        
        Returns:
            Classification results
        """
        if not SKLEARN_AVAILABLE or self.random_forest is None:
            return {'threat_level': 'unknown', 'confidence': 0.0}
        
        try:
            features_scaled = self.scaler.transform(features)
            
            # Predict threat class
            prediction = self.random_forest.predict(features_scaled)[0]
            probabilities = self.random_forest.predict_proba(features_scaled)[0]
            
            threat_classes = ['benign', 'suspicious', 'malicious']
            
            return {
                'threat_level': threat_classes[prediction],
                'confidence': float(max(probabilities)),
                'probabilities': {
                    threat_classes[i]: float(probabilities[i]) 
                    for i in range(len(threat_classes))
                }
            }
        except Exception as e:
            logger.error(f"Error in threat classification: {e}")
            return {'threat_level': 'unknown', 'confidence': 0.0}
    
    def cluster_behavior(self, features: np.ndarray) -> int:
        """
        Cluster user behavior using K-Means
        
        Args:
            features: Feature array
        
        Returns:
            Cluster ID
        """
        if not SKLEARN_AVAILABLE or self.kmeans is None:
            return 0
        
        try:
            features_scaled = self.scaler.transform(features)
            cluster = self.kmeans.predict(features_scaled)[0]
            return int(cluster)
        except Exception as e:
            logger.error(f"Error in behavior clustering: {e}")
            return 0
    
    def train(self, training_data: List[Dict], labels: List[int] = None):
        """
        Train anomaly detection models
        
        Args:
            training_data: List of session data dictionaries
            labels: Optional labels for supervised training
        """
        if not SKLEARN_AVAILABLE:
            logger.error("Cannot train: scikit-learn not available")
            return
        
        # Extract features from training data
        X = np.array([self.extract_features(data)[0] for data in training_data])
        
        # Fit scaler
        self.scaler.fit(X)
        X_scaled = self.scaler.transform(X)
        
        # Train Isolation Forest (unsupervised)
        logger.info("Training Isolation Forest...")
        self.isolation_forest.fit(X_scaled)
        
        # Train K-Means (unsupervised)
        logger.info("Training K-Means clustering...")
        self.kmeans.fit(X_scaled)
        
        # Train Random Forest (supervised) if labels provided
        if labels is not None:
            logger.info("Training Random Forest classifier...")
            self.random_forest.fit(X_scaled, labels)
        
        # Save models
        self._save_models()
        logger.info("Models trained and saved successfully")
    
    def _save_models(self):
        """Save trained models to disk"""
        os.makedirs(self.model_dir, exist_ok=True)
        
        if self.isolation_forest is not None:
            joblib.dump(self.isolation_forest, os.path.join(self.model_dir, 'isolation_forest.pkl'))
        
        if self.random_forest is not None:
            joblib.dump(self.random_forest, os.path.join(self.model_dir, 'random_forest.pkl'))
        
        if self.kmeans is not None:
            joblib.dump(self.kmeans, os.path.join(self.model_dir, 'kmeans.pkl'))
        
        joblib.dump(self.scaler, os.path.join(self.model_dir, 'scaler.pkl'))
        
        logger.info("Models saved to disk")

