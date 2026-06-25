"""Admin registrations for bug-bounty self-pentest models."""

from __future__ import annotations

from django.contrib import admin

from .models import Finding, SelfTestRun


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
