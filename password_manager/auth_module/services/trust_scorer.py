"""
Trust Scoring Service for Recovery Attempts

Calculates comprehensive trust scores based on:
- Challenge success rate (40%)
- Device recognition (20%)
- Behavioral biometrics match (20%)
- Temporal consistency (20%)
"""

from django.utils import timezone
from datetime import timedelta
import numpy as np
from typing import Optional

from security.models import UserDevice
from auth_module.quantum_recovery_models import RecoveryAttempt, BehavioralBiometrics, TemporalChallenge


class TrustScorerService:
    """Calculate trust scores for recovery attempts"""
    
    def calculate_comprehensive_trust_score(self, attempt: RecoveryAttempt) -> float:
        """
        Calculate overall trust score
        
        Formula:
        Trust Score = (Challenge Success × 0.4) + (Device Recognition × 0.2) + 
                     (Behavioral Match × 0.2) + (Temporal Consistency × 0.2)
        
        Returns:
            Float between 0.0 and 1.0
        """
        challenge_score = self.calculate_challenge_success_score(attempt)
        device_score = self.calculate_device_recognition_score(attempt)
        behavioral_score = self.calculate_behavioral_match_score(attempt)
        temporal_score = self.calculate_temporal_consistency_score(attempt)
        
        trust_score = (
            challenge_score * 0.4 +
            device_score * 0.2 +
            behavioral_score * 0.2 +
            temporal_score * 0.2
        )
        
        return min(1.0, max(0.0, trust_score))
    
    def calculate_challenge_success_score(self, attempt: RecoveryAttempt) -> float:
        """
        Calculate score based on challenge success rate
        
        Returns:
            0.0 to 1.0
        """
        if attempt.challenges_sent == 0:
            return 0.0
        
        success_rate = attempt.challenges_completed / attempt.challenges_sent
        
        # Apply penalty for failed attempts
        failure_penalty = attempt.challenges_failed * 0.1
        
        score = success_rate - failure_penalty
        
        return max(0.0, min(1.0, score))
    
    def calculate_device_recognition_score(self, attempt: RecoveryAttempt) -> float:
        """
        Score based on device fingerprint matching
        
        Scoring:
        - 1.0: Known trusted device
        - 0.7: Known device (not trusted)
        - 0.5: Similar device characteristics
        - 0.2: Unknown device with some common features
        - 0.0: Completely unknown device
        """
        device_fp = attempt.initiated_from_device_fingerprint
        user = attempt.recovery_setup.user
        
        if not device_fp:
            return 0.3  # Neutral if no fingerprint
        
        # Check for exact match with trusted device
        if UserDevice.objects.filter(
            user=user,
            fingerprint=device_fp,
            is_trusted=True
        ).exists():
            return 1.0
        
        # Check for exact match with known device
        if UserDevice.objects.filter(
            user=user,
            fingerprint=device_fp
        ).exists():
            return 0.7
        
        # Check for similar devices
        user_devices = UserDevice.objects.filter(user=user)
        if user_devices.exists():
            # Calculate similarity based on browser, OS, device type
            similarity_scores = []
            for device in user_devices:
                similarity = self._calculate_device_similarity(attempt, device)
                similarity_scores.append(similarity)
            
            max_similarity = max(similarity_scores) if similarity_scores else 0.0
            
            # Scale similarity to 0.2-0.5 range
            return 0.2 + (max_similarity * 0.3)
        
        return 0.0
    
    def calculate_behavioral_match_score(self, attempt: RecoveryAttempt) -> float:
        """
        Score based on behavioral biometrics matching
        
        Compares:
        - Typical login times
        - Typical locations
        - Challenge response timing patterns
        """
        user = attempt.recovery_setup.user
        behavioral = BehavioralBiometrics.objects.filter(user=user).first()
        
        if not behavioral:
            return 0.5  # Neutral if no baseline
        
        # Analyze challenge response patterns
        challenges = attempt.challenges.filter(status='completed')
        
        if challenges.count() < 3:
            return 0.5  # Not enough data
        
        # Calculate individual components
        time_match = self._match_typical_times(attempt, behavioral)
        location_match = self._match_typical_locations(attempt, behavioral)
        timing_pattern = self._analyze_response_timing_patterns(challenges)
        
        # Weighted average
        score = (time_match * 0.4 + location_match * 0.3 + timing_pattern * 0.3)
        
        return score
    
    def calculate_temporal_consistency_score(self, attempt: RecoveryAttempt) -> float:
        """
        Score based on temporal response patterns
        
        Analyzes:
        - Response timing consistency
        - Response time windows matching typical behavior
        - Pattern of engagement over time
        """
        challenges = attempt.challenges.filter(status='completed')
        
        if challenges.count() < 3:
            return 0.5  # Not enough data
        
        # Calculate response time variance (lower variance = more consistent)
        response_times = []
        for challenge in challenges:
            if challenge.actual_response_time_seconds:
                response_times.append(challenge.actual_response_time_seconds)
        
        if not response_times:
            return 0.5
        
        # Calculate coefficient of variation (normalized standard deviation)
        mean_time = np.mean(response_times)
        std_time = np.std(response_times)
        
        if mean_time == 0:
            cv = 0
        else:
            cv = std_time / mean_time
        
        # Lower CV = higher consistency score
        # CV of 0 = perfect consistency (score 1.0)
        # CV of 1 = high variance (score 0.5)
        # CV of 2+ = very inconsistent (score 0.0)
        consistency_score = max(0.0, 1.0 - (cv / 2.0))
        
        # Check if responses occurred in expected time windows
        window_match_count = 0
        for challenge in challenges:
            if challenge.timing_pattern_matches:
                window_match_count += 1
        
        window_match_score = window_match_count / challenges.count()
        
        # Weighted average
        score = (consistency_score * 0.6 + window_match_score * 0.4)
        
        return score
    
    # Helper methods
    
    def _calculate_device_similarity(self, attempt, device) -> float:
        """Calculate similarity between attempt device and known device"""
        similarity_score = 0.0
        
        # Parse user agent from attempt (simplified)
        # In production, use proper user agent parsing library
        attempt_ua = attempt.initiated_from_device_fingerprint
        
        # Compare components (browser, OS, device type)
        # This is simplified - in production, use proper comparison
        similarity_score = 0.5  # Placeholder
        
        return similarity_score
    
    def _match_typical_times(self, attempt, behavioral) -> float:
        """Match attempt time against typical login times"""
        attempt_hour = attempt.initiated_at.hour
        
        if not behavioral.typical_login_times:
            return 0.5
        
        # Check if attempt hour is in typical hours
        if attempt_hour in behavioral.typical_login_times:
            return 1.0
        
        # Check if within 2 hours of typical times
        for typical_hour in behavioral.typical_login_times:
            if abs(attempt_hour - typical_hour) <= 2:
                return 0.7
        
        return 0.3
    
    def _match_typical_locations(self, attempt, behavioral) -> float:
        """Match attempt location against typical locations"""
        attempt_location = attempt.initiated_from_location
        
        if not attempt_location or not behavioral.typical_locations:
            return 0.5
        
        # Check for exact match
        for typical_location in behavioral.typical_locations:
            if self._locations_match(attempt_location, typical_location):
                return 1.0
        
        # Check for same country/region
        for typical_location in behavioral.typical_locations:
            if self._locations_nearby(attempt_location, typical_location):
                return 0.6
        
        return 0.2
    
    def _analyze_response_timing_patterns(self, challenges) -> float:
        """Analyze timing patterns in challenge responses"""
        # Placeholder - in production, use more sophisticated analysis
        return 0.7
    
    def _locations_match(self, loc1, loc2) -> bool:
        """Check if two locations match"""
        if isinstance(loc1, dict) and isinstance(loc2, dict):
            return (
                loc1.get('city') == loc2.get('city') and
                loc1.get('country') == loc2.get('country')
            )
        return False
    
    def _locations_nearby(self, loc1, loc2) -> bool:
        """Check if two locations are nearby"""
        if isinstance(loc1, dict) and isinstance(loc2, dict):
            return loc1.get('country') == loc2.get('country')
        return False


# Global instance
trust_scorer = TrustScorerService()

