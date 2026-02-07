"""
Stroop Effect Service
=====================

Implements Stroop-like interference tests for cognitive verification.
The Stroop effect reveals implicit associations that genuine password
creators have but attackers lack.

@author Password Manager Team
@created 2026-02-07
"""

import random
from typing import Dict, List, Any, Tuple


class StroopEffectService:
    """
    Service for generating and evaluating Stroop-effect challenges.
    
    The Stroop effect is a cognitive phenomenon where interference occurs
    when a word's meaning conflicts with its visual presentation.
    
    For password verification:
    - Show password characters in conflicting contexts
    - Measure interference patterns in response times
    - Creators show different interference than attackers due to
      their implicit associations with password elements
    """
    
    # Color palette for Stroop tests
    COLORS = {
        'red': '#FF4444',
        'blue': '#4444FF',
        'green': '#44FF44',
        'yellow': '#FFFF44',
        'purple': '#AA44AA',
        'orange': '#FFAA44',
    }
    
    # Number words that conflict with digits
    NUMBER_WORDS = ['ZERO', 'ONE', 'TWO', 'THREE', 'FOUR', 
                    'FIVE', 'SIX', 'SEVEN', 'EIGHT', 'NINE']
    
    # Semantic categories for character classification
    CHAR_CATEGORIES = {
        'digits': set('0123456789'),
        'lowercase': set('abcdefghijklmnopqrstuvwxyz'),
        'uppercase': set('ABCDEFGHIJKLMNOPQRSTUVWXYZ'),
        'symbols': set('!@#$%^&*()-_=+[]{}|;:,.<>?/~`'),
    }
    
    def __init__(self, difficulty: str = 'medium'):
        """
        Initialize Stroop service.
        
        Args:
            difficulty: Challenge difficulty level
        """
        self.difficulty = difficulty
        self.interference_levels = {
            'easy': 'low',
            'medium': 'medium', 
            'hard': 'high'
        }
    
    def generate_stroop_stimulus(
        self,
        password: str,
        char_index: int
    ) -> Dict[str, Any]:
        """
        Generate a Stroop stimulus for a password character.
        
        Args:
            password: The password being tested
            char_index: Index of the target character
            
        Returns:
            Stimulus configuration dictionary
        """
        target_char = password[char_index]
        interference_level = self.interference_levels.get(self.difficulty, 'medium')
        
        # Determine stimulus type based on character
        if target_char.isdigit():
            stimulus = self._generate_digit_stroop(target_char, interference_level)
        elif target_char.isalpha():
            stimulus = self._generate_letter_stroop(target_char, interference_level)
        else:
            stimulus = self._generate_symbol_stroop(target_char, interference_level)
        
        # Add metadata
        stimulus['target_char'] = target_char
        stimulus['char_position'] = char_index
        stimulus['difficulty'] = self.difficulty
        stimulus['interference_level'] = interference_level
        
        return stimulus
    
    def _generate_digit_stroop(
        self,
        digit: str,
        interference: str
    ) -> Dict[str, Any]:
        """
        Generate Stroop stimulus for a digit.
        
        Shows a number word in a color that may conflict with
        the digit's position or other semantic meaning.
        """
        digit_int = int(digit)
        
        if interference == 'high':
            # Maximum interference: wrong number word
            other_digits = [i for i in range(10) if i != digit_int]
            display_word = self.NUMBER_WORDS[random.choice(other_digits)]
            display_color = random.choice(list(self.COLORS.keys()))
        elif interference == 'medium':
            # Some interference: correct number but wrong color
            display_word = self.NUMBER_WORDS[digit_int]
            # Use color that conflicts (if possible)
            color_words = ['RED', 'BLUE', 'GREEN', 'YELLOW', 'PURPLE', 'ORANGE']
            if display_word in color_words:
                available = [c for c in self.COLORS.keys() if c.upper() != display_word]
                display_color = random.choice(available)
            else:
                display_color = random.choice(list(self.COLORS.keys()))
        else:
            # Low interference: congruent
            display_word = self.NUMBER_WORDS[digit_int]
            display_color = random.choice(list(self.COLORS.keys()))
        
        return {
            'type': 'digit_stroop',
            'display_word': display_word,
            'display_color': display_color,
            'color_hex': self.COLORS[display_color],
            'instruction': 'Identify the password digit after viewing',
        }
    
    def _generate_letter_stroop(
        self,
        letter: str,
        interference: str
    ) -> Dict[str, Any]:
        """
        Generate Stroop stimulus for a letter.
        
        Shows color words with conflicting text colors.
        """
        color_names = list(self.COLORS.keys())
        
        if interference == 'high':
            # Incongruent: color word in different color
            color_word = random.choice(color_names).upper()
            available_colors = [c for c in color_names if c.upper() != color_word]
            display_color = random.choice(available_colors)
        elif interference == 'medium':
            # Partially congruent
            color_word = random.choice(color_names).upper()
            display_color = random.choice(color_names)
        else:
            # Congruent
            display_color = random.choice(color_names)
            color_word = display_color.upper()
        
        return {
            'type': 'letter_stroop',
            'display_word': color_word,
            'display_color': display_color,
            'color_hex': self.COLORS[display_color],
            'target_case': 'upper' if letter.isupper() else 'lower',
            'instruction': 'After viewing the colored word, identify the password letter',
        }
    
    def _generate_symbol_stroop(
        self,
        symbol: str,
        interference: str
    ) -> Dict[str, Any]:
        """
        Generate Stroop stimulus for a symbol.
        
        Uses visual noise and color to create interference.
        """
        # For symbols, use visual distraction
        distractor_symbols = random.sample(list(self.CHAR_CATEGORIES['symbols']), 5)
        
        if interference == 'high':
            # Many distractors, quick flash
            display_time = 500
        elif interference == 'medium':
            display_time = 750
        else:
            display_time = 1000
        
        display_color = random.choice(list(self.COLORS.keys()))
        
        return {
            'type': 'symbol_stroop',
            'display_word': ''.join(distractor_symbols),
            'display_color': display_color,
            'color_hex': self.COLORS[display_color],
            'flash_duration_ms': display_time,
            'instruction': 'Identify the password symbol from the display',
        }
    
    def evaluate_stroop_response(
        self,
        stimulus: Dict[str, Any],
        response: str,
        response_time_ms: int,
        baseline_time: float = None
    ) -> Dict[str, Any]:
        """
        Evaluate a Stroop response for implicit memory indicators.
        
        Args:
            stimulus: The stimulus that was presented
            response: User's response
            response_time_ms: Response time in milliseconds
            baseline_time: User's baseline reaction time (optional)
            
        Returns:
            Evaluation results
        """
        target = stimulus['target_char']
        is_correct = response == target
        
        # Calculate interference effect
        interference_level = stimulus.get('interference_level', 'medium')
        expected_increase = {
            'low': 0,
            'medium': 150,  # 150ms increase expected
            'high': 300,    # 300ms increase expected
        }
        
        expected_time = (baseline_time or 1000) + expected_increase.get(interference_level, 150)
        
        # Creators handle interference differently
        # They show more interference for semantically related content
        time_deviation = response_time_ms - expected_time
        
        # Calculate stroop effect magnitude
        stroop_effect = response_time_ms - (baseline_time or 1000)
        
        # Pattern analysis
        pattern_score = self._analyze_stroop_pattern(
            stimulus, response_time_ms, is_correct, baseline_time
        )
        
        return {
            'is_correct': is_correct,
            'response_time_ms': response_time_ms,
            'expected_time': expected_time,
            'time_deviation': time_deviation,
            'stroop_effect': stroop_effect,
            'interference_level': interference_level,
            'pattern_score': pattern_score,
            'creator_indicator': pattern_score > 0.5,
        }
    
    def _analyze_stroop_pattern(
        self,
        stimulus: Dict[str, Any],
        response_time: int,
        is_correct: bool,
        baseline: float = None
    ) -> float:
        """
        Analyze if Stroop response pattern matches creator profile.
        
        Returns score from 0-1 indicating likelihood of creator.
        """
        score = 0.5  # Start neutral
        
        base = baseline or 1000
        interference = stimulus.get('interference_level', 'medium')
        
        # Expected behaviors for creators:
        # 1. Show appropriate interference (some slowdown, not too much)
        if interference == 'high':
            expected_range = (base + 200, base + 500)
        elif interference == 'medium':
            expected_range = (base + 100, base + 300)
        else:
            expected_range = (base, base + 150)
        
        if expected_range[0] <= response_time <= expected_range[1]:
            score += 0.2
        elif response_time > expected_range[1]:
            # Too slow - could be attacker deliberating
            score -= 0.1
        elif response_time < expected_range[0]:
            # Very fast - either expert or robotic
            if response_time < base * 0.7:
                score -= 0.15  # Suspiciously fast
            else:
                score += 0.1  # Fast but natural
        
        # Correctness under interference
        if is_correct:
            if interference == 'high':
                score += 0.15  # Hard to be correct under high interference
            else:
                score += 0.1
        else:
            if interference == 'high':
                score += 0.05  # Errors expected under high interference
            else:
                score -= 0.1  # Shouldn't make errors on easy ones
        
        return max(0.0, min(1.0, score))
    
    def get_display_config(self) -> Dict[str, Any]:
        """Get configuration for Stroop display in frontend."""
        return {
            'colors': self.COLORS,
            'animation_duration_ms': {
                'easy': 1000,
                'medium': 750,
                'hard': 500,
            }.get(self.difficulty, 750),
            'mask_duration_ms': 200,
            'response_timeout_ms': 5000,
            'font_family': 'monospace',
            'font_size': '48px',
        }
