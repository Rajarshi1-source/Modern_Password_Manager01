"""
Defender AI Engine - Real-time Password Defense Monitor
========================================================

Monitors password strength in real-time and generates defense strategies.
This AI represents the "defensive" side of the adversarial system,
working to protect and strengthen passwords.

Integrates with existing PasswordStrengthPredictor for base analysis.
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class DefenseLevel(Enum):
    CRITICAL = "critical"
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"
    FORTRESS = "fortress"


class RecommendationPriority(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class DefenseStrategy:
    """A specific defense strategy against an attack."""
    name: str
    description: str
    implementation_steps: List[str]
    effectiveness: float  # 0-1
    difficulty: str  # easy, medium, hard


@dataclass
class Recommendation:
    """A personalized defense recommendation."""
    title: str
    description: str
    priority: RecommendationPriority
    action_items: List[str]
    estimated_improvement: float  # Improvement in defense score
    addresses_attacks: List[str]


@dataclass
class DefenseAssessment:
    """Complete defense assessment for a password."""
    defense_level: DefenseLevel
    defense_score: float  # 0-1
    vulnerabilities: List[str]
    strengths: List[str]
    recommendations: List[Recommendation]
    counter_strategies: List[DefenseStrategy]


class DefenderAI:
    """
    Real-time password defense monitor and strategy generator.
    
    Capabilities:
    - Real-time strength assessment during typing
    - Counter-strategy generation based on Attacker AI findings
    - Adaptive recommendations based on user behavior
    - Integration with existing PasswordStrengthPredictor
    
    Works in tandem with AttackerAI to provide comprehensive security.
    """
    
    # Defense strategy templates
    STRATEGIES = {
        'increase_length': DefenseStrategy(
            name="Increase Password Length",
            description="Longer passwords exponentially increase brute force time",
            implementation_steps=[
                "Aim for 16+ characters",
                "Consider using a passphrase",
                "Add random words to your password"
            ],
            effectiveness=0.9,
            difficulty="easy"
        ),
        'add_complexity': DefenseStrategy(
            name="Add Character Complexity",
            description="Use all character types to expand the keyspace",
            implementation_steps=[
                "Include uppercase letters",
                "Add numbers in non-obvious positions",
                "Use special characters randomly"
            ],
            effectiveness=0.7,
            difficulty="easy"
        ),
        'remove_patterns': DefenseStrategy(
            name="Remove Predictable Patterns",
            description="Eliminate patterns that attackers can exploit",
            implementation_steps=[
                "Avoid keyboard walks (qwerty, etc.)",
                "Don't use dates or years",
                "Avoid sequential characters"
            ],
            effectiveness=0.85,
            difficulty="medium"
        ),
        'use_passphrase': DefenseStrategy(
            name="Use Diceware Passphrase",
            description="Random word combinations are secure and memorable",
            implementation_steps=[
                "Choose 4-6 random words",
                "Add a number or symbol between words",
                "Avoid common phrases"
            ],
            effectiveness=0.95,
            difficulty="easy"
        ),
        'use_generator': DefenseStrategy(
            name="Use Password Generator",
            description="Generated passwords are truly random",
            implementation_steps=[
                "Use the built-in password generator",
                "Set length to 20+ characters",
                "Include all character types"
            ],
            effectiveness=0.99,
            difficulty="easy"
        ),
        'avoid_dictionary': DefenseStrategy(
            name="Avoid Dictionary Words",
            description="Dictionary attacks target common words",
            implementation_steps=[
                "Don't use recognizable words",
                "Misspell words intentionally",
                "Use acronyms instead of full words"
            ],
            effectiveness=0.8,
            difficulty="medium"
        ),
        'randomize_substitutions': DefenseStrategy(
            name="Randomize Character Substitutions",
            description="Predictable l33t speak is easily cracked",
            implementation_steps=[
                "Don't use common substitutions (@ for a, 3 for e)",
                "Place numbers randomly",
                "Use uncommon special characters"
            ],
            effectiveness=0.6,
            difficulty="medium"
        ),
    }
    
    def __init__(self, password_predictor=None):
        """
        Initialize the Defender AI.
        
        Args:
            password_predictor: Optional PasswordStrengthPredictor instance
        """
        self.password_predictor = password_predictor
        self._load_defense_patterns()
        logger.info("DefenderAI initialized")
    
    def _load_defense_patterns(self):
        """Load defense patterns and best practices."""
        self.min_recommended_length = 16
        self.min_acceptable_entropy = 60  # bits
        self.ideal_entropy = 80  # bits
    
    def assess_defense(self, password_features: Dict) -> DefenseAssessment:
        """
        Evaluate current password defense posture.
        
        Args:
            password_features: Dictionary containing password analysis features
        
        Returns:
            DefenseAssessment with complete defense evaluation
        """
        # Calculate base defense score
        defense_score = self._calculate_defense_score(password_features)
        defense_level = self._determine_defense_level(defense_score)
        
        # Identify vulnerabilities
        vulnerabilities = self._identify_vulnerabilities(password_features)
        
        # Identify strengths
        strengths = self._identify_strengths(password_features)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            password_features, vulnerabilities
        )
        
        # Select relevant counter-strategies
        counter_strategies = self._select_counter_strategies(vulnerabilities)
        
        return DefenseAssessment(
            defense_level=defense_level,
            defense_score=defense_score,
            vulnerabilities=vulnerabilities,
            strengths=strengths,
            recommendations=recommendations,
            counter_strategies=counter_strategies
        )
    
    def _calculate_defense_score(self, features: Dict) -> float:
        """Calculate overall defense score (0-1)."""
        score = 0.0
        
        # Length contribution (up to 30%)
        length = features.get('length', 0)
        length_score = min(length / 20, 1.0) * 0.30
        score += length_score
        
        # Entropy contribution (up to 30%)
        entropy = features.get('entropy', 0)
        entropy_score = min(entropy / 80, 1.0) * 0.30
        score += entropy_score
        
        # Character diversity (up to 20%)
        diversity = features.get('character_diversity', 0)
        score += diversity * 0.20
        
        # Absence of patterns (up to 20%)
        has_patterns = features.get('has_common_patterns', False)
        if not has_patterns:
            score += 0.20
        else:
            score += 0.05  # Small credit for having a password at all
        
        # Penalty for high guessability
        guessability = features.get('guessability_score', 50)
        if guessability > 70:
            score *= 0.7  # 30% penalty
        elif guessability > 50:
            score *= 0.85  # 15% penalty
        
        return min(max(score, 0.0), 1.0)
    
    def _determine_defense_level(self, score: float) -> DefenseLevel:
        """Determine defense level from score."""
        if score >= 0.9:
            return DefenseLevel.FORTRESS
        elif score >= 0.75:
            return DefenseLevel.STRONG
        elif score >= 0.5:
            return DefenseLevel.MODERATE
        elif score >= 0.25:
            return DefenseLevel.WEAK
        else:
            return DefenseLevel.CRITICAL
    
    def _identify_vulnerabilities(self, features: Dict) -> List[str]:
        """Identify password vulnerabilities."""
        vulnerabilities = []
        
        # Length vulnerabilities
        length = features.get('length', 0)
        if length < 8:
            vulnerabilities.append("critically_short")
        elif length < 12:
            vulnerabilities.append("short_length")
        elif length < 16:
            vulnerabilities.append("moderate_length")
        
        # Entropy vulnerabilities
        entropy = features.get('entropy', 0)
        if entropy < 30:
            vulnerabilities.append("low_entropy")
        elif entropy < 50:
            vulnerabilities.append("moderate_entropy")
        
        # Character class vulnerabilities
        if not features.get('has_upper', False):
            vulnerabilities.append("no_uppercase")
        if not features.get('has_digit', False):
            vulnerabilities.append("no_digits")
        if not features.get('has_special', False):
            vulnerabilities.append("no_special")
        
        # Pattern vulnerabilities
        if features.get('has_common_patterns', False):
            vulnerabilities.append("contains_patterns")
        
        pattern_info = features.get('pattern_info', {})
        if pattern_info.get('keyboard_walk', False):
            vulnerabilities.append("keyboard_walk")
        if pattern_info.get('date_pattern', False):
            vulnerabilities.append("date_pattern")
        if pattern_info.get('repeated_chars', False):
            vulnerabilities.append("repeated_chars")
        
        # Guessability
        guessability = features.get('guessability_score', 50)
        if guessability > 80:
            vulnerabilities.append("highly_guessable")
        elif guessability > 60:
            vulnerabilities.append("guessable")
        
        return vulnerabilities
    
    def _identify_strengths(self, features: Dict) -> List[str]:
        """Identify password strengths."""
        strengths = []
        
        length = features.get('length', 0)
        if length >= 20:
            strengths.append("excellent_length")
        elif length >= 16:
            strengths.append("good_length")
        
        entropy = features.get('entropy', 0)
        if entropy >= 80:
            strengths.append("high_entropy")
        elif entropy >= 60:
            strengths.append("good_entropy")
        
        diversity = features.get('character_diversity', 0)
        if diversity >= 0.8:
            strengths.append("excellent_diversity")
        elif diversity >= 0.6:
            strengths.append("good_diversity")
        
        if features.get('has_upper', False) and features.get('has_lower', False) \
           and features.get('has_digit', False) and features.get('has_special', False):
            strengths.append("all_character_types")
        
        if not features.get('has_common_patterns', False):
            strengths.append("no_obvious_patterns")
        
        return strengths
    
    def _generate_recommendations(
        self,
        features: Dict,
        vulnerabilities: List[str]
    ) -> List[Recommendation]:
        """Generate personalized recommendations based on vulnerabilities."""
        recommendations = []
        
        # Length recommendations
        if 'critically_short' in vulnerabilities:
            recommendations.append(Recommendation(
                title="Critical: Increase Password Length",
                description="Your password is dangerously short. It can be cracked in seconds.",
                priority=RecommendationPriority.CRITICAL,
                action_items=[
                    "Increase to at least 12 characters immediately",
                    "Consider using a passphrase",
                    "Use the password generator for maximum security"
                ],
                estimated_improvement=0.4,
                addresses_attacks=["brute_force", "dictionary"]
            ))
        elif 'short_length' in vulnerabilities:
            recommendations.append(Recommendation(
                title="Increase Password Length",
                description="Longer passwords are exponentially harder to crack.",
                priority=RecommendationPriority.HIGH,
                action_items=[
                    "Aim for 16+ characters",
                    "Add random words to create a passphrase"
                ],
                estimated_improvement=0.25,
                addresses_attacks=["brute_force", "hybrid"]
            ))
        
        # Pattern recommendations
        if 'keyboard_walk' in vulnerabilities:
            recommendations.append(Recommendation(
                title="Remove Keyboard Pattern",
                description="Keyboard walks like 'qwerty' are in every attacker's dictionary.",
                priority=RecommendationPriority.CRITICAL,
                action_items=[
                    "Remove keyboard walk sequences",
                    "Replace with random characters",
                    "Use non-adjacent keys"
                ],
                estimated_improvement=0.35,
                addresses_attacks=["pattern", "dictionary"]
            ))
        
        if 'date_pattern' in vulnerabilities:
            recommendations.append(Recommendation(
                title="Remove Date Pattern",
                description="Dates are commonly used and easily cracked.",
                priority=RecommendationPriority.HIGH,
                action_items=[
                    "Replace dates with random numbers",
                    "If you need memorable numbers, use obscure ones"
                ],
                estimated_improvement=0.2,
                addresses_attacks=["pattern", "social"]
            ))
        
        # Character type recommendations
        if 'no_special' in vulnerabilities:
            recommendations.append(Recommendation(
                title="Add Special Characters",
                description="Special characters expand the keyspace significantly.",
                priority=RecommendationPriority.MEDIUM,
                action_items=[
                    "Add at least 2 special characters",
                    "Place them randomly, not at the end",
                    "Use uncommon symbols like ^, ~, or |"
                ],
                estimated_improvement=0.15,
                addresses_attacks=["brute_force"]
            ))
        
        # Guessability recommendations
        if 'highly_guessable' in vulnerabilities:
            recommendations.append(Recommendation(
                title="Avoid Common Password Patterns",
                description="Your password matches patterns that attackers check first.",
                priority=RecommendationPriority.CRITICAL,
                action_items=[
                    "Use the password generator",
                    "If remembering is important, use Diceware",
                    "Avoid words that relate to you personally"
                ],
                estimated_improvement=0.4,
                addresses_attacks=["dictionary", "rule_based", "social"]
            ))
        
        # Sort by priority
        priority_order = {
            RecommendationPriority.CRITICAL: 0,
            RecommendationPriority.HIGH: 1,
            RecommendationPriority.MEDIUM: 2,
            RecommendationPriority.LOW: 3,
        }
        recommendations.sort(key=lambda x: priority_order[x.priority])
        
        return recommendations[:5]  # Return top 5 recommendations
    
    def _select_counter_strategies(
        self,
        vulnerabilities: List[str]
    ) -> List[DefenseStrategy]:
        """Select relevant counter-strategies for detected vulnerabilities."""
        strategies = []
        
        vulnerability_to_strategy = {
            'critically_short': 'increase_length',
            'short_length': 'increase_length',
            'moderate_length': 'increase_length',
            'no_uppercase': 'add_complexity',
            'no_digits': 'add_complexity',
            'no_special': 'add_complexity',
            'keyboard_walk': 'remove_patterns',
            'date_pattern': 'remove_patterns',
            'repeated_chars': 'remove_patterns',
            'contains_patterns': 'remove_patterns',
            'highly_guessable': 'use_generator',
            'guessable': 'use_passphrase',
            'low_entropy': 'use_generator',
            'moderate_entropy': 'use_passphrase',
        }
        
        added = set()
        for vulnerability in vulnerabilities:
            strategy_key = vulnerability_to_strategy.get(vulnerability)
            if strategy_key and strategy_key not in added:
                strategies.append(self.STRATEGIES[strategy_key])
                added.add(strategy_key)
        
        # Sort by effectiveness
        strategies.sort(key=lambda x: x.effectiveness, reverse=True)
        
        return strategies[:4]  # Return top 4 strategies
    
    def generate_counter_strategy(
        self,
        attack_vectors: List[Dict]
    ) -> List[DefenseStrategy]:
        """
        Generate defenses against specific attack vectors from AttackerAI.
        
        Args:
            attack_vectors: List of attack vectors from AttackerAI.get_attack_vectors()
        
        Returns:
            List of defense strategies to counter the attacks
        """
        strategies = []
        
        attack_to_strategy = {
            'dictionary': ['use_generator', 'avoid_dictionary'],
            'rule_based': ['randomize_substitutions', 'use_generator'],
            'pattern': ['remove_patterns'],
            'brute_force': ['increase_length', 'add_complexity'],
            'markov': ['use_generator'],
            'hybrid': ['increase_length', 'use_generator'],
        }
        
        added = set()
        for attack in attack_vectors:
            category = attack.get('category', '')
            strategy_keys = attack_to_strategy.get(category, [])
            
            for key in strategy_keys:
                if key not in added and key in self.STRATEGIES:
                    strategies.append(self.STRATEGIES[key])
                    added.add(key)
        
        return strategies
    
    def get_recommendations(
        self,
        user_profile: Optional[Dict] = None,
        recent_battles: Optional[List[Dict]] = None
    ) -> List[Recommendation]:
        """
        Get personalized defense recommendations based on user history.
        
        Args:
            user_profile: User's defense profile data
            recent_battles: Recent adversarial battle results
        
        Returns:
            List of personalized recommendations
        """
        recommendations = []
        
        if user_profile:
            # Check overall defense score trend
            if user_profile.get('overall_defense_score', 0) < 0.5:
                recommendations.append(Recommendation(
                    title="Improve Overall Password Security",
                    description="Your password portfolio has room for improvement.",
                    priority=RecommendationPriority.HIGH,
                    action_items=[
                        "Review and update weak passwords",
                        "Enable password strength checking",
                        "Use the password generator for new accounts"
                    ],
                    estimated_improvement=0.3,
                    addresses_attacks=["all"]
                ))
            
            # Check for common vulnerabilities
            common_vulns = user_profile.get('common_vulnerabilities', [])
            if 'short_length' in common_vulns:
                recommendations.append(Recommendation(
                    title="Your Passwords Tend to Be Short",
                    description="We've noticed your passwords are often under 12 characters.",
                    priority=RecommendationPriority.MEDIUM,
                    action_items=[
                        "Use password generator with 16+ character setting",
                        "Try memorable passphrases"
                    ],
                    estimated_improvement=0.25,
                    addresses_attacks=["brute_force"]
                ))
        
        if recent_battles:
            # Analyze recent battle losses
            losses = [b for b in recent_battles if b.get('outcome') == 'attacker_wins']
            if len(losses) > len(recent_battles) * 0.3:  # >30% loss rate
                recommendations.append(Recommendation(
                    title="Recent Security Concerns Detected",
                    description="Several of your passwords have been vulnerable to attacks.",
                    priority=RecommendationPriority.CRITICAL,
                    action_items=[
                        "Review flagged passwords immediately",
                        "Update with generated passwords",
                        "Enable adversarial monitoring"
                    ],
                    estimated_improvement=0.4,
                    addresses_attacks=["multiple"]
                ))
        
        return recommendations
