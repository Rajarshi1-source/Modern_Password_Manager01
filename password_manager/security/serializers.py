from rest_framework import serializers
from .models import (
    SocialMediaAccount, LoginAttempt, UserDevice,
    SecurityAlert, UserNotificationSettings, AccountLockEvent
)

class SocialMediaAccountSerializer(serializers.ModelSerializer):
    """Serializer for social media accounts"""
    class Meta:
        model = SocialMediaAccount
        fields = [
            'id', 'platform', 'username', 'email', 'account_id',
            'status', 'auto_lock_enabled', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

class LoginAttemptSerializer(serializers.ModelSerializer):
    """Serializer for login attempts"""
    user_display = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = LoginAttempt
        fields = [
            'id', 'user', 'user_display', 'username_attempted',
            'ip_address', 'user_agent', 'location', 'status',
            'failure_reason', 'is_suspicious', 'threat_score',
            'timestamp'
        ]
        read_only_fields = ['id', 'user_display', 'timestamp']

class UserDeviceSerializer(serializers.ModelSerializer):
    """Serializer for user devices"""
    class Meta:
        model = UserDevice
        fields = [
            'id', 'device_id', 'device_name', 'device_type',
            'browser', 'os', 'ip_address', 'is_trusted',
            'last_seen', 'created_at'
        ]
        read_only_fields = ['id', 'device_id', 'last_seen', 'created_at']

class SecurityAlertSerializer(serializers.ModelSerializer):
    """Serializer for security alerts"""
    user_display = serializers.CharField(source='user.username', read_only=True)
    alert_type_display = serializers.CharField(source='get_alert_type_display', read_only=True)
    severity_display = serializers.CharField(source='get_severity_display', read_only=True)
    
    class Meta:
        model = SecurityAlert
        fields = [
            'id', 'user', 'user_display', 'alert_type', 'alert_type_display',
            'severity', 'severity_display', 'title', 'message', 'data',
            'is_read', 'is_resolved', 'created_at', 'resolved_at'
        ]
        read_only_fields = [
            'id', 'user_display', 'alert_type_display', 'severity_display',
            'created_at', 'resolved_at'
        ]

class UserNotificationSettingsSerializer(serializers.ModelSerializer):
    """Serializer for user notification settings"""
    class Meta:
        model = UserNotificationSettings
        fields = [
            'id', 'email_alerts', 'sms_alerts', 'push_alerts', 'auto_lock_accounts',
            'suspicious_activity_threshold', 'alert_cooldown_minutes', 'phone_number',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

class AccountLockEventSerializer(serializers.ModelSerializer):
    """Serializer for account lock events"""
    user_display = serializers.CharField(source='user.username', read_only=True)
    social_account_display = serializers.CharField(source='social_account.platform', read_only=True)
    
    class Meta:
        model = AccountLockEvent
        fields = [
            'id', 'user', 'user_display', 'social_account', 'social_account_display',
            'action', 'reason', 'triggered_by_alert', 'auto_triggered',
            'success', 'timestamp'
        ]
        read_only_fields = [
            'id', 'user_display', 'social_account_display', 'timestamp'
        ] 