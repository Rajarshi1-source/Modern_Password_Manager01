"""
Implicit Memory Detector Service
================================

ML-based classification to detect whether a responder has implicit
memory traces of the password (indicating genuine creation) or is
using stolen credentials (no implicit memory).

@author Password Manager Team
@created 2026-02-07
"""

import math
import statistics
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from django.conf import settings


@dataclass
class DetectionResult:
    """Result of implicit memory detection."""
    is_creator: bool
    creator_probability: float
    confidence: float
    features: Dict[str, float]
    anomalies: List[str]
    explanation: str


class ImplicitMemoryDetector:
    """
    Detects implicit memory traces that distinguish password creators
    from attackers.
    
    Psychological basis:
    - Creators have procedural memory from typing the password repeatedly
    - Creators show faster recognition of their own password elements
    - Creators exhibit priming effects with password-related stimuli
    - Attackers lack these implicit traces even with plaintext access
    
    This service uses a rule-based classifier with the following features:
    1. Reaction time advantage (faster = more likely creator)
    2. Response consistency (lower variance = more likely creator)
    3. Stroop interference pattern (specific patterns for creators)
    4. Priming effect magnitude
    5. Accuracy under time pressure
    """
    
    # Classification thresholds
    DEFAULT_CREATOR_THRESHOLD = 0.65
    DEFAULT_HIGH_CONFIDENCE_THRESHOLD = 0.85
    
    def __init__(self, user_profile: Optional[Dict] = None):
        """
        Initialize detector with optional user cognitive profile.
        
        Args:
            user_profile: User's baseline cognitive profile data
        """
        self.profile = user_profile or {}
        
        config = getattr(settings, 'COGNITIVE_AUTH', {})
        self.creator_threshold = config.get('ML_CONFIDENCE_THRESHOLD', self.DEFAULT_CREATOR_THRESHOLD)
        self.creator_advantage = config.get('CREATOR_ADVANTAGE_FACTOR', 0.3)
    
    def detect(
        self,
        session_data: Dict[str, Any],
        responses: List[Dict[str, Any]]
    ) -> DetectionResult:
        """
        Analyze session data to detect implicit memory traces.
        
        Args:
            session_data: Metadata about the verification session
            responses: List of challenge responses with timing data
            
        Returns:
            DetectionResult with classification and explanation
        """
        if len(responses) < 3:
            return DetectionResult(
                is_creator=False,
                creator_probability=0.5,
                confidence=0.0,
                features={},
                anomalies=['insufficient_data'],
                explanation="Not enough responses for reliable detection"
            )
        
        # Extract features
        features = self._extract_features(responses)
        
        # Detect anomalies
        anomalies = self._detect_anomalies(features, responses)
        
        # Calculate creator probability
        creator_probability = self._calculate_creator_probability(features)
        
        # Calculate confidence
        confidence = self._calculate_confidence(features, responses)
        
        # If anomalies detected, reduce confidence
        if anomalies:
            confidence *= 0.7
            creator_probability *= 0.8
        
        # Make classification decision
        is_creator = creator_probability >= self.creator_threshold
        
        # Generate explanation
        explanation = self._generate_explanation(features, is_creator, anomalies)
        
        return DetectionResult(
            is_creator=is_creator,
            creator_probability=creator_probability,
            confidence=confidence,
            features=features,
            anomalies=anomalies,
            explanation=explanation
        )
    
    def _extract_features(self, responses: List[Dict[str, Any]]) -> Dict[str, float]:
        """Extract features for classification."""
        # Basic timing features
        times = [r['reaction_time_ms'] for r in responses]
        correct_times = [r['reaction_time_ms'] for r in responses if r.get('is_correct', False)]
        
        mean_time = statistics.mean(times)
        std_time = statistics.stdev(times) if len(times) > 1 else 0
        
        # Baseline comparison
        baseline_mean = self.profile.get('baseline_reaction_time_mean', mean_time * 1.3)
        speed_ratio = mean_time / baseline_mean if baseline_mean > 0 else 1.0
        
        # Accuracy
        accuracy = len([r for r in responses if r.get('is_correct', False)]) / len(responses)
        
        # Consistency (coefficient of variation)
        cv = std_time / mean_time if mean_time > 0 else 0
        
        # Hesitation pattern
        avg_hesitations = statistics.mean([r.get('hesitation_count', 0) for r in responses])
        
        # Correction pattern
        avg_corrections = statistics.mean([r.get('correction_count', 0) for r in responses])
        
        # Per-challenge-type features
        type_features = self._extract_type_features(responses)
        
        features = {
            'mean_reaction_time': mean_time,
            'std_reaction_time': std_time,
            'speed_ratio': speed_ratio,
            'accuracy': accuracy,
            'coefficient_of_variation': cv,
            'avg_hesitations': avg_hesitations,
            'avg_corrections': avg_corrections,
            **type_features
        }
        
        return features
    
    def _extract_type_features(self, responses: List[Dict[str, Any]]) -> Dict[str, float]:
        """Extract per-challenge-type features."""
        type_groups = {}
        for r in responses:
            ctype = r.get('challenge_type', 'unknown')
            if ctype not in type_groups:
                type_groups[ctype] = []
            type_groups[ctype].append(r)
        
        features = {}
        
        for ctype, group in type_groups.items():
            times = [r['reaction_time_ms'] for r in group]
            accuracy = len([r for r in group if r.get('is_correct', False)]) / len(group)
            
            features[f'{ctype}_mean_time'] = statistics.mean(times) if times else 0
            features[f'{ctype}_accuracy'] = accuracy
        
        return features
    
    def _detect_anomalies(
        self, 
        features: Dict[str, float],
        responses: List[Dict[str, Any]]
    ) -> List[str]:
        """Detect anomalous patterns indicative of an attacker."""
        anomalies = []
        
        # Check for robotic timing (too consistent)
        if features['coefficient_of_variation'] < 0.05:
            anomalies.append('robotic_timing')
        
        # Check for excessive slowness
        if features['speed_ratio'] > 2.0:
            anomalies.append('very_slow_responses')
        
        # Check for high error rate with slow responses (unusual combination)
        if features['accuracy'] < 0.5 and features['mean_reaction_time'] > 2000:
            anomalies.append('slow_with_errors')
        
        # Check for declining performance (fatigue vs learning curve)
        if len(responses) >= 6:
            first_half = responses[:len(responses)//2]
            second_half = responses[len(responses)//2:]
            
            first_accuracy = len([r for r in first_half if r.get('is_correct', False)]) / len(first_half)
            second_accuracy = len([r for r in second_half if r.get('is_correct', False)]) / len(second_half)
            
            if first_accuracy - second_accuracy > 0.3:
                anomalies.append('performance_decline')
        
        # Check for perfect accuracy with high reaction times (memorized responses)
        if features['accuracy'] == 1.0 and features['mean_reaction_time'] > 1500:
            anomalies.append('slow_perfect_accuracy')
        
        return anomalies
    
    def _calculate_creator_probability(self, features: Dict[str, float]) -> float:
        """
        Calculate probability that responder is the password creator.
        
        Uses weighted feature scoring based on implicit memory principles.
        """
        probability = 0.5  # Start neutral
        
        # Feature 1: Speed ratio (most important)
        # Creators should be ~30% faster than baseline
        expected_ratio = 1.0 - self.creator_advantage  # 0.7
        if features['speed_ratio'] <= expected_ratio:
            # Faster than expected - strong creator signal
            bonus = min(0.2, (expected_ratio - features['speed_ratio']) * 0.5)
            probability += bonus
        elif features['speed_ratio'] > 1.5:
            # Much slower - strong attacker signal
            penalty = min(0.25, (features['speed_ratio'] - 1.0) * 0.2)
            probability -= penalty
        
        # Feature 2: Consistency
        expected_cv = 0.2  # Creators have consistent timing
        if features['coefficient_of_variation'] < expected_cv:
            probability += 0.1
        elif features['coefficient_of_variation'] > 0.5:
            probability -= 0.1
        
        # Feature 3: Accuracy
        if features['accuracy'] >= 0.9:
            probability += 0.1
        elif features['accuracy'] >= 0.7:
            probability += 0.05
        elif features['accuracy'] < 0.5:
            probability -= 0.15
        
        # Feature 4: Hesitation pattern (creators hesitate less)
        if features['avg_hesitations'] < 0.5:
            probability += 0.05
        elif features['avg_hesitations'] > 2:
            probability -= 0.1
        
        # Feature 5: Correction pattern (creators make fewer corrections)
        if features['avg_corrections'] < 0.3:
            probability += 0.05
        elif features['avg_corrections'] > 1.5:
            probability -= 0.1
        
        # Feature 6: Stroop performance (if available)
        # Creators show specific interference patterns
        if 'stroop_accuracy' in features:
            # Stroop is harder, so lower accuracy is expected
            # But creators still outperform attackers
            if features['stroop_accuracy'] >= 0.8:
                probability += 0.05
        
        # Feature 7: Priming effect (if available)
        # Creators show stronger priming
        if 'priming_mean_time' in features and 'scrambled_mean_time' in features:
            priming_advantage = features['scrambled_mean_time'] - features['priming_mean_time']
            if priming_advantage > 100:  # 100ms faster with priming
                probability += 0.05
        
        return max(0.0, min(1.0, probability))
    
    def _calculate_confidence(
        self, 
        features: Dict[str, float],
        responses: List[Dict[str, Any]]
    ) -> float:
        """Calculate confidence in the classification."""
        # Base confidence from sample size
        n = len(responses)
        sample_confidence = min(1.0, n / 10)  # Full confidence at 10+ samples
        
        # Confidence from feature clarity
        # If features strongly indicate creator or attacker, confidence is high
        creator_prob = self._calculate_creator_probability(features)
        decision_clarity = abs(creator_prob - 0.5) * 2  # 0-1 scale
        
        # Confidence from consistency
        consistency_confidence = 1.0 - min(1.0, features['coefficient_of_variation'])
        
        # Combine factors
        confidence = (
            sample_confidence * 0.3 +
            decision_clarity * 0.5 +
            consistency_confidence * 0.2
        )
        
        return min(1.0, confidence)
    
    def _generate_explanation(
        self,
        features: Dict[str, float],
        is_creator: bool,
        anomalies: List[str]
    ) -> str:
        """Generate human-readable explanation of the classification."""
        if is_creator:
            explanation = "Implicit memory traces detected: "
            factors = []
            
            if features['speed_ratio'] < 0.8:
                factors.append("response speed consistent with creator familiarity")
            if features['coefficient_of_variation'] < 0.25:
                factors.append("timing consistency indicates procedural memory")
            if features['accuracy'] >= 0.8:
                factors.append("high accuracy under time pressure")
            if features.get('avg_hesitations', 1) < 0.5:
                factors.append("low hesitation suggests automatic recognition")
            
            explanation += "; ".join(factors) if factors else "multiple implicit memory indicators present"
        else:
            explanation = "Insufficient implicit memory evidence: "
            factors = []
            
            if features['speed_ratio'] > 1.3:
                factors.append("slower than expected for password creator")
            if features['coefficient_of_variation'] > 0.4:
                factors.append("high timing variability suggests deliberate responses")
            if features['accuracy'] < 0.6:
                factors.append("low accuracy indicates unfamiliarity")
            if features.get('avg_hesitations', 0) > 1.5:
                factors.append("hesitation pattern inconsistent with implicit memory")
            
            explanation += "; ".join(factors) if factors else "response patterns inconsistent with password creator"
        
        if anomalies:
            explanation += f" [Anomalies detected: {', '.join(anomalies)}]"
        
        return explanation
    
    def get_feature_importance(self) -> Dict[str, float]:
        """Return the relative importance of each feature."""
        return {
            'speed_ratio': 0.25,
            'coefficient_of_variation': 0.20,
            'accuracy': 0.20,
            'avg_hesitations': 0.10,
            'avg_corrections': 0.10,
            'stroop_performance': 0.08,
            'priming_effect': 0.07,
        }
