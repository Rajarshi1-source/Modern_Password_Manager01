from django.contrib import admin

from stegano_vault.models import StegoAccessEvent, StegoVault


@admin.register(StegoVault)
class StegoVaultAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "label",
        "blob_size_tier",
        "crypto_ver",
        "updated_at",
        "last_accessed_at",
    )
    list_filter = ("blob_size_tier", "crypto_ver")
    search_fields = ("user__username", "label")
    readonly_fields = (
        "id",
        "image_mime",
        "cover_hash",
        "schema_ver",
        "created_at",
        "updated_at",
        "last_accessed_at",
    )

    def has_add_permission(self, request):  # pragma: no cover
        return False

    def get_readonly_fields(self, request, obj=None):
        # Never let admins see / edit the raw image bytes via the UI.
        return self.readonly_fields + ("image",)


@admin.register(StegoAccessEvent)
class StegoAccessEventAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "stego_vault",
        "kind",
        "surface",
        "ip",
        "created_at",
    )
    list_filter = ("kind", "surface")
    search_fields = ("user__username", "ip", "stego_vault__label")
    readonly_fields = (
        "id",
        "stego_vault",
        "user",
        "kind",
        "surface",
        "ip",
        "user_agent",
        "details",
        "created_at",
    )

    def has_add_permission(self, request):  # pragma: no cover
        return False

    def has_change_permission(self, request, obj=None):  # pragma: no cover
        return False
