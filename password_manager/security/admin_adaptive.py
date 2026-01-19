"""
Django Admin Configuration for Adaptive Password Feature
=========================================================

Custom admin views for managing adaptive password models.
Provides read-only access to typing patterns and adaptations
for support and debugging purposes.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone

from .models import (
    AdaptivePasswordConfig,
    TypingSession,
    PasswordAdaptation,
    UserTypingProfile,
    AdaptationFeedback,
)


# =============================================================================
# User Typing Profile Admin
# =============================================================================

@admin.register(UserTypingProfile)
class UserTypingProfileAdmin(admin.ModelAdmin):
    """Admin for user typing profiles."""
    
    list_display = (
        'user',
        'total_sessions',
        'success_rate_display',
        'average_wpm',
        'profile_confidence_display',
        'updated_at',
    )
    list_filter = ('updated_at', 'created_at')
    search_fields = ('user__username', 'user__email')
    readonly_fields = (
        'id',
        'created_at',
        'updated_at',
        'last_session_at',
        'total_sessions',
        'successful_sessions',
        'success_rate',
        'profile_confidence',
    )
    
    fieldsets = (
        ('User Information', {
            'fields': ('id', 'user')
        }),
        ('Substitution Preferences', {
            'fields': ('preferred_substitutions', 'substitution_confidence'),
            'classes': ('collapse',)
        }),
        ('Typing Metrics', {
            'fields': (
                'average_wpm',
                'wpm_variance',
                'error_prone_positions',
                'common_error_types',
                'rhythm_signature',
            )
        }),
        ('Statistics', {
            'fields': (
                'total_sessions',
                'successful_sessions',
                'success_rate',
                'profile_confidence',
                'minimum_sessions_for_suggestion',
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'last_session_at')
        }),
    )
    
    def success_rate_display(self, obj):
        """Display success rate as percentage with color."""
        rate = obj.success_rate * 100
        color = 'green' if rate >= 80 else 'orange' if rate >= 50 else 'red'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
            color, rate
        )
    success_rate_display.short_description = 'Success Rate'
    
    def profile_confidence_display(self, obj):
        """Display profile confidence with progress bar."""
        confidence = obj.profile_confidence * 100
        color = 'green' if confidence >= 70 else 'orange' if confidence >= 40 else 'red'
        return format_html(
            '<div style="width: 100px; background: #eee; border-radius: 5px;">'
            '<div style="width: {}px; background: {}; height: 15px; border-radius: 5px;"></div>'
            '</div> {:.0f}%',
            confidence, color, confidence
        )
    profile_confidence_display.short_description = 'Confidence'


# =============================================================================
# Typing Session Admin
# =============================================================================

@admin.register(TypingSession)
class TypingSessionAdmin(admin.ModelAdmin):
    """Admin for typing sessions - read-only for privacy."""
    
    list_display = (
        'user',
        'password_length',
        'success_badge',
        'error_count',
        'total_time_display',
        'device_type',
        'created_at',
    )
    list_filter = ('success', 'device_type', 'input_method', 'created_at')
    search_fields = ('user__username', 'user__email')
    readonly_fields = (
        'id',
        'user',
        'password_hash_prefix',
        'password_length',
        'success',
        'error_positions',
        'error_count',
        'timing_profile',
        'total_time_ms',
        'device_type',
        'input_method',
        'created_at',
    )
    
    def has_add_permission(self, request):
        """Disable adding sessions from admin (privacy)."""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Disable editing sessions (read-only)."""
        return False
    
    def success_badge(self, obj):
        """Display success status as badge."""
        if obj.success:
            return format_html(
                '<span style="background: #10B981; color: white; padding: 3px 8px; '
                'border-radius: 10px; font-size: 11px;">✓ Success</span>'
            )
        return format_html(
            '<span style="background: #EF4444; color: white; padding: 3px 8px; '
            'border-radius: 10px; font-size: 11px;">✗ Failed</span>'
        )
    success_badge.short_description = 'Status'
    
    def total_time_display(self, obj):
        """Display total time in seconds."""
        seconds = obj.total_time_ms / 1000 if obj.total_time_ms else 0
        return f"{seconds:.2f}s"
    total_time_display.short_description = 'Duration'


# =============================================================================
# Password Adaptation Admin
# =============================================================================

@admin.register(PasswordAdaptation)
class PasswordAdaptationAdmin(admin.ModelAdmin):
    """Admin for password adaptations."""
    
    list_display = (
        'user',
        'status_badge',
        'adaptation_type',
        'adaptation_generation',
        'confidence_display',
        'memorability_change',
        'suggested_at',
    )
    list_filter = ('status', 'adaptation_type', 'suggested_at')
    search_fields = ('user__username', 'user__email')
    readonly_fields = (
        'id',
        'password_hash_prefix',
        'adapted_hash_prefix',
        'suggested_at',
        'decided_at',
        'rolled_back_at',
        'rollback_chain_display',
    )
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'user', 'status', 'adaptation_type')
        }),
        ('Password Hashes (Privacy-Safe)', {
            'fields': ('password_hash_prefix', 'adapted_hash_prefix'),
            'classes': ('collapse',)
        }),
        ('Adaptation Details', {
            'fields': (
                'substitutions_applied',
                'adaptation_generation',
                'confidence_score',
            )
        }),
        ('Memorability Metrics', {
            'fields': (
                'memorability_score_before',
                'memorability_score_after',
            )
        }),
        ('Rollback Chain', {
            'fields': ('previous_adaptation', 'rollback_chain_display')
        }),
        ('Timestamps', {
            'fields': ('suggested_at', 'decided_at', 'rolled_back_at')
        }),
        ('Notes', {
            'fields': ('reason',)
        }),
    )
    
    def status_badge(self, obj):
        """Display status as colored badge."""
        colors = {
            'suggested': '#8B5CF6',
            'accepted': '#10B981',
            'rejected': '#F59E0B',
            'active': '#06B6D4',
            'rolled_back': '#6B7280',
        }
        color = colors.get(obj.status, '#6B7280')
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 10px; '
            'border-radius: 10px; font-size: 11px; text-transform: uppercase;">{}</span>',
            color, obj.status
        )
    status_badge.short_description = 'Status'
    
    def confidence_display(self, obj):
        """Display confidence as percentage."""
        conf = (obj.confidence_score or 0) * 100
        color = 'green' if conf >= 80 else 'orange' if conf >= 50 else 'red'
        return format_html(
            '<span style="color: {};">{:.0f}%</span>', color, conf
        )
    confidence_display.short_description = 'Confidence'
    
    def memorability_change(self, obj):
        """Display memorability improvement."""
        before = obj.memorability_score_before or 0
        after = obj.memorability_score_after or 0
        change = (after - before) * 100
        
        if change > 0:
            return format_html(
                '<span style="color: green;">+{:.1f}%</span>', change
            )
        elif change < 0:
            return format_html(
                '<span style="color: red;">{:.1f}%</span>', change
            )
        return format_html('<span style="color: gray;">0%</span>')
    memorability_change.short_description = 'Memorability Δ'
    
    def rollback_chain_display(self, obj):
        """Display rollback chain."""
        chain = obj.get_rollback_chain()
        if len(chain) <= 1:
            return "No previous versions"
        
        items = []
        for i, adaptation in enumerate(chain):
            status = f"[{adaptation.status}]"
            items.append(f"Gen {adaptation.adaptation_generation}: {status}")
        
        return " → ".join(items)
    rollback_chain_display.short_description = 'Rollback Chain'


# =============================================================================
# Adaptive Password Config Admin
# =============================================================================

@admin.register(AdaptivePasswordConfig)
class AdaptivePasswordConfigAdmin(admin.ModelAdmin):
    """Admin for user configuration."""
    
    list_display = (
        'user',
        'is_enabled_display',
        'auto_suggest_display',
        'suggestion_frequency_days',
        'consent_given_at',
    )
    list_filter = (
        'is_enabled',
        'auto_suggest_enabled',
        'allow_centralized_training',
        'allow_federated_learning',
    )
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('id', 'created_at', 'updated_at', 'consent_given_at')
    
    fieldsets = (
        ('User', {
            'fields': ('id', 'user')
        }),
        ('Feature Settings', {
            'fields': (
                'is_enabled',
                'auto_suggest_enabled',
                'suggestion_frequency_days',
            )
        }),
        ('Privacy Settings', {
            'fields': (
                'differential_privacy_epsilon',
                'allow_centralized_training',
                'allow_federated_learning',
            )
        }),
        ('Consent', {
            'fields': ('consent_given_at', 'consent_version')
        }),
        ('Timestamps', {
            'fields': (
                'created_at',
                'updated_at',
                'last_suggestion_at',
            )
        }),
    )
    
    def is_enabled_display(self, obj):
        """Display enabled status as icon."""
        if obj.is_enabled:
            return format_html(
                '<span style="color: green; font-size: 16px;">✓</span>'
            )
        return format_html(
            '<span style="color: red; font-size: 16px;">✗</span>'
        )
    is_enabled_display.short_description = 'Enabled'
    
    def auto_suggest_display(self, obj):
        """Display auto-suggest status."""
        if obj.auto_suggest_enabled:
            return format_html(
                '<span style="color: green;">Auto</span>'
            )
        return format_html(
            '<span style="color: gray;">Manual</span>'
        )
    auto_suggest_display.short_description = 'Suggestions'


# =============================================================================
# Adaptation Feedback Admin
# =============================================================================

@admin.register(AdaptationFeedback)
class AdaptationFeedbackAdmin(admin.ModelAdmin):
    """Admin for adaptation feedback."""
    
    list_display = (
        'user',
        'rating_stars',
        'typing_accuracy_improved',
        'memorability_improved',
        'days_since_adaptation',
        'created_at',
    )
    list_filter = (
        'rating',
        'typing_accuracy_improved',
        'memorability_improved',
        'created_at',
    )
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('id', 'created_at', 'days_since_adaptation')
    
    fieldsets = (
        ('References', {
            'fields': ('id', 'adaptation', 'user')
        }),
        ('Rating', {
            'fields': ('rating',)
        }),
        ('Improvement Indicators', {
            'fields': (
                'typing_accuracy_improved',
                'memorability_improved',
                'typing_speed_improved',
            )
        }),
        ('Feedback', {
            'fields': ('additional_feedback',)
        }),
        ('Metadata', {
            'fields': (
                'days_since_adaptation',
                'typing_sessions_since',
                'created_at',
            )
        }),
    )
    
    def rating_stars(self, obj):
        """Display rating as stars."""
        filled = '★' * obj.rating
        empty = '☆' * (5 - obj.rating)
        color = 'gold' if obj.rating >= 4 else 'orange' if obj.rating >= 2 else 'red'
        return format_html(
            '<span style="color: {}; font-size: 14px;">{}{}</span>',
            color, filled, empty
        )
    rating_stars.short_description = 'Rating'
