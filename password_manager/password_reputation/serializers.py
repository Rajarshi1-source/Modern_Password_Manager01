"""DRF serializers for password_reputation."""

from __future__ import annotations

import base64

from rest_framework import serializers

from .models import AnchorBatch, ReputationAccount, ReputationEvent, ReputationProof
from .providers import DEFAULT_SCHEME, available_schemes


class Base64BytesField(serializers.Field):
    """Mirror of the zk_proofs Base64BytesField — tolerant on input, canonical on output."""

    def to_representation(self, value):
        if isinstance(value, memoryview):
            value = bytes(value)
        if value is None:
            return None
        return base64.b64encode(value).decode("ascii")

    def to_internal_value(self, data):
        if not isinstance(data, str):
            raise serializers.ValidationError("Expected a base64-encoded string.")
        s = data.strip().replace("-", "+").replace("_", "/")
        pad = (-len(s)) % 4
        try:
            return base64.b64decode(s + "=" * pad, validate=True)
        except (ValueError, base64.binascii.Error) as exc:
            raise serializers.ValidationError(f"Invalid base64: {exc}") from exc


class ReputationProofSubmitSerializer(serializers.Serializer):
    """Payload accepted by POST /api/reputation/submit-proof/."""

    scope_id = serializers.CharField(max_length=128)
    commitment = Base64BytesField()
    claimed_entropy_bits = serializers.IntegerField(min_value=0, max_value=1024)
    binding_hash = Base64BytesField()
    scheme = serializers.CharField(required=False, default=DEFAULT_SCHEME)

    def validate_scheme(self, value):
        if value not in available_schemes():
            raise serializers.ValidationError(f"Unsupported reputation scheme: {value}")
        return value


class ReputationAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReputationAccount
        fields = [
            "score",
            "tokens",
            "proofs_accepted",
            "proofs_rejected",
            "last_proof_at",
            "last_breach_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ReputationProofSerializer(serializers.ModelSerializer):
    commitment = Base64BytesField()

    class Meta:
        model = ReputationProof
        fields = [
            "id",
            "scheme",
            "scope_id",
            "commitment",
            "claimed_entropy_bits",
            "status",
            "score_delta",
            "tokens_delta",
            "error_message",
            "created_at",
        ]
        read_only_fields = fields


class AnchorBatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnchorBatch
        fields = [
            "id",
            "adapter",
            "merkle_root",
            "batch_size",
            "status",
            "tx_hash",
            "block_number",
            "network",
            "error_message",
            "created_at",
            "submitted_at",
            "confirmed_at",
        ]
        read_only_fields = fields


class ReputationEventSerializer(serializers.ModelSerializer):
    leaf_hash = Base64BytesField()
    anchor_batch = AnchorBatchSerializer(read_only=True)

    class Meta:
        model = ReputationEvent
        fields = [
            "id",
            "event_type",
            "score_delta",
            "tokens_delta",
            "proof",
            "leaf_hash",
            "anchor_batch",
            "anchor_status",
            "note",
            "created_at",
        ]
        read_only_fields = fields


class LeaderboardEntrySerializer(serializers.Serializer):
    """Public leaderboard row — intentionally minimal."""

    rank = serializers.IntegerField()
    user_id = serializers.IntegerField()
    username = serializers.CharField()
    score = serializers.IntegerField()
    tokens = serializers.IntegerField()
    proofs_accepted = serializers.IntegerField()
