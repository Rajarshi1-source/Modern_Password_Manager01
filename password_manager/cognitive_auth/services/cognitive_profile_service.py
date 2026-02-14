"""
Cognitive Profile Service
=========================

Manages user cognitive profiles including baseline calibration,
profile updates, and profile quality assessment.

@author Password Manager Team
@created 2026-02-07
"""

import statistics
from typing import Dict, List, Any, Optional, TYPE_CHECKING
from django.conf import settings
from django.utils import timezone
from django.db import transaction

if TYPE_CHECKING:
    from ..models import CognitiveProfile


class CognitiveProfileService:
    """
    Service for managing user cognitive profiles.
    
    Profiles capture baseline reaction times and recognition patterns
    that are used to detect implicit memory during verification.
    """
    
    # Calibration requirements
    MIN_CALIBRATION_CHALLENGES = 15
    TARGET_CALIBRATION_CHALLENGES = 20
    
    def __init__(self):
        """Initialize profile service."""
        config = getattr(settings, 'COGNITIVE_AUTH', {})
        self.min_calibration = config.get(
            'BASELINE_CALIBRATION_CHALLENGES', 
            self.MIN_CALIBRATION_CHALLENGES
        )
    
    def get_or_create_profile(self, user) -> 'CognitiveProfile':
        """Get existing profile or create new one for user."""
        from ..models import CognitiveProfile
        
        profile, created = CognitiveProfile.objects.get_or_create(
            user=user,
            defaults={
                'scrambled_baseline': {},
                'stroop_baseline': {},
                'priming_baseline': {},
                'partial_baseline': {},
            }
        )
        
        return profile
    
    def update_profile_from_responses(
        self,
        user,
        responses: List[Dict[str, Any]],
        is_calibration: bool = False
    ) -> 'CognitiveProfile':
        """
        Update user's profile with new response data.
        
        Args:
            user: User object
            responses: List of challenge responses
            is_calibration: Whether this is a calibration session
            
        Returns:
            Updated CognitiveProfile
        """
        profile = self.get_or_create_profile(user)
        
        # Only use correct responses for baseline updates
        correct_responses = [r for r in responses if r.get('is_correct', False)]
        
        if not correct_responses:
            return profile
        
        # Update overall baseline
        reaction_times = [r['reaction_time_ms'] for r in correct_responses]
        self._update_overall_baseline(profile, reaction_times, is_calibration)
        
        # Update per-type baselines
        self._update_type_baselines(profile, correct_responses, is_calibration)
        
        # Update calibration status
        if is_calibration:
            profile.calibration_challenges_completed += len(correct_responses)
            
            if profile.calibration_challenges_completed >= self.min_calibration:
                profile.is_calibrated = True
        
        # Update profile quality
        profile.profile_confidence = self._calculate_profile_confidence(profile)
        profile.last_calibration_at = timezone.now()
        
        # Generate cognitive fingerprint
        profile.cognitive_fingerprint = self._generate_fingerprint(profile)
        
        profile.save()
        
        return profile
    
    def _update_overall_baseline(
        self,
        profile: 'CognitiveProfile',
        reaction_times: List[float],
        is_calibration: bool
    ):
        """Update overall reaction time baseline."""
        if not reaction_times:
            return
        
        new_mean = statistics.mean(reaction_times)
        new_std = statistics.stdev(reaction_times) if len(reaction_times) > 1 else 0
        
        if profile.baseline_reaction_time_mean == 0 or is_calibration:
            # First calibration or recalibration
            profile.baseline_reaction_time_mean = new_mean
            profile.baseline_reaction_time_std = new_std
        else:
            # Exponential smoothing update
            alpha = 0.1  # Learning rate
            profile.baseline_reaction_time_mean = (
                profile.baseline_reaction_time_mean * (1 - alpha) + 
                new_mean * alpha
            )
            profile.baseline_reaction_time_std = (
                profile.baseline_reaction_time_std * (1 - alpha) + 
                new_std * alpha
            )
    
    def _update_type_baselines(
        self,
        profile: 'CognitiveProfile',
        responses: List[Dict[str, Any]],
        is_calibration: bool
    ):
        """Update per-challenge-type baselines."""
        # Group responses by type
        type_groups = {}
        for r in responses:
            ctype = r.get('challenge_type', 'unknown')
            if ctype not in type_groups:
                type_groups[ctype] = []
            type_groups[ctype].append(r)
        
        baseline_fields = {
            'scrambled': 'scrambled_baseline',
            'stroop': 'stroop_baseline',
            'priming': 'priming_baseline',
            'partial': 'partial_baseline',
        }
        
        alpha = 0.2 if is_calibration else 0.1
        
        for ctype, group in type_groups.items():
            if ctype not in baseline_fields:
                continue
            
            times = [r['reaction_time_ms'] for r in group]
            new_metrics = {
                'mean': statistics.mean(times),
                'std': statistics.stdev(times) if len(times) > 1 else 0,
                'min': min(times),
                'max': max(times),
                'count': len(times),
            }
            
            field_name = baseline_fields[ctype]
            current = getattr(profile, field_name) or {}
            
            if not current or is_calibration:
                setattr(profile, field_name, new_metrics)
            else:
                # Exponential smoothing
                updated = {
                    'mean': current.get('mean', new_metrics['mean']) * (1 - alpha) + new_metrics['mean'] * alpha,
                    'std': current.get('std', new_metrics['std']) * (1 - alpha) + new_metrics['std'] * alpha,
                    'min': min(current.get('min', new_metrics['min']), new_metrics['min']),
                    'max': max(current.get('max', new_metrics['max']), new_metrics['max']),
                    'count': current.get('count', 0) + new_metrics['count'],
                }
                setattr(profile, field_name, updated)
    
    def _calculate_profile_confidence(self, profile: 'CognitiveProfile') -> float:
        """Calculate confidence in profile accuracy."""
        confidence = 0.0
        
        # Factor 1: Calibration completeness
        calibration_ratio = min(1.0, profile.calibration_challenges_completed / self.min_calibration)
        confidence += calibration_ratio * 0.4
        
        # Factor 2: Type coverage
        type_coverage = 0
        for field in ['scrambled_baseline', 'stroop_baseline', 'priming_baseline', 'partial_baseline']:
            baseline = getattr(profile, field, {})
            if baseline and baseline.get('count', 0) >= 3:
                type_coverage += 1
        
        confidence += (type_coverage / 4) * 0.3
        
        # Factor 3: Data recency
        if profile.last_calibration_at:
            days_since_update = (timezone.now() - profile.last_calibration_at).days
            recency_factor = max(0, 1 - days_since_update / 90)  # Decay over 90 days
            confidence += recency_factor * 0.3
        
        return min(1.0, confidence)
    
    def _generate_fingerprint(self, profile: 'CognitiveProfile') -> str:
        """Generate a cognitive fingerprint hash."""
        import hashlib
        
        components = [
            str(profile.baseline_reaction_time_mean),
            str(profile.baseline_reaction_time_std),
            str(profile.scrambled_baseline),
            str(profile.stroop_baseline),
            str(profile.priming_baseline),
            str(profile.partial_baseline),
        ]
        
        fingerprint_data = '|'.join(components)
        return hashlib.sha256(fingerprint_data.encode()).hexdigest()[:64]
    
    def needs_recalibration(self, profile: 'CognitiveProfile') -> bool:
        """Check if profile needs recalibration."""
        if not profile.is_calibrated:
            return True
        
        if not profile.last_calibration_at:
            return True
        
        # Recalibrate if older than 60 days
        days_since_calibration = (timezone.now() - profile.last_calibration_at).days
        if days_since_calibration > 60:
            return True
        
        # Recalibrate if confidence is low
        if profile.profile_confidence < 0.5:
            return True
        
        return False
    
    def get_profile_summary(self, user) -> Dict[str, Any]:
        """Get a summary of user's cognitive profile."""
        profile = self.get_or_create_profile(user)
        
        return {
            'is_calibrated': profile.is_calibrated,
            'calibration_progress': min(100, int(
                profile.calibration_challenges_completed / self.min_calibration * 100
            )),
            'profile_confidence': profile.profile_confidence,
            'baseline_reaction_time': profile.baseline_reaction_time_mean,
            'needs_recalibration': self.needs_recalibration(profile),
            'last_updated': profile.last_calibration_at.isoformat() if profile.last_calibration_at else None,
            'type_coverage': {
                'scrambled': bool(profile.scrambled_baseline),
                'stroop': bool(profile.stroop_baseline),
                'priming': bool(profile.priming_baseline),
                'partial': bool(profile.partial_baseline),
            }
        }
    
    def reset_profile(self, user) -> 'CognitiveProfile':
        """Reset user's cognitive profile for recalibration."""
        profile = self.get_or_create_profile(user)
        
        profile.baseline_reaction_time_mean = 0.0
        profile.baseline_reaction_time_std = 0.0
        profile.scrambled_baseline = {}
        profile.stroop_baseline = {}
        profile.priming_baseline = {}
        profile.partial_baseline = {}
        profile.calibration_challenges_completed = 0
        profile.is_calibrated = False
        profile.profile_confidence = 0.0
        profile.cognitive_fingerprint = ''
        
        profile.save()
        
        return profile
