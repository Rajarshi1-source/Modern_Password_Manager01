"""
FHE Sharing Serializers

DRF serializers for the Homomorphic Password Sharing API.
"""

from rest_framework import serializers
from django.contrib.auth.models import User
from django.utils import timezone

from .models import HomomorphicShare, ShareAccessLog, ShareGroup


class ShareGroupSerializer(serializers.ModelSerializer):
    """Serializer for ShareGroup model."""

    owner_username = serializers.CharField(
        source='owner.username', read_only=True
    )
    shares_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = ShareGroup
        fields = [
            'id', 'name', 'description', 'owner', 'owner_username',
            'vault_item', 'shares_count', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'owner', 'created_at', 'updated_at']


class CreateShareGroupSerializer(serializers.Serializer):
    """Input serializer for creating a share group."""

    name = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, default='')
    vault_item_id = serializers.UUIDField()


class HomomorphicShareSerializer(serializers.ModelSerializer):
    """
    Full share serializer for the owner's view.
    Includes all metadata and management info.
    """

    owner_username = serializers.CharField(
        source='owner.username', read_only=True
    )
    recipient_username = serializers.CharField(
        source='recipient.username', read_only=True
    )
    is_expired = serializers.BooleanField(read_only=True)
    is_usage_limit_reached = serializers.BooleanField(read_only=True)
    is_usable = serializers.BooleanField(read_only=True)
    remaining_uses = serializers.IntegerField(read_only=True)
    bound_domains = serializers.SerializerMethodField()
    group_name = serializers.CharField(
        source='group.name', read_only=True, default=None
    )

    class Meta:
        model = HomomorphicShare
        fields = [
            'id', 'owner', 'owner_username',
            'recipient', 'recipient_username',
            'vault_item', 'group', 'group_name',
            'permission_level', 'can_autofill',
            'can_view_password', 'can_copy_password',
            'max_uses', 'use_count', 'remaining_uses',
            'expires_at', 'is_active', 'is_expired',
            'is_usage_limit_reached', 'is_usable',
            'revoked_at', 'revocation_reason',
            'token_metadata', 'bound_domains',
            'created_at', 'updated_at', 'last_used_at',
        ]
        read_only_fields = [
            'id', 'owner', 'recipient', 'vault_item',
            'encrypted_autofill_token', 'token_metadata',
            'use_count', 'is_active', 'revoked_at',
            'revoked_by', 'created_at', 'updated_at', 'last_used_at',
        ]

    def get_bound_domains(self, obj):
        return obj.get_bound_domains()


class ShareRecipientSerializer(serializers.ModelSerializer):
    """
    Limited share serializer for the recipient's view.
    Hides owner-only fields and sensitive metadata.
    """

    owner_username = serializers.CharField(
        source='owner.username', read_only=True
    )
    is_expired = serializers.BooleanField(read_only=True)
    is_usable = serializers.BooleanField(read_only=True)
    remaining_uses = serializers.IntegerField(read_only=True)
    bound_domains = serializers.SerializerMethodField()

    class Meta:
        model = HomomorphicShare
        fields = [
            'id', 'owner_username',
            'permission_level', 'can_autofill',
            'use_count', 'remaining_uses',
            'expires_at', 'is_expired', 'is_usable',
            'bound_domains',
            'created_at', 'last_used_at',
        ]

    def get_bound_domains(self, obj):
        return obj.get_bound_domains()


class CreateShareSerializer(serializers.Serializer):
    """Input serializer for creating a new homomorphic share."""

    vault_item_id = serializers.UUIDField(
        help_text="UUID of the vault item to share"
    )
    recipient_username = serializers.CharField(
        max_length=150,
        help_text="Username of the recipient"
    )
    domain_constraints = serializers.ListField(
        child=serializers.CharField(max_length=255),
        required=False,
        default=list,
        help_text="Domains where autofill is allowed (e.g., ['github.com', 'gitlab.com'])"
    )
    expires_at = serializers.DateTimeField(
        required=False,
        allow_null=True,
        default=None,
        help_text="When the share expires (ISO 8601). Null for default expiry."
    )
    max_uses = serializers.IntegerField(
        required=False,
        allow_null=True,
        default=None,
        min_value=1,
        max_value=10000,
        help_text="Maximum number of autofill uses. Null = unlimited."
    )
    group_id = serializers.UUIDField(
        required=False,
        allow_null=True,
        default=None,
        help_text="Optional share group ID to add this share to"
    )

    def validate_recipient_username(self, value):
        try:
            User.objects.get(username=value)
        except User.DoesNotExist:
            raise serializers.ValidationError(
                f"User '{value}' not found"
            )
        return value

    def validate_domain_constraints(self, value):
        if value:
            for domain in value:
                if not domain or len(domain) < 3:
                    raise serializers.ValidationError(
                        f"Invalid domain: '{domain}'"
                    )
        return value


class UseAutofillSerializer(serializers.Serializer):
    """Input serializer for using an autofill token."""

    domain = serializers.CharField(
        max_length=255,
        help_text="The domain where autofill is being attempted"
    )
    form_field_selector = serializers.CharField(
        max_length=500,
        required=False,
        default='input[type="password"]',
        help_text="CSS selector for the target form field"
    )


class RevokeShareSerializer(serializers.Serializer):
    """Input serializer for revoking a share."""

    reason = serializers.CharField(
        max_length=255,
        required=False,
        default='',
        help_text="Optional reason for revocation"
    )


class ShareAccessLogSerializer(serializers.ModelSerializer):
    """Serializer for share access log entries."""

    username = serializers.CharField(
        source='user.username', read_only=True, default='System'
    )

    class Meta:
        model = ShareAccessLog
        fields = [
            'id', 'share', 'user', 'username',
            'action', 'domain', 'success', 'failure_reason',
            'ip_address', 'details', 'timestamp',
        ]
        read_only_fields = fields
