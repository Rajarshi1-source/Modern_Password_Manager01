"""DRF serializers for self-destruct policies."""

from __future__ import annotations

from rest_framework import serializers

from .models import PolicyKind, PolicyStatus, SelfDestructEvent, SelfDestructPolicy


class SelfDestructPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = SelfDestructPolicy
        fields = (
            'id', 'vault_item_id', 'kinds', 'status',
            'expires_at', 'max_uses', 'access_count',
            'geofence_lat', 'geofence_lng', 'geofence_radius_m',
            'last_accessed_at', 'last_denied_reason',
            'created_at', 'updated_at',
        )
        read_only_fields = (
            'id', 'status', 'access_count', 'last_accessed_at',
            'last_denied_reason', 'created_at', 'updated_at',
        )

    def validate_kinds(self, value):
        if not isinstance(value, list) or not value:
            raise serializers.ValidationError('At least one policy kind is required.')
        allowed = set(PolicyKind.values)
        bad = [v for v in value if v not in allowed]
        if bad:
            raise serializers.ValidationError(f'Unknown kind(s): {sorted(bad)}')
        return value

    def validate(self, attrs):
        kinds = set(attrs.get('kinds') or [])
        if PolicyKind.TTL in kinds and not attrs.get('expires_at'):
            raise serializers.ValidationError({'expires_at': 'Required for TTL policies.'})
        if PolicyKind.USE_LIMIT in kinds and not attrs.get('max_uses'):
            raise serializers.ValidationError({'max_uses': 'Required for use-limit policies.'})
        if PolicyKind.GEOFENCE in kinds:
            missing = [f for f in ('geofence_lat', 'geofence_lng', 'geofence_radius_m') if attrs.get(f) is None]
            if missing:
                raise serializers.ValidationError({f: 'Required for geofence policies.' for f in missing})
        return attrs


class SelfDestructEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = SelfDestructEvent
        fields = ('id', 'policy', 'decision', 'reason', 'ip', 'lat', 'lng', 'created_at')
        read_only_fields = fields
