from django.contrib import admin

from .models import (
    CircadianProfile,
    CircadianTOTPDevice,
    SleepObservation,
    WearableLink,
)


@admin.register(CircadianProfile)
class CircadianProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "chronotype",
        "baseline_sleep_midpoint_minutes",
        "phase_stddev_minutes",
        "phase_lock_minutes",
        "sample_count",
        "last_calibrated_at",
    )
    search_fields = ("user__username", "user__email")


@admin.register(SleepObservation)
class SleepObservationAdmin(admin.ModelAdmin):
    list_display = ("user", "provider", "sleep_start", "sleep_end", "efficiency_score")
    list_filter = ("provider",)
    search_fields = ("user__username",)


@admin.register(WearableLink)
class WearableLinkAdmin(admin.ModelAdmin):
    list_display = ("user", "provider", "expires_at", "last_synced_at")
    list_filter = ("provider",)
    search_fields = ("user__username",)


@admin.register(CircadianTOTPDevice)
class CircadianTOTPDeviceAdmin(admin.ModelAdmin):
    list_display = ("user", "name", "confirmed", "last_verified_at", "created_at")
    list_filter = ("confirmed", "drift_algorithm")
    search_fields = ("user__username",)
