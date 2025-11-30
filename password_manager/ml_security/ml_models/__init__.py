"""
ML Models for Password Manager Security

This package contains implementations of various machine learning models:
- Password strength predictor (LSTM)
- Anomaly detector (Isolation Forest + Random Forest)
- Threat analyzer (Hybrid CNN-LSTM)
- Behavior clusterer (K-Means)
"""

import os
import logging

logger = logging.getLogger(__name__)

# Global model instances
_models = {}

def load_models():
    """
    Load all trained ML models on application startup
    """
    from .password_strength import PasswordStrengthPredictor
    from .anomaly_detector import AnomalyDetector
    from .threat_analyzer import ThreatAnalyzer
    
    global _models
    
    try:
        # Load password strength model
        _models['password_strength'] = PasswordStrengthPredictor()
        logger.info("Password strength model loaded")
    except Exception as e:
        logger.warning(f"Failed to load password strength model: {e}")
    
    try:
        # Load anomaly detection model
        _models['anomaly_detector'] = AnomalyDetector()
        logger.info("Anomaly detection model loaded")
    except Exception as e:
        logger.warning(f"Failed to load anomaly detection model: {e}")
    
    try:
        # Load threat analyzer model
        _models['threat_analyzer'] = ThreatAnalyzer()
        logger.info("Threat analyzer model loaded")
    except Exception as e:
        logger.warning(f"Failed to load threat analyzer model: {e}")
    
    return _models


def get_model(model_name):
    """
    Get a loaded model instance
    
    Args:
        model_name: Name of the model ('password_strength', 'anomaly_detector', 'threat_analyzer')
    
    Returns:
        Model instance or None if not loaded
    """
    return _models.get(model_name)


__all__ = ['load_models', 'get_model']

