from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid

# Create your models here.

class EmergencyContact(models.Model):
    """Model for storing emergency contacts"""
    STATUS_CHOICES = (
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )
    
    ACCESS_TYPES = (
        ('view', 'View Only'),
        ('full', 'Full Access'),
    )
    
    # The user who will be granted emergency access
    emergency_contact = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,
        related_name='emergency_access_to'
    )
    
    # The user who grants access to their vault
    vault_owner = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,
        related_name='emergency_contacts'
    )
    
    # Status of the emergency contact relationship
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    
    # Type of access granted
    access_type = models.CharField(
        max_length=10,
        choices=ACCESS_TYPES,
        default='view'
    )
    
    # Waiting period in hours before emergency access is granted
    waiting_period_hours = models.IntegerField(default=24)
    
    # Email for sending notifications
    email = models.EmailField(blank=True)
    
    # Date fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['emergency_contact', 'vault_owner']
        
    def __str__(self):
        return f"{self.emergency_contact.username} - Emergency contact for {self.vault_owner.username}"

class EmergencyAccessRequest(models.Model):
    """Model for tracking emergency access requests"""
    STATUS_CHOICES = (
        ('pending', 'Waiting Period'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('auto_approved', 'Automatically Approved'),
        ('expired', 'Expired'),
        ('canceled', 'Canceled'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Reference to the emergency contact relationship
    emergency_contact = models.ForeignKey(
        EmergencyContact,
        on_delete=models.CASCADE,
        related_name='access_requests'
    )
    
    # Status of the request
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    
    # Timestamps
    requested_at = models.DateTimeField(default=timezone.now)
    approved_at = models.DateTimeField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    access_granted_at = models.DateTimeField(null=True, blank=True)
    
    # When the access will be automatically granted
    auto_approve_at = models.DateTimeField(null=True, blank=True)
    
    # When the access expires (null for no expiration)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    # Reason for the request
    reason = models.TextField(blank=True)
    
    # Key to track the one-time vault access
    access_key = models.CharField(max_length=64, blank=True)
    
    def __str__(self):
        return f"Access request by {self.emergency_contact.emergency_contact.username} for {self.emergency_contact.vault_owner.username}"
        
    def save(self, *args, **kwargs):
        # Set auto_approve_at on creation
        if not self.id and not self.auto_approve_at:
            waiting_period = self.emergency_contact.waiting_period_hours
            self.auto_approve_at = timezone.now() + timezone.timedelta(hours=waiting_period)
            
        super().save(*args, **kwargs)

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone_number = models.CharField(max_length=20, blank=True)
    is_phone_verified = models.BooleanField(default=False)
    recovery_email = models.EmailField(blank=True)
    is_recovery_email_verified = models.BooleanField(default=False)
    account_locked = models.BooleanField(default=False)
    lock_reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Profile for {self.user.username}"


class UserPreferences(models.Model):
    """
    Comprehensive user preferences for all aspects of the application
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='preferences')
    
    # Theme preferences
    theme_mode = models.CharField(max_length=20, default='auto', choices=[
        ('light', 'Light'),
        ('dark', 'Dark'),
        ('auto', 'Auto (System)')
    ])
    theme_primary_color = models.CharField(max_length=20, default='#4A6CF7')
    theme_font_size = models.CharField(max_length=20, default='medium', choices=[
        ('small', 'Small'),
        ('medium', 'Medium'),
        ('large', 'Large'),
        ('xlarge', 'Extra Large')
    ])
    theme_font_family = models.CharField(max_length=20, default='system')
    theme_compact_mode = models.BooleanField(default=False)
    theme_animations = models.BooleanField(default=True)
    theme_high_contrast = models.BooleanField(default=False)
    
    # Notification preferences
    notifications_enabled = models.BooleanField(default=True)
    notifications_browser = models.BooleanField(default=True)
    notifications_email = models.BooleanField(default=True)
    notifications_push = models.BooleanField(default=False)
    notifications_breach_alerts = models.BooleanField(default=True)
    notifications_security_alerts = models.BooleanField(default=True)
    notifications_account_activity = models.BooleanField(default=True)
    notifications_marketing = models.BooleanField(default=False)
    notifications_product_updates = models.BooleanField(default=True)
    notifications_quiet_hours_enabled = models.BooleanField(default=False)
    notifications_quiet_hours_start = models.TimeField(default='22:00')
    notifications_quiet_hours_end = models.TimeField(default='08:00')
    notifications_sound = models.BooleanField(default=True)
    notifications_sound_volume = models.FloatField(default=0.5)
    
    # Security preferences
    security_auto_lock_enabled = models.BooleanField(default=True)
    security_auto_lock_timeout = models.IntegerField(default=5, help_text='Minutes')
    security_biometric_auth = models.BooleanField(default=False)
    security_two_factor_auth = models.BooleanField(default=False)
    security_require_reauth = models.BooleanField(default=True)
    security_reauth_timeout = models.IntegerField(default=30, help_text='Minutes')
    security_clear_clipboard = models.BooleanField(default=True)
    security_clipboard_timeout = models.IntegerField(default=30, help_text='Seconds')
    security_default_password_length = models.IntegerField(default=16)
    security_include_symbols = models.BooleanField(default=True)
    security_include_numbers = models.BooleanField(default=True)
    security_include_uppercase = models.BooleanField(default=True)
    security_include_lowercase = models.BooleanField(default=True)
    security_breach_monitoring = models.BooleanField(default=True)
    security_dark_web_monitoring = models.BooleanField(default=True)
    
    # Privacy preferences
    privacy_analytics = models.BooleanField(default=True)
    privacy_error_reporting = models.BooleanField(default=True)
    privacy_performance_monitoring = models.BooleanField(default=True)
    privacy_crash_reports = models.BooleanField(default=True)
    privacy_usage_data = models.BooleanField(default=True)
    privacy_keep_login_history = models.BooleanField(default=True)
    privacy_login_history_days = models.IntegerField(default=90)
    privacy_keep_audit_logs = models.BooleanField(default=True)
    privacy_audit_log_days = models.IntegerField(default=365)
    
    # UI/UX preferences
    ui_language = models.CharField(max_length=10, default='en')
    ui_date_format = models.CharField(max_length=20, default='MM/DD/YYYY')
    ui_time_format = models.CharField(max_length=10, default='12h', choices=[
        ('12h', '12 Hour'),
        ('24h', '24 Hour')
    ])
    ui_timezone = models.CharField(max_length=100, default='auto')
    ui_vault_view = models.CharField(max_length=20, default='grid', choices=[
        ('grid', 'Grid'),
        ('list', 'List'),
        ('compact', 'Compact')
    ])
    ui_sort_by = models.CharField(max_length=20, default='name')
    ui_sort_order = models.CharField(max_length=10, default='asc', choices=[
        ('asc', 'Ascending'),
        ('desc', 'Descending')
    ])
    ui_group_by = models.CharField(max_length=20, default='none')
    ui_show_recent_items = models.BooleanField(default=True)
    ui_recent_items_count = models.IntegerField(default=10)
    ui_show_favorites = models.BooleanField(default=True)
    ui_show_weak_passwords = models.BooleanField(default=True)
    ui_show_breach_alerts = models.BooleanField(default=True)
    ui_sidebar_collapsed = models.BooleanField(default=False)
    ui_sidebar_position = models.CharField(max_length=10, default='left', choices=[
        ('left', 'Left'),
        ('right', 'Right')
    ])
    
    # Accessibility preferences
    accessibility_screen_reader = models.BooleanField(default=False)
    accessibility_reduced_motion = models.BooleanField(default=False)
    accessibility_large_text = models.BooleanField(default=False)
    accessibility_keyboard_navigation = models.BooleanField(default=True)
    accessibility_focus_indicators = models.BooleanField(default=True)
    accessibility_announce_changes = models.BooleanField(default=True)
    
    # Advanced preferences
    advanced_developer_mode = models.BooleanField(default=False)
    advanced_debug_logs = models.BooleanField(default=False)
    advanced_experimental_features = models.BooleanField(default=False)
    advanced_beta_features = models.BooleanField(default=False)
    advanced_lazy_loading = models.BooleanField(default=True)
    advanced_cache_enabled = models.BooleanField(default=True)
    advanced_offline_mode = models.BooleanField(default=True)
    advanced_auto_sync = models.BooleanField(default=True)
    advanced_sync_interval = models.IntegerField(default=60, help_text='Seconds')
    advanced_conflict_resolution = models.CharField(max_length=20, default='latest')
    
    # Metadata
    version = models.CharField(max_length=20, default='1.0.0')
    device_id = models.CharField(max_length=200, blank=True)
    last_synced = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'User Preferences'
        verbose_name_plural = 'User Preferences'
    
    def __str__(self):
        return f"Preferences for {self.user.username}"
    
    def to_dict(self):
        """Convert preferences to dictionary format"""
        return {
            'theme': {
                'mode': self.theme_mode,
                'primaryColor': self.theme_primary_color,
                'fontSize': self.theme_font_size,
                'fontFamily': self.theme_font_family,
                'compactMode': self.theme_compact_mode,
                'animations': self.theme_animations,
                'highContrast': self.theme_high_contrast,
            },
            'notifications': {
                'enabled': self.notifications_enabled,
                'browser': self.notifications_browser,
                'email': self.notifications_email,
                'push': self.notifications_push,
                'breachAlerts': self.notifications_breach_alerts,
                'securityAlerts': self.notifications_security_alerts,
                'accountActivity': self.notifications_account_activity,
                'marketingEmails': self.notifications_marketing,
                'productUpdates': self.notifications_product_updates,
                'quietHoursEnabled': self.notifications_quiet_hours_enabled,
                'quietHoursStart': self.notifications_quiet_hours_start.strftime('%H:%M'),
                'quietHoursEnd': self.notifications_quiet_hours_end.strftime('%H:%M'),
                'sound': self.notifications_sound,
                'soundVolume': self.notifications_sound_volume,
            },
            'security': {
                'autoLockEnabled': self.security_auto_lock_enabled,
                'autoLockTimeout': self.security_auto_lock_timeout,
                'biometricAuth': self.security_biometric_auth,
                'twoFactorAuth': self.security_two_factor_auth,
                'requireReauth': self.security_require_reauth,
                'reauthTimeout': self.security_reauth_timeout,
                'clearClipboard': self.security_clear_clipboard,
                'clipboardTimeout': self.security_clipboard_timeout,
                'defaultPasswordLength': self.security_default_password_length,
                'includeSymbols': self.security_include_symbols,
                'includeNumbers': self.security_include_numbers,
                'includeUppercase': self.security_include_uppercase,
                'includeLowercase': self.security_include_lowercase,
                'breachMonitoring': self.security_breach_monitoring,
                'darkWebMonitoring': self.security_dark_web_monitoring,
            },
            'privacy': {
                'analytics': self.privacy_analytics,
                'errorReporting': self.privacy_error_reporting,
                'performanceMonitoring': self.privacy_performance_monitoring,
                'crashReports': self.privacy_crash_reports,
                'usageData': self.privacy_usage_data,
                'keepLoginHistory': self.privacy_keep_login_history,
                'loginHistoryDays': self.privacy_login_history_days,
                'keepAuditLogs': self.privacy_keep_audit_logs,
                'auditLogDays': self.privacy_audit_log_days,
            },
            'ui': {
                'language': self.ui_language,
                'dateFormat': self.ui_date_format,
                'timeFormat': self.ui_time_format,
                'timezone': self.ui_timezone,
                'vaultView': self.ui_vault_view,
                'sortBy': self.ui_sort_by,
                'sortOrder': self.ui_sort_order,
                'groupBy': self.ui_group_by,
                'showRecentItems': self.ui_show_recent_items,
                'recentItemsCount': self.ui_recent_items_count,
                'showFavorites': self.ui_show_favorites,
                'showWeakPasswords': self.ui_show_weak_passwords,
                'showBreachAlerts': self.ui_show_breach_alerts,
                'sidebarCollapsed': self.ui_sidebar_collapsed,
                'sidebarPosition': self.ui_sidebar_position,
            },
            'accessibility': {
                'screenReader': self.accessibility_screen_reader,
                'reducedMotion': self.accessibility_reduced_motion,
                'largeText': self.accessibility_large_text,
                'keyboardNavigation': self.accessibility_keyboard_navigation,
                'focusIndicators': self.accessibility_focus_indicators,
                'announceChanges': self.accessibility_announce_changes,
            },
            'advanced': {
                'developerMode': self.advanced_developer_mode,
                'debugLogs': self.advanced_debug_logs,
                'experimentalFeatures': self.advanced_experimental_features,
                'betaFeatures': self.advanced_beta_features,
                'lazyLoading': self.advanced_lazy_loading,
                'cacheEnabled': self.advanced_cache_enabled,
                'offlineMode': self.advanced_offline_mode,
                'autoSync': self.advanced_auto_sync,
                'syncInterval': self.advanced_sync_interval,
                'conflictResolution': self.advanced_conflict_resolution,
            },
            '_metadata': {
                'version': self.version,
                'lastModified': self.updated_at.isoformat(),
                'lastSync': self.last_synced.isoformat() if self.last_synced else None,
                'deviceId': self.device_id,
            }
        }