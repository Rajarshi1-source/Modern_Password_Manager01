"""Personality inference from AI assistant conversations.

Pulls recent ``ChatMessage`` entries from the ``ai_assistant`` app, feeds them
into a Claude JSON adapter call, validates the schema, and upserts the
profile + creates a ``MoralFrameworkSnapshot``. The input surface area is
deliberately minimal — services that want to run inference on demand call
:meth:`PersonalityInferenceService.infer`.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import List, Optional

from django.utils import timezone

from ..models import (
    AuditEventType,
    MoralFrameworkSnapshot,
    PersonalityProfile,
)
from .audit_service import record_event
from .claude_adapter import AdapterCall, ClaudeJSONAdapter, LLMSchemaError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Privacy helpers
# ---------------------------------------------------------------------------

# High-signal PII patterns that should never leave the host in a prompt to an
# external LLM. The redaction is intentionally conservative — any doubtful span
# is replaced with a tag rather than letting raw text through. Personality
# inference works fine on the remaining structural content (vocabulary,
# sentence length, sentiment), so losing these spans costs nothing.
_PII_PATTERNS = (
    (re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'), '[REDACTED_EMAIL]'),
    # Phone numbers (loose international + NA formats)
    (re.compile(r'\+?\d[\d\s().-]{7,}\d'), '[REDACTED_PHONE]'),
    # Credit-card-ish 13–19 digit runs (allow separators)
    (re.compile(r'\b(?:\d[ -]?){12,18}\d\b'), '[REDACTED_CARD]'),
    # SSN-ish
    (re.compile(r'\b\d{3}-\d{2}-\d{4}\b'), '[REDACTED_SSN]'),
    # IPv4
    (re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b'), '[REDACTED_IP]'),
    # URLs (often carry tokens in query strings)
    (re.compile(r'https?://\S+', re.IGNORECASE), '[REDACTED_URL]'),
    # Explicit password / secret / token assignments
    (re.compile(
        r'(?i)\b(?:password|passwd|pwd|secret|api[_-]?key|token|bearer)\s*[:=]\s*\S+'
    ), '[REDACTED_SECRET]'),
    # Long base64/hex blobs that look like keys or tokens
    (re.compile(r'\b[A-Za-z0-9+/=_-]{32,}\b'), '[REDACTED_TOKEN]'),
)

# Hard cap on how much of each message we forward, in case a user pastes an
# entire document into chat. Personality features are saturated by the first
# few hundred characters.
_MAX_MESSAGE_CHARS = 400


def _scrub_pii(text: str) -> str:
    """Apply the PII redaction patterns and clamp the result in size."""
    if not isinstance(text, str) or not text:
        return ''
    out = text
    for pattern, replacement in _PII_PATTERNS:
        out = pattern.sub(replacement, out)
    if len(out) > _MAX_MESSAGE_CHARS:
        out = out[:_MAX_MESSAGE_CHARS] + ' [...]'
    return out


def user_opted_in(user) -> bool:
    """Return True iff the user explicitly consents to personality inference.

    The feature is gated on ``UserPreferences.privacy_analytics`` so the
    same toggle controls analytics telemetry and AI-based auth — removing
    a surprise-consent vector.
    """

    try:
        prefs = user.preferences  # type: ignore[attr-defined]
    except Exception:
        try:
            from user.models import UserPreferences

            prefs = UserPreferences.objects.get(user=user)
        except Exception:
            return False
    return bool(getattr(prefs, 'privacy_analytics', False))


# ---------------------------------------------------------------------------
# Output schema
# ---------------------------------------------------------------------------

_INFERENCE_SCHEMA = {
    'type': 'object',
    'required': ['traits', 'themes', 'moral_framework', 'confidence'],
    'properties': {
        'traits': {'type': 'object'},
        'themes': {'type': 'array'},
        'moral_framework': {'type': 'object'},
        'confidence': {'type': 'number'},
    },
}


def _inference_validator(data):
    if not isinstance(data, dict):
        raise ValueError("expected object")
    for key in ('traits', 'themes', 'moral_framework', 'confidence'):
        if key not in data:
            raise ValueError(f"missing key: {key}")
    if not isinstance(data['traits'], dict):
        raise ValueError("traits must be object")
    if not isinstance(data['moral_framework'], dict):
        raise ValueError("moral_framework must be object")
    if not isinstance(data['themes'], list):
        raise ValueError("themes must be array")
    try:
        conf = float(data['confidence'])
    except (TypeError, ValueError):
        raise ValueError("confidence must be number")
    data['confidence'] = max(0.0, min(1.0, conf))
    return data


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

@dataclass
class InferenceResult:
    profile: PersonalityProfile
    snapshot: MoralFrameworkSnapshot
    confidence: float
    sample_size: int


class PersonalityInferenceService:
    """Run personality + moral-framework inference from chat history."""

    DEFAULT_MESSAGE_LIMIT = 120

    def __init__(self, adapter: Optional[ClaudeJSONAdapter] = None) -> None:
        self.adapter = adapter

    # --------------------------------------------------------------
    def infer(
        self,
        user,
        *,
        message_limit: int = DEFAULT_MESSAGE_LIMIT,
    ) -> InferenceResult:
        if not user_opted_in(user):
            raise PermissionError("User has not opted in to personality analytics")

        profile, _ = PersonalityProfile.objects.get_or_create(
            user=user,
            defaults={'opted_in': True, 'opt_in_changed_at': timezone.now()},
        )
        if not profile.opted_in:
            profile.mark_opted_in(True)

        messages = self._collect_messages(user, message_limit)
        if not messages:
            # Nothing to learn from yet; return an empty-confidence snapshot so
            # callers can fan out without branching.
            snapshot = MoralFrameworkSnapshot.objects.create(
                profile=profile,
                coefficients={},
                value_tags=[],
                confidence=0.0,
                sample_size=0,
                inference_model=getattr(self.adapter, 'model', '') if self.adapter else '',
            )
            record_event(
                profile,
                AuditEventType.PROFILE_INFERRED,
                {'sample_size': 0, 'reason': 'no_messages'},
            )
            return InferenceResult(profile, snapshot, confidence=0.0, sample_size=0)

        prompt = self._build_prompt(messages)
        try:
            result = self._call_adapter(prompt)
        except LLMSchemaError as exc:
            logger.warning("personality inference schema error: %s", exc)
            record_event(
                profile,
                AuditEventType.MODEL_ERROR,
                {'phase': 'inference', 'error': str(exc)},
            )
            raise

        confidence = float(result.get('confidence', 0.0))
        profile.trait_features = dict(result.get('traits', {}))
        profile.theme_weights = list(result.get('themes', []))
        profile.source_messages_analysed = len(messages)
        profile.last_inferred_at = timezone.now()
        profile.inference_model = getattr(self._svc_model(), 'model', '') or 'claude-json'
        profile.save()

        snapshot = MoralFrameworkSnapshot.objects.create(
            profile=profile,
            coefficients=dict(result.get('moral_framework', {})),
            value_tags=list(result.get('value_tags', [])),
            confidence=confidence,
            sample_size=len(messages),
            inference_model=profile.inference_model,
        )
        record_event(
            profile,
            AuditEventType.PROFILE_INFERRED,
            {'sample_size': len(messages), 'confidence': confidence},
        )
        return InferenceResult(profile, snapshot, confidence=confidence, sample_size=len(messages))

    # --------------------------------------------------------------
    def _collect_messages(self, user, limit: int) -> List[str]:
        try:
            from ai_assistant.models import ChatMessage

            qs = (
                ChatMessage.objects.filter(session__user=user)
                .order_by('-created_at')
                .values_list('content', flat=True)[:limit]
            )
            return [m for m in qs if isinstance(m, str) and m]
        except Exception:
            return []

    def _build_prompt(self, messages: List[str]) -> str:
        # Scrub PII before the prompt ever leaves the process. The external
        # LLM receives redacted tokens in place of emails, phones, credit
        # cards, IPs, URLs, and high-entropy secrets. Messages are also
        # length-clamped so a single paste doesn't dominate the window.
        scrubbed = [_scrub_pii(m) for m in messages[:80]]
        scrubbed = [m for m in scrubbed if m]
        numbered = "\n".join(f"[{i+1}] {m}" for i, m in enumerate(scrubbed))
        return (
            "Analyse the following first-person messages from one user and infer their "
            "personality traits, recurring themes, and moral framework coefficients. "
            "Respond ONLY with a JSON object with the following keys:\n"
            " - traits: object mapping trait names to floats in [0,1]\n"
            " - themes: array of {label, weight} pairs\n"
            " - moral_framework: object with care/fairness/loyalty/authority/sanctity/liberty coefficients in [0,1]\n"
            " - value_tags: array of short strings\n"
            " - confidence: float in [0,1]\n\n"
            f"MESSAGES:\n{numbered}"
        )

    def _call_adapter(self, prompt: str) -> dict:
        if self.adapter is None:
            self.adapter = self._build_default_adapter()
        call = AdapterCall(prompt=prompt, schema=_inference_validator)
        result = self.adapter.call(call)
        if not isinstance(result, dict):
            raise LLMSchemaError("adapter returned non-dict payload")
        return result

    def _build_default_adapter(self) -> ClaudeJSONAdapter:
        from ai_assistant.services.claude_service import ClaudeService

        return ClaudeJSONAdapter(ClaudeService())

    def _svc_model(self):
        if self.adapter is None:
            return None
        return getattr(self.adapter, '_svc', None)
