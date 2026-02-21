"""
Password Archaeology Serializers
==================================
"""

from rest_framework import serializers
from .models import (
    PasswordHistoryEntry,
    SecurityEvent,
    StrengthSnapshot,
    PasswordTimeline,
    AchievementRecord,
    WhatIfScenario,
)


class PasswordHistoryEntrySerializer(serializers.ModelSerializer):
    """Serializer for password history entries (read-only, no plaintext hashes)."""
    trigger_display = serializers.CharField(
        source='get_trigger_display', read_only=True,
    )
    has_blockchain_proof = serializers.SerializerMethodField()

    class Meta:
        model = PasswordHistoryEntry
        fields = [
            'id', 'credential_domain', 'credential_label',
            'strength_before', 'strength_after',
            'entropy_before', 'entropy_after',
            'trigger', 'trigger_display', 'change_notes',
            'has_blockchain_proof', 'commitment_hash',
            'changed_at', 'created_at',
        ]
        read_only_fields = fields

    def get_has_blockchain_proof(self, obj):
        return bool(obj.blockchain_commitment_id)


class SecurityEventSerializer(serializers.ModelSerializer):
    """Serializer for security events."""
    event_type_display = serializers.CharField(
        source='get_event_type_display', read_only=True,
    )

    class Meta:
        model = SecurityEvent
        fields = [
            'id', 'event_type', 'event_type_display', 'severity',
            'title', 'description', 'metadata',
            'risk_score_impact', 'resolved', 'resolved_at',
            'resolution_notes', 'occurred_at', 'created_at',
        ]
        read_only_fields = fields


class StrengthSnapshotSerializer(serializers.ModelSerializer):
    """Serializer for strength snapshots."""

    class Meta:
        model = StrengthSnapshot
        fields = [
            'id', 'credential_domain', 'strength_score',
            'entropy_bits', 'character_class_coverage',
            'length', 'breach_exposure_count', 'is_reused',
            'snapshot_at',
        ]
        read_only_fields = fields


class AchievementSerializer(serializers.ModelSerializer):
    """Serializer for achievement records."""

    class Meta:
        model = AchievementRecord
        fields = [
            'id', 'achievement_type', 'badge_tier',
            'title', 'description', 'icon_name',
            'score_points', 'earned_at', 'acknowledged',
        ]
        read_only_fields = [
            'id', 'achievement_type', 'badge_tier',
            'title', 'description', 'icon_name',
            'score_points', 'earned_at',
        ]


class WhatIfScenarioSerializer(serializers.ModelSerializer):
    """Serializer for what-if scenario results."""
    scenario_type_display = serializers.CharField(
        source='get_scenario_type_display', read_only=True,
    )

    class Meta:
        model = WhatIfScenario
        fields = [
            'id', 'credential_domain',
            'scenario_type', 'scenario_type_display',
            'scenario_params',
            'actual_risk_score', 'simulated_risk_score',
            'risk_reduction', 'exposure_days_saved',
            'insight_text', 'created_at',
        ]
        read_only_fields = fields


class WhatIfRequestSerializer(serializers.Serializer):
    """Input serializer for running what-if scenarios."""
    scenario_type = serializers.ChoiceField(
        choices=WhatIfScenario.SCENARIO_TYPES,
    )
    credential_domain = serializers.CharField(
        required=False, default='', allow_blank=True,
    )
    vault_item_id = serializers.UUIDField(required=False, allow_null=True)
    params = serializers.DictField(required=False, default=dict)


class TimelineEventSerializer(serializers.Serializer):
    """Unified serializer for mixed timeline events (read-only)."""
    id = serializers.CharField()
    type = serializers.CharField()
    timestamp = serializers.CharField()
    # Password change fields
    credential_domain = serializers.CharField(required=False, default='')
    credential_label = serializers.CharField(required=False, default='')
    trigger = serializers.CharField(required=False, default='')
    trigger_display = serializers.CharField(required=False, default='')
    strength_before = serializers.IntegerField(required=False, default=0)
    strength_after = serializers.IntegerField(required=False, default=0)
    entropy_before = serializers.FloatField(required=False, default=0)
    entropy_after = serializers.FloatField(required=False, default=0)
    change_notes = serializers.CharField(required=False, default='')
    has_blockchain_proof = serializers.BooleanField(required=False, default=False)
    commitment_hash = serializers.CharField(required=False, default='')
    # Security event fields
    event_type = serializers.CharField(required=False, default='')
    event_type_display = serializers.CharField(required=False, default='')
    severity = serializers.CharField(required=False, default='')
    title = serializers.CharField(required=False, default='')
    description = serializers.CharField(required=False, default='')
    risk_score_impact = serializers.IntegerField(required=False, default=0)
    resolved = serializers.BooleanField(required=False, default=False)
    resolved_at = serializers.CharField(required=False, allow_null=True)
    metadata = serializers.DictField(required=False, default=dict)
