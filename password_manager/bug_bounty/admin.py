"""Admin registrations for bug-bounty self-pentest models."""

from __future__ import annotations

from django.contrib import admin

from .models import (
    BountyProgram,
    Finding,
    Reward,
    SelfTestRun,
    Submission,
)


@admin.register(SelfTestRun)
class SelfTestRunAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'trigger', 'status', 'started_at', 'completed_at')
    list_filter = ('trigger', 'status')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('id', 'started_at', 'completed_at', 'summary')


@admin.register(Finding)
class FindingAdmin(admin.ModelAdmin):
    list_display = ('check_id', 'user', 'severity', 'status', 'last_seen')
    list_filter = ('severity', 'status', 'check_id')
    search_fields = ('user__username', 'user__email', 'check_id', 'title')
    readonly_fields = ('id', 'first_seen', 'last_seen', 'evidence', 'fingerprint')


@admin.register(BountyProgram)
class BountyProgramAdmin(admin.ModelAdmin):
    list_display = ('title', 'owner', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('title', 'owner__username', 'owner__email')
    readonly_fields = ('id', 'created_at', 'updated_at')


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = (
        'title', 'program', 'researcher', 'status',
        'severity_claimed', 'severity_assigned', 'created_at',
    )
    list_filter = ('status', 'severity_claimed', 'severity_assigned')
    search_fields = (
        'title', 'program__title', 'researcher__username', 'researcher__email',
    )
    readonly_fields = ('id', 'created_at', 'updated_at')


@admin.register(Reward)
class RewardAdmin(admin.ModelAdmin):
    list_display = ('submission', 'amount', 'currency', 'status', 'adapter', 'paid_at')
    list_filter = ('status', 'currency', 'adapter')
    search_fields = ('submission__title', 'payout_ref')
    readonly_fields = ('id', 'created_at', 'updated_at', 'paid_at', 'payout_ref')
