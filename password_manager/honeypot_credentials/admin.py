from django.contrib import admin

from .models import HoneypotCredential, HoneypotAccessEvent, HoneypotTemplate


@admin.register(HoneypotTemplate)
class HoneypotTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'password_pattern', 'is_builtin', 'created_at')
    list_filter = ('is_builtin', 'password_pattern')
    search_fields = ('name', 'fake_site_template', 'fake_username_template')


@admin.register(HoneypotCredential)
class HoneypotCredentialAdmin(admin.ModelAdmin):
    list_display = ('label', 'user', 'fake_site', 'decoy_strategy', 'is_active', 'created_at')
    list_filter = ('is_active', 'decoy_strategy')
    search_fields = ('label', 'fake_username', 'fake_site', 'user__username')
    readonly_fields = ('created_at', 'updated_at', 'last_rotated_at')


@admin.register(HoneypotAccessEvent)
class HoneypotAccessEventAdmin(admin.ModelAdmin):
    list_display = ('honeypot', 'access_type', 'ip', 'geo_country', 'alert_sent', 'accessed_at')
    list_filter = ('access_type', 'alert_sent', 'geo_country')
    search_fields = ('ip', 'user_agent', 'honeypot__label')
    readonly_fields = ('accessed_at',)
