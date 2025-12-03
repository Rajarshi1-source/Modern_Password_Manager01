"""
ML Models for Password Manager Security

This package contains implementations of various machine learning models:
- Password strength predictor (LSTM)
- Anomaly detector (Isolation Forest + Random Forest)
- Threat analyzer (Hybrid CNN-LSTM)
- Behavior clusterer (K-Means)

Performance Optimizations:
- Models are loaded once at application startup
- Warm-up predictions eliminate TensorFlow's first-call latency
- Singleton pattern prevents redundant model loading
"""

import os
import logging
import time

logger = logging.getLogger(__name__)

# Global model instances
_models = {}
_models_loaded = False


def _warmup_models():
    """
    Run warm-up predictions to eliminate TensorFlow's first-call latency.
    
    TensorFlow performs lazy initialization (JIT compilation, graph building)
    on the first actual computation. Running dummy predictions at startup
    ensures all subsequent requests are fast.
    """
    warmup_start = time.time()
    
    # Warm up password strength model
    if 'password_strength' in _models and _models['password_strength'] is not None:
        try:
            # Run a dummy prediction to trigger TensorFlow initialization
            _models['password_strength'].predict("WarmUpPassword123!")
            logger.info("Password strength model warmed up")
        except Exception as e:
            logger.warning(f"Failed to warm up password strength model: {e}")
    
    # Warm up anomaly detector
    if 'anomaly_detector' in _models and _models['anomaly_detector'] is not None:
        try:
            # Run a dummy anomaly detection
            dummy_session = {
                'session_duration': 300,
                'typing_speed': 45.0,
                'vault_accesses': 5,
                'device_consistency': 0.95,
                'location_consistency': 0.88
            }
            _models['anomaly_detector'].detect_anomaly(dummy_session, None)
            logger.info("Anomaly detector model warmed up")
        except Exception as e:
            logger.warning(f"Failed to warm up anomaly detector: {e}")
    
    # Warm up threat analyzer
    if 'threat_analyzer' in _models and _models['threat_analyzer'] is not None:
        try:
            # Run a dummy threat analysis
            dummy_session = {'ip': '127.0.0.1', 'user_agent': 'warmup'}
            dummy_behavior = {'typing_speed': 45.0, 'mouse_movement': 'normal'}
            _models['threat_analyzer'].analyze_threat(dummy_session, 'warmup_user', dummy_behavior)
            logger.info("Threat analyzer model warmed up")
        except Exception as e:
            logger.warning(f"Failed to warm up threat analyzer: {e}")
    
    warmup_time = time.time() - warmup_start
    logger.info(f"ML model warm-up completed in {warmup_time:.2f}s")


def load_models():
    """
    Load all trained ML models on application startup.
    
    This function implements a singleton pattern to ensure models are
    only loaded once, even if called multiple times during Django startup.
    """
    from .password_strength import PasswordStrengthPredictor
    from .anomaly_detector import AnomalyDetector
    from .threat_analyzer import ThreatAnalyzer
    
    global _models, _models_loaded
    
    # Prevent loading models multiple times
    if _models_loaded:
        logger.debug("ML models already loaded, skipping reload")
        return _models
    
    load_start = time.time()
    
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
    
    load_time = time.time() - load_start
    logger.info(f"ML models loaded in {load_time:.2f}s")
    
    # Warm up models to eliminate first-request latency
    _warmup_models()
    
    _models_loaded = True
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


def is_models_loaded():
    """Check if models have been loaded"""
    return _models_loaded


__all__ = ['load_models', 'get_model', 'is_models_loaded']

