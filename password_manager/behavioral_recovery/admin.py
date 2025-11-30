"""
Django Admin Configuration for Behavioral Recovery
"""

from django.contrib import admin
from django.utils.html import format_html
from .models import (
    BehavioralCommitment,
    BehavioralRecoveryAttempt,
    BehavioralChallenge,
    BehavioralProfileSnapshot,
    RecoveryAuditLog
)


@admin.register(BehavioralCommitment)
class BehavioralCommitmentAdmin(admin.ModelAdmin):
    list_display = ['commitment_id_short', 'user', 'challenge_type', 'is_active', 'creation_timestamp', 'samples_used']
    list_filter = ['challenge_type', 'is_active', 'creation_timestamp']
    search_fields = ['user__username', 'user__email', 'commitment_id']
    readonly_fields = ['commitment_id', 'creation_timestamp', 'last_verified']
    
    def commitment_id_short(self, obj):
        return str(obj.commitment_id)[:8]
    commitment_id_short.short_description = 'ID'
    
    fieldsets = (
        ('User & Identity', {
            'fields': ('user', 'commitment_id')
        }),
        ('Behavioral Data', {
            'fields': ('encrypted_embedding', 'challenge_type', 'samples_used')
        }),
        ('Unlock Conditions', {
            'fields': ('unlock_conditions', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('creation_timestamp', 'last_verified')
        }),
    )


@admin.register(BehavioralRecoveryAttempt)
class BehavioralRecoveryAttemptAdmin(admin.ModelAdmin):
    list_display = [
        'attempt_id_short', 
        'user_or_email', 
        'status_badge', 
        'current_stage', 
        'progress',
        'overall_similarity_display',
        'started_at'
    ]
    list_filter = ['status', 'current_stage', 'started_at']
    search_fields = ['user__username', 'user__email', 'contact_email', 'attempt_id']
    readonly_fields = ['attempt_id', 'started_at', 'overall_similarity']
    
    def attempt_id_short(self, obj):
        return str(obj.attempt_id)[:8]
    attempt_id_short.short_description = 'ID'
    
    def user_or_email(self, obj):
        return obj.user.username if obj.user else obj.contact_email
    user_or_email.short_description = 'User'
    
    def status_badge(self, obj):
        colors = {
            'in_progress': 'blue',
            'completed': 'green',
            'failed': 'red',
            'abandoned': 'gray',
            'expired': 'orange',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def progress(self, obj):
        percentage = (obj.challenges_completed / obj.challenges_total * 100) if obj.challenges_total > 0 else 0
        return f"{obj.challenges_completed}/{obj.challenges_total} ({percentage:.0f}%)"
    progress.short_description = 'Progress'
    
    def overall_similarity_display(self, obj):
        if obj.overall_similarity is not None:
            score = obj.overall_similarity
            color = 'green' if score >= 0.87 else 'orange' if score >= 0.70 else 'red'
            return format_html(
                '<span style="color: {}; font-weight: bold;">{:.2f}</span>',
                color,
                score
            )
        return '-'
    overall_similarity_display.short_description = 'Similarity'
    
    fieldsets = (
        ('Identification', {
            'fields': ('user', 'attempt_id', 'contact_email')
        }),
        ('Timeline', {
            'fields': ('started_at', 'expected_completion_date', 'completed_at')
        }),
        ('Progress', {
            'fields': ('current_stage', 'status', 'challenges_completed', 'challenges_total', 'samples_collected')
        }),
        ('Behavioral Analysis', {
            'fields': ('similarity_scores', 'overall_similarity')
        }),
        ('Security Context', {
            'fields': ('ip_address', 'user_agent', 'device_fingerprint')
        }),
    )


@admin.register(BehavioralChallenge)
class BehavioralChallengeAdmin(admin.ModelAdmin):
    list_display = [
        'challenge_id_short',
        'recovery_attempt_short',
        'challenge_type',
        'similarity_display',
        'passed_badge',
        'completed_at',
        'time_taken_seconds'
    ]
    list_filter = ['challenge_type', 'passed', 'created_at']
    search_fields = ['challenge_id', 'recovery_attempt__attempt_id']
    readonly_fields = ['challenge_id', 'created_at', 'completed_at']
    
    def challenge_id_short(self, obj):
        return str(obj.challenge_id)[:8]
    challenge_id_short.short_description = 'Challenge ID'
    
    def recovery_attempt_short(self, obj):
        return str(obj.recovery_attempt.attempt_id)[:8]
    recovery_attempt_short.short_description = 'Attempt'
    
    def similarity_display(self, obj):
        if obj.similarity_score is not None:
            score = obj.similarity_score
            color = 'green' if score >= 0.87 else 'orange' if score >= 0.70 else 'red'
            return format_html(
                '<span style="color: {};">{:.3f}</span>',
                color,
                score
            )
        return '-'
    similarity_display.short_description = 'Similarity'
    
    def passed_badge(self, obj):
        if obj.passed is None:
            return '-'
        color = 'green' if obj.passed else 'red'
        text = '✓' if obj.passed else '✗'
        return format_html(
            '<span style="color: {}; font-size: 18px; font-weight: bold;">{}</span>',
            color,
            text
        )
    passed_badge.short_description = 'Passed'


@admin.register(BehavioralProfileSnapshot)
class BehavioralProfileSnapshotAdmin(admin.ModelAdmin):
    list_display = ['snapshot_id_short', 'user', 'period_range', 'samples_count', 'quality_score', 'created_at']
    list_filter = ['created_at', 'quality_score']
    search_fields = ['user__username', 'snapshot_id']
    readonly_fields = ['snapshot_id', 'created_at']
    
    def snapshot_id_short(self, obj):
        return str(obj.snapshot_id)[:8]
    snapshot_id_short.short_description = 'ID'
    
    def period_range(self, obj):
        return f"{obj.period_start.date()} to {obj.period_end.date()}"
    period_range.short_description = 'Period'


@admin.register(RecoveryAuditLog)
class RecoveryAuditLogAdmin(admin.ModelAdmin):
    list_display = [
        'timestamp',
        'event_type_badge',
        'recovery_attempt_short',
        'ip_address',
        'severity',
        'user_agent_short'
    ]
    list_filter = ['event_type', 'severity', 'timestamp']
    search_fields = ['recovery_attempt__attempt_id', 'ip_address', 'user_agent']
    readonly_fields = ['timestamp', 'event_type', 'recovery_attempt', 'severity', 'ip_address', 'user_agent', 'details']
    
    def event_type_badge(self, obj):
        colors = {
            'recovery_initiated': 'blue',
            'challenge_completed': 'green',
            'recovery_completed': 'green',
            'adversarial_detected': 'red',
            'replay_detected': 'red',
            'suspicious_activity': 'orange',
        }
        color = colors.get(obj.event_type, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 3px; font-size: 11px;">{}</span>',
            color,
            obj.get_event_type_display()
        )
    event_type_badge.short_description = 'Event'
    
    def recovery_attempt_short(self, obj):
        if obj.recovery_attempt:
            return str(obj.recovery_attempt.attempt_id)[:8]
        return '-'
    recovery_attempt_short.short_description = 'Attempt'
    
    def user_agent_short(self, obj):
        if obj.user_agent:
            return obj.user_agent[:50] + ('...' if len(obj.user_agent) > 50 else '')
        return '-'
    user_agent_short.short_description = 'User Agent'

