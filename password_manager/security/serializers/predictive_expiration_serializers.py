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
    medium_count = serializers.IntegerField()
    pending_rotations = serializers.IntegerField()
    recent_rotations = serializers.IntegerField()
    active_threats = ThreatActorSummarySerializer(many=True)
    industry_threat = IndustryThreatLevelSerializer(allow_null=True)
    credentials_at_risk = CredentialRiskListSerializer(many=True)
    last_scan_at = serializers.DateTimeField(allow_null=True)


class ForceRotationSerializer(serializers.Serializer):
    """Serializer for force rotation requests."""
    reason = serializers.CharField(
        max_length=500,
        required=False,
        default='Manual rotation request'
    )
    new_password = serializers.CharField(
        max_length=200,
        required=False,
        write_only=True
    )


class CredentialAnalysisRequestSerializer(serializers.Serializer):
    """Serializer for credential analysis requests."""
    credential_id = serializers.UUIDField()
    password = serializers.CharField(write_only=True)
    domain = serializers.CharField(max_length=255)
    created_at = serializers.DateTimeField(required=False)


class RiskAnalysisResponseSerializer(serializers.Serializer):
    """Serializer for risk analysis responses."""
    overall_score = serializers.FloatField()
    pattern_risk = serializers.FloatField()
    threat_risk = serializers.FloatField()
    industry_risk = serializers.FloatField()
    age_risk = serializers.FloatField()
    risk_level = serializers.CharField()
    factors = serializers.ListField(child=serializers.CharField())
    predicted_compromise_date = serializers.DateField(allow_null=True)
    prediction_confidence = serializers.FloatField()
    recommended_action = serializers.CharField()
    recommended_rotation_date = serializers.DateField(allow_null=True)


class ThreatSummarySerializer(serializers.Serializer):
    """Serializer for threat landscape summary."""
    total_active_actors = serializers.IntegerField()
    critical_threats = serializers.IntegerField()
    high_threats = serializers.IntegerField()
    ransomware_active = serializers.IntegerField()
    apt_active = serializers.IntegerField()
    industries_at_risk = serializers.IntegerField()
    last_updated = serializers.DateTimeField()
