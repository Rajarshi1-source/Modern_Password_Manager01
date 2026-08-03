"""
Noise Encryptor
===============

Makes dark protocol payload BYTES computationally indistinguishable from
random, via AES-GCM encryption plus padding. "Computationally", not
"statistically": this is AES-GCM's designed security property under standard
hardness assumptions (a correct, non-reused nonce and a secure block cipher),
not an unconditional, information-theoretic guarantee.

Scope, stated precisely because the distinction matters: this hides the
CONTENT of a payload, and REDUCES the precision of its observable size by
bucketing the padded plaintext into one of a small set of fixed block sizes
(see BLOCK_SIZES) before a further FIXED 36-byte envelope (12-byte nonce +
16-byte GCM tag + 8-byte key hash) is appended on the wire. It does not hide
the size exactly:
  * A payload already at or beyond the largest block adds no further
    padding (only the size prefix), so its length is visible past that
    ceiling.
  * A payload landing within 4 bytes of a block boundary (see
    `_pad_to_block`'s `padding_needed` accounting) falls through to the
    NEXT block size doubled, not the boundary block itself -- a narrow band
    where the wire size overshoots the bucket a slightly larger payload
    would land in.
Neither behavior is exploited by this layer to leak anything on its own; both
are documented here because a reader relying on "bucketed" as an exact
guarantee would be wrong in these two cases. It does not make the traffic
itself unobservable - timing, volume and direction remain visible to anyone
watching the link, which is why this is one layer of traffic-analysis
resistance rather than anonymity. The anonymity comes from carrying that
traffic over a Tor v3 onion circuit (see `tor_service.py`), which has its own
stated scope and limits - it is not restated here.

Features:
- Variable-length padding
- Timing randomization
- Statistical analysis resistance
- Entropy normalization

@author Password Manager Team
@created 2026-02-02
"""

import os
import secrets
import hashlib
import logging
from typing import Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

# Target entropy per byte (should be close to 8 for true randomness)
TARGET_ENTROPY = 7.9

# Padding size ranges
MIN_PADDING = 32
MAX_PADDING = 2048
TYPICAL_PADDING = 256

# Block sizes for traffic shaping
BLOCK_SIZES = [64, 128, 256, 512, 1024, 2048, 4096]


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class NoisyBundle:
    """A bundle with noise applied for traffic analysis resistance."""
    original_size: int
    padded_size: int
    encrypted_data: bytes
    padding_size: int
    block_size: int
    entropy_score: float
    nonce: bytes = field(default_factory=lambda: os.urandom(12))
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def overhead_ratio(self) -> float:
        """Calculate the overhead ratio from padding."""
        if self.original_size == 0:
            return 0.0
        return self.padded_size / self.original_size


# =============================================================================
# Noise Encryptor
# =============================================================================

class NoiseEncryptor:
    """
    Applies noise and obfuscation to traffic bundles.

    See the module docstring for the precise, non-overclaiming scope of what
    this buys: computational (not statistical) indistinguishability of the
    output bytes, and bucketed (not exact) size hiding -- with a ceiling at
    the largest configured block size, and a narrow near-boundary band that
    overshoots to the next block doubled instead of the boundary block.

    Goals:
    - Reduce the precision of a payload's observable size (bucketed, bounded)
    - Add timing uncertainty
    - Normalize entropy distribution
    """
    
    def __init__(self):
        self._crypto_service = None
    
    @property
    def crypto_service(self):
        """Lazy load crypto service."""
        if self._crypto_service is None:
            from .crypto_service import CryptoService
            self._crypto_service = CryptoService()
        return self._crypto_service
    
    # =========================================================================
    # Noise Application
    # =========================================================================
    
    def apply_noise(self, bundle) -> NoisyBundle:
        """
        Apply noise to a traffic bundle.
        
        Args:
            bundle: TrafficBundle to process
            
        Returns:
            NoisyBundle with noise applied
        """
        original_data = bundle.encrypted_payload
        original_size = len(original_data)
        
        # Step 1: Add random padding
        padded_data, padding_size = self._add_padding(original_data)
        
        # Step 2: Normalize to block size
        block_size = self._select_block_size(len(padded_data))
        blocked_data = self._pad_to_block(padded_data, block_size)
        
        # Step 3: Apply final encryption layer with random key
        # This ensures the output looks completely random
        noise_key = os.urandom(32)
        nonce = os.urandom(12)
        
        encrypted, tag = self.crypto_service.encrypt_aes_gcm(
            key=noise_key,
            nonce=nonce,
            plaintext=blocked_data,
        )
        
        # Combine: nonce + tag + encrypted + noise_key_hash
        # The key hash allows verification without exposing the key
        key_hash = hashlib.sha256(noise_key).digest()[:8]
        final_data = nonce + (tag or b'') + (encrypted or b'') + key_hash
        
        # Step 4: Calculate entropy score
        entropy = self._calculate_entropy(final_data)
        
        # Update bundle with metadata
        bundle.padding_size = padding_size
        bundle.save(update_fields=['padding_size'])
        
        return NoisyBundle(
            original_size=original_size,
            padded_size=len(final_data),
            encrypted_data=final_data,
            padding_size=padding_size,
            block_size=block_size,
            entropy_score=entropy,
            nonce=nonce,
        )
    
    def remove_noise(
        self,
        noisy_data: bytes,
        noise_key: bytes,
    ) -> bytes:
        """
        Remove noise from received data.
        
        Args:
            noisy_data: Data with noise applied
            noise_key: The key used for noise encryption
            
        Returns:
            Original data with noise removed
        """
        if len(noisy_data) < 28 + 8:  # nonce(12) + tag(16) + key_hash(8)
            raise ValueError("Data too short")
        
        # Extract components
        nonce = noisy_data[:12]
        tag = noisy_data[12:28]
        key_hash = noisy_data[-8:]
        ciphertext = noisy_data[28:-8]
        
        # Verify key hash
        expected_hash = hashlib.sha256(noise_key).digest()[:8]
        if not secrets.compare_digest(key_hash, expected_hash):
            raise ValueError("Key verification failed")
        
        # Decrypt. ``decrypt_aes_gcm`` now raises ``DecryptionError``
        # on tag-verify failure (audit hardening, Group A / commit 1)
        # rather than returning ``None`` — translate to the existing
        # ``ValueError("Decryption failed")`` contract so this layer's
        # callers see no behaviour change.
        from .crypto_service import DecryptionError
        try:
            decrypted = self.crypto_service.decrypt_aes_gcm(
                key=noise_key,
                nonce=nonce,
                ciphertext=ciphertext,
                tag=tag,
            )
        except DecryptionError as e:
            raise ValueError("Decryption failed") from e
        
        # Remove block padding
        unblocked = self._remove_block_padding(decrypted)
        
        # Remove random padding
        original = self._remove_padding(unblocked)
        
        return original
    
    # =========================================================================
    # Padding Operations
    # =========================================================================
    
    def _add_padding(self, data: bytes) -> Tuple[bytes, int]:
        """
        Add random padding to data.
        
        Uses a distribution that makes traffic analysis harder:
        - Minimum padding always applied
        - Additional random padding based on original size
        - Occasional large padding for traffic shaping
        """
        # Base padding
        base_padding = MIN_PADDING
        
        # Size-proportional padding (5-15% of original size)
        proportional = int(len(data) * (0.05 + secrets.randbelow(10) / 100))
        
        # Random additional padding
        random_extra = secrets.randbelow(MAX_PADDING - MIN_PADDING)
        
        # Occasional large padding burst (10% chance)
        burst = 0
        if secrets.randbelow(10) == 0:
            burst = secrets.randbelow(MAX_PADDING)
        
        total_padding = min(base_padding + proportional + random_extra + burst, MAX_PADDING)
        
        # Generate random padding
        padding = os.urandom(total_padding)
        
        # Format: [2-byte padding length][padding][original data]
        padded = total_padding.to_bytes(2, 'big') + padding + data
        
        return padded, total_padding
    
    def _remove_padding(self, data: bytes) -> bytes:
        """Remove padding from data."""
        if len(data) < 2:
            raise ValueError("Data too short for padding")
        
        padding_size = int.from_bytes(data[:2], 'big')
        
        if len(data) < 2 + padding_size:
            raise ValueError("Invalid padding size")
        
        return data[2 + padding_size:]
    
    # =========================================================================
    # Block Operations
    # =========================================================================
    
    def _select_block_size(self, data_size: int) -> int:
        """
        Select appropriate block size for data.
        
        Chooses the smallest block size that can fit the data,
        with some randomization for traffic analysis resistance.
        """
        for block_size in BLOCK_SIZES:
            if data_size <= block_size:
                # 20% chance to use larger block for obfuscation
                if secrets.randbelow(5) == 0 and block_size != BLOCK_SIZES[-1]:
                    idx = BLOCK_SIZES.index(block_size)
                    return BLOCK_SIZES[min(idx + 1, len(BLOCK_SIZES) - 1)]
                return block_size
        
        # For very large data, use the largest block size
        return BLOCK_SIZES[-1]
    
    def _pad_to_block(self, data: bytes, block_size: int) -> bytes:
        """Pad data to exact block size."""
        current_size = len(data)
        
        if current_size >= block_size:
            # Data larger than block, just add size prefix
            return current_size.to_bytes(4, 'big') + data
        
        # Add padding to reach block size
        padding_needed = block_size - current_size - 4  # -4 for size prefix
        
        if padding_needed < 0:
            # Not enough room, use next block size
            next_block = block_size * 2
            padding_needed = next_block - current_size - 4
        
        padding = os.urandom(padding_needed)
        
        return current_size.to_bytes(4, 'big') + data + padding
    
    def _remove_block_padding(self, data: bytes) -> bytes:
        """Remove block padding from data."""
        if len(data) < 4:
            raise ValueError("Data too short for block format")
        
        original_size = int.from_bytes(data[:4], 'big')
        
        if len(data) < 4 + original_size:
            raise ValueError("Invalid block size")
        
        return data[4:4 + original_size]
    
    # =========================================================================
    # Entropy Analysis
    # =========================================================================
    
    def _calculate_entropy(self, data: bytes) -> float:
        """
        Calculate Shannon entropy of data.

        Returns bits of entropy per byte (max 8.0 for truly random).
        """
        if not data:
            return 0.0

        # Count byte frequencies
        freq = [0] * 256
        for byte in data:
            freq[byte] += 1

        # Calculate entropy
        import math
        entropy = 0.0
        length = len(data)

        for count in freq:
            if count > 0:
                probability = count / length
                entropy -= probability * math.log2(probability)

        return entropy

    calculate_entropy = _calculate_entropy

    def generate_noise(self, size: int) -> bytes:
        """Generate cryptographically secure random noise of the requested size."""
        import secrets as _secrets
        return _secrets.token_bytes(size)
    
    def verify_randomness(self, data: bytes) -> dict:
        """
        Verify that data appears sufficiently random.
        
        Performs several statistical tests to ensure
        the data is indistinguishable from random noise.
        """
        entropy = self._calculate_entropy(data)
        
        # Check byte distribution
        freq = [0] * 256
        for byte in data:
            freq[byte] += 1
        
        expected = len(data) / 256
        chi_squared = sum((f - expected) ** 2 / expected for f in freq if expected > 0)
        
        # Calculate longest run of zeros/ones
        bits = ''.join(format(b, '08b') for b in data)
        max_run = 0
        current_run = 0
        last_bit = None
        
        for bit in bits:
            if bit == last_bit:
                current_run += 1
                max_run = max(max_run, current_run)
            else:
                current_run = 1
                last_bit = bit
        
        # Calculate autocorrelation at lag 1
        autocorr = 0
        if len(data) > 1:
            mean = sum(data) / len(data)
            var = sum((b - mean) ** 2 for b in data) / len(data)
            if var > 0:
                autocorr = sum((data[i] - mean) * (data[i+1] - mean) 
                              for i in range(len(data) - 1)) / ((len(data) - 1) * var)
        
        return {
            'entropy_per_byte': entropy,
            'passes_entropy_test': entropy >= TARGET_ENTROPY * 0.95,
            'chi_squared': chi_squared,
            'passes_distribution_test': chi_squared < 300,  # Approximate threshold
            'max_bit_run': max_run,
            'passes_run_test': max_run < 30,  # Reasonable for random data
            'autocorrelation': autocorr,
            'passes_autocorrelation_test': abs(autocorr) < 0.1,
            'overall_quality': 'good' if entropy >= 7.5 else ('fair' if entropy >= 7.0 else 'poor'),
        }
    
    # =========================================================================
    # Timing Noise
    # =========================================================================
    
    def generate_timing_noise(self) -> int:
        """
        Generate random timing delay in milliseconds.
        
        Uses a distribution that mimics natural network jitter
        while adding uncertainty for timing analysis.
        """
        import random
        
        # Base delay: exponential distribution with mean 20ms
        base = int(random.expovariate(1/20))
        
        # Add uniform component: 0-50ms
        uniform = secrets.randbelow(50)
        
        # Occasional spike: 5% chance of 100-500ms delay
        spike = 0
        if secrets.randbelow(20) == 0:
            spike = 100 + secrets.randbelow(400)
        
        total = min(base + uniform + spike, 1000)  # Cap at 1 second
        
        return total
    
    def create_timing_pattern(self, count: int) -> list:
        """
        Create a pattern of timing delays for batch operations.
        
        The pattern is designed to resist timing correlation attacks.
        """
        delays = []
        
        for i in range(count):
            delay = self.generate_timing_noise()
            
            # Occasionally sync with previous (creates realistic patterns)
            if i > 0 and secrets.randbelow(4) == 0:
                delay = delays[-1] + secrets.randbelow(20) - 10
                delay = max(0, delay)
            
            delays.append(delay)
        
        return delays


# =============================================================================
# Module-level Instance
# =============================================================================

_noise_encryptor = None


def get_noise_encryptor() -> NoiseEncryptor:
    """Get noise encryptor singleton."""
    global _noise_encryptor
    if _noise_encryptor is None:
        _noise_encryptor = NoiseEncryptor()
    return _noise_encryptor
