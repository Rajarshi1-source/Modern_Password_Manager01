"""
Priming Test Service
====================

Implements semantic priming tests for cognitive verification.
Priming effects reveal implicit memory traces that genuine password
creators exhibit but attackers cannot replicate.

@author Password Manager Team
@created 2026-02-07
"""

import random
from typing import Dict, List, Any, Optional


class PrimingTestService:
    """
    Service for generating and evaluating priming tests.
    
    Priming is a cognitive phenomenon where exposure to a stimulus
    influences response to a subsequent stimulus. Password creators
    show stronger priming effects for their own password elements
    because of repeated exposure during creation and use.
    
    Test mechanism:
    1. Flash a prime stimulus briefly (password elements)
    2. Present a target for recognition
    3. Measure response time - primed responses are faster
    4. Compare to non-primed baseline
    """
    
    # Priming durations by difficulty (milliseconds)
    PRIME_DURATIONS = {
        'easy': 250,     # Clear priming
        'medium': 150,   # Moderate priming
        'hard': 75,      # Subliminal-like priming
    }
    
    # Mask durations (inter-stimulus interval)
    MASK_DURATIONS = {
        'easy': 300,
        'medium': 200,
        'hard': 100,
    }
    
    def __init__(self, difficulty: str = 'medium'):
        """
        Initialize priming service.
        
        Args:
            difficulty: Challenge difficulty level
        """
        self.difficulty = difficulty
        self.prime_duration = self.PRIME_DURATIONS.get(difficulty, 150)
        self.mask_duration = self.MASK_DURATIONS.get(difficulty, 200)
    
    def generate_priming_challenge(
        self,
        password: str,
        target_index: int = None
    ) -> Dict[str, Any]:
        """
        Generate a priming challenge for password verification.
        
        Args:
            password: The password being tested
            target_index: Optional specific index to target
            
        Returns:
            Challenge configuration dictionary
        """
        if target_index is None:
            target_index = random.randint(0, len(password) - 1)
        
        target_char = password[target_index]
        
        # Determine prime type
        prime_type = self._select_prime_type(password, target_index)
        
        # Generate prime stimulus
        prime_stimulus = self._generate_prime(password, target_index, prime_type)
        
        # Generate target options
        target_options = self._generate_target_options(target_char)
        
        return {
            'challenge_type': 'priming',
            'prime_type': prime_type,
            'prime_stimulus': prime_stimulus,
            'prime_duration_ms': self.prime_duration,
            'mask_duration_ms': self.mask_duration,
            'target_char': target_char,
            'target_index': target_index,
            'target_options': target_options,
            'difficulty': self.difficulty,
            'display_config': self._get_display_config(),
        }
    
    def _select_prime_type(self, password: str, target_index: int) -> str:
        """Select the type of priming to use."""
        types = ['adjacent', 'fragment', 'semantic', 'masked']
        
        if self.difficulty == 'easy':
            # Use clearer priming types
            return random.choice(['adjacent', 'fragment'])
        elif self.difficulty == 'hard':
            # Use subtler priming
            return random.choice(['semantic', 'masked'])
        else:
            return random.choice(types)
    
    def _generate_prime(
        self,
        password: str,
        target_index: int,
        prime_type: str
    ) -> Dict[str, Any]:
        """Generate prime stimulus based on type."""
        if prime_type == 'adjacent':
            return self._generate_adjacent_prime(password, target_index)
        elif prime_type == 'fragment':
            return self._generate_fragment_prime(password, target_index)
        elif prime_type == 'semantic':
            return self._generate_semantic_prime(password, target_index)
        else:  # masked
            return self._generate_masked_prime(password, target_index)
    
    def _generate_adjacent_prime(
        self,
        password: str,
        target_index: int
    ) -> Dict[str, Any]:
        """
        Generate prime using adjacent characters.
        
        Shows characters immediately before/after the target,
        which primes recognition through sequential memory.
        """
        start = max(0, target_index - 2)
        end = min(len(password), target_index + 3)
        
        # Create prime with target position masked
        prime_chars = list(password[start:end])
        target_pos_in_prime = target_index - start
        prime_chars[target_pos_in_prime] = '?'
        
        return {
            'type': 'adjacent',
            'text': ''.join(prime_chars),
            'highlight_position': target_pos_in_prime,
            'context': f'characters at positions {start}-{end}',
        }
    
    def _generate_fragment_prime(
        self,
        password: str,
        target_index: int
    ) -> Dict[str, Any]:
        """
        Generate prime using a password fragment.
        
        Shows a random fragment from the password to activate
        related memory traces.
        """
        # Get a fragment that doesn't include the target
        fragment_size = min(4, len(password) // 2)
        
        # Find a suitable position for the fragment
        possible_starts = []
        for i in range(len(password) - fragment_size + 1):
            if not (i <= target_index < i + fragment_size):
                possible_starts.append(i)
        
        if possible_starts:
            start = random.choice(possible_starts)
            fragment = password[start:start + fragment_size]
        else:
            # Fallback to adjacent prime
            return self._generate_adjacent_prime(password, target_index)
        
        return {
            'type': 'fragment',
            'text': fragment,
            'fragment_position': start,
            'context': f'fragment from position {start}',
        }
    
    def _generate_semantic_prime(
        self,
        password: str,
        target_index: int
    ) -> Dict[str, Any]:
        """
        Generate semantic prime based on character type.
        
        Uses semantic category (digit, letter, symbol) to prime
        recognition without showing actual password content.
        """
        target = password[target_index]
        
        if target.isdigit():
            prime_text = random.choice(['123', '###', 'NUM'])
            category = 'number'
        elif target.islower():
            prime_text = random.choice(['abc', 'word', 'α'])
            category = 'lowercase letter'
        elif target.isupper():
            prime_text = random.choice(['ABC', 'WORD', 'Α'])
            category = 'uppercase letter'
        else:
            prime_text = random.choice(['!@#', '***', '⚡'])
            category = 'symbol'
        
        return {
            'type': 'semantic',
            'text': prime_text,
            'category': category,
            'context': f'semantic hint: {category}',
        }
    
    def _generate_masked_prime(
        self,
        password: str,
        target_index: int
    ) -> Dict[str, Any]:
        """
        Generate masked (subliminal-like) prime.
        
        Shows the actual target character very briefly,
        creating unconscious priming.
        """
        target = password[target_index]
        
        # Add visual masks around the target
        mask_chars = ['#', '█', '▓', '░']
        pre_mask = ''.join(random.choices(mask_chars, k=3))
        post_mask = ''.join(random.choices(mask_chars, k=3))
        
        return {
            'type': 'masked',
            'text': f'{pre_mask}{target}{post_mask}',
            'target_in_prime': True,
            'mask_strength': self.difficulty,
            'context': 'masked prime',
        }
    
    def _generate_target_options(self, target_char: str) -> List[str]:
        """Generate multiple choice options for the target."""
        options = [target_char]
        
        # Add similar-looking characters
        confusables = self._get_confusable_chars(target_char)
        options.extend(confusables[:3])
        
        # Pad with random chars if needed
        while len(options) < 4:
            if target_char.isdigit():
                char = str(random.randint(0, 9))
            elif target_char.isalpha():
                chars = 'abcdefghijklmnopqrstuvwxyz'
                if target_char.isupper():
                    chars = chars.upper()
                char = random.choice(chars)
            else:
                char = random.choice('!@#$%^&*()_+-=[]{}')
            
            if char not in options:
                options.append(char)
        
        random.shuffle(options)
        return options[:4]
    
    def _get_confusable_chars(self, char: str) -> List[str]:
        """Get characters that look similar to the given character."""
        confusables = {
            'o': ['0', 'O', 'Q'],
            'O': ['0', 'o', 'Q'],
            '0': ['o', 'O', 'Q'],
            'l': ['1', 'I', '|'],
            '1': ['l', 'I', '|'],
            'I': ['1', 'l', '|'],
            's': ['5', 'S', '$'],
            'S': ['5', 's', '$'],
            '5': ['s', 'S', '$'],
            'a': ['@', '4', 'A'],
            'e': ['3', 'E'],
            'i': ['1', '!', 'I'],
            'b': ['6', '8', 'B'],
            'g': ['9', 'G', 'q'],
            '8': ['B', '&'],
            'z': ['2', 'Z'],
            '2': ['z', 'Z'],
        }
        return confusables.get(char.lower(), [])
    
    def evaluate_priming_response(
        self,
        challenge: Dict[str, Any],
        response: str,
        response_time_ms: int,
        baseline_time: float = None
    ) -> Dict[str, Any]:
        """
        Evaluate a priming test response.
        
        Args:
            challenge: The challenge configuration
            response: User's response
            response_time_ms: Response time in milliseconds
            baseline_time: User's baseline reaction time
            
        Returns:
            Evaluation results
        """
        target = challenge['target_char']
        is_correct = response == target
        
        # Calculate priming effect
        base = baseline_time or 1000
        priming_effect = base - response_time_ms  # Positive = faster (primed)
        
        # Expected priming effect based on prime type
        expected_effects = {
            'adjacent': 150,   # Strong priming from context
            'fragment': 120,   # Moderate priming
            'semantic': 80,    # Weaker priming
            'masked': 200,     # Strong if prime was processed
        }
        
        prime_type = challenge['prime_stimulus']['type']
        expected = expected_effects.get(prime_type, 100)
        
        # Calculate priming score
        # Creators should show larger priming effects
        priming_score = self._calculate_priming_score(
            priming_effect, expected, is_correct
        )
        
        return {
            'is_correct': is_correct,
            'response_time_ms': response_time_ms,
            'baseline_time': base,
            'priming_effect': priming_effect,
            'expected_effect': expected,
            'priming_score': priming_score,
            'prime_type': prime_type,
            'creator_indicator': priming_score > 0.5,
        }
    
    def _calculate_priming_score(
        self,
        observed_effect: float,
        expected_effect: float,
        is_correct: bool
    ) -> float:
        """
        Calculate score indicating creator vs attacker.
        
        Returns score from 0-1.
        """
        score = 0.5  # Start neutral
        
        if not is_correct:
            # Incorrect response indicates possible attacker
            score -= 0.2
        
        # Compare observed priming to expected
        if observed_effect >= expected_effect:
            # Strong priming effect - creator signal
            bonus = min(0.25, (observed_effect - expected_effect) / 200 * 0.25)
            score += bonus
        elif observed_effect >= expected_effect * 0.5:
            # Moderate priming - slight creator signal
            score += 0.1
        elif observed_effect < 0:
            # Negative priming (slower with prime) - suspicious
            # Could indicate unfamiliarity with password
            score -= 0.15
        
        return max(0.0, min(1.0, score))
    
    def _get_display_config(self) -> Dict[str, Any]:
        """Get display configuration for frontend."""
        return {
            'prime_duration_ms': self.prime_duration,
            'mask_duration_ms': self.mask_duration,
            'pre_prime_fixation_ms': 500,
            'target_display_until_response': True,
            'font_family': 'monospace',
            'font_size': '48px',
            'prime_opacity': 1.0 if self.difficulty != 'hard' else 0.8,
            'mask_type': 'hash',  # or 'noise', 'blank'
        }
    
    def get_priming_statistics(
        self,
        responses: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Calculate aggregate priming statistics from multiple responses.
        
        Args:
            responses: List of evaluated priming responses
            
        Returns:
            Aggregate statistics
        """
        if not responses:
            return {'error': 'No responses to analyze'}
        
        import statistics as stats
        
        effects = [r['priming_effect'] for r in responses]
        scores = [r['priming_score'] for r in responses]
        correct_count = sum(1 for r in responses if r['is_correct'])
        
        return {
            'total_responses': len(responses),
            'accuracy': correct_count / len(responses),
            'mean_priming_effect': stats.mean(effects),
            'std_priming_effect': stats.stdev(effects) if len(effects) > 1 else 0,
            'mean_priming_score': stats.mean(scores),
            'creator_probability': sum(1 for r in responses if r['creator_indicator']) / len(responses),
        }
