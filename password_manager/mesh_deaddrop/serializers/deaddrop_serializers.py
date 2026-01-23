"""
Dead Drop API Serializers
==========================

Serializers for the mesh dead drop REST API.

@author Password Manager Team
@created 2026-01-22
"""

from rest_framework import serializers
from django.utils import timezone

from ..models import (
    DeadDrop,
    DeadDropFragment,
    MeshNode,
    NFCBeacon,
    DeadDropAccess,
    FragmentTransfer,
)


# =============================================================================
# Dead Drop Serializers
# =============================================================================

class DeadDropSerializer(serializers.ModelSerializer):
    """Basic dead drop serializer for list views."""
    
    owner_username = serializers.CharField(source='owner.username', read_only=True)
    threshold_display = serializers.CharField(read_only=True)
    time_remaining_seconds = serializers.IntegerField(read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = DeadDrop
        fields = [
            'id',
            'title',
            'description',
            'owner_username',
            'latitude',
            'longitude',
            'radius_meters',
            'location_hint',
            'required_fragments',
            'total_fragments',
            'threshold_display',
            'status',
            'is_active',
            'created_at',
            'expires_at',
            'time_remaining_seconds',
            'is_expired',
            'require_ble_verification',
            'require_nfc_tap',
        ]
        read_only_fields = ['id', 'status', 'created_at']


class DeadDropCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating dead drops."""
    
    secret = serializers.CharField(
        write_only=True,
        style={'input_type': 'password'},
        help_text="The secret data to protect"
    )
    expires_in_hours = serializers.IntegerField(
        default=168,
        min_value=1,
        max_value=8760,  # 1 year
        help_text="Hours until expiration"
    )
    
    class Meta:
        model = DeadDrop
        fields = [
            'title',
            'description',
            'latitude',
            'longitude',
            'radius_meters',
            'location_hint',
            'required_fragments',
            'total_fragments',
            'secret',
            'expires_in_hours',
            'recipient_email',
            'require_ble_verification',
            'require_nfc_tap',
            'min_ble_nodes_required',
            'max_attempts',
        ]
    
    def validate(self, data):
        """Validate threshold configuration."""
        k = data.get('required_fragments', 3)
        n = data.get('total_fragments', 5)
        
        if k > n:
            raise serializers.ValidationError({
                'required_fragments': f"Threshold k ({k}) cannot exceed total n ({n})"
            })
        
        if k < 2:
            raise serializers.ValidationError({
                'required_fragments': "Must require at least 2 fragments for security"
            })
        
        return data
    
    def create(self, validated_data):
        """Create dead drop using the distribution service."""
        from ..services import FragmentDistributionService
        
        secret = validated_data.pop('secret')
        expires_in_hours = validated_data.pop('expires_in_hours', 168)
        
        service = FragmentDistributionService()
        
        dead_drop, result = service.create_and_distribute(
            owner=self.context['request'].user,
            title=validated_data.get('title'),
            secret=secret.encode(),
            latitude=float(validated_data.get('latitude')),
            longitude=float(validated_data.get('longitude')),
            k=validated_data.get('required_fragments', 3),
            n=validated_data.get('total_fragments', 5),
            expires_in_hours=expires_in_hours,
            radius_meters=validated_data.get('radius_meters', 50),
            require_ble=validated_data.get('require_ble_verification', True),
            require_nfc=validated_data.get('require_nfc_tap', False)
        )
        
        return dead_drop


class DeadDropDetailSerializer(DeadDropSerializer):
    """Detailed dead drop serializer with fragments."""
    
    fragments = serializers.SerializerMethodField()
    distribution_status = serializers.SerializerMethodField()
    access_logs = serializers.SerializerMethodField()
    
    class Meta(DeadDropSerializer.Meta):
        fields = DeadDropSerializer.Meta.fields + [
            'fragments',
            'distribution_status',
            'access_logs',
            'collected_at',
            'secret_hash',
        ]
    
    def get_fragments(self, obj):
        """Get fragment overview (not actual data)."""
        fragments = obj.fragments.all()
        return [{
            'index': f.fragment_index,
            'is_distributed': f.is_distributed,
            'is_available': f.is_available,
            'is_collected': f.is_collected,
            'storage_type': f.storage_type,
            'node_name': f.node.device_name if f.node else None,
        } for f in fragments]
    
    def get_distribution_status(self, obj):
        """Get current distribution status."""
        from ..services import FragmentDistributionService
        service = FragmentDistributionService()
        return service.get_distribution_status(obj)
    
    def get_access_logs(self, obj):
        """Get recent access logs."""
        logs = obj.access_logs.order_by('-access_time')[:10]
        return [{
            'time': log.access_time,
            'result': log.result,
            'fragments_collected': log.fragments_collected,
            'location_verified': log.gps_verified and log.ble_verified,
        } for log in logs]


# =============================================================================
# Fragment Serializers
# =============================================================================

class DeadDropFragmentSerializer(serializers.ModelSerializer):
    """Fragment serializer (without sensitive data)."""
    
    node_name = serializers.CharField(source='node.device_name', read_only=True)
    
    class Meta:
        model = DeadDropFragment
        fields = [
            'id',
            'fragment_index',
            'storage_type',
            'is_distributed',
            'distributed_at',
            'is_available',
            'is_collected',
            'collected_at',
            'node_name',
            'last_ping',
        ]
        read_only_fields = fields


# =============================================================================
# Mesh Node Serializers
# =============================================================================

class MeshNodeSerializer(serializers.ModelSerializer):
    """Mesh node serializer."""
    
    owner_username = serializers.CharField(source='owner.username', read_only=True)
    reliability_percent = serializers.SerializerMethodField()
    
    class Meta:
        model = MeshNode
        fields = [
            'id',
            'device_name',
            'device_type',
            'owner_username',
            'is_online',
            'is_available_for_storage',
            'last_seen',
            'last_known_latitude',
            'last_known_longitude',
            'trust_score',
            'reliability_percent',
            'max_fragments',
            'current_fragment_count',
            'registered_at',
        ]
        read_only_fields = ['id', 'trust_score', 'registered_at', 'last_seen']
    
    def get_reliability_percent(self, obj):
        """Calculate reliability percentage."""
        total = obj.successful_transfers + obj.failed_transfers
        if total == 0:
            return None
        return round(obj.successful_transfers / total * 100, 1)


class MeshNodeRegisterSerializer(serializers.ModelSerializer):
    """Serializer for registering a new mesh node."""
    
    class Meta:
        model = MeshNode
        fields = [
            'device_name',
            'device_type',
            'ble_address',
            'public_key',
            'max_fragments',
            'is_available_for_storage',
        ]
    
    def validate_ble_address(self, value):
        """Validate BLE MAC address format."""
        import re
        if not re.match(r'^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$', value):
            raise serializers.ValidationError("Invalid BLE address format (expected XX:XX:XX:XX:XX:XX)")
        return value.upper()
    
    def validate_public_key(self, value):
        """Validate public key format."""
        import base64
        try:
            decoded = base64.b64decode(value)
            if len(decoded) != 32:
                raise serializers.ValidationError("Public key must be 32 bytes (X25519)")
        except Exception:
            raise serializers.ValidationError("Invalid base64-encoded public key")
        return value
    
    def create(self, validated_data):
        """Create mesh node for current user."""
        validated_data['owner'] = self.context['request'].user
        validated_data['is_online'] = True
        return super().create(validated_data)


# =============================================================================
# Location & Collection Serializers
# =============================================================================

class LocationClaimSerializer(serializers.Serializer):
    """Serializer for location claims during collection."""
    
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    accuracy_meters = serializers.FloatField(default=10.0, min_value=0)
    altitude = serializers.FloatField(required=False, allow_null=True)
    
    # BLE signals
    ble_nodes = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        default=list,
        help_text="List of {'id': uuid, 'rssi': int}"
    )
    
    # Optional verification
    wifi_fingerprint = serializers.CharField(required=False, allow_blank=True)
    nfc_response = serializers.CharField(required=False, allow_blank=True)
    
    def validate_ble_nodes(self, value):
        """Validate BLE node data."""
        for node in value:
            if 'id' not in node:
                raise serializers.ValidationError("Each BLE node must have 'id'")
            if 'rssi' in node:
                rssi = node['rssi']
                if not isinstance(rssi, int) or rssi > 0 or rssi < -120:
                    raise serializers.ValidationError(f"Invalid RSSI value: {rssi}")
        return value


class CollectFragmentsSerializer(serializers.Serializer):
    """Serializer for fragment collection request."""
    
    dead_drop_id = serializers.UUIDField()
    location = LocationClaimSerializer()
    access_code = serializers.CharField(required=False, allow_blank=True)
    
    def validate_dead_drop_id(self, value):
        """Validate dead drop exists and is active."""
        try:
            dead_drop = DeadDrop.objects.get(id=value)
        except DeadDrop.DoesNotExist:
            raise serializers.ValidationError("Dead drop not found")
        
        if not dead_drop.is_active:
            raise serializers.ValidationError("Dead drop is not active")
        
        if dead_drop.is_expired:
            raise serializers.ValidationError("Dead drop has expired")
        
        if dead_drop.status == 'collected':
            raise serializers.ValidationError("Dead drop already collected")
        
        return value


class DistributionStatusSerializer(serializers.Serializer):
    """Serializer for distribution status response."""
    
    total_fragments = serializers.IntegerField()
    required_fragments = serializers.IntegerField()
    distributed = serializers.IntegerField()
    available = serializers.IntegerField()
    collected = serializers.IntegerField()
    nodes_used = serializers.IntegerField()
    nodes_online = serializers.IntegerField()
    health = serializers.CharField()
    status = serializers.CharField()


# =============================================================================
# Access Log Serializers
# =============================================================================

class DeadDropAccessSerializer(serializers.ModelSerializer):
    """Access log serializer."""
    
    accessor_username = serializers.CharField(source='accessor.username', read_only=True)
    dead_drop_title = serializers.CharField(source='dead_drop.title', read_only=True)
    
    class Meta:
        model = DeadDropAccess
        fields = [
            'id',
            'dead_drop_title',
            'accessor_username',
            'access_time',
            'claimed_latitude',
            'claimed_longitude',
            'gps_verified',
            'ble_verified',
            'nfc_verified',
            'wifi_verified',
            'ble_nodes_detected',
            'velocity_check_passed',
            'result',
            'fragments_collected',
            'reconstruction_successful',
        ]
        read_only_fields = fields


# =============================================================================
# NFC Beacon Serializers
# =============================================================================

class NFCBeaconSerializer(serializers.ModelSerializer):
    """NFC beacon serializer."""
    
    class Meta:
        model = NFCBeacon
        fields = [
            'id',
            'tag_id',
            'is_active',
            'last_tapped',
            'tap_count',
        ]
        read_only_fields = ['id', 'last_tapped', 'tap_count']


class NFCChallengeSerializer(serializers.Serializer):
    """Serializer for NFC challenge request."""
    
    beacon_id = serializers.UUIDField()
    
    def validate_beacon_id(self, value):
        """Validate beacon exists."""
        try:
            beacon = NFCBeacon.objects.get(id=value, is_active=True)
        except NFCBeacon.DoesNotExist:
            raise serializers.ValidationError("NFC beacon not found or inactive")
        return value


class NFCVerifySerializer(serializers.Serializer):
    """Serializer for NFC verification."""
    
    beacon_id = serializers.UUIDField()
    response = serializers.CharField()
