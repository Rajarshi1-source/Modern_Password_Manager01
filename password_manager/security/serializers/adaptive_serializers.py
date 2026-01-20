"""
DRF Serializers for Adaptive Password Feature
==============================================

Serializers for REST API endpoints.
"""

from rest_framework import serializers
from django.contrib.auth.models import User

# Handle potential import issues
try:
    from ..models import (
        AdaptivePasswordConfig,
        TypingSession,
        PasswordAdaptation,
        UserTypingProfile,
        AdaptationFeedback,
    )
    MODELS_AVAILABLE = True
except ImportError:
    MODELS_AVAILABLE = False
    AdaptivePasswordConfig = None
    TypingSession = None
    PasswordAdaptation = None
    UserTypingProfile = None
    AdaptationFeedback = None



# =============================================================================
# Configuration Serializers
# =============================================================================

class AdaptivePasswordConfigSerializer(serializers.ModelSerializer):
    """Serializer for user adaptive password configuration."""
    
    username = serializers.CharField(source='user.username', read_only=True)
    days_until_next_suggestion = serializers.SerializerMethodField()
    
    class Meta:
        model = AdaptivePasswordConfig
        fields = [
            'id',
            'username',
            'is_enabled',
            'auto_suggest_enabled',
            'suggestion_frequency_days',
            'differential_privacy_epsilon',
            'allow_centralized_training',
            'allow_federated_learning',
            'consent_given_at',
            'consent_version',
            'last_suggestion_at',
            'days_until_next_suggestion',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id', 'username', 'consent_given_at', 'last_suggestion_at',
            'created_at', 'updated_at'
        ]
    
    def get_days_until_next_suggestion(self, obj):
        """Calculate days until next suggestion is due."""
        if not obj.last_suggestion_at:
            return 0  # Suggestion can be made now
        
        from django.utils import timezone
        days_since = (timezone.now() - obj.last_suggestion_at).days
        remaining = obj.suggestion_frequency_days - days_since
        return max(0, remaining)


class EnableAdaptivePasswordSerializer(serializers.Serializer):
    """Serializer for enabling adaptive passwords with consent."""
    
    consent = serializers.BooleanField(required=True)
    consent_version = serializers.CharField(default='1.0')
    suggestion_frequency_days = serializers.IntegerField(
        default=30, min_value=7, max_value=365
    )
    allow_centralized_training = serializers.BooleanField(default=True)
    allow_federated_learning = serializers.BooleanField(default=False)
    differential_privacy_epsilon = serializers.FloatField(
        default=0.5, min_value=0.1, max_value=2.0
    )
    
    def validate_consent(self, value):
        if not value:
            raise serializers.ValidationError(
                "Explicit consent is required to enable adaptive passwords."
            )
        return value


# =============================================================================
# Typing Session Serializers
# =============================================================================

class TypingSessionSerializer(serializers.ModelSerializer):
    """Serializer for typing sessions."""
    
    username = serializers.CharField(source='user.username', read_only=True)
    duration_seconds = serializers.SerializerMethodField()
    
    class Meta:
        model = TypingSession
        fields = [
            'id',
            'username',
            'password_length',
            'success',
            'error_count',
            'total_time_ms',
            'duration_seconds',
            'device_type',
            'input_method',
            'created_at',
        ]
        read_only_fields = ['id', 'username', 'created_at']
    
    def get_duration_seconds(self, obj):
        """Convert ms to seconds."""
        if obj.total_time_ms:
            return round(obj.total_time_ms / 1000, 2)
        return 0


class TypingSessionInputSerializer(serializers.Serializer):
    """Serializer for recording a typing session."""
    
    password = serializers.CharField(write_only=True, required=True)
    keystroke_timings = serializers.ListField(
        child=serializers.IntegerField(min_value=0, max_value=10000),
        allow_empty=True
    )
    backspace_positions = serializers.ListField(
        child=serializers.IntegerField(min_value=0),
        allow_empty=True,
        required=False
    )
    device_type = serializers.ChoiceField(
        choices=['desktop', 'mobile', 'tablet'],
        default='desktop'
    )
    input_method = serializers.ChoiceField(
        choices=['keyboard', 'touchscreen', 'voice'],
        default='keyboard'
    )


# =============================================================================
# Password Adaptation Serializers
# =============================================================================

class SubstitutionSerializer(serializers.Serializer):
    """Serializer for a single substitution."""
    
    position = serializers.IntegerField(min_value=0)
    original_char = serializers.CharField(max_length=1, required=False)
    suggested_char = serializers.CharField(max_length=1, required=False)
    from_char = serializers.CharField(max_length=1, source='original_char', required=False)
    to_char = serializers.CharField(max_length=1, source='suggested_char', required=False)
    confidence = serializers.FloatField(min_value=0, max_value=1, required=False)
    reason = serializers.CharField(required=False)


class PasswordAdaptationSerializer(serializers.ModelSerializer):
    """Serializer for password adaptations."""
    
    username = serializers.CharField(source='user.username', read_only=True)
    memorability_improvement = serializers.SerializerMethodField()
    can_rollback = serializers.SerializerMethodField()
    rollback_chain_length = serializers.SerializerMethodField()
    
    class Meta:
        model = PasswordAdaptation
        fields = [
            'id',
            'username',
            'status',
            'adaptation_type',
            'adaptation_generation',
            'substitutions_applied',
            'confidence_score',
            'memorability_score_before',
            'memorability_score_after',
            'memorability_improvement',
            'can_rollback',
            'rollback_chain_length',
            'reason',
            'suggested_at',
            'decided_at',
            'rolled_back_at',
        ]
        read_only_fields = [
            'id', 'username', 'suggested_at', 'decided_at', 'rolled_back_at'
        ]
    
    def get_memorability_improvement(self, obj):
        """Calculate memorability improvement percentage."""
        before = obj.memorability_score_before or 0
        after = obj.memorability_score_after or 0
        return round((after - before) * 100, 1)
    
    def get_can_rollback(self, obj):
        """Check if adaptation can be rolled back."""
        return obj.can_rollback()
    
    def get_rollback_chain_length(self, obj):
        """Get length of rollback chain."""
        return len(obj.get_rollback_chain())


class AdaptationSuggestionSerializer(serializers.Serializer):
    """Serializer for adaptation suggestions (output)."""
    
    has_suggestion = serializers.BooleanField()
    substitutions = SubstitutionSerializer(many=True, required=False)
    original_preview = serializers.CharField(required=False)
    adapted_preview = serializers.CharField(required=False)
    confidence_score = serializers.FloatField(required=False)
    memorability_improvement = serializers.FloatField(required=False)
    adaptation_type = serializers.CharField(required=False)
    reason = serializers.CharField(required=False)


class ApplyAdaptationSerializer(serializers.Serializer):
    """Serializer for applying an adaptation."""
    
    original_password = serializers.CharField(write_only=True, required=True)
    adapted_password = serializers.CharField(write_only=True, required=True)
    substitutions = serializers.ListField(
        child=serializers.DictField(),
        required=True
    )
    
    def validate(self, data):
        if data['original_password'] == data['adapted_password']:
            raise serializers.ValidationError(
                "Adapted password must be different from original."
            )
        return data


class RollbackAdaptationSerializer(serializers.Serializer):
    """Serializer for rollback requests."""
    
    adaptation_id = serializers.UUIDField(required=True)


# =============================================================================
# User Typing Profile Serializers
# =============================================================================

class UserTypingProfileSerializer(serializers.ModelSerializer):
    """Serializer for user typing profiles."""
    
    username = serializers.CharField(source='user.username', read_only=True)
    has_sufficient_data = serializers.SerializerMethodField()
    top_substitutions = serializers.SerializerMethodField()
    sessions_until_suggestion = serializers.SerializerMethodField()
    
    class Meta:
        model = UserTypingProfile
        fields = [
            'id',
            'username',
            'preferred_substitutions',
            'substitution_confidence',
            'average_wpm',
            'wpm_variance',
            'error_prone_positions',
            'common_error_types',
            'total_sessions',
            'successful_sessions',
            'success_rate',
            'profile_confidence',
            'has_sufficient_data',
            'sessions_until_suggestion',
            'top_substitutions',
            'last_session_at',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id', 'username', 'total_sessions', 'successful_sessions',
            'success_rate', 'profile_confidence', 'last_session_at',
            'created_at', 'updated_at'
        ]
    
    def get_has_sufficient_data(self, obj):
        return obj.has_sufficient_data()
    
    def get_top_substitutions(self, obj):
        return obj.get_top_substitutions(5)
    
    def get_sessions_until_suggestion(self, obj):
        remaining = obj.minimum_sessions_for_suggestion - obj.total_sessions
        return max(0, remaining)


class TypingProfileSummarySerializer(serializers.Serializer):
    """Lightweight serializer for profile summary."""
    
    has_profile = serializers.BooleanField()
    total_sessions = serializers.IntegerField(required=False)
    success_rate = serializers.FloatField(required=False)
    average_wpm = serializers.FloatField(required=False)
    profile_confidence = serializers.FloatField(required=False)
    has_sufficient_data = serializers.BooleanField(required=False)


# =============================================================================
# Adaptation Feedback Serializers
# =============================================================================

class AdaptationFeedbackSerializer(serializers.ModelSerializer):
    """Serializer for adaptation feedback."""
    
    username = serializers.CharField(source='user.username', read_only=True)
    rating_display = serializers.SerializerMethodField()
    
    class Meta:
        model = AdaptationFeedback
        fields = [
            'id',
            'adaptation',
            'username',
            'rating',
            'rating_display',
            'typing_accuracy_improved',
            'memorability_improved',
            'typing_speed_improved',
            'additional_feedback',
            'days_since_adaptation',
            'typing_sessions_since',
            'created_at',
        ]
        read_only_fields = [
            'id', 'username', 'days_since_adaptation', 'created_at'
        ]
    
    def get_rating_display(self, obj):
        return '★' * obj.rating + '☆' * (5 - obj.rating)


class SubmitFeedbackSerializer(serializers.Serializer):
    """Serializer for submitting feedback."""
    
    adaptation_id = serializers.UUIDField(required=True)
    rating = serializers.IntegerField(min_value=1, max_value=5, required=True)
    typing_accuracy_improved = serializers.BooleanField(
        required=False, allow_null=True
    )
    memorability_improved = serializers.BooleanField(
        required=False, allow_null=True
    )
    typing_speed_improved = serializers.BooleanField(
        required=False, allow_null=True
    )
    additional_feedback = serializers.CharField(
        required=False, allow_blank=True, max_length=1000
    )


# =============================================================================
# Statistics Serializers
# =============================================================================

class EvolutionStatsSerializer(serializers.Serializer):
    """Serializer for evolution statistics."""
    
    active_adaptations = serializers.IntegerField()
    total_adaptations = serializers.IntegerField()
    average_memorability_improvement = serializers.FloatField()
    total_typing_sessions = serializers.IntegerField()
    overall_success_rate = serializers.FloatField()


class DataExportSerializer(serializers.Serializer):
    """Serializer for GDPR data export."""
    
    export_date = serializers.DateTimeField()
    user_id = serializers.IntegerField()
    configuration = serializers.DictField(allow_null=True)
    typing_profile = serializers.DictField(allow_null=True)
    adaptations = serializers.ListField(child=serializers.DictField())
    session_count = serializers.IntegerField()
