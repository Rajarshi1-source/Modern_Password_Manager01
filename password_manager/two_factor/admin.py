from django.contrib import admin
from .models import TOTPDevice


@admin.register(TOTPDevice)
class TOTPDeviceAdmin(admin.ModelAdmin):
    list_display = ['user', 'name', 'confirmed', 'last_used_at', 'created_at']
    list_filter = ['confirmed', 'created_at']
    search_fields = ['user__username', 'user__email', 'name']
    readonly_fields = ['key', 'last_t', 'created_at', 'last_used_at']
    
    fieldsets = (
        ('Device Info', {
            'fields': ('user', 'name', 'confirmed')
        }),
        ('TOTP Configuration', {
            'fields': ('key', 'digits', 'step', 'tolerance'),
            'classes': ('collapse',)
        }),
        ('Usage', {
            'fields': ('last_t', 'last_used_at', 'created_at'),
        }),
    )
