"""
A/B Testing Admin Interface
===========================

Admin configuration for A/B testing and feature flags.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Avg
from .models import (
    FeatureFlag,
    Experiment,
    ExperimentAssignment,
    ExperimentMetric,
    FeatureFlagUsage
)


@admin.register(FeatureFlag)
class FeatureFlagAdmin(admin.ModelAdmin):
    list_display = [
        'name',
        'enabled_badge',
        'enabled_for_all',
        'rollout_percentage',
        'usage_count',
        'created_at'
    ]
    list_filter = ['enabled', 'enabled_for_all', 'created_at']
    search_fields = ['name', 'description']
    filter_horizontal = ['enabled_for_users']
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Flag Details', {
            'fields': ('id', 'name', 'description')
        }),
        ('State', {
            'fields': ('enabled',)
        }),
        ('Targeting', {
            'fields': ('enabled_for_all', 'enabled_for_users', 'enabled_for_cohorts', 'rollout_percentage')
        }),
        ('Configuration', {
            'fields': ('config',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at')
        }),
    )
    
    def enabled_badge(self, obj):
        if obj.enabled:
            return format_html('<span style="color: green;">✓ Enabled</span>')
        return format_html('<span style="color: red;">✗ Disabled</span>')
    enabled_badge.short_description = 'Status'
    
    def usage_count(self, obj):
        return obj.usage_logs.count()
    usage_count.short_description = 'Usage Count'


@admin.register(Experiment)
class ExperimentAdmin(admin.ModelAdmin):
    list_display = [
        'name',
        'type',
        'status_badge',
        'active_badge',
        'assignment_count',
        'conversion_rate',
        'winner',
        'created_at'
    ]
    list_filter = ['type', 'status', 'active', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Experiment Details', {
            'fields': ('id', 'name', 'description', 'type')
        }),
        ('Status', {
            'fields': ('status', 'active')
        }),
        ('Configuration', {
            'fields': ('variants', 'traffic_allocation', 'targeting')
        }),
        ('Goals', {
            'fields': ('primary_goal', 'secondary_goals')
        }),
        ('Schedule', {
            'fields': ('start_date', 'end_date')
        }),
        ('Results', {
            'fields': ('results', 'winner', 'confidence')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at')
        }),
    )
    
    def status_badge(self, obj):
        colors = {
            'draft': 'gray',
            'running': 'green',
            'paused': 'orange',
            'completed': 'blue',
            'archived': 'gray'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(f'<span style="color: {color};">{obj.status.upper()}</span>')
    status_badge.short_description = 'Status'
    
    def active_badge(self, obj):
        if obj.active:
            return format_html('<span style="color: green;">✓ Active</span>')
        return format_html('<span style="color: red;">✗ Inactive</span>')
    active_badge.short_description = 'Active'
    
    def assignment_count(self, obj):
        return obj.assignments.count()
    assignment_count.short_description = '# Assignments'
    
    def conversion_rate(self, obj):
        exposures = obj.metrics.filter(type='exposure').count()
        outcomes = obj.metrics.filter(type='outcome').count()
        
        if exposures == 0:
            return 'N/A'
        
        rate = (outcomes / exposures) * 100
        return f'{rate:.2f}%'
    conversion_rate.short_description = 'Conversion Rate'


@admin.register(ExperimentAssignment)
class ExperimentAssignmentAdmin(admin.ModelAdmin):
    list_display = ['experiment', 'user_display', 'variant', 'assigned_at']
    list_filter = ['experiment', 'variant', 'assigned_at']
    search_fields = ['experiment__name', 'user__username', 'anonymous_id', 'variant']
    readonly_fields = ['id', 'assigned_at']
    
    def user_display(self, obj):
        return obj.user.username if obj.user else f'Anon: {obj.anonymous_id[:20]}'
    user_display.short_description = 'User'


@admin.register(ExperimentMetric)
class ExperimentMetricAdmin(admin.ModelAdmin):
    list_display = ['experiment', 'type', 'name', 'variant', 'value', 'user_display', 'timestamp']
    list_filter = ['type', 'experiment', 'variant', 'timestamp']
    search_fields = ['experiment__name', 'name', 'user__username', 'anonymous_id']
    readonly_fields = ['id', 'created_at', 'timestamp']
    date_hierarchy = 'timestamp'
    
    def user_display(self, obj):
        return obj.user.username if obj.user else f'Anon: {obj.anonymous_id[:20]}'
    user_display.short_description = 'User'


@admin.register(FeatureFlagUsage)
class FeatureFlagUsageAdmin(admin.ModelAdmin):
    list_display = ['feature_flag', 'user', 'was_enabled', 'timestamp']
    list_filter = ['was_enabled', 'feature_flag', 'timestamp']
    search_fields = ['feature_flag__name', 'user__username']
    readonly_fields = ['id', 'timestamp']
    date_hierarchy = 'timestamp'

