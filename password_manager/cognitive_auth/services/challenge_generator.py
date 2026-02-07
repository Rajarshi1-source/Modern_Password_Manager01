"""
Challenge Generator Service
============================

Generates cognitive challenges for password verification testing.
Supports scrambled, stroop, priming, and partial reveal challenge types.

@author Password Manager Team
@created 2026-02-07
"""

import random
import hashlib
import secrets
from typing import Dict, List, Any, Optional, Tuple
from django.conf import settings
from django.utils import timezone
from datetime import timedelta


class ChallengeGenerator:
    """
    Generates cognitive verification challenges.
    
    Challenge types:
    - Scrambled: Jumbled password fragments for pattern recognition
    - Stroop: Color-word interference with password elements
    - Priming: Flash password-related stimuli before targets
    - Partial: Password with gaps to complete
    """
    
    # Stroop test colors
    COLORS = ['red', 'blue', 'green', 'yellow', 'purple', 'orange']
    COLOR_WORDS = ['RED', 'BLUE', 'GREEN', 'YELLOW', 'PURPLE', 'ORANGE']
    
    # Common character substitutions for confusion
    CONFUSABLE_CHARS = {
        'o': ['0', 'O', 'Q'],
        '0': ['o', 'O', 'Q'],
        'l': ['1', 'I', '|'],
        '1': ['l', 'I', '|'],
        's': ['5', 'S', '$'],
        '5': ['s', 'S', '$'],
        'a': ['@', '4', 'A'],
        'e': ['3', 'E'],
        'i': ['1', 'I', '!'],
        'b': ['6', '8', 'B'],
        'g': ['9', 'G', 'q'],
    }
    
    def __init__(self, password: str, user_settings: Optional[Dict] = None):
        """
        Initialize generator with the password to test.
        
        Args:
            password: The password to generate challenges for
            user_settings: Optional user preferences for challenges
        """
        self.password = password
        self.password_chars = list(password)
        self.password_len = len(password)
        self.user_settings = user_settings or {}
        
        # Get config from settings
        self.config = getattr(settings, 'COGNITIVE_AUTH', {})
        self.min_challenges = self.config.get('MIN_CHALLENGES', 5)
        self.max_challenges = self.config.get('MAX_CHALLENGES', 10)
        self.time_limit_ms = self.config.get('REACTION_TIME_THRESHOLD_MS', 2000)
    
    def generate_session_challenges(
        self,
        challenge_types: List[str] = None,
        num_challenges: int = None,
        difficulty: str = 'medium'
    ) -> List[Dict[str, Any]]:
        """
        Generate a complete set of challenges for a verification session.
        
        Args:
            challenge_types: Types of challenges to include
            num_challenges: Total number of challenges
            difficulty: Overall difficulty level
            
        Returns:
            List of challenge dictionaries
        """
        if challenge_types is None:
            challenge_types = self.config.get(
                'CHALLENGE_TYPES', 
                ['scrambled', 'stroop', 'priming', 'partial']
            )
        
        if num_challenges is None:
            num_challenges = random.randint(self.min_challenges, self.max_challenges)
        
        challenges = []
        
        # Distribute challenges across types
        type_distribution = self._distribute_challenge_types(
            challenge_types, num_challenges
        )
        
        sequence = 1
        for ctype, count in type_distribution.items():
            for _ in range(count):
                challenge = self._generate_challenge(ctype, difficulty, sequence)
                challenges.append(challenge)
                sequence += 1
        
        # Shuffle to mix challenge types
        random.shuffle(challenges)
        
        # Reassign sequence numbers after shuffle
        for i, challenge in enumerate(challenges):
            challenge['sequence_number'] = i + 1
        
        return challenges
    
    def _distribute_challenge_types(
        self, 
        types: List[str], 
        total: int
    ) -> Dict[str, int]:
        """Distribute challenges evenly across types."""
        base_count = total // len(types)
        remainder = total % len(types)
        
        distribution = {t: base_count for t in types}
        
        # Distribute remainder
        for i, t in enumerate(types):
            if i < remainder:
                distribution[t] += 1
        
        return distribution
    
    def _generate_challenge(
        self, 
        challenge_type: str, 
        difficulty: str,
        sequence: int
    ) -> Dict[str, Any]:
        """Generate a single challenge of the specified type."""
        generators = {
            'scrambled': self._generate_scrambled_challenge,
            'stroop': self._generate_stroop_challenge,
            'priming': self._generate_priming_challenge,
            'partial': self._generate_partial_challenge,
        }
        
        generator = generators.get(challenge_type, self._generate_scrambled_challenge)
        return generator(difficulty, sequence)
    
    def _generate_scrambled_challenge(
        self, 
        difficulty: str, 
        sequence: int
    ) -> Dict[str, Any]:
        """
        Generate a scrambled recognition challenge.
        
        Shows jumbled password fragments - genuine creators recognize
        patterns faster than attackers with plaintext access.
        """
        # Determine chunk size based on difficulty
        chunk_sizes = {'easy': 4, 'medium': 6, 'hard': 8}
        chunk_size = min(chunk_sizes.get(difficulty, 6), self.password_len)
        
        # Extract a random chunk
        if self.password_len <= chunk_size:
            chunk = self.password
            start_pos = 0
        else:
            start_pos = random.randint(0, self.password_len - chunk_size)
            chunk = self.password[start_pos:start_pos + chunk_size]
        
        # Scramble the chunk
        scrambled = self._scramble_string(chunk, difficulty)
        
        # Generate decoys
        decoys = self._generate_decoy_chunks(chunk, difficulty)
        
        # All options including correct answer
        options = [chunk] + decoys
        random.shuffle(options)
        correct_index = options.index(chunk)
        
        # Hash the correct answer
        answer_hash = hashlib.sha256(chunk.encode()).hexdigest()
        
        return {
            'challenge_type': 'scrambled',
            'difficulty': difficulty,
            'sequence_number': sequence,
            'challenge_data': {
                'scrambled_text': scrambled,
                'options': options,
                'chunk_position': start_pos,
                'display_type': 'multiple_choice',
            },
            'correct_answer_hash': answer_hash,
            'time_limit_ms': self._get_time_limit(difficulty),
            'display_duration_ms': self._get_display_duration('scrambled', difficulty),
        }
    
    def _generate_stroop_challenge(
        self, 
        difficulty: str, 
        sequence: int
    ) -> Dict[str, Any]:
        """
        Generate a Stroop-effect challenge.
        
        Password characters displayed in conflicting colors.
        Creators have implicit associations that produce interference
        patterns different from attackers.
        """
        # Select a password character
        char_index = random.randint(0, self.password_len - 1)
        target_char = self.password[char_index]
        
        # Choose a color (text color) and word color (meaning)
        display_color = random.choice(self.COLORS)
        
        # For Stroop effect: show a color word in a different color
        if difficulty == 'hard':
            # Maximum interference: wrong color word in wrong color
            word_options = [w for w in self.COLOR_WORDS if w.lower() != display_color]
            display_word = random.choice(word_options)
        elif difficulty == 'medium':
            # Some interference
            display_word = random.choice(self.COLOR_WORDS)
        else:
            # Congruent (easier)
            display_word = display_color.upper()
        
        # Task: identify the character shown after the Stroop stimulus
        confusable = self._get_confusable_options(target_char)
        options = [target_char] + confusable[:3]
        random.shuffle(options)
        
        answer_hash = hashlib.sha256(target_char.encode()).hexdigest()
        
        return {
            'challenge_type': 'stroop',
            'difficulty': difficulty,
            'sequence_number': sequence,
            'challenge_data': {
                'stroop_word': display_word,
                'stroop_color': display_color,
                'target_char': target_char,
                'char_position': char_index,
                'options': options,
                'instruction': 'After viewing the colored word, identify the password character',
            },
            'correct_answer_hash': answer_hash,
            'time_limit_ms': self._get_time_limit(difficulty),
            'display_duration_ms': self._get_display_duration('stroop', difficulty),
        }
    
    def _generate_priming_challenge(
        self, 
        difficulty: str, 
        sequence: int
    ) -> Dict[str, Any]:
        """
        Generate a priming test challenge.
        
        Brief flash of password-related stimuli followed by target.
        Genuine creators show priming effects (faster recognition)
        that attackers cannot replicate.
        """
        # Select characters for priming
        num_prime_chars = {'easy': 2, 'medium': 3, 'hard': 4}.get(difficulty, 3)
        
        if self.password_len >= num_prime_chars:
            start = random.randint(0, self.password_len - num_prime_chars)
            prime_chars = self.password[start:start + num_prime_chars]
        else:
            prime_chars = self.password
            start = 0
        
        # Prime stimulus (briefly flashed)
        prime_display = self._create_prime_stimulus(prime_chars, difficulty)
        
        # Target (what to recognize after priming)
        target_char = prime_chars[len(prime_chars) // 2]
        
        # Options
        confusable = self._get_confusable_options(target_char)
        options = [target_char] + confusable[:3]
        random.shuffle(options)
        
        # Priming duration decreases with difficulty
        prime_durations = {'easy': 200, 'medium': 100, 'hard': 50}
        
        answer_hash = hashlib.sha256(target_char.encode()).hexdigest()
        
        return {
            'challenge_type': 'priming',
            'difficulty': difficulty,
            'sequence_number': sequence,
            'challenge_data': {
                'prime_stimulus': prime_display,
                'prime_duration_ms': prime_durations.get(difficulty, 100),
                'target_char': target_char,
                'char_position': start + len(prime_chars) // 2,
                'options': options,
                'instruction': 'Watch the flash, then identify the middle character',
            },
            'correct_answer_hash': answer_hash,
            'time_limit_ms': self._get_time_limit(difficulty),
            'display_duration_ms': prime_durations.get(difficulty, 100),
        }
    
    def _generate_partial_challenge(
        self, 
        difficulty: str, 
        sequence: int
    ) -> Dict[str, Any]:
        """
        Generate a partial reveal challenge.
        
        Show password with gaps to complete. Creators complete
        gaps faster and with different hesitation patterns.
        """
        # Determine how many characters to hide
        hide_ratios = {'easy': 0.2, 'medium': 0.35, 'hard': 0.5}
        hide_ratio = hide_ratios.get(difficulty, 0.35)
        
        num_to_hide = max(1, int(self.password_len * hide_ratio))
        
        # Select positions to hide
        positions = random.sample(range(self.password_len), num_to_hide)
        positions.sort()
        
        # Create masked password
        masked = list(self.password)
        hidden_chars = []
        for pos in positions:
            hidden_chars.append((pos, masked[pos]))
            masked[pos] = '_'
        
        masked_password = ''.join(masked)
        
        # The correct answer is the hidden characters joined
        correct_answer = ''.join([c for _, c in hidden_chars])
        answer_hash = hashlib.sha256(correct_answer.encode()).hexdigest()
        
        return {
            'challenge_type': 'partial',
            'difficulty': difficulty,
            'sequence_number': sequence,
            'challenge_data': {
                'masked_password': masked_password,
                'hidden_positions': positions,
                'num_hidden': num_to_hide,
                'instruction': 'Fill in the missing characters',
                'input_type': 'text',
            },
            'correct_answer_hash': answer_hash,
            'time_limit_ms': self._get_time_limit(difficulty) * 2,  # More time for typing
            'display_duration_ms': 0,  # Displayed until response
        }
    
    def _scramble_string(self, s: str, difficulty: str) -> str:
        """Scramble a string based on difficulty."""
        chars = list(s)
        
        if difficulty == 'easy':
            # Light shuffle - swap adjacent pairs
            for i in range(0, len(chars) - 1, 2):
                chars[i], chars[i + 1] = chars[i + 1], chars[i]
        elif difficulty == 'medium':
            # Moderate shuffle
            random.shuffle(chars)
        else:
            # Hard - shuffle and add visual noise
            random.shuffle(chars)
            # Insert random chars at random positions
            noise_chars = ['·', '∙', '◦']
            for _ in range(len(chars) // 3):
                pos = random.randint(0, len(chars))
                chars.insert(pos, random.choice(noise_chars))
        
        return ''.join(chars)
    
    def _generate_decoy_chunks(self, original: str, difficulty: str) -> List[str]:
        """Generate decoy options that look similar to the original."""
        decoys = []
        
        for _ in range(3):
            decoy = list(original)
            
            # Number of substitutions based on difficulty
            num_subs = {'easy': 1, 'medium': 2, 'hard': 1}.get(difficulty, 2)
            
            positions = random.sample(range(len(decoy)), min(num_subs, len(decoy)))
            
            for pos in positions:
                char = decoy[pos]
                confusables = self.CONFUSABLE_CHARS.get(char.lower(), [])
                if confusables:
                    decoy[pos] = random.choice(confusables)
                else:
                    # Random character substitution
                    decoy[pos] = random.choice('abcdefghijklmnopqrstuvwxyz0123456789')
            
            decoy_str = ''.join(decoy)
            if decoy_str != original and decoy_str not in decoys:
                decoys.append(decoy_str)
        
        return decoys
    
    def _get_confusable_options(self, char: str) -> List[str]:
        """Get characters that look similar to the given character."""
        confusables = self.CONFUSABLE_CHARS.get(char.lower(), [])
        
        if len(confusables) < 3:
            # Add random characters
            extras = random.sample('abcdefghijklmnopqrstuvwxyz0123456789', 3)
            confusables.extend([e for e in extras if e != char.lower()])
        
        return confusables[:4]
    
    def _create_prime_stimulus(self, chars: str, difficulty: str) -> Dict[str, Any]:
        """Create a priming stimulus display configuration."""
        return {
            'text': chars,
            'mask_before': '####',
            'mask_after': '####',
            'font_size': 'large',
            'highlight': difficulty != 'hard',
        }
    
    def _get_time_limit(self, difficulty: str) -> int:
        """Get time limit based on difficulty."""
        limits = {'easy': 3000, 'medium': 2000, 'hard': 1500}
        base_limit = limits.get(difficulty, 2000)
        
        # Apply user's extended time setting if enabled
        if self.user_settings.get('extended_time_limit', False):
            base_limit = int(base_limit * 1.5)
        
        return base_limit
    
    def _get_display_duration(self, challenge_type: str, difficulty: str) -> int:
        """Get stimulus display duration."""
        # Durations in milliseconds
        durations = {
            'scrambled': {'easy': 0, 'medium': 0, 'hard': 2000},
            'stroop': {'easy': 1000, 'medium': 750, 'hard': 500},
            'priming': {'easy': 200, 'medium': 100, 'hard': 50},
            'partial': {'easy': 0, 'medium': 0, 'hard': 0},
        }
        
        type_durations = durations.get(challenge_type, {})
        return type_durations.get(difficulty, 0)
    
    def verify_response(
        self, 
        challenge: Dict[str, Any], 
        response: str
    ) -> Tuple[bool, str]:
        """
        Verify if a response is correct.
        
        Returns:
            Tuple of (is_correct, response_hash)
        """
        response_hash = hashlib.sha256(response.encode()).hexdigest()
        is_correct = response_hash == challenge['correct_answer_hash']
        
        return is_correct, response_hash
