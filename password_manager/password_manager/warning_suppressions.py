"""
Warning Suppressions for Development Environment

This module suppresses common development warnings that don't affect functionality.

Usage:
    Add to the top of settings.py:
    from .warning_suppressions import *
"""

import os
import warnings

# =============================================================================
# TensorFlow Warnings
# =============================================================================

# Suppress TensorFlow INFO messages (0=ALL, 1=INFO, 2=WARNING, 3=ERROR)
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

# Optional: Disable oneDNN custom operations
# Uncomment if you want to disable oneDNN (may slightly reduce performance)
# os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'

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

# Suppress Keras deprecation warnings
warnings.filterwarnings(
    'ignore',
    category=UserWarning,
    module='keras',
    message='.*input_length.*'
)

# Suppress Django model reloading warnings
warnings.filterwarnings(
    'ignore',
    category=RuntimeWarning,
    module='django.db.models.base',
    message='.*was already registered.*'
)

# =============================================================================
# Confirmation Message
# =============================================================================

# Print confirmation that suppressions are loaded (ASCII safe for all terminals)
# print("[OK] Warning suppressions loaded (TensorFlow, Keras, Django)")

