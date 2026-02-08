"""
Threat Intelligence Service
============================

Aggregates threat intelligence from multiple sources to assess
password vulnerability based on:
- Active threat actor campaigns
- Industry-specific threats
- Dark web breach data
- Known password dictionaries
"""

import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Q

logger = logging.getLogger(__name__)


@dataclass
class ThreatMatch:
    """Represents a threat matching the user's profile."""
    threat_actor_id: str
    threat_actor_name: str
    match_type: str  # 'industry', 'pattern', 'region'
    match_confidence: float
    threat_level: str
    description: str


@dataclass
class DictionaryMatch:
    """Represents a match against known password dictionaries."""
    dictionary_name: str
    match_type: str  # 'exact', 'partial', 'mutation'
    similarity_score: float


@dataclass
class ThreatLevel:
    """Represents the overall threat level for a credential."""
    level: str  # 'low', 'medium', 'high', 'critical'
    score: float  # 0-1
    factors: List[str]
    active_threats: List[ThreatMatch]
    recommended_action: str


@dataclass
class IndustryThreat:
    """Represents industry-specific threat information."""
    industry_code: str
    industry_name: str
    threat_level: str
    threat_score: float
    active_campaigns: int
    recent_breaches: int


class ThreatIntelligenceService:
    """
    Threat intelligence aggregation and analysis service.
    
    Collects threat data from multiple sources and provides
    risk assessment for specific credentials and users.
    """
    
    def __init__(self):
        """Initialize the threat intelligence service."""
        self._cache = {}
        self._cache_ttl = timedelta(hours=1)
    
    def fetch_active_ttps(self) -> List['ThreatActorTTP']:
        """
        Fetch all currently active threat actor TTPs.
        
        Returns:
            List of active ThreatActorTTP records
        """
        from ..models import ThreatActorTTP
        
        # Get TTPs active in the last 30 days
        cutoff_date = timezone.now() - timedelta(days=30)
        
        return list(ThreatActorTTP.objects.filter(
            is_currently_active=True,
        ).filter(
            Q(last_active__gte=cutoff_date) | Q(last_active__isnull=True)
        ).order_by('-threat_level', '-last_active'))
    
    def match_user_industry(
        self,
        user_industry: str
    ) -> List[IndustryThreat]:
        """
        Find threat actors and campaigns targeting the user's industry.
        
        Args:
            user_industry: The user's industry code
            
        Returns:
            List of industry-specific threats
        """
        from ..models import IndustryThreatLevel, ThreatActorTTP
        
        threats = []
        
        # Get industry threat level
        try:
            industry = IndustryThreatLevel.objects.get(
                industry_code=user_industry
            )
            threats.append(IndustryThreat(
                industry_code=industry.industry_code,
                industry_name=industry.industry_name,
                threat_level=industry.current_threat_level,
                threat_score=industry.threat_score,
                active_campaigns=industry.active_campaigns_count,
                recent_breaches=industry.recent_breaches_count,
            ))
        except IndustryThreatLevel.DoesNotExist:
            pass
        
        # Also check threat actors targeting this industry
        actors = ThreatActorTTP.objects.filter(
            is_currently_active=True,
            target_industries__contains=[user_industry]
        )
        
        for actor in actors:
            # Add as industry threat if not already covered
            if not any(t.industry_code == user_industry for t in threats):
                threats.append(IndustryThreat(
                    industry_code=user_industry,
                    industry_name=user_industry.replace('_', ' ').title(),
                    threat_level=actor.threat_level,
                    threat_score=self._threat_level_to_score(actor.threat_level),
                    active_campaigns=1,
                    recent_breaches=0,
                ))
        
        return threats
    
    def check_pattern_in_dictionaries(
        self,
        pattern_fingerprint: bytes,
        char_class_sequence: str
    ) -> List[DictionaryMatch]:
        """
        Check if a password pattern matches known compromised dictionaries.
        
        Args:
            pattern_fingerprint: The password structure fingerprint
            char_class_sequence: The character class sequence
            
        Returns:
            List of dictionary matches
        """
        # This is a simplified implementation
        # In production, this would check against actual password databases
        
        matches = []
        
        # Check for common weak patterns
        weak_patterns = [
            ('LLLLDDDD', 'rockyou_common', 0.8),  # word + 4 digits
            ('ULLLDDDD', 'rockyou_common', 0.75),  # Word123 pattern
            ('LLLLLLDD', 'common_passwords', 0.7),  # word + 2 digits
            ('DDDDDDDD', 'numeric_only', 0.9),  # all digits
            ('LLLLLLLL', 'dictionary_words', 0.6),  # all lowercase
        ]
        
        for pattern, dict_name, similarity in weak_patterns:
            if char_class_sequence.startswith(pattern[:4]):
                matches.append(DictionaryMatch(
                    dictionary_name=dict_name,
                    match_type='partial',
                    similarity_score=similarity * 0.8  # Partial match
                ))
        
        return matches
    
    def get_real_time_threat_level(
        self,
        user_id: int,
        credential_domain: str
    ) -> ThreatLevel:
        """
        Calculate real-time threat level for a specific credential.
        
        Combines multiple threat sources to provide an overall
        risk assessment.
        
        Args:
            user_id: The user's ID
            credential_domain: The domain/service of the credential
            
        Returns:
            ThreatLevel assessment
        """
        from django.contrib.auth.models import User
        from ..models import PredictiveExpirationSettings, ThreatActorTTP
        
        factors = []
        threat_matches = []
        total_score = 0.0
        
        # Get user settings for industry context
        try:
            user = User.objects.get(id=user_id)
            settings = PredictiveExpirationSettings.objects.get(user=user)
            user_industry = settings.industry
        except (User.DoesNotExist, PredictiveExpirationSettings.DoesNotExist):
            user_industry = ''
        
        # Check industry threats
        if user_industry:
            industry_threats = self.match_user_industry(user_industry)
            for threat in industry_threats:
                if threat.threat_score > 0.3:
                    factors.append(f"Industry threat: {threat.industry_name}")
                    total_score += threat.threat_score * 0.3
        
        # Check for active threat actors
        active_ttps = self.fetch_active_ttps()
        high_threat_count = sum(
            1 for ttp in active_ttps
            if ttp.threat_level in ['high', 'critical']
        )
        
        if high_threat_count > 0:
            factors.append(f"{high_threat_count} high-severity threats active")
            total_score += min(high_threat_count * 0.1, 0.3)
            
            # Add threat matches
            for ttp in active_ttps[:3]:  # Top 3 threats
                if ttp.threat_level in ['high', 'critical']:
                    threat_matches.append(ThreatMatch(
                        threat_actor_id=str(ttp.actor_id),
                        threat_actor_name=ttp.name,
                        match_type='active_threat',
                        match_confidence=0.7,
                        threat_level=ttp.threat_level,
                        description=f"Active {ttp.actor_type} threat"
                    ))
        
        # Check domain-specific risks
        high_value_domains = [
            'banking', 'finance', 'crypto', 'healthcare', 'government'
        ]
        for domain_keyword in high_value_domains:
            if domain_keyword in credential_domain.lower():
                factors.append(f"High-value domain: {domain_keyword}")
                total_score += 0.15
                break
        
        # Normalize score
        total_score = min(total_score, 1.0)
        
        # Determine threat level
        if total_score >= 0.8:
            level = 'critical'
            action = 'rotate_immediately'
        elif total_score >= 0.6:
            level = 'high'
            action = 'rotate_soon'
        elif total_score >= 0.4:
            level = 'medium'
            action = 'plan_rotation'
        else:
            level = 'low'
            action = 'monitor'
        
        return ThreatLevel(
            level=level,
            score=total_score,
            factors=factors,
            active_threats=threat_matches,
            recommended_action=action,
        )
    
    def correlate_ransomware_campaigns(
        self,
        user_industries: List[str]
    ) -> List[ThreatMatch]:
        """
        Correlate user's industries with active ransomware campaigns.
        
        Args:
            user_industries: List of industries the user is associated with
            
        Returns:
            List of matching ransomware threat actors
        """
        from ..models import ThreatActorTTP
        
        matches = []
        
        ransomware_actors = ThreatActorTTP.objects.filter(
            actor_type='ransomware',
            is_currently_active=True,
        )
        
        for actor in ransomware_actors:
            # Check industry overlap
            targeted = set(actor.target_industries)
            user_set = set(user_industries)
            
            overlap = targeted & user_set
            if overlap:
                confidence = len(overlap) / len(user_set) if user_set else 0
                matches.append(ThreatMatch(
                    threat_actor_id=str(actor.actor_id),
                    threat_actor_name=actor.name,
                    match_type='industry',
                    match_confidence=confidence,
                    threat_level=actor.threat_level,
                    description=f"Targets: {', '.join(overlap)}"
                ))
        
        return sorted(matches, key=lambda x: x.match_confidence, reverse=True)
    
    def get_threat_summary(self) -> Dict:
        """
        Get a summary of the current threat landscape.
        
        Returns:
            Dictionary with threat statistics
        """
        from ..models import ThreatActorTTP, IndustryThreatLevel
        
        active_actors = ThreatActorTTP.objects.filter(
            is_currently_active=True
        )
        
        return {
            'total_active_actors': active_actors.count(),
            'critical_threats': active_actors.filter(
                threat_level='critical'
            ).count(),
            'high_threats': active_actors.filter(
                threat_level='high'
            ).count(),
            'ransomware_active': active_actors.filter(
                actor_type='ransomware'
            ).count(),
            'apt_active': active_actors.filter(
                actor_type='apt'
            ).count(),
            'industries_at_risk': IndustryThreatLevel.objects.filter(
                current_threat_level__in=['high', 'severe', 'critical']
            ).count(),
            'last_updated': timezone.now().isoformat(),
        }
    
    def _threat_level_to_score(self, level: str) -> float:
        """Convert threat level string to numeric score."""
        mapping = {
            'low': 0.2,
            'medium': 0.4,
            'high': 0.7,
            'critical': 0.9,
            'elevated': 0.5,
            'severe': 0.8,
        }
        return mapping.get(level, 0.3)


# Singleton instance
_threat_service: Optional[ThreatIntelligenceService] = None


def get_threat_intelligence_service() -> ThreatIntelligenceService:
    """Get the singleton threat intelligence service instance."""
    global _threat_service
    if _threat_service is None:
        _threat_service = ThreatIntelligenceService()
    return _threat_service
