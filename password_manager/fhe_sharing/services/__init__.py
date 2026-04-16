"""
FHE Sharing Services Module

Contains:
- AutofillCircuitService: Legacy simulated autofill circuit (cipher_suite='simulated-v1')
- HomomorphicSharingService: Business logic for share lifecycle
- PreService: pyUmbral proxy re-encryption wrapper (cipher_suite='umbral-v1')
- PolicyFheService: TenSEAL CKKS homomorphic policy gates
"""

from .autofill_circuit_service import (
    AutofillCircuitService,
    get_autofill_circuit_service,
)
from .fhe_sharing_service import (
    HomomorphicSharingService,
    get_sharing_service,
)
from .pre_service import (
    PreService,
    ReencryptionResult,
    PreError,
    UmbralUnavailableError,
    KfragVerificationError,
    ReencryptionError,
    get_pre_service,
    is_available as pre_is_available,
)
from .policy_fhe_service import (
    PolicyFheService,
    PolicyDecision,
    get_policy_fhe_service,
)

__all__ = [
    'AutofillCircuitService',
    'get_autofill_circuit_service',
    'HomomorphicSharingService',
    'get_sharing_service',
    'PreService',
    'ReencryptionResult',
    'PreError',
    'UmbralUnavailableError',
    'KfragVerificationError',
    'ReencryptionError',
    'get_pre_service',
    'pre_is_available',
    'PolicyFheService',
    'PolicyDecision',
    'get_policy_fhe_service',
]
