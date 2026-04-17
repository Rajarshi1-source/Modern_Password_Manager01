from django.contrib import admin

from .models import SelfDestructEvent, SelfDestructPolicy


@admin.register(SelfDestructPolicy)
class SelfDestructPolicyAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'user', 'vault_item_id', 'status',
        'expires_at', 'max_uses', 'access_count',
        'created_at',
    )
    list_filter = ('status',)
    search_fields = ('user__email', 'vault_item_id')
    readonly_fields = ('created_at', 'updated_at', 'last_accessed_at', 'access_count')


@admin.register(SelfDestructEvent)
class SelfDestructEventAdmin(admin.ModelAdmin):
    list_display = ('id', 'policy', 'decision', 'reason', 'ip', 'created_at')
    list_filter = ('decision',)
    readonly_fields = ('created_at',)
