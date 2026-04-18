"""
Personality-Based Auth Models
=============================

Data-store for the AI-driven, personalized security-question feature.

Entities
--------

- :class:`PersonalityProfile` — per-user opt-in container that holds
  long-lived personality features learned from conversations. Gated behind
  ``UserPreferences.privacy_analytics``.
- :class:`MoralFrameworkSnapshot` — periodic snapshots of inferred values /
  moral framework coefficients. History is immutable so users can audit
  drift over time.
- :class:`PersonalityQuestion` — generated question templates with a target
  dimension (values, beliefs, preferences, style) and difficulty.
- :class:`PersonalityChallenge` — a live multi-question challenge presented
  to the user for a login / recovery attempt.
- :class:`PersonalityResponse` — the user's answer to a single question in
  a challenge, with the consistency score assigned by the scorer.
- :class:`PersonalityAuditLog` — tamper-evident append-only log of
  inference / challenge / failure events (hash-chained like the
  social-recovery log).

All sensitive free-text (question body, user answers, personality features)
is stored in :class:`models.JSONField` columns so we can control
serialization precisely and keep room for schema evolution without
migrations.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any, Dict, Optional

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class QuestionDimension(models.TextChoices):
    VALUES = 'values', 'Core Values'
    BELIEFS = 'beliefs', 'Beliefs'
    PREFERENCES = 'preferences', 'Preferences'
    STYLE = 'style', 'Communication Style'
    DECISIONS = 'decisions', 'Decision Patterns'
    MEMORIES = 'memories', 'Shared Memories'


class ChallengeStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    IN_PROGRESS = 'in_progress', 'In Progress'
    PASSED = 'passed', 'Passed'
    FAILED = 'failed', 'Failed'
    ABANDONED = 'abandoned', 'Abandoned'
    EXPIRED = 'expired', 'Expired'


class MoodContext(models.TextChoices):
    CALM = 'calm', 'Calm'
    STRESSED = 'stressed', 'Stressed'
    RUSHED = 'rushed', 'Rushed'
    HAPPY = 'happy', 'Happy'
    FRUSTRATED = 'frustrated', 'Frustrated'
    UNKNOWN = 'unknown', 'Unknown'


class AuditEventType(models.TextChoices):
    PROFILE_INFERRED = 'profile_inferred', 'Profile Updated'
    QUESTIONS_GENERATED = 'questions_generated', 'Questions Generated'
    CHALLENGE_CREATED = 'challenge_created', 'Challenge Created'
    CHALLENGE_PRESENTED = 'challenge_presented', 'Challenge Presented'
    RESPONSE_SUBMITTED = 'response_submitted', 'Response Submitted'
    CHALLENGE_PASSED = 'challenge_passed', 'Challenge Passed'
    CHALLENGE_FAILED = 'challenge_failed', 'Challenge Failed'
    CHALLENGE_ABANDONED = 'challenge_abandoned', 'Challenge Abandoned'
    RATE_LIMITED = 'rate_limited', 'Rate Limited'
    MODEL_ERROR = 'model_error', 'Model Error'


# ---------------------------------------------------------------------------
# Core profile
# ---------------------------------------------------------------------------

class PersonalityProfile(models.Model):
    """Per-user personality features learned from conversation history.

    Writing to this model is privacy-sensitive: services MUST verify the
    associated :class:`user.UserPreferences.privacy_analytics` flag is set
    before updating or reading inferred features for challenge generation.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='personality_profile',
    )

    # High-level traits expressed as coefficients / labels. Schema:
    # {"openness": 0.8, "conscientiousness": 0.6, ... , "tags": ["analytical"]}
    trait_features = models.JSONField(default=dict, blank=True)

    # Free-form themes / interests / hobbies ranked by weight.
    # [{"label": "astronomy", "weight": 0.7}, ...]
    theme_weights = models.JSONField(default=list, blank=True)

    # Optional embeddings vector (float list) for similarity scoring.
    embedding = models.JSONField(default=list, blank=True)

    # Track how much data the inference has been trained on.
    source_messages_analysed = models.IntegerField(default=0)
    last_inferred_at = models.DateTimeField(null=True, blank=True)
    inference_model = models.CharField(max_length=128, blank=True, default='')

    # Opt-in tracking. Rarely flipped off once on, but we store the whole
    # consent trail so we can prove compliance with privacy requirements.
    opted_in = models.BooleanField(default=False)
    opt_in_changed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'personality_profile'
        verbose_name = 'Personality Profile'
        verbose_name_plural = 'Personality Profiles'

    def __str__(self) -> str:
        return f"PersonalityProfile({self.user_id})"

    def mark_opted_in(self, opted: bool) -> None:
        self.opted_in = bool(opted)
        self.opt_in_changed_at = timezone.now()
        self.save(update_fields=['opted_in', 'opt_in_changed_at', 'updated_at'])


class MoralFrameworkSnapshot(models.Model):
    """Periodic immutable snapshot of the user's inferred moral framework.

    Includes coefficients for a Moral Foundations-inspired framework
    (care, fairness, loyalty, authority, sanctity, liberty) plus free-form
    value tags. History is append-only; edits create new rows.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(
        PersonalityProfile,
        on_delete=models.CASCADE,
        related_name='framework_snapshots',
    )

    coefficients = models.JSONField(default=dict)  # {"care": 0.7, ...}
    value_tags = models.JSONField(default=list)    # ["honesty", "autonomy"]
    confidence = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
    )
    sample_size = models.IntegerField(default=0)
    inference_model = models.CharField(max_length=128, blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'personality_moral_framework_snapshot'
        verbose_name = 'Moral Framework Snapshot'
        verbose_name_plural = 'Moral Framework Snapshots'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['profile', '-created_at']),
        ]

    def __str__(self) -> str:
        return f"FrameworkSnapshot({self.profile_id} @ {self.created_at:%Y-%m-%d})"


# ---------------------------------------------------------------------------
# Challenge system
# ---------------------------------------------------------------------------

class PersonalityQuestion(models.Model):
    """A generated question template.

    Questions are disposable — after ``single_use`` is True they cannot be
    served again, and a nightly Celery task prunes expired rows. Storing
    them separately from ``PersonalityChallenge`` allows us to (a) budget
    generation costs, (b) rotate pools, and (c) re-use high-quality
    questions across multiple challenges with difficulty tracking.
    """

    DIFFICULTY_EASY = 1
    DIFFICULTY_MEDIUM = 2
    DIFFICULTY_HARD = 3
    DIFFICULTY_CHOICES = [
        (DIFFICULTY_EASY, 'Easy'),
        (DIFFICULTY_MEDIUM, 'Medium'),
        (DIFFICULTY_HARD, 'Hard'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(
        PersonalityProfile,
        on_delete=models.CASCADE,
        related_name='questions',
    )
    dimension = models.CharField(
        max_length=16,
        choices=QuestionDimension.choices,
        default=QuestionDimension.VALUES,
    )
    difficulty = models.IntegerField(
        choices=DIFFICULTY_CHOICES,
        default=DIFFICULTY_MEDIUM,
    )

    prompt = models.TextField(help_text="Question text shown to the user")
    choices = models.JSONField(
        default=list,
        blank=True,
        help_text="Optional ordered list of multiple-choice answers",
    )
    expected_signature = models.JSONField(
        default=dict,
        blank=True,
        help_text="Structured expected answer, e.g. {'top': 'a', 'avoid': ['c']}",
    )
    rationale = models.TextField(
        blank=True,
        default='',
        help_text="LLM rationale for why this question probes the target dimension",
    )

    single_use = models.BooleanField(default=True)
    used_count = models.IntegerField(default=0)
    last_used_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    generator_model = models.CharField(max_length=128, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'personality_question'
        verbose_name = 'Personality Question'
        verbose_name_plural = 'Personality Questions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['profile', 'dimension', '-created_at']),
            models.Index(fields=['expires_at']),
        ]


class PersonalityChallenge(models.Model):
    """A bundle of questions presented to the user at authentication time."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(
        PersonalityProfile,
        on_delete=models.CASCADE,
        related_name='challenges',
    )

    questions = models.ManyToManyField(
        PersonalityQuestion,
        related_name='challenges',
        blank=True,
    )

    status = models.CharField(
        max_length=16,
        choices=ChallengeStatus.choices,
        default=ChallengeStatus.PENDING,
    )
    required_score = models.FloatField(
        default=0.65,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
    )
    achieved_score = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
    )

    mood_context = models.CharField(
        max_length=16,
        choices=MoodContext.choices,
        default=MoodContext.UNKNOWN,
    )
    mood_signals = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    presented_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()

    intent = models.CharField(
        max_length=64,
        default='login',
        help_text="Why the challenge was issued: login|recovery|step_up",
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        db_table = 'personality_challenge'
        verbose_name = 'Personality Challenge'
        verbose_name_plural = 'Personality Challenges'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['profile', '-created_at']),
            models.Index(fields=['status', 'expires_at']),
        ]

    @property
    def is_expired(self) -> bool:
        return self.expires_at and timezone.now() > self.expires_at

    def mark_presented(self):
        self.status = ChallengeStatus.IN_PROGRESS
        self.presented_at = timezone.now()
        self.save(update_fields=['status', 'presented_at'])


class PersonalityResponse(models.Model):
    """A single answer to a question inside a challenge."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    challenge = models.ForeignKey(
        PersonalityChallenge,
        on_delete=models.CASCADE,
        related_name='responses',
    )
    question = models.ForeignKey(
        PersonalityQuestion,
        on_delete=models.CASCADE,
        related_name='responses',
    )

    answer_text = models.TextField(blank=True, default='')
    answer_choice = models.CharField(max_length=128, blank=True, default='')
    answer_metadata = models.JSONField(default=dict, blank=True)

    consistency_score = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
    )
    latency_ms = models.IntegerField(null=True, blank=True)
    rationale = models.TextField(blank=True, default='')

    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'personality_response'
        verbose_name = 'Personality Response'
        verbose_name_plural = 'Personality Responses'
        unique_together = ('challenge', 'question')
        indexes = [
            models.Index(fields=['challenge', '-submitted_at']),
        ]


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------

class PersonalityAuditLog(models.Model):
    """Append-only, hash-chained audit log for personality-auth events.

    Follows the same pattern used by ``social_recovery.SocialRecoveryAuditLog``
    so operators only need to learn one tamper-evident log shape.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(
        PersonalityProfile,
        on_delete=models.CASCADE,
        related_name='audit_log',
    )
    challenge = models.ForeignKey(
        PersonalityChallenge,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_entries',
    )

    event_type = models.CharField(max_length=32, choices=AuditEventType.choices)
    event_payload = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    previous_hash = models.CharField(max_length=128, blank=True, default='')
    entry_hash = models.CharField(max_length=128)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'personality_audit_log'
        verbose_name = 'Personality Audit Log'
        verbose_name_plural = 'Personality Audit Logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['profile', '-created_at']),
            models.Index(fields=['event_type', '-created_at']),
        ]

    def compute_hash(self) -> str:
        """Derive a BLAKE2b hash over (previous_hash, payload, metadata)."""
        payload_bytes = json.dumps(
            {
                'profile': str(self.profile_id),
                'challenge': str(self.challenge_id) if self.challenge_id else None,
                'event_type': self.event_type,
                'event_payload': self.event_payload,
                'ip_address': self.ip_address,
                'previous_hash': self.previous_hash,
            },
            sort_keys=True,
            default=str,
        ).encode('utf-8')
        return hashlib.blake2b(payload_bytes, digest_size=32).hexdigest()
