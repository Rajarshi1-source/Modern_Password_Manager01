"""DRF serializers for decentralized_identity."""

from __future__ import annotations

from rest_framework import serializers

from .models import (
    CredentialSchema,
    UserDID,
    VCPresentation,
    VerifiableCredential,
)


class UserDIDSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserDID
        fields = (
            "id",
            "did_string",
            "public_key_multibase",
            "algorithm",
            "is_primary",
            "created_at",
        )
        read_only_fields = ("id", "created_at")


class CredentialSchemaSerializer(serializers.ModelSerializer):
    class Meta:
        model = CredentialSchema
        fields = ("schema_id", "name", "version", "context_urls")


class VCSerializer(serializers.ModelSerializer):
    schema = serializers.SlugRelatedField(read_only=True, slug_field="schema_id")

    class Meta:
        model = VerifiableCredential
        fields = (
            "id",
            "subject_did",
            "issuer_did",
            "schema",
            "jwt_vc",
            "jsonld_vc",
            "status",
            "issued_at",
            "expires_at",
            "storage_refs",
        )


class VCSummarySerializer(serializers.ModelSerializer):
    schema = serializers.SlugRelatedField(read_only=True, slug_field="schema_id")

    class Meta:
        model = VerifiableCredential
        fields = (
            "id",
            "schema",
            "subject_did",
            "issuer_did",
            "status",
            "issued_at",
            "expires_at",
            "storage_refs",
        )


class VPSerializer(serializers.ModelSerializer):
    class Meta:
        model = VCPresentation
        fields = (
            "id",
            "holder_did",
            "presented_to",
            "verified",
            "verification_errors",
            "presented_at",
        )


class RegisterDIDSerializer(serializers.Serializer):
    did_string = serializers.CharField(max_length=255)
    public_key_multibase = serializers.CharField(max_length=128)
    make_primary = serializers.BooleanField(required=False, default=True)


class IssueVCSerializer(serializers.Serializer):
    subject_did = serializers.CharField(max_length=255)
    schema_id = serializers.CharField(max_length=128)
    credential_subject = serializers.DictField()
    validity_days = serializers.IntegerField(
        required=False, default=365, min_value=1, max_value=3650
    )


class VerifyVPSerializer(serializers.Serializer):
    vp_jwt = serializers.CharField()
    nonce = serializers.CharField(required=False, allow_blank=True, default="")
    audience = serializers.CharField(required=False, allow_blank=True, default="")


class ChallengeSerializer(serializers.Serializer):
    did_string = serializers.CharField(max_length=255)


class SignInVerifySerializer(serializers.Serializer):
    did_string = serializers.CharField(max_length=255)
    nonce = serializers.CharField(max_length=128)
    vp_jwt = serializers.CharField()
