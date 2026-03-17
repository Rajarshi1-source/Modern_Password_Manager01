"""
FHE Sharing Admin Configuration
"""

from django.contrib import admin
from django.utils.html import format_html
from .models import HomomorphicShare, ShareAccessLog, ShareGroup


@admin.register(HomomorphicShare)
class HomomorphicShareAdmin(admin.ModelAdmin):
    """Admin interface for HomomorphicShare."""

    list_display = [
        'short_id', 'owner_link', 'arrow', 'recipient_link',
        'status_badge', 'use_count_display', 'expires_display',
        'created_at',
    ]
    list_filter = [
        'is_active', 'permission_level', 'created_at', 'expires_at',
    ]
    search_fields = [
        'owner__username', 'recipient__username',
        'id',
    ]
    readonly_fields = [
        'id', 'encrypted_autofill_token', 'token_metadata',
        'use_count', 'last_used_at', 'revoked_at', 'revoked_by',
        'created_at', 'updated_at',
    ]
    date_hierarchy = 'created_at'
    list_per_page = 25

    fieldsets = (
        ('Share Identity', {
            'fields': ('id', 'owner', 'recipient', 'vault_item', 'group'),
        }),
        ('Permissions', {
            'fields': (
                'permission_level', 'can_autofill',
                'can_view_password', 'can_copy_password',
            ),
        }),
        ('Usage & Limits', {
            'fields': (
                'max_uses', 'use_count', 'last_used_at',
            ),
        }),
        ('Lifecycle', {
            'fields': (
                'is_active', 'expires_at',
                'revoked_at', 'revoked_by', 'revocation_reason',
            ),
        }),
        ('FHE Token (Read Only)', {
            'fields': ('token_metadata',),
            'classes': ('collapse',),
        }),
        ('Domain Binding', {
            'fields': ('encrypted_domain_binding',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def short_id(self, obj):
        return str(obj.id)[:8]
    short_id.short_description = 'ID'

    def owner_link(self, obj):
        return obj.owner.username
    owner_link.short_description = 'Owner'

    def arrow(self, obj):
        return format_html('<span style="font-size:1.2em">→</span>')
    arrow.short_description = ''

    def recipient_link(self, obj):
        return obj.recipient.username
    recipient_link.short_description = 'Recipient'

    def status_badge(self, obj):
        if not obj.is_active:
            color = '#dc3545'
            text = 'Revoked'
        elif obj.is_expired:
            color = '#ffc107'
            text = 'Expired'
        elif obj.is_usage_limit_reached:
            color = '#fd7e14'
            text = 'Limit Reached'
        else:
            color = '#28a745'
            text = 'Active'
        return format_html(
            '<span style="background:{}; color:#fff; padding:2px 8px; '
            'border-radius:4px; font-size:0.85em;">{}</span>',
            color, text,
        )
    status_badge.short_description = 'Status'

    def use_count_display(self, obj):
        if obj.max_uses:
            return f"{obj.use_count}/{obj.max_uses}"
        return f"{obj.use_count}/∞"
    use_count_display.short_description = 'Uses'

    def expires_display(self, obj):
        if obj.expires_at is None:
            return 'Never'
        if obj.is_expired:
            return format_html(
                '<span style="color:#dc3545">{}</span>',
                obj.expires_at.strftime('%Y-%m-%d %H:%M'),
            )
        return obj.expires_at.strftime('%Y-%m-%d %H:%M')
    expires_display.short_description = 'Expires'


@admin.register(ShareAccessLog)
class ShareAccessLogAdmin(admin.ModelAdmin):
    """Admin interface for ShareAccessLog."""

    list_display = [
        'short_id', 'action_badge', 'username', 'domain',
        'success_icon', 'timestamp',
    ]
    list_filter = ['action', 'success', 'timestamp']
    search_fields = [
        'share__id', 'user__username', 'domain', 'ip_address',
    ]
    readonly_fields = ['id', 'timestamp']
    date_hierarchy = 'timestamp'
    list_per_page = 50

    def short_id(self, obj):
        return str(obj.id)[:8]
    short_id.short_description = 'ID'

    def username(self, obj):
        return obj.user.username if obj.user else 'System'
    username.short_description = 'User'

    def action_badge(self, obj):
        colors = {
            'share_created': '#17a2b8',
            'autofill_used': '#28a745',
            'autofill_denied': '#dc3545',
            'share_revoked': '#6c757d',
            'share_expired': '#ffc107',
            'domain_mismatch': '#fd7e14',
            'usage_limit_reached': '#fd7e14',
            'share_viewed': '#6610f2',
        }
        color = colors.get(obj.action, '#6c757d')
        return format_html(
            '<span style="background:{}; color:#fff; padding:2px 8px; '
            'border-radius:4px; font-size:0.85em;">{}</span>',
            color, obj.get_action_display(),
        )
    action_badge.short_description = 'Action'

    def success_icon(self, obj):
        if obj.success:
            return format_html('<span style="color:#28a745">✓</span>')
        return format_html(
            '<span style="color:#dc3545" title="{}">✗</span>',
            obj.failure_reason,
        )
    success_icon.short_description = 'OK'


@admin.register(ShareGroup)
class ShareGroupAdmin(admin.ModelAdmin):
    """Admin interface for ShareGroup."""

    list_display = [
        'name', 'owner', 'shares_count', 'created_at',
    ]
    list_filter = ['created_at']
    search_fields = ['name', 'owner__username']
    readonly_fields = ['id', 'created_at', 'updated_at']
