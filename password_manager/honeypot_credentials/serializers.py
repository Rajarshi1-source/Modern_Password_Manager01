"""
Honeypot DRF serializers. We deliberately expose very limited fields
in list mode so an attacker peeking at the wire can't correlate
honeypots with real vault items.
"""

from __future__ import annotations

from rest_framework import serializers

from .models import (
    DecoyStrategy,
    HoneypotAccessEvent,
    HoneypotCredential,
    HoneypotTemplate,
)


class HoneypotTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = HoneypotTemplate
        fields = (
            'id', 'name', 'fake_site_template', 'fake_username_template',
            'password_pattern', 'description', 'is_builtin', 'created_at',
        )
        read_only_fields = fields


class HoneypotCredentialSerializer(serializers.ModelSerializer):
    """
    Owner-facing serializer. The decoy password is NEVER serialized;
    use the dedicated reveal endpoint.
    """

    access_count = serializers.SerializerMethodField()

    class Meta:
        model = HoneypotCredential
        fields = (
            'id', 'label', 'fake_site', 'fake_username',
            'decoy_strategy', 'template', 'is_active',
            'alert_channels', 'last_rotated_at',
            'created_at', 'updated_at',
            'access_count',
        )
        read_only_fields = (
            'id', 'last_rotated_at', 'created_at', 'updated_at',
            'access_count',
        )

    def get_access_count(self, obj):
        return obj.access_events.count()

    def validate_decoy_strategy(self, value):
        if value not in DecoyStrategy.values:
            raise serializers.ValidationError('Unknown decoy strategy.')
        return value

    def validate_alert_channels(self, value):
        if value is None:
            return []
        allowed = {'email', 'sms', 'webhook', 'signal'}
        bad = [v for v in value if v not in allowed]
        if bad:
            raise serializers.ValidationError(
                f'Unknown alert channel(s): {sorted(bad)}',
            )
        return list(value)


class HoneypotAccessEventSerializer(serializers.ModelSerializer):
    honeypot_label = serializers.CharField(source='honeypot.label', read_only=True)

    class Meta:
        model = HoneypotAccessEvent
        fields = (
            'id', 'honeypot', 'honeypot_label',
            'access_type', 'ip', 'user_agent',
            'geo_country', 'geo_city', 'session_key',
            'alert_sent', 'alert_errors', 'accessed_at',
        )
        read_only_fields = fields
