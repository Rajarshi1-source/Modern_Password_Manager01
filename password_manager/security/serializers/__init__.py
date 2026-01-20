"""
__init__.py for security serializers package

This module exports serializers from both the modular package files
AND makes legacy serializers available from the parent directory.
"""

from rest_framework import serializers

# Lazy import function to avoid circular imports
def _get_models():
    """Lazy import security models."""
    from security.models import (
        SocialMediaAccount, LoginAttempt, UserDevice,
        SecurityAlert, UserNotificationSettings, AccountLockEvent
    )
    return {
        'SocialMediaAccount': SocialMediaAccount,
        'LoginAttempt': LoginAttempt,
        'UserDevice': UserDevice,
        'SecurityAlert': SecurityAlert,
        'UserNotificationSettings': UserNotificationSettings,
        'AccountLockEvent': AccountLockEvent,
    }


# ============================================================================
# Legacy Serializers (originally defined in security/serializers.py)
# These are needed by security/views.py
# ============================================================================

class SocialMediaAccountSerializer(serializers.ModelSerializer):
    """Serializer for social media accounts"""
    class Meta:
        model = property(lambda self: _get_models()['SocialMediaAccount'])
        fields = [
            'id', 'platform', 'username', 'email', 'account_id',
            'status', 'auto_lock_enabled', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def __init__(self, *args, **kwargs):
        # Set model dynamically to support lazy loading
        self.Meta.model = _get_models()['SocialMediaAccount']
        super().__init__(*args, **kwargs)


class LoginAttemptSerializer(serializers.ModelSerializer):
    """Serializer for login attempts"""
    user_display = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = property(lambda self: _get_models()['LoginAttempt'])
        fields = [
            'id', 'user', 'user_display', 'username_attempted',
            'ip_address', 'user_agent', 'location', 'status',
            'failure_reason', 'is_suspicious', 'threat_score',
            'timestamp'
        ]
        read_only_fields = ['id', 'user_display', 'timestamp']
    
    def __init__(self, *args, **kwargs):
        self.Meta.model = _get_models()['LoginAttempt']
        super().__init__(*args, **kwargs)


class UserDeviceSerializer(serializers.ModelSerializer):
    """Serializer for user devices"""
    class Meta:
        model = property(lambda self: _get_models()['UserDevice'])
        fields = [
            'id', 'device_id', 'device_name', 'device_type',
            'browser', 'os', 'ip_address', 'is_trusted',
            'last_seen', 'created_at'
        ]
        read_only_fields = ['id', 'device_id', 'last_seen', 'created_at']
    
    def __init__(self, *args, **kwargs):
        self.Meta.model = _get_models()['UserDevice']
        super().__init__(*args, **kwargs)


class SecurityAlertSerializer(serializers.ModelSerializer):
    """Serializer for security alerts"""
    user_display = serializers.CharField(source='user.username', read_only=True)
    alert_type_display = serializers.CharField(source='get_alert_type_display', read_only=True)
    severity_display = serializers.CharField(source='get_severity_display', read_only=True)
    
    class Meta:
        model = property(lambda self: _get_models()['SecurityAlert'])
        fields = [
            'id', 'user', 'user_display', 'alert_type', 'alert_type_display',
            'severity', 'severity_display', 'title', 'message', 'data',
            'is_read', 'is_resolved', 'created_at', 'resolved_at'
        ]
        read_only_fields = [
            'id', 'user_display', 'alert_type_display', 'severity_display',
            'created_at', 'resolved_at'
        ]
    
    def __init__(self, *args, **kwargs):
        self.Meta.model = _get_models()['SecurityAlert']
        super().__init__(*args, **kwargs)


class UserNotificationSettingsSerializer(serializers.ModelSerializer):
    """Serializer for user notification settings"""
    class Meta:
        model = property(lambda self: _get_models()['UserNotificationSettings'])
        fields = [
            'id', 'email_alerts', 'sms_alerts', 'push_alerts', 'auto_lock_accounts',
            'suspicious_activity_threshold', 'alert_cooldown_minutes', 'phone_number',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def __init__(self, *args, **kwargs):
        self.Meta.model = _get_models()['UserNotificationSettings']
        super().__init__(*args, **kwargs)


class AccountLockEventSerializer(serializers.ModelSerializer):
    """Serializer for account lock events"""
    user_display = serializers.CharField(source='user.username', read_only=True)
    social_account_display = serializers.CharField(source='social_account.platform', read_only=True)
    
    class Meta:
        model = property(lambda self: _get_models()['AccountLockEvent'])
        fields = [
            'id', 'user', 'user_display', 'social_account', 'social_account_display',
            'action', 'reason', 'triggered_by_alert', 'auto_triggered',
            'success', 'timestamp'
        ]
        read_only_fields = [
            'id', 'user_display', 'social_account_display', 'timestamp'
        ]
    
    def __init__(self, *args, **kwargs):
        self.Meta.model = _get_models()['AccountLockEvent']
        super().__init__(*args, **kwargs)


# ============================================================================
# Adaptive Serializers
# ============================================================================

try:
    from .adaptive_serializers import (
        AdaptivePasswordConfigSerializer,
        EnableAdaptivePasswordSerializer,
        TypingSessionSerializer,
        TypingSessionInputSerializer,
        PasswordAdaptationSerializer,
        AdaptationSuggestionSerializer,
        ApplyAdaptationSerializer,
        RollbackAdaptationSerializer,
        UserTypingProfileSerializer,
        TypingProfileSummarySerializer,
        AdaptationFeedbackSerializer,
        SubmitFeedbackSerializer,
        EvolutionStatsSerializer,
        DataExportSerializer,
    )
    ADAPTIVE_AVAILABLE = True
except ImportError as e:
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"Could not import adaptive serializers: {e}")
    ADAPTIVE_AVAILABLE = False


__all__ = [
    # Legacy serializers
    'SocialMediaAccountSerializer',
    'LoginAttemptSerializer',
    'UserDeviceSerializer',
    'SecurityAlertSerializer',
    'UserNotificationSettingsSerializer',
    'AccountLockEventSerializer',
]

# Add adaptive serializers to exports
if ADAPTIVE_AVAILABLE:
    __all__.extend([
        'AdaptivePasswordConfigSerializer',
        'EnableAdaptivePasswordSerializer',
        'TypingSessionSerializer',
        'TypingSessionInputSerializer',
        'PasswordAdaptationSerializer',
        'AdaptationSuggestionSerializer',
        'ApplyAdaptationSerializer',
        'RollbackAdaptationSerializer',
        'UserTypingProfileSerializer',
        'TypingProfileSummarySerializer',
        'AdaptationFeedbackSerializer',
        'SubmitFeedbackSerializer',
        'EvolutionStatsSerializer',
        'DataExportSerializer',
    ])
