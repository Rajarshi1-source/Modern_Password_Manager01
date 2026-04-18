from django.contrib import admin

from .models import (
    MoralFrameworkSnapshot,
    PersonalityAuditLog,
    PersonalityChallenge,
    PersonalityProfile,
    PersonalityQuestion,
    PersonalityResponse,
)


@admin.register(PersonalityProfile)
class PersonalityProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'opted_in', 'source_messages_analysed', 'last_inferred_at')
    search_fields = ('user__email', 'user__username')
    list_filter = ('opted_in',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(MoralFrameworkSnapshot)
class MoralFrameworkSnapshotAdmin(admin.ModelAdmin):
    list_display = ('profile', 'confidence', 'sample_size', 'created_at')
    readonly_fields = ('created_at',)


@admin.register(PersonalityQuestion)
class PersonalityQuestionAdmin(admin.ModelAdmin):
    list_display = ('profile', 'dimension', 'difficulty', 'single_use', 'used_count', 'created_at')
    list_filter = ('dimension', 'difficulty', 'single_use')


@admin.register(PersonalityChallenge)
class PersonalityChallengeAdmin(admin.ModelAdmin):
    list_display = ('profile', 'status', 'intent', 'achieved_score', 'required_score', 'created_at')
    list_filter = ('status', 'intent', 'mood_context')


@admin.register(PersonalityResponse)
class PersonalityResponseAdmin(admin.ModelAdmin):
    list_display = ('challenge', 'question', 'consistency_score', 'submitted_at')


@admin.register(PersonalityAuditLog)
class PersonalityAuditLogAdmin(admin.ModelAdmin):
    list_display = ('profile', 'event_type', 'challenge', 'created_at')
    list_filter = ('event_type',)
    readonly_fields = ('entry_hash', 'previous_hash', 'created_at')
