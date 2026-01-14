"""
Anonymized Breach Learning System
==================================

Learns from breach patterns across all users without storing PII.
Uses federated learning approach to improve attack detection
while preserving user privacy.

PRIVACY GUARANTEES:
- No individual passwords are ever stored
- Only statistical patterns are recorded
- All data is anonymized and aggregated
- Users can opt out of contributing data
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
import hashlib
import json

logger = logging.getLogger(__name__)


@dataclass
class AnonymizedPattern:
    """An anonymized password pattern for learning."""
    pattern_type: str
    pattern_hash: str  # Hash of pattern, not the pattern itself
    features: Dict  # Statistical features only
    attack_success_rate: float
    occurrence_count: int
    first_seen: datetime
    last_seen: datetime


@dataclass
class AttackTrend:
    """A trending attack pattern."""
    attack_type: str
    trend_direction: str  # 'rising', 'stable', 'declining'
    velocity: float  # Rate of change
    affected_pattern_count: int
    recommended_defenses: List[str]


@dataclass
class LearningUpdate:
    """An update to the learning system from a battle."""
    pattern_features: Dict
    attack_vectors_tested: List[str]
    successful_attacks: List[str]
    defense_score: float
    timestamp: datetime


class BreachLearningSystem:
    """
    Learns from anonymized breach patterns across all users.
    
    Privacy-First Design:
    - Only aggregated statistics are stored
    - No PII or actual passwords ever leave the system
    - Pattern hashes use one-way functions
    - Differential privacy can be applied to aggregates
    
    Learning Capabilities:
    - Tracks which patterns are vulnerable
    - Identifies trending attack methods
    - Improves defense recommendations over time
    - Federated learning approach
    """
    
    # Pattern types we track
    PATTERN_TYPES = [
        'length_distribution',
        'char_class_combo',
        'common_prefix',
        'common_suffix',
        'keyboard_pattern',
        'date_pattern',
        'leet_speak',
        'dictionary_base',
    ]
    
    # Trend thresholds
    TRENDING_THRESHOLD = 0.1  # 10% increase = trending
    DECLINING_THRESHOLD = -0.1  # 10% decrease = declining
    
    def __init__(self, storage_backend=None):
        """
        Initialize the learning system.
        
        Args:
            storage_backend: Optional database backend for persistence
        """
        self.storage = storage_backend
        self._pattern_cache = defaultdict(lambda: {
            'count': 0,
            'success_rates': [],
            'last_seen': None
        })
        self._attack_trends = {}
        logger.info("BreachLearningSystem initialized")
    
    def record_battle_result(
        self,
        password_features: Dict,
        battle_result: Dict,
        user_consent: bool = True
    ) -> None:
        """
        Record anonymized battle result for learning.
        
        Args:
            password_features: Password features (will be anonymized)
            battle_result: Result from GameEngine.run_battle()
            user_consent: Whether user consented to contribute data
        """
        if not user_consent:
            logger.debug("User did not consent to data contribution")
            return
        
        try:
            # Extract anonymized patterns
            patterns = self._extract_patterns(password_features)
            
            # Record each pattern
            for pattern in patterns:
                self._update_pattern_stats(
                    pattern,
                    battle_result.get('attack_score', 0),
                    battle_result.get('attack_vectors_used', [])
                )
            
            # Update attack trends
            self._update_attack_trends(battle_result.get('attack_vectors_used', []))
            
            logger.debug(f"Recorded {len(patterns)} anonymized patterns")
            
        except Exception as e:
            logger.error(f"Error recording battle result: {e}")
    
    def _extract_patterns(self, features: Dict) -> List[AnonymizedPattern]:
        """
        Extract anonymized patterns from password features.
        
        No actual password data is stored - only pattern hashes
        and statistical features.
        """
        patterns = []
        now = datetime.now()
        
        # Length distribution pattern
        length = features.get('length', 0)
        length_bucket = self._bucket_length(length)
        patterns.append(AnonymizedPattern(
            pattern_type='length_distribution',
            pattern_hash=hashlib.sha256(f"length:{length_bucket}".encode()).hexdigest()[:16],
            features={'length_bucket': length_bucket},
            attack_success_rate=0.0,  # Will be updated
            occurrence_count=1,
            first_seen=now,
            last_seen=now
        ))
        
        # Character class combination pattern
        char_classes = self._get_char_class_combo(features)
        patterns.append(AnonymizedPattern(
            pattern_type='char_class_combo',
            pattern_hash=hashlib.sha256(f"chars:{char_classes}".encode()).hexdigest()[:16],
            features={'char_classes': char_classes},
            attack_success_rate=0.0,
            occurrence_count=1,
            first_seen=now,
            last_seen=now
        ))
        
        # Pattern type if detected
        pattern_info = features.get('pattern_info', {})
        if pattern_info.get('keyboard_walk', False):
            patterns.append(AnonymizedPattern(
                pattern_type='keyboard_pattern',
                pattern_hash=hashlib.sha256(b"keyboard_walk").hexdigest()[:16],
                features={'type': 'keyboard_walk'},
                attack_success_rate=0.0,
                occurrence_count=1,
                first_seen=now,
                last_seen=now
            ))
        
        if pattern_info.get('date_pattern', False):
            patterns.append(AnonymizedPattern(
                pattern_type='date_pattern',
                pattern_hash=hashlib.sha256(b"date_pattern").hexdigest()[:16],
                features={'type': 'date'},
                attack_success_rate=0.0,
                occurrence_count=1,
                first_seen=now,
                last_seen=now
            ))
        
        return patterns
    
    def _bucket_length(self, length: int) -> str:
        """Bucket password length for anonymization."""
        if length < 8:
            return 'very_short'
        elif length < 12:
            return 'short'
        elif length < 16:
            return 'medium'
        elif length < 20:
            return 'long'
        else:
            return 'very_long'
    
    def _get_char_class_combo(self, features: Dict) -> str:
        """Get character class combination string."""
        classes = []
        if features.get('has_lower', False):
            classes.append('L')
        if features.get('has_upper', False):
            classes.append('U')
        if features.get('has_digit', False):
            classes.append('D')
        if features.get('has_special', False):
            classes.append('S')
        return ''.join(sorted(classes)) or 'NONE'
    
    def _update_pattern_stats(
        self,
        pattern: AnonymizedPattern,
        attack_success: float,
        attack_vectors: List[str]
    ) -> None:
        """Update pattern statistics in cache."""
        key = f"{pattern.pattern_type}:{pattern.pattern_hash}"
        
        self._pattern_cache[key]['count'] += 1
        self._pattern_cache[key]['success_rates'].append(attack_success)
        self._pattern_cache[key]['last_seen'] = datetime.now()
        
        # Keep only recent data (rolling window)
        if len(self._pattern_cache[key]['success_rates']) > 1000:
            self._pattern_cache[key]['success_rates'] = \
                self._pattern_cache[key]['success_rates'][-1000:]
    
    def _update_attack_trends(self, attack_vectors: List[str]) -> None:
        """Update attack trend tracking."""
        now = datetime.now()
        
        for attack in attack_vectors:
            if attack not in self._attack_trends:
                self._attack_trends[attack] = {
                    'count': 0,
                    'recent_count': 0,
                    'last_seen': now,
                    'history': []
                }
            
            self._attack_trends[attack]['count'] += 1
            self._attack_trends[attack]['recent_count'] += 1
            self._attack_trends[attack]['last_seen'] = now
            self._attack_trends[attack]['history'].append(now)
            
            # Keep only last 30 days of history
            cutoff = now - timedelta(days=30)
            self._attack_trends[attack]['history'] = [
                h for h in self._attack_trends[attack]['history']
                if h > cutoff
            ]
    
    def get_pattern_vulnerability(self, pattern_hash: str) -> Optional[float]:
        """
        Get vulnerability score for a pattern.
        
        Returns:
            Attack success rate for this pattern (0-1), or None if unknown
        """
        for key, data in self._pattern_cache.items():
            if pattern_hash in key:
                rates = data['success_rates']
                if rates:
                    return sum(rates) / len(rates)
        return None
    
    def get_trending_attacks(self, limit: int = 5) -> List[AttackTrend]:
        """
        Get currently trending attack patterns.
        
        Returns attacks that are increasing in frequency.
        """
        trends = []
        now = datetime.now()
        
        for attack, data in self._attack_trends.items():
            # Calculate trend velocity
            history = data['history']
            if len(history) < 10:
                continue
            
            # Compare recent (7 days) vs older (7-14 days)
            cutoff_recent = now - timedelta(days=7)
            cutoff_older = now - timedelta(days=14)
            
            recent = len([h for h in history if h > cutoff_recent])
            older = len([h for h in history if cutoff_older < h <= cutoff_recent])
            
            if older == 0:
                velocity = 1.0 if recent > 0 else 0.0
            else:
                velocity = (recent - older) / older
            
            # Determine trend direction
            if velocity > self.TRENDING_THRESHOLD:
                direction = 'rising'
            elif velocity < self.DECLINING_THRESHOLD:
                direction = 'declining'
            else:
                direction = 'stable'
            
            # Get recommended defenses
            defenses = self._get_defenses_for_attack(attack)
            
            trends.append(AttackTrend(
                attack_type=attack,
                trend_direction=direction,
                velocity=velocity,
                affected_pattern_count=data['count'],
                recommended_defenses=defenses
            ))
        
        # Sort by velocity (highest first) and limit
        trends.sort(key=lambda x: x.velocity, reverse=True)
        return trends[:limit]
    
    def _get_defenses_for_attack(self, attack_type: str) -> List[str]:
        """Get recommended defenses for an attack type."""
        defense_map = {
            'dictionary': ['Use password generator', 'Avoid common words'],
            'brute_force': ['Increase length to 16+', 'Use all character types'],
            'pattern': ['Remove keyboard walks', 'Avoid dates'],
            'rule_based': ['Avoid predictable substitutions'],
            'markov': ['Use truly random passwords'],
            'hybrid': ['Use long random passwords'],
        }
        
        for key, defenses in defense_map.items():
            if key in attack_type.lower():
                return defenses
        
        return ['Use password generator', 'Increase length']
    
    def get_aggregated_insights(self) -> Dict:
        """
        Get aggregated insights from all learning data.
        
        Returns summary statistics without any PII.
        """
        total_patterns = sum(d['count'] for d in self._pattern_cache.values())
        
        # Calculate vulnerability by pattern type
        type_vulnerabilities = defaultdict(list)
        for key, data in self._pattern_cache.items():
            pattern_type = key.split(':')[0]
            if data['success_rates']:
                avg_rate = sum(data['success_rates']) / len(data['success_rates'])
                type_vulnerabilities[pattern_type].append(avg_rate)
        
        vulnerabilities = {}
        for ptype, rates in type_vulnerabilities.items():
            if rates:
                vulnerabilities[ptype] = sum(rates) / len(rates)
        
        # Get trending attacks
        trending = self.get_trending_attacks(3)
        
        return {
            'total_patterns_analyzed': total_patterns,
            'pattern_type_vulnerabilities': vulnerabilities,
            'most_vulnerable_patterns': sorted(
                vulnerabilities.items(),
                key=lambda x: x[1],
                reverse=True
            )[:3],
            'trending_attacks': [
                {'type': t.attack_type, 'direction': t.trend_direction}
                for t in trending
            ],
            'last_updated': datetime.now().isoformat()
        }
    
    def update_threat_model(self) -> Dict:
        """
        Periodic model update from aggregated data.
        
        Should be called periodically (e.g., daily) to refresh
        the threat model based on collected data.
        
        Returns:
            Update summary
        """
        logger.info("Updating threat model from aggregated data")
        
        # Calculate new vulnerability thresholds
        all_rates = []
        for data in self._pattern_cache.values():
            all_rates.extend(data['success_rates'])
        
        if not all_rates:
            return {'status': 'no_data', 'message': 'No data to update from'}
        
        # Calculate percentiles
        all_rates.sort()
        n = len(all_rates)
        
        p25 = all_rates[int(n * 0.25)] if n > 4 else 0.25
        p50 = all_rates[int(n * 0.5)] if n > 2 else 0.5
        p75 = all_rates[int(n * 0.75)] if n > 4 else 0.75
        
        return {
            'status': 'updated',
            'patterns_analyzed': len(self._pattern_cache),
            'total_observations': n,
            'vulnerability_percentiles': {
                'p25': p25,
                'p50_median': p50,
                'p75': p75
            },
            'trending_attacks': len([
                t for t in self.get_trending_attacks()
                if t.trend_direction == 'rising'
            ]),
            'updated_at': datetime.now().isoformat()
        }
    
    def export_anonymized_data(self, format: str = 'json') -> str:
        """
        Export anonymized learning data for analysis.
        
        Returns data that can be shared without privacy concerns.
        """
        data = {
            'export_date': datetime.now().isoformat(),
            'pattern_summaries': [],
            'attack_trends': []
        }
        
        # Export pattern summaries (no raw data)
        for key, pdata in self._pattern_cache.items():
            pattern_type = key.split(':')[0]
            rates = pdata['success_rates']
            
            data['pattern_summaries'].append({
                'pattern_type': pattern_type,
                'observation_count': pdata['count'],
                'avg_attack_success': sum(rates) / len(rates) if rates else 0,
                'last_seen': pdata['last_seen'].isoformat() if pdata['last_seen'] else None
            })
        
        # Export attack trends
        for trend in self.get_trending_attacks(10):
            data['attack_trends'].append({
                'attack_type': trend.attack_type,
                'direction': trend.trend_direction,
                'velocity': trend.velocity
            })
        
        if format == 'json':
            return json.dumps(data, indent=2)
        else:
            return str(data)
