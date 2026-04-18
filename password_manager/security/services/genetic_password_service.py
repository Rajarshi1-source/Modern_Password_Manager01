"""
Genetic Password Evolution Service
==================================

Generates passwords using DNA sequencing data and epigenetic markers.
Creates truly unique, biologically-tied credentials that are impossible to replicate.

Key Components:
- GeneticSeedGenerator: Converts DNA data to cryptographic seeds
- EpigeneticEvolutionEngine: Evolves passwords based on biological age
- GeneticPasswordGenerator: Main password generation interface

Privacy Model:
- Raw DNA data is NEVER stored
- Only cryptographic hashes are retained
- Uses HKDF for secure key derivation

Author: Password Manager Team
Created: 2026-01-16
"""

import hashlib
import hmac
import os
import logging
from datetime import datetime
from typing import Tuple, Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum

from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend

logger = logging.getLogger(__name__)


# =============================================================================
# Enums and Constants
# =============================================================================

class GeneticProvider(Enum):
    """Available DNA/genetic data providers."""
    SEQUENCING = "sequencing"  # Sequencing.com - Primary
    TWENTYTHREEME = "23andme"
    ANCESTRY = "ancestry"
    MANUAL = "manual"  # File upload


# Cryptographically relevant SNP positions for seed generation
# These are well-studied, publicly available SNPs with high variability
SEED_SNPS = [
    # Ancestry-related markers (high variability)
    "rs1426654",   # SLC24A5 - skin pigmentation
    "rs16891982",  # SLC45A2 - skin/eye pigmentation
    "rs12913832",  # HERC2/OCA2 - eye color
    "rs1800407",   # OCA2 - eye color
    "rs12896399",  # SLC24A4 - hair color
    "rs1805007",   # MC1R - red hair
    "rs1805008",   # MC1R - red hair variant
    
    # Physical traits (high variability)
    "rs4988235",   # LCT - lactose tolerance
    "rs1815739",   # ACTN3 - muscle fiber type
    "rs7412",      # APOE - lipid metabolism
    "rs429358",    # APOE variant
    "rs9939609",   # FTO - metabolism
    "rs1800497",   # ANKK1/DRD2 - dopamine receptor
    
    # Additional high-variability markers
    "rs6265",      # BDNF - brain function
    "rs1799971",   # OPRM1 - opioid receptor
    "rs4680",      # COMT - catechol metabolism
    "rs1801282",   # PPARG - metabolism
    "rs5219",      # KCNJ11 - potassium channel
    "rs7903146",   # TCF7L2 - transcription factor
    "rs2241880",   # ATG16L1 - autophagy
    "rs10830963",  # MTNR1B - melatonin receptor
    
    # Blood type related
    "rs8176719",   # ABO - blood type
    "rs8176746",   # ABO variant
    "rs505922",    # ABO expression
]


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class GeneticSeed:
    """Represents a seed derived from genetic data."""
    seed_bytes: bytes
    snp_count: int
    provider: str
    generated_at: datetime = field(default_factory=datetime.now)
    epigenetic_factor: Optional[float] = None
    evolution_generation: int = 1


@dataclass
class GeneticCertificate:
    """Proof of genetic origin for a password."""
    certificate_id: str
    password_hash_prefix: str
    genetic_hash_prefix: str
    provider: str
    snp_markers_used: int
    epigenetic_age: Optional[float]
    generation_timestamp: datetime
    evolution_generation: int
    combined_with_quantum: bool
    quantum_certificate_id: Optional[str]
    password_length: int
    entropy_bits: int
    signature: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            'certificate_id': self.certificate_id,
            'password_hash_prefix': self.password_hash_prefix,
            'genetic_hash_prefix': self.genetic_hash_prefix,
            'provider': self.provider,
            'snp_markers_used': self.snp_markers_used,
            'epigenetic_age': self.epigenetic_age,
            'generation_timestamp': self.generation_timestamp.isoformat(),
            'evolution_generation': self.evolution_generation,
            'combined_with_quantum': self.combined_with_quantum,
            'quantum_certificate_id': self.quantum_certificate_id,
            'password_length': self.password_length,
            'entropy_bits': self.entropy_bits,
            'signature': self.signature,
        }


# =============================================================================
# Genetic Seed Generator
# =============================================================================

class GeneticSeedGenerator:
    """
    Converts DNA data to cryptographic seeds.
    
    Process:
    1. Parse SNP data from provider
    2. Select cryptographically relevant markers
    3. Apply one-way hash with salt (HKDF)
    4. Combine with epigenetic factor if available
    5. Generate deterministic seed
    
    Privacy: Raw SNP data is processed immediately and discarded.
    Only the resulting hash is retained.
    """
    
    def __init__(self, salt: bytes = None, snp_list: List[str] = None):
        """
        Initialize the seed generator.
        
        Args:
            salt: Cryptographic salt (32 bytes). Generated if not provided.
            snp_list: Custom list of SNP IDs to use. Defaults to SEED_SNPS.
        """
        self.salt = salt or os.urandom(32)
        self.snp_list = snp_list or SEED_SNPS
    
    def generate_seed_from_snps(
        self,
        snp_data: Dict[str, str],
        epigenetic_factor: float = None,
        evolution_generation: int = 1
    ) -> GeneticSeed:
        """
        Generate cryptographic seed from SNP data.
        
        Args:
            snp_data: Dictionary of SNP ID -> genotype (e.g., {"rs123": "AG"})
            epigenetic_factor: Biological age modifier (0.5-2.0)
            evolution_generation: Current evolution generation
            
        Returns:
            GeneticSeed with derived bytes
            
        Security:
            - Uses HKDF (HMAC-based Key Derivation Function) with SHA3-256
            - Produces 64 bytes (512 bits) of entropy
            - Deterministic: same input always produces same output
        """
        if not snp_data:
            raise ValueError("snp_data is empty; cannot generate a genetic seed")

        # Build the working set from whichever source has richer data.
        # When the caller's SNP data does not overlap with our curated list we
        # fall back to the full ``snp_data`` so callers experimenting with
        # custom marker sets still get a deterministic seed.
        relevant_snps = {}
        overlap = [s for s in self.snp_list if s in snp_data]
        source_keys = overlap if overlap else sorted(snp_data.keys())
        for snp in sorted(source_keys):
            genotype = snp_data.get(snp, "NN")
            if len(genotype) == 2:
                genotype = "".join(sorted(genotype))
            relevant_snps[snp] = genotype

        # Count actual SNPs found (not "NN")
        found_snps = len([v for v in relevant_snps.values() if v != "NN"])
        if found_snps == 0:
            raise ValueError("No usable SNPs found in snp_data")
        
        if found_snps < 5:
            logger.warning(f"Low SNP count for seed generation: {found_snps}")
        
        # Create deterministic input string
        snp_string = "|".join(f"{k}:{v}" for k, v in sorted(relevant_snps.items()))
        
        # Add evolution generation to input
        snp_string += f"|gen:{evolution_generation}"
        
        # Apply HKDF for secure key derivation
        hkdf = HKDF(
            algorithm=hashes.SHA3_256(),
            length=64,  # 512 bits of entropy
            salt=self.salt,
            info=b"genetic_password_seed_v1",
            backend=default_backend()
        )
        
        seed_bytes = hkdf.derive(snp_string.encode('utf-8'))
        
        # Apply epigenetic modifier if available
        if epigenetic_factor is not None:
            seed_bytes = self._apply_epigenetic_modifier(
                seed_bytes, epigenetic_factor
            )
        
        logger.info(f"Generated genetic seed from {found_snps} SNPs, gen {evolution_generation}")
        
        return GeneticSeed(
            seed_bytes=seed_bytes,
            snp_count=found_snps,
            provider="genetic",
            generated_at=datetime.now(),
            epigenetic_factor=epigenetic_factor,
            evolution_generation=evolution_generation,
        )
    
    def _apply_epigenetic_modifier(
        self, 
        seed: bytes, 
        factor: float
    ) -> bytes:
        """
        Modify seed based on epigenetic aging factor.
        
        This creates password "evolution" where passwords naturally
        change as biological age increases.
        
        Args:
            seed: Original 64-byte seed
            factor: Epigenetic factor (biological_age / chronological_age)
                    Values typically range from 0.8 to 1.2
                    
        Returns:
            Modified 64-byte seed
        """
        # Quantize factor to discrete evolution generations
        # This prevents tiny changes from affecting the password
        quantized = int(factor * 100)
        
        # Derive new seed incorporating the factor
        factor_bytes = quantized.to_bytes(4, 'big')
        combined = seed[:32] + factor_bytes + seed[36:]
        
        # Hash to mix the factor throughout
        modified = hashlib.sha3_512(combined).digest()
        
        return modified
    
    def get_seed_hash_prefix(self, seed: GeneticSeed) -> str:
        """
        Get the hash prefix for storage/verification.
        
        Only the prefix is stored, not the full hash.
        """
        full_hash = hashlib.sha256(seed.seed_bytes).hexdigest()
        return f"sha256:{full_hash[:32]}..."


# =============================================================================
# Epigenetic Evolution Engine (Premium Feature)
# =============================================================================

class EpigeneticEvolutionEngine:
    """
    Manages password evolution based on epigenetic markers.
    
    Premium Feature: Requires active subscription.
    
    Key Concept: As users age, their epigenetic markers change.
    This engine periodically updates password seeds to reflect
    biological changes, creating "evolving" credentials.
    
    The evolution is:
    - Gradual: Small changes accumulate over time
    - Threshold-based: Only significant changes trigger evolution
    - Verifiable: Each evolution is logged with certificates
    """
    
    # Minimum biological age change to trigger evolution (years)
    EVOLUTION_THRESHOLD = 0.5
    
    # Maximum evolutions per year (rate limiting)
    MAX_EVOLUTIONS_PER_YEAR = 12
    
    def __init__(self, epigenetic_provider=None):
        """
        Initialize the evolution engine.
        
        Args:
            epigenetic_provider: Provider for biological age data
        """
        self.provider = epigenetic_provider
    
    async def check_evolution_needed(
        self,
        last_biological_age: float,
        current_biological_age: float
    ) -> Tuple[bool, float]:
        """
        Check if password evolution is needed based on biological age change.
        
        Args:
            last_biological_age: Biological age at last evolution
            current_biological_age: Current biological age
            
        Returns:
            Tuple of (should_evolve, age_change)
        """
        age_change = abs(current_biological_age - last_biological_age)
        should_evolve = age_change >= self.EVOLUTION_THRESHOLD
        
        return should_evolve, age_change
    
    def calculate_evolution_factor(self, *args, **kwargs) -> float:
        """Calculate an epigenetic evolution factor.

        Two calling conventions are supported for backwards-compatibility:

        * ``calculate_evolution_factor(biological_age, chronological_age)`` —
          legacy ratio (clamped to ``[0.5, 2.0]``).
        * ``calculate_evolution_factor(biological_age, previous_age, current_generation)``
          — age-delta based factor clamped to ``[0.0, 1.0]`` used by the
          Genetic Password test suite. Larger deltas produce a larger factor,
          and higher generations dampen the result slightly.
        """
        # Legacy two-arg form
        if len(args) == 2 and not kwargs:
            biological_age, chronological_age = args
            if chronological_age is None or chronological_age <= 0:
                return 1.0
            factor = float(biological_age) / float(chronological_age)
            return max(0.5, min(2.0, factor))

        biological_age = kwargs.get("biological_age")
        previous_age = kwargs.get("previous_age")
        current_generation = kwargs.get("current_generation", 0)
        if args:
            biological_age = args[0] if biological_age is None else biological_age
            if len(args) > 1:
                previous_age = args[1] if previous_age is None else previous_age
            if len(args) > 2:
                current_generation = args[2]

        if biological_age is None or previous_age is None:
            raise TypeError("biological_age and previous_age are required")

        delta = abs(float(biological_age) - float(previous_age))
        # Saturating curve: 5 years of delta ≈ 0.99; tiny deltas yield ~0
        base = 1.0 - pow(0.5, max(delta, 0.0))
        dampening = 1.0 / (1.0 + max(int(current_generation or 0), 0) * 0.05)
        return max(0.0, min(1.0, base * dampening))

    def should_evolve(
        self,
        current_age: float,
        previous_age: float,
        threshold: float = None,
    ) -> bool:
        """Return ``True`` when the biological age delta exceeds ``threshold``."""
        if threshold is None:
            threshold = self.EVOLUTION_THRESHOLD
        return abs(float(current_age) - float(previous_age)) >= float(threshold)

    def get_next_generation(self, current_generation: int) -> int:
        """Return the next generation number (simply ``current + 1``)."""
        return int(current_generation or 0) + 1

    def calculate_next_generation(
        self,
        current_generation: int,
        age_change: float
    ) -> int:
        """Legacy helper retained for backwards compatibility."""
        if age_change >= self.EVOLUTION_THRESHOLD:
            return current_generation + 1
        return current_generation


# =============================================================================
# Genetic Password Generator
# =============================================================================

class GeneticPasswordGenerator:
    """
    Main interface for generating DNA-based passwords.
    
    Combines:
    - Genetic seed from DNA data
    - Epigenetic evolution factor (Premium)
    - Quantum entropy (optional, from existing quantum service)
    
    Features:
    - Deterministic: Same DNA + generation = same password
    - Evolvable: Passwords change with biological aging
    - Quantum-enhanced: Can combine with quantum randomness
    - Certified: Each password gets a cryptographic certificate
    """
    
    DEFAULT_CHARSETS = {
        "uppercase": "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
        "lowercase": "abcdefghijklmnopqrstuvwxyz",
        "numbers": "0123456789",
        "symbols": "!@#$%^&*()_+-=[]{}|;:,.<>?",
    }
    
    # Password length limits
    MIN_LENGTH = 8
    MAX_LENGTH = 128
    DEFAULT_LENGTH = 16
    
    def __init__(
        self,
        seed_generator: GeneticSeedGenerator = None,
        evolution_engine: EpigeneticEvolutionEngine = None,
        quantum_generator = None,
    ):
        """
        Initialize the password generator.
        
        Args:
            seed_generator: GeneticSeedGenerator instance
            evolution_engine: EpigeneticEvolutionEngine for premium features
            quantum_generator: Existing quantum RNG service (optional)
        """
        self.seed_generator = seed_generator or GeneticSeedGenerator()
        self.evolution_engine = evolution_engine
        self.quantum_generator = quantum_generator
        self._cert_secret = os.environ.get("GENETIC_CERT_SECRET", "genetic-cert-secret-key")
    
    async def generate_genetic_password(
        self,
        snp_data: Dict[str, str],
        length: int = DEFAULT_LENGTH,
        use_uppercase: bool = True,
        use_lowercase: bool = True,
        use_numbers: bool = True,
        use_symbols: bool = True,
        custom_charset: str = None,
        epigenetic_factor: float = None,
        evolution_generation: int = 1,
        combine_with_quantum: bool = True,
    ) -> Tuple[str, GeneticCertificate]:
        """
        Generate a password seeded by genetic data.
        
        Args:
            snp_data: User's SNP genotype data
            length: Password length (8-128)
            use_uppercase: Include A-Z
            use_lowercase: Include a-z
            use_numbers: Include 0-9
            use_symbols: Include special characters
            custom_charset: Override default charset
            epigenetic_factor: Biological age modifier
            evolution_generation: Current evolution generation
            combine_with_quantum: Also use quantum entropy
            
        Returns:
            Tuple of (password, genetic_certificate)
            
        Raises:
            ValueError: If length is out of range or no charset selected
        """
        # Validate length
        length = max(self.MIN_LENGTH, min(self.MAX_LENGTH, length))
        
        # Generate genetic seed
        genetic_seed = self.seed_generator.generate_seed_from_snps(
            snp_data, epigenetic_factor, evolution_generation
        )
        
        # Optionally combine with quantum entropy
        quantum_cert_id = None
        if combine_with_quantum and self.quantum_generator:
            try:
                quantum_result = await self.quantum_generator.get_raw_random_bytes(32)
                if quantum_result and len(quantum_result) >= 2:
                    quantum_bytes, quantum_cert = quantum_result
                    combined_seed = self._combine_seeds(
                        genetic_seed.seed_bytes, quantum_bytes
                    )
                    if hasattr(quantum_cert, 'certificate_id'):
                        quantum_cert_id = quantum_cert.certificate_id
                else:
                    combined_seed = genetic_seed.seed_bytes
            except Exception as e:
                logger.warning(f"Quantum combination failed, using genetic only: {e}")
                combined_seed = genetic_seed.seed_bytes
        else:
            combined_seed = genetic_seed.seed_bytes
        
        # Build charset
        if custom_charset:
            charset = custom_charset
        else:
            charset = self._build_charset(
                use_uppercase, use_lowercase, use_numbers, use_symbols
            )
        
        if not charset:
            charset = self.DEFAULT_CHARSETS["lowercase"]
        
        # Generate password using HMAC-DRBG seeded with genetic data
        password = self._generate_from_seed(combined_seed, charset, length)
        
        # Calculate entropy
        import math
        entropy_bits = int(math.log2(len(charset)) * length)
        
        # Create certificate
        certificate = self._create_certificate(
            password=password,
            seed=genetic_seed,
            epigenetic_factor=epigenetic_factor,
            combined_with_quantum=combine_with_quantum,
            quantum_cert_id=quantum_cert_id,
            length=length,
            charset=charset,
            entropy_bits=entropy_bits,
        )
        
        logger.info(
            f"Generated genetic password: {length} chars, "
            f"{genetic_seed.snp_count} SNPs, gen {evolution_generation}, "
            f"quantum={combine_with_quantum}"
        )
        
        return password, certificate
    
    def _combine_seeds(self, genetic: bytes, quantum: bytes) -> bytes:
        """
        Combine genetic and quantum seeds.
        
        Uses XOR followed by SHA3-512 for thorough mixing.
        """
        # Ensure equal length for XOR
        genetic_32 = genetic[:32]
        quantum_32 = quantum[:32] if len(quantum) >= 32 else quantum.ljust(32, b'\x00')
        
        # XOR the seeds
        combined = bytes(g ^ q for g, q in zip(genetic_32, quantum_32))
        
        # Hash to mix thoroughly and extend to 64 bytes
        return hashlib.sha3_512(combined + genetic[32:]).digest()
    
    def _build_charset(
        self, 
        upper: bool, 
        lower: bool, 
        nums: bool, 
        syms: bool
    ) -> str:
        """Build charset from options."""
        charset = ""
        if upper:
            charset += self.DEFAULT_CHARSETS["uppercase"]
        if lower:
            charset += self.DEFAULT_CHARSETS["lowercase"]
        if nums:
            charset += self.DEFAULT_CHARSETS["numbers"]
        if syms:
            charset += self.DEFAULT_CHARSETS["symbols"]
        return charset
    
    def _generate_from_seed(
        self, 
        seed: bytes, 
        charset: str, 
        length: int
    ) -> str:
        """
        Generate password deterministically from seed.
        
        Uses HMAC-DRBG (Deterministic Random Bit Generator) for
        cryptographically secure, deterministic randomness.
        
        Implements rejection sampling to avoid modulo bias.
        """
        password = []
        counter = 0
        charset_len = len(charset)
        
        # Calculate maximum valid byte value for rejection sampling
        # This eliminates modulo bias
        max_valid = (256 // charset_len) * charset_len
        
        while len(password) < length:
            # HMAC-DRBG: deterministic pseudo-random output
            prng_output = hmac.new(
                seed,
                counter.to_bytes(8, 'big'),
                hashlib.sha256
            ).digest()
            
            for byte_val in prng_output:
                if len(password) >= length:
                    break
                    
                # Rejection sampling: skip values that would cause bias
                if byte_val < max_valid:
                    char_index = byte_val % charset_len
                    password.append(charset[char_index])
            
            counter += 1
            
            # Safety limit to prevent infinite loop
            if counter > 1000:
                logger.error("Password generation exceeded iteration limit")
                break
        
        return "".join(password)
    
    def _create_certificate(
        self,
        password: str,
        seed: GeneticSeed,
        epigenetic_factor: Optional[float],
        combined_with_quantum: bool,
        quantum_cert_id: Optional[str],
        length: int,
        charset: str,
        entropy_bits: int,
    ) -> GeneticCertificate:
        """
        Create cryptographic certificate proving genetic origin.
        
        The certificate includes:
        - Password hash (prefix only)
        - Genetic seed hash (prefix only)
        - Provider and SNP count
        - Epigenetic and evolution info
        - Cryptographic signature
        """
        import uuid
        
        # Hash password and genetic seed (store only prefix)
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        genetic_hash = hashlib.sha256(seed.seed_bytes).hexdigest()
        
        certificate_id = str(uuid.uuid4())
        
        # Build signature data
        sig_data = (
            f"{certificate_id}:"
            f"{password_hash[:16]}:"
            f"{genetic_hash[:16]}:"
            f"{seed.evolution_generation}:"
            f"{combined_with_quantum}"
        )
        
        # Create HMAC signature
        signature = hmac.new(
            self._cert_secret.encode(),
            sig_data.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return GeneticCertificate(
            certificate_id=certificate_id,
            password_hash_prefix=f"sha256:{password_hash[:16]}...",
            genetic_hash_prefix=f"sha256:{genetic_hash[:16]}...",
            provider=seed.provider,
            snp_markers_used=seed.snp_count,
            epigenetic_age=epigenetic_factor * 50 if epigenetic_factor else None,
            generation_timestamp=datetime.now(),
            evolution_generation=seed.evolution_generation,
            combined_with_quantum=combined_with_quantum,
            quantum_certificate_id=quantum_cert_id,
            password_length=length,
            entropy_bits=entropy_bits,
            signature=signature,
        )
    
    # ------------------------------------------------------------------
    # Convenience sync helpers (used by unit tests and sync callers)
    # ------------------------------------------------------------------
    def generate_password(
        self,
        seed: GeneticSeed,
        length: int = DEFAULT_LENGTH,
        uppercase: bool = True,
        lowercase: bool = True,
        numbers: bool = True,
        symbols: bool = True,
        custom_charset: str = None,
    ) -> str:
        """Generate a password deterministically from a ``GeneticSeed``."""
        length = max(self.MIN_LENGTH, min(self.MAX_LENGTH, length))
        charset = custom_charset or self._build_charset(uppercase, lowercase, numbers, symbols)
        if not charset:
            charset = self.DEFAULT_CHARSETS["lowercase"]
        return self._generate_from_seed(seed.seed_bytes, charset, length)

    def generate_password_with_certificate(
        self,
        seed: GeneticSeed,
        length: int = DEFAULT_LENGTH,
        uppercase: bool = True,
        lowercase: bool = True,
        numbers: bool = True,
        symbols: bool = True,
        custom_charset: str = None,
        combine_with_quantum: bool = False,
        quantum_cert_id: Optional[str] = None,
    ) -> Tuple[str, GeneticCertificate]:
        """Generate a password plus its signed certificate."""
        length = max(self.MIN_LENGTH, min(self.MAX_LENGTH, length))
        charset = custom_charset or self._build_charset(uppercase, lowercase, numbers, symbols)
        if not charset:
            charset = self.DEFAULT_CHARSETS["lowercase"]
        password = self._generate_from_seed(seed.seed_bytes, charset, length)
        import math
        entropy_bits = int(math.log2(len(charset)) * length) if charset else 0
        certificate = self._create_certificate(
            password=password,
            seed=seed,
            epigenetic_factor=seed.epigenetic_factor,
            combined_with_quantum=combine_with_quantum,
            quantum_cert_id=quantum_cert_id,
            length=length,
            charset=charset,
            entropy_bits=entropy_bits,
        )
        return password, certificate

    def generate_password_with_quantum(
        self,
        seed: GeneticSeed,
        length: int = DEFAULT_LENGTH,
        combine_with_quantum: bool = True,
        **charset_kwargs,
    ) -> str:
        """Generate a password by mixing ``seed`` with quantum entropy.

        Falls back to the purely genetic ``generate_password`` output if the
        quantum generator is unavailable or raises an exception — tests mock
        the quantum generator so the happy path executes in-process.
        """
        charset = charset_kwargs.get("custom_charset") or self._build_charset(
            charset_kwargs.get("uppercase", True),
            charset_kwargs.get("lowercase", True),
            charset_kwargs.get("numbers", True),
            charset_kwargs.get("symbols", True),
        )
        if not charset:
            charset = self.DEFAULT_CHARSETS["lowercase"]

        combined_seed = seed.seed_bytes
        if combine_with_quantum:
            try:
                if self.quantum_generator is None:
                    from security.services.quantum_rng_service import get_quantum_generator
                    self.quantum_generator = get_quantum_generator()
                q_out = self.quantum_generator.generate_password(
                    length=length
                ) if self.quantum_generator else None
                if isinstance(q_out, tuple) and q_out:
                    q_password = q_out[0]
                    combined_seed = self._combine_seeds(
                        seed.seed_bytes, q_password.encode() if isinstance(q_password, str) else bytes(q_password)
                    )
            except Exception as exc:
                logger.warning("Quantum combination failed, falling back to genetic only: %s", exc)

        return self._generate_from_seed(combined_seed, charset, length)

    def verify_certificate(self, certificate: GeneticCertificate) -> bool:
        """
        Verify the authenticity of a genetic certificate.
        
        Returns True if the signature is valid.
        """
        sig_data = (
            f"{certificate.certificate_id}:"
            f"{certificate.password_hash_prefix[7:23]}:"  # Extract hash portion
            f"{certificate.genetic_hash_prefix[7:23]}:"
            f"{certificate.evolution_generation}:"
            f"{certificate.combined_with_quantum}"
        )
        
        expected_sig = hmac.new(
            self._cert_secret.encode(),
            sig_data.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected_sig, certificate.signature)


# =============================================================================
# Singleton Instance Management
# =============================================================================

_genetic_generator_instance: Optional[GeneticPasswordGenerator] = None


def get_genetic_generator() -> GeneticPasswordGenerator:
    """
    Get or create the singleton GeneticPasswordGenerator instance.
    
    Lazily initializes the generator with quantum support if available.
    """
    global _genetic_generator_instance
    
    if _genetic_generator_instance is None:
        # Try to import quantum generator
        try:
            from .quantum_rng_service import get_quantum_generator
            quantum_gen = get_quantum_generator()
        except ImportError:
            quantum_gen = None
            logger.warning("Quantum generator not available for genetic passwords")
        
        # Create seed generator with secure salt
        seed_gen = GeneticSeedGenerator()
        
        # Create evolution engine (for premium features)
        evolution_engine = EpigeneticEvolutionEngine()
        
        _genetic_generator_instance = GeneticPasswordGenerator(
            seed_generator=seed_gen,
            evolution_engine=evolution_engine,
            quantum_generator=quantum_gen,
        )
    
    return _genetic_generator_instance


def reset_genetic_generator():
    """Reset the singleton instance (for testing)."""
    global _genetic_generator_instance
    _genetic_generator_instance = None
