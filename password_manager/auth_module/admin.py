from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.urls import reverse
from django.db.models import Count, Avg, Q
from django.utils import timezone
from datetime import timedelta

from .quantum_recovery_models import (
    PasskeyRecoverySetup,
    RecoveryShard,
    RecoveryGuardian,
    RecoveryAttempt,
    TemporalChallenge,
    GuardianApproval,
    RecoveryAuditLog,
    BehavioralBiometrics
)


@admin.register(PasskeyRecoverySetup)
class PasskeyRecoverySetupAdmin(admin.ModelAdmin):
    list_display = [
        'user_email', 'is_active', 'total_shards', 'threshold_shards',
        'guardian_count', 'created_at'
    ]
    list_filter = ['is_active', 'created_at']
    search_fields = ['user__email']
    readonly_fields = [
        'user', 'kyber_private_key_encrypted',
        'created_at', 'updated_at'
    ]
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User Email'
    
    def guardian_count(self, obj):
        count = obj.guardians.filter(status='active').count()
        return f"{count}/{obj.total_shards}"
    guardian_count.short_description = 'Active Guardians'


@admin.register(RecoveryShard)
class RecoveryShardAdmin(admin.ModelAdmin):
    list_display = [
        'shard_index', 'shard_type', 'user_email',
        'is_honeypot', 'access_count', 'created_at'
    ]
    list_filter = ['shard_type', 'is_honeypot', 'created_at']
    search_fields = ['recovery_setup__user__email']
    readonly_fields = [
        'recovery_setup', 'shard_index', 'encrypted_shard_data',
        'encryption_metadata', 'created_at', 'updated_at'
    ]
    
    def user_email(self, obj):
        return obj.recovery_setup.user.email
    user_email.short_description = 'User'


@admin.register(RecoveryGuardian)
class RecoveryGuardianAdmin(admin.ModelAdmin):
    list_display = [
        'user_email', 'guardian_email_display', 'status',
        'requires_video_verification', 'total_recoveries',
        'created_at'
    ]
    list_filter = ['status', 'requires_video_verification', 'created_at']
    search_fields = ['recovery_setup__user__email']
    readonly_fields = [
        'recovery_setup', 'invitation_token', 'guardian_public_key',
        'invitation_sent_at', 'accepted_at'
    ]
    
    def user_email(self, obj):
        return obj.recovery_setup.user.email
    user_email.short_description = 'User'
    
    def guardian_email_display(self, obj):
        try:
            email = obj.encrypted_guardian_info.decode('utf-8')
            return email[:20] + '...' if len(email) > 20 else email
        except:
            return '[Encrypted]'
    guardian_email_display.short_description = 'Guardian Email'
    
    def total_recoveries(self, obj):
        return obj.total_recoveries_assisted
    total_recoveries.short_description = 'Recoveries Assisted'


@admin.register(RecoveryAttempt)
class RecoveryAttemptAdmin(admin.ModelAdmin):
    list_display = [
        'id_short', 'user_email', 'status', 'trust_score_display',
        'challenges_progress', 'initiated_at', 'honeypot_status',
        'recovery_result'
    ]
    list_filter = [
        'status', 'recovery_successful', 'honeypot_triggered',
        'suspicious_activity_detected', 'initiated_at'
    ]
    search_fields = ['recovery_setup__user__email', 'initiated_from_ip']
    readonly_fields = [
        'recovery_setup', 'trust_score',
        'initiated_at', 'completed_at'
    ]
    date_hierarchy = 'initiated_at'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('recovery_setup', 'status', 'initiated_at', 'completed_at')
        }),
        ('Challenge Tracking', {
            'fields': (
                'challenges_sent', 'challenges_completed', 'challenges_failed',
                'challenge_success_rate'
            )
        }),
        ('Trust Scoring', {
            'fields': (
                'trust_score', 'device_recognition_score',
                'behavioral_match_score', 'temporal_consistency_score'
            )
        }),
        ('Security Context', {
            'fields': (
                'initiated_from_ip', 'initiated_from_device_fingerprint',
                'initiated_from_location', 'initiated_from_user_agent'
            )
        }),
        ('Security Alerts', {
            'fields': (
                'honeypot_triggered', 'suspicious_activity_detected',
                'suspicious_activity_details', 'canary_alert_sent_at',
                'canary_alert_acknowledged'
            )
        }),
        ('Recovery Result', {
            'fields': ('recovery_successful', 'failure_reason', 'forensic_log')
        }),
    )
    
    def id_short(self, obj):
        return str(obj.id)[:8] + '...'
    id_short.short_description = 'ID'
    
    def user_email(self, obj):
        return obj.recovery_setup.user.email
    user_email.short_description = 'User'
    
    def trust_score_display(self, obj):
        score = obj.trust_score * 100
        if score >= 70:
            color = 'green'
            icon = '✅'
        elif score >= 50:
            color = 'orange'
            icon = '⚠️'
        else:
            color = 'red'
            icon = '❌'
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} {:.1f}%</span>',
            color, icon, score
        )
    trust_score_display.short_description = 'Trust Score'
    
    def challenges_progress(self, obj):
        if obj.challenges_sent == 0:
            return '0/0'
        
        percentage = (obj.challenges_completed / obj.challenges_sent) * 100
        color = 'green' if percentage >= 80 else 'orange' if percentage >= 60 else 'red'
        
        return format_html(
            '<span style="color: {};">{}/{} ({:.0f}%)</span>',
            color, obj.challenges_completed, obj.challenges_sent, percentage
        )
    challenges_progress.short_description = 'Challenges'
    
    def honeypot_status(self, obj):
        if obj.honeypot_triggered:
            return format_html('<span style="color: red; font-weight: bold;">⚠️ TRIGGERED</span>')
        return format_html('<span style="color: green;">✅ Clean</span>')
    honeypot_status.short_description = 'Honeypot'
    
    def recovery_result(self, obj):
        if obj.status == 'completed':
            if obj.recovery_successful:
                return format_html('<span style="color: green; font-weight: bold;">✅ Success</span>')
            else:
                return format_html('<span style="color: red;">❌ Failed</span>')
        elif obj.status == 'failed':
            return format_html('<span style="color: red;">❌ Failed</span>')
        elif obj.status == 'cancelled':
            return format_html('<span style="color: orange;">🚫 Cancelled</span>')
        else:
            return format_html('<span style="color: gray;">⏳ In Progress</span>')
    recovery_result.short_description = 'Result'


@admin.register(TemporalChallenge)
class TemporalChallengeAdmin(admin.ModelAdmin):
    list_display = [
        'challenge_type', 'recovery_user_email', 'status',
        'is_correct_display', 'response_time_display',
        'expected_response_time_window_start'
    ]
    list_filter = ['challenge_type', 'status', 'delivery_channel', 'created_at']
    search_fields = ['recovery_attempt__recovery_setup__user__email']
    readonly_fields = [
        'recovery_attempt', 'encrypted_challenge_data',
        'encrypted_expected_response', 'expected_response_time_window_start', 'sent_at',
        'response_received_at', 'expires_at'
    ]
    date_hierarchy = 'created_at'
    
    def recovery_user_email(self, obj):
        return obj.recovery_attempt.recovery_setup.user.email
    recovery_user_email.short_description = 'User'
    
    def is_correct_display(self, obj):
        if obj.response_correct is None:
            return '-'
        if obj.response_correct:
            return format_html('<span style="color: green;">✅ Correct</span>')
        return format_html('<span style="color: red;">❌ Incorrect</span>')
    is_correct_display.short_description = 'Response'
    
    def response_time_display(self, obj):
        if not obj.actual_response_time_seconds:
            return '-'
        
        seconds = obj.actual_response_time_seconds
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            return f"{seconds // 60}m {seconds % 60}s"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours}h {minutes}m"
    response_time_display.short_description = 'Response Time'


@admin.register(GuardianApproval)
class GuardianApprovalAdmin(admin.ModelAdmin):
    list_display = [
        'guardian_email_display', 'recovery_user_email', 'status',
        'requires_video', 'responded_at', 'shard_released'
    ]
    list_filter = ['status', 'shard_released', 'requested_at']
    search_fields = [
        'recovery_attempt__recovery_setup__user__email',
        'guardian__encrypted_guardian_info'
    ]
    readonly_fields = [
        'recovery_attempt', 'guardian', 'approval_token',
        'approval_window_start', 'approval_window_end',
        'responded_at', 'requested_at'
    ]
    
    def guardian_email_display(self, obj):
        try:
            email = obj.guardian.encrypted_guardian_info.decode('utf-8')
            return email[:30] + '...' if len(email) > 30 else email
        except:
            return '[Encrypted]'
    guardian_email_display.short_description = 'Guardian'
    
    def recovery_user_email(self, obj):
        return obj.recovery_attempt.recovery_setup.user.email
    recovery_user_email.short_description = 'User'
    
    def requires_video(self, obj):
        return '📹 Yes' if obj.guardian.requires_video_verification else 'No'
    requires_video.short_description = 'Video Required'


@admin.register(RecoveryAuditLog)
class RecoveryAuditLogAdmin(admin.ModelAdmin):
    list_display = [
        'timestamp', 'user_email', 'event_type', 'ip_address',
        'recovery_attempt_link'
    ]
    list_filter = ['event_type', 'timestamp']
    search_fields = ['user__email', 'ip_address', 'event_type']
    readonly_fields = [
        'user', 'event_type', 'recovery_attempt_id', 'event_data',
        'ip_address', 'user_agent', 'timestamp'
    ]
    date_hierarchy = 'timestamp'
    
    def user_email(self, obj):
        return obj.user.email if obj.user else 'N/A'
    user_email.short_description = 'User'
    
    def recovery_attempt_link(self, obj):
        if obj.recovery_attempt_id:
            url = reverse('admin:auth_module_recoveryattempt_change', args=[obj.recovery_attempt_id])
            return format_html('<a href="{}">View Attempt</a>', url)
        return '-'
    recovery_attempt_link.short_description = 'Recovery Attempt'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


@admin.register(BehavioralBiometrics)
class BehavioralBiometricsAdmin(admin.ModelAdmin):
    list_display = [
        'user_email', 'typical_login_times_display',
        'typical_locations_count', 'last_updated'
    ]
    list_filter = ['last_updated']
    search_fields = ['user__email']
    readonly_fields = [
        'user', 'typical_login_times', 'typical_locations',
        'keystroke_dynamics', 'mouse_movement_patterns',
        'last_updated'
    ]
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User'
    
    def typical_login_times_display(self, obj):
        if not obj.typical_login_times:
            return 'No data'
        
        hours = sorted(obj.typical_login_times)[:5]  # Show first 5
        time_str = ', '.join([f"{h}:00" for h in hours])
        if len(obj.typical_login_times) > 5:
            time_str += '...'
        return time_str
    typical_login_times_display.short_description = 'Typical Times'
    
    def typical_locations_count(self, obj):
        if not obj.typical_locations:
            return 0
        return len(obj.typical_locations)
    typical_locations_count.short_description = 'Locations'
