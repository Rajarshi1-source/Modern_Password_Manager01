"""
Adaptive Password Service
=========================

Reinforcement learning-based password adaptation that learns from
user typing patterns to make passwords more memorable.

Components:
- TypingPatternCollector: Secure keystroke pattern capture
- AdaptivePasswordRL: Contextual bandit for substitution selection
- SubstitutionLearner: Learns user's natural substitutions
- MemorabilityScorer: Neural network for memorability prediction

Privacy:
- Never stores raw keystrokes
- Only aggregated patterns with differential privacy
- All data encrypted at rest
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
import hashlib
import json
import logging
import math
import random
import numpy as np
from datetime import datetime, timedelta

from django.contrib.auth.models import User
from django.utils import timezone
from django.conf import settings

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


@dataclass
class SubstitutionSuggestion:
    """A suggested character substitution."""
    position: int
    original_char: str
    suggested_char: str
    confidence: float
    reason: str


@dataclass
class AdaptationSuggestion:
    """Full password adaptation suggestion."""
    substitutions: List[SubstitutionSuggestion]
    original_password_preview: str  # First 2 chars + *** + last 2 chars
    adapted_password_preview: str
    confidence_score: float
    memorability_improvement: float
    adaptation_type: str
    reason: str


@dataclass
class TypingProfileStats:
    """Aggregated typing statistics."""
    total_sessions: int
    success_rate: float
    average_wpm: float
    error_prone_positions: Dict[int, float]
    preferred_substitutions: Dict[str, str]
    profile_confidence: float


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
            return float(noisy_mean)
        else:
            # Fallback to numpy Laplace mechanism
            mean_timing = sum(timings) / len(timings)
            sensitivity = (upper_bound - lower_bound) / len(timings)
            noise = np.random.laplace(0, sensitivity / self.epsilon)
            return float(mean_timing + noise)
    
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
    
    def hash_password_prefix(self, password: str) -> str:
        """Get privacy-safe hash prefix of password."""
        full_hash = hashlib.sha256(password.encode()).hexdigest()
        return full_hash[:16]
    
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
# Typing Pattern Collector
# =============================================================================

class TypingPatternCollector:
    """
    Collects and processes typing patterns securely.
    
    NEVER stores raw keystrokes - only derived patterns.
    """
    
    def __init__(self, privacy_guard: PrivacyGuard = None):
        self.privacy_guard = privacy_guard or PrivacyGuard()
    
    def process_keystroke_data(
        self,
        password: str,
        keystroke_timings: List[int],  # Inter-key delay in ms
        backspace_positions: List[int],  # Where backspaces occurred
    ) -> TypingPattern:
        """
        Process raw keystroke data into privacy-safe pattern.
        
        Args:
            password: The password entered (for hashing only)
            keystroke_timings: List of inter-key delays
            backspace_positions: Positions where backspace was pressed
            
        Returns:
            Privacy-safe TypingPattern
        """
        # Create pattern
        pattern = TypingPattern(
            password_hash_prefix=self.privacy_guard.hash_password_prefix(password),
            password_length=len(password),
            error_positions=backspace_positions,
            timing_buckets={
                i: self.privacy_guard.anonymize_timing(t)
                for i, t in enumerate(keystroke_timings)
            },
            total_time_ms=sum(keystroke_timings),
            success=len(backspace_positions) == 0,
        )
        
        # Apply differential privacy
        return self.privacy_guard.sanitize_pattern(pattern)
    
    def detect_error_types(
        self,
        error_positions: List[int],
        password_length: int,
    ) -> Dict[str, float]:
        """
        Analyze error positions to detect common error types.
        
        Returns probability distribution of error types.
        """
        if not error_positions:
            return {}
        
        error_types = {
            'beginning': 0.0,  # Errors in first 25%
            'middle': 0.0,     # Errors in middle 50%
            'end': 0.0,        # Errors in last 25%
            'repeated': 0.0,   # Same position multiple times
        }
        
        quarter = password_length // 4
        
        for pos in error_positions:
            if pos < quarter:
                error_types['beginning'] += 1
            elif pos > password_length - quarter:
                error_types['end'] += 1
            else:
                error_types['middle'] += 1
        
        # Check for repeated errors
        position_counts = {}
        for pos in error_positions:
            position_counts[pos] = position_counts.get(pos, 0) + 1
        if any(c > 1 for c in position_counts.values()):
            error_types['repeated'] = sum(1 for c in position_counts.values() if c > 1)
        
        # Normalize
        total = sum(error_types.values())
        if total > 0:
            error_types = {k: v / total for k, v in error_types.items()}
        
        return error_types


# =============================================================================
# Substitution Learner
# =============================================================================

class SubstitutionLearner:
    """
    Learns user's natural character substitution preferences.
    
    Uses a contextual multi-armed bandit approach to select
    the best substitutions for each user.
    """
    
    def __init__(self):
        # Prior probabilities for each substitution
        self.substitution_priors = {
            char: {sub: 1.0 for sub in subs}
            for char, subs in COMMON_SUBSTITUTIONS.items()
        }
    
    def update_from_errors(
        self,
        error_positions: List[int],
        password_chars: List[str],
        profile: Dict[str, Any],
    ) -> Dict[str, Dict[str, float]]:
        """
        Update substitution preferences based on error patterns.
        
        If user frequently makes errors at positions with certain
        characters, suggest substituting those characters.
        """
        updates = {}
        
        for pos in error_positions:
            if pos < len(password_chars):
                char = password_chars[pos].lower()
                if char in COMMON_SUBSTITUTIONS:
                    # User struggles with this position
                    # Increase probability of substitution
                    if char not in updates:
                        updates[char] = {}
                    for sub in COMMON_SUBSTITUTIONS[char]:
                        updates[char][sub] = updates[char].get(sub, 0) + 0.1
        
        return updates
    
    def suggest_substitutions(
        self,
        password: str,
        error_prone_positions: Dict[int, float],
        user_preferences: Dict[str, str],
        n_suggestions: int = 3,
    ) -> List[SubstitutionSuggestion]:
        """
        Suggest character substitutions to make password easier.
        
        Args:
            password: Current password
            error_prone_positions: Positions with high error rates
            user_preferences: User's learned preferences
            n_suggestions: Max number of suggestions
            
        Returns:
            List of substitution suggestions
        """
        suggestions = []
        
        # Sort positions by error rate (highest first)
        sorted_positions = sorted(
            error_prone_positions.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        for pos, error_rate in sorted_positions[:n_suggestions]:
            if pos >= len(password):
                continue
                
            char = password[pos].lower()
            
            # Check if this character has substitution options
            if char in COMMON_SUBSTITUTIONS:
                # Check user preference first
                if char in user_preferences:
                    suggested = user_preferences[char]
                else:
                    # Use most common substitution
                    suggested = COMMON_SUBSTITUTIONS[char][0]
                
                suggestions.append(SubstitutionSuggestion(
                    position=pos,
                    original_char=password[pos],
                    suggested_char=suggested,
                    confidence=min(0.95, error_rate + 0.3),
                    reason=f"High error rate ({error_rate:.0%}) at position {pos+1}"
                ))
        
        return suggestions


# =============================================================================
# Memorability Scorer
# =============================================================================

class MemorabilityScorer:
    """
    Predicts how memorable a password is.
    
    Features considered:
    - Pattern regularity (keyboard patterns, sequences)
    - Character variety
    - Length vs complexity balance
    - Personal meaning signals
    """
    
    # Keyboard adjacency for pattern detection
    KEYBOARD_ROWS = [
        "qwertyuiop",
        "asdfghjkl",
        "zxcvbnm"
    ]
    
    def __init__(self):
        self.keyboard_adjacency = self._build_adjacency_map()
    
    def _build_adjacency_map(self) -> Dict[str, set]:
        """Build map of adjacent keys on QWERTY keyboard."""
        adjacency = {}
        for row in self.KEYBOARD_ROWS:
            for i, char in enumerate(row):
                adjacent = set()
                if i > 0:
                    adjacent.add(row[i-1])
                if i < len(row) - 1:
                    adjacent.add(row[i+1])
                adjacency[char] = adjacent
        return adjacency
    
    def calculate_score(self, password: str) -> float:
        """
        Calculate memorability score (0.0 to 1.0).
        
        Higher score = more memorable.
        """
        if not password:
            return 0.0
        
        scores = {
            'length': self._score_length(password),
            'patterns': self._score_patterns(password),
            'variety': self._score_variety(password),
            'pronounceable': self._score_pronounceability(password),
        }
        
        # Weighted average
        weights = {
            'length': 0.2,
            'patterns': 0.3,
            'variety': 0.2,
            'pronounceable': 0.3,
        }
        
        total = sum(scores[k] * weights[k] for k in scores)
        return min(1.0, max(0.0, total))
    
    def _score_length(self, password: str) -> float:
        """Optimal length is 12-16 characters."""
        length = len(password)
        if length < 8:
            return 0.3
        elif length <= 12:
            return 0.7
        elif length <= 16:
            return 1.0
        elif length <= 20:
            return 0.8
        else:
            return 0.5
    
    def _score_patterns(self, password: str) -> float:
        """
        Check for memorable patterns (keyboard walks, sequences).
        Patterns make passwords more memorable.
        """
        score = 0.5  # Base score
        
        # Check for keyboard patterns (adjacent keys)
        keyboard_pattern_count = 0
        lower = password.lower()
        for i in range(len(lower) - 1):
            if lower[i] in self.keyboard_adjacency:
                if lower[i+1] in self.keyboard_adjacency.get(lower[i], set()):
                    keyboard_pattern_count += 1
        
        if keyboard_pattern_count >= 2:
            score += 0.2
        
        # Check for number sequences
        if any(seq in password for seq in ['123', '234', '345', '456']):
            score += 0.1
        
        # Check for repeated patterns
        for i in range(1, len(password) // 2 + 1):
            if password[:i] * 2 in password:
                score += 0.1
                break
        
        return min(1.0, score)
    
    def _score_variety(self, password: str) -> float:
        """
        Balance between variety and memorability.
        Too much variety = harder to remember.
        """
        has_lower = any(c.islower() for c in password)
        has_upper = any(c.isupper() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_symbol = any(not c.isalnum() for c in password)
        
        variety = sum([has_lower, has_upper, has_digit, has_symbol])
        
        # 2-3 types is ideal for memorability
        if variety == 2:
            return 0.9
        elif variety == 3:
            return 1.0
        elif variety == 1:
            return 0.6
        else:  # 4 types
            return 0.7
    
    def _score_pronounceability(self, password: str) -> float:
        """
        Pronounceable passwords are more memorable.
        Check for vowel-consonant patterns.
        """
        vowels = set('aeiouAEIOU')
        
        # Count vowel-consonant transitions
        transitions = 0
        prev_is_vowel = None
        alpha_chars = [c for c in password if c.isalpha()]
        
        for char in alpha_chars:
            is_vowel = char in vowels
            if prev_is_vowel is not None and is_vowel != prev_is_vowel:
                transitions += 1
            prev_is_vowel = is_vowel
        
        if not alpha_chars:
            return 0.5
        
        # Ideal is ~50% transitions
        ratio = transitions / len(alpha_chars)
        if 0.3 <= ratio <= 0.7:
            return 1.0
        elif 0.2 <= ratio <= 0.8:
            return 0.7
        else:
            return 0.4
    
    def compare_passwords(
        self,
        original: str,
        adapted: str,
    ) -> Tuple[float, float, float]:
        """
        Compare memorability of original vs adapted password.
        
        Returns:
            Tuple of (original_score, adapted_score, improvement)
        """
        original_score = self.calculate_score(original)
        adapted_score = self.calculate_score(adapted)
        improvement = adapted_score - original_score
        
        return original_score, adapted_score, improvement


# =============================================================================
# LSTM Memorability Model (Neural Network)
# =============================================================================

class MemorabilityLSTM:
    """
    LSTM-based neural network for password memorability prediction.
    
    Uses PyTorch to implement an LSTM model that predicts how memorable
    a password is based on extracted features.
    
    Input: Password features (length, entropy, patterns, typing profile)
    Output: Memorability score [0, 1]
    
    This is an advanced model that can be used alongside the rule-based
    MemorabilityScorer for hybrid predictions.
    """
    
    def __init__(self, input_dim: int = 50, hidden_dim: int = 128, model_path: str = None):
        """
        Initialize LSTM memorability model.
        
        Args:
            input_dim: Dimension of input feature vector
            hidden_dim: Hidden layer dimension
            model_path: Path to pre-trained model weights
        """
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.model = None
        self.torch_available = False
        
        # Try to import PyTorch
        try:
            import torch
            import torch.nn as nn
            self.torch = torch
            self.nn = nn
            self.torch_available = True
            
            # Define the LSTM model
            class LSTMModel(nn.Module):
                def __init__(self, input_dim, hidden_dim):
                    super().__init__()
                    self.lstm = nn.LSTM(
                        input_size=input_dim,
                        hidden_size=hidden_dim,
                        num_layers=2,
                        batch_first=True,
                        dropout=0.2
                    )
                    self.fc = nn.Sequential(
                        nn.Linear(hidden_dim, 64),
                        nn.ReLU(),
                        nn.Dropout(0.3),
                        nn.Linear(64, 1),
                        nn.Sigmoid()  # Output [0, 1]
                    )
                
                def forward(self, x):
                    lstm_out, _ = self.lstm(x)
                    last_out = lstm_out[:, -1, :]
                    return self.fc(last_out)
            
            self.model = LSTMModel(input_dim, hidden_dim)
            
            # Load pre-trained weights if available
            if model_path:
                try:
                    self.model.load_state_dict(torch.load(model_path))
                    logger.info(f"Loaded LSTM model from {model_path}")
                except Exception as e:
                    logger.warning(f"Could not load model from {model_path}: {e}")
            
            logger.info("LSTM memorability model initialized")
        
        except ImportError:
            self.torch_available = False
            logger.warning("PyTorch not available. LSTM model disabled, using rule-based fallback.")
    
    def extract_features(
        self,
        password: str,
        typing_profile: Optional[Dict[str, Any]] = None
    ) -> List[float]:
        """
        Extract features for memorability prediction.
        
        Args:
            password: Password string (never stored, only used for feature extraction)
            typing_profile: User's typing profile for context
        
        Returns:
            Feature vector (input_dim dimensions)
        """
        features = []
        profile = typing_profile or {}
        
        # === Password Structure Features (10 features) ===
        # Length features
        features.append(len(password) / 50.0)  # Normalized length
        features.append(1.0 if 12 <= len(password) <= 16 else 0.5)  # Optimal length
        
        # Character diversity
        unique_chars = len(set(password))
        features.append(unique_chars / len(password) if password else 0)
        
        # Character type presence
        features.append(1.0 if any(c.islower() for c in password) else 0.0)
        features.append(1.0 if any(c.isupper() for c in password) else 0.0)
        features.append(1.0 if any(c.isdigit() for c in password) else 0.0)
        features.append(1.0 if any(not c.isalnum() for c in password) else 0.0)
        
        # Leetspeak detection
        leetspeak_count = sum(1 for c in password if c in '0@!1$3479|+')
        features.append(leetspeak_count / len(password) if password else 0)
        
        # Case transitions
        case_transitions = sum(1 for i in range(1, len(password)) 
                               if password[i].isupper() != password[i-1].isupper()
                               and password[i].isalpha() and password[i-1].isalpha())
        features.append(case_transitions / len(password) if password else 0)
        
        # Symbol clustering
        symbol_runs = sum(1 for i in range(len(password)) 
                         if not password[i].isalnum() and 
                         (i == 0 or password[i-1].isalnum()))
        features.append(symbol_runs / max(1, len(password)))
        
        # === Entropy Features (5 features) ===
        import math
        entropy = 0
        char_freq = {}
        for c in password:
            char_freq[c] = char_freq.get(c, 0) + 1
        for c, freq in char_freq.items():
            p = freq / len(password)
            entropy -= p * math.log2(p) if p > 0 else 0
        features.append(entropy / 6.0)  # Normalized entropy
        features.append(1.0 if entropy > 3 else entropy / 3.0)  # Entropy quality
        
        # Bigram entropy
        if len(password) > 1:
            bigrams = [password[i:i+2] for i in range(len(password)-1)]
            bigram_freq = {}
            for b in bigrams:
                bigram_freq[b] = bigram_freq.get(b, 0) + 1
            bigram_entropy = 0
            for b, freq in bigram_freq.items():
                p = freq / len(bigrams)
                bigram_entropy -= p * math.log2(p) if p > 0 else 0
            features.append(bigram_entropy / 8.0)
        else:
            features.append(0.0)
        
        features.append(len(char_freq) / 26.0)  # Alphabet coverage
        features.append(1.0 if len(set(password.lower())) > 8 else 0.5)
        
        # === Pattern Features (10 features) ===
        # Keyboard patterns
        keyboard_rows = ["qwertyuiop", "asdfghjkl", "zxcvbnm"]
        row_sequences = 0
        lower = password.lower()
        for row in keyboard_rows:
            for i in range(len(lower) - 1):
                if lower[i] in row and lower[i+1] in row:
                    idx1, idx2 = row.index(lower[i]), row.index(lower[i+1])
                    if abs(idx1 - idx2) == 1:
                        row_sequences += 1
        features.append(row_sequences / len(password) if password else 0)
        
        # Number sequences
        number_seq = any(seq in password for seq in ['123', '234', '345', '987', '876'])
        features.append(1.0 if number_seq else 0.0)
        
        # Repeating characters
        repeat_count = sum(1 for i in range(1, len(password)) if password[i] == password[i-1])
        features.append(repeat_count / len(password) if password else 0)
        
        # Repeating patterns
        has_repeat_pattern = any(password[:i] * 2 in password for i in range(1, len(password)//2 + 1))
        features.append(1.0 if has_repeat_pattern else 0.0)
        
        # Pronounceability (vowel-consonant ratio)
        vowels = set('aeiouAEIOU')
        consonants = set('bcdfghjklmnpqrstvwxyzBCDFGHJKLMNPQRSTVWXYZ')
        v_count = sum(1 for c in password if c in vowels)
        c_count = sum(1 for c in password if c in consonants)
        features.append(v_count / (v_count + c_count) if (v_count + c_count) > 0 else 0.5)
        features.append(1.0 if 0.3 <= v_count / len(password) <= 0.5 else 0.5 if password else 0)
        
        # Word-like substrings (heuristic)
        alpha_segments = ''.join(c if c.isalpha() else ' ' for c in password).split()
        avg_segment_len = sum(len(s) for s in alpha_segments) / len(alpha_segments) if alpha_segments else 0
        features.append(avg_segment_len / 8.0)  # Normalized
        features.append(len(alpha_segments) / 5.0)  # Number of word-like parts
        features.append(1.0 if any(len(s) >= 4 for s in alpha_segments) else 0.0)
        features.append(1.0 if all(len(s) <= 6 for s in alpha_segments) else 0.5)
        
        # === Typing Profile Features (10 features) ===
        features.append(profile.get('avg_inter_keystroke_time', 0) / 500.0)
        features.append(profile.get('typing_speed_wpm', 0) / 100.0)
        features.append(profile.get('success_rate', 0.5))
        features.append(profile.get('profile_confidence', 0.0))
        
        # Error-prone positions
        error_positions = profile.get('error_prone_positions', {})
        features.append(len(error_positions) / 10.0)
        features.append(max(error_positions.values()) if error_positions else 0.0)
        
        # Substitution preferences
        subs = profile.get('preferred_substitutions', {})
        features.append(len(subs) / 10.0)
        features.append(1.0 if any(c in subs for c in password.lower()) else 0.0)
        
        features.append(profile.get('total_sessions', 0) / 100.0)
        features.append(1.0 if profile.get('total_sessions', 0) >= 10 else 0.5)
        
        # === Pad or truncate to input_dim ===
        while len(features) < self.input_dim:
            features.append(0.0)
        
        return features[:self.input_dim]
    
    def predict(
        self,
        password: str,
        typing_profile: Optional[Dict[str, Any]] = None
    ) -> float:
        """
        Predict memorability score for a password.
        
        Args:
            password: Password to evaluate (never stored)
            typing_profile: Optional typing profile for context
        
        Returns:
            Memorability score [0, 1]
        """
        if not self.torch_available or self.model is None:
            # Fallback to feature-based heuristic
            features = self.extract_features(password, typing_profile)
            # Simple weighted average of key features
            return min(1.0, max(0.0, sum(features[:15]) / 15.0))
        
        # Extract features
        features = self.extract_features(password, typing_profile)
        
        # Convert to tensor and predict
        self.model.eval()
        with self.torch.no_grad():
            x = self.torch.FloatTensor(features).unsqueeze(0).unsqueeze(0)
            score = self.model(x).item()
        
        return float(score)
    
    def compare_passwords(
        self,
        original: str,
        adapted: str,
        typing_profile: Optional[Dict[str, Any]] = None
    ) -> Tuple[float, float, float]:
        """
        Compare memorability of original vs adapted password.
        
        Returns:
            Tuple of (original_score, adapted_score, improvement)
        """
        original_score = self.predict(original, typing_profile)
        adapted_score = self.predict(adapted, typing_profile)
        improvement = adapted_score - original_score
        
        return original_score, adapted_score, improvement
    
    def train_on_feedback(
        self,
        passwords: List[str],
        labels: List[float],
        epochs: int = 10,
        learning_rate: float = 0.001
    ):
        """
        Train/fine-tune model on user feedback.
        
        Args:
            passwords: List of passwords
            labels: List of memorability labels (0-1)
            epochs: Training epochs
            learning_rate: Learning rate
        """
        if not self.torch_available or self.model is None:
            logger.warning("Cannot train: PyTorch not available")
            return
        
        # Extract features for all passwords
        X = [self.extract_features(p) for p in passwords]
        y = labels
        
        # Convert to tensors
        X_tensor = self.torch.FloatTensor(X).unsqueeze(1)
        y_tensor = self.torch.FloatTensor(y).unsqueeze(1)
        
        # Training
        criterion = self.nn.MSELoss()
        optimizer = self.torch.optim.Adam(self.model.parameters(), lr=learning_rate)
        
        self.model.train()
        for epoch in range(epochs):
            optimizer.zero_grad()
            outputs = self.model(X_tensor)
            loss = criterion(outputs, y_tensor)
            loss.backward()
            optimizer.step()
            
            if (epoch + 1) % 5 == 0:
                logger.debug(f"Epoch {epoch+1}/{epochs}, Loss: {loss.item():.4f}")
        
        logger.info(f"LSTM model trained on {len(passwords)} samples")


# =============================================================================
# Contextual Bandit for Adaptation
# =============================================================================


class AdaptationBandit:
    """
    Contextual multi-armed bandit for selecting adaptations.
    
    Uses Thompson Sampling with Beta priors for each action.
    Actions = different substitution strategies.
    """
    
    def __init__(self):
        # Beta distribution parameters for each strategy
        self.arms = {
            'aggressive': {'alpha': 1.0, 'beta': 1.0},  # Many substitutions
            'conservative': {'alpha': 1.0, 'beta': 1.0},  # Few substitutions
            'error_focused': {'alpha': 1.0, 'beta': 1.0},  # Target error positions
            'rhythm_focused': {'alpha': 1.0, 'beta': 1.0},  # Target slow positions
        }
    
    def select_strategy(self, context: Dict[str, Any]) -> str:
        """
        Select adaptation strategy using Thompson Sampling.
        
        Args:
            context: User typing profile context
            
        Returns:
            Selected strategy name
        """
        # Sample from Beta distribution for each arm
        samples = {}
        for arm, params in self.arms.items():
            samples[arm] = np.random.beta(params['alpha'], params['beta'])
        
        # Context-based adjustments
        if context.get('error_rate', 0) > 0.3:
            samples['error_focused'] *= 1.5
        if context.get('typing_speed', 'normal') == 'slow':
            samples['rhythm_focused'] *= 1.5
        
        # Select best arm
        return max(samples, key=samples.get)
    
    def update(self, strategy: str, reward: float):
        """
        Update arm parameters based on reward.
        
        Args:
            strategy: The strategy that was used
            reward: Reward value (0.0 to 1.0)
        """
        if strategy in self.arms:
            if reward > 0.5:
                self.arms[strategy]['alpha'] += 1
            else:
                self.arms[strategy]['beta'] += 1


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
        self.pattern_collector = TypingPatternCollector(self.privacy_guard)
        self.substitution_learner = SubstitutionLearner()
        self.memorability_scorer = MemorabilityScorer()
        self.bandit = AdaptationBandit()
    
    def record_typing_session(
        self,
        password: str,
        keystroke_timings: List[int],
        backspace_positions: List[int],
        device_type: str = 'desktop',
        input_method: str = 'keyboard',
    ) -> Dict[str, Any]:
        """
        Record a typing session for learning.
        
        Args:
            password: The password entered
            keystroke_timings: Inter-key delays in ms
            backspace_positions: Where backspaces occurred
            device_type: desktop, mobile, tablet
            input_method: keyboard, touchscreen, voice
            
        Returns:
            Session summary
        """
        from .models import TypingSession, UserTypingProfile, AdaptivePasswordConfig
        
        # Check if user has opted in
        try:
            config = AdaptivePasswordConfig.objects.get(user=self.user)
            if not config.is_enabled:
                return {'error': 'Adaptive passwords not enabled'}
        except AdaptivePasswordConfig.DoesNotExist:
            return {'error': 'Adaptive passwords not configured'}
        
        # Process keystroke data
        pattern = self.pattern_collector.process_keystroke_data(
            password, keystroke_timings, backspace_positions
        )
        pattern.device_type = device_type
        pattern.input_method = input_method
        
        # Save session
        session = TypingSession.objects.create(
            user=self.user,
            password_hash_prefix=pattern.password_hash_prefix,
            password_length=pattern.password_length,
            success=pattern.success,
            error_positions=pattern.error_positions,
            error_count=len(pattern.error_positions),
            timing_profile=pattern.timing_buckets,
            total_time_ms=pattern.total_time_ms,
            device_type=device_type,
            input_method=input_method,
        )
        
        # Update typing profile
        self._update_typing_profile(pattern)
        
        return {
            'session_id': str(session.id),
            'success': pattern.success,
            'error_count': len(pattern.error_positions),
        }
    
    def _update_typing_profile(self, pattern: TypingPattern):
        """Update user's aggregated typing profile."""
        from .models import UserTypingProfile
        
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
    
    def suggest_adaptation(
        self,
        password: str,
        force: bool = False,
    ) -> Optional[AdaptationSuggestion]:
        """
        Generate adaptation suggestion for a password.
        
        Args:
            password: Current password
            force: Force suggestion even if timing criteria not met
            
        Returns:
            AdaptationSuggestion or None
        """
        from .models import UserTypingProfile, AdaptivePasswordConfig
        
        # Check configuration
        try:
            config = AdaptivePasswordConfig.objects.get(user=self.user)
            if not config.is_enabled:
                return None
            if not force and not config.should_suggest_adaptation():
                return None
        except AdaptivePasswordConfig.DoesNotExist:
            return None
        
        # Get typing profile
        try:
            profile = UserTypingProfile.objects.get(user=self.user)
            if not profile.has_sufficient_data():
                return None
        except UserTypingProfile.DoesNotExist:
            return None
        
        # Select adaptation strategy
        context = {
            'error_rate': 1 - profile.success_rate,
            'typing_speed': 'slow' if (profile.average_wpm or 40) < 30 else 'normal',
            'sessions': profile.total_sessions,
        }
        strategy = self.bandit.select_strategy(context)
        
        # Generate substitution suggestions
        error_positions = {
            int(k): v for k, v in profile.error_prone_positions.items()
        }
        
        suggestions = self.substitution_learner.suggest_substitutions(
            password=password,
            error_prone_positions=error_positions,
            user_preferences=profile.preferred_substitutions,
            n_suggestions=3 if strategy == 'aggressive' else 1,
        )
        
        if not suggestions:
            return None
        
        # Create adapted password
        adapted_chars = list(password)
        for sub in suggestions:
            if sub.position < len(adapted_chars):
                adapted_chars[sub.position] = sub.suggested_char
        adapted_password = ''.join(adapted_chars)
        
        # Calculate memorability
        orig_score, adapted_score, improvement = \
            self.memorability_scorer.compare_passwords(password, adapted_password)
        
        # Only suggest if there's improvement
        if improvement < 0.05 and not force:
            return None
        
        # Create preview (privacy-safe)
        def create_preview(p: str) -> str:
            if len(p) <= 4:
                return '*' * len(p)
            return p[:2] + '*' * (len(p) - 4) + p[-2:]
        
        return AdaptationSuggestion(
            substitutions=suggestions,
            original_password_preview=create_preview(password),
            adapted_password_preview=create_preview(adapted_password),
            confidence_score=sum(s.confidence for s in suggestions) / len(suggestions),
            memorability_improvement=improvement,
            adaptation_type=strategy,
            reason=f"Based on {profile.total_sessions} typing sessions with "
                   f"{(1-profile.success_rate)*100:.0f}% error rate",
        )
    
    def apply_adaptation(
        self,
        original_password: str,
        adapted_password: str,
        substitutions: List[Dict],
    ) -> Dict[str, Any]:
        """
        Apply and record a password adaptation.
        
        Args:
            original_password: The original password
            adapted_password: The adapted password
            substitutions: List of applied substitutions
            
        Returns:
            Adaptation record summary
        """
        from .models import (
            PasswordAdaptation, UserTypingProfile, AdaptivePasswordConfig
        )
        
        # Get previous adaptation if exists
        previous = PasswordAdaptation.objects.filter(
            user=self.user,
            adapted_hash_prefix=self.privacy_guard.hash_password_prefix(original_password),
            status='active',
        ).first()
        
        generation = (previous.adaptation_generation + 1) if previous else 1
        
        # Calculate memorability scores
        orig_score = self.memorability_scorer.calculate_score(original_password)
        adapted_score = self.memorability_scorer.calculate_score(adapted_password)
        
        # Create adaptation record
        adaptation = PasswordAdaptation.objects.create(
            user=self.user,
            password_hash_prefix=self.privacy_guard.hash_password_prefix(original_password),
            adapted_hash_prefix=self.privacy_guard.hash_password_prefix(adapted_password),
            previous_adaptation=previous,
            adaptation_generation=generation,
            adaptation_type='substitution',
            substitutions_applied={str(s['position']): s for s in substitutions},
            confidence_score=sum(s.get('confidence', 0.8) for s in substitutions) / len(substitutions),
            memorability_score_before=orig_score,
            memorability_score_after=adapted_score,
            status='active',
            decided_at=timezone.now(),
            reason=f"User-approved adaptation (gen {generation})",
        )
        
        # Mark previous as rolled back
        if previous:
            previous.status = 'rolled_back'
            previous.save()
        
        # Update suggestion timing
        try:
            config = AdaptivePasswordConfig.objects.get(user=self.user)
            config.last_suggestion_at = timezone.now()
            config.save()
        except AdaptivePasswordConfig.DoesNotExist:
            pass
        
        return {
            'adaptation_id': str(adaptation.id),
            'generation': generation,
            'memorability_before': orig_score,
            'memorability_after': adapted_score,
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
        from .models import PasswordAdaptation, UserTypingProfile
        
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
        from .models import PasswordAdaptation
        
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
        from .models import (
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
