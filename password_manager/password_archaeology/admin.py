"""
Password Archaeology Admin
============================
"""

from django.contrib import admin
from .models import (
    PasswordHistoryEntry,
    SecurityEvent,
    StrengthSnapshot,
    PasswordTimeline,
    AchievementRecord,
    WhatIfScenario,
)


@admin.register(PasswordHistoryEntry)
class PasswordHistoryEntryAdmin(admin.ModelAdmin):
    list_display = [
        'credential_domain', 'user', 'trigger',
        'strength_before', 'strength_after', 'changed_at',
    ]
    list_filter = ['trigger', 'changed_at']
    search_fields = ['credential_domain', 'credential_label', 'user__username']
    readonly_fields = ['id', 'commitment_hash', 'created_at']
    date_hierarchy = 'changed_at'


@admin.register(SecurityEvent)
class SecurityEventAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'user', 'event_type', 'severity',
        'resolved', 'occurred_at',
    ]
    list_filter = ['event_type', 'severity', 'resolved', 'occurred_at']
    search_fields = ['title', 'description', 'user__username']
    readonly_fields = ['id', 'created_at']
    date_hierarchy = 'occurred_at'


@admin.register(StrengthSnapshot)
class StrengthSnapshotAdmin(admin.ModelAdmin):
    list_display = [
        'credential_domain', 'user', 'strength_score',
        'entropy_bits', 'breach_exposure_count', 'snapshot_at',
    ]
    list_filter = ['snapshot_at', 'is_reused']
    search_fields = ['credential_domain', 'user__username']
    readonly_fields = ['id']
    date_hierarchy = 'snapshot_at'


@admin.register(PasswordTimeline)
class PasswordTimelineAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'current_overall_score', 'total_credentials_tracked',
        'total_password_changes', 'average_strength_score',
        'last_computed_at',
    ]
    search_fields = ['user__username']
    readonly_fields = ['last_computed_at', 'created_at']


@admin.register(AchievementRecord)
class AchievementRecordAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'user', 'achievement_type', 'badge_tier',
        'score_points', 'acknowledged', 'earned_at',
    ]
    list_filter = ['achievement_type', 'badge_tier', 'acknowledged']
    search_fields = ['title', 'user__username']
    readonly_fields = ['id', 'earned_at']


@admin.register(WhatIfScenario)
class WhatIfScenarioAdmin(admin.ModelAdmin):
    list_display = [
        'credential_domain', 'user', 'scenario_type',
        'actual_risk_score', 'simulated_risk_score',
        'risk_reduction', 'created_at',
    ]
    list_filter = ['scenario_type', 'created_at']
    search_fields = ['credential_domain', 'user__username']
    readonly_fields = ['id', 'created_at']
