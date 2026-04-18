"""High-level challenge orchestration.

Coordinates question selection, challenge lifecycle, scoring, and audit
logging. Other apps — e.g. authentication/step-up flows — should interact
exclusively through this service rather than touching model rows directly.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Iterable, List, Optional

from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from ..models import (
    AuditEventType,
    ChallengeStatus,
    MoodContext,
    PersonalityChallenge,
    PersonalityProfile,
    PersonalityQuestion,
    PersonalityResponse,
)
from .audit_service import record_event
from .consistency_scorer import ConsistencyScorerService, ScoreResult
from .inference_service import user_opted_in
from .mood_context import MoodContextService, MoodEstimate
from .question_generator import QuestionGeneratorService

logger = logging.getLogger(__name__)


DEFAULT_QUESTIONS_PER_CHALLENGE = 3
DEFAULT_CHALLENGE_TTL_MINUTES = 10
RATE_LIMIT_CACHE_PREFIX = 'personality_auth:rl'
RATE_LIMIT_MAX_ATTEMPTS = 5
RATE_LIMIT_WINDOW_SECONDS = 900  # 15 minutes


@dataclass
class PreparedChallenge:
    challenge: PersonalityChallenge
    questions: List[PersonalityQuestion]
    mood: MoodEstimate


@dataclass
class SubmissionResult:
    response: PersonalityResponse
    score: ScoreResult
    challenge: PersonalityChallenge
    finished: bool
    passed: Optional[bool]


class RateLimited(Exception):
    pass


class ChallengeOrchestrator:
    def __init__(
        self,
        *,
        question_generator: Optional[QuestionGeneratorService] = None,
        scorer: Optional[ConsistencyScorerService] = None,
        mood: Optional[MoodContextService] = None,
    ) -> None:
        self.question_generator = question_generator or QuestionGeneratorService()
        self.scorer = scorer or ConsistencyScorerService()
        self.mood = mood or MoodContextService()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def start_challenge(
        self,
        user,
        *,
        intent: str = 'login',
        ip_address: Optional[str] = None,
        typing_signals: Optional[dict] = None,
        required_score: float = 0.65,
        ttl_minutes: int = DEFAULT_CHALLENGE_TTL_MINUTES,
        question_count: int = DEFAULT_QUESTIONS_PER_CHALLENGE,
    ) -> PreparedChallenge:
        if not user_opted_in(user):
            raise PermissionError("User has not opted in to personality auth")

        self._check_rate_limit(user)

        profile = self._get_or_raise(user)
        mood = self.mood.estimate(user, typing_signals=typing_signals)

        questions = self._select_questions(profile, question_count, mood.context)
        if len(questions) < question_count:
            # Top up the pool lazily.
            try:
                self.question_generator.generate(profile)
            except Exception as exc:
                logger.warning("on-demand question generation failed: %s", exc)
            questions = self._select_questions(profile, question_count, mood.context)

        if not questions:
            raise RuntimeError("No questions available for challenge")

        expires_at = timezone.now() + timedelta(minutes=ttl_minutes)
        with transaction.atomic():
            challenge = PersonalityChallenge.objects.create(
                profile=profile,
                status=ChallengeStatus.PENDING,
                required_score=required_score,
                mood_context=mood.context,
                mood_signals=mood.signals,
                expires_at=expires_at,
                intent=intent,
                ip_address=ip_address,
            )
            challenge.questions.add(*questions)
            for q in questions:
                q.used_count = (q.used_count or 0) + 1
                q.last_used_at = timezone.now()
                q.save(update_fields=['used_count', 'last_used_at'])
            challenge.mark_presented()

        record_event(
            profile,
            AuditEventType.CHALLENGE_CREATED,
            {
                'challenge_id': str(challenge.id),
                'intent': intent,
                'question_count': len(questions),
                'mood': mood.context,
            },
            challenge=challenge,
            ip_address=ip_address,
        )
        return PreparedChallenge(challenge=challenge, questions=list(questions), mood=mood)

    # ------------------------------------------------------------------
    def submit_response(
        self,
        challenge: PersonalityChallenge,
        question: PersonalityQuestion,
        *,
        answer_text: str = '',
        answer_choice: str = '',
        latency_ms: Optional[int] = None,
        answer_metadata: Optional[dict] = None,
    ) -> SubmissionResult:
        if challenge.status not in (ChallengeStatus.PENDING, ChallengeStatus.IN_PROGRESS):
            raise ValueError(f"Challenge is {challenge.status}; cannot accept responses")
        if challenge.is_expired:
            challenge.status = ChallengeStatus.EXPIRED
            challenge.save(update_fields=['status'])
            raise ValueError("Challenge has expired")

        if not challenge.questions.filter(pk=question.pk).exists():
            raise ValueError("Question is not part of this challenge")

        result = self.scorer.score(
            question,
            answer_text=answer_text,
            answer_choice=answer_choice,
            latency_ms=latency_ms,
            trait_features=challenge.profile.trait_features or {},
        )

        with transaction.atomic():
            response, _ = PersonalityResponse.objects.update_or_create(
                challenge=challenge,
                question=question,
                defaults={
                    'answer_text': answer_text,
                    'answer_choice': answer_choice,
                    'answer_metadata': answer_metadata or {},
                    'consistency_score': result.score,
                    'latency_ms': latency_ms,
                    'rationale': result.rationale,
                },
            )

        record_event(
            challenge.profile,
            AuditEventType.RESPONSE_SUBMITTED,
            {
                'challenge_id': str(challenge.id),
                'question_id': str(question.id),
                'score': result.score,
                'hard_fail': result.hard_fail,
            },
            challenge=challenge,
        )

        finished = False
        passed: Optional[bool] = None
        if result.hard_fail:
            self._finalize(challenge, passed=False, aggregate=result.score)
            finished = True
            passed = False
        elif self._all_answered(challenge):
            aggregate = self.scorer.aggregate(challenge.responses.all())
            passed = aggregate >= float(challenge.required_score or 0.65)
            self._finalize(challenge, passed=passed, aggregate=aggregate)
            finished = True

        return SubmissionResult(
            response=response,
            score=result,
            challenge=challenge,
            finished=finished,
            passed=passed,
        )

    # ------------------------------------------------------------------
    def abandon(self, challenge: PersonalityChallenge) -> None:
        if challenge.status in (ChallengeStatus.PASSED, ChallengeStatus.FAILED):
            return
        challenge.status = ChallengeStatus.ABANDONED
        challenge.completed_at = timezone.now()
        challenge.save(update_fields=['status', 'completed_at'])
        record_event(
            challenge.profile,
            AuditEventType.CHALLENGE_ABANDONED,
            {'challenge_id': str(challenge.id)},
            challenge=challenge,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _finalize(self, challenge: PersonalityChallenge, *, passed: bool, aggregate: float) -> None:
        challenge.status = ChallengeStatus.PASSED if passed else ChallengeStatus.FAILED
        challenge.achieved_score = aggregate
        challenge.completed_at = timezone.now()
        challenge.save(update_fields=['status', 'achieved_score', 'completed_at'])
        record_event(
            challenge.profile,
            AuditEventType.CHALLENGE_PASSED if passed else AuditEventType.CHALLENGE_FAILED,
            {'challenge_id': str(challenge.id), 'achieved_score': aggregate},
            challenge=challenge,
        )

    def _all_answered(self, challenge: PersonalityChallenge) -> bool:
        total = challenge.questions.count()
        answered = challenge.responses.exclude(consistency_score__isnull=True).count()
        return total and answered >= total

    def _select_questions(
        self,
        profile: PersonalityProfile,
        count: int,
        mood: str,
    ) -> List[PersonalityQuestion]:
        qs = profile.questions.filter(
            models_q_unused_or_reusable(),
        ).order_by('?')
        if mood == MoodContext.STRESSED:
            qs = qs.order_by('difficulty', '?')
        elif mood == MoodContext.FRUSTRATED:
            qs = qs.filter(difficulty__lte=PersonalityQuestion.DIFFICULTY_MEDIUM).order_by('difficulty', '?')

        picks: List[PersonalityQuestion] = []
        dimensions_seen: set = set()
        for q in qs[: count * 4]:
            if q.expires_at and q.expires_at < timezone.now():
                continue
            if q.single_use and q.used_count:
                continue
            if q.dimension in dimensions_seen:
                continue
            dimensions_seen.add(q.dimension)
            picks.append(q)
            if len(picks) >= count:
                break
        return picks

    def _get_or_raise(self, user) -> PersonalityProfile:
        try:
            return PersonalityProfile.objects.get(user=user)
        except PersonalityProfile.DoesNotExist:
            raise PermissionError("No personality profile — opt in and run inference first")

    def _check_rate_limit(self, user) -> None:
        key = f"{RATE_LIMIT_CACHE_PREFIX}:{user.pk}"
        try:
            attempts = cache.get(key, 0)
        except Exception:
            attempts = 0
        if attempts >= RATE_LIMIT_MAX_ATTEMPTS:
            try:
                profile = PersonalityProfile.objects.get(user=user)
                record_event(
                    profile,
                    AuditEventType.RATE_LIMITED,
                    {'attempts': attempts},
                )
            except PersonalityProfile.DoesNotExist:
                pass
            raise RateLimited(
                f"Too many personality challenges ({attempts}) in the last "
                f"{RATE_LIMIT_WINDOW_SECONDS // 60} minutes"
            )
        try:
            cache.set(key, attempts + 1, timeout=RATE_LIMIT_WINDOW_SECONDS)
        except Exception:
            pass


def models_q_unused_or_reusable():
    from django.db.models import Q

    return Q(single_use=False) | Q(used_count=0)
