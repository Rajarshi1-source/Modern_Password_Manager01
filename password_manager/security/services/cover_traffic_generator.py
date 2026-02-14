"""
Cover Traffic Generator
=======================

Generates cover traffic to mask real vault operations.

Features:
- Constant-rate traffic generation
- Mimics user behavior patterns
- Indistinguishable from real vault operations
- Adaptive intensity based on user preferences

@author Password Manager Team
@created 2026-02-02
"""

import os
import json
import secrets
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, TYPE_CHECKING
from dataclasses import dataclass, field

if TYPE_CHECKING:
    from ..models.dark_protocol_models import CoverTrafficPattern

from django.utils import timezone
from django.conf import settings

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

# Operation types that cover traffic can mimic
FAKE_OPERATIONS = [
    'vault_list',
    'vault_get',
    'vault_search',
    'vault_sync',
    'vault_metadata',
    'security_check',
    'heartbeat',
]

# Payload size ranges for different operation types
PAYLOAD_SIZES = {
    'vault_list': (256, 2048),
    'vault_get': (128, 1024),
    'vault_search': (64, 512),
    'vault_sync': (512, 4096),
    'vault_metadata': (64, 256),
    'security_check': (32, 128),
    'heartbeat': (16, 64),
}


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class CoverMessage:
    """A cover traffic message."""
    message_id: str
    operation: str
    payload: bytes
    size: int
    scheduled_at: datetime
    delay_ms: int = 0
    is_sent: bool = False
    sent_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'message_id': self.message_id,
            'operation': self.operation,
            'size': self.size,
            'scheduled_at': self.scheduled_at.isoformat(),
            'is_sent': self.is_sent,
        }


@dataclass
class TrafficBurst:
    """A burst of cover traffic messages."""
    burst_id: str
    messages: List[CoverMessage]
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def total_size(self) -> int:
        return sum(m.size for m in self.messages)
    
    @property
    def message_count(self) -> int:
        return len(self.messages)


# =============================================================================
# Cover Traffic Generator
# =============================================================================

class CoverTrafficGenerator:
    """
    Generates cover traffic that is indistinguishable from real operations.
    
    Goals:
    - Maintain constant traffic rate regardless of real activity
    - Mimic realistic user behavior patterns
    - Vary message sizes to match real operations
    - Adapt to user's configured intensity
    """
    
    def __init__(self):
        self._noise_encryptor = None
        self._garlic_router = None
    
    @property
    def noise_encryptor(self):
        """Lazy load noise encryptor."""
        if self._noise_encryptor is None:
            from .noise_encryptor import NoiseEncryptor
            self._noise_encryptor = NoiseEncryptor()
        return self._noise_encryptor
    
    @property
    def garlic_router(self):
        """Lazy load garlic router."""
        if self._garlic_router is None:
            from .garlic_router import GarlicRouter
            self._garlic_router = GarlicRouter()
        return self._garlic_router
    
    # =========================================================================
    # Message Generation
    # =========================================================================
    
    def generate_cover_message(
        self,
        operation: str = None,
        size: int = None,
    ) -> CoverMessage:
        """
        Generate a single cover traffic message.
        
        Args:
            operation: Specific operation to mimic (random if not specified)
            size: Message size (random in operation range if not specified)
            
        Returns:
            CoverMessage ready for transmission
        """
        # Select operation if not specified
        if operation is None:
            operation = secrets.choice(FAKE_OPERATIONS)
        
        # Determine size
        if size is None:
            min_size, max_size = PAYLOAD_SIZES.get(operation, (64, 512))
            size = secrets.randbelow(max_size - min_size) + min_size
        
        # Generate realistic-looking payload
        payload = self._generate_fake_payload(operation, size)
        
        # Calculate timing
        delay_ms = self.noise_encryptor.generate_timing_noise()
        
        return CoverMessage(
            message_id=secrets.token_hex(16),
            operation=operation,
            payload=payload,
            size=len(payload),
            scheduled_at=timezone.now() + timedelta(milliseconds=delay_ms),
            delay_ms=delay_ms,
        )
    
    def _generate_fake_payload(self, operation: str, size: int) -> bytes:
        """
        Generate a fake payload that looks like a real operation.
        
        The payload is structured to be indistinguishable from
        real vault operations when encrypted.
        """
        # Create a realistic-looking structure
        fake_data = {
            'op': operation,
            'ts': timezone.now().timestamp(),
            'rid': secrets.token_hex(8),
            'data': {},
        }
        
        # Add operation-specific fake data
        if operation == 'vault_list':
            fake_data['data'] = {
                'page': secrets.randbelow(10) + 1,
                'limit': 20,
                'filters': {},
            }
        elif operation == 'vault_get':
            fake_data['data'] = {
                'item_id': secrets.token_hex(16),
            }
        elif operation == 'vault_search':
            fake_data['data'] = {
                'query': secrets.token_hex(8),
                'limit': 10,
            }
        elif operation == 'vault_sync':
            fake_data['data'] = {
                'last_sync': (timezone.now() - timedelta(hours=1)).isoformat(),
                'device_id': secrets.token_hex(8),
            }
        elif operation == 'vault_metadata':
            fake_data['data'] = {
                'fields': ['updated_at', 'size'],
            }
        elif operation == 'security_check':
            fake_data['data'] = {
                'check_type': 'integrity',
            }
        else:  # heartbeat
            fake_data['data'] = {'ping': True}
        
        # Serialize
        json_bytes = json.dumps(fake_data).encode()
        
        # Pad to target size
        if len(json_bytes) < size:
            padding = os.urandom(size - len(json_bytes))
            return json_bytes + b'\x00' + padding
        elif len(json_bytes) > size:
            return json_bytes[:size]
        
        return json_bytes
    
    # =========================================================================
    # Burst Generation
    # =========================================================================
    
    def generate_burst(
        self,
        count: int = None,
        intensity: float = 0.5,
    ) -> TrafficBurst:
        """
        Generate a burst of cover traffic messages.
        
        Args:
            count: Number of messages (calculated from intensity if not specified)
            intensity: Traffic intensity 0.0-1.0
            
        Returns:
            TrafficBurst with multiple messages
        """
        # Calculate message count based on intensity
        if count is None:
            # Base: 2-10 messages per burst
            min_messages = 2
            max_messages = int(2 + intensity * 8)
            count = secrets.randbelow(max_messages - min_messages + 1) + min_messages
        
        messages = []
        
        # Generate messages with varied operations and sizes
        operation_weights = self._calculate_operation_weights()
        
        for _ in range(count):
            operation = self._weighted_choice(operation_weights)
            message = self.generate_cover_message(operation=operation)
            messages.append(message)
        
        return TrafficBurst(
            burst_id=secrets.token_hex(16),
            messages=messages,
        )
    
    def _calculate_operation_weights(self) -> Dict[str, float]:
        """
        Calculate operation weights for realistic distribution.
        
        Based on typical user behavior patterns.
        """
        return {
            'vault_list': 0.25,      # Most common
            'vault_get': 0.30,       # Very common
            'vault_search': 0.15,
            'vault_sync': 0.10,
            'vault_metadata': 0.10,
            'security_check': 0.05,
            'heartbeat': 0.05,
        }
    
    def _weighted_choice(self, weights: Dict[str, float]) -> str:
        """Select an operation based on weights."""
        import random
        
        total = sum(weights.values())
        r = random.random() * total
        
        cumulative = 0
        for operation, weight in weights.items():
            cumulative += weight
            if r <= cumulative:
                return operation
        
        return list(weights.keys())[0]
    
    # =========================================================================
    # Pattern-Based Generation
    # =========================================================================
    
    def generate_scheduled_traffic(
        self,
        pattern: 'CoverTrafficPattern',  # From models
        duration_minutes: int = 60,
    ) -> List[CoverMessage]:
        """
        Generate cover traffic based on user's pattern configuration.
        
        Args:
            pattern: User's CoverTrafficPattern settings
            duration_minutes: How far ahead to schedule
            
        Returns:
            List of scheduled CoverMessages
        """
        messages = []
        current_time = timezone.now()
        end_time = current_time + timedelta(minutes=duration_minutes)
        
        while current_time < end_time:
            # Get hourly activity level
            hour = current_time.hour
            activity_level = pattern.hourly_pattern.get(str(hour), 0.5)
            
            # Calculate rate based on pattern settings and activity level
            base_rate = (pattern.min_rate_per_minute + pattern.max_rate_per_minute) / 2
            rate = base_rate * activity_level
            
            # Add jitter
            jitter = pattern.jitter_ms / 1000  # Convert to seconds
            interval = 60 / rate if rate > 0 else 60
            interval += (secrets.randbelow(int(jitter * 2000)) - jitter * 1000) / 1000
            interval = max(1, interval)  # At least 1 second between messages
            
            # Create message
            message = self.generate_cover_message()
            message.scheduled_at = current_time
            messages.append(message)
            
            # Advance time
            current_time += timedelta(seconds=interval)
            
            # Handle bursts
            if secrets.random() < pattern.burst_probability:
                burst_count = secrets.randbelow(5) + 2
                for _ in range(burst_count):
                    burst_message = self.generate_cover_message()
                    burst_delay = secrets.randbelow(500)  # 0-500ms
                    burst_message.scheduled_at = current_time + timedelta(milliseconds=burst_delay)
                    messages.append(burst_message)
        
        return messages
    
    def learn_from_real_traffic(
        self,
        user,
        lookback_hours: int = 24,
    ) -> Dict[str, Any]:
        """
        Analyze real traffic to improve cover traffic patterns.
        
        Args:
            user: User whose traffic to analyze
            lookback_hours: How far back to look
            
        Returns:
            Updated pattern parameters
        """
        from ..models.dark_protocol_models import TrafficBundle, CoverTrafficPattern
        
        # Get recent real traffic
        since = timezone.now() - timedelta(hours=lookback_hours)
        real_bundles = TrafficBundle.objects.filter(
            session__user=user,
            bundle_type='real',
            created_at__gte=since,
        ).order_by('created_at')
        
        if not real_bundles.exists():
            return {}
        
        # Calculate statistics
        sizes = [b.payload_size for b in real_bundles]
        timestamps = [b.created_at for b in real_bundles]
        
        # Calculate intervals
        intervals = []
        for i in range(1, len(timestamps)):
            delta = (timestamps[i] - timestamps[i-1]).total_seconds()
            intervals.append(delta)
        
        if not intervals:
            return {}
        
        avg_interval = sum(intervals) / len(intervals)
        rate_per_minute = 60 / avg_interval if avg_interval > 0 else 10
        
        # Calculate size distribution
        avg_size = sum(sizes) / len(sizes)
        min_size = min(sizes)
        max_size = max(sizes)
        
        # Update pattern
        pattern, _ = CoverTrafficPattern.objects.get_or_create(user=user)
        
        # Smooth updates (don't change too drastically)
        pattern.min_rate_per_minute = int((pattern.min_rate_per_minute + rate_per_minute * 0.8) / 2)
        pattern.max_rate_per_minute = int((pattern.max_rate_per_minute + rate_per_minute * 1.2) / 2)
        pattern.typical_message_size = int((pattern.typical_message_size + avg_size) / 2)
        pattern.min_message_size = min(pattern.min_message_size, min_size)
        pattern.max_message_size = max(pattern.max_message_size, max_size)
        pattern.last_pattern_update = timezone.now()
        
        pattern.save()
        
        return {
            'rate_per_minute': rate_per_minute,
            'avg_size': avg_size,
            'samples': len(sizes),
            'updated_at': timezone.now().isoformat(),
        }
    
    # =========================================================================
    # Traffic Mixing
    # =========================================================================
    
    def mix_with_real_traffic(
        self,
        real_messages: List[bytes],
        cover_count: int = None,
    ) -> List[bytes]:
        """
        Mix real messages with cover traffic.
        
        The result is indistinguishable: an observer cannot tell
        which messages are real and which are cover.
        
        Args:
            real_messages: Real operation payloads
            cover_count: Number of cover messages to add
            
        Returns:
            Mixed list of all messages (shuffled)
        """
        if cover_count is None:
            # Add 1-3 cover messages per real message
            cover_count = len(real_messages) * (secrets.randbelow(3) + 1)
        
        all_messages = list(real_messages)
        
        # Generate and add cover messages
        for _ in range(cover_count):
            cover = self.generate_cover_message()
            all_messages.append(cover.payload)
        
        # Shuffle to randomize order
        import random
        random.shuffle(all_messages)
        
        return all_messages
    
    # =========================================================================
    # Intensity Control
    # =========================================================================
    
    def calculate_adaptive_intensity(
        self,
        user,
        current_time: datetime = None,
    ) -> float:
        """
        Calculate adaptive traffic intensity based on context.
        
        Factors:
        - Time of day
        - Recent activity level
        - User preferences
        - Threat level
        """
        from ..models.dark_protocol_models import DarkProtocolConfig, CoverTrafficPattern
        
        if current_time is None:
            current_time = timezone.now()
        
        # Get user config
        try:
            config = DarkProtocolConfig.objects.get(user=user)
            base_intensity = config.cover_traffic_intensity
        except DarkProtocolConfig.DoesNotExist:
            base_intensity = 0.5
        
        # Get hourly pattern
        try:
            pattern = CoverTrafficPattern.objects.get(user=user)
            hour_factor = pattern.hourly_pattern.get(str(current_time.hour), 1.0)
        except CoverTrafficPattern.DoesNotExist:
            hour_factor = 1.0
        
        # Combine factors
        intensity = base_intensity * hour_factor
        
        # Add random variation (±10%)
        variation = (secrets.randbelow(200) - 100) / 1000
        intensity += variation
        
        # Clamp to valid range
        intensity = max(0.1, min(1.0, intensity))
        
        return intensity


# =============================================================================
# Module-level Instance
# =============================================================================

_cover_generator = None


def get_cover_traffic_generator() -> CoverTrafficGenerator:
    """Get cover traffic generator singleton."""
    global _cover_generator
    if _cover_generator is None:
        _cover_generator = CoverTrafficGenerator()
    return _cover_generator
