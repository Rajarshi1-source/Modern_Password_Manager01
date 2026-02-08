"""
Pattern Analysis Engine
========================

ML-based password pattern analysis for predictive expiration.
Extracts structural fingerprints, detects common mutations,
and predicts attacker guessing strategies.
"""

import hashlib
import re
import logging
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from collections import Counter
import math

logger = logging.getLogger(__name__)


@dataclass
class PatternFingerprint:
    """Represents a password's structural fingerprint."""
    structure_hash: bytes
    char_class_sequence: str  # e.g., "LLLDDDSS" (Lower, Digit, Symbol)
    length: int
    entropy_estimate: float
    has_dictionary_base: bool
    detected_base_words: List[str]
    mutations: List[str]
    keyboard_patterns: List[str]
    date_patterns: List[str]


@dataclass
class MutationType:
    """Represents a detected password mutation."""
    original: str
    mutated: str
    mutation_type: str  # e.g., "leet", "case", "append", "prepend"
    confidence: float


@dataclass
class LikelyGuess:
    """Represents a likely attacker guess attempt."""
    guess_pattern: str
    probability: float
    attack_type: str  # e.g., "dictionary", "hybrid", "rule-based"


class PatternAnalysisEngine:
    """
    ML-based password pattern analysis engine.
    
    Analyzes passwords to extract structural patterns, detect
    common mutations, and predict vulnerability to attacks.
    """
    
    # Common leet speak substitutions
    LEET_MAPPINGS = {
        'a': ['@', '4'],
        'e': ['3'],
        'i': ['1', '!'],
        'o': ['0'],
        's': ['$', '5'],
        't': ['7'],
        'l': ['1'],
        'b': ['8'],
        'g': ['9'],
    }
    
    # Reverse leet mappings for detection
    REVERSE_LEET = {}
    for letter, subs in LEET_MAPPINGS.items():
        for sub in subs:
            REVERSE_LEET[sub] = letter
    
    # Common keyboard patterns
    KEYBOARD_PATTERNS = [
        'qwerty', 'qwertyuiop', 'asdf', 'asdfgh', 'zxcvbn',
        '123456', '12345678', '1234567890',
        'qazwsx', 'qweasd', '1qaz2wsx',
        'password', 'pass', 'passwd',
    ]
    
    # Common base words (top dictionary words used in passwords)
    COMMON_BASE_WORDS = [
        'password', 'letmein', 'welcome', 'monkey', 'dragon',
        'master', 'login', 'admin', 'princess', 'sunshine',
        'shadow', 'football', 'baseball', 'soccer', 'hockey',
        'summer', 'winter', 'spring', 'autumn', 'love',
        'hello', 'secret', 'access', 'trustno', 'computer',
    ]
    
    # Date patterns regex
    DATE_PATTERNS = [
        r'\d{4}$',           # Year at end (2024)
        r'\d{2}\d{2}\d{2,4}',  # MMDDYY or MMDDYYYY
        r'\d{4}\d{2}\d{2}',   # YYYYMMDD
        r'19\d{2}',           # 19XX year
        r'20\d{2}',           # 20XX year
    ]
    
    def __init__(self):
        """Initialize the pattern analysis engine."""
        self.common_base_words_set = set(self.COMMON_BASE_WORDS)
        self.keyboard_patterns_set = set(self.KEYBOARD_PATTERNS)
    
    def extract_structure_fingerprint(self, password: str) -> bytes:
        """
        Extract a structural fingerprint from a password.
        
        The fingerprint represents the character class pattern
        without storing the actual password content.
        
        Args:
            password: The password to analyze
            
        Returns:
            A hashed fingerprint of the password structure
        """
        # Create character class sequence
        char_classes = self._get_char_class_sequence(password)
        
        # Add length bucket
        length_bucket = self._get_length_bucket(len(password))
        
        # Combine into fingerprint
        fingerprint_data = f"{char_classes}:{length_bucket}"
        
        return hashlib.sha256(fingerprint_data.encode()).digest()
    
    def analyze_password(self, password: str) -> PatternFingerprint:
        """
        Perform comprehensive pattern analysis on a password.
        
        Args:
            password: The password to analyze
            
        Returns:
            PatternFingerprint with detailed analysis results
        """
        # Extract character class sequence
        char_class_seq = self._get_char_class_sequence(password)
        
        # Calculate entropy
        entropy = self._calculate_entropy(password)
        
        # Detect base words
        base_words = self._detect_base_words(password)
        has_dictionary_base = len(base_words) > 0
        
        # Detect mutations
        mutations = self._detect_mutations(password)
        
        # Detect keyboard patterns
        keyboard_patterns = self._detect_keyboard_patterns(password)
        
        # Detect date patterns
        date_patterns = self._detect_date_patterns(password)
        
        # Generate structure hash
        structure_hash = self.extract_structure_fingerprint(password)
        
        return PatternFingerprint(
            structure_hash=structure_hash,
            char_class_sequence=char_class_seq,
            length=len(password),
            entropy_estimate=entropy,
            has_dictionary_base=has_dictionary_base,
            detected_base_words=base_words,
            mutations=[m.mutation_type for m in mutations],
            keyboard_patterns=keyboard_patterns,
            date_patterns=date_patterns,
        )
    
    def calculate_similarity_score(
        self,
        fingerprint1: bytes,
        fingerprint2: bytes
    ) -> float:
        """
        Calculate similarity between two password fingerprints.
        
        Uses Hamming distance on the fingerprint bytes.
        
        Args:
            fingerprint1: First fingerprint
            fingerprint2: Second fingerprint
            
        Returns:
            Similarity score between 0 and 1
        """
        if len(fingerprint1) != len(fingerprint2):
            return 0.0
        
        # Count matching bytes
        matching = sum(
            1 for a, b in zip(fingerprint1, fingerprint2) if a == b
        )
        
        return matching / len(fingerprint1)
    
    def detect_common_mutations(self, password: str) -> List[MutationType]:
        """
        Detect common password mutations.
        
        Identifies leet speak, case variations, and common
        append/prepend patterns.
        
        Args:
            password: The password to analyze
            
        Returns:
            List of detected mutations
        """
        return self._detect_mutations(password)
    
    def identify_base_word_patterns(self, password: str) -> List[str]:
        """
        Identify dictionary words that may be the base of the password.
        
        Args:
            password: The password to analyze
            
        Returns:
            List of potential base words
        """
        return self._detect_base_words(password)
    
    def predict_attacker_guesses(
        self,
        password: str,
        max_guesses: int = 10
    ) -> List[LikelyGuess]:
        """
        Predict likely attacker guessing attempts for this password.
        
        Analyzes the password structure to predict what attack
        patterns would most likely succeed.
        
        Args:
            password: The password to analyze
            max_guesses: Maximum number of guesses to return
            
        Returns:
            List of likely guesses with probabilities
        """
        guesses = []
        analysis = self.analyze_password(password)
        
        # If has dictionary base, predict dictionary + rule attacks
        if analysis.has_dictionary_base:
            for word in analysis.detected_base_words[:3]:
                # Pure dictionary attack
                guesses.append(LikelyGuess(
                    guess_pattern=f"dictionary:{word}",
                    probability=0.7,
                    attack_type="dictionary"
                ))
                
                # Dictionary + common append patterns
                guesses.append(LikelyGuess(
                    guess_pattern=f"hybrid:{word}+digits",
                    probability=0.5,
                    attack_type="hybrid"
                ))
        
        # If has keyboard patterns
        for pattern in analysis.keyboard_patterns[:2]:
            guesses.append(LikelyGuess(
                guess_pattern=f"keyboard:{pattern}",
                probability=0.6,
                attack_type="pattern"
            ))
        
        # If has date patterns
        for pattern in analysis.date_patterns[:2]:
            guesses.append(LikelyGuess(
                guess_pattern=f"date_pattern",
                probability=0.4,
                attack_type="rule-based"
            ))
        
        # If has leet mutations
        if 'leet' in analysis.mutations:
            guesses.append(LikelyGuess(
                guess_pattern="leet_substitution",
                probability=0.6,
                attack_type="rule-based"
            ))
        
        # Sort by probability and limit
        guesses.sort(key=lambda x: x.probability, reverse=True)
        return guesses[:max_guesses]
    
    def get_char_class_distribution(
        self,
        password: str
    ) -> Dict[str, float]:
        """
        Calculate the distribution of character classes in a password.
        
        Args:
            password: The password to analyze
            
        Returns:
            Dictionary with percentages for each character class
        """
        if not password:
            return {}
        
        counts = Counter()
        for char in password:
            counts[self._classify_char(char)] += 1
        
        total = len(password)
        return {k: v / total for k, v in counts.items()}
    
    def _get_char_class_sequence(self, password: str) -> str:
        """Get the character class sequence for a password."""
        return ''.join(self._classify_char(c) for c in password)
    
    def _classify_char(self, char: str) -> str:
        """Classify a single character into a class."""
        if char.islower():
            return 'L'  # Lowercase
        elif char.isupper():
            return 'U'  # Uppercase
        elif char.isdigit():
            return 'D'  # Digit
        else:
            return 'S'  # Symbol
    
    def _get_length_bucket(self, length: int) -> str:
        """Get a length bucket for fingerprinting."""
        if length <= 6:
            return 'very_short'
        elif length <= 8:
            return 'short'
        elif length <= 12:
            return 'medium'
        elif length <= 16:
            return 'long'
        else:
            return 'very_long'
    
    def _calculate_entropy(self, password: str) -> float:
        """Calculate Shannon entropy of the password."""
        if not password:
            return 0.0
        
        # Character frequency
        freq = Counter(password)
        length = len(password)
        
        # Calculate entropy
        entropy = 0.0
        for count in freq.values():
            if count > 0:
                p = count / length
                entropy -= p * math.log2(p)
        
        # Scale by length for bits of entropy
        return entropy * length
    
    def _detect_base_words(self, password: str) -> List[str]:
        """Detect dictionary base words in the password."""
        detected = []
        password_lower = password.lower()
        
        # Normalize leet speak
        normalized = self._normalize_leet(password_lower)
        
        # Check for common base words
        for word in self.COMMON_BASE_WORDS:
            if word in password_lower or word in normalized:
                detected.append(word)
        
        return detected
    
    def _normalize_leet(self, text: str) -> str:
        """Convert leet speak back to normal letters."""
        result = []
        for char in text:
            if char in self.REVERSE_LEET:
                result.append(self.REVERSE_LEET[char])
            else:
                result.append(char)
        return ''.join(result)
    
    def _detect_mutations(self, password: str) -> List[MutationType]:
        """Detect common password mutations."""
        mutations = []
        
        # Check for leet speak
        for char in password:
            if char in self.REVERSE_LEET:
                mutations.append(MutationType(
                    original=self.REVERSE_LEET[char],
                    mutated=char,
                    mutation_type='leet',
                    confidence=0.9
                ))
                break  # Only add once
        
        # Check for common append patterns (numbers at end)
        if re.search(r'\d{1,4}$', password):
            mutations.append(MutationType(
                original='',
                mutated='digits',
                mutation_type='append_digits',
                confidence=0.8
            ))
        
        # Check for common prepend patterns
        if re.search(r'^\d{1,4}', password):
            mutations.append(MutationType(
                original='',
                mutated='digits',
                mutation_type='prepend_digits',
                confidence=0.7
            ))
        
        # Check for capitalization patterns (first letter caps)
        if password and password[0].isupper() and password[1:].islower():
            mutations.append(MutationType(
                original='all_lower',
                mutated='title_case',
                mutation_type='capitalize_first',
                confidence=0.85
            ))
        
        return mutations
    
    def _detect_keyboard_patterns(self, password: str) -> List[str]:
        """Detect keyboard walk patterns."""
        detected = []
        password_lower = password.lower()
        
        for pattern in self.KEYBOARD_PATTERNS:
            if pattern in password_lower:
                detected.append(pattern)
        
        return detected
    
    def _detect_date_patterns(self, password: str) -> List[str]:
        """Detect date patterns in the password."""
        detected = []
        
        for pattern in self.DATE_PATTERNS:
            if re.search(pattern, password):
                detected.append(pattern)
        
        return detected


# Singleton instance
_pattern_engine: Optional[PatternAnalysisEngine] = None


def get_pattern_analysis_engine() -> PatternAnalysisEngine:
    """Get the singleton pattern analysis engine instance."""
    global _pattern_engine
    if _pattern_engine is None:
        _pattern_engine = PatternAnalysisEngine()
    return _pattern_engine
