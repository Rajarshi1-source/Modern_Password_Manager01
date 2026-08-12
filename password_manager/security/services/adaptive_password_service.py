"""
Adaptive Password Service (zero-knowledge)
==========================================

Learns from user typing patterns to suggest more memorable passwords WITHOUT
the server ever seeing a raw password. The server keeps only:
- aggregate learning signals (bucketized timings, error positions,
  substitution-class acceptances) under differential privacy, and
- an exported per-user preference model the client uses to rank suggestions.

All password-touching computation (fingerprinting, candidate generation,
memorability scoring, previews) happens client-side. See
docs/adaptive-password-zk-remediation-plan.md.

Privacy:
- Never receives or stores the raw password (only client-keyed fingerprints)
- Only aggregated patterns with differential privacy
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Tuple
import logging
import math
import numpy as np

from django.contrib.auth.models import User
from django.db import transaction, IntegrityError
from django.utils import timezone

from .adaptive_policy_service import (
    ACCEPTANCE_REWARD,
    ROLLBACK_REWARD,
    credit_adaptation_best_effort,
    policy_weights,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Constants and Configuration
# =============================================================================

# Common character substitutions (leetspeak mappings)
COMMON_SUBSTITUTIONS = {
    'a': ['@', '4'],
    'e': ['3'],
    'i': ['1', '!'],
    'o': ['0'],
    's': ['$', '5'],
    'l': ['1', '|'],
    't': ['7', '+'],
    'b': ['8'],
    'g': ['9'],
}

# Reverse substitutions (for detecting user preferences)
REVERSE_SUBSTITUTIONS = {
    '@': 'a', '4': 'a',
    '3': 'e',
    '1': 'i', '!': 'i',
    '0': 'o',
    '$': 's', '5': 's',
    '|': 'l',
    '7': 't', '+': 't',
    '8': 'b',
    '9': 'g',
}

# Timing buckets for anonymization
TIMING_BUCKETS = [50, 100, 150, 200, 300, 500, 750, 1000, 2000]

# =============================================================================
# Memorability model (Phase 4 — plan §4.1/§4.2, gap B4)
# =============================================================================

#: The four memorability features the CLIENT scores (it is the only side that
#: can — scoring needs the raw password). The server's job is only to learn the
#: parameters that feed that scorer and to publish them in the preference model.
MEMORABILITY_FEATURES = ('length', 'patterns', 'variety', 'pronounceable')

#: Starting weights, used until a user's own feedback has moved them. Same
#: numbers this feature has published since its first version, kept so a
#: pre-Phase-4 client sees no behaviour change.
DEFAULT_MEMORABILITY_WEIGHTS = {
    'length': 0.2,
    'patterns': 0.3,
    'variety': 0.2,
    'pronounceable': 0.3,
}

#: Fallback optimal-length band, published until the user has enough sessions
#: for their own band to mean anything.
DEFAULT_OPTIMAL_LENGTH = (12, 16)

#: Successful typing sessions required in a single length bucket before that
#: bucket may set the published band. Below this, one lucky short password
#: would redefine "optimal" for everything the client scores afterwards.
MIN_SESSIONS_FOR_LENGTH_BAND = 10

#: Length buckets are ``floor(len / 4)``, so bucket 0 covers 0-3 characters.
#: Excluded from the band search outright: a 0-3 character password is not a
#: credible preference signal, it is far more likely a truncated or abandoned
#: entry, and publishing "your optimal length is 0-3" would actively mislead
#: the client's length-fit scorer. This is a domain exclusion, not a clamp on
#: the learned value — every other bucket is used exactly as measured.
MIN_LENGTH_BUCKET = 1

#: EMA rate for the per-feature weight nudge. Small on purpose: a single
#: "yes, easier to remember" is one data point about one adaptation, and the
#: plan (§4.2) specifies an EMA precisely because the sample size does not
#: support anything heavier.
MEMORABILITY_WEIGHT_EMA_ALPHA = 0.1

#: Floor on any single learned weight. Without it a long run of one-sided
#: feedback can drive a feature's weight to (numerically) zero, after which it
#: can never be nudged back up — the nudge is multiplicative in effect once
#: renormalized, so zero is an absorbing state.
MIN_MEMORABILITY_WEIGHT = 0.02

#: Number of relative slots a session's keystroke timings are binned into for
#: ``UserTypingProfile.rhythm_signature``. Fixed so signatures from sessions of
#: different lengths can be blended element-wise at all.
RHYTHM_BINS = 8


def normalize_memorability_weights(raw) -> Dict[str, float]:
    """Coerce a stored weight blob into a complete, normalized weight dict.

    Returns the defaults unless *every* feature is present with a finite,
    non-negative number that sums to something positive. Partial blobs are
    rejected rather than back-filled: a half-learned model blended with
    defaults is a third thing neither side intended.
    """
    if not isinstance(raw, dict):
        return dict(DEFAULT_MEMORABILITY_WEIGHTS)

    values: Dict[str, float] = {}
    total = 0.0
    for name in MEMORABILITY_FEATURES:
        if name not in raw:
            return dict(DEFAULT_MEMORABILITY_WEIGHTS)
        # isinstance, not a bare float(raw[name]): the wire value must be a
        # genuine JSON number. float(None)/float('')/float(' ') already
        # raise here, but float('0.5') and float(True) both silently
        # succeed -- a numeric string or a JSON boolean would be accepted
        # as a real weight, which the client's own type check (typeof
        # value === 'number') would reject for the identical wire input.
        # bool is excluded explicitly because Python's bool is an int
        # subclass, so isinstance(True, int) is True.
        raw_value = raw[name]
        if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float)):
            return dict(DEFAULT_MEMORABILITY_WEIGHTS)
        value = float(raw_value)
        # math.isfinite, not a bare `>= 0` test: float('inf') >= 0 is True and
        # float('nan') >= 0 is False, so neither is caught by the comparison
        # alone in the way a reader expects.
        if not math.isfinite(value) or value < 0:
            return dict(DEFAULT_MEMORABILITY_WEIGHTS)
        values[name] = value
        total += value

    if total <= 0:
        return dict(DEFAULT_MEMORABILITY_WEIGHTS)
    return {name: value / total for name, value in values.items()}


def nudge_memorability_weights(adaptation, feedback) -> Optional[Dict[str, float]]:
    """Nudge one user's memorability weights from one feedback row (plan §4.2).

    **A weight tracks how well that feature PREDICTS this user's experience, not
    whether this user liked the adaptation.** That distinction is the whole rule.

    ``weights[f]`` scales feature ``f`` inside ``scoreMemorability``
    (``Σ weights[f] · features[f]``), and every feature is oriented so higher
    always means "easier to remember". So the driver's signed delta
    (``memorability_driver_delta``) is the model's *prediction* of which way
    memorability moved, and ``memorability_improved`` is what the user actually
    *observed*. Agreement means the feature explained this user; disagreement
    means it mispredicted. Hence:

    ==================  ===================  ==========================
    user says           driver delta         action
    ==================  ===================  ==========================
    yes, easier         positive             raise (predicted correctly)
    yes, easier         negative             lower (mispredicted)
    no, harder          positive             lower (mispredicted)
    no, harder          negative             raise (predicted correctly)
    ==================  ===================  ==========================

    ...applied as an EMA step toward 1.0 (agree) or 0.0 (disagree), after which
    all four are renormalized to sum to 1.

    The sign matters because ``memorability_driver`` is selected by largest
    ABSOLUTE movement, so it is frequently the feature that got *worse* --
    canonical leetspeak (``password`` → ``p@ssw0rd``) drives ``variety`` 1.00 →
    0.33. Before this rule the weight rose on any "yes", so a user telling us
    their leetspeak password was easier to remember made the model score future
    low-variety candidates *less* memorable -- backwards. It also lowered the
    weight of a feature that had correctly predicted "this got harder", punishing
    it for being right.

    Deliberately a no-op (returning ``None``) whenever the signal is not
    conclusive: ``memorability_improved`` unanswered, no driver, no recorded
    driver delta (a pre-delta client, or a row written before the field existed),
    or a delta of exactly 0.0 (the feature did not move, so it predicted
    nothing). Nudging on any of these would teach the model from the absence of
    data.

    Note the delta is NOT inferred from ``memorability_score_after -
    _before`` when absent: that aggregate mixes all four weighted features and
    can disagree in sign with the driver's own delta, which would reintroduce
    exactly the imprecision this field exists to remove.

    Runs from the weekly policy task rather than from ``export_preference_model``
    as the plan's §4.2 text implies. Learning is a write and export is a read;
    doing this on the GET would make ``/preference-model/`` mutate state on every
    poll, and would credit the same feedback row once per page refresh instead of
    exactly once (the task's ``policy_reward_applied_at`` stamp is what makes it
    once, and it already holds the row lock).

    Locked, same reasoning as ``credit_arms``: this is a genuine
    read-modify-write (read the stored weights, EMA one of them, renormalize,
    write back), so two feedback rows for the same user processed by
    overlapping task runs could both read the row before either commits, and
    the second save would silently discard the first's EMA step. Must be
    called inside a transaction (the caller's ``transaction.atomic()``); a
    bare call outside one raises, by design, the same way an un-transacted
    ``select_for_update()`` does anywhere else in this feature.

    Args:
        adaptation: The ``PasswordAdaptation`` the feedback is about.
        feedback: The ``AdaptationFeedback`` row.

    Returns:
        The new normalized weights, or ``None`` if nothing was learned.
    """
    from ..models import UserTypingProfile

    improved = feedback.memorability_improved
    if improved is None:
        return None
    driver = (adaptation.memorability_driver or '').strip()
    if driver not in MEMORABILITY_FEATURES:
        return None
    delta = adaptation.memorability_driver_delta
    # `is None` then `== 0.0`, not a single falsy test: 0.0 and None mean
    # different things here (feature did not move / client never told us), even
    # though both are no-ops, and conflating them would hide which is which from
    # anyone reading this later.
    if delta is None:
        return None
    if not math.isfinite(delta) or delta == 0.0:
        return None

    profile, _ = UserTypingProfile.objects.select_for_update().get_or_create(
        user=adaptation.user,
        defaults={
            'preferred_substitutions': {},
            'substitution_confidence': {},
            'error_prone_positions': {},
        },
    )
    weights = normalize_memorability_weights(profile.memorability_weights)
    # Did the driver feature predict what the user reported? `improved` is the
    # observed direction, `delta > 0` the predicted one.
    predicted_correctly = (delta > 0.0) == bool(improved)
    target = 1.0 if predicted_correctly else 0.0
    weights[driver] = max(
        MIN_MEMORABILITY_WEIGHT,
        weights[driver] * (1 - MEMORABILITY_WEIGHT_EMA_ALPHA)
        + target * MEMORABILITY_WEIGHT_EMA_ALPHA,
    )
    weights = normalize_memorability_weights(weights)

    profile.memorability_weights = weights
    profile.save(update_fields=['memorability_weights', 'updated_at'])
    return weights


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class TypingPattern:
    """Processed typing pattern data (privacy-safe)."""
    password_hash_prefix: str
    password_length: int
    error_positions: List[int]
    timing_buckets: Dict[int, int]  # position -> bucket
    total_time_ms: int
    success: bool
    device_type: str = 'desktop'
    input_method: str = 'keyboard'


# =============================================================================
# Privacy Guard (with pydp for formal DP guarantees)
# =============================================================================

class PrivacyGuard:
    """
    Privacy protection for typing data using Google's pydp library.
    
    Implements:
    - Differential privacy for pattern aggregation (using pydp)
    - Privacy budget tracking
    - Data anonymization
    - Secure deletion
    
    Uses pydp (Google's differential privacy library) for formal DP guarantees.
    """
    
    def __init__(self, epsilon: float = 0.5, delta: float = 1e-5):
        """
        Initialize with differential privacy parameters.
        
        Args:
            epsilon: DP epsilon (0.1=strong, 1.0=weak, 0.5=balanced)
            delta: Probability of privacy breach (default: 1e-5)
        """
        self.epsilon = epsilon
        self.delta = delta
        self.operations_count = 0  # Track for privacy budget
        
        # Try to import pydp, fall back to numpy if not available
        try:
            from pydp.algorithms.laplacian import BoundedMean, BoundedSum
            self.pydp_available = True
            self.BoundedMean = BoundedMean
            self.BoundedSum = BoundedSum
            logger.info("Using pydp library for formal DP guarantees")
        except ImportError:
            self.pydp_available = False
            logger.warning("pydp not available, using numpy fallback for DP")
    
    def anonymize_timing(self, timing_ms: int) -> int:
        """Convert exact timing to privacy-safe bucket."""
        for bucket in TIMING_BUCKETS:
            if timing_ms <= bucket:
                return bucket
        return TIMING_BUCKETS[-1]
    
    def add_noise_to_timings(
        self,
        timings: List[float],
        lower_bound: float = 0.0,
        upper_bound: float = 1000.0
    ) -> float:
        """
        Add Laplacian noise to timing measurements using pydp.
        
        Args:
            timings: List of inter-keystroke timings (ms)
            lower_bound: Min valid timing
            upper_bound: Max valid timing
        
        Returns:
            DP-protected average timing
        """
        if not timings:
            return 0.0
        
        self.operations_count += 1
        
        if self.pydp_available:
            # Use pydp BoundedMean for formal DP guarantees
            dp_mean = self.BoundedMean(
                epsilon=self.epsilon,
                lower_bound=lower_bound,
                upper_bound=upper_bound
            )
            noisy_mean = dp_mean.quick_result(timings)
            logger.debug(f"pydp: Applied DP noise to {len(timings)} samples -> {noisy_mean}ms")
            return float(max(lower_bound, min(upper_bound, noisy_mean)))
        else:
            # Fallback to numpy Laplace mechanism with rejection sampling to
            # stay strictly inside (lower_bound, upper_bound) since timings are
            # physically non-negative and bounded.
            clipped = [max(lower_bound, min(upper_bound, t)) for t in timings]
            mean_timing = sum(clipped) / len(clipped)
            sensitivity = (upper_bound - lower_bound) / len(clipped)
            scale = sensitivity / self.epsilon
            for _ in range(20):
                noisy = mean_timing + float(np.random.laplace(0, scale))
                if lower_bound < noisy < upper_bound:
                    return float(noisy)
            # Give up: clamp strictly inside the interval.
            margin = max((upper_bound - lower_bound) * 1e-6, 1e-9)
            return float(max(lower_bound + margin, min(upper_bound - margin, mean_timing)))
    
    def add_noise_to_error_histogram(
        self,
        error_positions: List[int],
        max_position: int = 50
    ) -> Dict[int, int]:
        """
        Create DP-protected histogram of error positions.
        
        Args:
            error_positions: List of error indices
            max_position: Maximum password length
        
        Returns:
            DP-protected histogram {position: count}
        """
        self.operations_count += 1
        
        # Create histogram
        histogram = {i: 0 for i in range(max_position)}
        for pos in error_positions:
            if 0 <= pos < max_position:
                histogram[pos] += 1
        
        # Add Laplacian noise to each bin
        dp_histogram = {}
        for pos, count in histogram.items():
            # Laplace noise with scale = sensitivity / epsilon
            noise = np.random.laplace(0, 1.0 / self.epsilon)
            noisy_count = max(0, count + noise)  # Ensure non-negative
            dp_histogram[pos] = int(round(noisy_count))
        
        return dp_histogram
    
    def add_noise_to_substitutions(
        self,
        substitutions: Dict[str, str]
    ) -> Dict[str, str]:
        """
        Add noise to substitution mappings.
        Randomly adds/removes substitutions based on epsilon.
        
        Args:
            substitutions: Character substitution mappings
        
        Returns:
            DP-protected substitution dict
        """
        self.operations_count += 1
        dp_substitutions = substitutions.copy()
        
        # With probability based on epsilon, add/remove random substitutions
        noise_probability = min(0.1, 1.0 / self.epsilon)
        
        for char in 'oaeilstz':  # Common substitution characters
            if np.random.random() < noise_probability:
                # Add random substitution
                dp_substitutions[char] = np.random.choice(['0', '@', '!', '1', '$', '7', '2'])
        
        return dp_substitutions
    
    def verify_privacy_budget(self, additional_operations: int = 0) -> bool:
        """
        Verify if privacy budget is exhausted.
        
        Uses the composition theorem to calculate total epsilon.
        
        Args:
            additional_operations: Number of additional DP operations planned
        
        Returns:
            True if budget allows more operations
        """
        total_operations = self.operations_count + additional_operations
        
        if total_operations == 0:
            return True
        
        # Advanced composition theorem: ε_total ≈ sqrt(2 * k * ln(1/δ)) * ε + k * ε * (e^ε - 1)
        # Simplified: ε_total ≈ sqrt(2 * k * ln(1/δ)) * ε for small ε
        total_epsilon = np.sqrt(2 * total_operations * np.log(1 / self.delta)) * self.epsilon
        
        # Warn if approaching budget limit (ε > 1.0 is often considered high)
        if total_epsilon > 1.0:
            logger.warning(f"Privacy budget approaching limit: ε_total = {total_epsilon:.2f}")
            return False
        
        if total_epsilon > 0.8:
            logger.info(f"Privacy budget status: ε_total = {total_epsilon:.2f} ({self.operations_count} operations)")
        
        return True
    
    def get_privacy_budget_status(self) -> Dict[str, Any]:
        """
        Get current privacy budget status.
        
        Returns:
            Dict with epsilon, delta, operations, and remaining budget
        """
        total_epsilon = np.sqrt(2 * max(1, self.operations_count) * np.log(1 / self.delta)) * self.epsilon
        max_operations = int((1.0 / self.epsilon) ** 2 / (2 * np.log(1 / self.delta)))
        
        return {
            'epsilon': self.epsilon,
            'delta': self.delta,
            'operations_count': self.operations_count,
            'total_epsilon_used': round(total_epsilon, 4),
            'max_recommended_operations': max_operations,
            'budget_remaining_pct': max(0, round((1 - total_epsilon) * 100, 1)),
            'using_pydp': self.pydp_available,
        }
    
    def add_laplace_noise(self, value: float, sensitivity: float = 1.0) -> float:
        """Add Laplacian noise for differential privacy (legacy method)."""
        self.operations_count += 1
        scale = sensitivity / self.epsilon
        noise = np.random.laplace(0, scale)
        return value + noise
    
    def sanitize_pattern(self, pattern: TypingPattern) -> TypingPattern:
        """Apply DP noise to pattern data."""
        # Use pydp for timing if available
        if self.pydp_available and pattern.timing_buckets:
            timing_values = list(pattern.timing_buckets.values())
            noisy_avg = self.add_noise_to_timings(timing_values)
            # Distribute noise proportionally
            noise_factor = noisy_avg / (sum(timing_values) / len(timing_values)) if timing_values else 1
            noisy_timings = {
                pos: self.anonymize_timing(int(bucket * noise_factor))
                for pos, bucket in pattern.timing_buckets.items()
            }
        else:
            # Fallback: Add noise to timing buckets individually
            noisy_timings = {}
            for pos, bucket in pattern.timing_buckets.items():
                noise = int(self.add_laplace_noise(0, sensitivity=50))
                noisy_timings[pos] = self.anonymize_timing(bucket + noise)
        
        return TypingPattern(
            password_hash_prefix=pattern.password_hash_prefix,
            password_length=pattern.password_length,
            error_positions=pattern.error_positions,
            timing_buckets=noisy_timings,
            total_time_ms=int(self.add_laplace_noise(
                pattern.total_time_ms, sensitivity=100
            )),
            success=pattern.success,
            device_type=pattern.device_type,
            input_method=pattern.input_method,
        )


# =============================================================================
# Main Adaptive Password Service
# =============================================================================

class AdaptivePasswordService:
    """
    Main service for adaptive password management.
    
    Orchestrates:
    - Typing pattern collection
    - Substitution learning
    - Memorability scoring
    - Adaptation suggestions
    """
    
    def __init__(self, user: User):
        self.user = user
        self.privacy_guard = PrivacyGuard()
    
    def record_typing_session_v2(
        self,
        password_fingerprint: str,
        length_bucket: int,
        keystroke_timings: List[int],
        backspace_positions: List[int] = None,
        device_type: str = 'desktop',
        input_method: str = 'keyboard',
        substitution_classes_used: Optional[List[Dict]] = None,
        success: Optional[bool] = None,
        expected_fp_key_version: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Record a typing session under the zero-knowledge v2 contract.

        The client supplies a *keyed fingerprint* (opaque to the server) and a
        coarse length bucket — never the raw password. The aggregate learning
        signals (errors, timing, WPM) are updated exactly as in the legacy
        path; only the password-derived ingestion is gone.

        Args:
            password_fingerprint: Client-keyed HMAC fingerprint (base64url).
            length_bucket: Coarse length bucket = floor(len / 4).
            keystroke_timings: Inter-key delays in ms.
            backspace_positions: Positions where backspaces occurred.
            device_type: desktop, mobile, tablet.
            input_method: keyboard, touchscreen, voice.
            substitution_classes_used: Optional consented substitution-class
                usage, e.g. ``[{"from": "o", "to": "0"}]`` (no positions/chars
                of the password).
            success: Explicit session outcome from the caller (whether the
                password was ultimately entered correctly). When omitted, falls
                back to the heuristic "no backspaces" — note a corrected typo is
                not a failed attempt, so callers should pass this explicitly.
            expected_fp_key_version: The era the caller's serializer already
                validated the client's ``fp_key_version`` against (see
                ``FingerprintKeyVersionMixin``). Re-checked against a fresh
                config read below to close the gap between that validation and
                this write — see the comment at the check itself.

        Returns:
            Session summary (carries ``schema_version: 2``).
        """
        from ..models import TypingSession, AdaptivePasswordConfig

        backspace_positions = list(backspace_positions or [])

        # Opt-in / consent gate.
        try:
            config = AdaptivePasswordConfig.objects.get(user=self.user)
            if not config.is_enabled:
                return {'error': 'Adaptive passwords not enabled'}
        except AdaptivePasswordConfig.DoesNotExist:
            return {'error': 'Adaptive passwords not configured'}

        # Close the TOCTOU window between the view's era validation and this
        # write. The serializer already compared the client's fp_key_version
        # against a config read taken *before* this one; without this check,
        # a rotation that commits in between would make this fresh read see
        # the NEW era, and the row below would be stamped with it — even
        # though the fingerprint was actually derived under the OLD salt.
        # Reject and let the client re-fetch /adaptive/config/ and retry,
        # rather than silently writing a row no era can ever reproduce.
        if (
            expected_fp_key_version is not None
            and config.fp_key_version != expected_fp_key_version
        ):
            return {
                'error': 'Fingerprint key era changed mid-request; re-fetch and retry.',
                'code': 'fp_key_era_changed',
            }

        # Prefer the caller's explicit outcome; backspaces are only error
        # *metadata*, not a reliable success signal (a corrected typo still
        # succeeds), so they are used solely as a last-resort fallback.
        session_success = (len(backspace_positions) == 0) if success is None else bool(success)
        timing_buckets = {
            i: self.privacy_guard.anonymize_timing(t)
            for i, t in enumerate(keystroke_timings)
        }

        # Build a privacy-safe pattern for profile aggregation. We never had the
        # password, so exact length is unknown — approximate it from the bucket
        # purely for the WPM heuristic (the stored column keeps only the bucket).
        approx_length = max(0, int(length_bucket) * 4)
        pattern = TypingPattern(
            password_hash_prefix='',  # ZK v2: no server-side password hash
            password_length=approx_length,
            error_positions=backspace_positions,
            timing_buckets=timing_buckets,
            total_time_ms=sum(keystroke_timings) if keystroke_timings else 0,
            success=session_success,
            device_type=device_type,
            input_method=input_method,
        )
        pattern = self.privacy_guard.sanitize_pattern(pattern)

        session = TypingSession.objects.create(
            user=self.user,
            password_fingerprint=password_fingerprint,
            length_bucket=length_bucket,
            # Stamped from the server's own config, never from the request body.
            # The client's fp_key_version is only ever *compared* (serializer
            # 409), so a client cannot backdate a row into a dead era.
            fp_key_version=config.fp_key_version,
            success=session_success,
            error_positions=pattern.error_positions,
            error_count=len(pattern.error_positions),
            timing_profile=pattern.timing_buckets,
            total_time_ms=pattern.total_time_ms,
            device_type=device_type,
            input_method=input_method,
        )

        # Update aggregate profile, then fold in any consented substitution-class
        # usage the client reported (used to learn per-class preferences).
        self._update_typing_profile(pattern)
        if substitution_classes_used:
            self._record_substitution_classes(substitution_classes_used)

        return {
            'schema_version': 2,
            'session_id': str(session.id),
            'success': session_success,
            'error_count': len(pattern.error_positions),
        }

    def _record_substitution_classes(self, classes: List[Dict]):
        """Fold consented substitution-class usage into the aggregate profile.

        Stores only ``from->to`` *classes* (e.g. the user tends to map o→0),
        never anything tied to the password's contents or positions.
        """
        from ..models import UserTypingProfile

        profile, _ = UserTypingProfile.objects.get_or_create(
            user=self.user,
            defaults={
                'preferred_substitutions': {},
                'substitution_confidence': {},
                'error_prone_positions': {},
            },
        )
        changed = False
        for entry in classes:
            from_char = entry.get('from')
            to_char = entry.get('to')
            if not from_char or not to_char:
                continue
            key = f"{from_char}->{to_char}"
            current = profile.substitution_confidence.get(key, 0.0)
            # Exponential moving average toward 1.0 (capped).
            profile.substitution_confidence[key] = min(1.0, current * 0.8 + 0.2)
            profile.preferred_substitutions[from_char] = to_char
            changed = True
        if changed:
            profile.save()

    def _update_typing_profile(self, pattern: TypingPattern):
        """Update user's aggregated typing profile."""
        from ..models import UserTypingProfile
        
        profile, created = UserTypingProfile.objects.get_or_create(
            user=self.user,
            defaults={
                'preferred_substitutions': {},
                'substitution_confidence': {},
                'error_prone_positions': {},
            }
        )
        
        # Update session counts
        profile.total_sessions += 1
        if pattern.success:
            profile.successful_sessions += 1
        profile.success_rate = profile.successful_sessions / profile.total_sessions
        
        # Update error-prone positions
        for pos in pattern.error_positions:
            pos_str = str(pos)
            current = profile.error_prone_positions.get(pos_str, 0)
            # Exponential moving average
            profile.error_prone_positions[pos_str] = current * 0.9 + 0.1
        
        # Decay non-error positions
        for pos_str in list(profile.error_prone_positions.keys()):
            if int(pos_str) not in pattern.error_positions:
                profile.error_prone_positions[pos_str] *= 0.95
        
        # Classify what KIND of errors this user makes (plan §4.4, gap B6).
        profile.common_error_types = self._blend_error_types(
            profile.common_error_types, pattern.error_positions
        )

        # Rhythm signature (plan §4.4, gap B6): a fixed-length, scale-free
        # summary of this session's timing shape, EMA'd into the profile.
        session_rhythm = self._rhythm_vector(pattern.timing_buckets)
        if session_rhythm is not None:
            profile.rhythm_signature = self._blend_rhythm(
                profile.rhythm_signature, session_rhythm
            )

        # Update WPM
        if pattern.total_time_ms > 0:
            # Approximate WPM from password length and time
            chars_per_min = (pattern.password_length / pattern.total_time_ms) * 60000
            wpm = chars_per_min / 5  # Standard: 5 chars = 1 word

            if profile.average_wpm is None:
                profile.average_wpm = wpm
                # First observation: no deviation to measure yet. 0.0, not
                # None, so the field stops reading as "never written".
                profile.wpm_variance = 0.0
            else:
                # Exponentially-weighted variance (plan §4.4, gap B6).
                #
                # The plan says "Welford, online", but Welford maintains the
                # ARITHMETIC mean and its M2 companion, and this profile stores
                # an EWMA (`average_wpm * 0.9 + wpm * 0.1`) with no M2 column.
                # Pairing Welford's M2 with an EWMA mean would produce a number
                # that is not the variance of anything. The EWMA's own variance
                # companion (West/Finch) is the consistent choice and needs no
                # new field:
                #     diff = x - mean_prev
                #     mean = mean_prev + alpha * diff
                #     var  = (1 - alpha) * (var_prev + alpha * diff^2)
                # with the same alpha = 0.1 the mean already uses.
                alpha = 0.1
                diff = wpm - profile.average_wpm
                previous_variance = profile.wpm_variance or 0.0
                profile.average_wpm = profile.average_wpm + alpha * diff
                profile.wpm_variance = (1 - alpha) * (
                    previous_variance + alpha * diff * diff
                )

        # Update profile confidence
        profile.profile_confidence = min(1.0, profile.total_sessions / 50)
        profile.last_session_at = timezone.now()

        # update_fields, not a bare save(): this is the request-path writer
        # (record_typing_session_v2 -> here) for the columns above only, and
        # runs on every typing session -- the highest-frequency of the three
        # call sites that read/write this row. memorability_weights is owned
        # by nudge_memorability_weights (the weekly feedback task); an
        # unscoped save() here would read-then-write-back whatever stale
        # value this instance happened to load, silently reverting a nudge
        # that committed in the gap between this method's read and its save.
        # Same class of bug already fixed for aggregate_typing_profiles and
        # nudge_memorability_weights itself -- this was the third, and the
        # one on the hottest path.
        profile.save(update_fields=[
            'total_sessions', 'successful_sessions', 'success_rate',
            'error_prone_positions', 'common_error_types', 'rhythm_signature',
            'average_wpm', 'wpm_variance', 'profile_confidence',
            'last_session_at', 'updated_at',
        ])
    
    @staticmethod
    def _blend_error_types(current: Optional[Dict], error_positions: List[int]) -> Dict:
        """Fold this session's error shape into the aggregate distribution.

        Classified from ``backspace_positions`` adjacency alone, because that is
        genuinely all the server has: the client sends WHERE a correction
        happened, never WHICH key was pressed. The labels are therefore
        positional proxies and are documented as such rather than presented as
        keystroke forensics:

        - ``transposition`` — two corrections at adjacent positions, the
          signature of backing over a swapped pair.
        - ``repeated`` — the same position corrected more than once in one
          session, i.e. a character the user genuinely struggles with.
        - ``adjacent_key`` — an isolated single correction; the residual class,
          and the most common cause of one is hitting a neighbouring key.

        A true adjacent-key slip and any other one-character mistake are
        indistinguishable from positions alone, so ``adjacent_key`` should be
        read as "isolated single-character error", not as a proven cause.

        Returns the EMA-blended distribution, always summing to 1 when any error
        was observed. A clean session leaves the distribution untouched: zero
        errors is not evidence about which error *type* dominates.
        """
        counts = {'adjacent_key': 0, 'transposition': 0, 'repeated': 0}
        if error_positions:
            seen = set()
            duplicates = set()
            for position in error_positions:
                if position in seen:
                    duplicates.add(position)
                seen.add(position)
            for position in sorted(seen):
                if position in duplicates:
                    counts['repeated'] += 1
                elif (position - 1) in seen or (position + 1) in seen:
                    counts['transposition'] += 1
                else:
                    counts['adjacent_key'] += 1

        total = sum(counts.values())
        blended = dict(current or {})
        if total == 0:
            return blended

        alpha = 0.2
        for label, count in counts.items():
            try:
                previous = float(blended.get(label, 0.0))
            except (TypeError, ValueError):
                previous = 0.0
            if not math.isfinite(previous) or previous < 0:
                previous = 0.0
            blended[label] = previous * (1 - alpha) + (count / total) * alpha

        # Renormalize so the stored value is always a distribution. Without
        # this, a profile carrying stale keys from an older schema would leave
        # the sum drifting away from 1 forever.
        scale = sum(v for v in blended.values() if isinstance(v, (int, float)))
        if scale > 0:
            blended = {
                k: (v / scale) for k, v in blended.items()
                if isinstance(v, (int, float))
            }
        return blended

    @staticmethod
    def _rhythm_vector(timing_buckets: Dict[int, int]) -> Optional[List[float]]:
        """Summarize a session's timings as a fixed-length, scale-free vector.

        Keystroke counts differ per session, so the raw timing list cannot be
        blended element-wise across sessions. Positions are binned into
        ``RHYTHM_BINS`` relative slots (first eighth of the password, second
        eighth, …) and each bin's mean timing divided by the session mean, which
        removes overall typing speed and leaves only the *shape* — where this
        user speeds up and slows down within a password.

        Adds no information the server does not already hold: it is a lossy
        summary of ``TypingSession.timing_profile``, which is stored per session
        in full (already bucketized and DP-noised upstream).

        Returns ``None`` for a session with no usable timings.
        """
        if not timing_buckets:
            return None
        # Sort numerically, not lexicographically: the only current caller
        # builds this dict with int keys (enumerate()), but TypingSession.
        # timing_profile is a JSONField, and JSON always stringifies object
        # keys -- '10' would sort before '2' for a caller that ever passes a
        # stored profile back in, silently scrambling the rhythm shape.
        ordered = [
            timing_buckets[k]
            for k in sorted(timing_buckets, key=lambda position: int(position))
        ]
        values = [float(v) for v in ordered if isinstance(v, (int, float)) and v > 0]
        if not values:
            return None
        mean = sum(values) / len(values)
        if mean <= 0:
            return None

        bins = [[] for _ in range(RHYTHM_BINS)]
        for index, value in enumerate(values):
            slot = min(RHYTHM_BINS - 1, (index * RHYTHM_BINS) // len(values))
            bins[slot].append(value)
        # An empty bin (fewer keystrokes than bins) reads as 1.0 — "average
        # speed", the neutral value — rather than 0.0, which would be
        # indistinguishable from "typed instantly here".
        return [
            round((sum(b) / len(b)) / mean, 4) if b else 1.0
            for b in bins
        ]

    @staticmethod
    def _blend_rhythm(current, session_rhythm: List[float]) -> List[float]:
        """EMA this session's rhythm vector into the stored signature."""
        alpha = 0.2
        if not isinstance(current, list) or len(current) != RHYTHM_BINS:
            # First write, or a signature from a different RHYTHM_BINS. Adopt
            # the session outright instead of blending against a vector whose
            # bins mean something else.
            return list(session_rhythm)
        blended = []
        # strict=True: the guard above already proves both sequences have
        # exactly RHYTHM_BINS elements; stating that invariant here means a
        # future edit that breaks it fails loudly instead of silently
        # truncating.
        for previous, value in zip(current, session_rhythm, strict=True):
            try:
                previous_value = float(previous)
            except (TypeError, ValueError):
                previous_value = value
            if not math.isfinite(previous_value):
                previous_value = value
            blended.append(round(previous_value * (1 - alpha) + value * alpha, 4))
        return blended

    def export_preference_model(self) -> Dict[str, Any]:
        """Export the per-user preference model for client-side suggestion ranking.

        This is the zero-knowledge replacement for the server-side ``/suggest/``
        path: the client downloads this model and ranks locally-generated
        candidates against it (remediation plan §4). It contains only aggregate,
        non-reversible signals — substitution-class weights + memorability
        params — and never any password-derived data.

        Returns:
            ``{model_version, fp_key_version, substitution_weights,
            exploration, weight_sources, memorability_params,
            error_prone_positions}``.

        Phase 4: ``memorability_params`` is no longer a hard-coded literal with
        no consumer. ``optimal_length_min/max`` come from this user's own
        successful-session length distribution and ``weights`` from whatever
        their ``memorability_improved`` feedback has nudged them to; the client
        finally reads both in ``scoreMemorability``. ``error_prone_positions``
        is published so ``rankSuggestions`` can boost substitutions where the
        user actually stumbles — the position → character join happens on the
        client, because the server has no password to join against.

        Phase 3: ``substitution_weights`` is no longer the static leetspeak
        table. Each class resolves to the posterior mean of the user's own
        ``SubstitutionPolicyArm``, falling back to the profile's usage-based
        confidence, then the DP-noised cross-user prior, then the baseline
        (see ``adaptive_policy_service.policy_weights`` for why the population
        signal ranks below both user-specific ones).

        ``exploration`` carries the raw ``{alpha, beta}`` per class so the
        client draws the Thompson sample itself. Exploration therefore stays
        on-device and this endpoint stays deterministic and cacheable — the
        server would otherwise have to return a different, unrepeatable answer
        on every call.

        Note: the profile itself is deliberately NOT era-scoped. It holds
        behavioural aggregates (WPM, error-prone positions, substitution-class
        preferences) that describe the *user*, not any particular password, so
        they stay valid across a fingerprint key rotation. Only the
        fingerprint-keyed tables (TypingSession, PasswordAdaptation) — and, as
        of Phase 3, the policy arms, whose behavioural reward is computed by
        joining two fingerprints inside one era — are scoped.
        """
        from ..models import AdaptivePasswordConfig, UserTypingProfile

        # Baseline weights from the shared leetspeak map (primary > secondary).
        baseline: Dict[str, Dict[str, float]] = {}
        for char, subs in COMMON_SUBSTITUTIONS.items():
            baseline[char] = {
                sub: (0.6 if idx == 0 else 0.4) for idx, sub in enumerate(subs)
            }

        model_version = 0
        # Usage-based, user-specific overrides from the aggregate profile: which
        # classes this user already reaches for. Distinct from a policy arm,
        # which records which classes actually *worked* when adapted.
        profile_overrides: Dict[str, Dict[str, float]] = {}
        try:
            profile = UserTypingProfile.objects.get(user=self.user)
        except UserTypingProfile.DoesNotExist:
            profile = None

        if profile is not None:
            # Monotonic-ish version so the client can cache/invalidate.
            model_version = profile.total_sessions

            for key, confidence in (profile.substitution_confidence or {}).items():
                if '->' not in key:
                    continue
                from_char, to_char = key.split('->', 1)
                if not from_char or not to_char:
                    continue
                try:
                    conf = float(confidence)
                except (TypeError, ValueError):
                    continue
                profile_overrides.setdefault(from_char, {})[to_char] = max(
                    0.0, min(1.0, conf)
                )

            # Explicit preferences get a strong confidence so the client ranks
            # them first.
            for from_char, to_char in (profile.preferred_substitutions or {}).items():
                if not isinstance(from_char, str) or not isinstance(to_char, str):
                    continue
                row = profile_overrides.setdefault(from_char, {})
                row[to_char] = max(row.get(to_char, 0.0), 0.9)

        optimal_min, optimal_max = self._learn_optimal_length_band()
        memorability_params = {
            'optimal_length_min': optimal_min,
            'optimal_length_max': optimal_max,
            'weights': normalize_memorability_weights(
                profile.memorability_weights if profile is not None else None
            ),
        }

        # Phase 4 (plan §4.3, gap B3): the "learns from your typing errors"
        # claim. These positions have been written and decayed since the
        # feature's first version and read by NOTHING; the join that makes them
        # useful (position -> which character sits there) can only happen on the
        # client. Keys are stringified positions, so they are normalized to a
        # {str: float} map here rather than trusted as stored.
        error_prone_positions: Dict[str, float] = {}
        if profile is not None:
            for position, rate in (profile.error_prone_positions or {}).items():
                try:
                    index = int(position)
                    value = float(rate)
                except (TypeError, ValueError):
                    continue
                if index < 0 or not math.isfinite(value):
                    continue
                error_prone_positions[str(index)] = max(0.0, min(1.0, value))

        fp_key_version = AdaptivePasswordConfig.objects.filter(
            user=self.user
        ).values_list('fp_key_version', flat=True).first() or 1

        substitution_weights, exploration, weight_sources = policy_weights(
            self.user,
            fp_key_version=fp_key_version,
            baseline=baseline,
            user_overrides=profile_overrides,
        )

        return {
            'model_version': model_version,
            'fp_key_version': fp_key_version,
            'substitution_weights': substitution_weights,
            'exploration': exploration,
            'weight_sources': weight_sources,
            'memorability_params': memorability_params,
            'error_prone_positions': error_prone_positions,
        }

    def _learn_optimal_length_band(self) -> Tuple[int, int]:
        """Derive this user's optimal password-length band (plan §4.2).

        The user's own ``length_bucket`` distribution weighted by per-bucket
        success rate: ``count_b * (successes_b / count_b)`` is just
        ``successes_b``, so the winning bucket is simply the one where this user
        has typed correctly most often. A bucket is ``floor(len / 4)``, so
        bucket *b* publishes the band ``[4b, 4b + 3]``.

        Deliberately NOT era-scoped, unlike ``get_evolution_stats`` and
        ``get_adaptation_history``. Those two read ``TypingSession`` for its
        *fingerprint*, which is exactly what a key rotation invalidates. This
        reads only ``length_bucket`` and ``success`` — behavioural columns that
        carry no fingerprint and so create no cross-era correlation — and it
        describes the user's typing, not any particular password. That puts it
        in the same category as ``UserTypingProfile`` itself, which
        ``export_preference_model``'s own docstring already documents as
        deliberately un-scoped.

        Returns:
            ``(optimal_length_min, optimal_length_max)``; the defaults when no
            bucket has enough successful sessions to speak for itself.
        """
        from django.db.models import Count, Q

        from ..models import TypingSession

        rows = (
            TypingSession.objects
            .filter(user=self.user, length_bucket__gte=MIN_LENGTH_BUCKET)
            .values('length_bucket')
            .annotate(successes=Count('id', filter=Q(success=True)))
            .order_by('length_bucket')
        )

        best_bucket = None
        best_successes = 0
        for row in rows:
            successes = row['successes']
            # Strict >: `rows` is ordered by bucket ascending, so a tie keeps
            # the SHORTER band rather than resolving on database row order.
            if successes >= MIN_SESSIONS_FOR_LENGTH_BAND and successes > best_successes:
                best_bucket = row['length_bucket']
                best_successes = successes

        if best_bucket is None:
            return DEFAULT_OPTIMAL_LENGTH
        return (best_bucket * 4, best_bucket * 4 + 3)

    def apply_adaptation_v2(
        self,
        original_fingerprint: str,
        adapted_fingerprint: str,
        substitution_classes: List[Dict],
        previews: Optional[Dict[str, str]] = None,
        memorability_improvement: Optional[float] = None,
        memorability_score_before: Optional[float] = None,
        memorability_score_after: Optional[float] = None,
        memorability_driver: Optional[str] = None,
        memorability_driver_delta: Optional[float] = None,
        expected_fp_key_version: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Apply/record an adaptation under the zero-knowledge v2 contract.

        Stores only fingerprints, masked previews, and substitution *classes* —
        never raw passwords. The rollback chain is keyed by fingerprint.

        Args:
            original_fingerprint: Fingerprint of the original password.
            adapted_fingerprint: Fingerprint of the adapted password.
            substitution_classes: ``[{"from": "o", "to": "0", "confidence"?: …}]``.
            previews: Optional ``{original_masked, adapted_masked}`` (client-masked).
            memorability_improvement: Optional client-computed Δ (informational).
            memorability_score_before: Optional client-measured memorability of
                the original password, in ``[0, 1]`` (plan §4.1). Before Phase 4
                both score columns were hard-``None``, which is why
                ``get_evolution_stats``' ``average_memorability_improvement``
                was permanently 0.
            memorability_score_after: Same, for the adapted password.
            memorability_driver: Which of the four memorability features moved
                most, per the client. Only used later, to attribute a user's
                ``memorability_improved`` feedback to a feature weight.
            memorability_driver_delta: That feature's own SIGNED before→after
                change, in ``[-1, 1]``. Stored only alongside a driver — a delta
                with no feature to attribute it to teaches nothing. Read by
                ``nudge_memorability_weights`` to tell whether the driver
                predicted the user's answer or mispredicted it.
            expected_fp_key_version: The era the caller's serializer already
                validated the client's ``fp_key_version`` against. See
                ``record_typing_session_v2`` for why this is re-checked here
                rather than trusted from the earlier validation alone.

        Returns:
            Adaptation record summary (carries ``schema_version: 2``).
        """
        from ..models import PasswordAdaptation, AdaptivePasswordConfig

        # Opt-in / consent gate (same as record_typing_session_v2): never persist
        # adaptation records for users who haven't enabled the feature.
        try:
            config = AdaptivePasswordConfig.objects.get(user=self.user)
            if not config.is_enabled:
                return {'error': 'Adaptive passwords not enabled'}
        except AdaptivePasswordConfig.DoesNotExist:
            return {'error': 'Adaptive passwords not configured'}

        # Same TOCTOU close as record_typing_session_v2: reject rather than
        # silently stamp this adaptation under an era that committed after the
        # view's validation, which the fingerprints were never derived under.
        if (
            expected_fp_key_version is not None
            and config.fp_key_version != expected_fp_key_version
        ):
            return {
                'error': 'Fingerprint key era changed mid-request; re-fetch and retry.',
                'code': 'fp_key_era_changed',
            }

        previews = previews or {}
        substitution_classes = list(substitution_classes or [])

        confidences = [
            float(c['confidence'])
            for c in substitution_classes
            if isinstance(c.get('confidence'), (int, float))
        ]
        confidence_score = (sum(confidences) / len(confidences)) if confidences else 0.8

        substitutions_applied = {
            str(i): {'from': c.get('from'), 'to': c.get('to')}
            for i, c in enumerate(substitution_classes)
        }

        # Atomic + row-locked chain mutation. The parent lookup, the new active
        # row, and the parent's rollback are committed together, so a retried or
        # concurrent /apply/ cannot fork the rollback chain. The
        # ``uniq_active_adapted_fp_per_user`` partial-unique constraint is the
        # DB-level backstop (at most one active row per adapted_fingerprint).
        try:
            with transaction.atomic():
                # Chain by fingerprint: the previous *active* adaptation whose
                # adapted fingerprint equals this original is the parent.
                # Era-scoped: a pre-rotation row can never become the parent of a
                # post-rotation adaptation. Its fingerprints were derived under a
                # different key, so treating it as the chain head would link two
                # unrelated passwords.
                previous = (
                    PasswordAdaptation.objects.select_for_update()
                    .filter(
                        user=self.user,
                        fp_key_version=config.fp_key_version,
                        adapted_fingerprint=original_fingerprint,
                        status='active',
                    )
                    .order_by('-suggested_at')
                    .first()
                )
                generation = (previous.adaptation_generation + 1) if previous else 1

                reason = f"User-approved ZK adaptation (gen {generation})"
                # Derive the reported delta from before/after when both are
                # present, rather than trusting the separately-sent
                # memorability_improvement verbatim -- the two are computed
                # independently client-side and nothing upstream guarantees
                # they agree, so this text could otherwise contradict the
                # memorability_score_before/_after actually stored for the
                # same row (round 7 review). before/after are the more
                # granular, individually-bounded signal, so they win when
                # both are available; memorability_improvement is only used
                # standalone for a pre-Phase-4 client that sent no absolute
                # scores at all (see test_scores_are_omitted_together_or_
                # not_at_all for why a lone score is dropped, not rejected,
                # a case this must not disturb).
                has_score_pair = (
                    memorability_score_before is not None
                    and memorability_score_after is not None
                )
                reported_delta = (
                    (memorability_score_after - memorability_score_before)
                    if has_score_pair
                    else memorability_improvement
                )
                if reported_delta is not None:
                    reason += (
                        f"; client-reported memorability Δ={reported_delta:+.2f}"
                    )

                # Free the parent's unique (adapted_fingerprint, active) slot
                # before inserting the child to avoid a self-collision when a
                # password is adapted back to a prior fingerprint.
                if previous:
                    previous.status = 'rolled_back'
                    previous.rolled_back_at = timezone.now()
                    previous.save(update_fields=['status', 'rolled_back_at'])

                adaptation = PasswordAdaptation.objects.create(
                    user=self.user,
                    original_fingerprint=original_fingerprint,
                    adapted_fingerprint=adapted_fingerprint,
                    fp_key_version=config.fp_key_version,
                    original_masked=previews.get('original_masked', ''),
                    adapted_masked=previews.get('adapted_masked', ''),
                    previous_adaptation=previous,
                    adaptation_generation=generation,
                    adaptation_type='substitution',
                    substitutions_applied=substitutions_applied,
                    confidence_score=confidence_score,
                    # Phase 4: the client's real readings, or NULL when it did
                    # not send them. Storing only ONE of the pair would be
                    # worse than storing neither -- get_evolution_stats keys
                    # off `memorability_score_before is not None` and would
                    # then average a delta against an implicit 0 -- so the
                    # pair is written together or not at all.
                    memorability_score_before=(
                        memorability_score_before if has_score_pair else None
                    ),
                    memorability_score_after=(
                        memorability_score_after if has_score_pair else None
                    ),
                    memorability_driver=memorability_driver or '',
                    # Same "together or not at all" reasoning as the score pair
                    # above, for the same reason: a delta with no driver names no
                    # feature to attribute it to, so nudge_memorability_weights
                    # could never use it. Accept-and-normalize rather than
                    # reject, matching this endpoint's established contract for
                    # an incomplete memorability payload.
                    memorability_driver_delta=(
                        memorability_driver_delta if memorability_driver else None
                    ),
                    status='active',
                    decided_at=timezone.now(),
                    reason=reason,
                )

                # Close the near end of the learning loop (plan §3.3, gap B2):
                # before Phase 3, accepting a suggestion taught the model
                # nothing at all. Credit each applied substitution class with a
                # partial acceptance reward — weak positive evidence, since
                # take-up is not yet proof the change helped. Inside the same
                # atomic block so a failed insert cannot leave a credited arm
                # behind for an adaptation that never existed.
                credit_adaptation_best_effort(adaptation, ACCEPTANCE_REWARD)
        except IntegrityError:
            # Another concurrent apply already created the active row for this
            # adapted_fingerprint. Surface a deterministic, retryable error
            # instead of leaving a forked chain.
            logger.warning(
                'Concurrent ZK adaptation rejected for user %s (adapted_fingerprint clash)',
                self.user.id,
            )
            return {'error': 'An active adaptation for this fingerprint already exists.'}

        # Atomic single-column UPDATE: avoids writing back a possibly-stale
        # config instance fetched before the transaction above.
        AdaptivePasswordConfig.objects.filter(user=self.user).update(
            last_suggestion_at=timezone.now()
        )

        return {
            'schema_version': 2,
            'adaptation_id': str(adaptation.id),
            'generation': generation,
            'can_rollback': previous is not None,
        }

    def rollback_adaptation(
        self,
        adaptation_id: str,
    ) -> Dict[str, Any]:
        """
        Rollback to previous password version.
        
        Args:
            adaptation_id: ID of adaptation to rollback
            
        Returns:
            Rollback result
        """
        from ..models import (
            AdaptivePasswordConfig, PasswordAdaptation, UserTypingProfile
        )

        try:
            config = AdaptivePasswordConfig.objects.get(user=self.user)
        except AdaptivePasswordConfig.DoesNotExist:
            return {'error': 'Adaptive passwords not configured'}

        # Era-scoped: rows from a superseded fingerprint key era are retained for
        # audit but must not be reactivated — their fingerprints no longer
        # correspond to anything the client can derive.
        #
        # Atomic + row-locked, mirroring apply_adaptation_v2: releasing the
        # child's 'active' slot and reactivating the parent must commit
        # together, or a failure between the two saves would leave the chain
        # with no active row at all. select_for_update() also serializes
        # against a concurrent apply/rollback on the same chain, and the
        # IntegrityError guard is the DB-level backstop for the era-scoped
        # uniq_active_original_fp_per_user constraint.
        try:
            with transaction.atomic():
                try:
                    adaptation = PasswordAdaptation.objects.select_for_update().get(
                        id=adaptation_id,
                        user=self.user,
                        fp_key_version=config.fp_key_version,
                    )
                except PasswordAdaptation.DoesNotExist:
                    return {'error': 'Adaptation not found'}

                if not adaptation.can_rollback():
                    return {'error': 'Cannot rollback this adaptation'}

                previous = adaptation.previous_adaptation

                # Mark current as rolled back
                adaptation.status = 'rolled_back'
                adaptation.rolled_back_at = timezone.now()
                adaptation.save(update_fields=['status', 'rolled_back_at'])

                # Reactivate previous
                previous.status = 'active'
                previous.save(update_fields=['status'])

                # Close the far end of the loop (plan §3.3): an undo is the
                # strongest negative signal this feature can observe, so the
                # arm takes a hard-zero reward. Kept alongside — not instead
                # of — the substitution_confidence decay below: the two writers
                # feed different consumers (the bandit posterior and the
                # UserTypingProfile aggregate), and leaving one of them
                # un-updated on rollback is exactly the inconsistency that made
                # the old confidence decay the only thing a rollback taught.
                credit_adaptation_best_effort(adaptation, ROLLBACK_REWARD)
        except IntegrityError:
            logger.warning(
                'Rollback rejected for user %s (active fingerprint clash)',
                self.user.id,
            )
            return {'error': 'An active adaptation for this fingerprint already exists.'}

        # Update typing profile to avoid same suggestion
        try:
            profile = UserTypingProfile.objects.get(user=self.user)
            # Reduce confidence in the rolled-back substitutions
            for pos, sub in adaptation.substitutions_applied.items():
                sub_key = f"{sub.get('from', '')}->{sub.get('to', '')}"
                if sub_key in profile.substitution_confidence:
                    profile.substitution_confidence[sub_key] *= 0.5
            profile.save()
        except UserTypingProfile.DoesNotExist:
            pass

        return {
            'success': True,
            'rolled_back_to': str(previous.id),
            'generation': previous.adaptation_generation,
        }
    
    def get_adaptation_history(self) -> List[Dict]:
        """Get user's adaptation history for the CURRENT fingerprint key era.

        Rows from superseded eras are deliberately omitted: their fingerprints
        were derived under a different key, so presenting them as part of the
        user's live adaptation chain would be misleading. They remain in the DB
        and are still covered by the GDPR export/delete paths.
        """
        from ..models import AdaptivePasswordConfig, PasswordAdaptation

        try:
            fp_key_version = AdaptivePasswordConfig.objects.values_list(
                'fp_key_version', flat=True
            ).get(user=self.user)
        except AdaptivePasswordConfig.DoesNotExist:
            return []

        # select_related: can_rollback() below reads self.previous_adaptation
        # (a FK) on every 'active' row; without this, each such row issues its
        # own lazy SELECT (N+1) instead of a single JOIN.
        adaptations = PasswordAdaptation.objects.filter(
            user=self.user,
            fp_key_version=fp_key_version,
        ).select_related('previous_adaptation').order_by('-suggested_at')[:20]
        
        return [
            {
                'id': str(a.id),
                'generation': a.adaptation_generation,
                'type': a.adaptation_type,
                'status': a.status,
                'suggested_at': a.suggested_at.isoformat(),
                'memorability_before': a.memorability_score_before,
                'memorability_after': a.memorability_score_after,
                'can_rollback': a.can_rollback(),
            }
            for a in adaptations
        ]
    
    def delete_all_data(self) -> Dict[str, int]:
        """
        Delete all typing data for GDPR compliance.
        
        Returns:
            Count of deleted records
        """
        from ..models import (
            TypingSession, PasswordAdaptation,
            UserTypingProfile, AdaptivePasswordConfig, SubstitutionPolicyArm
        )

        counts = {}

        # Erasure must be all-or-nothing: without this, a failure partway
        # through (e.g. a dropped connection between deletes) leaves earlier
        # deletes committed and later ones -- including the policy-arm delete
        # below, which runs last and would be the most likely step skipped --
        # never applied, silently leaving the user partially erased with no
        # way to tell from the exception alone what actually survived.
        with transaction.atomic():
            counts['typing_sessions'] = TypingSession.objects.filter(
                user=self.user
            ).delete()[0]

            counts['adaptations'] = PasswordAdaptation.objects.filter(
                user=self.user
            ).delete()[0]

            counts['profiles'] = UserTypingProfile.objects.filter(
                user=self.user
            ).delete()[0]

            # The bandit's per-user learned posteriors (which substitutions
            # THIS user tends to accept) are personal data too, independently
            # keyed by `user` -- deleting PasswordAdaptation above does not
            # cascade to these, so without this they would survive GDPR
            # erasure indefinitely even though the account itself is kept.
            counts['policy_arms'] = SubstitutionPolicyArm.objects.filter(
                user=self.user
            ).delete()[0]

            # Disable but don't delete config
            try:
                config = AdaptivePasswordConfig.objects.get(user=self.user)
                config.is_enabled = False
                config.save()
                counts['config_disabled'] = 1
            except AdaptivePasswordConfig.DoesNotExist:
                counts['config_disabled'] = 0

        logger.info(f"Deleted adaptive password data for user {self.user.id}: {counts}")
        
        return counts
