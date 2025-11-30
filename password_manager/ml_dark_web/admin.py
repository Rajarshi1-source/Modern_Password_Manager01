"""
Django Admin interface for ML Dark Web Monitoring
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import (
    BreachSource, MLBreachData, UserCredentialMonitoring,
    MLBreachMatch, DarkWebScrapeLog, BreachPatternAnalysis,
    MLModelMetadata
)


@admin.register(BreachSource)
class BreachSourceAdmin(admin.ModelAdmin):
    list_display = ['name', 'source_type', 'is_active', 'reliability_badge', 'last_scraped', 'scrape_frequency_hours']
    list_filter = ['source_type', 'is_active', 'last_scraped']
    search_fields = ['name', 'url']
    readonly_fields = ['created_at', 'updated_at', 'last_scraped']
    ordering = ['-reliability_score', '-last_scraped']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'url', 'source_type', 'is_active')
        }),
        ('Configuration', {
            'fields': ('scrape_frequency_hours', 'reliability_score')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'last_scraped'),
            'classes': ('collapse',)
        }),
    )
    
    def reliability_badge(self, obj):
        if obj.reliability_score >= 0.8:
            color = 'green'
        elif obj.reliability_score >= 0.5:
            color = 'orange'
        else:
            color = 'red'
        return format_html(
            '<span style="color: {};">{:.2f}</span>',
            color,
            obj.reliability_score
        )
    reliability_badge.short_description = 'Reliability'
    
    actions = ['trigger_scrape', 'deactivate_sources', 'activate_sources']
    
    def trigger_scrape(self, request, queryset):
        from .tasks import scrape_dark_web_source
        for source in queryset:
            scrape_dark_web_source.delay(source.id)
        self.message_user(request, f'Scraping initiated for {queryset.count()} source(s)')
    trigger_scrape.short_description = 'Trigger scraping for selected sources'
    
    def deactivate_sources(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, f'{queryset.count()} source(s) deactivated')
    deactivate_sources.short_description = 'Deactivate selected sources'
    
    def activate_sources(self, request, queryset):
        queryset.update(is_active=True)
        self.message_user(request, f'{queryset.count()} source(s) activated')
    activate_sources.short_description = 'Activate selected sources'


@admin.register(MLBreachData)
class MLBreachDataAdmin(admin.ModelAdmin):
    list_display = ['breach_id', 'title_short', 'source', 'severity_badge', 'confidence_badge', 'detected_at', 'processing_status']
    list_filter = ['severity', 'processing_status', 'detected_at', 'source']
    search_fields = ['breach_id', 'title', 'description']
    readonly_fields = ['breach_id', 'detected_at', 'processed_at', 'ml_model_version', 'confidence_score']
    date_hierarchy = 'detected_at'
    ordering = ['-detected_at']
    
    fieldsets = (
        ('Breach Information', {
            'fields': ('breach_id', 'title', 'description', 'source')
        }),
        ('ML Classification', {
            'fields': ('severity', 'confidence_score', 'ml_model_version', 'processing_status')
        }),
        ('Details', {
            'fields': ('affected_records', 'exposed_data_types', 'breach_date')
        }),
        ('Content', {
            'fields': ('raw_content', 'processed_content', 'extracted_emails', 'extracted_domains'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('detected_at', 'processed_at'),
            'classes': ('collapse',)
        }),
    )
    
    def title_short(self, obj):
        return obj.title[:50] + '...' if len(obj.title) > 50 else obj.title
    title_short.short_description = 'Title'
    
    def severity_badge(self, obj):
        colors = {
            'LOW': 'green',
            'MEDIUM': 'orange',
            'HIGH': 'red',
            'CRITICAL': 'darkred'
        }
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            colors.get(obj.severity, 'black'),
            obj.severity
        )
    severity_badge.short_description = 'Severity'
    
    def confidence_badge(self, obj):
        color = 'green' if obj.confidence_score >= 0.8 else 'orange' if obj.confidence_score >= 0.6 else 'red'
        return format_html(
            '<span style="color: {};">{:.2%}</span>',
            color,
            obj.confidence_score
        )
    confidence_badge.short_description = 'Confidence'
    
    actions = ['process_breaches', 'mark_completed']
    
    def process_breaches(self, request, queryset):
        from .tasks import match_credentials_against_breach
        for breach in queryset:
            match_credentials_against_breach.delay(breach.id)
        self.message_user(request, f'Processing initiated for {queryset.count()} breach(es)')
    process_breaches.short_description = 'Process selected breaches'
    
    def mark_completed(self, request, queryset):
        queryset.update(processing_status='completed')
        self.message_user(request, f'{queryset.count()} breach(es) marked as completed')
    mark_completed.short_description = 'Mark as completed'


@admin.register(UserCredentialMonitoring)
class UserCredentialMonitoringAdmin(admin.ModelAdmin):
    list_display = ['user', 'domain', 'credential_type', 'is_active', 'created_at', 'last_checked']
    list_filter = ['is_active', 'credential_type', 'domain', 'created_at']
    search_fields = ['user__username', 'user__email', 'domain']
    readonly_fields = ['email_hash', 'created_at', 'last_checked']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'domain', 'credential_type')
        }),
        ('Monitoring', {
            'fields': ('is_active', 'email_hash')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'last_checked'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['activate_monitoring', 'deactivate_monitoring', 'check_against_breaches']
    
    def activate_monitoring(self, request, queryset):
        queryset.update(is_active=True)
        self.message_user(request, f'{queryset.count()} credential(s) activated')
    activate_monitoring.short_description = 'Activate monitoring'
    
    def deactivate_monitoring(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, f'{queryset.count()} credential(s) deactivated')
    deactivate_monitoring.short_description = 'Deactivate monitoring'
    
    def check_against_breaches(self, request, queryset):
        from .tasks import check_user_against_all_breaches
        user_ids = queryset.values_list('user_id', flat=True).distinct()
        for user_id in user_ids:
            check_user_against_all_breaches.delay(user_id)
        self.message_user(request, f'Breach check initiated for {len(user_ids)} user(s)')
    check_against_breaches.short_description = 'Check against breaches'


@admin.register(MLBreachMatch)
class MLBreachMatchAdmin(admin.ModelAdmin):
    list_display = ['user', 'breach_link', 'similarity_badge', 'confidence_badge', 'detected_at', 'resolved', 'alert_created']
    list_filter = ['resolved', 'alert_created', 'match_type', 'detected_at']
    search_fields = ['user__username', 'breach__breach_id', 'breach__title']
    readonly_fields = ['detected_at', 'resolved_at', 'similarity_score', 'confidence_score']
    date_hierarchy = 'detected_at'
    ordering = ['-detected_at']
    
    fieldsets = (
        ('Match Information', {
            'fields': ('user', 'breach', 'monitored_credential', 'match_type')
        }),
        ('ML Scores', {
            'fields': ('similarity_score', 'confidence_score', 'matched_data')
        }),
        ('Status', {
            'fields': ('resolved', 'resolved_at', 'alert_created', 'alert_id')
        }),
        ('Timestamps', {
            'fields': ('detected_at',),
            'classes': ('collapse',)
        }),
    )
    
    def breach_link(self, obj):
        url = reverse('admin:ml_dark_web_mlbreachdata_change', args=[obj.breach.id])
        return format_html('<a href="{}">{}</a>', url, obj.breach.breach_id)
    breach_link.short_description = 'Breach'
    
    def similarity_badge(self, obj):
        color = 'red' if obj.similarity_score >= 0.9 else 'orange' if obj.similarity_score >= 0.75 else 'green'
        return format_html(
            '<span style="color: {};">{:.2%}</span>',
            color,
            obj.similarity_score
        )
    similarity_badge.short_description = 'Similarity'
    
    def confidence_badge(self, obj):
        color = 'red' if obj.confidence_score >= 0.9 else 'orange' if obj.confidence_score >= 0.75 else 'green'
        return format_html(
            '<span style="color: {};">{:.2%}</span>',
            color,
            obj.confidence_score
        )
    confidence_badge.short_description = 'Confidence'
    
    actions = ['mark_resolved', 'create_alerts']
    
    def mark_resolved(self, request, queryset):
        from django.utils import timezone
        queryset.update(resolved=True, resolved_at=timezone.now())
        self.message_user(request, f'{queryset.count()} match(es) marked as resolved')
    mark_resolved.short_description = 'Mark as resolved'
    
    def create_alerts(self, request, queryset):
        from .tasks import create_breach_alert
        for match in queryset.filter(alert_created=False):
            create_breach_alert.delay(match.id)
        self.message_user(request, 'Alert creation initiated for selected matches')
    create_alerts.short_description = 'Create alerts for matches'


@admin.register(DarkWebScrapeLog)
class DarkWebScrapeLogAdmin(admin.ModelAdmin):
    list_display = ['source', 'started_at', 'status_badge', 'items_found', 'breaches_detected', 'processing_time_seconds']
    list_filter = ['status', 'started_at', 'source']
    search_fields = ['source__name', 'error_message']
    readonly_fields = ['started_at', 'completed_at', 'processing_time_seconds']
    date_hierarchy = 'started_at'
    ordering = ['-started_at']
    
    def status_badge(self, obj):
        colors = {
            'running': 'blue',
            'completed': 'green',
            'failed': 'red',
            'partial': 'orange'
        }
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            colors.get(obj.status, 'black'),
            obj.status.upper()
        )
    status_badge.short_description = 'Status'


@admin.register(BreachPatternAnalysis)
class BreachPatternAnalysisAdmin(admin.ModelAdmin):
    list_display = ['pattern_id', 'pattern_type', 'risk_level', 'confidence_score', 'frequency', 'is_active']
    list_filter = ['pattern_type', 'risk_level', 'is_active', 'first_seen']
    search_fields = ['pattern_id', 'description']
    readonly_fields = ['pattern_id', 'detected_at', 'first_seen', 'last_seen']
    date_hierarchy = 'detected_at'
    
    filter_horizontal = ['affected_breaches']


@admin.register(MLModelMetadata)
class MLModelMetadataAdmin(admin.ModelAdmin):
    list_display = ['model_type', 'version', 'accuracy_badge', 'training_date', 'is_active']
    list_filter = ['model_type', 'is_active', 'training_date']
    search_fields = ['version', 'notes']
    readonly_fields = ['training_date', 'last_used']
    
    fieldsets = (
        ('Model Information', {
            'fields': ('model_type', 'version', 'file_path', 'is_active')
        }),
        ('Performance Metrics', {
            'fields': ('accuracy', 'precision', 'recall', 'f1_score')
        }),
        ('Training Information', {
            'fields': ('training_samples', 'hyperparameters', 'notes')
        }),
        ('Timestamps', {
            'fields': ('training_date', 'last_used'),
            'classes': ('collapse',)
        }),
    )
    
    def accuracy_badge(self, obj):
        if obj.accuracy is None:
            return 'N/A'
        color = 'green' if obj.accuracy >= 0.9 else 'orange' if obj.accuracy >= 0.8 else 'red'
        return format_html(
            '<span style="color: {};">{:.2%}</span>',
            color,
            obj.accuracy
        )
    accuracy_badge.short_description = 'Accuracy'

