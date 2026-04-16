from django.contrib import admin

from .models import (
    AmbientContext,
    AmbientObservation,
    AmbientProfile,
    AmbientSignalConfig,
)


@admin.register(AmbientProfile)
class AmbientProfileAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "device_fp",
        "local_salt_version",
        "samples_used",
        "last_observation_at",
        "updated_at",
    )
    search_fields = ("user__email", "user__username", "device_fp")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(AmbientContext)
class AmbientContextAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "label",
        "profile",
        "is_trusted",
        "radius",
        "samples_used",
        "last_matched_at",
    )
    list_filter = ("is_trusted",)
    search_fields = ("label", "profile__user__email", "profile__user__username")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(AmbientObservation)
class AmbientObservationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "surface",
        "matched_context",
        "trust_score",
        "novelty_score",
        "created_at",
    )
    list_filter = ("surface", "schema_version")
    search_fields = ("user__email", "user__username", "embedding_digest")
    readonly_fields = ("id", "created_at")


@admin.register(AmbientSignalConfig)
class AmbientSignalConfigAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "signal_key", "enabled", "updated_at")
    list_filter = ("enabled", "signal_key")
    search_fields = ("user__email", "user__username", "signal_key")
    readonly_fields = ("id", "created_at", "updated_at")
