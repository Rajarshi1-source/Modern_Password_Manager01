from django.contrib import admin
from .models import EmergencyContact, EmergencyAccessRequest, UserProfile, UserPreferences

# Register your models here.


@admin.register(EmergencyContact)
class EmergencyContactAdmin(admin.ModelAdmin):
    list_display = ['emergency_contact', 'vault_owner', 'status', 'access_type', 'created_at']
    list_filter = ['status', 'access_type', 'created_at']
    search_fields = ['emergency_contact__username', 'vault_owner__username', 'email']


@admin.register(EmergencyAccessRequest)
class EmergencyAccessRequestAdmin(admin.ModelAdmin):
    list_display = ['emergency_contact', 'status', 'requested_at', 'auto_approve_at']
    list_filter = ['status', 'requested_at']
    search_fields = ['emergency_contact__emergency_contact__username', 'emergency_contact__vault_owner__username']


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'phone_number', 'is_phone_verified', 'recovery_email', 'is_recovery_email_verified', 'account_locked']
    list_filter = ['is_phone_verified', 'is_recovery_email_verified', 'account_locked', 'created_at']
    search_fields = ['user__username', 'phone_number', 'recovery_email']


@admin.register(UserPreferences)
class UserPreferencesAdmin(admin.ModelAdmin):
    list_display = [
        'user',
        'theme_mode',
        'ui_language',
        'notifications_enabled',
        'security_auto_lock_enabled',
        'updated_at'
    ]
    list_filter = [
        'theme_mode',
        'ui_language',
        'notifications_enabled',
        'security_auto_lock_enabled',
        'privacy_analytics',
        'updated_at'
    ]
    search_fields = ['user__username']
    readonly_fields = ['version', 'created_at', 'updated_at', 'last_synced']
    
    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Theme', {
            'fields': (
                'theme_mode',
                'theme_primary_color',
                'theme_font_size',
                'theme_font_family',
                'theme_compact_mode',
                'theme_animations',
                'theme_high_contrast'
            ),
            'classes': ('collapse',)
        }),
        ('Notifications', {
            'fields': (
                'notifications_enabled',
                'notifications_browser',
                'notifications_email',
                'notifications_push',
                'notifications_breach_alerts',
                'notifications_security_alerts',
                'notifications_account_activity',
                'notifications_marketing',
                'notifications_product_updates',
                'notifications_quiet_hours_enabled',
                'notifications_quiet_hours_start',
                'notifications_quiet_hours_end',
                'notifications_sound',
                'notifications_sound_volume'
            ),
            'classes': ('collapse',)
        }),
        ('Security', {
            'fields': (
                'security_auto_lock_enabled',
                'security_auto_lock_timeout',
                'security_biometric_auth',
                'security_two_factor_auth',
                'security_require_reauth',
                'security_reauth_timeout',
                'security_clear_clipboard',
                'security_clipboard_timeout',
                'security_default_password_length',
                'security_include_symbols',
                'security_include_numbers',
                'security_include_uppercase',
                'security_include_lowercase',
                'security_breach_monitoring',
                'security_dark_web_monitoring'
            ),
            'classes': ('collapse',)
        }),
        ('Privacy', {
            'fields': (
                'privacy_analytics',
                'privacy_error_reporting',
                'privacy_performance_monitoring',
                'privacy_crash_reports',
                'privacy_usage_data',
                'privacy_keep_login_history',
                'privacy_login_history_days',
                'privacy_keep_audit_logs',
                'privacy_audit_log_days'
            ),
            'classes': ('collapse',)
        }),
        ('UI/UX', {
            'fields': (
                'ui_language',
                'ui_date_format',
                'ui_time_format',
                'ui_timezone',
                'ui_vault_view',
                'ui_sort_by',
                'ui_sort_order',
                'ui_group_by',
                'ui_show_recent_items',
                'ui_recent_items_count',
                'ui_show_favorites',
                'ui_show_weak_passwords',
                'ui_show_breach_alerts',
                'ui_sidebar_collapsed',
                'ui_sidebar_position'
            ),
            'classes': ('collapse',)
        }),
        ('Accessibility', {
            'fields': (
                'accessibility_screen_reader',
                'accessibility_reduced_motion',
                'accessibility_large_text',
                'accessibility_keyboard_navigation',
                'accessibility_focus_indicators',
                'accessibility_announce_changes'
            ),
            'classes': ('collapse',)
        }),
        ('Advanced', {
            'fields': (
                'advanced_developer_mode',
                'advanced_debug_logs',
                'advanced_experimental_features',
                'advanced_beta_features',
                'advanced_lazy_loading',
                'advanced_cache_enabled',
                'advanced_offline_mode',
                'advanced_auto_sync',
                'advanced_sync_interval',
                'advanced_conflict_resolution'
            ),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': (
                'version',
                'device_id',
                'last_synced',
                'created_at',
                'updated_at'
            )
        }),
    )
