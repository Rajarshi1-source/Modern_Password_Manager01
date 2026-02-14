"""
Predictive Expiration Service
==============================

Core service for predicting password compromise and managing
proactive rotations based on threat intelligence.

Combines pattern analysis, threat intelligence, and user context
to provide risk assessments for each credential.
"""

import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import transaction
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models import PredictiveExpirationRule

from .pattern_analysis_engine import (
    PatternAnalysisEngine,
    PatternFingerprint,
    get_pattern_analysis_engine
)
from .threat_intelligence_service import (
    ThreatIntelligenceService,
    ThreatLevel,
    get_threat_intelligence_service
)

logger = logging.getLogger(__name__)


@dataclass
class RiskScore:
    """Represents a comprehensive risk score for a credential."""
    overall_score: float  # 0-1
    pattern_risk: float
    threat_risk: float
    industry_risk: float
    age_risk: float
    factors: List[str]
    confidence: float


@dataclass
class PredictionResult:
    """Result of compromise timeline prediction."""
    predicted_date: Optional[datetime]
    confidence: float
    risk_level: str
    contributing_factors: List[str]
    days_until_predicted: Optional[int]


@dataclass
class RotationPlan:
    """Recommended rotation plan for a credential."""
    should_rotate: bool
    urgency: str  # 'none', 'low', 'medium', 'high', 'critical'
    recommended_date: Optional[datetime]
    reasons: List[str]
    new_password_requirements: Dict


class PredictiveExpirationService:
    """
    Core prediction engine for password expiration.
    
    Analyzes passwords, correlates with threat intelligence,
    and predicts when passwords might be compromised.
    """
    
    # Risk weights
    PATTERN_WEIGHT = 0.35
    THREAT_WEIGHT = 0.30
    INDUSTRY_WEIGHT = 0.20
    AGE_WEIGHT = 0.15
    
    # Risk thresholds
    HIGH_RISK_THRESHOLD = 0.7
    MEDIUM_RISK_THRESHOLD = 0.4
    LOW_RISK_THRESHOLD = 0.2
    
    def __init__(self):
        """Initialize the predictive expiration service."""
        self.pattern_engine = get_pattern_analysis_engine()
        self.threat_service = get_threat_intelligence_service()
    
    def analyze_password_pattern(
        self,
        password: str
    ) -> PatternFingerprint:
        """
        Analyze a password to extract its structural pattern.
        
        Args:
            password: The password to analyze
            
        Returns:
            PatternFingerprint with analysis results
        """
        return self.pattern_engine.analyze_password(password)
    
    def calculate_exposure_risk(
        self,
        password: str,
        user_id: int,
        credential_domain: str,
        credential_age_days: int
    ) -> RiskScore:
        """
        Calculate comprehensive exposure risk for a credential.
        
        Combines pattern analysis, threat intelligence, industry
        context, and credential age into an overall risk score.
        
        Args:
            password: The password to analyze
            user_id: The user's ID
            credential_domain: Domain/service for this credential
            credential_age_days: Age of the credential in days
            
        Returns:
            RiskScore with detailed breakdown
        """
        factors = []
        
        # 1. Pattern Risk
        pattern = self.pattern_engine.analyze_password(password)
        pattern_risk = self._calculate_pattern_risk(pattern)
        
        if pattern_risk > 0.5:
            factors.append("Password follows predictable patterns")
        if pattern.has_dictionary_base:
            factors.append("Contains dictionary words")
        if pattern.keyboard_patterns:
            factors.append("Contains keyboard patterns")
        if 'leet' in pattern.mutations:
            factors.append("Uses common l33t substitutions")
        
        # 2. Threat Risk
        threat_level = self.threat_service.get_real_time_threat_level(
            user_id, credential_domain
        )
        threat_risk = threat_level.score
        factors.extend(threat_level.factors)
        
        # 3. Industry Risk
        industry_risk = self._calculate_industry_risk(user_id)
        if industry_risk > 0.5:
            factors.append("Your industry is currently targeted")
        
        # 4. Age Risk
        age_risk = self._calculate_age_risk(credential_age_days)
        if age_risk > 0.5:
            factors.append(f"Password is {credential_age_days} days old")
        
        # Calculate weighted overall score
        overall_score = (
            pattern_risk * self.PATTERN_WEIGHT +
            threat_risk * self.THREAT_WEIGHT +
            industry_risk * self.INDUSTRY_WEIGHT +
            age_risk * self.AGE_WEIGHT
        )
        
        # Calculate confidence based on data availability
        confidence = self._calculate_confidence(
            pattern, threat_level, credential_age_days
        )
        
        return RiskScore(
            overall_score=min(overall_score, 1.0),
            pattern_risk=pattern_risk,
            threat_risk=threat_risk,
            industry_risk=industry_risk,
            age_risk=age_risk,
            factors=factors,
            confidence=confidence,
        )
    
    def predict_compromise_timeline(
        self,
        password: str,
        user_id: int,
        credential_domain: str,
        credential_age_days: int
    ) -> PredictionResult:
        """
        Predict when a password might be compromised.
        
        Uses risk factors to estimate a timeline for potential
        credential compromise.
        
        Args:
            password: The password to analyze
            user_id: The user's ID
            credential_domain: Domain/service for this credential
            credential_age_days: Age of the credential in days
            
        Returns:
            PredictionResult with predicted compromise date
        """
        # Calculate risk score
        risk = self.calculate_exposure_risk(
            password, user_id, credential_domain, credential_age_days
        )
        
        # Predict timeline based on risk
        if risk.overall_score >= 0.9:
            # Critical risk - could be compromised any time
            days_until = 7
            risk_level = 'critical'
        elif risk.overall_score >= 0.7:
            # High risk - weeks
            days_until = int(30 * (1 - risk.overall_score))
            risk_level = 'high'
        elif risk.overall_score >= 0.5:
            # Medium risk - months
            days_until = int(90 * (1 - risk.overall_score))
            risk_level = 'medium'
        elif risk.overall_score >= 0.3:
            # Low risk - several months
            days_until = int(180 * (1 - risk.overall_score))
            risk_level = 'low'
        else:
            # Minimal risk
            days_until = None
            risk_level = 'minimal'
        
        predicted_date = None
        if days_until is not None:
            predicted_date = timezone.now() + timedelta(days=days_until)
        
        return PredictionResult(
            predicted_date=predicted_date,
            confidence=risk.confidence,
            risk_level=risk_level,
            contributing_factors=risk.factors,
            days_until_predicted=days_until,
        )
    
    def should_force_rotation(
        self,
        password: str,
        user_id: int,
        credential_domain: str,
        credential_age_days: int
    ) -> Tuple[bool, List[str]]:
        """
        Determine if a password should be forcibly rotated.
        
        Args:
            password: The password to analyze
            user_id: The user's ID
            credential_domain: Domain/service for this credential
            credential_age_days: Age of the credential in days
            
        Returns:
            Tuple of (should_rotate, list_of_reasons)
        """
        from ..models import PredictiveExpirationSettings
        from django.contrib.auth.models import User
        
        # Get user's rotation threshold
        try:
            user = User.objects.get(id=user_id)
            settings = PredictiveExpirationSettings.objects.get(user=user)
            threshold = settings.force_rotation_threshold
        except (User.DoesNotExist, PredictiveExpirationSettings.DoesNotExist):
            threshold = 0.8  # Default threshold
        
        # Calculate risk
        risk = self.calculate_exposure_risk(
            password, user_id, credential_domain, credential_age_days
        )
        
        reasons = []
        should_rotate = False
        
        # Check against threshold
        if risk.overall_score >= threshold:
            should_rotate = True
            reasons.append(f"Risk score {risk.overall_score:.2%} exceeds threshold")
        
        # Check for critical threat factors
        if risk.threat_risk >= 0.8:
            should_rotate = True
            reasons.append("Critical threat level detected")
        
        # Check for very old passwords
        if credential_age_days > 365:
            should_rotate = True
            reasons.append("Password older than 1 year")
        
        # Add contributing factors to reasons
        if should_rotate:
            reasons.extend(risk.factors[:3])  # Top 3 factors
        
        return should_rotate, reasons
    
    def generate_rotation_recommendation(
        self,
        password: str,
        user_id: int,
        credential_domain: str,
        credential_age_days: int
    ) -> RotationPlan:
        """
        Generate a comprehensive rotation recommendation.
        
        Provides timing, urgency, and requirements for password
        rotation based on current risk assessment.
        
        Args:
            password: The password to analyze
            user_id: The user's ID
            credential_domain: Domain/service for this credential
            credential_age_days: Age of the credential in days
            
        Returns:
            RotationPlan with recommendations
        """
        # Check if rotation is needed
        should_rotate, reasons = self.should_force_rotation(
            password, user_id, credential_domain, credential_age_days
        )
        
        if not should_rotate:
            # Still calculate prediction for planning
            prediction = self.predict_compromise_timeline(
                password, user_id, credential_domain, credential_age_days
            )
            
            if prediction.risk_level in ['medium', 'high']:
                # Recommend proactive rotation
                return RotationPlan(
                    should_rotate=True,
                    urgency='low' if prediction.risk_level == 'medium' else 'medium',
                    recommended_date=prediction.predicted_date - timedelta(days=7)
                                     if prediction.predicted_date else None,
                    reasons=[f"Proactive rotation recommended: {prediction.risk_level} risk"],
                    new_password_requirements=self._generate_requirements(password),
                )
            else:
                return RotationPlan(
                    should_rotate=False,
                    urgency='none',
                    recommended_date=None,
                    reasons=["No immediate rotation needed"],
                    new_password_requirements={},
                )
        
        # Determine urgency based on risk
        risk = self.calculate_exposure_risk(
            password, user_id, credential_domain, credential_age_days
        )
        
        if risk.overall_score >= 0.9:
            urgency = 'critical'
            recommended_date = timezone.now()  # Immediately
        elif risk.overall_score >= 0.7:
            urgency = 'high'
            recommended_date = timezone.now() + timedelta(days=3)
        elif risk.overall_score >= 0.5:
            urgency = 'medium'
            recommended_date = timezone.now() + timedelta(days=7)
        else:
            urgency = 'low'
            recommended_date = timezone.now() + timedelta(days=14)
        
        return RotationPlan(
            should_rotate=True,
            urgency=urgency,
            recommended_date=recommended_date,
            reasons=reasons,
            new_password_requirements=self._generate_requirements(password),
        )
    
    @transaction.atomic
    def update_user_pattern_profile(self, user_id: int) -> None:
        """
        Update a user's password pattern profile.
        
        Analyzes all user credentials to build a comprehensive
        pattern profile for vulnerability assessment.
        
        Args:
            user_id: The user's ID
        """
        from ..models import PasswordPatternProfile
        from django.contrib.auth.models import User
        
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            logger.warning(f"User {user_id} not found for pattern update")
            return
        
        # Get or create profile
        profile, created = PasswordPatternProfile.objects.get_or_create(
            user=user
        )
        
        # In a real implementation, this would iterate over vault entries
        # For now, we just update the timestamp
        profile.last_analysis_at = timezone.now()
        profile.save()
        
        logger.info(f"Updated pattern profile for user {user_id}")
    
    @transaction.atomic
    def create_expiration_rule(
        self,
        user_id: int,
        credential_id: str,
        credential_domain: str,
        password: str,
        credential_age_days: int
    ) -> 'PredictiveExpirationRule':
        """
        Create or update an expiration rule for a credential.
        
        Args:
            user_id: The user's ID
            credential_id: UUID of the credential
            credential_domain: Domain/service for this credential
            password: The password to analyze
            credential_age_days: Age of the credential in days
            
        Returns:
            The created/updated PredictiveExpirationRule
        """
        from ..models import PredictiveExpirationRule
        from django.contrib.auth.models import User
        import uuid
        
        user = User.objects.get(id=user_id)
        
        # Calculate risk and prediction
        risk = self.calculate_exposure_risk(
            password, user_id, credential_domain, credential_age_days
        )
        prediction = self.predict_compromise_timeline(
            password, user_id, credential_domain, credential_age_days
        )
        rotation = self.generate_rotation_recommendation(
            password, user_id, credential_domain, credential_age_days
        )
        
        # Map risk level
        if risk.overall_score >= 0.8:
            risk_level = 'critical'
        elif risk.overall_score >= 0.6:
            risk_level = 'high'
        elif risk.overall_score >= 0.4:
            risk_level = 'medium'
        elif risk.overall_score >= 0.2:
            risk_level = 'low'
        else:
            risk_level = 'minimal'
        
        # Map recommended action
        action_map = {
            'critical': 'rotate_immediately',
            'high': 'rotate_soon',
            'medium': 'plan_rotation',
            'low': 'monitor',
            'none': 'no_action',
        }
        recommended_action = action_map.get(rotation.urgency, 'no_action')
        
        # Create or update rule
        rule, created = PredictiveExpirationRule.objects.update_or_create(
            user=user,
            credential_id=uuid.UUID(credential_id),
            defaults={
                'credential_domain': credential_domain,
                'risk_level': risk_level,
                'risk_score': risk.overall_score,
                'predicted_compromise_date': prediction.predicted_date.date()
                                              if prediction.predicted_date else None,
                'prediction_confidence': prediction.confidence,
                'threat_factors': risk.factors,
                'pattern_similarity_score': risk.pattern_risk,
                'industry_threat_correlation': risk.industry_risk,
                'recommended_action': recommended_action,
                'recommended_rotation_date': rotation.recommended_date.date()
                                              if rotation.recommended_date else None,
                'last_evaluated_at': timezone.now(),
            }
        )
        
        logger.info(
            f"{'Created' if created else 'Updated'} expiration rule "
            f"for credential {credential_id}: {risk_level} risk"
        )
        
        return rule
    
    def _calculate_pattern_risk(self, pattern: PatternFingerprint) -> float:
        """Calculate risk score based on password pattern."""
        risk = 0.0
        
        # Short passwords are higher risk
        if pattern.length < 8:
            risk += 0.4
        elif pattern.length < 12:
            risk += 0.2
        elif pattern.length < 16:
            risk += 0.1
        
        # Dictionary base words increase risk
        if pattern.has_dictionary_base:
            risk += 0.3
        
        # Keyboard patterns increase risk
        if pattern.keyboard_patterns:
            risk += 0.25
        
        # Leet speak is easily reversed
        if 'leet' in pattern.mutations:
            risk += 0.15
        
        # Low entropy increases risk
        if pattern.entropy_estimate < 30:
            risk += 0.2
        elif pattern.entropy_estimate < 50:
            risk += 0.1
        
        return min(risk, 1.0)
    
    def _calculate_industry_risk(self, user_id: int) -> float:
        """Calculate risk based on user's industry."""
        from ..models import PredictiveExpirationSettings, IndustryThreatLevel
        from django.contrib.auth.models import User
        
        try:
            user = User.objects.get(id=user_id)
            settings = PredictiveExpirationSettings.objects.get(user=user)
            
            if settings.industry:
                try:
                    industry = IndustryThreatLevel.objects.get(
                        industry_code=settings.industry
                    )
                    return industry.threat_score
                except IndustryThreatLevel.DoesNotExist:
                    pass
        except (User.DoesNotExist, PredictiveExpirationSettings.DoesNotExist):
            pass
        
        return 0.2  # Default low industry risk
    
    def _calculate_age_risk(self, age_days: int) -> float:
        """Calculate risk based on credential age."""
        if age_days > 365:
            return 0.8
        elif age_days > 180:
            return 0.5
        elif age_days > 90:
            return 0.3
        elif age_days > 30:
            return 0.1
        else:
            return 0.0
    
    def _calculate_confidence(
        self,
        pattern: PatternFingerprint,
        threat_level: ThreatLevel,
        age_days: int
    ) -> float:
        """Calculate confidence in the risk assessment."""
        confidence = 0.5  # Base confidence
        
        # More factors = higher confidence
        if pattern.detected_base_words:
            confidence += 0.1
        if threat_level.active_threats:
            confidence += 0.15
        if age_days > 0:
            confidence += 0.1
        if len(threat_level.factors) > 2:
            confidence += 0.1
        
        return min(confidence, 0.95)
    
    def _generate_requirements(self, current_password: str) -> Dict:
        """Generate requirements for a new password."""
        pattern = self.pattern_engine.analyze_password(current_password)
        
        requirements = {
            'min_length': max(16, len(current_password) + 4),
            'require_uppercase': True,
            'require_lowercase': True,
            'require_digits': True,
            'require_symbols': True,
            'avoid_patterns': [],
        }
        
        # Avoid previous patterns
        if pattern.keyboard_patterns:
            requirements['avoid_patterns'].append('keyboard_walks')
        if pattern.has_dictionary_base:
            requirements['avoid_patterns'].append('dictionary_words')
        if 'leet' in pattern.mutations:
            requirements['avoid_patterns'].append('leet_substitutions')
        
        return requirements


# Singleton instance
_expiration_service: Optional[PredictiveExpirationService] = None


def get_predictive_expiration_service() -> PredictiveExpirationService:
    """Get the singleton predictive expiration service instance."""
    global _expiration_service
    if _expiration_service is None:
        _expiration_service = PredictiveExpirationService()
    return _expiration_service
