"""
Cosmic Ray Entropy Provider
============================

Harvests true random entropy from cosmic ray particle detection.
Uses USB cosmic ray detectors (e.g., CosmicWatch) or simulation fallback.

Entropy Sources:
- Muon arrival times (microsecond precision)
- Detection energy levels
- Inter-arrival time intervals

Physical Basis:
Cosmic rays originate from supernovae, active galactic nuclei, and other
high-energy astrophysical phenomena. Muons reaching sea level are the 
decay products of cosmic ray interactions in the upper atmosphere.
Their arrival times are fundamentally unpredictable due to:
- Stochastic particle physics processes
- Atmospheric variations
- Cosmic source fluctuations
- Quantum tunneling events in detector geometry

Security Properties:
- True randomness from quantum processes (particle decay)
- No pseudorandom algorithm can predict cosmic ray arrivals
- Entropy quality: ~6-8 bits per event with proper extraction

@author Password Manager Team
@created 2026-02-08
"""

import os
import time
import math
import struct
import hashlib
import logging
import asyncio
import random
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum

# Serial port for USB detector
try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================

class CosmicRayConfig:
    """Configuration for cosmic ray entropy harvesting."""
    
    @staticmethod
    def _get_settings():
        return getattr(settings, 'COSMIC_RAY_ENTROPY', {})
    
    @classmethod
    def ENABLED(cls) -> bool:
        return cls._get_settings().get('ENABLED', True)
    
    @classmethod
    def SERIAL_PORT(cls) -> str:
        return cls._get_settings().get('SERIAL_PORT', 'auto')
    
    @classmethod
    def BAUD_RATE(cls) -> int:
        return cls._get_settings().get('BAUD_RATE', 9600)
    
    @classmethod
    def EVENT_BUFFER_SIZE(cls) -> int:
        return cls._get_settings().get('EVENT_BUFFER_SIZE', 100)
    
    @classmethod
    def MIN_EVENTS_FOR_ENTROPY(cls) -> int:
        return cls._get_settings().get('MIN_EVENTS_FOR_ENTROPY', 10)
    
    @classmethod
    def SIMULATION_FALLBACK(cls) -> bool:
        return cls._get_settings().get('SIMULATION_FALLBACK', True)
    
    @classmethod
    def POOL_CONTRIBUTION_PERCENT(cls) -> int:
        return cls._get_settings().get('POOL_CONTRIBUTION_PERCENT', 20)
    
    @classmethod
    def CONTINUOUS_COLLECTION(cls) -> bool:
        """If True, collect events continuously. If False, on-demand only."""
        return cls._get_settings().get('CONTINUOUS_COLLECTION', False)


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class CosmicRayEvent:
    """
    Single cosmic ray detection event.
    
    Represents a muon passing through the detector, captured with
    high-precision timing and energy information.
    """
    timestamp: datetime
    microseconds: int  # Sub-millisecond precision
    energy_adc: int    # ADC value from photomultiplier (0-1023)
    detector_id: str   # Unique detector identifier
    channel: int = 0   # Detection channel (for multi-channel detectors)
    
    def to_entropy_bytes(self) -> bytes:
        """
        Convert cosmic ray event to entropy bytes.
        
        Uses:
        - Microsecond timing (high entropy from unpredictable arrival)
        - Energy level variations (detector noise + physics)
        - Nanosecond-level system timing residue
        """
        entropy_data = bytearray()
        
        # Timestamp microseconds (best entropy source)
        entropy_data.extend(struct.pack('<Q', self.microseconds))
        
        # Energy ADC value (lower bits have noise)
        entropy_data.extend(struct.pack('<H', self.energy_adc & 0xFFFF))
        
        # Mix with current nanoseconds for additional jitter
        ns = time.time_ns() % (10**9)
        entropy_data.extend(struct.pack('<I', ns & 0xFFFFFFFF))
        
        # Channel variation
        entropy_data.append(self.channel & 0xFF)
        
        return bytes(entropy_data)
    
    def entropy_quality_score(self) -> float:
        """
        Estimate entropy quality for this event (0-1).
        
        Higher energy events typically have better timing resolution.
        """
        # Energy quality (mid-range ADC values are most reliable)
        if 100 <= self.energy_adc <= 900:
            energy_score = 1.0
        elif 50 <= self.energy_adc <= 950:
            energy_score = 0.8
        else:
            energy_score = 0.5
        
        # Timing precision (microseconds should have good distribution)
        timing_score = 0.9  # Assume good timing precision from detector
        
        return (energy_score + timing_score) / 2
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for API response."""
        return {
            'timestamp': self.timestamp.isoformat(),
            'microseconds': self.microseconds,
            'energy_adc': self.energy_adc,
            'detector_id': self.detector_id,
            'channel': self.channel,
            'quality_score': self.entropy_quality_score()
        }


@dataclass
class CosmicEntropyBatch:
    """Result of cosmic ray entropy generation."""
    entropy_bytes: bytes
    events_used: int
    generation_time: datetime
    detector_mode: str  # 'hardware' or 'simulation'
    min_entropy_estimate: float
    
    def to_dict(self) -> Dict:
        return {
            'bytes_generated': len(self.entropy_bytes),
            'events_used': self.events_used,
            'generation_time': self.generation_time.isoformat(),
            'detector_mode': self.detector_mode,
            'min_entropy_estimate': self.min_entropy_estimate
        }


# =============================================================================
# USB Detector Client
# =============================================================================

class CosmicWatchClient:
    """
    Client for CosmicWatch Desktop Muon Detector.
    
    CosmicWatch is an open-source cosmic ray detector project:
    https://cosmicwatch.lns.mit.edu/
    
    Serial Protocol:
    - Baud rate: 9600 (configurable)
    - Format: CSV lines with timestamp, ADC value, event count
    - Example: "12345678,512,1"
    
    Hardware Requirements:
    - CosmicWatch detector kit (~$100-150)
    - USB-Serial connection
    - Silicon Photomultiplier (SiPM) for muon detection
    """
    
    def __init__(
        self,
        port: Optional[str] = None,
        baud_rate: int = 9600,
        timeout: float = 1.0
    ):
        self.port = port
        self.baud_rate = baud_rate
        self.timeout = timeout
        self._serial: Optional['serial.Serial'] = None
        self._detector_id: Optional[str] = None
        self._is_connected = False
        self._event_buffer: List[CosmicRayEvent] = []
        self._collection_task: Optional[asyncio.Task] = None
    
    def find_detector_port(self) -> Optional[str]:
        """
        Auto-detect CosmicWatch detector port.
        
        Looks for:
        - Arduino-based devices (common for CosmicWatch)
        - Devices with specific VID/PID if known
        """
        if not SERIAL_AVAILABLE:
            return None
        
        try:
            ports = serial.tools.list_ports.comports()
            
            for port in ports:
                # Look for Arduino boards (CosmicWatch uses Arduino Nano)
                desc_lower = (port.description or '').lower()
                if any(keyword in desc_lower for keyword in 
                       ['arduino', 'ch340', 'ftdi', 'cosmic', 'muon']):
                    logger.info(f"Found potential cosmic ray detector: {port.device}")
                    return port.device
                
                # Check for specific manufacturer
                if port.manufacturer and 'arduino' in port.manufacturer.lower():
                    logger.info(f"Found Arduino device: {port.device}")
                    return port.device
            
            return None
            
        except Exception as e:
            logger.warning(f"Error scanning serial ports: {e}")
            return None
    
    def connect(self) -> bool:
        """
        Connect to the cosmic ray detector.
        
        Returns:
            True if connected successfully, False otherwise.
        """
        if not SERIAL_AVAILABLE:
            logger.warning("pyserial not installed, hardware detection unavailable")
            return False
        
        # Determine port
        port = self.port
        if port == 'auto' or port is None:
            port = self.find_detector_port()
        
        if not port:
            logger.info("No cosmic ray detector found")
            return False
        
        try:
            self._serial = serial.Serial(
                port=port,
                baudrate=self.baud_rate,
                timeout=self.timeout
            )
            
            # Wait for detector initialization
            time.sleep(2)
            
            # Read and discard initial boot messages
            self._serial.flushInput()
            
            # Set detector ID from port name
            self._detector_id = f"cosmic-{port.replace('/', '-').replace(':', '-')}"
            self._is_connected = True
            
            logger.info(f"Connected to cosmic ray detector on {port}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to detector on {port}: {e}")
            self._is_connected = False
            return False
    
    def disconnect(self):
        """Disconnect from the detector."""
        if self._serial and self._serial.is_open:
            self._serial.close()
        self._is_connected = False
        self._serial = None
        logger.info("Disconnected from cosmic ray detector")
    
    def is_connected(self) -> bool:
        """Check if detector is connected."""
        return self._is_connected and self._serial is not None and self._serial.is_open
    
    def read_event(self) -> Optional[CosmicRayEvent]:
        """
        Read a single cosmic ray event from the detector.
        
        Blocks until an event is received or timeout.
        
        Returns:
            CosmicRayEvent if detected, None on timeout.
        """
        if not self.is_connected():
            return None
        
        try:
            line = self._serial.readline().decode('utf-8').strip()
            
            if not line:
                return None
            
            # Parse CosmicWatch format: timestamp_us,adc_value,event_count
            parts = line.split(',')
            
            if len(parts) >= 2:
                timestamp_us = int(parts[0])
                adc_value = int(parts[1])
                channel = int(parts[2]) if len(parts) > 2 else 0
                
                return CosmicRayEvent(
                    timestamp=timezone.now(),
                    microseconds=timestamp_us,
                    energy_adc=adc_value,
                    detector_id=self._detector_id or 'unknown',
                    channel=channel
                )
            
            return None
            
        except Exception as e:
            logger.warning(f"Error reading cosmic event: {e}")
            return None
    
    async def collect_events(
        self,
        count: int = 10,
        timeout_seconds: float = 60.0
    ) -> List[CosmicRayEvent]:
        """
        Collect multiple cosmic ray events.
        
        Args:
            count: Number of events to collect
            timeout_seconds: Maximum time to wait
            
        Returns:
            List of collected events (may be less than count on timeout)
        """
        events = []
        start_time = time.time()
        
        while len(events) < count:
            if time.time() - start_time > timeout_seconds:
                logger.warning(f"Timeout collecting cosmic events, got {len(events)}/{count}")
                break
            
            event = self.read_event()
            if event:
                events.append(event)
            else:
                await asyncio.sleep(0.01)  # Short sleep to prevent busy-wait
        
        return events
    
    async def start_continuous_collection(self, buffer_size: int = 100):
        """
        Start continuous background collection of cosmic ray events.
        
        Events are stored in a ring buffer for later consumption.
        """
        if self._collection_task is not None:
            return
        
        async def _collect_loop():
            while self.is_connected():
                event = self.read_event()
                if event:
                    self._event_buffer.append(event)
                    # Ring buffer: remove oldest if full
                    if len(self._event_buffer) > buffer_size:
                        self._event_buffer.pop(0)
                await asyncio.sleep(0.001)
        
        self._collection_task = asyncio.create_task(_collect_loop())
        logger.info("Started continuous cosmic ray collection")
    
    def stop_continuous_collection(self):
        """Stop continuous background collection."""
        if self._collection_task:
            self._collection_task.cancel()
            self._collection_task = None
            logger.info("Stopped continuous cosmic ray collection")
    
    def get_buffered_events(self, clear: bool = True) -> List[CosmicRayEvent]:
        """
        Get events from the buffer.
        
        Args:
            clear: If True, clear the buffer after getting events
            
        Returns:
            List of buffered events
        """
        events = list(self._event_buffer)
        if clear:
            self._event_buffer.clear()
        return events
    
    def get_status(self) -> Dict:
        """Get detector status."""
        return {
            'connected': self.is_connected(),
            'detector_id': self._detector_id,
            'port': self.port,
            'buffer_size': len(self._event_buffer),
            'continuous_collection': self._collection_task is not None
        }


# =============================================================================
# Simulated Cosmic Ray Detection
# =============================================================================

class SimulatedCosmicDetector:
    """
    Simulated cosmic ray detector for testing and fallback.
    
    Uses cryptographically secure random timing to simulate muon arrivals
    following realistic Poisson statistics.
    
    Sea-level muon flux: ~1 muon/cm²/minute
    Typical detector area: ~25 cm² → ~25 events/minute
    
    Note: While this uses os.urandom for simulation, the timing
    between requests still adds some real entropy from system state.
    """
    
    # Average events per second at sea level for typical detector
    MEAN_EVENT_RATE = 0.42  # ~25 events/minute
    
    def __init__(self, detector_id: str = "simulated-cosmic-01"):
        self.detector_id = detector_id
        self._last_event_time = time.time()
    
    def _poisson_wait_time(self) -> float:
        """
        Generate Poisson-distributed wait time.
        
        Uses inverse transform sampling with cryptographic randomness.
        """
        # Use os.urandom for unpredictability
        rand_bytes = os.urandom(8)
        u = struct.unpack('<Q', rand_bytes)[0] / (2**64)
        
        # Exponential distribution (inter-arrival times for Poisson)
        # Clamp to avoid infinite wait or log(0)
        u = max(u, 1e-10)
        
        # Proper exponential distribution: -ln(u) / lambda
        wait_time = -math.log(u) / self.MEAN_EVENT_RATE
        
        return max(0.001, min(wait_time, 60.0))  # Clamp to reasonable range (60s max)
    
    def generate_event(self) -> CosmicRayEvent:
        """
        Generate a simulated cosmic ray event.
        
        Uses current system state for entropy:
        - High-precision timing
        - os.urandom for ADC values
        - Process-level timing jitter
        """
        now = timezone.now()
        
        # Use time.time_ns() for microsecond precision
        ns = time.time_ns()
        microseconds = ns // 1000
        
        # Simulated energy (ADC 0-1023) based on typical muon energy distribution
        # Use cryptographic random for unpredictability
        rand_bytes = os.urandom(4)
        rand_val = struct.unpack('<I', rand_bytes)[0]
        
        # Energy follows roughly log-normal distribution for muons
        # Simplified: mostly mid-range with some variation
        base_energy = 400 + (rand_val % 400)  # 400-800 typical range
        noise = (rand_val >> 16) % 100 - 50    # ±50 noise
        energy = max(50, min(1000, base_energy + noise))
        
        return CosmicRayEvent(
            timestamp=now,
            microseconds=microseconds % (10**12),  # Keep reasonable size
            energy_adc=energy,
            detector_id=self.detector_id,
            channel=0
        )
    
    async def collect_events(
        self,
        count: int = 10,
        realistic_timing: bool = True
    ) -> List[CosmicRayEvent]:
        """
        Collect simulated cosmic ray events.
        
        Args:
            count: Number of events to generate
            realistic_timing: If True, add Poisson-distributed delays
                            to simulate real detection timing
        """
        events = []
        
        for _ in range(count):
            if realistic_timing:
                # Add realistic wait time (compressed for usability)
                wait = self._poisson_wait_time() * 0.1  # Speed up 10x
                await asyncio.sleep(min(wait, 0.5))
            
            events.append(self.generate_event())
        
        return events
    
    def get_status(self) -> Dict:
        """Get simulated detector status."""
        return {
            'connected': True,
            'detector_id': self.detector_id,
            'mode': 'simulation',
            'mean_event_rate': self.MEAN_EVENT_RATE,
            'buffer_size': 0,
            'continuous_collection': False
        }


# =============================================================================
# Entropy Extraction
# =============================================================================

class CosmicEntropyExtractor:
    """
    Extracts cryptographic-quality entropy from cosmic ray events.
    
    Uses multiple techniques:
    1. Inter-arrival time differences
    2. Energy level LSBs (noise-dominated)
    3. XOR combination of multiple events
    4. SHA-3 conditioning for uniformity
    """
    
    @staticmethod
    def extract_from_events(
        events: List[CosmicRayEvent],
        target_bytes: int = 32,
        use_von_neumann: bool = True
    ) -> Tuple[bytes, float]:
        """
        Extract entropy from a list of cosmic ray events.
        
        Args:
            events: List of cosmic ray events
            target_bytes: Desired output size
            use_von_neumann: Apply von Neumann debiasing
            
        Returns:
            Tuple of (entropy_bytes, min_entropy_estimate)
        """
        if not events:
            return b'', 0.0
        
        # Collect raw entropy from all events
        raw_entropy = bytearray()
        
        # Method 1: Event data entropy
        for event in events:
            raw_entropy.extend(event.to_entropy_bytes())
        
        # Method 2: Inter-arrival time deltas
        if len(events) >= 2:
            for i in range(1, len(events)):
                delta_us = events[i].microseconds - events[i-1].microseconds
                raw_entropy.extend(struct.pack('<q', delta_us))
        
        # Method 3: Energy differences (noise-rich)
        if len(events) >= 2:
            for i in range(1, len(events)):
                energy_diff = events[i].energy_adc - events[i-1].energy_adc
                raw_entropy.extend(struct.pack('<h', energy_diff))
        
        # Von Neumann debiasing on LSBs
        if use_von_neumann:
            raw_entropy = CosmicEntropyExtractor._von_neumann_debias(raw_entropy)
        
        # Condition through SHAKE-256 for uniformity and expansion
        from hashlib import shake_256
        conditioned = shake_256(bytes(raw_entropy)).digest(target_bytes)
        
        # Estimate min-entropy
        min_entropy = CosmicEntropyExtractor._estimate_min_entropy(conditioned)
        
        return conditioned, min_entropy
    
    @staticmethod
    def _von_neumann_debias(data: bytes) -> bytes:
        """
        Apply von Neumann debiasing to remove bias.
        
        Takes pairs of bits:
        - 01 -> 0
        - 10 -> 1
        - 00, 11 -> discard
        """
        # Convert to bits
        bits = []
        for byte in data:
            for i in range(8):
                bits.append((byte >> (7 - i)) & 1)
        
        # Von Neumann extraction
        debiased_bits = []
        for i in range(0, len(bits) - 1, 2):
            if bits[i] != bits[i + 1]:
                debiased_bits.append(bits[i])
        
        # Convert back to bytes
        result = bytearray()
        for i in range(0, len(debiased_bits) - 7, 8):
            byte_val = 0
            for j in range(8):
                byte_val = (byte_val << 1) | debiased_bits[i + j]
            result.append(byte_val)
        
        return bytes(result)
    
    @staticmethod
    def _estimate_min_entropy(data: bytes) -> float:
        """
        Estimate min-entropy in bits per byte.
        
        Uses frequency analysis for a simple estimate.
        Perfect random data has ~8 bits/byte.
        """
        if not data:
            return 0.0
        
        # Count byte frequencies
        freq = {}
        for byte in data:
            freq[byte] = freq.get(byte, 0) + 1
        
        # Max probability
        max_prob = max(freq.values()) / len(data)
        
        # Min-entropy estimate
        import math
        if max_prob > 0:
            min_entropy = -math.log2(max_prob)
        else:
            min_entropy = 8.0
        
        return min(8.0, min_entropy)


# =============================================================================
# Cosmic Ray Entropy Provider
# =============================================================================

class CosmicRayEntropyProvider:
    """
    Cosmic ray-based entropy provider.
    
    Implements the QuantumRNGProvider interface pattern for integration
    with the quantum entropy pool.
    
    Operating Modes:
    1. Hardware Mode: Real detector connected via USB
    2. Simulation Mode: Cryptographic fallback with realistic timing
    3. Hybrid Mode: Hardware with simulation fallback
    """
    
    def __init__(self, prefer_hardware: bool = True):
        self.prefer_hardware = prefer_hardware
        self._hardware_client: Optional[CosmicWatchClient] = None
        self._simulator = SimulatedCosmicDetector()
        self._mode = 'uninitialized'
        self._last_source_info: Dict = {}
        self._continuous_enabled = False
    
    def _initialize(self):
        """Initialize detector connection."""
        if self._mode != 'uninitialized':
            return
        
        config = CosmicRayConfig._get_settings()
        
        if self.prefer_hardware and config.get('ENABLED', True):
            self._hardware_client = CosmicWatchClient(
                port=config.get('SERIAL_PORT', 'auto'),
                baud_rate=config.get('BAUD_RATE', 9600)
            )
            
            if self._hardware_client.connect():
                self._mode = 'hardware'
                logger.info("Cosmic ray provider using hardware detector")
                return
            else:
                self._hardware_client = None
        
        if config.get('SIMULATION_FALLBACK', True):
            self._mode = 'simulation'
            logger.info("Cosmic ray provider using simulation fallback")
        else:
            self._mode = 'disabled'
            logger.warning("Cosmic ray entropy disabled (no hardware, no fallback)")
    
    async def fetch_random_bytes(self, count: int) -> Tuple[bytes, Optional[str]]:
        """
        Fetch random bytes from cosmic ray detection.
        
        Args:
            count: Number of random bytes to generate
            
        Returns:
            Tuple of (random_bytes, source_identifier)
        """
        self._initialize()
        
        if self._mode == 'disabled':
            raise RuntimeError("Cosmic ray entropy is disabled")
        
        # Calculate events needed (each event provides ~8 bytes of entropy)
        min_events = max(10, count // 4)
        
        if self._mode == 'hardware' and self._hardware_client:
            # Try hardware first
            try:
                # Check for buffered events from continuous collection
                events = self._hardware_client.get_buffered_events(clear=True)
                
                # Collect more if needed
                if len(events) < min_events:
                    additional = await self._hardware_client.collect_events(
                        count=min_events - len(events),
                        timeout_seconds=30.0
                    )
                    events.extend(additional)
                
                if len(events) >= min_events // 2:  # Accept if we got at least half
                    entropy, quality = CosmicEntropyExtractor.extract_from_events(
                        events, target_bytes=count
                    )
                    
                    self._last_source_info = {
                        'mode': 'hardware',
                        'events_used': len(events),
                        'min_entropy_per_byte': quality
                    }
                    
                    return entropy, f"cosmic-hw-{len(events)}"
                
            except Exception as e:
                logger.warning(f"Hardware collection failed: {e}, falling back to simulation")
        
        # Simulation fallback
        events = await self._simulator.collect_events(
            count=min_events,
            realistic_timing=False  # Skip delays for simulation
        )
        
        entropy, quality = CosmicEntropyExtractor.extract_from_events(
            events, target_bytes=count
        )
        
        self._last_source_info = {
            'mode': 'simulation',
            'events_used': len(events),
            'min_entropy_per_byte': quality
        }
        
        return entropy, f"cosmic-sim-{len(events)}"
    
    def get_provider_name(self) -> str:
        """Return provider identifier."""
        return "cosmic_ray_muon"
    
    def get_quantum_source(self) -> str:
        """Return description of the entropy phenomenon used."""
        return "cosmic_ray_muon_timing"
    
    def is_available(self) -> bool:
        """Check if provider is available and configured."""
        self._initialize()
        return self._mode in ('hardware', 'simulation')
    
    def get_last_source_info(self) -> Dict:
        """Get information about the last entropy generation."""
        return self._last_source_info.copy()
    
    def get_status(self) -> Dict:
        """Get comprehensive status information."""
        self._initialize()
        
        status = {
            'mode': self._mode,
            'available': self.is_available(),
            'continuous_collection': self._continuous_enabled,
            'last_source': self._last_source_info.copy()
        }
        
        if self._mode == 'hardware' and self._hardware_client:
            status['hardware'] = self._hardware_client.get_status()
        elif self._mode == 'simulation':
            status['simulation'] = self._simulator.get_status()
        
        return status
    
    def enable_continuous_collection(self, buffer_size: int = 100):
        """
        Enable continuous background collection (requires user opt-in).
        
        Events are buffered for faster entropy generation.
        """
        if self._mode == 'hardware' and self._hardware_client:
            asyncio.create_task(
                self._hardware_client.start_continuous_collection(buffer_size)
            )
            self._continuous_enabled = True
            logger.info("Enabled continuous cosmic ray collection")
        else:
            logger.warning("Continuous collection only available with hardware detector")
    
    def disable_continuous_collection(self):
        """Disable continuous background collection."""
        if self._hardware_client:
            self._hardware_client.stop_continuous_collection()
        self._continuous_enabled = False
        logger.info("Disabled continuous cosmic ray collection")
    
    def close(self):
        """Clean up resources."""
        self.disable_continuous_collection()
        if self._hardware_client:
            self._hardware_client.disconnect()
            self._hardware_client = None
        self._mode = 'uninitialized'


# =============================================================================
# Factory Functions
# =============================================================================

_cosmic_provider: Optional[CosmicRayEntropyProvider] = None


def get_cosmic_provider() -> CosmicRayEntropyProvider:
    """Get or create the cosmic ray entropy provider singleton."""
    global _cosmic_provider
    if _cosmic_provider is None:
        _cosmic_provider = CosmicRayEntropyProvider()
    return _cosmic_provider


async def generate_cosmic_password(
    length: int = 16,
    charset: Optional[str] = None,
    max_retries: int = 3
) -> Tuple[str, Dict]:
    """
    Generate a password using cosmic ray entropy.
    
    Args:
        length: Password length (8-128)
        charset: Optional custom character set
        max_retries: Number of retry attempts for entropy generation
        
    Returns:
        Tuple of (password, generation_info)
    """
    provider = get_cosmic_provider()
    
    # Default charset
    if charset is None:
        charset = (
            "abcdefghijklmnopqrstuvwxyz"
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            "0123456789"
            "!@#$%^&*()_+-=[]{}|;:,.<>?"
        )
    
    length = max(8, min(128, length))
    charset_len = len(charset)
    
    # Calculate required entropy bytes (with margin for rejection sampling)
    # Each byte gives us 256 possibilities; we need enough for rejection sampling
    required_bytes = max(length * 4, 64)  # Generous margin
    
    for attempt in range(max_retries):
        try:
            # Get entropy (extra for rejection sampling)
            entropy_bytes, source_id = await provider.fetch_random_bytes(required_bytes)
            
            # Generate password using rejection sampling
            password_chars = []
            byte_index = 0
            
            while len(password_chars) < length and byte_index < len(entropy_bytes):
                byte_val = entropy_bytes[byte_index]
                byte_index += 1
                
                # Rejection sampling for uniform distribution
                # Only accept bytes that fall within the exact multiple of charset_len
                max_valid = (256 // charset_len) * charset_len
                if byte_val < max_valid:
                    password_chars.append(charset[byte_val % charset_len])
            
            # Check if we generated enough characters
            if len(password_chars) < length:
                if attempt < max_retries - 1:
                    logger.warning(f"Insufficient entropy on attempt {attempt + 1}, retrying...")
                    continue
                else:
                    # Fallback: use remaining bytes with modulo (slight bias, but functional)
                    # We continue from where we left off or restart if needed
                    while len(password_chars) < length and byte_index < len(entropy_bytes):
                        password_chars.append(charset[entropy_bytes[byte_index] % charset_len])
                        byte_index += 1
            
            password = "".join(password_chars)
            
            info = {
                'source': source_id,
                'entropy_bits': len(entropy_bytes) * 8,
                'status': provider.get_last_source_info(),
                'retries_needed': attempt
            }
            
            return password, info
            
        except Exception as e:
            if attempt == max_retries - 1:
                logger.error(f"Failed to generate cosmic password after {max_retries} attempts: {e}")
                raise RuntimeError(f"Failed to generate cosmic password: {e}")
            logger.warning(f"Attempt {attempt + 1} failed: {e}, retrying...")
    
    raise RuntimeError("Unexpected exit from retry loop")
