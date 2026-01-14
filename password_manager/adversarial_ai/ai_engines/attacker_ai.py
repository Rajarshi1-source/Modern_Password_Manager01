"""
Attacker AI Engine - Password Cracking Simulation
==================================================

Simulates attacker behavior using latest password cracking techniques.
This AI represents the "offensive" side of the adversarial system,
attempting to identify vulnerabilities in passwords.

IMPORTANT: This module NEVER sees actual passwords. It only analyzes
extracted features (entropy, patterns, length, etc.) to simulate attacks.
"""

import logging
import math
import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class AttackCategory(Enum):
    DICTIONARY = "dictionary"
    BRUTE_FORCE = "brute_force"
    RULE_BASED = "rule_based"
    PATTERN = "pattern"
    MARKOV = "markov"
    HYBRID = "hybrid"
    SOCIAL = "social"
    RAINBOW = "rainbow"


@dataclass
class AttackResult:
    """Result of an attack simulation."""
    attack_name: str
    category: AttackCategory
    success_probability: float
    estimated_time_seconds: int
    reasoning: str
    countermeasures: List[str] = field(default_factory=list)


@dataclass
class AttackSimulationResult:
    """Complete result of running all attack simulations."""
    overall_success_probability: float
    estimated_crack_time_seconds: int
    attack_results: List[AttackResult]
    most_effective_attack: Optional[AttackResult]
    vulnerability_summary: str


class AttackerAI:
    """
    Simulates attacker behavior using latest cracking techniques.
    
    Attack Types Simulated:
    - Dictionary attacks (common passwords, leaked lists)
    - Rule-based mutations (l33t speak, appending numbers)
    - Markov chain generation
    - Hashcat rule simulation
    - Pattern-based guessing (keyboard walks, dates)
    - Brute force estimation
    
    All analysis is done on extracted features, never on actual passwords.
    """
    
    # Common password patterns (regex-like descriptions)
    KEYBOARD_PATTERNS = [
        'qwerty', 'asdf', 'zxcv', '1234', '4321',
        'qazwsx', 'poiuy', 'lkjhg', '!@#$', 'qweasd'
    ]
    
    DATE_PATTERNS = [
        r'\d{4}$',  # Year at end
        r'\d{2}/\d{2}',  # Date format
        r'(19|20)\d{2}',  # Recent years
    ]
    
    LEET_SUBSTITUTIONS = {
        'a': ['4', '@'],
        'e': ['3'],
        'i': ['1', '!'],
        'o': ['0'],
        's': ['5', '$'],
        't': ['7'],
        'l': ['1'],
    }
    
    # Hashrate assumptions (hashes per second for modern GPU)
    HASHRATE_MD5 = 50_000_000_000  # 50 billion/sec
    HASHRATE_SHA256 = 10_000_000_000  # 10 billion/sec
    HASHRATE_BCRYPT_12 = 5_000  # Very slow (secure)
    
    def __init__(self, use_advanced_models: bool = False):
        """
        Initialize the Attacker AI.
        
        Args:
            use_advanced_models: Whether to use ML models (if available)
        """
        self.use_advanced_models = use_advanced_models
        self._load_attack_patterns()
        logger.info("AttackerAI initialized")
    
    def _load_attack_patterns(self):
        """Load known attack patterns and wordlists metadata."""
        # Common password list sizes (for estimation)
        self.wordlist_sizes = {
            'rockyou': 14_344_391,
            'common_passwords': 10_000,
            'crackstation': 1_493_677_782,
            'hashesorg': 8_472_657,
        }
        
        # Rule sets (number of mutations per word)
        self.rule_multipliers = {
            'best64': 77,
            'dive': 99_092,
            'toggles': 16,
            'leetspeak': 128,
        }
    
    def simulate_attack(self, password_features: Dict) -> AttackSimulationResult:
        """
        Run attack simulation on password features.
        
        Args:
            password_features: Dictionary containing:
                - length: int
                - entropy: float
                - has_upper: bool
                - has_lower: bool
                - has_digit: bool
                - has_special: bool
                - has_common_patterns: bool
                - character_diversity: float
                - guessability_score: float (0-100, lower is harder to guess)
                - pattern_info: dict (optional)
        
        Returns:
            AttackSimulationResult with all attack outcomes
        """
        attack_results = []
        
        # Run each attack type
        attack_results.append(self._simulate_dictionary_attack(password_features))
        attack_results.append(self._simulate_rule_based_attack(password_features))
        attack_results.append(self._simulate_pattern_attack(password_features))
        attack_results.append(self._simulate_brute_force(password_features))
        attack_results.append(self._simulate_markov_attack(password_features))
        attack_results.append(self._simulate_hybrid_attack(password_features))
        
        # Find most effective attack
        most_effective = max(attack_results, key=lambda x: x.success_probability)
        
        # Calculate overall success probability (any attack succeeding)
        # Using: P(any success) = 1 - P(all fail)
        all_fail_prob = 1.0
        for result in attack_results:
            all_fail_prob *= (1 - result.success_probability)
        overall_success = 1 - all_fail_prob
        
        # Minimum crack time is from fastest attack
        min_time = min(r.estimated_time_seconds for r in attack_results)
        
        # Generate vulnerability summary
        vulnerability_summary = self._generate_vulnerability_summary(
            password_features, attack_results
        )
        
        return AttackSimulationResult(
            overall_success_probability=overall_success,
            estimated_crack_time_seconds=min_time,
            attack_results=attack_results,
            most_effective_attack=most_effective,
            vulnerability_summary=vulnerability_summary
        )
    
    def _simulate_dictionary_attack(self, features: Dict) -> AttackResult:
        """Simulate dictionary attack."""
        guessability = features.get('guessability_score', 50)
        has_patterns = features.get('has_common_patterns', False)
        
        # Higher guessability = more likely in dictionary
        if guessability > 80:
            success_prob = 0.9
            time_estimate = 1  # Immediate
            reasoning = "Password matches common dictionary patterns"
        elif guessability > 60:
            success_prob = 0.6
            time_estimate = 60  # ~1 minute with wordlists
            reasoning = "Password likely in extended wordlists"
        elif has_patterns:
            success_prob = 0.4
            time_estimate = 300  # 5 minutes
            reasoning = "Contains recognizable patterns"
        else:
            success_prob = 0.1
            time_estimate = 3600  # 1 hour
            reasoning = "Not found in common dictionaries"
        
        return AttackResult(
            attack_name="Dictionary Attack",
            category=AttackCategory.DICTIONARY,
            success_probability=success_prob,
            estimated_time_seconds=time_estimate,
            reasoning=reasoning,
            countermeasures=[
                "Use random character combinations",
                "Avoid common words and phrases",
                "Use a password generator"
            ]
        )
    
    def _simulate_rule_based_attack(self, features: Dict) -> AttackResult:
        """Simulate rule-based mutation attack (hashcat rules)."""
        length = features.get('length', 0)
        has_digit = features.get('has_digit', False)
        has_special = features.get('has_special', False)
        diversity = features.get('character_diversity', 0)
        
        # Check for common mutation patterns
        # e.g., "Password1!", "p@ssw0rd", etc.
        if length < 10 and has_digit and diversity < 0.5:
            success_prob = 0.7
            time_estimate = 120
            reasoning = "Follows common mutation patterns (word + numbers)"
        elif has_special and length < 12:
            success_prob = 0.5
            time_estimate = 600
            reasoning = "Special chars at predictable positions"
        else:
            success_prob = 0.2
            time_estimate = 7200
            reasoning = "Mutations not immediately obvious"
        
        return AttackResult(
            attack_name="Rule-Based Mutation",
            category=AttackCategory.RULE_BASED,
            success_probability=success_prob,
            estimated_time_seconds=time_estimate,
            reasoning=reasoning,
            countermeasures=[
                "Avoid predictable character substitutions",
                "Don't just append numbers to words",
                "Place special characters randomly"
            ]
        )
    
    def _simulate_pattern_attack(self, features: Dict) -> AttackResult:
        """Simulate keyboard walk and pattern-based attacks."""
        has_patterns = features.get('has_common_patterns', False)
        pattern_info = features.get('pattern_info', {})
        
        keyboard_walk = pattern_info.get('keyboard_walk', False)
        date_pattern = pattern_info.get('date_pattern', False)
        repeated_chars = pattern_info.get('repeated_chars', False)
        
        if keyboard_walk:
            success_prob = 0.85
            time_estimate = 10
            reasoning = "Keyboard walk pattern detected"
        elif date_pattern:
            success_prob = 0.75
            time_estimate = 30
            reasoning = "Date pattern detected"
        elif repeated_chars:
            success_prob = 0.6
            time_estimate = 60
            reasoning = "Repeated character sequences"
        elif has_patterns:
            success_prob = 0.4
            time_estimate = 300
            reasoning = "Some predictable patterns detected"
        else:
            success_prob = 0.05
            time_estimate = 86400
            reasoning = "No obvious patterns found"
        
        return AttackResult(
            attack_name="Pattern Recognition",
            category=AttackCategory.PATTERN,
            success_probability=success_prob,
            estimated_time_seconds=time_estimate,
            reasoning=reasoning,
            countermeasures=[
                "Avoid keyboard walks (qwerty, etc.)",
                "Don't use dates or years",
                "Avoid repeated characters or sequences"
            ]
        )
    
    def _simulate_brute_force(self, features: Dict) -> AttackResult:
        """
        Simulate brute force attack.
        Uses entropy and length to estimate time.
        """
        entropy = features.get('entropy', 0)
        length = features.get('length', 0)
        
        # Calculate keyspace
        charset_size = 0
        if features.get('has_lower', False):
            charset_size += 26
        if features.get('has_upper', False):
            charset_size += 26
        if features.get('has_digit', False):
            charset_size += 10
        if features.get('has_special', False):
            charset_size += 32
        
        if charset_size == 0:
            charset_size = 26  # Default to lowercase
        
        keyspace = charset_size ** length
        
        # Using bcrypt as typical modern hash
        time_seconds = keyspace / self.HASHRATE_BCRYPT_12
        
        # Cap at reasonable values
        time_seconds = min(time_seconds, 10**15)  # ~31 million years max
        
        if time_seconds < 1:
            success_prob = 0.99
            reasoning = "Trivially brute-forceable"
        elif time_seconds < 3600:
            success_prob = 0.9
            reasoning = "Brute force feasible within hours"
        elif time_seconds < 86400:
            success_prob = 0.7
            reasoning = "Brute force possible within days"
        elif time_seconds < 2592000:  # 30 days
            success_prob = 0.3
            reasoning = "Brute force would take weeks"
        elif time_seconds < 31536000:  # 1 year
            success_prob = 0.1
            reasoning = "Brute force would take months"
        else:
            success_prob = 0.01
            reasoning = f"Brute force infeasible ({time_seconds/31536000:.0f} years)"
        
        return AttackResult(
            attack_name="Brute Force",
            category=AttackCategory.BRUTE_FORCE,
            success_probability=success_prob,
            estimated_time_seconds=int(time_seconds),
            reasoning=reasoning,
            countermeasures=[
                "Use longer passwords (16+ characters)",
                "Use all character types",
                "Consider using passphrases"
            ]
        )
    
    def _simulate_markov_attack(self, features: Dict) -> AttackResult:
        """
        Simulate Markov chain attack.
        These attacks guess based on character transition probabilities.
        """
        entropy = features.get('entropy', 0)
        diversity = features.get('character_diversity', 0)
        
        # Markov attacks work well on natural-looking passwords
        # Low entropy + natural patterns = vulnerable
        if entropy < 30 and diversity < 0.4:
            success_prob = 0.6
            time_estimate = 180
            reasoning = "Password follows natural language patterns"
        elif entropy < 50:
            success_prob = 0.3
            time_estimate = 1800
            reasoning = "Some predictable character transitions"
        else:
            success_prob = 0.1
            time_estimate = 36000
            reasoning = "Character distribution appears random"
        
        return AttackResult(
            attack_name="Markov Chain",
            category=AttackCategory.MARKOV,
            success_probability=success_prob,
            estimated_time_seconds=time_estimate,
            reasoning=reasoning,
            countermeasures=[
                "Avoid natural word patterns",
                "Include unexpected character combinations",
                "Use truly random generation"
            ]
        )
    
    def _simulate_hybrid_attack(self, features: Dict) -> AttackResult:
        """
        Simulate hybrid attack (dictionary + brute force on parts).
        """
        length = features.get('length', 0)
        guessability = features.get('guessability_score', 50)
        
        # Hybrid attacks work when password has guessable core + random parts
        if length < 12 and guessability > 50:
            success_prob = 0.5
            time_estimate = 900
            reasoning = "Password appears to be word + random suffix"
        elif length < 16:
            success_prob = 0.25
            time_estimate = 7200
            reasoning = "Potential hybrid structure detected"
        else:
            success_prob = 0.05
            time_estimate = 86400
            reasoning = "Too long for efficient hybrid attack"
        
        return AttackResult(
            attack_name="Hybrid (Dictionary + Brute)",
            category=AttackCategory.HYBRID,
            success_probability=success_prob,
            estimated_time_seconds=time_estimate,
            reasoning=reasoning,
            countermeasures=[
                "Avoid adding predictable suffixes",
                "Use fully random passwords",
                "Use longer passwords (16+)"
            ]
        )
    
    def _generate_vulnerability_summary(
        self,
        features: Dict,
        results: List[AttackResult]
    ) -> str:
        """Generate human-readable vulnerability summary."""
        # Find top vulnerabilities
        high_risk = [r for r in results if r.success_probability > 0.5]
        
        if not high_risk:
            return "Password shows good resistance to common attacks."
        
        if len(high_risk) >= 3:
            return f"Critical: Password is vulnerable to {len(high_risk)} attack types. " \
                   f"Most dangerous: {high_risk[0].attack_name}."
        
        attack_names = ", ".join(r.attack_name for r in high_risk)
        return f"Warning: Password vulnerable to {attack_names}. " \
               f"Consider strengthening."
    
    def estimate_crack_time(
        self,
        entropy: float,
        patterns: List[str],
        hash_type: str = 'bcrypt'
    ) -> Tuple[int, str]:
        """
        Estimate time to crack based on password characteristics.
        
        Args:
            entropy: Password entropy in bits
            patterns: List of detected pattern types
            hash_type: Type of hash (md5, sha256, bcrypt)
        
        Returns:
            Tuple of (seconds, human-readable time)
        """
        # Get hashrate
        hashrates = {
            'md5': self.HASHRATE_MD5,
            'sha256': self.HASHRATE_SHA256,
            'bcrypt': self.HASHRATE_BCRYPT_12,
        }
        hashrate = hashrates.get(hash_type, self.HASHRATE_BCRYPT_12)
        
        # Calculate keyspace from entropy
        keyspace = 2 ** entropy
        
        # Reduce keyspace if patterns detected
        if 'keyboard_walk' in patterns:
            keyspace = min(keyspace, 10_000)
        if 'dictionary' in patterns:
            keyspace = min(keyspace, 1_000_000)
        if 'date' in patterns:
            keyspace = min(keyspace, 100_000)
        
        seconds = keyspace / hashrate
        
        # Human-readable time
        if seconds < 1:
            human = "instant"
        elif seconds < 60:
            human = f"{seconds:.0f} seconds"
        elif seconds < 3600:
            human = f"{seconds/60:.0f} minutes"
        elif seconds < 86400:
            human = f"{seconds/3600:.0f} hours"
        elif seconds < 2592000:
            human = f"{seconds/86400:.0f} days"
        elif seconds < 31536000:
            human = f"{seconds/2592000:.0f} months"
        else:
            years = seconds / 31536000
            if years > 1_000_000:
                human = f"{years/1_000_000:.0f} million years"
            elif years > 1000:
                human = f"{years/1000:.0f} thousand years"
            else:
                human = f"{years:.0f} years"
        
        return int(seconds), human
    
    def get_attack_vectors(self, password_features: Dict) -> List[Dict]:
        """
        Get ordered list of likely successful attack vectors.
        
        Returns list of attack vector dictionaries sorted by success probability.
        """
        result = self.simulate_attack(password_features)
        
        vectors = []
        for attack in sorted(
            result.attack_results,
            key=lambda x: x.success_probability,
            reverse=True
        ):
            vectors.append({
                'name': attack.attack_name,
                'category': attack.category.value,
                'success_probability': attack.success_probability,
                'estimated_time': attack.estimated_time_seconds,
                'reasoning': attack.reasoning,
                'countermeasures': attack.countermeasures,
            })
        
        return vectors
