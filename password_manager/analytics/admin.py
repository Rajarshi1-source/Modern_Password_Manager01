"""
Analytics Admin Interface
=========================

Admin configuration for analytics models.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Avg
from .models import (
    AnalyticsEvent,
    UserEngagement,
    Conversion,
    UserSession,
    PerformanceMetric,
    Funnel,
    FunnelCompletion,
    CohortDefinition
)


@admin.register(AnalyticsEvent)
class AnalyticsEventAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'user', 'session_id_short', 'path', 'timestamp']
    list_filter = ['category', 'timestamp', 'created_at']
    search_fields = ['name', 'session_id', 'user__username', 'path']
    readonly_fields = ['id', 'created_at', 'timestamp']
    date_hierarchy = 'timestamp'
    
    fieldsets = (
        ('Event Details', {
            'fields': ('id', 'name', 'category', 'properties')
        }),
        ('User Context', {
            'fields': ('user', 'session_id')
        }),
        ('Context', {
            'fields': ('url', 'path', 'referrer')
        }),
        ('Metadata', {
            'fields': ('user_agent', 'ip_address', 'language', 'platform')
        }),
        ('Timestamps', {
            'fields': ('timestamp', 'created_at')
        }),
    )
    
    def session_id_short(self, obj):
        return obj.session_id[:20] + '...' if len(obj.session_id) > 20 else obj.session_id
    session_id_short.short_description = 'Session ID'


@admin.register(UserEngagement)
class UserEngagementAdmin(admin.ModelAdmin):
    list_display = ['metric', 'value', 'user', 'session_id_short', 'timestamp']
    list_filter = ['metric', 'timestamp']
    search_fields = ['metric', 'session_id', 'user__username']
    readonly_fields = ['id', 'created_at', 'timestamp']
    date_hierarchy = 'timestamp'
    
    def session_id_short(self, obj):
        return obj.session_id[:20] + '...' if len(obj.session_id) > 20 else obj.session_id
    session_id_short.short_description = 'Session ID'


@admin.register(Conversion)
class ConversionAdmin(admin.ModelAdmin):
    list_display = ['name', 'value_formatted', 'user', 'session_id_short', 'timestamp']
    list_filter = ['name', 'timestamp']
    search_fields = ['name', 'session_id', 'user__username']
    readonly_fields = ['id', 'created_at', 'timestamp']
    date_hierarchy = 'timestamp'
    
    def value_formatted(self, obj):
        return f'${obj.value:.2f}' if obj.value else '$0.00'
    value_formatted.short_description = 'Value'
    value_formatted.admin_order_field = 'value'
    
    def session_id_short(self, obj):
        return obj.session_id[:20] + '...' if len(obj.session_id) > 20 else obj.session_id
    session_id_short.short_description = 'Session ID'


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    list_display = [
        'session_id_short',
        'user',
        'start_time',
        'duration_formatted',
        'page_views',
        'event_count',
        'is_engaged_badge',
        'device_type'
    ]
    list_filter = ['device_type', 'browser', 'os', 'is_engaged', 'is_bounce', 'start_time']
    search_fields = ['session_id', 'user__username', 'ip_address']
    readonly_fields = ['id', 'created_at', 'updated_at']
    date_hierarchy = 'start_time'
    
    fieldsets = (
        ('Session Details', {
            'fields': ('id', 'user', 'session_id', 'start_time', 'end_time', 'duration')
        }),
        ('Session Data', {
            'fields': ('page_views', 'event_count', 'feature_usage', 'user_journey')
        }),
        ('Context', {
            'fields': ('referrer', 'landing_page', 'exit_page')
        }),
        ('Device Info', {
            'fields': ('user_agent', 'ip_address', 'device_type', 'browser', 'os', 'screen_resolution')
        }),
        ('Engagement', {
            'fields': ('is_bounce', 'is_engaged')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def session_id_short(self, obj):
        return obj.session_id[:15] + '...' if len(obj.session_id) > 15 else obj.session_id
    session_id_short.short_description = 'Session'
    
    def duration_formatted(self, obj):
        if obj.duration:
            minutes = obj.duration // 60
            seconds = obj.duration % 60
            return f'{minutes}m {seconds}s'
        return 'N/A'
    duration_formatted.short_description = 'Duration'
    duration_formatted.admin_order_field = 'duration'
    
    def is_engaged_badge(self, obj):
        if obj.is_engaged:
            return format_html('<span style="color: green;">✓ Engaged</span>')
        return format_html('<span style="color: gray;">Not Engaged</span>')
    is_engaged_badge.short_description = 'Engagement'


@admin.register(PerformanceMetric)
class PerformanceMetricAdmin(admin.ModelAdmin):
    list_display = ['metric_type', 'metric_name', 'value_formatted', 'user', 'timestamp']
    list_filter = ['metric_type', 'timestamp']
    search_fields = ['metric_type', 'metric_name', 'session_id', 'user__username']
    readonly_fields = ['id', 'created_at', 'timestamp']
    date_hierarchy = 'timestamp'
    
    def value_formatted(self, obj):
        return f'{obj.value:.2f}ms'
    value_formatted.short_description = 'Value'
    value_formatted.admin_order_field = 'value'


@admin.register(Funnel)
class FunnelAdmin(admin.ModelAdmin):
    list_display = ['name', 'steps_count', 'active_badge', 'completion_rate', 'created_at']
    list_filter = ['active', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Funnel Details', {
            'fields': ('id', 'name', 'description')
        }),
        ('Steps', {
            'fields': ('steps',)
        }),
        ('Configuration', {
            'fields': ('active',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at')
        }),
    )
    
    def steps_count(self, obj):
        return len(obj.steps)
    steps_count.short_description = '# Steps'
    
    def active_badge(self, obj):
        if obj.active:
            return format_html('<span style="color: green;">✓ Active</span>')
        return format_html('<span style="color: red;">✗ Inactive</span>')
    active_badge.short_description = 'Status'
    
    def completion_rate(self, obj):
        total = obj.completions.count()
        if total == 0:
            return 'N/A'
        completed = obj.completions.filter(completed=True).count()
        rate = (completed / total) * 100
        return f'{rate:.1f}%'
    completion_rate.short_description = 'Completion Rate'


@admin.register(FunnelCompletion)
class FunnelCompletionAdmin(admin.ModelAdmin):
    list_display = [
        'funnel',
        'user',
        'completed_badge',
        'abandoned_at_step',
        'duration_formatted',
        'start_time'
    ]
    list_filter = ['completed', 'funnel', 'start_time']
    search_fields = ['funnel__name', 'session_id', 'user__username']
    readonly_fields = ['id', 'created_at', 'updated_at']
    date_hierarchy = 'start_time'
    
    def completed_badge(self, obj):
        if obj.completed:
            return format_html('<span style="color: green;">✓ Completed</span>')
        return format_html('<span style="color: orange;">✗ Abandoned</span>')
    completed_badge.short_description = 'Status'
    
    def duration_formatted(self, obj):
        if obj.duration:
            minutes = obj.duration // 60
            seconds = obj.duration % 60
            return f'{minutes}m {seconds}s'
        return 'N/A'
    duration_formatted.short_description = 'Duration'
    duration_formatted.admin_order_field = 'duration'


@admin.register(CohortDefinition)
class CohortDefinitionAdmin(admin.ModelAdmin):
    list_display = ['name', 'user_count', 'active_badge', 'last_calculated', 'created_at']
    list_filter = ['active', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['id', 'user_count', 'last_calculated', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Cohort Details', {
            'fields': ('id', 'name', 'description')
        }),
        ('Criteria', {
            'fields': ('criteria',)
        }),
        ('Configuration', {
            'fields': ('active',)
        }),
        ('Statistics', {
            'fields': ('user_count', 'last_calculated')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at')
        }),
    )
    
    def active_badge(self, obj):
        if obj.active:
            return format_html('<span style="color: green;">✓ Active</span>')
        return format_html('<span style="color: red;">✗ Inactive</span>')
    active_badge.short_description = 'Status'

