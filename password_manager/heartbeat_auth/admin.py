from django.contrib import admin

from .models import (
    HeartbeatEvent,
    HeartbeatProfile,
    HeartbeatReading,
    HeartbeatSession,
)


@admin.register(HeartbeatProfile)
class HeartbeatProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'status', 'enrollment_count',
                    'baseline_rmssd', 'baseline_mean_hr',
                    'match_threshold', 'updated_at')
    list_filter = ('status',)
    search_fields = ('user__email',)
    readonly_fields = ('enrolled_at', 'updated_at')


@admin.register(HeartbeatSession)
class HeartbeatSessionAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'session_type', 'status',
                    'match_score', 'duress_detected', 'created_at')
    list_filter = ('session_type', 'status', 'duress_detected')
    search_fields = ('user__email', 'id')
    readonly_fields = ('id', 'created_at', 'completed_at')


@admin.register(HeartbeatReading)
class HeartbeatReadingAdmin(admin.ModelAdmin):
    list_display = ('id', 'session', 'rmssd', 'sdnn',
                    'mean_hr', 'pnn50', 'captured_at')
    search_fields = ('session__id',)


@admin.register(HeartbeatEvent)
class HeartbeatEventAdmin(admin.ModelAdmin):
    list_display = ('id', 'session', 'decision', 'reason', 'ip', 'created_at')
    list_filter = ('decision',)
    search_fields = ('session__id', 'ip')
