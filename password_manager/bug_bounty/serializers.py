"""DRF serializers for the bug-bounty self-pentest and bounty-program APIs."""

from __future__ import annotations

from decimal import Decimal

from rest_framework import serializers

from .models import (
    BountyProgram,
    Finding,
    FindingStatus,
    ProgramStatus,
    Reward,
    SelfTestRun,
    Severity,
    Submission,
    SubmissionStatus,
)
from .rewards.adapters import available_adapters


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


# --------------------------------------------------------------------------- #
# Phase 2 — bounty program / submissions / rewards
# --------------------------------------------------------------------------- #


class BountyProgramSerializer(serializers.ModelSerializer):
    """Serialize a bounty program; owner is set from the request, not the body."""

    owner_username = serializers.CharField(source='owner.username', read_only=True)
    submission_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = BountyProgram
        fields = (
            'id', 'owner_username', 'title', 'description', 'scope', 'policy',
            'reward_tiers', 'status', 'submission_count', 'created_at', 'updated_at',
        )
        # owner is taken from request.user; counts/timestamps are derived.
        read_only_fields = (
            'id', 'owner_username', 'submission_count', 'created_at', 'updated_at',
        )

    def validate_scope(self, value):
        """Scope must be a JSON list of in-scope targets."""
        if not isinstance(value, list):
            raise serializers.ValidationError('Scope must be a list of in-scope targets.')
        return value

    def validate_reward_tiers(self, value):
        """Reward tiers must map known severities to non-negative amounts."""
        if not isinstance(value, dict):
            raise serializers.ValidationError(
                'Reward tiers must be an object mapping severity to amount.'
            )
        valid = set(Severity.values)
        for severity, amount in value.items():
            if severity not in valid:
                raise serializers.ValidationError(f'Unknown severity tier "{severity}".')
            if not isinstance(amount, (int, float)) or isinstance(amount, bool) or amount < 0:
                raise serializers.ValidationError(
                    f'Reward for "{severity}" must be a non-negative number.'
                )
        return value


class RewardSerializer(serializers.ModelSerializer):
    """Read-only view of a reward obligation; mutated only via the service layer."""

    class Meta:
        model = Reward
        fields = (
            'id', 'amount', 'currency', 'status', 'adapter', 'payout_ref',
            'created_at', 'paid_at',
        )
        read_only_fields = fields


class SubmissionSerializer(serializers.ModelSerializer):
    """Serialize a researcher submission; only the initial report fields are writable."""

    program_title = serializers.CharField(source='program.title', read_only=True)
    researcher_username = serializers.CharField(source='researcher.username', read_only=True)
    reward = RewardSerializer(read_only=True)

    class Meta:
        model = Submission
        fields = (
            'id', 'program', 'program_title', 'researcher_username', 'title',
            'description', 'severity_claimed', 'severity_assigned', 'status',
            'triage_note', 'reward', 'created_at', 'updated_at',
        )
        # Everything past the researcher's initial report is owned by triage.
        read_only_fields = (
            'id', 'program_title', 'researcher_username', 'severity_assigned',
            'status', 'triage_note', 'reward', 'created_at', 'updated_at',
        )

    def validate_program(self, program):
        """Reports may only be filed against an active program."""
        if program.status != ProgramStatus.ACTIVE:
            raise serializers.ValidationError(
                'This program is not currently accepting submissions.'
            )
        return program


class TransitionSerializer(serializers.Serializer):
    """Input for a generic triage transition (owner-driven)."""

    to_status = serializers.ChoiceField(choices=SubmissionStatus.choices)
    severity_assigned = serializers.ChoiceField(
        choices=Severity.choices, required=False, allow_blank=True, default='',
    )
    note = serializers.CharField(required=False, allow_blank=True, default='', max_length=2000)


class IssueRewardSerializer(serializers.Serializer):
    """Input for recording a reward obligation on a resolved submission."""

    amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal('0.01'),
    )
    currency = serializers.CharField(max_length=3, required=False, default='USD')
    adapter = serializers.CharField(max_length=64, required=False, default='manual')
    note = serializers.CharField(required=False, allow_blank=True, default='', max_length=2000)

    def validate_adapter(self, value):
        """Only a registered payout adapter may be named."""
        if value not in available_adapters():
            raise serializers.ValidationError(f'Unknown payout adapter "{value}".')
        return value

    def validate_currency(self, value):
        """Normalise to an upper-case 3-letter currency code."""
        if not value.isalpha() or len(value) != 3:
            raise serializers.ValidationError('Currency must be a 3-letter code, e.g. "USD".')
        return value.upper()
