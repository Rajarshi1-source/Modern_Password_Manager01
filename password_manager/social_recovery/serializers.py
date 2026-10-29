"""DRF serializers for the social_recovery API."""
from __future__ import annotations

import base64
import binascii
from typing import Any

from rest_framework import serializers

from shared import sealed_shares

from .models import (
    RecoveryCircle,
    RelationshipCommitment,
    SocialRecoveryAuditLog,
    SocialRecoveryRequest,
    VouchAttestation,
    Voucher,
)


def _b64_decode(value: Any, field_name: str) -> bytes:
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value)
    if not isinstance(value, str):
        raise serializers.ValidationError({field_name: "must be a base64 string"})
    try:
        return base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise serializers.ValidationError({field_name: "invalid base64"})


def _sealed(decoder, message, value):
    """``decoder(value)``, or a validation error with the fixed ``message``."""
    raw = decoder(value)
    if raw is None:
        raise serializers.ValidationError(message)
    return raw


def _b64_encode(blob: Any) -> str:
    if blob is None:
        return ""
    return base64.b64encode(bytes(blob)).decode("ascii")


class VoucherInputSerializer(serializers.Serializer):
    """Single voucher entry used by ``POST /circles/``."""

    user_id = serializers.IntegerField(required=False, allow_null=True)
    did_string = serializers.CharField(required=False, allow_blank=True, max_length=255)
    email = serializers.EmailField(required=False, allow_blank=True)
    display_name = serializers.CharField(required=False, allow_blank=True, max_length=128)
    ed25519_public_key = serializers.CharField(max_length=128)
    relationship_label = serializers.CharField(required=False, allow_blank=True, max_length=64)
    vouch_weight = serializers.IntegerField(required=False, default=1, min_value=1, max_value=10)
    stake_amount = serializers.IntegerField(required=False, default=0, min_value=0)
    # Sealed on the owner's device (shared/sealed_shares.py).
    hybrid_public_key = serializers.CharField()
    share_index = serializers.IntegerField(min_value=1, max_value=255)
    sealed_share = serializers.CharField()
    share_proof_hash = serializers.CharField()

    def validate_hybrid_public_key(self, value):
        return _sealed(sealed_shares.decode_hybrid_public_key,
                       sealed_shares.INVALID_HYBRID_PUBLIC_KEY, value)

    def validate_sealed_share(self, value):
        return _sealed(sealed_shares.decode_sealed_share,
                       sealed_shares.INVALID_SEALED_SHARE, value)

    def validate_share_proof_hash(self, value):
        return _sealed(sealed_shares.decode_digest, sealed_shares.INVALID_DIGEST, value)

    def validate(self, attrs):
        if not any(
            [
                attrs.get("user_id"),
                attrs.get("did_string"),
                attrs.get("email"),
            ]
        ):
            raise serializers.ValidationError(
                "voucher must specify at least one of user_id / did_string / email"
            )
        return attrs


class CreateCircleSerializer(serializers.Serializer):
    # The seed is split and sealed on the owner's device; only its check is sent.
    secret_check = serializers.CharField()
    threshold = serializers.IntegerField(min_value=2, max_value=10)
    min_voucher_reputation = serializers.IntegerField(required=False, default=0, min_value=0)
    min_total_stake = serializers.IntegerField(required=False, default=0, min_value=0)
    cooldown_hours = serializers.IntegerField(required=False, default=24, min_value=0)
    vouchers = VoucherInputSerializer(many=True)

    def to_internal_value(self, data):
        if hasattr(data, "keys") and any(
            k in data for k in ("master_secret_hex", "secret_hex", "secret")
        ):
            raise serializers.ValidationError(
                {"master_secret_hex": "send sealed shares only; the recovery seed "
                                      "never leaves your device"}
            )
        return super().to_internal_value(data)

    def validate_secret_check(self, value):
        return _sealed(sealed_shares.decode_digest, sealed_shares.INVALID_DIGEST, value)


class VoucherSerializer(serializers.ModelSerializer):
    class Meta:
        model = Voucher
        fields = (
            "voucher_id",
            "circle",
            "user",
            "did_string",
            "email",
            "display_name",
            "ed25519_public_key",
            "relationship_label",
            "vouch_weight",
            "share_index",
            "stake_amount",
            "status",
            "invitation_expires_at",
            "accepted_at",
            "created_at",
        )
        read_only_fields = fields


class RelationshipCommitmentSerializer(serializers.ModelSerializer):
    pedersen_commitment_b64 = serializers.SerializerMethodField()

    class Meta:
        model = RelationshipCommitment
        fields = ("commitment_id", "voucher", "pedersen_commitment_b64", "salt_hash", "created_at")
        read_only_fields = fields

    def get_pedersen_commitment_b64(self, obj):
        return _b64_encode(obj.pedersen_commitment)


class CircleSerializer(serializers.ModelSerializer):
    vouchers = VoucherSerializer(many=True, read_only=True)
    secret_commitment_b64 = serializers.SerializerMethodField()

    class Meta:
        model = RecoveryCircle
        fields = (
            "circle_id",
            "user",
            "threshold",
            "total_vouchers",
            "status",
            "min_voucher_reputation",
            "min_total_stake",
            "cooldown_hours",
            "created_at",
            "activated_at",
            "secret_commitment_b64",
            "vouchers",
        )
        read_only_fields = fields

    def get_secret_commitment_b64(self, obj):
        return _b64_encode(obj.secret_commitment)


class AcceptInvitationSerializer(serializers.Serializer):
    invitation_token = serializers.CharField(max_length=128)
    signature_b64 = serializers.CharField()
    share_proof = serializers.CharField()

    def to_internal_value(self, data):
        cleaned = super().to_internal_value(data)
        cleaned["signature"] = _b64_decode(cleaned.pop("signature_b64"), "signature_b64")
        return cleaned


class InitiateRequestSerializer(serializers.Serializer):
    circle_id = serializers.UUIDField()
    initiator_email = serializers.EmailField(required=False, allow_blank=True)
    device_fingerprint = serializers.CharField(required=False, allow_blank=True, max_length=128)
    geo = serializers.JSONField(required=False, default=dict)
    requester_public_key = serializers.CharField()
    abandon_token_hash = serializers.CharField(required=False)

    def validate_requester_public_key(self, value):
        return _sealed(sealed_shares.decode_hybrid_public_key,
                       sealed_shares.INVALID_HYBRID_PUBLIC_KEY, value)

    def validate_abandon_token_hash(self, value):
        return _sealed(sealed_shares.decode_digest, sealed_shares.INVALID_DIGEST, value)


class AttestationSerializer(serializers.Serializer):
    voucher_id = serializers.UUIDField()
    decision = serializers.ChoiceField(choices=("approve", "deny"))
    signature_b64 = serializers.CharField()
    fresh_commitment_b64 = serializers.CharField(required=False, allow_blank=True)
    proof_T_b64 = serializers.CharField(required=False, allow_blank=True)
    proof_s_b64 = serializers.CharField(required=False, allow_blank=True)
    stake_amount = serializers.IntegerField(required=False, default=0, min_value=0)
    resealed_share = serializers.CharField(required=False, allow_blank=True)

    def to_internal_value(self, data):
        cleaned = super().to_internal_value(data)
        cleaned["signature"] = _b64_decode(cleaned.pop("signature_b64"), "signature_b64")
        resealed = cleaned.pop("resealed_share", "")
        cleaned["resealed_share"] = None
        if resealed:
            cleaned["resealed_share"] = sealed_shares.decode_sealed_share(resealed)
            if cleaned["resealed_share"] is None:
                raise serializers.ValidationError(
                    {"resealed_share": sealed_shares.INVALID_SEALED_SHARE})
        for key in ("fresh_commitment", "proof_T", "proof_s"):
            src = cleaned.pop(f"{key}_b64", "")
            cleaned[key] = _b64_decode(src, f"{key}_b64") if src else None
        return cleaned


class AttestationDetailSerializer(serializers.ModelSerializer):
    signature_b64 = serializers.SerializerMethodField()

    class Meta:
        model = VouchAttestation
        fields = (
            "attestation_id",
            "request",
            "voucher",
            "decision",
            "stake_committed",
            "attested_at",
            "signature_b64",
        )
        read_only_fields = fields

    def get_signature_b64(self, obj):
        return _b64_encode(obj.ed25519_signature)


class RequestSerializer(serializers.ModelSerializer):
    attestations = AttestationDetailSerializer(many=True, read_only=True)
    # Guardians re-seal their shares to this key after checking its
    # fingerprint with the requester over another channel.
    requester_public_key = serializers.SerializerMethodField()

    def get_requester_public_key(self, obj):
        return _b64_encode(obj.requester_public_key)

    class Meta:
        model = SocialRecoveryRequest
        fields = (
            "request_id",
            "circle",
            "status",
            "initiator_email",
            "required_approvals",
            "received_approvals",
            "total_weight",
            "total_stake_committed",
            "challenge_nonce",
            "risk_score",
            "requester_public_key",
            "created_at",
            "expires_at",
            "completed_at",
            "attestations",
        )
        read_only_fields = fields


class AuditLogSerializer(serializers.ModelSerializer):
    entry_hash_hex = serializers.SerializerMethodField()
    prev_hash_hex = serializers.SerializerMethodField()

    class Meta:
        model = SocialRecoveryAuditLog
        fields = (
            "entry_id",
            "event_type",
            "event_data",
            "user",
            "circle",
            "created_at",
            "prev_hash_hex",
            "entry_hash_hex",
        )
        read_only_fields = fields

    def get_entry_hash_hex(self, obj):
        return bytes(obj.entry_hash).hex()

    def get_prev_hash_hex(self, obj):
        return bytes(obj.prev_hash or b"").hex()
