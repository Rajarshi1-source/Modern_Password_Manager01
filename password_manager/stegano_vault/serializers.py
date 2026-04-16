from rest_framework import serializers

from stegano_vault.models import StegoAccessEvent, StegoVault


class StegoVaultSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()
    size_bytes = serializers.SerializerMethodField()

    class Meta:
        model = StegoVault
        fields = (
            "id",
            "label",
            "image_mime",
            "blob_size_tier",
            "crypto_ver",
            "cover_hash",
            "schema_ver",
            "notes",
            "created_at",
            "updated_at",
            "last_accessed_at",
            "image_url",
            "size_bytes",
        )
        read_only_fields = fields

    def get_image_url(self, obj: StegoVault) -> str:
        try:
            return obj.image.url
        except Exception:
            return ""

    def get_size_bytes(self, obj: StegoVault) -> int:
        try:
            return int(obj.image.size)
        except Exception:
            return 0


class StegoAccessEventSerializer(serializers.ModelSerializer):
    stego_vault_label = serializers.SerializerMethodField()

    class Meta:
        model = StegoAccessEvent
        fields = (
            "id",
            "stego_vault",
            "stego_vault_label",
            "kind",
            "surface",
            "ip",
            "user_agent",
            "details",
            "created_at",
        )
        read_only_fields = fields

    def get_stego_vault_label(self, obj: StegoAccessEvent) -> str:
        try:
            return obj.stego_vault.label if obj.stego_vault_id else ""
        except Exception:
            return ""
