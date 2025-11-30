"""
Shared utilities and common functionality for the Password Manager application.

This package contains reusable components that are used across multiple apps
in the password manager project.
"""

# Version information
__version__ = '1.0.0'
__author__ = 'Password Manager Team'

# Import common utilities to make them easily accessible
try:
    from .validators import *
    from .constants import *
    from .utils import *
    from .decorators import *
    
    __all__ = [
        'validators',
        'constants', 
        'utils',
        'decorators',
    ]
except ImportError:
    # Handle gracefully during Django startup
    __all__ = []
