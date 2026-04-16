"""DRF serializers for the zk_proofs app."""

from __future__ import annotations

import base64

from rest_framework import serializers

from .models import (
    ZKCommitment,
    ZKSession,
    ZKSessionParticipant,
    ZKVerificationAttempt,
)
from .providers import DEFAULT_SCHEME, available_schemes


class Base64BytesField(serializers.Field):
    """
    Serializer field for binary payloads.

    Input:  tolerant base64 (standard or urlsafe, optional padding).
    Output: canonical standard base64 ASCII string.
    """

    def to_representation(self, value):
        if isinstance(value, memoryview):
            value = bytes(value)
        if value is None:
            return None
        return base64.b64encode(value).decode("ascii")

    def to_internal_value(self, data):
        if not isinstance(data, str):
            raise serializers.ValidationError("Expected a base64-encoded string.")
        # Normalise urlsafe variants so clients can be sloppy.
        s = data.strip().replace("-", "+").replace("_", "/")
        pad = (-len(s)) % 4
        try:
            return base64.b64decode(s + "=" * pad, validate=True)
        except (ValueError, base64.binascii.Error) as exc:
            raise serializers.ValidationError(f"Invalid base64: {exc}") from exc


class ZKCommitmentSerializer(serializers.ModelSerializer):
    commitment = Base64BytesField()

    class Meta:
        model = ZKCommitment
        fields = [
            "id",
            "scope_type",
            "scope_id",
            "commitment",
            "scheme",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class ZKCommitmentCreateSerializer(serializers.Serializer):
    scope_type = serializers.ChoiceField(choices=ZKCommitment.SCOPE_CHOICES)
    scope_id = serializers.CharField(max_length=128)
    commitment = Base64BytesField()
    scheme = serializers.CharField(required=False, default=DEFAULT_SCHEME)

    def validate_scheme(self, value):
        if value not in available_schemes():
            raise serializers.ValidationError(f"Unsupported ZK scheme: {value}")
        return value


class ZKEqualityProofSerializer(serializers.Serializer):
    commitment_a_id = serializers.UUIDField()
    commitment_b_id = serializers.UUIDField()
    proof_T = Base64BytesField()
    proof_s = Base64BytesField()


class ZKVerificationAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = ZKVerificationAttempt
        fields = [
            "id",
            "commitment_a",
            "commitment_b",
            "scheme",
            "result",
            "error_message",
            "created_at",
        ]
        read_only_fields = fields


class ZKSessionCreateSerializer(serializers.Serializer):
    """Payload for creating a new multi-party verification session."""

    reference_commitment_id = serializers.UUIDField()
    title = serializers.CharField(max_length=128, required=False, allow_blank=True, default="")
    description = serializers.CharField(required=False, allow_blank=True, default="")
    expires_in_hours = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=24 * 30,
        default=24 * 7,
        help_text="Session auto-expires after this many hours. Max 30 days.",
    )


class ZKSessionParticipantPublicSerializer(serializers.ModelSerializer):
    """Participant projection visible to the session owner."""

    class Meta:
        model = ZKSessionParticipant
        fields = [
            "id",
            "invited_email",
            "invited_label",
            "status",
            "error_message",
            "created_at",
            "verified_at",
            "participant_commitment",
            "attempt",
        ]
        read_only_fields = fields


class ZKSessionParticipantOwnerSerializer(ZKSessionParticipantPublicSerializer):
    """Owner view includes the invite token so the owner can share it."""

    class Meta(ZKSessionParticipantPublicSerializer.Meta):
        fields = ZKSessionParticipantPublicSerializer.Meta.fields + ["invite_token"]
        read_only_fields = fields


class ZKSessionSerializer(serializers.ModelSerializer):
    participants = ZKSessionParticipantOwnerSerializer(many=True, read_only=True)
    participant_count = serializers.SerializerMethodField()
    verified_count = serializers.SerializerMethodField()
    failed_count = serializers.SerializerMethodField()
    pending_count = serializers.SerializerMethodField()

    class Meta:
        model = ZKSession
        fields = [
            "id",
            "title",
            "description",
            "status",
            "reference_commitment",
            "expires_at",
            "created_at",
            "closed_at",
            "participants",
            "participant_count",
            "verified_count",
            "failed_count",
            "pending_count",
        ]
        read_only_fields = fields

    def get_participant_count(self, obj) -> int:
        return obj.participants.count()

    def get_verified_count(self, obj) -> int:
        return obj.participants.filter(status=ZKSessionParticipant.STATUS_VERIFIED).count()

    def get_failed_count(self, obj) -> int:
        return obj.participants.filter(status=ZKSessionParticipant.STATUS_FAILED).count()

    def get_pending_count(self, obj) -> int:
        return obj.participants.filter(
            status__in=[
                ZKSessionParticipant.STATUS_PENDING,
                ZKSessionParticipant.STATUS_JOINED,
            ]
        ).count()


class ZKSessionInviteSerializer(serializers.Serializer):
    """Payload the owner posts to add a new invite slot to an open session."""

    invited_email = serializers.EmailField(required=False, allow_blank=True, default="")
    invited_label = serializers.CharField(max_length=128, required=False, allow_blank=True, default="")


class ZKSessionJoinInfoSerializer(serializers.Serializer):
    """Projection returned to the invitee when they resolve their token.

    Intentionally omits the reference commitment bytes and other participant
    tokens so the invitee only sees what they need to produce a proof.
    """

    session_id = serializers.UUIDField()
    participant_id = serializers.UUIDField()
    status = serializers.CharField()
    title = serializers.CharField()
    description = serializers.CharField()
    scheme = serializers.CharField()
    reference_commitment_id = serializers.UUIDField()
    reference_commitment_b64 = serializers.CharField()
    reference_scope_type = serializers.CharField()
    reference_scope_id = serializers.CharField()
    expires_at = serializers.DateTimeField()


class ZKSessionSubmitProofSerializer(serializers.Serializer):
    """Proof submission by a session invitee.

    ``participant_commitment_id`` must belong to the authenticated user. The
    server computes the Schnorr verification of ``(proof_T, proof_s)`` against
    the session's reference commitment and the participant's commitment.
    """

    invite_token = serializers.CharField(max_length=80)
    participant_commitment_id = serializers.UUIDField()
    proof_T = Base64BytesField()
    proof_s = Base64BytesField()
