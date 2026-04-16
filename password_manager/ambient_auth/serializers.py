"""DRF serializers for ambient_auth."""

from __future__ import annotations

from rest_framework import serializers

from .models import (
    AmbientContext,
    AmbientObservation,
    AmbientProfile,
    AmbientSignalConfig,
    SCHEMA_VERSION,
    SIGNAL_KEYS,
    SURFACE_CHOICES,
)


SURFACE_VALUES = [s for s, _ in SURFACE_CHOICES]


class AmbientIngestSerializer(serializers.Serializer):
    """Payload accepted by POST /api/ambient/ingest/."""

    surface = serializers.ChoiceField(choices=SURFACE_VALUES)
    schema_version = serializers.IntegerField(min_value=1, max_value=SCHEMA_VERSION)
    device_fp = serializers.CharField(max_length=128)
    local_salt_version = serializers.IntegerField(min_value=1, max_value=10_000, required=False, default=1)
    signal_availability = serializers.DictField(child=serializers.BooleanField(), required=False, default=dict)
    coarse_features = serializers.DictField(required=False, default=dict)
    embedding_digest = serializers.CharField(max_length=256, required=False, allow_blank=True, default="")
    embedding_vector = serializers.ListField(
        child=serializers.FloatField(),
        required=False,
        max_length=256,
    )


class AmbientContextSerializer(serializers.ModelSerializer):
    class Meta:
        model = AmbientContext
        fields = [
            "id",
            "label",
            "is_trusted",
            "radius",
            "samples_used",
            "last_matched_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "samples_used",
            "last_matched_at",
            "created_at",
            "updated_at",
        ]


class AmbientObservationSerializer(serializers.ModelSerializer):
    matched_context = AmbientContextSerializer(read_only=True)

    class Meta:
        model = AmbientObservation
        fields = [
            "id",
            "surface",
            "schema_version",
            "signal_availability",
            "coarse_features_json",
            "embedding_digest",
            "trust_score",
            "novelty_score",
            "reasons_json",
            "matched_context",
            "created_at",
        ]
        read_only_fields = fields


class AmbientProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = AmbientProfile
        fields = [
            "id",
            "device_fp",
            "local_salt_version",
            "samples_used",
            "last_observation_at",
            "signal_weights_json",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class AmbientSignalConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = AmbientSignalConfig
        fields = [
            "signal_key",
            "enabled",
            "enabled_on_surfaces",
            "updated_at",
        ]
        read_only_fields = ["updated_at"]

    def validate_signal_key(self, value):
        if value not in SIGNAL_KEYS:
            raise serializers.ValidationError(f"Unknown signal_key: {value}")
        return value


class PromoteContextSerializer(serializers.Serializer):
    observation_id = serializers.UUIDField()
    label = serializers.CharField(max_length=64)


class RenameContextSerializer(serializers.Serializer):
    label = serializers.CharField(max_length=64)
