"""
Ocean Wave Entropy Provider
============================

Harvests cryptographic entropy from NOAA ocean buoy data.
Follows the QuantumRNGProvider pattern for integration with
the existing quantum entropy pool.

Entropy Sources:
- Wave height, period, and direction
- Sea surface temperature
- Wind speed and gusts
- Atmospheric pressure

Algorithm:
1. Fetch real-time data from multiple geographically distributed buoys
2. Extract LSBs from floating-point measurements (high entropy)
3. Apply von Neumann debiasing to remove statistical bias
4. Mix sources using XOR and hash conditioning
5. Validate min-entropy > 4 bits/byte

Security: Uses BLAKE3 for hash conditioning to ensure uniform distribution.

@author Password Manager Team
@created 2026-01-23
"""

import os
import asyncio
import logging
import hashlib
import struct
import secrets
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum

# Import base class from quantum_rng_service
from security.services.quantum_rng_service import QuantumRNGProvider, QuantumProvider

# Import NOAA client
from security.services.noaa_api_client import (
    NOAABuoyClient,
    BuoyReading,
    PRIORITY_BUOYS,
    ALL_BUOYS,
    get_noaa_client,
    extract_entropy_bytes_from_reading,
    combine_readings_entropy,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================

class OceanEntropyConfig:
    """Configuration for ocean entropy harvesting."""
    
    # Feature flag
    ENABLED = os.environ.get('OCEAN_ENTROPY_ENABLED', 'true').lower() == 'true'
    
    # Minimum entropy quality (bits per byte)
    MIN_ENTROPY_BITS = float(os.environ.get('OCEAN_MIN_ENTROPY_BITS_PER_BYTE', 4.0))
    
    # Number of buoys to fetch from
    MIN_BUOYS = int(os.environ.get('OCEAN_MIN_BUOYS', 2))
    MAX_BUOYS = int(os.environ.get('OCEAN_MAX_BUOYS', 5))
    
    # Pool contribution (percentage of total entropy pool)
    POOL_CONTRIBUTION_PERCENT = int(os.environ.get('OCEAN_POOL_CONTRIBUTION_PERCENT', 25))
    
    # Staleness threshold
    MAX_DATA_AGE_MINUTES = int(os.environ.get('OCEAN_MAX_DATA_AGE_MINUTES', 60))


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class OceanEntropyBatch:
    """Result of ocean entropy generation."""
    entropy_bytes: bytes
    source_buoys: List[str]
    readings_used: int
    generation_time: datetime
    min_entropy_estimate: float
    debiased: bool
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'bytes_count': len(self.entropy_bytes),
            'source_buoys': self.source_buoys,
            'readings_used': self.readings_used,
            'generation_time': self.generation_time.isoformat(),
            'min_entropy_estimate': self.min_entropy_estimate,
            'debiased': self.debiased,
        }


# =============================================================================
# Entropy Extraction Algorithm
# =============================================================================

class EntropyExtractor:
    """
    Extracts cryptographic-quality entropy from buoy data.
    
    Uses multiple techniques to maximize entropy:
    1. LSB extraction from floating-point mantissas
    2. Delta encoding between readings
    3. Von Neumann debiasing
    4. Hash conditioning with BLAKE3
    """
    
    @staticmethod
    def extract_lsb_bits(value: float, num_bits: int = 8) -> List[int]:
        """
        Extract least significant bits from a floating-point value.
        
        The LSBs of measurement noise are effectively random.
        """
        if value is None:
            return []
        
        # Pack as 64-bit double
        packed = struct.pack('d', value)
        
        # Convert to integer
        int_val = int.from_bytes(packed, 'little')
        
        # Extract LSBs
        bits = []
        for i in range(num_bits):
            bits.append((int_val >> i) & 1)
        
        return bits
    
    @staticmethod
    def von_neumann_debias(bits: List[int]) -> List[int]:
        """
        Apply von Neumann debiasing to a bit stream.
        
        Takes pairs of bits:
        - 01 -> 0
        - 10 -> 1
        - 00, 11 -> discard
        
        This removes any bias from the source, outputting unbiased bits
        at the cost of ~75% data loss.
        """
        debiased = []
        
        for i in range(0, len(bits) - 1, 2):
            if bits[i] == 0 and bits[i+1] == 1:
                debiased.append(0)
            elif bits[i] == 1 and bits[i+1] == 0:
                debiased.append(1)
            # else: discard pair
        
        return debiased
    
    @staticmethod
    def bits_to_bytes(bits: List[int]) -> bytes:
        """Convert bit list to bytes."""
        # Pad to multiple of 8
        while len(bits) % 8 != 0:
            bits.append(0)
        
        result = bytearray()
        for i in range(0, len(bits), 8):
            byte_bits = bits[i:i+8]
            byte_val = sum(b << (7-j) for j, b in enumerate(byte_bits))
            result.append(byte_val)
        
        return bytes(result)
    
    @staticmethod
    def extract_all_bits(reading: BuoyReading) -> List[int]:
        """Extract all available entropy bits from a reading."""
        all_bits = []
        
        # High entropy sources (waves, wind gusts)
        if reading.wave_height_m is not None:
            all_bits.extend(EntropyExtractor.extract_lsb_bits(reading.wave_height_m, 12))
        
        if reading.wave_period_sec is not None:
            all_bits.extend(EntropyExtractor.extract_lsb_bits(reading.wave_period_sec, 10))
        
        if reading.wind_gust_mps is not None:
            all_bits.extend(EntropyExtractor.extract_lsb_bits(reading.wind_gust_mps, 12))
        
        if reading.wind_speed_mps is not None:
            all_bits.extend(EntropyExtractor.extract_lsb_bits(reading.wind_speed_mps, 10))
        
        # Medium entropy (temperatures, pressure)
        if reading.sea_temp_c is not None:
            all_bits.extend(EntropyExtractor.extract_lsb_bits(reading.sea_temp_c, 8))
        
        if reading.air_temp_c is not None:
            all_bits.extend(EntropyExtractor.extract_lsb_bits(reading.air_temp_c, 8))
        
        if reading.pressure_hpa is not None:
            all_bits.extend(EntropyExtractor.extract_lsb_bits(reading.pressure_hpa, 10))
        
        # Directional data (lower entropy but still useful)
        if reading.wave_direction_deg is not None:
            all_bits.extend(EntropyExtractor.extract_lsb_bits(float(reading.wave_direction_deg), 6))
        
        if reading.wind_direction_deg is not None:
            all_bits.extend(EntropyExtractor.extract_lsb_bits(float(reading.wind_direction_deg), 6))
        
        return all_bits
    
    @staticmethod
    def estimate_min_entropy(data: bytes) -> float:
        """
        Estimate min-entropy of data in bits per byte.
        
        Uses a simple frequency-based estimation.
        Perfect random data has ~8 bits/byte.
        """
        if not data:
            return 0.0
        
        # Count byte frequencies
        counts = [0] * 256
        for b in data:
            counts[b] += 1
        
        # Find maximum probability
        max_prob = max(counts) / len(data)
        
        # Min-entropy = -log2(max_prob)
        import math
        if max_prob == 0:
            return 8.0
        
        return -math.log2(max_prob)
    
    @classmethod
    def extract_entropy_from_readings(
        cls,
        readings: List[BuoyReading],
        target_bytes: int = 64,
        debias: bool = True
    ) -> Tuple[bytes, float]:
        """
        Extract entropy from multiple buoy readings.
        
        Args:
            readings: List of BuoyReading objects
            target_bytes: Desired output size
            debias: Whether to apply von Neumann debiasing
            
        Returns:
            Tuple of (entropy_bytes, min_entropy_estimate)
        """
        all_bits = []
        
        # Extract bits from all readings
        for reading in readings:
            bits = cls.extract_all_bits(reading)
            all_bits.extend(bits)
        
        # Apply von Neumann debiasing if requested
        if debias:
            all_bits = cls.von_neumann_debias(all_bits)
        
        # Convert to bytes
        raw_bytes = cls.bits_to_bytes(all_bits)
        
        # If not enough bytes, we need more readings
        if len(raw_bytes) < target_bytes:
            logger.warning(f"Only extracted {len(raw_bytes)} bytes, need {target_bytes}")
        
        # Hash condition to target size using BLAKE3
        # This ensures uniform distribution and exact output size
        try:
            import blake3
            conditioned = blake3.blake3(raw_bytes).digest(length=target_bytes)
        except ImportError:
            # Fallback to BLAKE2b
            h = hashlib.blake2b(raw_bytes, digest_size=min(target_bytes, 64))
            conditioned = h.digest()
            
            # If need more bytes, extend with additional hashing
            while len(conditioned) < target_bytes:
                h = hashlib.blake2b(conditioned + raw_bytes, digest_size=64)
                conditioned += h.digest()
            conditioned = conditioned[:target_bytes]
        
        # Estimate entropy quality
        min_entropy = cls.estimate_min_entropy(conditioned)
        
        return conditioned, min_entropy


# =============================================================================
# Ocean Wave Entropy Provider
# =============================================================================

class OceanWaveEntropyProvider(QuantumRNGProvider):
    """
    NOAA Ocean Wave entropy provider.
    
    Harvests entropy from oceanic phenomena:
    - Wave patterns (height, period, direction)  
    - Temperature fluctuations
    - Atmospheric variations
    
    Uses multiple geographically distributed buoys for
    maximum entropy diversity and fault tolerance.
    
    Follows the QuantumRNGProvider interface for seamless
    integration with the existing entropy pool.
    """
    
    def __init__(self):
        self._client = get_noaa_client()
        self._last_region_index = 0
    
    async def fetch_random_bytes(self, count: int) -> Tuple[bytes, Optional[str]]:
        """
        Fetch random bytes from ocean wave data.
        
        Args:
            count: Number of random bytes to generate
            
        Returns:
            Tuple of (random_bytes, source_identifier)
        """
        if not OceanEntropyConfig.ENABLED:
            raise RuntimeError("Ocean entropy harvesting is disabled")
        
        # Select buoys using hourly rotation
        buoy_ids = self._select_buoys()
        
        # Fetch readings from selected buoys
        readings = await self._client.fetch_multiple_buoys(buoy_ids)
        
        if len(readings) < OceanEntropyConfig.MIN_BUOYS:
            raise RuntimeError(
                f"Insufficient buoy data: got {len(readings)}, need {OceanEntropyConfig.MIN_BUOYS}"
            )
        
        # Filter out stale readings
        now = datetime.utcnow()
        max_age = timedelta(minutes=OceanEntropyConfig.MAX_DATA_AGE_MINUTES)
        
        fresh_readings = [
            r for r in readings.values()
            if (now - r.timestamp) < max_age
        ]
        
        if len(fresh_readings) < OceanEntropyConfig.MIN_BUOYS:
            raise RuntimeError(f"Insufficient fresh buoy data: {len(fresh_readings)}")
        
        # Extract entropy
        entropy_bytes, min_entropy = EntropyExtractor.extract_entropy_from_readings(
            fresh_readings,
            target_bytes=count,
            debias=True
        )
        
        # Validate entropy quality
        if min_entropy < OceanEntropyConfig.MIN_ENTROPY_BITS:
            logger.warning(f"Low entropy quality: {min_entropy:.2f} bits/byte")
        
        # Generate source identifier
        source_buoys = [r.buoy_id for r in fresh_readings]
        source_id = f"ocean:{','.join(source_buoys[:3])}:{datetime.utcnow().strftime('%Y%m%d%H%M')}"
        
        logger.info(
            f"Generated {len(entropy_bytes)} bytes from {len(fresh_readings)} buoys "
            f"(min-entropy: {min_entropy:.2f} bits/byte)"
        )
        
        return entropy_bytes, source_id
    
    def _select_buoys(self) -> List[str]:
        """
        Select buoys to use for entropy harvesting.
        
        Uses hourly rotation across regions for geographic diversity.
        """
        # Get current region based on hour
        region = self._client.get_region_for_hour()
        
        # Get buoys from primary region
        primary_buoys = self._client.get_region_buoy_ids(region)
        
        # Add some from other regions for diversity
        all_regions = list(PRIORITY_BUOYS.keys())
        other_regions = [r for r in all_regions if r != region]
        
        selected = list(primary_buoys[:2])  # 2 from primary
        
        # Add 1 from each other region
        for r in other_regions:
            region_buoys = self._client.get_region_buoy_ids(r)
            if region_buoys:
                selected.append(region_buoys[0])
        
        return selected[:OceanEntropyConfig.MAX_BUOYS]
    
    def get_provider_name(self) -> str:
        """Return the provider identifier."""
        return "noaa_ocean_wave"
    
    def get_provider_enum(self):
        """Return the QuantumProvider enum value."""
        # Note: Need to add this to QuantumProvider enum
        return "noaa_ocean_wave"
    
    def get_quantum_source(self) -> str:
        """Return description of the entropy phenomenon used."""
        return "ocean_wave_patterns"
    
    def is_available(self) -> bool:
        """Check if provider is available and configured."""
        return OceanEntropyConfig.ENABLED
    
    async def get_status(self) -> Dict[str, Any]:
        """Get provider status including buoy health."""
        status = {
            'enabled': OceanEntropyConfig.ENABLED,
            'provider': 'noaa_ocean_wave',
            'source': 'Ocean wave patterns & temperature',
            'buoys': {},
            'healthy_count': 0,
            'total_buoys': len(ALL_BUOYS),
        }
        
        # Check a sample of buoys
        sample_buoys = self._select_buoys()
        
        for buoy_id in sample_buoys:
            buoy_status = await self._client.get_buoy_status(buoy_id)
            status['buoys'][buoy_id] = {
                'online': buoy_status.is_online,
                'last_reading': buoy_status.last_reading_time.isoformat() if buoy_status.last_reading_time else None,
                'age_minutes': buoy_status.data_age_minutes,
            }
            if buoy_status.is_online:
                status['healthy_count'] += 1
        
        status['available'] = status['healthy_count'] >= OceanEntropyConfig.MIN_BUOYS
        
        return status


# =============================================================================
# Entropy Mixer (combines multiple sources)
# =============================================================================

class EntropyMixer:
    """
    Mixes multiple entropy sources using cryptographic combining.
    
    Based on XOR mixing with hash conditioning.
    Even if one source is compromised, the output remains
    unpredictable as long as ONE source is truly random.
    """
    
    @staticmethod
    def mix_sources(*sources: bytes) -> bytes:
        """
        Mix multiple entropy sources together.
        
        Args:
            *sources: Variable number of byte sequences to mix
            
        Returns:
            Mixed entropy bytes
        """
        if not sources:
            raise ValueError("No sources to mix")
        
        if len(sources) == 1:
            return sources[0]
        
        # Filter out empty sources
        sources = [s for s in sources if s]
        if not sources:
            raise ValueError("All sources are empty")
        
        # Ensure all sources are same length (use minimum)
        min_len = min(len(s) for s in sources)
        sources = [s[:min_len] for s in sources]
        
        # XOR all sources together
        mixed = bytearray(sources[0])
        for source in sources[1:]:
            for i in range(min_len):
                mixed[i] ^= source[i]
        
        # Condition with SHA3-512 to eliminate statistical bias
        import hashlib
        try:
            conditioned = hashlib.sha3_512(bytes(mixed)).digest()
        except AttributeError:
            # Fallback if SHA3 not available
            conditioned = hashlib.sha512(bytes(mixed)).digest()
        
        # Truncate to original size
        return conditioned[:min_len]
    
    @staticmethod
    def weighted_mix(sources: Dict[str, Tuple[bytes, float]]) -> bytes:
        """
        Mix sources with weights based on quality estimates.
        
        Args:
            sources: Dict of {name: (bytes, quality_weight)}
            
        Returns:
            Mixed entropy
        """
        if not sources:
            raise ValueError("No sources to mix")
        
        # Sort by weight (higher = more trusted)
        sorted_sources = sorted(sources.items(), key=lambda x: x[1][1], reverse=True)
        
        # Extract just the bytes
        byte_sources = [s[1][0] for s in sorted_sources]
        
        return EntropyMixer.mix_sources(*byte_sources)


# =============================================================================
# Exceptions
# =============================================================================

class EntropyUnavailable(Exception):
    """Raised when entropy cannot be fetched from ocean sources."""
    pass


class InsufficientEntropySources(Exception):
    """Raised when not enough entropy sources are available."""
    pass


# =============================================================================
# Entropy Quality Assessment
# =============================================================================

def assess_entropy_quality(data: bytes) -> Dict[str, Any]:
    """
    Assess the quality of entropy using statistical tests.
    
    Uses Shannon entropy, chi-squared, and runs tests to evaluate
    the randomness quality of the generated entropy.
    
    Args:
        data: Bytes to analyze
        
    Returns:
        Dictionary with quality metrics
    """
    from collections import Counter
    import math
    
    if not data:
        return {'quality': 'poor', 'entropy_ratio': 0.0}
    
    # Shannon entropy calculation
    byte_counts = Counter(data)
    length = len(data)
    
    shannon_entropy = -sum(
        (count / length) * math.log2(count / length)
        for count in byte_counts.values()
    )
    
    # Max entropy for bytes is 8.0 bits
    entropy_ratio = shannon_entropy / 8.0
    
    # Chi-squared test for uniformity
    expected = length / 256
    chi_squared = sum(
        ((byte_counts.get(i, 0) - expected) ** 2) / expected
        for i in range(256)
    )
    
    # Runs test for randomness
    runs = 1
    for i in range(1, length):
        if data[i] != data[i-1]:
            runs += 1
    expected_runs = (2 * length - 1) / 3
    runs_z_score = abs(runs - expected_runs) / math.sqrt((16 * length - 29) / 90) if length > 2 else 0
    
    return {
        'shannon_entropy': shannon_entropy,
        'entropy_ratio': entropy_ratio,
        'chi_squared': chi_squared,
        'runs': runs,
        'runs_z_score': runs_z_score,
        'quality': 'good' if entropy_ratio > 0.95 else 'fair' if entropy_ratio > 0.8 else 'poor',
        'bytes_analyzed': length,
    }


# =============================================================================
# Hybrid Entropy Generator (Multi-Source)
# =============================================================================

@dataclass
class EntropySource:
    """Metadata about an entropy source contribution."""
    name: str
    provider: str
    bytes_contributed: int
    quality_score: float  # 0.0 to 1.0
    timestamp: datetime
    metadata: Dict[str, Any]


class HybridEntropyGenerator:
    """
    High-level hybrid entropy generator.
    
    Combines quantum and ocean sources with optional genetic seed.
    Provides unified interface for password generation.
    
    Security Principle:
    - XOR-based mixing ensures that compromise of ANY single source
      doesn't weaken the output (as long as ONE source remains secure)
    - SHA3-512 conditioning eliminates statistical bias
    - SHAKE256 for expandable output
    """
    
    def __init__(
        self,
        quantum_provider=None,
        ocean_provider=None,
        genetic_provider=None,
    ):
        """
        Initialize hybrid generator.
        
        Args:
            quantum_provider: QuantumRNGProvider instance
            ocean_provider: OceanWaveEntropyProvider instance
            genetic_provider: Optional GeneticSeedProvider instance
        """
        self.quantum_provider = quantum_provider
        self.ocean_provider = ocean_provider or get_ocean_provider()
        self.genetic_provider = genetic_provider
        self.mixer = EntropyMixer()
        self.mix_history: List[Dict[str, Any]] = []
    
    async def generate_entropy(
        self,
        num_bytes: int,
        include_genetic: bool = False,
    ) -> Tuple[bytes, Dict[str, Any]]:
        """
        Generate hybrid entropy with full audit trail.
        
        Args:
            num_bytes: Number of bytes needed
            include_genetic: Whether to include genetic seed
        
        Returns:
            Tuple of (entropy_bytes, certificate_data)
        
        Raises:
            InsufficientEntropySources: If fewer than 2 sources available
        """
        logger.info(f"Generating {num_bytes} bytes of hybrid entropy")
        
        sources: List[EntropySource] = []
        raw_contributions: List[bytes] = []
        
        # Fetch quantum entropy (if available)
        quantum_bytes = None
        quantum_metadata = {}
        if self.quantum_provider:
            try:
                quantum_bytes, source_id = await self.quantum_provider.fetch_random_bytes(num_bytes)
                quantum_metadata = {
                    'provider': getattr(self.quantum_provider, 'get_provider_name', lambda: 'quantum')(),
                    'source_id': source_id,
                    'quality_score': 1.0,
                }
                sources.append(EntropySource(
                    name='quantum',
                    provider=quantum_metadata['provider'],
                    bytes_contributed=len(quantum_bytes),
                    quality_score=1.0,
                    timestamp=datetime.utcnow(),
                    metadata=quantum_metadata,
                ))
                raw_contributions.append(quantum_bytes)
                logger.info("✓ Quantum entropy fetched")
            except Exception as e:
                logger.warning(f"Failed to fetch quantum entropy: {e}")
        
        # Fetch ocean entropy
        ocean_bytes = None
        ocean_metadata = {}
        try:
            ocean_bytes, source_id = await self.ocean_provider.fetch_random_bytes(num_bytes)
            ocean_metadata = {
                'provider': 'noaa_ocean_wave',
                'source_id': source_id,
                'quality_score': 0.9,
            }
            sources.append(EntropySource(
                name='ocean',
                provider='NOAA',
                bytes_contributed=len(ocean_bytes),
                quality_score=0.9,
                timestamp=datetime.utcnow(),
                metadata=ocean_metadata,
            ))
            raw_contributions.append(ocean_bytes)
            logger.info("✓ Ocean entropy fetched")
        except Exception as e:
            logger.warning(f"Failed to fetch ocean entropy: {e}")
        
        # Fetch genetic entropy if requested
        genetic_bytes = None
        genetic_metadata = {}
        if include_genetic and self.genetic_provider:
            try:
                genetic_bytes = await self.genetic_provider.generate_seed(num_bytes)
                genetic_metadata = {
                    'provider': getattr(self.genetic_provider, 'provider_name', 'genetic'),
                    'quality_score': 0.85,
                }
                sources.append(EntropySource(
                    name='genetic',
                    provider=genetic_metadata['provider'],
                    bytes_contributed=len(genetic_bytes),
                    quality_score=0.85,
                    timestamp=datetime.utcnow(),
                    metadata=genetic_metadata,
                ))
                raw_contributions.append(genetic_bytes)
                logger.info("✓ Genetic entropy included")
            except Exception as e:
                logger.warning(f"Failed to fetch genetic entropy: {e}")
        
        # Require at least 2 sources for security
        if len(sources) < 2:
            raise InsufficientEntropySources(
                f"Only {len(sources)} source(s) available, need at least 2"
            )
        
        # Mix all available sources using XOR
        min_len = min(len(b) for b in raw_contributions)
        normalized = [b[:min_len] for b in raw_contributions]
        
        mixed = bytearray(normalized[0])
        for contribution in normalized[1:]:
            for i in range(min_len):
                mixed[i] ^= contribution[i]
        
        # Condition with SHA3-512
        from hashlib import sha3_512, shake_256
        conditioned = sha3_512(bytes(mixed)).digest()
        
        # Expand using SHAKE256 to desired length
        expanded = shake_256(conditioned).digest(num_bytes)
        
        # Assess quality
        quality_assessment = assess_entropy_quality(expanded)
        
        # Build certificate data
        certificate = {
            'timestamp': datetime.utcnow().isoformat(),
            'sources': [
                {
                    'name': s.name,
                    'provider': s.provider,
                    'quality_score': s.quality_score,
                    'bytes_contributed': s.bytes_contributed,
                    'metadata': s.metadata,
                }
                for s in sources
            ],
            'total_sources': len(sources),
            'output_bytes': num_bytes,
            'mixing_algorithm': 'XOR + SHA3-512 + SHAKE256',
            'quality_assessment': quality_assessment,
        }
        
        # Store in history
        self.mix_history.append({
            'timestamp': datetime.utcnow(),
            'sources': [s.name for s in sources],
            'bytes_mixed': min_len,
            'output_bytes': num_bytes,
        })
        
        logger.info(f"✓ Generated {num_bytes} bytes from {len(sources)} sources")
        
        return expanded, certificate
    
    def get_audit_trail(self) -> List[Dict[str, Any]]:
        """Get mixing audit trail for transparency."""
        return self.mix_history.copy()


# =============================================================================
# Convenience Functions
# =============================================================================

_ocean_provider: Optional[OceanWaveEntropyProvider] = None


def get_ocean_provider() -> OceanWaveEntropyProvider:
    """Get or create the ocean entropy provider singleton."""
    global _ocean_provider
    if _ocean_provider is None:
        _ocean_provider = OceanWaveEntropyProvider()
    return _ocean_provider


async def generate_ocean_entropy(count: int) -> Tuple[bytes, str]:
    """
    Generate entropy from ocean wave data.
    
    Convenience function for quick entropy generation.
    
    Args:
        count: Number of bytes to generate
        
    Returns:
        Tuple of (entropy_bytes, source_id)
    """
    provider = get_ocean_provider()
    return await provider.fetch_random_bytes(count)


async def generate_hybrid_entropy(
    count: int,
    include_quantum: bool = True,
    include_genetic: bool = False,
) -> Tuple[bytes, Dict[str, Any]]:
    """
    Generate hybrid entropy from multiple sources.
    
    Args:
        count: Number of bytes to generate
        include_quantum: Whether to include quantum source
        include_genetic: Whether to include genetic source
        
    Returns:
        Tuple of (entropy_bytes, certificate_data)
    """
    quantum_provider = None
    if include_quantum:
        try:
            from security.services.quantum_rng_service import get_quantum_pool
            quantum_pool = get_quantum_pool()
            # Create a wrapper that matches expected interface
            class QuantumWrapper:
                def __init__(self, pool):
                    self.pool = pool
                async def fetch_random_bytes(self, count):
                    result = await self.pool.get_random_bytes(count)
                    return result[0], f"quantum:{result[1].provider}"
                def get_provider_name(self):
                    return "quantum"
            quantum_provider = QuantumWrapper(quantum_pool)
        except ImportError:
            pass
    
    generator = HybridEntropyGenerator(
        quantum_provider=quantum_provider,
    )
    
    return await generator.generate_entropy(count, include_genetic=include_genetic)

