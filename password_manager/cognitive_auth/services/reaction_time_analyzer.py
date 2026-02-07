"""
Reaction Time Analyzer Service
==============================

Statistical analysis of response timing to detect implicit memory patterns.
Genuine password creators show distinct reaction time distributions
compared to attackers with stolen credentials.

@author Password Manager Team
@created 2026-02-07
"""

import math
import statistics
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from django.conf import settings


@dataclass
class ReactionTimeMetrics:
    """Container for reaction time analysis results."""
    mean: float
    median: float
    std_dev: float
    min_time: float
    max_time: float
    coefficient_of_variation: float
    z_score: float = 0.0
    percentile: float = 0.0
    is_anomalous: bool = False
    confidence: float = 0.0


class ReactionTimeAnalyzer:
    """
    Analyzes reaction time patterns to distinguish password creators
    from attackers.
    
    Key principles:
    1. Genuine creators have faster reaction times (implicit memory)
    2. Creator reaction times are more consistent (lower variance)
    3. Creators show less hesitation and fewer corrections
    4. Attackers show deliberate, calculated responses (higher latency)
    """
    
    # Configurable thresholds
    DEFAULT_ANOMALY_Z_THRESHOLD = 2.5
    DEFAULT_MIN_SAMPLES = 5
    DEFAULT_CREATOR_ADVANTAGE = 0.3  # 30% faster expected
    
    def __init__(self, baseline_metrics: Optional[Dict[str, float]] = None):
        """
        Initialize analyzer with optional baseline metrics.
        
        Args:
            baseline_metrics: User's baseline reaction time statistics
        """
        self.baseline = baseline_metrics or {}
        
        # Get config from settings
        config = getattr(settings, 'COGNITIVE_AUTH', {})
        self.anomaly_threshold = config.get('ANOMALY_Z_THRESHOLD', self.DEFAULT_ANOMALY_Z_THRESHOLD)
        self.min_samples = config.get('MIN_SAMPLES', self.DEFAULT_MIN_SAMPLES)
        self.creator_advantage = config.get('CREATOR_ADVANTAGE_FACTOR', self.DEFAULT_CREATOR_ADVANTAGE)
    
    def analyze_single_response(
        self, 
        reaction_time_ms: int,
        challenge_type: str,
        is_correct: bool
    ) -> ReactionTimeMetrics:
        """
        Analyze a single response's reaction time.
        
        Args:
            reaction_time_ms: Response time in milliseconds
            challenge_type: Type of challenge (scrambled, stroop, etc.)
            is_correct: Whether the response was correct
            
        Returns:
            ReactionTimeMetrics with analysis results
        """
        metrics = ReactionTimeMetrics(
            mean=float(reaction_time_ms),
            median=float(reaction_time_ms),
            std_dev=0.0,
            min_time=float(reaction_time_ms),
            max_time=float(reaction_time_ms),
            coefficient_of_variation=0.0,
        )
        
        # Compare to baseline if available
        if self.baseline:
            baseline_mean = self.baseline.get('mean', 0)
            baseline_std = self.baseline.get('std_dev', 1)
            
            if baseline_std > 0:
                metrics.z_score = (reaction_time_ms - baseline_mean) / baseline_std
                metrics.is_anomalous = abs(metrics.z_score) > self.anomaly_threshold
                
                # Calculate confidence based on expected creator behavior
                # Creators should be faster (negative z-score is good)
                if metrics.z_score <= 0:
                    # Faster than baseline - likely genuine
                    metrics.confidence = min(1.0, 0.5 + abs(metrics.z_score) * 0.2)
                else:
                    # Slower than baseline - suspicious
                    metrics.confidence = max(0.0, 0.5 - metrics.z_score * 0.15)
        
        # Adjust confidence based on correctness
        if not is_correct:
            metrics.confidence *= 0.5
        
        return metrics
    
    def analyze_session_responses(
        self, 
        responses: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Analyze all responses in a verification session.
        
        Args:
            responses: List of response dictionaries with timing data
            
        Returns:
            Comprehensive analysis of the session
        """
        if len(responses) < self.min_samples:
            return {
                'sufficient_data': False,
                'message': f'Need at least {self.min_samples} responses for analysis',
                'creator_probability': 0.5,
                'confidence': 0.0,
            }
        
        # Extract timing data
        reaction_times = [r['reaction_time_ms'] for r in responses]
        correct_times = [r['reaction_time_ms'] for r in responses if r.get('is_correct', False)]
        incorrect_times = [r['reaction_time_ms'] for r in responses if not r.get('is_correct', True)]
        
        # Calculate basic statistics
        overall_metrics = self._calculate_metrics(reaction_times)
        
        # Per-challenge-type analysis
        type_analysis = self._analyze_by_challenge_type(responses)
        
        # Calculate creator probability
        creator_probability = self._estimate_creator_probability(
            overall_metrics,
            responses,
            type_analysis
        )
        
        # Detect suspicious patterns
        suspicious_patterns = self._detect_suspicious_patterns(responses)
        
        return {
            'sufficient_data': True,
            'overall_metrics': {
                'mean': overall_metrics.mean,
                'median': overall_metrics.median,
                'std_dev': overall_metrics.std_dev,
                'cv': overall_metrics.coefficient_of_variation,
            },
            'accuracy': len(correct_times) / len(responses) if responses else 0,
            'correct_response_metrics': self._calculate_metrics(correct_times).__dict__ if correct_times else None,
            'type_analysis': type_analysis,
            'creator_probability': creator_probability,
            'confidence': self._calculate_overall_confidence(responses, type_analysis),
            'suspicious_patterns': suspicious_patterns,
            'is_anomalous': len(suspicious_patterns) > 0,
        }
    
    def _calculate_metrics(self, times: List[float]) -> ReactionTimeMetrics:
        """Calculate statistical metrics for a list of times."""
        if not times:
            return ReactionTimeMetrics(
                mean=0, median=0, std_dev=0, 
                min_time=0, max_time=0, coefficient_of_variation=0
            )
        
        mean = statistics.mean(times)
        median = statistics.median(times)
        std_dev = statistics.stdev(times) if len(times) > 1 else 0
        cv = (std_dev / mean) if mean > 0 else 0
        
        return ReactionTimeMetrics(
            mean=mean,
            median=median,
            std_dev=std_dev,
            min_time=min(times),
            max_time=max(times),
            coefficient_of_variation=cv,
        )
    
    def _analyze_by_challenge_type(
        self, 
        responses: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """Analyze responses grouped by challenge type."""
        type_groups = {}
        
        for response in responses:
            ctype = response.get('challenge_type', 'unknown')
            if ctype not in type_groups:
                type_groups[ctype] = []
            type_groups[ctype].append(response)
        
        analysis = {}
        for ctype, group in type_groups.items():
            times = [r['reaction_time_ms'] for r in group]
            metrics = self._calculate_metrics(times)
            
            correct_count = sum(1 for r in group if r.get('is_correct', False))
            
            analysis[ctype] = {
                'count': len(group),
                'accuracy': correct_count / len(group) if group else 0,
                'mean_time': metrics.mean,
                'std_dev': metrics.std_dev,
                'metrics': metrics.__dict__,
            }
        
        return analysis
    
    def _estimate_creator_probability(
        self,
        overall_metrics: ReactionTimeMetrics,
        responses: List[Dict[str, Any]],
        type_analysis: Dict[str, Dict[str, Any]]
    ) -> float:
        """
        Estimate probability that responder is the password creator.
        
        Factors:
        1. Reaction time compared to expected creator baseline
        2. Consistency of responses (lower CV = more likely creator)
        3. Pattern of correct vs incorrect responses
        4. Hesitation and correction patterns
        """
        probability = 0.5  # Start neutral
        
        # Factor 1: Speed advantage
        # Creators should be faster than baseline by ~30%
        if self.baseline:
            baseline_mean = self.baseline.get('mean', overall_metrics.mean)
            expected_creator_time = baseline_mean * (1 - self.creator_advantage)
            
            if overall_metrics.mean <= expected_creator_time:
                # Faster than expected - strong creator signal
                speed_factor = min(0.25, (expected_creator_time - overall_metrics.mean) / expected_creator_time * 0.5)
                probability += speed_factor
            else:
                # Slower than expected - attacker signal
                slow_factor = min(0.25, (overall_metrics.mean - expected_creator_time) / expected_creator_time * 0.5)
                probability -= slow_factor
        
        # Factor 2: Consistency (Low CV = likely creator)
        # Creators have learned muscle memory, attackers are more variable
        expected_cv = 0.25  # Expected coefficient of variation for creators
        if overall_metrics.coefficient_of_variation < expected_cv:
            probability += 0.15
        elif overall_metrics.coefficient_of_variation > expected_cv * 2:
            probability -= 0.15
        
        # Factor 3: Accuracy pattern
        correct_count = sum(1 for r in responses if r.get('is_correct', False))
        accuracy = correct_count / len(responses) if responses else 0
        
        if accuracy >= 0.9:
            probability += 0.1
        elif accuracy < 0.5:
            probability -= 0.2
        
        # Factor 4: Hesitation patterns
        total_hesitations = sum(r.get('hesitation_count', 0) for r in responses)
        avg_hesitations = total_hesitations / len(responses) if responses else 0
        
        if avg_hesitations < 0.5:
            # Low hesitation - creator signal
            probability += 0.05
        elif avg_hesitations > 2:
            # High hesitation - attacker signal
            probability -= 0.1
        
        # Factor 5: Correction patterns
        total_corrections = sum(r.get('correction_count', 0) for r in responses)
        avg_corrections = total_corrections / len(responses) if responses else 0
        
        if avg_corrections < 0.3:
            probability += 0.05
        elif avg_corrections > 1.5:
            probability -= 0.1
        
        # Clamp to valid probability range
        return max(0.0, min(1.0, probability))
    
    def _detect_suspicious_patterns(
        self, 
        responses: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Detect patterns indicative of an attacker.
        
        Suspicious patterns include:
        - Unnaturally consistent timing (robotic)
        - Deliberate delays followed by quick responses
        - Decreasing accuracy over time
        - Timing patterns that don't match challenge difficulty
        """
        patterns = []
        
        if len(responses) < 3:
            return patterns
        
        times = [r['reaction_time_ms'] for r in responses]
        
        # Check for robotic consistency (too perfect)
        if len(times) > 3:
            cv = statistics.stdev(times) / statistics.mean(times) if statistics.mean(times) > 0 else 0
            if cv < 0.05:  # Less than 5% variation is suspicious
                patterns.append({
                    'type': 'robotic_timing',
                    'severity': 'high',
                    'description': 'Unnaturally consistent response times',
                    'cv': cv,
                })
        
        # Check for deliberate delay pattern
        # (long pause followed by very quick responses)
        for i in range(1, len(times)):
            if times[i-1] > 2000 and times[i] < 500:
                patterns.append({
                    'type': 'delay_burst',
                    'severity': 'medium',
                    'description': 'Long delay followed by rapid response',
                    'position': i,
                })
        
        # Check for accuracy decline
        midpoint = len(responses) // 2
        first_half_correct = sum(1 for r in responses[:midpoint] if r.get('is_correct', False))
        second_half_correct = sum(1 for r in responses[midpoint:] if r.get('is_correct', False))
        
        first_half_accuracy = first_half_correct / midpoint if midpoint > 0 else 0
        second_half_accuracy = second_half_correct / (len(responses) - midpoint) if (len(responses) - midpoint) > 0 else 0
        
        if first_half_accuracy - second_half_accuracy > 0.3:
            patterns.append({
                'type': 'accuracy_decline',
                'severity': 'medium',
                'description': 'Significant decline in accuracy over session',
                'first_half': first_half_accuracy,
                'second_half': second_half_accuracy,
            })
        
        return patterns
    
    def _calculate_overall_confidence(
        self,
        responses: List[Dict[str, Any]],
        type_analysis: Dict[str, Dict[str, Any]]
    ) -> float:
        """Calculate overall confidence in the verification result."""
        if not responses:
            return 0.0
        
        # Base confidence from sample size
        sample_confidence = min(1.0, len(responses) / 10)
        
        # Confidence from accuracy
        correct_count = sum(1 for r in responses if r.get('is_correct', False))
        accuracy = correct_count / len(responses)
        accuracy_confidence = accuracy
        
        # Confidence from type diversity
        type_diversity = len(type_analysis) / 4  # 4 possible types
        
        # Combine factors
        confidence = (sample_confidence * 0.3 + 
                     accuracy_confidence * 0.5 + 
                     type_diversity * 0.2)
        
        return min(1.0, confidence)
    
    def update_baseline(
        self, 
        current_baseline: Dict[str, float],
        new_responses: List[Dict[str, Any]],
        learning_rate: float = 0.1
    ) -> Dict[str, float]:
        """
        Update baseline metrics with new data using exponential smoothing.
        
        Args:
            current_baseline: Current baseline metrics
            new_responses: New response data to incorporate
            learning_rate: How much to weight new data (0-1)
            
        Returns:
            Updated baseline metrics
        """
        new_times = [r['reaction_time_ms'] for r in new_responses if r.get('is_correct', False)]
        
        if not new_times:
            return current_baseline
        
        new_metrics = self._calculate_metrics(new_times)
        
        # Exponential smoothing
        updated = {
            'mean': (current_baseline.get('mean', new_metrics.mean) * (1 - learning_rate) +
                    new_metrics.mean * learning_rate),
            'std_dev': (current_baseline.get('std_dev', new_metrics.std_dev) * (1 - learning_rate) +
                       new_metrics.std_dev * learning_rate),
            'median': (current_baseline.get('median', new_metrics.median) * (1 - learning_rate) +
                      new_metrics.median * learning_rate),
        }
        
        return updated
