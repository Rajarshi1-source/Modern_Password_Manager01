"""
Entanglement Serializers
========================

Django REST Framework serializers for quantum entanglement API.
"""

from rest_framework import serializers
from django.contrib.auth.models import User

# Handle case where models may not be migrated yet
try:
    from security.models import (
        EntangledDevicePair,
        SharedRandomnessPool,
        EntanglementSyncEvent,
        UserDevice,
    )
    MODELS_AVAILABLE = True
except ImportError:
    MODELS_AVAILABLE = False
    # Create placeholder classes for serializers to reference
    EntangledDevicePair = None
    SharedRandomnessPool = None
    EntanglementSyncEvent = None
    UserDevice = None



class DeviceSerializer(serializers.ModelSerializer):
    """Serializer for device information."""
    
    class Meta:
        model = UserDevice
        fields = ['device_id', 'device_name', 'device_type', 'is_trusted', 'last_seen']


class InitiatePairingSerializer(serializers.Serializer):
    """Request to initiate device pairing."""
    
    device_a_id = serializers.UUIDField(
        help_text="First device UUID"
    )
    device_b_id = serializers.UUIDField(
        help_text="Second device UUID"
    )
    
    def validate(self, data):
        if data['device_a_id'] == data['device_b_id']:
            raise serializers.ValidationError("Cannot pair a device with itself")
        return data


class PairingSessionSerializer(serializers.Serializer):
    """Response for pairing initiation."""
    
    session_id = serializers.CharField()
    device_a_id = serializers.UUIDField()
    device_b_id = serializers.UUIDField()
    verification_code = serializers.CharField()
    expires_at = serializers.DateTimeField()
    created_at = serializers.DateTimeField()


class VerifyPairingSerializer(serializers.Serializer):
    """Request to verify and complete pairing."""
    
    session_id = serializers.CharField(
        help_text="Pairing session ID"
    )
    verification_code = serializers.CharField(
        max_length=6,
        min_length=6,
        help_text="6-digit verification code"
    )
    device_b_public_key = serializers.CharField(
        help_text="Base64-encoded lattice public key from device B"
    )


class PairingCompleteSerializer(serializers.Serializer):
    """Response for successful pairing."""
    
    pair_id = serializers.UUIDField()
    status = serializers.CharField()
    generation = serializers.IntegerField()
    device_a_id = serializers.UUIDField()
    device_b_id = serializers.UUIDField()
    ciphertext_b64 = serializers.CharField()


class SyncRequestSerializer(serializers.Serializer):
    """Request for key synchronization."""
    
    pair_id = serializers.UUIDField(
        help_text="Entangled pair ID"
    )
    device_id = serializers.UUIDField(
        help_text="Requesting device ID"
    )


class SyncResultSerializer(serializers.Serializer):
    """Response for sync operation."""
    
    success = serializers.BooleanField()
    pair_id = serializers.UUIDField()
    new_generation = serializers.IntegerField()
    entropy_status = serializers.CharField()
    sync_timestamp = serializers.DateTimeField()
    error_message = serializers.CharField(allow_null=True)


class RotateKeysSerializer(serializers.Serializer):
    """Request for key rotation."""
    
    pair_id = serializers.UUIDField(
        help_text="Entangled pair ID"
    )
    device_id = serializers.UUIDField(
        help_text="Device initiating rotation"
    )


class EntropyAnalysisSerializer(serializers.Serializer):
    """Response for entropy analysis."""
    
    has_anomaly = serializers.BooleanField()
    anomaly_type = serializers.CharField(allow_null=True)
    severity = serializers.CharField()
    kl_divergence = serializers.FloatField()
    entropy_a = serializers.FloatField()
    entropy_b = serializers.FloatField()
    detected_at = serializers.DateTimeField()
    recommendation = serializers.CharField()
    details = serializers.DictField(required=False)


class RevokeRequestSerializer(serializers.Serializer):
    """Request for instant revocation."""
    
    pair_id = serializers.UUIDField(
        help_text="Pair to revoke"
    )
    compromised_device_id = serializers.UUIDField(
        required=False,
        allow_null=True,
        help_text="ID of compromised device (optional)"
    )
    reason = serializers.CharField(
        max_length=500,
        default="Manual revocation",
        help_text="Reason for revocation"
    )


class RevocationResultSerializer(serializers.Serializer):
    """Response for revocation."""
    
    success = serializers.BooleanField()
    pair_id = serializers.UUIDField()
    revoked_at = serializers.DateTimeField()
    reason = serializers.CharField()
    affected_devices = serializers.ListField(
        child=serializers.UUIDField()
    )


class SharedRandomnessPoolSerializer(serializers.ModelSerializer):
    """Serializer for randomness pool status."""
    
    class Meta:
        model = SharedRandomnessPool
        fields = [
            'pool_generation',
            'entropy_measurement',
            'last_refreshed_at',
        ]
    
    is_healthy = serializers.SerializerMethodField()
    is_critical = serializers.SerializerMethodField()
    
    def get_is_healthy(self, obj):
        return obj.is_entropy_healthy()
    
    def get_is_critical(self, obj):
        return obj.is_entropy_critical()


class EntanglementSyncEventSerializer(serializers.ModelSerializer):
    """Serializer for sync events."""
    
    event_type_display = serializers.CharField(
        source='get_event_type_display',
        read_only=True
    )
    initiated_by = serializers.SerializerMethodField()
    
    class Meta:
        model = EntanglementSyncEvent
        fields = [
            'id',
            'event_type',
            'event_type_display',
            'initiated_by',
            'success',
            'details',
            'created_at',
        ]
    
    def get_initiated_by(self, obj):
        if obj.initiated_by_device:
            return {
                'device_id': str(obj.initiated_by_device.device_id),
                'device_name': obj.initiated_by_device.device_name,
            }
        return None


class EntangledDevicePairSerializer(serializers.ModelSerializer):
    """Full serializer for entangled pair."""
    
    device_a = DeviceSerializer(read_only=True)
    device_b = DeviceSerializer(read_only=True)
    pool = SharedRandomnessPoolSerializer(
        source='sharedrandomnesspool',
        read_only=True
    )
    recent_events = serializers.SerializerMethodField()
    
    class Meta:
        model = EntangledDevicePair
        fields = [
            'id',
            'user',
            'device_a',
            'device_b',
            'status',
            'pairing_initiated_at',
            'pairing_completed_at',
            'last_sync_at',
            'revoked_at',
            'revocation_reason',
            'pool',
            'recent_events',
        ]
    
    def get_recent_events(self, obj):
        events = obj.sync_events.all()[:5]
        return EntanglementSyncEventSerializer(events, many=True).data


class PairStatusSerializer(serializers.Serializer):
    """Pair status summary."""
    
    pair_id = serializers.UUIDField()
    status = serializers.CharField()
    device_a_id = serializers.UUIDField()
    device_b_id = serializers.UUIDField()
    current_generation = serializers.IntegerField()
    last_sync_at = serializers.DateTimeField(allow_null=True)
    entropy_health = serializers.CharField()
    entropy_score = serializers.FloatField()
    created_at = serializers.DateTimeField()


class UserPairsListSerializer(serializers.Serializer):
    """List of user's entangled pairs."""
    
    pairs = PairStatusSerializer(many=True)
    total_count = serializers.IntegerField()
    max_allowed = serializers.IntegerField()
