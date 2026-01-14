"""
Game Theory Decision Engine
===========================

Orchestrates the adversarial simulation using game theory principles.
Coordinates Attacker AI vs Defender AI battles to find optimal strategies.

Inspired by AlphaGo's approach: use game theory to find the best
move (defense strategy) against a sophisticated opponent (attacker).
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import hashlib
from datetime import datetime

from .attacker_ai import AttackerAI, AttackSimulationResult, AttackResult
from .defender_ai import DefenderAI, DefenseAssessment, Recommendation

logger = logging.getLogger(__name__)


class BattleOutcome(Enum):
    DEFENDER_WINS = "defender_wins"
    ATTACKER_WINS = "attacker_wins"
    DRAW = "draw"
    ONGOING = "ongoing"


@dataclass
class BattleRound:
    """A single round in the adversarial battle."""
    round_number: int
    attack_used: str
    attack_success_prob: float
    defense_applied: str
    defense_effectiveness: float
    round_winner: str  # 'attacker' or 'defender'


@dataclass
class BattleResult:
    """Complete result of an adversarial battle."""
    battle_id: str
    outcome: BattleOutcome
    attack_score: float  # 0-1, attacker's overall success probability
    defense_score: float  # 0-1, defender's strength
    estimated_crack_time_seconds: int
    crack_time_human: str
    
    # Detailed results
    attack_simulation: AttackSimulationResult
    defense_assessment: DefenseAssessment
    
    # Battle replay
    rounds: List[BattleRound]
    
    # Summary
    key_vulnerabilities: List[str]
    key_strengths: List[str]
    recommendations: List[Recommendation]
    
    # Metadata
    timestamp: datetime = field(default_factory=datetime.now)


class GameEngine:
    """
    Coordinates Attacker vs Defender battle using game theory.
    
    Strategy:
    - Minimax-style decision making for attack/defense
    - Nash equilibrium for optimal defense recommendations
    - Iterative deepening for complex password analysis
    
    The engine runs both AIs against each other and determines
    the optimal defense strategy based on the analysis.
    """
    
    # Thresholds for battle outcomes
    DEFENDER_WIN_THRESHOLD = 0.7  # Defense score above this = defender wins
    ATTACKER_WIN_THRESHOLD = 0.6  # Attack success above this = attacker wins
    
    def __init__(
        self,
        attacker_ai: Optional[AttackerAI] = None,
        defender_ai: Optional[DefenderAI] = None
    ):
        """
        Initialize the Game Engine.
        
        Args:
            attacker_ai: Optional AttackerAI instance
            defender_ai: Optional DefenderAI instance
        """
        self.attacker = attacker_ai or AttackerAI()
        self.defender = defender_ai or DefenderAI()
        logger.info("GameEngine initialized with Attacker and Defender AIs")
    
    def run_battle(
        self,
        password_features: Dict,
        user_id: Optional[int] = None
    ) -> BattleResult:
        """
        Execute full adversarial simulation.
        
        This is the main entry point - runs both AIs against each other
        and produces a comprehensive battle result.
        
        Args:
            password_features: Password analysis features
            user_id: Optional user ID for personalization
        
        Returns:
            BattleResult with complete battle analysis
        """
        # Generate battle ID
        battle_id = self._generate_battle_id(password_features)
        
        # Run attack simulation
        attack_result = self.attacker.simulate_attack(password_features)
        
        # Run defense assessment
        defense_result = self.defender.assess_defense(password_features)
        
        # Generate counter-strategies based on attacks
        attack_vectors = self.attacker.get_attack_vectors(password_features)
        counter_strategies = self.defender.generate_counter_strategy(attack_vectors)
        
        # Simulate battle rounds
        rounds = self._simulate_battle_rounds(
            attack_result.attack_results,
            defense_result.counter_strategies
        )
        
        # Calculate Nash equilibrium (optimal play)
        equilibrium = self._calculate_equilibrium(
            attack_result.attack_results,
            defense_result.counter_strategies
        )
        
        # Determine outcome
        outcome = self._determine_outcome(
            attack_result.overall_success_probability,
            defense_result.defense_score
        )
        
        # Get human-readable crack time
        entropy = password_features.get('entropy', 0)
        patterns = []
        if password_features.get('has_common_patterns', False):
            patterns.append('patterns')
        _, crack_time_human = self.attacker.estimate_crack_time(entropy, patterns)
        
        return BattleResult(
            battle_id=battle_id,
            outcome=outcome,
            attack_score=attack_result.overall_success_probability,
            defense_score=defense_result.defense_score,
            estimated_crack_time_seconds=attack_result.estimated_crack_time_seconds,
            crack_time_human=crack_time_human,
            attack_simulation=attack_result,
            defense_assessment=defense_result,
            rounds=rounds,
            key_vulnerabilities=defense_result.vulnerabilities[:5],
            key_strengths=defense_result.strengths[:5],
            recommendations=defense_result.recommendations
        )
    
    def _generate_battle_id(self, features: Dict) -> str:
        """Generate unique battle ID."""
        data = f"{features.get('length', 0)}-{features.get('entropy', 0)}-{datetime.now().isoformat()}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    def _simulate_battle_rounds(
        self,
        attacks: List[AttackResult],
        defenses: List
    ) -> List[BattleRound]:
        """
        Simulate individual battle rounds.
        
        Each round pits an attack against the best available defense.
        """
        rounds = []
        defense_names = [d.name for d in defenses] if defenses else ['Basic Defense']
        
        for i, attack in enumerate(attacks[:5]):  # Top 5 attacks
            # Find best defense for this attack
            best_defense = defense_names[0] if defense_names else 'Basic Defense'
            defense_effectiveness = 1 - attack.success_probability
            
            # Determine round winner
            if attack.success_probability > 0.5:
                round_winner = 'attacker'
            else:
                round_winner = 'defender'
            
            rounds.append(BattleRound(
                round_number=i + 1,
                attack_used=attack.attack_name,
                attack_success_prob=attack.success_probability,
                defense_applied=best_defense,
                defense_effectiveness=defense_effectiveness,
                round_winner=round_winner
            ))
        
        return rounds
    
    def _calculate_equilibrium(
        self,
        attacks: List[AttackResult],
        defenses: List
    ) -> Dict:
        """
        Find optimal defense strategy using game theory.
        
        Uses simplified Nash equilibrium calculation to find
        the best defense strategy given probable attacks.
        
        Returns:
            Dictionary with equilibrium strategy
        """
        if not attacks or not defenses:
            return {'strategy': 'increase_all', 'confidence': 0.5}
        
        # Calculate payoff matrix
        # Rows = attack types, Columns = defense types
        # Values = probability of attack success (lower is better for defender)
        
        # For each defense, calculate how well it counters the attacks
        defense_scores = []
        for defense in defenses:
            total_mitigation = 0
            for attack in attacks:
                # Check if defense counters this attack
                if self._defense_counters_attack(defense, attack):
                    mitigation = defense.effectiveness * attack.success_probability
                else:
                    mitigation = 0.1 * attack.success_probability
                total_mitigation += mitigation
            
            avg_mitigation = total_mitigation / len(attacks)
            defense_scores.append((defense.name, avg_mitigation))
        
        # Best defense = highest mitigation
        best = max(defense_scores, key=lambda x: x[1])
        
        return {
            'strategy': best[0],
            'confidence': best[1],
            'all_strategies': defense_scores
        }
    
    def _defense_counters_attack(self, defense, attack: AttackResult) -> bool:
        """Check if a defense counters an attack."""
        # Mapping of attacks to effective defenses
        counters = {
            'Dictionary Attack': ['Use Password Generator', 'Avoid Dictionary Words'],
            'Rule-Based Mutation': ['Randomize Character Substitutions', 'Use Password Generator'],
            'Pattern Recognition': ['Remove Predictable Patterns'],
            'Brute Force': ['Increase Password Length', 'Add Character Complexity'],
            'Markov Chain': ['Use Password Generator', 'Use Diceware Passphrase'],
            'Hybrid (Dictionary + Brute)': ['Increase Password Length', 'Use Password Generator'],
        }
        
        effective_defenses = counters.get(attack.attack_name, [])
        return defense.name in effective_defenses
    
    def _determine_outcome(
        self,
        attack_success: float,
        defense_score: float
    ) -> BattleOutcome:
        """
        Determine battle outcome based on scores.
        
        Uses configurable thresholds to determine winner.
        """
        # Compare relative strengths
        if defense_score >= self.DEFENDER_WIN_THRESHOLD and attack_success < 0.4:
            return BattleOutcome.DEFENDER_WINS
        elif attack_success >= self.ATTACKER_WIN_THRESHOLD and defense_score < 0.5:
            return BattleOutcome.ATTACKER_WINS
        elif abs(defense_score - (1 - attack_success)) < 0.1:
            return BattleOutcome.DRAW
        elif defense_score > (1 - attack_success):
            return BattleOutcome.DEFENDER_WINS
        else:
            return BattleOutcome.ATTACKER_WINS
    
    def get_quick_assessment(self, password_features: Dict) -> Dict:
        """
        Get a quick assessment without full battle simulation.
        
        Useful for real-time feedback during password typing.
        
        Returns:
            Dictionary with quick assessment metrics
        """
        # Quick attack analysis
        attack_result = self.attacker.simulate_attack(password_features)
        
        # Quick defense score
        defense_score = self.defender.assess_defense(password_features).defense_score
        
        # Determine quick outcome
        if defense_score >= 0.8 and attack_result.overall_success_probability < 0.3:
            status = "excellent"
            message = "Excellent! Password is highly resistant to attacks."
        elif defense_score >= 0.6:
            status = "good"
            message = "Good password. Minor improvements possible."
        elif defense_score >= 0.4:
            status = "moderate"
            message = "Moderate strength. Consider improvements."
        elif defense_score >= 0.2:
            status = "weak"
            message = "Weak password. Vulnerable to common attacks."
        else:
            status = "critical"
            message = "Critical! Password can be cracked quickly."
        
        return {
            'status': status,
            'message': message,
            'defense_score': defense_score,
            'attack_success_probability': attack_result.overall_success_probability,
            'most_effective_attack': attack_result.most_effective_attack.attack_name 
                if attack_result.most_effective_attack else None,
            'estimated_crack_time': attack_result.estimated_crack_time_seconds
        }
    
    def analyze_password_delta(
        self,
        old_features: Dict,
        new_features: Dict
    ) -> Dict:
        """
        Analyze the security improvement between two password versions.
        
        Useful for showing progress when user updates password.
        
        Returns:
            Dictionary with delta analysis
        """
        old_result = self.run_battle(old_features)
        new_result = self.run_battle(new_features)
        
        defense_improvement = new_result.defense_score - old_result.defense_score
        attack_reduction = old_result.attack_score - new_result.attack_score
        time_improvement = new_result.estimated_crack_time_seconds - old_result.estimated_crack_time_seconds
        
        return {
            'defense_improvement': defense_improvement,
            'defense_improvement_percent': defense_improvement * 100,
            'attack_reduction': attack_reduction,
            'attack_reduction_percent': attack_reduction * 100,
            'time_improvement_seconds': time_improvement,
            'old_outcome': old_result.outcome.value,
            'new_outcome': new_result.outcome.value,
            'improved': defense_improvement > 0
        }
