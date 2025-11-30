"""
Email Masking Admin Configuration
"""

from django.contrib import admin
from .models import EmailAlias, EmailMaskingProvider, EmailAliasActivity


@admin.register(EmailAlias)
class EmailAliasAdmin(admin.ModelAdmin):
    list_display = ('alias_email', 'user', 'provider', 'status', 'emails_received', 'emails_forwarded', 'emails_blocked', 'created_at')
    list_filter = ('provider', 'status', 'created_at')
    search_fields = ('alias_email', 'alias_name', 'description', 'user__username', 'forwards_to')
    readonly_fields = ('created_at', 'updated_at', 'last_used_at')
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Alias Information', {
            'fields': ('user', 'alias_email', 'alias_name', 'description')
        }),
        ('Provider Details', {
            'fields': ('provider', 'provider_alias_id')
        }),
        ('Forwarding', {
            'fields': ('forwards_to',)
        }),
        ('Status & Statistics', {
            'fields': ('status', 'emails_received', 'emails_forwarded', 'emails_blocked')
        }),
        ('Vault Integration', {
            'fields': ('vault_item_id',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'last_used_at', 'expires_at')
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


@admin.register(EmailMaskingProvider)
class EmailMaskingProviderAdmin(admin.ModelAdmin):
    list_display = ('user', 'provider', 'is_active', 'is_default', 'monthly_quota', 'aliases_created_this_month', 'created_at')
    list_filter = ('provider', 'is_active', 'is_default', 'created_at')
    search_fields = ('user__username',)
    readonly_fields = ('created_at', 'updated_at', 'last_sync_at')
    
    fieldsets = (
        ('User & Provider', {
            'fields': ('user', 'provider')
        }),
        ('API Configuration', {
            'fields': ('api_key', 'api_endpoint'),
            'description': 'Note: API key is encrypted in the database'
        }),
        ('Settings', {
            'fields': ('is_active', 'is_default')
        }),
        ('Quota Management', {
            'fields': ('monthly_quota', 'aliases_created_this_month', 'quota_reset_date')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'last_sync_at')
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


@admin.register(EmailAliasActivity)
class EmailAliasActivityAdmin(admin.ModelAdmin):
    list_display = ('alias', 'activity_type', 'sender_email', 'subject', 'timestamp')
    list_filter = ('activity_type', 'timestamp')
    search_fields = ('alias__alias_email', 'sender_email', 'subject')
    readonly_fields = ('timestamp',)
    date_hierarchy = 'timestamp'
    
    fieldsets = (
        ('Activity Details', {
            'fields': ('alias', 'activity_type')
        }),
        ('Email Information', {
            'fields': ('sender_email', 'subject')
        }),
        ('Additional Details', {
            'fields': ('details',)
        }),
        ('Timestamp', {
            'fields': ('timestamp',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('alias', 'alias__user')
