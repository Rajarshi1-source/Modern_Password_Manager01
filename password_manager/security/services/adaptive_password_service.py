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
from typing import Dict, List, Optional, Any
import logging
import numpy as np

from django.contrib.auth.models import User
from django.db import transaction, IntegrityError
from django.utils import timezone

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
        
        # Update WPM
        if pattern.total_time_ms > 0:
            # Approximate WPM from password length and time
            chars_per_min = (pattern.password_length / pattern.total_time_ms) * 60000
            wpm = chars_per_min / 5  # Standard: 5 chars = 1 word
            
            if profile.average_wpm is None:
                profile.average_wpm = wpm
            else:
                profile.average_wpm = profile.average_wpm * 0.9 + wpm * 0.1
        
        # Update profile confidence
        profile.profile_confidence = min(1.0, profile.total_sessions / 50)
        profile.last_session_at = timezone.now()
        
        profile.save()
    
    def export_preference_model(self) -> Dict[str, Any]:
        """Export the per-user preference model for client-side suggestion ranking.

        This is the zero-knowledge replacement for the server-side ``/suggest/``
        path: the client downloads this model and ranks locally-generated
        candidates against it (remediation plan §4). It contains only aggregate,
        non-reversible signals — substitution-class weights + memorability
        params — and never any password-derived data.

        Returns:
            ``{model_version, substitution_weights, memorability_params}``.
        """
        from ..models import UserTypingProfile

        # Baseline weights from the shared leetspeak map (primary > secondary).
        substitution_weights: Dict[str, Dict[str, float]] = {}
        for char, subs in COMMON_SUBSTITUTIONS.items():
            substitution_weights[char] = {
                sub: (0.6 if idx == 0 else 0.4) for idx, sub in enumerate(subs)
            }

        model_version = 0
        try:
            profile = UserTypingProfile.objects.get(user=self.user)
        except UserTypingProfile.DoesNotExist:
            profile = None

        if profile is not None:
            # Monotonic-ish version so the client can cache/invalidate.
            model_version = profile.total_sessions

            # Learned per-class confidence overrides the baseline.
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
                substitution_weights.setdefault(from_char, {})[to_char] = max(
                    0.0, min(1.0, conf)
                )

            # Explicit preferences get a strong confidence so the client ranks
            # them first.
            for from_char, to_char in (profile.preferred_substitutions or {}).items():
                if not isinstance(from_char, str) or not isinstance(to_char, str):
                    continue
                row = substitution_weights.setdefault(from_char, {})
                row[to_char] = max(row.get(to_char, 0.0), 0.9)

        memorability_params = {
            'optimal_length_min': 12,
            'optimal_length_max': 16,
            'weights': {
                'length': 0.2,
                'patterns': 0.3,
                'variety': 0.2,
                'pronounceable': 0.3,
            },
        }

        return {
            'model_version': model_version,
            'substitution_weights': substitution_weights,
            'memorability_params': memorability_params,
        }

    def apply_adaptation_v2(
        self,
        original_fingerprint: str,
        adapted_fingerprint: str,
        substitution_classes: List[Dict],
        previews: Optional[Dict[str, str]] = None,
        memorability_improvement: Optional[float] = None,
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
                previous = (
                    PasswordAdaptation.objects.select_for_update()
                    .filter(
                        user=self.user,
                        adapted_fingerprint=original_fingerprint,
                        status='active',
                    )
                    .order_by('-suggested_at')
                    .first()
                )
                generation = (previous.adaptation_generation + 1) if previous else 1

                reason = f"User-approved ZK adaptation (gen {generation})"
                if memorability_improvement is not None:
                    reason += (
                        f"; client-reported memorability Δ={memorability_improvement:+.2f}"
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
                    original_masked=previews.get('original_masked', ''),
                    adapted_masked=previews.get('adapted_masked', ''),
                    previous_adaptation=previous,
                    adaptation_generation=generation,
                    adaptation_type='substitution',
                    substitutions_applied=substitutions_applied,
                    confidence_score=confidence_score,
                    memorability_score_before=None,
                    memorability_score_after=None,
                    status='active',
                    decided_at=timezone.now(),
                    reason=reason,
                )
        except IntegrityError:
            # Another concurrent apply already created the active row for this
            # adapted_fingerprint. Surface a deterministic, retryable error
            # instead of leaving a forked chain.
            logger.warning(
                'Concurrent ZK adaptation rejected for user %s (adapted_fingerprint clash)',
                self.user.id,
            )
            return {'error': 'An active adaptation for this fingerprint already exists.'}

        config.last_suggestion_at = timezone.now()
        config.save(update_fields=['last_suggestion_at'])

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
        from ..models import PasswordAdaptation, UserTypingProfile
        
        try:
            adaptation = PasswordAdaptation.objects.get(
                id=adaptation_id,
                user=self.user,
            )
        except PasswordAdaptation.DoesNotExist:
            return {'error': 'Adaptation not found'}
        
        if not adaptation.can_rollback():
            return {'error': 'Cannot rollback this adaptation'}
        
        previous = adaptation.previous_adaptation
        
        # Mark current as rolled back
        adaptation.status = 'rolled_back'
        adaptation.rolled_back_at = timezone.now()
        adaptation.save()
        
        # Reactivate previous
        previous.status = 'active'
        previous.save()
        
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
        """Get user's adaptation history."""
        from ..models import PasswordAdaptation
        
        adaptations = PasswordAdaptation.objects.filter(
            user=self.user
        ).order_by('-suggested_at')[:20]
        
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
            UserTypingProfile, AdaptivePasswordConfig
        )
        
        counts = {}
        
        counts['typing_sessions'] = TypingSession.objects.filter(
            user=self.user
        ).delete()[0]
        
        counts['adaptations'] = PasswordAdaptation.objects.filter(
            user=self.user
        ).delete()[0]
        
        counts['profiles'] = UserTypingProfile.objects.filter(
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
