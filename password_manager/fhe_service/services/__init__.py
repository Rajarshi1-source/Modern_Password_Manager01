"""
FHE Services Module

Contains:
- ConcreteService: Lightweight FHE operations using Concrete-Python
- SEALBatchService: Batch FHE operations using TenSEAL/SEAL
- FHEOperationRouter: Intelligent routing between services
- FHEComputationCache: Redis-based caching for FHE results
- AdaptiveFHEManager: Adaptive circuit depth management

Singleton getters:
- get_concrete_service(): Get/create ConcreteService singleton
- get_seal_service(): Get/create SEALBatchService singleton
- get_fhe_router(): Get/create FHEOperationRouter singleton
- get_fhe_cache(): Get/create FHEComputationCache singleton
- get_adaptive_manager(): Get/create AdaptiveFHEManager singleton
"""

# Import classes
from .concrete_service import ConcreteService, get_concrete_service
from .seal_service import SEALBatchService, get_seal_service
from .fhe_router import FHEOperationRouter, EncryptionTier
from .fhe_cache import FHEComputationCache, get_fhe_cache
from .adaptive_manager import AdaptiveFHEManager, get_adaptive_manager

# Import router singleton getter (depends on other services)
from .fhe_router import get_fhe_router

__all__ = [
    # Classes
    'ConcreteService',
    'SEALBatchService',
    'FHEOperationRouter',
    'EncryptionTier',
    'FHEComputationCache',
    'AdaptiveFHEManager',
    # Singleton getters
    'get_concrete_service',
    'get_seal_service',
    'get_fhe_router',
    'get_fhe_cache',
    'get_adaptive_manager',
]

