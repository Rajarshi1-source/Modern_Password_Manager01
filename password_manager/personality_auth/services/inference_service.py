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

from django.conf import settings
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


class _PresidioAdapter:
    """Lazily-initialised Microsoft Presidio backend for PII scrubbing.

    Presidio is an *optional* dependency. The adapter defers the import of
    ``presidio_analyzer`` / ``presidio_anonymizer`` (and their spaCy NLP
    backend) until the first call to ``scrub`` so:

    * Deployments without the optional packages installed are unaffected.
    * Test environments that disable the feature pay no import cost.
    * A broken model file or missing spaCy weights is detected the first
      time scrubbing is requested and reported as a single warning, after
      which the adapter falls back to regex permanently.

    The analyzer + anonymizer engines are cached on the instance, so the
    spaCy model is loaded at most once per process even though the
    adapter is consumed from a singleton (see ``_get_presidio_adapter``).
    """

    def __init__(self, language: str = 'en') -> None:
        self.language = language
        self._analyzer = None
        self._anonymizer = None
        self._initialised = False
        self._available = False

    def _ensure_initialised(self) -> None:
        if self._initialised:
            return
        self._initialised = True
        try:
            from presidio_analyzer import AnalyzerEngine
            from presidio_anonymizer import AnonymizerEngine
        except Exception as exc:
            logger.warning(
                "presidio-analyzer/anonymizer not importable (%s); "
                "personality PII scrub will use the regex backend",
                exc,
            )
            return
        try:
            self._analyzer = AnalyzerEngine()
            self._anonymizer = AnonymizerEngine()
        except Exception as exc:
            # Most commonly: the spaCy model (e.g. en_core_web_lg) is not
            # installed. We treat this as a soft failure rather than
            # propagating because the regex fallback still provides the
            # high-signal cases.
            logger.warning(
                "presidio engines failed to initialise (%s); falling back "
                "to regex-only PII scrub for personality inference",
                exc,
            )
            self._analyzer = None
            self._anonymizer = None
            return
        self._available = True
        logger.info(
            "presidio PII scrubber initialised (language=%s)",
            self.language,
        )

    @property
    def available(self) -> bool:
        self._ensure_initialised()
        return self._available

    def scrub(self, text: str) -> str:
        """Replace presidio-detected spans with ``<ENTITY_TYPE>`` tags.

        The default Presidio anonymizer replaces each detected span with
        a tag of the form ``<PERSON>``, ``<LOCATION>``, etc. We forward
        that result through the regex pass downstream so high-entropy
        tokens Presidio doesn't recognise still get caught.
        """
        if not self.available:
            return text
        try:
            results = self._analyzer.analyze(text=text, language=self.language)
        except Exception:
            logger.exception(
                "presidio analyze() failed; returning text unchanged "
                "(regex pass will still apply)",
            )
            return text
        if not results:
            return text
        try:
            anonymised = self._anonymizer.anonymize(
                text=text, analyzer_results=results,
            )
        except Exception:
            logger.exception(
                "presidio anonymize() failed; returning text unchanged",
            )
            return text
        return getattr(anonymised, 'text', text)


_presidio_adapter: Optional[_PresidioAdapter] = None


def _get_presidio_adapter() -> Optional[_PresidioAdapter]:
    """Return the process-singleton Presidio adapter, or ``None`` if the
    feature flag is disabled.

    Reading the flag at call time (rather than caching) means an
    operator can flip ``PERSONALITY_AUTH_USE_PRESIDIO`` via
    ``override_settings`` in tests or via a config reload at runtime
    without restarting the process.
    """
    global _presidio_adapter
    if not getattr(settings, 'PERSONALITY_AUTH_USE_PRESIDIO', False):
        return None
    if _presidio_adapter is None:
        language = getattr(settings, 'PERSONALITY_AUTH_PRESIDIO_LANGUAGE', 'en')
        _presidio_adapter = _PresidioAdapter(language=language)
    return _presidio_adapter


def _reset_presidio_adapter_for_tests() -> None:
    """Clear the singleton so a test that flips the feature flag or
    swaps in a fake adapter starts from a clean slate."""
    global _presidio_adapter
    _presidio_adapter = None


def _scrub_pii(text: str) -> str:
    """Redact PII from a chat message before forwarding to the LLM.

    Two backends, applied in order so the regex pass acts as a safety
    net for whatever the NLP pass misses:

    1. **Presidio** (opt-in via ``PERSONALITY_AUTH_USE_PRESIDIO``).
       Microsoft Presidio's analyzer + anonymizer driven by a spaCy
       NER model. Detects ``PERSON``, ``LOCATION``, ``DATE_TIME``,
       ``IBAN``, ``NRP``, ``US_DRIVER_LICENSE``, ``MEDICAL_LICENSE``,
       ``CRYPTO``, and several other entity classes that the regex
       pass below would never catch. Disabled by default because the
       dependency stack (``presidio-analyzer``, ``presidio-anonymizer``,
       and a spaCy model — recommended ``en_core_web_lg``, ~560 MB) is
       heavy. If presidio is enabled but the import or model load
       fails, the adapter records a one-time warning and this step is
       skipped — the regex pass below still runs.

    2. **Regex pass** (always-on). Matches the high-signal patterns in
       ``_PII_PATTERNS``: email, phone, credit-card-ish digit runs,
       SSN, IPv4, URLs, secret/token assignments, and long base64/hex
       blobs. Runs unconditionally so high-entropy values that NER
       tools tend to miss (random API keys, base64 secrets) are still
       caught.

    Finally the result is clamped to ``_MAX_MESSAGE_CHARS`` so a pasted
    document doesn't dominate the prompt window.

    **Residual limits** (acknowledged, defence-in-depth only):

    * NER misses unusual names, code-switched text, and OOV entities.
    * The regex pass only matches the patterns it knows about; free-
      text identifiers (informal addresses, niche identifiers) that
      neither backend recognises will still reach the LLM.
    * The clamp loses trailing content — a multi-paragraph paste's
      tail is dropped. This is intentional.

    Treat the resulting prompt as semi-trusted, not as fully sanitised.
    """
    if not isinstance(text, str) or not text:
        return ''

    out = text

    adapter = _get_presidio_adapter()
    if adapter is not None:
        try:
            scrubbed = adapter.scrub(out)
            if isinstance(scrubbed, str):
                out = scrubbed
        except Exception:
            # Defence-in-depth: never let the optional backend take the
            # request down. The regex pass below still runs.
            logger.exception(
                "presidio scrub raised; continuing with regex-only output",
            )

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
