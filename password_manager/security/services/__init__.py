"""
Security services package for password manager.

Includes:
- breach_monitor: HIBP breach monitoring
- crypto_service: Cryptographic operations
- quantum_rng_service: Quantum random number generation
- genetic_password_service: DNA-based password generation
- dna_provider_service: DNA data provider integrations
- epigenetic_service: Epigenetic evolution management
"""

# Import services to make them accessible through the package
from . import hibp
from . import breach_monitor
from . import crypto_service
from . import quantum_rng_service
from . import genetic_password_service
from . import dna_provider_service
from . import epigenetic_service

# Convenient imports for main classes
from .genetic_password_service import (
    GeneticSeedGenerator,
    GeneticPasswordGenerator,
    GeneticCertificate,
    get_genetic_generator,
)

from .dna_provider_service import (
    get_dna_provider,
    get_supported_providers,
    ManualUploadProvider,
    SequencingDNAProvider,
)

from .epigenetic_service import (
    EpigeneticEvolutionManager,
    get_epigenetic_provider,
    get_evolution_manager,
)
 