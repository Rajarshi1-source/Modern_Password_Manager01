"""
Predictive Expiration Serializers
==================================

DRF serializers for predictive password expiration API.
"""

from rest_framework import serializers
from django.contrib.auth.models import User

from ..models import (
    PasswordPatternProfile,
    ThreatActorTTP,
    IndustryThreatLevel,
    PredictiveExpirationRule,
    PasswordRotationEvent,
    ThreatIntelFeed,
    PredictiveExpirationSettings,
)


class PasswordPatternProfileSerializer(serializers.ModelSerializer):
    """Serializer for user's password pattern profile."""
    username = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = PasswordPatternProfile
        fields = [
            'id',
            'username',
            'char_class_distribution',
            'avg_password_length',
            'length_variance',
            'min_length_used',
            'max_length_used',
            'uses_common_base_words',
            'uses_keyboard_patterns',
            'uses_date_patterns',
            'uses_leet_substitutions',
            'total_passwords_analyzed',
            'weak_patterns_detected',
            'overall_pattern_risk_score',
            'last_analysis_at',
            'updated_at',
        ]
        read_only_fields = fields


class ThreatActorTTPSerializer(serializers.ModelSerializer):
    """Serializer for threat actor TTPs."""
    
    class Meta:
        model = ThreatActorTTP
        fields = [
            'actor_id',
            'name',
            'aliases',
            'actor_type',
            'target_industries',
            'target_regions',
            'password_patterns_exploited',
            'attack_techniques',
            'threat_level',
            'is_currently_active',
            'first_observed',
            'last_active',
            'source',
        ]
        read_only_fields = fields


class ThreatActorSummarySerializer(serializers.ModelSerializer):
    """Lightweight serializer for threat actor summaries."""
    
    class Meta:
        model = ThreatActorTTP
        fields = [
            'actor_id',
            'name',
            'actor_type',
            'threat_level',
            'is_currently_active',
        ]


class IndustryThreatLevelSerializer(serializers.ModelSerializer):
    """Serializer for industry threat levels."""
    active_actors_count = serializers.SerializerMethodField()
    
    class Meta:
        model = IndustryThreatLevel
        fields = [
            'industry_code',
            'industry_name',
            'current_threat_level',
            'threat_score',
            'active_campaigns_count',
            'recent_breaches_count',
            'recent_credential_leaks',
            'threat_trend',
            'advisory_message',
            'recommended_actions',
            'active_actors_count',
            'last_assessment_at',
        ]
        read_only_fields = fields
    
    def get_active_actors_count(self, obj):
        return obj.active_threat_actors.count()


class PredictiveExpirationRuleSerializer(serializers.ModelSerializer):
    """Serializer for predictive expiration rules."""
    matched_actors = ThreatActorSummarySerializer(
        source='matched_threat_actors',
        many=True,
        read_only=True
    )
    
    class Meta:
        model = PredictiveExpirationRule
        fields = [
            'rule_id',
            'credential_id',
            'credential_domain',
            'risk_level',
            'risk_score',
            'predicted_compromise_date',
            'prediction_confidence',
            'threat_factors',
            'pattern_similarity_score',
            'industry_threat_correlation',
            'recommended_action',
            'recommended_rotation_date',
            'is_active',
            'user_acknowledged',
            'user_acknowledged_at',
            'last_notification_sent',
            'notification_count',
            'matched_actors',
            'created_at',
            'updated_at',
            'last_evaluated_at',
        ]
        read_only_fields = [
            'rule_id', 'risk_level', 'risk_score',
            'predicted_compromise_date', 'prediction_confidence',
            'threat_factors', 'pattern_similarity_score',
            'industry_threat_correlation', 'recommended_action',
            'recommended_rotation_date', 'matched_actors',
            'created_at', 'updated_at', 'last_evaluated_at',
            'last_notification_sent', 'notification_count',
        ]


class CredentialRiskListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for credential risk listing."""
    
    class Meta:
        model = PredictiveExpirationRule
        fields = [
            'rule_id',
            'credential_id',
            'credential_domain',
            'risk_level',
            'risk_score',
            'recommended_action',
            'predicted_compromise_date',
            'user_acknowledged',
            'last_evaluated_at',
        ]


class PasswordRotationEventSerializer(serializers.ModelSerializer):
    """Serializer for password rotation events."""
    
    class Meta:
        model = PasswordRotationEvent
        fields = [
            'event_id',
            'credential_id',
            'credential_domain',
            'rotation_type',
            'outcome',
            'trigger_reason',
            'threat_factors_at_rotation',
            'risk_score_at_rotation',
            'old_password_strength',
            'new_password_strength',
            'initiated_at',
            'completed_at',
        ]
        read_only_fields = fields


class ThreatIntelFeedSerializer(serializers.ModelSerializer):
    """Serializer for threat intelligence feeds."""
    
    class Meta:
        model = ThreatIntelFeed
        fields = [
            'feed_id',
            'name',
            'feed_type',
            'reliability_score',
            'is_active',
            'is_healthy',
            'health_check_message',
            'sync_frequency_minutes',
            'last_sync_at',
            'last_sync_success',
            'last_sync_items_count',
            'total_items_ingested',
        ]
        read_only_fields = ['feed_id', 'is_healthy', 'health_check_message',
                           'last_sync_at', 'last_sync_success',
                           'last_sync_items_count', 'total_items_ingested']


class PredictiveExpirationSettingsSerializer(serializers.ModelSerializer):
    """Serializer for user's predictive expiration settings."""
    
    class Meta:
        model = PredictiveExpirationSettings
        fields = [
            'is_enabled',
            'auto_rotation_enabled',
            'force_rotation_threshold',
            'warning_threshold',
            'industry',
            'organization_size',
            'notify_on_high_risk',
            'notify_on_medium_risk',
            'notification_frequency_hours',
            'include_all_credentials',
            'exclude_domains',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def validate_force_rotation_threshold(self, value):
        if not 0 <= value <= 1:
            raise serializers.ValidationError(
                "Threshold must be between 0 and 1"
            )
        return value
    
    def validate_warning_threshold(self, value):
        if not 0 <= value <= 1:
            raise serializers.ValidationError(
                "Threshold must be between 0 and 1"
            )
        return value


class DashboardSerializer(serializers.Serializer):
    """Serializer for the predictive expiration dashboard."""
    overall_risk_score = serializers.FloatField()
    total_credentials = serializers.IntegerField()
    at_risk_count = serializers.IntegerField()
    critical_count = serializers.IntegerField()
    high_count = serializers.IntegerField()
    # Alias exposed for clients that expect `high_risk_count`.
    high_risk_count = serializers.IntegerField()
    medium_count = serializers.IntegerField()
    pending_rotations = serializers.IntegerField()
    recent_rotations = serializers.IntegerField()
    active_threats = ThreatActorSummarySerializer(many=True)
    industry_threat = IndustryThreatLevelSerializer(allow_null=True)
    credentials_at_risk = CredentialRiskListSerializer(many=True)
    last_scan_at = serializers.DateTimeField(allow_null=True)


class ForceRotationSerializer(serializers.Serializer):
    """Serializer for force rotation requests.

    Zero-knowledge: the rotate endpoint only *records* the rotation obligation
    (a PasswordRotationEvent) — the actual password is regenerated, re-encrypted
    and stored entirely client-side. It therefore accepts a reason only; no
    plaintext password field exists here, so a new password can never reach the
    server. (The view already ignored the old write-only ``new_password``.)
    """
    reason = serializers.CharField(
        max_length=500,
        required=False,
        default='Manual rotation request'
    )


# Allowed coarse vocabularies for the zero-knowledge fingerprint payload.
# Anything outside these sets is rejected so the client cannot smuggle
# higher-resolution (identifying) data through these fields.
LENGTH_BUCKETS = ['very_short', 'short', 'medium', 'long', 'very_long']
ENTROPY_BANDS = ['very_low', 'low', 'medium', 'high', 'very_high']
DOMAIN_CLASSES = [
    'finance', 'healthcare', 'technology', 'government', 'retail',
    'education', 'social', 'email', 'shopping', 'other',
]

# Upper bound on a single ingest batch — rejects oversized payloads.
MAX_FINGERPRINT_BATCH = 500


class FingerprintItemSerializer(serializers.Serializer):
    """A single zero-knowledge password fingerprint uploaded by the browser.

    Every field is irreversible structural metadata. There is deliberately no
    ``password``, no ``detected_base_words`` and no exact-domain field: the
    server can never reconstruct the credential from this payload.
    """
    credential_id = serializers.CharField(max_length=128)
    # Character-class sequence, restricted to U/L/D/S so it cannot carry the
    # actual characters of the password.
    char_class_sequence = serializers.RegexField(
        r'^[ULDS]*$', max_length=256
    )
    length = serializers.IntegerField(
        min_value=0, max_value=4096, required=False
    )
    length_bucket = serializers.ChoiceField(choices=LENGTH_BUCKETS)
    # Entropy is uploaded as a coarse band only; the representative estimate is
    # derived server-side so ingest and daily re-scoring score identically.
    entropy_band = serializers.ChoiceField(choices=ENTROPY_BANDS)
    structure_hash = serializers.RegexField(
        r'^[0-9a-fA-F]{64}$', required=False, allow_blank=True, default=''
    )
    has_dictionary_base = serializers.BooleanField(required=False, default=False)
    has_keyboard_pattern = serializers.BooleanField(required=False, default=False)
    has_date_pattern = serializers.BooleanField(required=False, default=False)
    has_leet = serializers.BooleanField(required=False, default=False)
    age_days = serializers.IntegerField(
        min_value=0, max_value=100000, required=False, default=0
    )
    # Coarse category only — never the exact site.
    domain_class = serializers.ChoiceField(
        choices=DOMAIN_CLASSES, required=False, allow_blank=True, default=''
    )

    def validate(self, attrs):
        # The char-class sequence already encodes the exact length, so derive
        # it server-side rather than trusting a (possibly conflicting) client
        # value. Keeps scoring and profile aggregation on one length source.
        attrs['length'] = len(attrs['char_class_sequence'])
        return attrs


class FingerprintIngestSerializer(serializers.Serializer):
    """Batch of password fingerprints submitted on vault unlock / change."""
    fingerprints = FingerprintItemSerializer(many=True)

    def validate_fingerprints(self, value):
        if not value:
            raise serializers.ValidationError(
                "At least one fingerprint is required."
            )
        if len(value) > MAX_FINGERPRINT_BATCH:
            raise serializers.ValidationError(
                f"Batch too large (max {MAX_FINGERPRINT_BATCH})."
            )
        # Reject duplicate credential_ids: the (user, credential_id) upsert
        # would keep only the last, yet both would be counted in the profile.
        ids = [fp['credential_id'] for fp in value]
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError(
                "Duplicate credential_id values in a single batch."
            )
        return value


class ThreatSummarySerializer(serializers.Serializer):
    """Serializer for threat landscape summary."""
    total_active_actors = serializers.IntegerField()
    critical_threats = serializers.IntegerField()
    high_threats = serializers.IntegerField()
    ransomware_active = serializers.IntegerField()
    apt_active = serializers.IntegerField()
    industries_at_risk = serializers.IntegerField()
    last_updated = serializers.DateTimeField()
