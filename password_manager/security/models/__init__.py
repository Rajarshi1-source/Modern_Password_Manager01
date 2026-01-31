"""
Security Models Package
========================

This package contains all security-related Django models.
It consolidates models from multiple submodules into a single namespace.
"""

# Import all models from core (previously models.py)
from .core import *

# Import ocean entropy models
from .ocean_entropy_models import (
    OceanEntropyBatch,
    HybridPasswordCertificate,
    BuoyHealthStatus,
    OceanEntropyUsageStats,
)

# Import duress code models
from .duress_models import (
    DuressCodeConfiguration,
    DuressCode,
    DecoyVault,
    DuressEvent,
    EvidencePackage,
    TrustedAuthority,
)
