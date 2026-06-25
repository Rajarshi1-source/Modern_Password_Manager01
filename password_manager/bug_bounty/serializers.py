"""DRF serializers for the bug-bounty self-pentest API."""

from __future__ import annotations

from rest_framework import serializers

from .models import Finding, FindingStatus, SelfTestRun


class FindingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Finding
        fields = (
            'id', 'check_id', 'title', 'severity', 'status', 'remediation',
            'evidence', 'first_seen', 'last_seen', 'resolved_at',
        )
        # Only `status` is writable (acknowledge / resolve / false-positive);
        # everything else is owned by the harness.
        read_only_fields = (
            'id', 'check_id', 'title', 'severity', 'remediation', 'evidence',
            'first_seen', 'last_seen', 'resolved_at',
        )

    def validate_status(self, value):
        allowed = {
            FindingStatus.OPEN,
            FindingStatus.ACKNOWLEDGED,
            FindingStatus.RESOLVED,
            FindingStatus.FALSE_POSITIVE,
        }
        if value not in allowed:
            raise serializers.ValidationError('Invalid finding status.')
        return value


class SelfTestRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = SelfTestRun
        fields = ('id', 'trigger', 'status', 'summary', 'started_at', 'completed_at')
        read_only_fields = fields
