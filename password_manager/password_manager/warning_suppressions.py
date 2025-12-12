"""
Warning Suppressions for Development Environment

This module suppresses common development warnings that don't affect functionality.
These warnings are expected in local development environments where certain
production-only libraries (liboqs, pqcrypto, concrete-python) aren't installed.

Usage:
    Add to the top of settings.py:
    from .warning_suppressions import *
"""

import os
import sys
import warnings
import logging

# =============================================================================
# TensorFlow Warnings - Suppress before TensorFlow imports
# =============================================================================

# Suppress TensorFlow INFO/WARNING messages (0=ALL, 1=INFO, 2=WARNING, 3=ERROR)
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

# Disable oneDNN optimizations warning
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'

# Suppress TensorFlow deprecation warnings
os.environ['TF_CPP_MIN_VLOG_LEVEL'] = '3'

# =============================================================================
# Detect Environment
# =============================================================================

# Check if we're in development mode (default True for local development)
DEBUG_MODE = os.environ.get('DEBUG', 'True').lower() == 'true'

# Check if running in Docker
IN_DOCKER = os.path.exists('/.dockerenv') or os.environ.get('DOCKER_CONTAINER', False)

# =============================================================================
# Suppress Cryptographic Library Warnings (Development Only)
# =============================================================================

if DEBUG_MODE and not IN_DOCKER:
    # In local development without Docker, suppress crypto library warnings
    # These are expected because liboqs, pqcrypto, and concrete-python
    # require Linux-specific compilation that's handled in Docker
    
    # Create a custom filter for crypto-related warnings
    class CryptoLibraryWarningFilter(logging.Filter):
        """Filter out expected crypto library warnings in development."""
        
        SUPPRESSED_MESSAGES = [
            'liboqs-python not available',
            'pqcrypto not available',
            'concrete-python not available',
            'Using SIMULATED Kyber',
            'Using fallback encryption',
            'FHE operations will use fallback',
            'not quantum-resistant',
            'NOT for production',
            'NOT SECURE FOR PRODUCTION',
            'Running ConcreteService in fallback mode',
        ]
        
        def filter(self, record):
            """Return False to suppress the log record."""
            message = str(record.getMessage())
            for suppressed in self.SUPPRESSED_MESSAGES:
                if suppressed in message:
                    return False
            return True
    
    # Apply the filter to root logger and specific loggers
    crypto_filter = CryptoLibraryWarningFilter()
    
    # Apply to root logger
    logging.getLogger().addFilter(crypto_filter)
    
    # Apply to specific loggers that generate these warnings
    for logger_name in [
        'auth_module.services.kyber_crypto',
        'behavioral_recovery.services.quantum_crypto_service',
        'fhe_service.services.concrete_service',
        '__main__',
    ]:
        logging.getLogger(logger_name).addFilter(crypto_filter)

# =============================================================================
# Python Package Warnings
# =============================================================================

# Suppress pkg_resources deprecation warning from djangorestframework-simplejwt
warnings.filterwarnings(
    'ignore',
    category=UserWarning,
    module='rest_framework_simplejwt',
    message='.*pkg_resources.*'
)

# Suppress pkg_resources deprecation warnings globally
warnings.filterwarnings(
    'ignore',
    category=DeprecationWarning,
    message='.*pkg_resources.*'
)

# Suppress Keras deprecation warnings
warnings.filterwarnings(
    'ignore',
    category=UserWarning,
    module='keras',
    message='.*input_length.*'
)

warnings.filterwarnings(
    'ignore',
    category=UserWarning,
    module='keras',
    message='.*is deprecated.*'
)

# Suppress Django model reloading warnings
warnings.filterwarnings(
    'ignore',
    category=RuntimeWarning,
    module='django.db.models.base',
    message='.*was already registered.*'
)

# Suppress dj-rest-auth compatibility warnings with django-allauth 65.x
warnings.filterwarnings('ignore', message='app_settings.USERNAME_REQUIRED is deprecated')
warnings.filterwarnings('ignore', message='app_settings.EMAIL_REQUIRED is deprecated')

# Suppress TensorFlow-related warnings
warnings.filterwarnings(
    'ignore',
    category=FutureWarning,
    module='tensorflow.*'
)

warnings.filterwarnings(
    'ignore',
    category=DeprecationWarning,
    module='tensorflow.*'
)

# =============================================================================
# Numpy/SciPy Warnings
# =============================================================================

warnings.filterwarnings(
    'ignore',
    category=DeprecationWarning,
    module='numpy.*'
)

# =============================================================================
# PyTorch Warnings
# =============================================================================

warnings.filterwarnings(
    'ignore',
    category=UserWarning,
    module='torch.*'
)

# =============================================================================
# Confirmation (Only in Verbose Mode)
# =============================================================================

# Set this environment variable to see suppression status:
# SHOW_SUPPRESSION_STATUS=True
if os.environ.get('SHOW_SUPPRESSION_STATUS', '').lower() == 'true':
    print("[OK] Warning suppressions loaded")
    if DEBUG_MODE and not IN_DOCKER:
        print("[OK] Crypto library warnings suppressed (development mode)")
