"""
Vault Services Module

Contains service classes for vault operations:
- VaultOptimizationService: Caching, query optimization, compression
- CloudStorage: Cloud backup functionality

Zero-Knowledge Architecture:
All encryption/decryption happens client-side.
These services handle server-side operations on encrypted data only.
"""

from .vault_optimization_service import (
    VaultCacheManager,
    VaultQueryOptimizer,
    VaultCompression,
    AuthHashService,
    vault_cache,
    cache_vault_data,
    measure_query_time
)

__all__ = [
    'VaultCacheManager',
    'VaultQueryOptimizer', 
    'VaultCompression',
    'AuthHashService',
    'vault_cache',
    'cache_vault_data',
    'measure_query_time'
]

