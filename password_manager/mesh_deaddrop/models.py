"""
Mesh Dead Drop Models
=====================

Core models for offline mesh network password sharing:
- DeadDrop: Physical location-based secret drops
- DeadDropFragment: Shamir secret shares distributed across nodes
- MeshNode: BLE mesh network participants
- DeadDropAccess: Access attempt logs
- FragmentTransfer: Node-to-node transfer logs
- NFCBeacon: Optional NFC verification beacons

Security Features:
- 3-of-5 threshold by default (Shamir's Secret Sharing)
- Multi-factor location verification (GPS + BLE + optional NFC)
- Time-bound fragment encryption
- Anti-spoofing measures

@author Password Manager Team
@created 2026-01-22
"""

import uuid
import hashlib
from datetime import timedelta

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator


# =============================================================================
# Core Dead Drop Model
# =============================================================================

class DeadDrop(models.Model):
    """
    A physical dead drop location where secrets can be retrieved.
    
    Uses Shamir's Secret Sharing to split the secret into fragments
    distributed across multiple mesh nodes. Recipients must be physically
    present at the location to collect enough fragments to reconstruct.
    """
    
    STATUS_CHOICES = [
        ('pending', 'Pending Distribution'),
        ('distributed', 'Fragments Distributed'),
        ('active', 'Active - Ready for Collection'),
        ('collected', 'Collected'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    ]
    
    # Identity
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='dead_drops'
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # Location (GPS coordinates + geofence)
    latitude = models.DecimalField(
        max_digits=9, 
        decimal_places=6,
        help_text="Latitude of dead drop location"
    )
    longitude = models.DecimalField(
        max_digits=9, 
        decimal_places=6,
        help_text="Longitude of dead drop location"
    )
    radius_meters = models.IntegerField(
        default=50,
        validators=[MinValueValidator(10), MaxValueValidator(1000)],
        help_text="Geofence radius in meters"
    )
    location_hint = models.TextField(
        blank=True,
        help_text="Human-readable hint to find exact spot"
    )
    
    # Encrypted Secret
    encrypted_secret = models.BinaryField(
        help_text="Full encrypted secret (only for verification)"
    )
    secret_hash = models.CharField(
        max_length=128,
        help_text="BLAKE3 hash of original secret"
    )
    encryption_algorithm = models.CharField(
        max_length=50,
        default='XChaCha20-Poly1305'
    )
    
    # Shamir Threshold Configuration
    required_fragments = models.IntegerField(
        default=3,
        validators=[MinValueValidator(2), MaxValueValidator(10)],
        help_text="k in (k,n) threshold - minimum fragments needed"
    )
    total_fragments = models.IntegerField(
        default=5,
        validators=[MinValueValidator(2), MaxValueValidator(20)],
        help_text="n in (k,n) threshold - total fragments created"
    )
    
    # Timing
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(
        help_text="When the dead drop expires"
    )
    collected_at = models.DateTimeField(null=True, blank=True)
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    is_active = models.BooleanField(default=True)
    
    # Access Control
    recipient_email = models.EmailField(
        blank=True,
        null=True,
        help_text="Optional: restrict to specific recipient"
    )
    recipient_public_key = models.TextField(
        blank=True,
        null=True,
        help_text="X25519 public key for recipient-only decryption"
    )
    access_code_hash = models.CharField(
        max_length=128,
        blank=True,
        null=True,
        help_text="Optional PIN/access code (hashed)"
    )
    max_attempts = models.IntegerField(
        default=3,
        help_text="Maximum collection attempts before lockout"
    )
    
    # Verification Requirements
    require_ble_verification = models.BooleanField(
        default=True,
        help_text="Require BLE beacon detection"
    )
    require_nfc_tap = models.BooleanField(
        default=False,
        help_text="Require NFC tap for verification"
    )
    min_ble_nodes_required = models.IntegerField(
        default=2,
        help_text="Minimum BLE nodes that must be visible"
    )
    
    class Meta:
        db_table = 'mesh_dead_drop'
        verbose_name = 'Dead Drop'
        verbose_name_plural = 'Dead Drops'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['owner', '-created_at']),
            models.Index(fields=['status', 'expires_at']),
            models.Index(fields=['latitude', 'longitude']),
        ]
    
    def __str__(self):
        return f"{self.title} ({self.status})"
    
    @property
    def is_expired(self):
        return timezone.now() > self.expires_at
    
    @property
    def time_remaining_seconds(self):
        if self.is_expired:
            return 0
        return int((self.expires_at - timezone.now()).total_seconds())
    
    @property
    def threshold_display(self):
        return f"{self.required_fragments}-of-{self.total_fragments}"
    
    def mark_collected(self, user=None):
        """Mark the dead drop as successfully collected."""
        self.status = 'collected'
        self.collected_at = timezone.now()
        self.is_active = False
        self.save()


# =============================================================================
# Fragment Model
# =============================================================================

class DeadDropFragment(models.Model):
    """
    A single fragment of a secret, stored on a mesh node.
    
    Uses Shamir's Secret Sharing - each fragment is a point on a polynomial.
    Need k fragments to reconstruct the secret via Lagrange interpolation.
    Individual fragments reveal nothing about the secret.
    """
    
    STORAGE_CHOICES = [
        ('self', 'Creator Device'),
        ('mesh_node', 'BLE Mesh Node'),
        ('trusted_device', 'Trusted Friend Device'),
        ('cloud_backup', 'Encrypted Cloud Backup'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dead_drop = models.ForeignKey(
        DeadDrop,
        on_delete=models.CASCADE,
        related_name='fragments'
    )
    
    # Shamir share data
    fragment_index = models.IntegerField(
        help_text="Share index (x-coordinate in Shamir)"
    )
    encrypted_fragment = models.BinaryField(
        help_text="Encrypted share data"
    )
    fragment_hash = models.CharField(
        max_length=128,
        help_text="BLAKE3 hash for integrity verification"
    )
    
    # Storage location
    storage_type = models.CharField(
        max_length=20,
        choices=STORAGE_CHOICES,
        default='mesh_node'
    )
    node = models.ForeignKey(
        'MeshNode',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='stored_fragments'
    )
    node_public_key = models.TextField(
        blank=True,
        null=True,
        help_text="Public key used to encrypt for this node"
    )
    
    # Status
    is_distributed = models.BooleanField(default=False)
    distributed_at = models.DateTimeField(null=True, blank=True)
    last_ping = models.DateTimeField(null=True, blank=True)
    is_available = models.BooleanField(default=True)
    
    # Collection tracking
    is_collected = models.BooleanField(default=False)
    collected_at = models.DateTimeField(null=True, blank=True)
    collected_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='collected_fragments'
    )
    
    class Meta:
        db_table = 'mesh_dead_drop_fragment'
        verbose_name = 'Dead Drop Fragment'
        verbose_name_plural = 'Dead Drop Fragments'
        unique_together = ['dead_drop', 'fragment_index']
        ordering = ['fragment_index']
    
    def __str__(self):
        return f"Fragment {self.fragment_index}/{self.dead_drop.total_fragments} for {self.dead_drop.title}"
    
    def mark_distributed(self, node=None):
        """Mark fragment as distributed to a node."""
        self.is_distributed = True
        self.distributed_at = timezone.now()
        if node:
            self.node = node
            self.node_public_key = node.public_key
        self.save()


# =============================================================================
# Mesh Node Model
# =============================================================================

class MeshNode(models.Model):
    """
    A device participating in the BLE mesh network.
    
    Can store fragments and relay messages to other nodes.
    Identified by UUID and BLE MAC address.
    """
    
    DEVICE_TYPES = [
        ('phone_android', 'Android Phone'),
        ('phone_ios', 'iPhone'),
        ('tablet', 'Tablet'),
        ('raspberry_pi', 'Raspberry Pi'),
        ('dedicated', 'Dedicated Node'),
        ('other', 'Other Device'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='mesh_nodes'
    )
    
    # Identity
    public_key = models.TextField(
        help_text="X25519 public key for encryption"
    )
    private_key_encrypted = models.BinaryField(
        null=True,
        blank=True,
        help_text="Encrypted private key (only stored on device)"
    )
    
    # Device info
    device_name = models.CharField(max_length=100)
    device_type = models.CharField(
        max_length=20,
        choices=DEVICE_TYPES,
        default='phone_android'
    )
    ble_address = models.CharField(
        max_length=17,
        help_text="BLE MAC address (XX:XX:XX:XX:XX:XX)"
    )
    device_fingerprint = models.CharField(
        max_length=128,
        blank=True,
        help_text="Device hardware fingerprint"
    )
    
    # Location (last known)
    last_known_latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True
    )
    last_known_longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True
    )
    location_updated_at = models.DateTimeField(null=True, blank=True)
    
    # Availability
    is_online = models.BooleanField(default=False)
    is_available_for_storage = models.BooleanField(default=True)
    last_seen = models.DateTimeField(auto_now=True)
    
    # Storage capacity
    max_fragments = models.IntegerField(
        default=10,
        help_text="Maximum fragments this node can store"
    )
    current_fragment_count = models.IntegerField(default=0)
    
    # Trust & Reputation
    trust_score = models.FloatField(
        default=0.5,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Trust score 0-1 based on reliability"
    )
    successful_transfers = models.IntegerField(default=0)
    failed_transfers = models.IntegerField(default=0)
    
    # Timestamps
    registered_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'mesh_node'
        verbose_name = 'Mesh Node'
        verbose_name_plural = 'Mesh Nodes'
        indexes = [
            models.Index(fields=['ble_address']),
            models.Index(fields=['is_online', 'is_available_for_storage']),
            models.Index(fields=['last_known_latitude', 'last_known_longitude']),
        ]
    
    def __str__(self):
        return f"{self.device_name} ({self.device_type})"
    
    @property
    def has_capacity(self):
        return self.current_fragment_count < self.max_fragments
    
    def update_location(self, lat, lon):
        """Update node's last known location."""
        self.last_known_latitude = lat
        self.last_known_longitude = lon
        self.location_updated_at = timezone.now()
        self.save()
    
    def record_transfer_success(self):
        """Record a successful transfer."""
        self.successful_transfers += 1
        self._update_trust_score()
        self.save()
    
    def record_transfer_failure(self):
        """Record a failed transfer."""
        self.failed_transfers += 1
        self._update_trust_score()
        self.save()
    
    def _update_trust_score(self):
        """Recalculate trust score based on transfer history."""
        total = self.successful_transfers + self.failed_transfers
        if total > 0:
            self.trust_score = self.successful_transfers / total
        else:
            self.trust_score = 0.5


# =============================================================================
# NFC Beacon Model
# =============================================================================

class NFCBeacon(models.Model):
    """
    Optional NFC beacon for additional location verification.
    
    Physical NFC tags placed at dead drop locations that must be
    tapped to prove physical presence (anti-spoofing).
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dead_drop = models.ForeignKey(
        DeadDrop,
        on_delete=models.CASCADE,
        related_name='nfc_beacons'
    )
    
    # NFC Tag ID
    tag_id = models.CharField(
        max_length=64,
        unique=True,
        help_text="NFC tag unique identifier"
    )
    tag_signature = models.CharField(
        max_length=256,
        help_text="Cryptographic signature on tag"
    )
    
    # Challenge-response
    current_challenge = models.CharField(
        max_length=64,
        blank=True,
        help_text="Current challenge for rotation"
    )
    challenge_expires_at = models.DateTimeField(null=True, blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    last_tapped = models.DateTimeField(null=True, blank=True)
    tap_count = models.IntegerField(default=0)
    
    class Meta:
        db_table = 'mesh_nfc_beacon'
        verbose_name = 'NFC Beacon'
        verbose_name_plural = 'NFC Beacons'
    
    def __str__(self):
        return f"NFC Beacon for {self.dead_drop.title}"
    
    def verify_tap(self, response):
        """Verify NFC tap response."""
        if not self.current_challenge:
            return False
        if self.challenge_expires_at and timezone.now() > self.challenge_expires_at:
            return False
        # Verify cryptographic response
        expected = hashlib.blake2b(
            f"{self.tag_id}:{self.current_challenge}".encode(),
            digest_size=32
        ).hexdigest()
        return response == expected
    
    def rotate_challenge(self):
        """Generate new challenge."""
        import secrets
        self.current_challenge = secrets.token_hex(32)
        self.challenge_expires_at = timezone.now() + timedelta(minutes=5)
        self.save()
        return self.current_challenge


# =============================================================================
# Access Log Model
# =============================================================================

class DeadDropAccess(models.Model):
    """
    Records of access attempts to dead drops.
    
    Logs all collection attempts for security auditing,
    including location verification results.
    """
    
    RESULT_CHOICES = [
        ('success', 'Collection Successful'),
        ('insufficient_fragments', 'Insufficient Fragments'),
        ('location_failed', 'Location Verification Failed'),
        ('spoofing_detected', 'GPS Spoofing Detected'),
        ('ble_failed', 'BLE Verification Failed'),
        ('nfc_failed', 'NFC Verification Failed'),
        ('access_code_wrong', 'Wrong Access Code'),
        ('expired', 'Dead Drop Expired'),
        ('locked_out', 'Locked Out'),
        ('error', 'Technical Error'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dead_drop = models.ForeignKey(
        DeadDrop,
        on_delete=models.CASCADE,
        related_name='access_logs'
    )
    accessor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='dead_drop_accesses'
    )
    
    # Timing
    access_time = models.DateTimeField(auto_now_add=True)
    
    # Location claim
    claimed_latitude = models.DecimalField(max_digits=9, decimal_places=6)
    claimed_longitude = models.DecimalField(max_digits=9, decimal_places=6)
    claimed_accuracy_meters = models.FloatField(null=True, blank=True)
    
    # Verification results
    gps_verified = models.BooleanField(default=False)
    ble_verified = models.BooleanField(default=False)
    nfc_verified = models.BooleanField(default=False)
    wifi_verified = models.BooleanField(default=False)
    
    ble_nodes_detected = models.IntegerField(default=0)
    ble_node_ids = models.JSONField(default=list)
    
    # Anti-spoofing
    velocity_check_passed = models.BooleanField(default=True)
    location_history_score = models.FloatField(
        null=True,
        blank=True,
        help_text="Confidence score from location history analysis"
    )
    
    # Collection result
    result = models.CharField(
        max_length=30,
        choices=RESULT_CHOICES
    )
    fragments_collected = models.IntegerField(default=0)
    reconstruction_successful = models.BooleanField(default=False)
    
    # Network info
    access_ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    device_fingerprint = models.CharField(max_length=128, blank=True)
    
    # Error details
    error_message = models.TextField(blank=True)
    
    class Meta:
        db_table = 'mesh_dead_drop_access'
        verbose_name = 'Dead Drop Access'
        verbose_name_plural = 'Dead Drop Accesses'
        ordering = ['-access_time']
        indexes = [
            models.Index(fields=['dead_drop', '-access_time']),
            models.Index(fields=['accessor', '-access_time']),
            models.Index(fields=['result', '-access_time']),
        ]
    
    def __str__(self):
        return f"Access to {self.dead_drop.title} - {self.result}"


# =============================================================================
# Fragment Transfer Log
# =============================================================================

class FragmentTransfer(models.Model):
    """
    Log of fragment transfers between mesh nodes.
    
    Tracks the movement of fragments for debugging and
    reliability analysis.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    fragment = models.ForeignKey(
        DeadDropFragment,
        on_delete=models.CASCADE,
        related_name='transfers'
    )
    
    # Nodes involved
    from_node = models.ForeignKey(
        MeshNode,
        on_delete=models.SET_NULL,
        null=True,
        related_name='sent_transfers'
    )
    to_node = models.ForeignKey(
        MeshNode,
        on_delete=models.SET_NULL,
        null=True,
        related_name='received_transfers'
    )
    
    # Transfer details
    transfer_time = models.DateTimeField(auto_now_add=True)
    transfer_duration_ms = models.IntegerField(null=True, blank=True)
    encryption_method = models.CharField(max_length=50, default='X25519+XChaCha20')
    
    # Result
    transfer_successful = models.BooleanField()
    bytes_transferred = models.IntegerField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    
    class Meta:
        db_table = 'mesh_fragment_transfer'
        verbose_name = 'Fragment Transfer'
        verbose_name_plural = 'Fragment Transfers'
        ordering = ['-transfer_time']
    
    def __str__(self):
        status = '✓' if self.transfer_successful else '✗'
        return f"{status} Transfer: {self.from_node} → {self.to_node}"


# =============================================================================
# Location Verification Cache
# =============================================================================

class LocationVerificationCache(models.Model):
    """
    Cache of recent location verifications for anti-spoofing.
    
    Stores location history to detect impossible travel and
    GPS spoofing attempts.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='location_cache'
    )
    
    # Location
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    accuracy_meters = models.FloatField(null=True, blank=True)
    
    # Source
    source = models.CharField(
        max_length=20,
        choices=[
            ('gps', 'GPS'),
            ('ble', 'BLE Beacons'),
            ('wifi', 'WiFi'),
            ('cell', 'Cell Tower'),
            ('nfc', 'NFC Tap'),
        ]
    )
    
    # Timing
    recorded_at = models.DateTimeField(auto_now_add=True)
    
    # Verification
    is_verified = models.BooleanField(default=False)
    verification_method = models.CharField(max_length=50, blank=True)
    
    class Meta:
        db_table = 'mesh_location_cache'
        verbose_name = 'Location Cache'
        verbose_name_plural = 'Location Cache Entries'
        ordering = ['-recorded_at']
        indexes = [
            models.Index(fields=['user', '-recorded_at']),
        ]
    
    def __str__(self):
        return f"Location for {self.user.username} at {self.recorded_at}"
