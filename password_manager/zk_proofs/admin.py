from django.contrib import admin

from .models import ZKCommitment, ZKSession, ZKSessionParticipant, ZKVerificationAttempt


@admin.register(ZKCommitment)
class ZKCommitmentAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "scope_type", "scope_id", "scheme", "created_at")
    list_filter = ("scope_type", "scheme")
    search_fields = ("user__email", "scope_id")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(ZKVerificationAttempt)
class ZKVerificationAttemptAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "commitment_a", "commitment_b", "result", "scheme", "created_at")
    list_filter = ("result", "scheme")
    search_fields = ("user__email",)
    readonly_fields = ("id", "created_at")


class ZKSessionParticipantInline(admin.TabularInline):
    model = ZKSessionParticipant
    extra = 0
    readonly_fields = (
        "id",
        "invite_token",
        "status",
        "user",
        "participant_commitment",
        "error_message",
        "created_at",
        "verified_at",
        "attempt",
    )
    fields = readonly_fields + ("invited_email", "invited_label")


@admin.register(ZKSession)
class ZKSessionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "owner",
        "title",
        "status",
        "reference_commitment",
        "expires_at",
        "created_at",
    )
    list_filter = ("status",)
    search_fields = ("owner__email", "title")
    readonly_fields = ("id", "created_at", "closed_at")
    inlines = [ZKSessionParticipantInline]


@admin.register(ZKSessionParticipant)
class ZKSessionParticipantAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "session",
        "status",
        "user",
        "invited_email",
        "invited_label",
        "created_at",
        "verified_at",
    )
    list_filter = ("status",)
    search_fields = ("invited_email", "invited_label", "user__email")
    readonly_fields = (
        "id",
        "invite_token",
        "created_at",
        "verified_at",
        "attempt",
        "participant_commitment",
    )
