"""Generate personality-aware challenge questions."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import List, Optional

from django.utils import timezone

from ..models import (
    AuditEventType,
    PersonalityProfile,
    PersonalityQuestion,
    QuestionDimension,
)
from .audit_service import record_event
from .claude_adapter import AdapterCall, ClaudeJSONAdapter, LLMSchemaError

logger = logging.getLogger(__name__)


@dataclass
class GenerationPlan:
    dimension: str
    difficulty: int = PersonalityQuestion.DIFFICULTY_MEDIUM
    count: int = 1


def _questions_validator(data):
    if not isinstance(data, list):
        raise ValueError("expected a list of question objects")
    out = []
    for idx, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"item {idx} must be an object")
        if 'prompt' not in item or not isinstance(item['prompt'], str) or not item['prompt'].strip():
            raise ValueError(f"item {idx} missing 'prompt'")
        choices = item.get('choices', [])
        if not isinstance(choices, list):
            raise ValueError(f"item {idx} 'choices' must be a list")
        expected = item.get('expected_signature', {})
        if not isinstance(expected, dict):
            raise ValueError(f"item {idx} 'expected_signature' must be an object")
        out.append(
            {
                'prompt': item['prompt'].strip(),
                'choices': [str(c) for c in choices],
                'expected_signature': expected,
                'rationale': str(item.get('rationale', ''))[:2000],
            }
        )
    if not out:
        raise ValueError("no questions returned")
    return out


class QuestionGeneratorService:
    """Generate new question pool entries for a profile."""

    DEFAULT_POOL_SIZE = 10
    DEFAULT_TTL_HOURS = 72

    def __init__(self, adapter: Optional[ClaudeJSONAdapter] = None) -> None:
        self.adapter = adapter

    def generate(
        self,
        profile: PersonalityProfile,
        plans: Optional[List[GenerationPlan]] = None,
        *,
        ttl_hours: int = DEFAULT_TTL_HOURS,
    ) -> List[PersonalityQuestion]:
        plans = plans or self._default_plans()
        generated: List[PersonalityQuestion] = []
        expires_at = timezone.now() + timedelta(hours=ttl_hours)
        model_tag = getattr(self._svc(), 'model', '') or 'claude-json'

        for plan in plans:
            prompt = self._build_prompt(profile, plan)
            try:
                items = self._call(prompt)
            except LLMSchemaError as exc:
                logger.warning("question generation failed for %s: %s", plan.dimension, exc)
                record_event(
                    profile,
                    AuditEventType.MODEL_ERROR,
                    {'phase': 'generate_questions', 'error': str(exc), 'dimension': plan.dimension},
                )
                continue

            for item in items[: plan.count]:
                q = PersonalityQuestion.objects.create(
                    profile=profile,
                    dimension=plan.dimension,
                    difficulty=plan.difficulty,
                    prompt=item['prompt'],
                    choices=item['choices'],
                    expected_signature=item['expected_signature'],
                    rationale=item['rationale'],
                    expires_at=expires_at,
                    generator_model=model_tag,
                )
                generated.append(q)

        record_event(
            profile,
            AuditEventType.QUESTIONS_GENERATED,
            {'count': len(generated), 'dimensions': [p.dimension for p in plans]},
        )
        return generated

    # --------------------------------------------------------------

    def _default_plans(self) -> List[GenerationPlan]:
        return [
            GenerationPlan(QuestionDimension.VALUES, PersonalityQuestion.DIFFICULTY_MEDIUM, 2),
            GenerationPlan(QuestionDimension.BELIEFS, PersonalityQuestion.DIFFICULTY_MEDIUM, 2),
            GenerationPlan(QuestionDimension.STYLE, PersonalityQuestion.DIFFICULTY_EASY, 2),
            GenerationPlan(QuestionDimension.DECISIONS, PersonalityQuestion.DIFFICULTY_HARD, 1),
        ]

    def _build_prompt(self, profile: PersonalityProfile, plan: GenerationPlan) -> str:
        return (
            "Create multiple-choice questions that probe the target dimension using the "
            "provided personality features. Each question must be answerable by the user "
            "without memorization tricks, grounded in their *values*, not biographical "
            "facts. Avoid questions whose answer could be inferred from public profiles.\n\n"
            f"TARGET_DIMENSION: {plan.dimension}\n"
            f"DIFFICULTY: {plan.difficulty} (1=easy, 3=hard)\n"
            f"REQUESTED_COUNT: {plan.count}\n\n"
            f"TRAITS: {profile.trait_features}\n"
            f"THEMES: {profile.theme_weights}\n\n"
            "Respond with a JSON array of objects; each object has: prompt (string), "
            "choices (array of 3-4 strings), expected_signature (object with 'top' and "
            "optional 'avoid' list keyed on choice indexes 'a'|'b'|'c'|'d'), rationale "
            "(short string)."
        )

    def _call(self, prompt: str):
        if self.adapter is None:
            self.adapter = self._build_default_adapter()
        return self.adapter.call(AdapterCall(prompt=prompt, schema=_questions_validator))

    def _build_default_adapter(self) -> ClaudeJSONAdapter:
        from ai_assistant.services.claude_service import ClaudeService

        return ClaudeJSONAdapter(ClaudeService())

    def _svc(self):
        if self.adapter is None:
            return None
        return getattr(self.adapter, '_svc', None)
