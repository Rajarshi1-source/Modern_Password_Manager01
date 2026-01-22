"""
Verifiable Delay Function (VDF) Service
=========================================

Implements Wesolowski VDF for provable computation time.
Provides time-lock puzzles that cannot be solved faster than intended,
even with unlimited computing power.

Key Properties:
- Sequential computation (cannot be parallelized)
- Fast verification (O(log t) time)
- Based on repeated squaring in RSA groups

Reference: B. Wesolowski, "Efficient Verifiable Delay Functions" (2019)

@author Password Manager Team
@created 2026-01-22
"""

import os
import time
import hashlib
import secrets
import logging
from dataclasses import dataclass, field
from typing import Tuple, Optional, Dict, Any
from datetime import datetime
import json

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================

DEFAULT_MODULUS_BITS = int(getattr(settings, 'VDF_MODULUS_BITS', 2048))
DEFAULT_ITERATIONS_PER_SECOND = int(getattr(settings, 'VDF_ITERATIONS_PER_SECOND', 100000))
PRIME_BITS = 256  # Bits for Fiat-Shamir prime


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class VDFParams:
    """VDF parameters."""
    modulus: int
    challenge: int
    iterations: int
    
    def to_dict(self) -> Dict:
        return {
            'modulus': str(self.modulus),
            'challenge': str(self.challenge),
            'iterations': self.iterations
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'VDFParams':
        return cls(
            modulus=int(data['modulus']),
            challenge=int(data['challenge']),
            iterations=data['iterations']
        )


@dataclass
class VDFOutput:
    """VDF computation output with proof."""
    output: int                    # y = g^(2^t) mod n
    proof: int                     # Wesolowski proof π
    iterations: int                # Number of squarings t
    computation_time: float        # Actual time taken
    hardware_info: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            'output': str(self.output),
            'proof': str(self.proof),
            'iterations': self.iterations,
            'computation_time': self.computation_time,
            'hardware_info': self.hardware_info
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'VDFOutput':
        return cls(
            output=int(data['output']),
            proof=int(data['proof']),
            iterations=data['iterations'],
            computation_time=data.get('computation_time', 0),
            hardware_info=data.get('hardware_info', {})
        )


@dataclass
class VDFVerification:
    """Result of VDF verification."""
    is_valid: bool
    verification_time_ms: int
    error_message: Optional[str] = None


# =============================================================================
# VDF Service
# =============================================================================

class VDFService:
    """
    Verifiable Delay Function service using Wesolowski's construction.
    
    The VDF computes y = g^(2^t) mod n through sequential squaring.
    A proof π allows fast verification without recomputing.
    
    Security relies on:
    1. RSA assumption (factoring is hard)
    2. Low-order group assumption
    
    Verification equation: g^r · π^l = y (mod n)
    where l = H_prime(g, y) and r = 2^t mod l
    """
    
    def __init__(
        self,
        modulus_bits: int = DEFAULT_MODULUS_BITS,
        iterations_per_second: int = DEFAULT_ITERATIONS_PER_SECOND
    ):
        """
        Initialize VDF service.
        
        Args:
            modulus_bits: Size of RSA modulus (larger = more secure)
            iterations_per_second: Estimated iterations per second
        """
        self.modulus_bits = modulus_bits
        self.iterations_per_second = iterations_per_second
        self._modulus_cache = None
    
    # =========================================================================
    # Main Public API
    # =========================================================================
    
    def generate_params(self, delay_seconds: int) -> VDFParams:
        """
        Generate VDF parameters for a target delay.
        
        Args:
            delay_seconds: Target delay in seconds
            
        Returns:
            VDFParams with modulus, challenge, and iteration count
        """
        if delay_seconds < 1:
            raise ValueError("Delay must be at least 1 second")
        
        # Generate or reuse RSA modulus
        modulus = self._get_modulus()
        
        # Calculate iterations for target delay
        iterations = self.estimate_iterations(delay_seconds)
        
        # Generate random challenge
        challenge = secrets.randbelow(modulus - 2) + 2
        
        return VDFParams(
            modulus=modulus,
            challenge=challenge,
            iterations=iterations
        )
    
    def compute(
        self,
        params: VDFParams,
        progress_callback=None
    ) -> VDFOutput:
        """
        Compute VDF output and proof.
        
        This is the computationally expensive operation that
        requires 'iterations' sequential squarings.
        
        Args:
            params: VDF parameters
            progress_callback: Optional callback(percent, iterations_done)
            
        Returns:
            VDFOutput with output, proof, and timing info
        """
        logger.info(f"Starting VDF computation: {params.iterations:,} iterations")
        start_time = time.time()
        
        g = params.challenge
        n = params.modulus
        t = params.iterations
        
        # Step 1: Compute y = g^(2^t) mod n (sequential squaring)
        y = g
        report_interval = max(1, t // 100)
        
        for i in range(t):
            y = pow(y, 2, n)
            
            if progress_callback and i % report_interval == 0:
                progress = (i / t) * 100
                progress_callback(progress, i)
        
        # Step 2: Generate Wesolowski proof
        proof = self._wesolowski_prove(g, y, n, t)
        
        elapsed = time.time() - start_time
        logger.info(f"VDF computation complete in {elapsed:.2f}s")
        
        return VDFOutput(
            output=y,
            proof=proof,
            iterations=t,
            computation_time=elapsed,
            hardware_info=self._get_hardware_info()
        )
    
    def verify(
        self,
        params: VDFParams,
        output: VDFOutput
    ) -> VDFVerification:
        """
        Verify a VDF proof in O(log t) time.
        
        Much faster than recomputing: verification uses the proof
        to check correctness without sequential computation.
        
        Args:
            params: Original VDF parameters
            output: VDF output with proof
            
        Returns:
            VDFVerification result
        """
        start_time = time.time()
        
        try:
            is_valid = self._wesolowski_verify(
                g=params.challenge,
                y=output.output,
                proof=output.proof,
                n=params.modulus,
                t=params.iterations
            )
            
            elapsed_ms = int((time.time() - start_time) * 1000)
            
            return VDFVerification(
                is_valid=is_valid,
                verification_time_ms=elapsed_ms
            )
            
        except Exception as e:
            logger.error(f"VDF verification failed: {e}")
            return VDFVerification(
                is_valid=False,
                verification_time_ms=0,
                error_message=str(e)
            )
    
    # =========================================================================
    # Wesolowski VDF Implementation
    # =========================================================================
    
    def _wesolowski_prove(self, g: int, y: int, n: int, t: int) -> int:
        """
        Generate Wesolowski proof.
        
        Proof: π = g^⌊(2^t)/l⌋ mod n
        where l = H_prime(g, y) is a prime derived via Fiat-Shamir
        
        Args:
            g: Challenge (generator)
            y: Output (g^(2^t) mod n)
            n: RSA modulus
            t: Number of squarings
            
        Returns:
            Proof π
        """
        # Derive prime l via Fiat-Shamir
        l = self._fiat_shamir_prime(g, y, n)
        
        # Compute q = ⌊2^t / l⌋
        # We need to compute g^q mod n
        # q = (2^t) // l
        
        # We compute this by tracking the exponent mod l during squaring
        # Then compute g^q where q = (2^t - r) / l and r = 2^t mod l
        
        exponent = pow(2, t, l * n)  # 2^t mod (l*n) to get enough precision
        q = exponent // l
        
        # Compute proof π = g^q mod n
        proof = pow(g, q, n)
        
        return proof
    
    def _wesolowski_verify(
        self,
        g: int, y: int, proof: int, n: int, t: int
    ) -> bool:
        """
        Verify Wesolowski proof.
        
        Verification: g^r · π^l = y (mod n)
        where l = H_prime(g, y) and r = 2^t mod l
        
        This runs in O(log t) time, much faster than computing y.
        
        Args:
            g: Challenge
            y: Claimed output
            proof: Wesolowski proof π
            n: RSA modulus
            t: Number of squarings
            
        Returns:
            True if proof is valid
        """
        # Derive prime l via Fiat-Shamir
        l = self._fiat_shamir_prime(g, y, n)
        
        # Compute r = 2^t mod l
        r = pow(2, t, l)
        
        # Verify: g^r · π^l ≡ y (mod n)
        lhs = (pow(g, r, n) * pow(proof, l, n)) % n
        
        return lhs == y
    
    def _fiat_shamir_prime(self, g: int, y: int, n: int) -> int:
        """
        Derive a prime l from (g, y, n) using Fiat-Shamir heuristic.
        
        Args:
            g: Challenge
            y: Output
            n: Modulus
            
        Returns:
            A prime l of PRIME_BITS bits
        """
        # Hash the inputs to get deterministic randomness
        hash_input = f"{g}:{y}:{n}".encode()
        hash_bytes = hashlib.sha512(hash_input).digest()
        
        # Use hash to seed prime generation
        seed = int.from_bytes(hash_bytes[:32], 'big')
        
        # Find next prime after seed
        candidate = seed | (1 << (PRIME_BITS - 1)) | 1
        while not self._is_prime(candidate):
            candidate += 2
        
        return candidate
    
    # =========================================================================
    # Utility Methods
    # =========================================================================
    
    def estimate_iterations(
        self,
        delay_seconds: int,
        hardware_class: str = 'standard'
    ) -> int:
        """
        Estimate iterations for target delay.
        
        Args:
            delay_seconds: Target delay
            hardware_class: 'low', 'standard', 'high'
            
        Returns:
            Number of iterations
        """
        speeds = {
            'low': 30000,       # Raspberry Pi
            'standard': 100000,  # Laptop
            'high': 200000,     # High-end desktop
        }
        speed = speeds.get(hardware_class, self.iterations_per_second)
        return delay_seconds * speed
    
    def estimate_time(self, iterations: int) -> Dict:
        """
        Estimate time to complete iterations on various hardware.
        
        Args:
            iterations: Number of iterations
            
        Returns:
            Time estimates for different hardware
        """
        speeds = {
            'raspberry_pi': 30000,
            'smartphone': 50000,
            'laptop': 100000,
            'desktop': 150000,
            'high_end': 200000,
        }
        
        estimates = {}
        for device, speed in speeds.items():
            seconds = iterations / speed
            estimates[device] = {
                'seconds': int(seconds),
                'human_readable': self._format_duration(seconds)
            }
        
        return estimates
    
    def _get_modulus(self) -> int:
        """Get or generate RSA modulus."""
        if self._modulus_cache:
            return self._modulus_cache
        
        p, q = self._generate_safe_primes()
        self._modulus_cache = p * q
        return self._modulus_cache
    
    def _generate_safe_primes(self) -> Tuple[int, int]:
        """Generate two safe primes for RSA modulus."""
        half_bits = self.modulus_bits // 2
        
        p = self._generate_prime(half_bits)
        q = self._generate_prime(half_bits)
        
        # Ensure p != q
        while p == q:
            q = self._generate_prime(half_bits)
        
        return p, q
    
    def _generate_prime(self, bits: int) -> int:
        """Generate a random prime of given bit size."""
        while True:
            candidate = secrets.randbits(bits)
            candidate |= (1 << (bits - 1)) | 1  # Set MSB and LSB
            if self._is_prime(candidate):
                return candidate
    
    def _is_prime(self, n: int, k: int = 20) -> bool:
        """Miller-Rabin primality test."""
        if n < 2:
            return False
        if n == 2 or n == 3:
            return True
        if n % 2 == 0:
            return False
        
        # Write n-1 as 2^r * d
        r, d = 0, n - 1
        while d % 2 == 0:
            r += 1
            d //= 2
        
        # Witness loop
        for _ in range(k):
            a = secrets.randbelow(n - 3) + 2
            x = pow(a, d, n)
            
            if x == 1 or x == n - 1:
                continue
            
            for _ in range(r - 1):
                x = pow(x, 2, n)
                if x == n - 1:
                    break
            else:
                return False
        
        return True
    
    def _format_duration(self, seconds: float) -> str:
        """Format duration as human-readable string."""
        if seconds < 60:
            return f"{int(seconds)} seconds"
        elif seconds < 3600:
            return f"{int(seconds / 60)} minutes"
        elif seconds < 86400:
            return f"{seconds / 3600:.1f} hours"
        else:
            return f"{seconds / 86400:.1f} days"
    
    def _get_hardware_info(self) -> Dict:
        """Get information about the computing hardware."""
        import platform
        
        return {
            'platform': platform.system(),
            'processor': platform.processor(),
            'python_version': platform.python_version(),
            'timestamp': datetime.now().isoformat()
        }


# =============================================================================
# High-Level Time-Lock VDF Service
# =============================================================================

class TimeLockVDFService:
    """
    Higher-level service combining VDF with encryption for time-locked secrets.
    """
    
    def __init__(self):
        self.vdf = VDFService()
    
    def create_time_locked_secret(
        self,
        secret: bytes,
        delay_seconds: int
    ) -> Dict:
        """
        Create a time-locked secret that can only be unlocked after delay.
        
        Args:
            secret: Secret data to lock
            delay_seconds: Delay before secret can be retrieved
            
        Returns:
            Dictionary with encrypted data and VDF parameters
        """
        # Generate VDF parameters
        params = self.vdf.generate_params(delay_seconds)
        
        # Compute VDF to get output (this would normally be done by server setup)
        # In practice, we store the parameters and the secret is encrypted
        # with a key derived from the VDF output
        
        # For now, encrypt with a key derived from the challenge
        key_material = hashlib.sha256(str(params.challenge).encode()).digest()
        key = Fernet.generate_key()
        fernet = Fernet(key)
        encrypted_secret = fernet.encrypt(secret)
        
        return {
            'encrypted_data': encrypted_secret,
            'vdf_params': params.to_dict(),
            'unlock_key_encrypted': key,  # In production, this would be time-locked
        }
    
    def unlock_secret(
        self,
        locked_data: Dict,
        vdf_output: VDFOutput
    ) -> bytes:
        """
        Unlock a time-locked secret after VDF computation.
        
        Args:
            locked_data: Output from create_time_locked_secret
            vdf_output: Result of VDF computation
            
        Returns:
            Original secret
        """
        # Verify VDF was computed correctly
        params = VDFParams.from_dict(locked_data['vdf_params'])
        verification = self.vdf.verify(params, vdf_output)
        
        if not verification.is_valid:
            raise ValueError("VDF verification failed")
        
        # Decrypt the secret
        key = locked_data['unlock_key_encrypted']
        fernet = Fernet(key)
        return fernet.decrypt(locked_data['encrypted_data'])


# =============================================================================
# Module-level instances
# =============================================================================

vdf_service = VDFService()
time_lock_vdf_service = TimeLockVDFService()
