"""DRF serializers for circadian_totp."""

from __future__ import annotations

from rest_framework import serializers

from .models import (
    CircadianProfile,
    CircadianTOTPDevice,
    SleepObservation,
    WearableLink,
)


class CircadianProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = CircadianProfile
        fields = (
            "chronotype",
            "baseline_sleep_midpoint_minutes",
            "phase_stddev_minutes",
            "phase_lock_minutes",
            "sample_count",
            "last_calibrated_at",
            "updated_at",
        )
        read_only_fields = fields


class SleepObservationSerializer(serializers.ModelSerializer):
    class Meta:
        model = SleepObservation
        fields = (
            "id",
            "provider",
            "sleep_start",
            "sleep_end",
            "efficiency_score",
            "ingested_at",
        )
        read_only_fields = ("id", "ingested_at")


class WearableLinkSerializer(serializers.ModelSerializer):
    linked = serializers.SerializerMethodField()

    class Meta:
        model = WearableLink
        fields = (
            "id",
            "provider",
            "external_user_id",
            "scope",
            "expires_at",
            "last_synced_at",
            "created_at",
            "linked",
        )
        read_only_fields = fields

    def get_linked(self, obj: WearableLink) -> bool:
        return bool(obj.oauth_access_token_encrypted)


class CircadianTOTPDeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = CircadianTOTPDevice
        fields = (
            "id",
            "name",
            "digits",
            "step_seconds",
            "drift_algorithm",
            "confirmed",
            "last_verified_at",
            "created_at",
        )
        read_only_fields = fields


class _ObservationInputSerializer(serializers.Serializer):
    sleep_start = serializers.DateTimeField()
    sleep_end = serializers.DateTimeField()
    efficiency_score = serializers.FloatField(required=False, allow_null=True)

    def validate(self, attrs):
        if attrs["sleep_end"] <= attrs["sleep_start"]:
            raise serializers.ValidationError("sleep_end must be after sleep_start")
        duration_minutes = (
            (attrs["sleep_end"] - attrs["sleep_start"]).total_seconds() / 60
        )
        if duration_minutes < 30 or duration_minutes > 24 * 60:
            raise serializers.ValidationError(
                "sleep window must be between 30 minutes and 24 hours"
            )
        return attrs


class SleepIngestSerializer(serializers.Serializer):
    observations = _ObservationInputSerializer(many=True)

    def validate_observations(self, value):
        if not value:
            raise serializers.ValidationError("at least one observation is required")
        if len(value) > 400:
            raise serializers.ValidationError("too many observations in one request")
        return value
