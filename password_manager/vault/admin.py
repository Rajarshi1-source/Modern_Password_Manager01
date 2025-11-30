from django.contrib import admin
from vault.models.vault_models import EncryptedVaultItem
from vault.models import UserSalt, AuditLog, BreachAlert

@admin.register(EncryptedVaultItem)
class EncryptedVaultItemAdmin(admin.ModelAdmin):
    list_display = ('item_type', 'user', 'created_at', 'updated_at')
    list_filter = ('item_type', 'user')
    search_fields = ('item_id', 'user__username')
    readonly_fields = ('id', 'created_at', 'updated_at')

# Register other models as needed
admin.site.register(UserSalt)
admin.site.register(AuditLog)
admin.site.register(BreachAlert)
