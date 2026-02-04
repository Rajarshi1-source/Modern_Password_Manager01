"""
Dark Protocol Network Models
=============================

Models for the anonymous vault access network using garlic routing
with cover traffic and censorship resistance.

Models:
- DarkProtocolNode: Registered network nodes (entry, relay, destination)
- GarlicSession: Active encrypted sessions with layered keys
- CoverTrafficPattern: User-specific cover traffic patterns
- RoutingPath: Pre-computed anonymous routing paths
- TrafficBundle: Encrypted traffic bundles (real + cover)
- NetworkHealth: Node health and latency metrics
- DarkProtocolConfig: User-specific configuration

@author Password Manager Team
@created 2026-02-02
"""

import uuid
import secrets
from datetime import timedelta
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator

User = get_user_model()


# =============================================================================
# Constants
# =============================================================================

NODE_TYPE_CHOICES = [
    ('entry', 'Entry Node'),
    ('relay', 'Relay Node'),
    ('destination', 'Destination Node'),
    ('bridge', 'Bridge Node'),  # For censorship circumvention
]

NODE_STATUS_CHOICES = [
    ('active', 'Active'),
    ('inactive', 'Inactive'),
    ('maintenance', 'Maintenance'),
    ('compromised', 'Compromised'),
]

SESSION_STATUS_CHOICES = [
    ('establishing', 'Establishing'),
    ('active', 'Active'),
    ('suspended', 'Suspended'),
    ('terminated', 'Terminated'),
]

BUNDLE_TYPE_CHOICES = [
    ('real', 'Real Operation'),
    ('cover', 'Cover Traffic'),
    ('heartbeat', 'Heartbeat'),
    ('padding', 'Padding'),
]


# =============================================================================
# Dark Protocol Node
# =============================================================================

class DarkProtocolNode(models.Model):
    """
    Represents a node in the dark protocol network.
    
    Nodes can be:
    - Entry nodes: First hop from client
    - Relay nodes: Intermediate hops
    - Destination nodes: Final hop to vault service
    - Bridge nodes: Hidden entry points for censorship circumvention
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Node identification
    node_id = models.CharField(max_length=64, unique=True, db_index=True)
    fingerprint = models.CharField(max_length=128, unique=True)  # Cryptographic fingerprint
    
    # Node type and status
    node_type = models.CharField(max_length=20, choices=NODE_TYPE_CHOICES, default='relay')
    status = models.CharField(max_length=20, choices=NODE_STATUS_CHOICES, default='active')
    
    # Network location (obfuscated for privacy)
    region = models.CharField(max_length=50, blank=True)  # Geographic region (e.g., "EU", "NA")
    onion_address = models.CharField(max_length=128, blank=True)  # .onion style address
    
    # Cryptographic material
    public_key = models.BinaryField()  # Lattice public key for encryption
    signing_key = models.BinaryField()  # For verifying node signatures
    
    # Capacity and performance
    bandwidth_mbps = models.IntegerField(default=100)
    max_circuits = models.IntegerField(default=1000)
    current_circuits = models.IntegerField(default=0)
    
    # Trust and reputation
    trust_score = models.FloatField(
        default=0.5,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)]
    )
    uptime_percentage = models.FloatField(default=100.0)
    
    # Timestamps
    registered_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)
    
    # Owner (for self-hosted nodes)
    owner = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='dark_protocol_nodes'
    )
    
    class Meta:
        ordering = ['-trust_score', '-uptime_percentage']
        indexes = [
            models.Index(fields=['node_type', 'status']),
            models.Index(fields=['region', 'status']),
        ]
    
    def __str__(self):
        return f"{self.node_type.upper()} Node: {self.node_id[:8]}..."
    
    @property
    def is_available(self):
        """Check if node is available for new circuits."""
        return (
            self.status == 'active' and
            self.current_circuits < self.max_circuits and
            self.last_seen_at > timezone.now() - timedelta(minutes=5)
        )
    
    @property
    def load_percentage(self):
        """Current load as percentage of capacity."""
        if self.max_circuits == 0:
            return 100.0
        return (self.current_circuits / self.max_circuits) * 100


# =============================================================================
# Garlic Session
# =============================================================================

class GarlicSession(models.Model):
    """
    Active encrypted session using garlic routing.
    
    Each session has multiple encryption layers (like cloves in garlic),
    with each layer corresponding to a hop in the routing path.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Session identification
    session_id = models.CharField(max_length=64, unique=True, db_index=True)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='dark_protocol_sessions'
    )
    
    # Session status
    status = models.CharField(
        max_length=20,
        choices=SESSION_STATUS_CHOICES,
        default='establishing'
    )
    
    # Routing path (encrypted, stored as JSON list of node IDs)
    encrypted_path = models.BinaryField()  # Encrypted routing path
    path_length = models.IntegerField(default=3)  # Number of hops
    
    # Encryption layers (stored as encrypted key material)
    layer_keys = models.BinaryField()  # Encrypted session keys for each layer
    
    # Entry node (first hop - we know this one)
    entry_node = models.ForeignKey(
        DarkProtocolNode,
        on_delete=models.SET_NULL,
        null=True,
        related_name='entry_sessions'
    )
    
    # Session timing
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField()
    
    # Traffic statistics (for cover traffic calibration)
    bytes_sent = models.BigIntegerField(default=0)
    bytes_received = models.BigIntegerField(default=0)
    messages_sent = models.IntegerField(default=0)
    messages_received = models.IntegerField(default=0)
    
    # Security flags
    is_verified = models.BooleanField(default=False)  # Path verified working
    rotation_pending = models.BooleanField(default=False)  # Path needs rotation
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        return f"Session {self.session_id[:8]}... ({self.status})"
    
    @property
    def is_expired(self):
        return timezone.now() > self.expires_at
    
    @property
    def is_active(self):
        return self.status == 'active' and not self.is_expired
    
    def save(self, *args, **kwargs):
        if not self.expires_at:
            # Default expiry: 30 minutes
            self.expires_at = timezone.now() + timedelta(minutes=30)
        super().save(*args, **kwargs)


# =============================================================================
# Cover Traffic Pattern
# =============================================================================

class CoverTrafficPattern(models.Model):
    """
    User-specific cover traffic patterns to mask real vault operations.
    
    Cover traffic is designed to be statistically indistinguishable
    from real operations, making traffic analysis attacks ineffective.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    user = models.OneToOneField(
        User, on_delete=models.CASCADE,
        related_name='cover_traffic_pattern'
    )
    
    # Traffic rate settings
    min_rate_per_minute = models.IntegerField(default=10)
    max_rate_per_minute = models.IntegerField(default=30)
    burst_probability = models.FloatField(default=0.1)  # Probability of traffic burst
    
    # Timing characteristics
    avg_interval_ms = models.IntegerField(default=2000)  # Average between messages
    jitter_ms = models.IntegerField(default=500)  # Random timing variation
    
    # Message size distribution (to mimic real operations)
    min_message_size = models.IntegerField(default=64)
    max_message_size = models.IntegerField(default=4096)
    typical_message_size = models.IntegerField(default=512)
    
    # Activity patterns (JSON: hour -> relative activity level)
    hourly_pattern = models.JSONField(default=dict)  # 0-23 hour patterns
    
    # Learning settings
    learn_from_real_traffic = models.BooleanField(default=True)
    last_pattern_update = models.DateTimeField(null=True, blank=True)
    
    # Toggle
    is_enabled = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        status = "Enabled" if self.is_enabled else "Disabled"
        return f"Cover Pattern for {self.user.email} ({status})"
    
    @classmethod
    def get_default_hourly_pattern(cls):
        """Generate default hourly activity pattern."""
        # Simulates typical user activity: higher during day, lower at night
        return {
            str(h): 0.3 if 0 <= h < 6 else (0.8 if 6 <= h < 22 else 0.5)
            for h in range(24)
        }
    
    def save(self, *args, **kwargs):
        if not self.hourly_pattern:
            self.hourly_pattern = self.get_default_hourly_pattern()
        super().save(*args, **kwargs)


# =============================================================================
# Routing Path
# =============================================================================

class RoutingPath(models.Model):
    """
    Pre-computed anonymous routing paths through the network.
    
    Paths are rotated regularly to prevent correlation attacks.
    Multiple paths can be active simultaneously for load balancing.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    user = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='routing_paths'
    )
    
    # Path identifier
    path_id = models.CharField(max_length=64, unique=True, db_index=True)
    
    # Encrypted path data (list of node IDs and session keys)
    encrypted_path_data = models.BinaryField()
    
    # Path characteristics
    hop_count = models.IntegerField(default=3)
    estimated_latency_ms = models.IntegerField(default=0)
    
    # Nodes in path (only entry is known; others encrypted)
    entry_node = models.ForeignKey(
        DarkProtocolNode,
        on_delete=models.CASCADE,
        related_name='path_entries'
    )
    
    # Path status
    is_active = models.BooleanField(default=True)
    is_primary = models.BooleanField(default=False)  # Primary path for user
    
    # Validity
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    last_used_at = models.DateTimeField(null=True, blank=True)
    
    # Usage statistics
    times_used = models.IntegerField(default=0)
    failures = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['-is_primary', '-created_at']
        indexes = [
            models.Index(fields=['user', 'is_active']),
        ]
    
    def __str__(self):
        primary = " (Primary)" if self.is_primary else ""
        return f"Path {self.path_id[:8]}...{primary}"
    
    @property
    def is_expired(self):
        return timezone.now() > self.expires_at
    
    @property
    def reliability(self):
        """Calculate path reliability based on usage."""
        total = self.times_used + self.failures
        if total == 0:
            return 1.0
        return self.times_used / total
    
    def save(self, *args, **kwargs):
        if not self.path_id:
            self.path_id = secrets.token_hex(32)
        if not self.expires_at:
            # Default: paths expire after 5 minutes
            self.expires_at = timezone.now() + timedelta(minutes=5)
        super().save(*args, **kwargs)


# =============================================================================
# Traffic Bundle
# =============================================================================

class TrafficBundle(models.Model):
    """
    Encrypted traffic bundles combining real and cover traffic.
    
    All traffic (real operations + cover) is bundled together,
    making it impossible to distinguish actual vault operations.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Bundle identification
    bundle_id = models.CharField(max_length=64, unique=True, db_index=True)
    
    # Associated session
    session = models.ForeignKey(
        GarlicSession,
        on_delete=models.CASCADE,
        related_name='traffic_bundles'
    )
    
    # Bundle type
    bundle_type = models.CharField(
        max_length=20,
        choices=BUNDLE_TYPE_CHOICES,
        default='cover'
    )
    
    # Encrypted payload (indistinguishable from random)
    encrypted_payload = models.BinaryField()
    payload_size = models.IntegerField()
    
    # Timing (for replay protection)
    created_at = models.DateTimeField(auto_now_add=True)
    sequence_number = models.BigIntegerField()  # Monotonic sequence
    
    # Noise characteristics
    padding_size = models.IntegerField(default=0)  # Random padding added
    timing_jitter_ms = models.IntegerField(default=0)  # Delay added
    
    # Status
    is_sent = models.BooleanField(default=False)
    sent_at = models.DateTimeField(null=True, blank=True)
    acknowledged = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['sequence_number']
        indexes = [
            models.Index(fields=['session', 'is_sent']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"Bundle {self.bundle_id[:8]}... ({self.bundle_type})"
    
    def save(self, *args, **kwargs):
        if not self.bundle_id:
            self.bundle_id = secrets.token_hex(32)
        super().save(*args, **kwargs)


# =============================================================================
# Network Health
# =============================================================================

class NetworkHealth(models.Model):
    """
    Network health and performance metrics.
    
    Tracks overall network status and individual node performance
    to enable optimal path selection.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Health check target
    node = models.ForeignKey(
        DarkProtocolNode,
        on_delete=models.CASCADE,
        related_name='health_records'
    )
    
    # Timing
    checked_at = models.DateTimeField(auto_now_add=True)
    
    # Latency measurements (in milliseconds)
    latency_ms = models.IntegerField()
    jitter_ms = models.IntegerField(default=0)
    
    # Availability
    is_reachable = models.BooleanField(default=True)
    response_time_ms = models.IntegerField(null=True)
    
    # Load
    current_load_percent = models.FloatField(default=0.0)
    
    # Cryptographic verification
    signature_valid = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-checked_at']
        indexes = [
            models.Index(fields=['node', 'checked_at']),
        ]
    
    def __str__(self):
        status = "✓" if self.is_reachable else "✗"
        return f"Health {status} {self.node.node_id[:8]} @ {self.checked_at}"


# =============================================================================
# Dark Protocol Configuration
# =============================================================================

class DarkProtocolConfig(models.Model):
    """
    User-specific dark protocol configuration.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    user = models.OneToOneField(
        User, on_delete=models.CASCADE,
        related_name='dark_protocol_config'
    )
    
    # Feature toggles
    is_enabled = models.BooleanField(default=False)
    auto_enable_on_threat = models.BooleanField(default=True)
    
    # Routing preferences
    preferred_regions = models.JSONField(default=list)  # e.g., ["EU", "NA"]
    min_hops = models.IntegerField(default=3)
    max_hops = models.IntegerField(default=5)
    
    # Cover traffic
    cover_traffic_enabled = models.BooleanField(default=True)
    cover_traffic_intensity = models.FloatField(
        default=0.5,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)]
    )
    
    # Session preferences
    session_timeout_minutes = models.IntegerField(default=30)
    auto_path_rotation = models.BooleanField(default=True)
    path_rotation_interval_minutes = models.IntegerField(default=5)
    
    # Security preferences
    use_bridge_nodes = models.BooleanField(default=False)  # For censorship circumvention
    require_verified_nodes = models.BooleanField(default=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        status = "Enabled" if self.is_enabled else "Disabled"
        return f"Dark Protocol Config for {self.user.email} ({status})"
