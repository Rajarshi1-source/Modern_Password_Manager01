"""Consistency scoring for personality challenge responses.

Compares a user's answer against the :attr:`PersonalityQuestion.expected_signature`
and the :attr:`PersonalityProfile.trait_features` and returns a float in
``[0, 1]``. The scorer is deterministic and has no LLM dependency — we only
use Claude for inference and question generation, not real-time scoring,
so individual login attempts stay fast, cheap, and offline-friendly.

Scoring heuristics (additive with caps at 1.0):

* Matching the ``expected_signature.top`` choice yields +0.7.
* Matching a choice listed in ``expected_signature.also`` yields +0.4.
* Answering a choice listed in ``expected_signature.avoid`` zeros the score.
* Free-text answers receive a token-overlap score against
  ``expected_signature.keywords`` (+0.2 per keyword matched, cap +0.7).
* Latency is *informational*: responses faster than ``min_latency_ms`` or
  slower than ``max_latency_ms`` get a small confidence deduction. The
  deduction is surfaced in the rationale but never drives the score
  negative on its own because legitimate users can be slow/rushed too.

The scorer returns a :class:`ScoreResult` the orchestrator can feed back to
the ``PersonalityResponse`` row.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

from ..models import PersonalityQuestion, PersonalityResponse


_WORD_RE = re.compile(r"[a-zA-Z0-9']+")


@dataclass
class ScoreResult:
    score: float
    latency_penalty: float
    rationale: str
    hard_fail: bool = False


def _tokenize(text: str) -> List[str]:
    return [w.lower() for w in _WORD_RE.findall(text or '')]


def _choice_index(answer: str, choices: Iterable[str]) -> Optional[str]:
    """Return ``a``/``b``/``c``/``d`` for the matched choice, if any."""
    if not answer:
        return None
    answer = answer.strip().lower()
    letters = ['a', 'b', 'c', 'd', 'e', 'f']
    for i, choice in enumerate(choices):
        if i >= len(letters):
            break
        letter = letters[i]
        if answer == letter or answer == choice.strip().lower():
            return letter
    return None


class ConsistencyScorerService:
    DEFAULT_MIN_LATENCY_MS = 400
    DEFAULT_MAX_LATENCY_MS = 45_000

    def score(
        self,
        question: PersonalityQuestion,
        answer_text: str = '',
        answer_choice: str = '',
        *,
        latency_ms: Optional[int] = None,
        trait_features: Optional[Dict[str, Any]] = None,
        min_latency_ms: int = DEFAULT_MIN_LATENCY_MS,
        max_latency_ms: int = DEFAULT_MAX_LATENCY_MS,
    ) -> ScoreResult:
        signature = question.expected_signature or {}
        choices = question.choices or []
        base = 0.0
        rationale_parts: List[str] = []
        hard_fail = False

        top = str(signature.get('top', '')).strip().lower()
        also = [str(x).lower() for x in signature.get('also', [])]
        avoid = [str(x).lower() for x in signature.get('avoid', [])]
        keywords = [str(x).lower() for x in signature.get('keywords', [])]

        matched_letter = _choice_index(answer_choice or answer_text, choices)

        if matched_letter:
            if matched_letter in avoid:
                rationale_parts.append(f"answer '{matched_letter}' is in avoid list")
                hard_fail = True
            elif top and matched_letter == top:
                base += 0.7
                rationale_parts.append("matched top choice (+0.70)")
            elif matched_letter in also:
                base += 0.4
                rationale_parts.append(f"matched also choice '{matched_letter}' (+0.40)")

        if keywords and answer_text:
            tokens = set(_tokenize(answer_text))
            hits = [kw for kw in keywords if kw in tokens]
            if hits:
                bonus = min(0.7, 0.2 * len(hits))
                base += bonus
                rationale_parts.append(
                    f"keyword hits {hits!r} (+{bonus:.2f})"
                )

        if trait_features and signature.get('trait_weights'):
            # Optional: reward answers whose expected_signature lists traits that
            # correlate with the user's existing profile vector (e.g. a high
            # openness user picking the "curious" choice).
            bonus = 0.0
            weights = signature['trait_weights']
            if isinstance(weights, dict):
                for trait, expected in weights.items():
                    user_val = float(trait_features.get(trait, 0.5))
                    bonus += max(0.0, 0.1 * (1.0 - abs(float(expected) - user_val)))
            bonus = min(bonus, 0.3)
            if bonus:
                base += bonus
                rationale_parts.append(f"trait alignment (+{bonus:.2f})")

        # Latency bookkeeping.
        latency_penalty = 0.0
        if latency_ms is not None:
            if latency_ms < min_latency_ms:
                latency_penalty = 0.05
                rationale_parts.append(
                    f"suspiciously fast ({latency_ms}ms, -0.05)"
                )
            elif latency_ms > max_latency_ms:
                latency_penalty = 0.05
                rationale_parts.append(
                    f"slow response ({latency_ms}ms, -0.05)"
                )

        score = 0.0 if hard_fail else max(0.0, min(1.0, base - latency_penalty))

        return ScoreResult(
            score=score,
            latency_penalty=latency_penalty,
            rationale='; '.join(rationale_parts) or 'no criteria triggered',
            hard_fail=hard_fail,
        )

    def aggregate(self, responses: Iterable[PersonalityResponse]) -> float:
        """Weighted mean of question scores, weighted by question difficulty."""
        total = 0.0
        weight = 0.0
        for resp in responses:
            q = resp.question
            w = float(getattr(q, 'difficulty', 1) or 1)
            if resp.consistency_score is not None:
                total += resp.consistency_score * w
                weight += w
        return total / weight if weight else 0.0
