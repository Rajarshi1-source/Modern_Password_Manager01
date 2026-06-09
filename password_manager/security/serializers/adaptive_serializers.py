"""
DRF Serializers for Adaptive Password Feature
==============================================

Serializers for REST API endpoints.
"""

from collections.abc import Mapping

from rest_framework import serializers
from rest_framework.exceptions import APIException
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
            'length_bucket',
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


# =============================================================================
# Password Adaptation Serializers
# =============================================================================
#
# NOTE: the legacy v1 input serializers (TypingSessionInputSerializer,
# SubstitutionSerializer, AdaptationSuggestionSerializer, ApplyAdaptationSerializer)
# were removed in the zero-knowledge v2 cleanup — they accepted/echoed raw
# passwords and class-level substitutions with positions. The v2 serializers
# (TypingSessionInputV2Serializer / ApplyAdaptationV2Serializer) are the only
# inputs now.

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


# =============================================================================
# Zero-Knowledge v2 Serializers (PR-3)
# =============================================================================
#
# The v2 wire contract removes raw password material from every adaptive
# endpoint. The client sends a *keyed fingerprint* (opaque to the server) plus
# coarse, non-reversible features; suggestions are generated client-side from a
# downloaded preference model. See docs/adaptive-password-zk-remediation-plan.md
# (§4 wire contracts, §6 backend changes).

# Schema version the v2 endpoints accept. Anything else is a "client upgrade
# required" error (never a silent fallback to accepting plaintext).
ZK_SCHEMA_VERSION = 2

# Raw-password fields that must NEVER appear on an adaptive request body.
# Rejected fail-closed (HTTP 422) as defense-in-depth, independent of any flag.
FORBIDDEN_PLAINTEXT_FIELDS = ('password', 'original_password', 'adapted_password')

# A client fingerprint is unpadded base64url (see cryptoService.passwordFingerprint,
# which emits 24 chars / 144 bits); allow a small range for forward-compat.
FINGERPRINT_REGEX = r'^[A-Za-z0-9_-]{16,64}$'


class PlaintextRejected(APIException):
    """Raised when a forbidden raw-password field is present (fail-closed).

    Returns HTTP 422 to make the zero-knowledge violation explicit and
    distinct from ordinary validation errors (400).
    """

    status_code = 422
    default_detail = (
        'Raw password material is not allowed on adaptive endpoints. '
        'Send a client-computed fingerprint instead (zero-knowledge).'
    )
    default_code = 'plaintext_rejected'


def _fingerprint_field(**kwargs):
    """Build a CharField validating the base64url fingerprint charset/length."""
    return serializers.RegexField(
        FINGERPRINT_REGEX,
        error_messages={
            'invalid': 'Must be an unpadded base64url fingerprint (16-64 chars).',
        },
        **kwargs,
    )


def _validate_substitution_classes(value):
    """Validate a list of class-level substitutions: ``{from, to[, confidence]}``.

    Only single-character substitution *classes* are allowed — never positions
    or full strings — so nothing password-revealing crosses the wire.
    """
    if not isinstance(value, list):
        raise serializers.ValidationError('Expected a list of substitution classes.')
    allowed_keys = {'from', 'to', 'confidence'}
    cleaned = []
    for item in value:
        if not isinstance(item, Mapping):
            raise serializers.ValidationError('Each substitution must be an object.')
        # Fail closed on any field outside the class-level contract, so no
        # position/char metadata that could reveal the password slips through.
        extra = set(item.keys()) - allowed_keys
        if extra:
            raise serializers.ValidationError(
                f"Unexpected substitution field(s): {', '.join(sorted(extra))}."
            )
        from_char = item.get('from')
        to_char = item.get('to')
        if not isinstance(from_char, str) or len(from_char) != 1:
            raise serializers.ValidationError("Each substitution needs a single-char 'from'.")
        if not isinstance(to_char, str) or len(to_char) != 1:
            raise serializers.ValidationError("Each substitution needs a single-char 'to'.")
        entry = {'from': from_char, 'to': to_char}
        if 'confidence' in item:
            try:
                conf = float(item['confidence'])
            except (TypeError, ValueError):
                raise serializers.ValidationError("'confidence' must be a number.") from None
            if not 0.0 <= conf <= 1.0:
                raise serializers.ValidationError("'confidence' must be in [0, 1].")
            entry['confidence'] = conf
        cleaned.append(entry)
    return cleaned


class RejectPlaintextMixin:
    """Reject any request body carrying raw-password fields, fail-closed.

    The check runs in ``to_internal_value`` (before required-field checks) and
    raises :class:`PlaintextRejected` (422), so a forbidden field is rejected
    even when the rest of the payload is malformed. This is the serializer-level
    enforcement of the ZK invariant (remediation plan §1).
    """

    def to_internal_value(self, data):
        if isinstance(data, Mapping):
            present = [f for f in FORBIDDEN_PLAINTEXT_FIELDS if f in data]
            if present:
                raise PlaintextRejected(
                    f"Forbidden raw-password field(s): {', '.join(present)}."
                )
        return super().to_internal_value(data)


class SchemaVersionMixin:
    """Require ``schema_version == ZK_SCHEMA_VERSION`` (else 'client upgrade required').

    NOTE: DRF's serializer metaclass only collects *declared fields* from
    ``Serializer`` subclasses, not from a plain mixin — so concrete serializers
    must declare the ``schema_version`` field themselves. This mixin supplies
    the matching ``validate_schema_version`` (method lookup follows the MRO).
    """

    def validate_schema_version(self, value):
        if value != ZK_SCHEMA_VERSION:
            raise serializers.ValidationError(
                f'Client upgrade required: this endpoint accepts only '
                f'schema_version {ZK_SCHEMA_VERSION}.'
            )
        return value


class TypingSessionInputV2Serializer(
    RejectPlaintextMixin, SchemaVersionMixin, serializers.Serializer
):
    """v2 record-session input: fingerprint + coarse features, no password."""

    schema_version = serializers.IntegerField(required=True)
    password_fingerprint = _fingerprint_field(required=True)
    length_bucket = serializers.IntegerField(min_value=0, required=True)
    keystroke_timings = serializers.ListField(
        child=serializers.IntegerField(min_value=0, max_value=10000),
        allow_empty=True,
    )
    backspace_positions = serializers.ListField(
        child=serializers.IntegerField(min_value=0),
        allow_empty=True,
        required=False,
        default=list,
    )
    device_type = serializers.ChoiceField(
        choices=['desktop', 'mobile', 'tablet'], default='desktop'
    )
    input_method = serializers.ChoiceField(
        choices=['keyboard', 'touchscreen', 'voice'], default='keyboard'
    )
    substitution_classes_used = serializers.ListField(
        child=serializers.DictField(), required=False, default=list
    )
    # Explicit session outcome (was the password ultimately entered correctly?).
    # Optional for backward-compat; when omitted the service falls back to a
    # "no backspaces" heuristic.
    success = serializers.BooleanField(required=False, allow_null=True)

    def validate_substitution_classes_used(self, value):
        return _validate_substitution_classes(value)


class ApplyAdaptationV2Serializer(
    RejectPlaintextMixin, SchemaVersionMixin, serializers.Serializer
):
    """v2 apply input: original/adapted fingerprints + class-level subs only."""

    schema_version = serializers.IntegerField(required=True)
    original_fingerprint = _fingerprint_field(required=True)
    adapted_fingerprint = _fingerprint_field(required=True)
    substitutions = serializers.ListField(child=serializers.DictField(), required=True)
    previews = serializers.DictField(required=False)
    memorability_improvement = serializers.FloatField(
        required=False, min_value=-1.0, max_value=1.0
    )

    def validate_substitutions(self, value):
        return _validate_substitution_classes(value)

    def validate_previews(self, value):
        # Previews are masked client-side; only accept the two masked strings.
        allowed = {'original_masked', 'adapted_masked'}
        extra = set(value.keys()) - allowed
        if extra:
            raise serializers.ValidationError(
                f'Unexpected preview field(s): {", ".join(sorted(extra))}.'
            )
        for key, masked in value.items():
            if not isinstance(masked, str) or not 0 < len(masked) <= 64:
                raise serializers.ValidationError(f'{key} must be a short masked string.')
            # Must actually be masked — a mask character is required so plaintext
            # can never be persisted as a "preview" (zero-knowledge guarantee).
            if '*' not in masked:
                raise serializers.ValidationError(
                    f'{key} must be a masked preview (contain "*"), not plaintext.'
                )
        return value

    def validate(self, data):
        if data['original_fingerprint'] == data['adapted_fingerprint']:
            raise serializers.ValidationError(
                'Adapted fingerprint must differ from the original.'
            )
        return data


class PreferenceModelSerializer(serializers.Serializer):
    """Output serializer for the exported per-user preference model.

    Carries only aggregate, non-reversible learning signals (substitution-class
    weights + memorability params) — never any password-derived data.
    """

    model_version = serializers.IntegerField()
    substitution_weights = serializers.DictField(
        child=serializers.DictField(child=serializers.FloatField())
    )
    memorability_params = serializers.DictField()
