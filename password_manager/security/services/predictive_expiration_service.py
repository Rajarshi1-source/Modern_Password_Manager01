"""
Predictive Expiration Service
==============================

Core service for predicting password compromise and managing
proactive rotations based on threat intelligence.

Combines pattern analysis, threat intelligence, and user context
to provide risk assessments for each credential.
"""

import hashlib
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models import PredictiveExpirationRule

from .pattern_analysis_engine import (
    PatternAnalysisEngine,
    PatternFingerprint,
    build_fingerprint_from_metadata,
    get_pattern_analysis_engine,
)
from .threat_intelligence_service import (
    ThreatIntelligenceService,
    ThreatLevel,
    get_threat_intelligence_service
)

logger = logging.getLogger(__name__)


class _DictLikeMixin:
    """Expose dataclass fields via subscript / membership so that legacy
    tests which treat these results as plain dicts keep working."""

    # Aliases for legacy keys
    _ALIASES: Dict[str, str] = {}

    def __getitem__(self, key):
        if key in self._ALIASES:
            key = self._ALIASES[key]
        return getattr(self, key)

    def __contains__(self, key):
        if key in self._ALIASES:
            key = self._ALIASES[key]
        return hasattr(self, key)

    def get(self, key, default=None):
        try:
            return self[key]
        except AttributeError:
            return default


@dataclass
class RiskScore(_DictLikeMixin):
    """Represents a comprehensive risk score for a credential."""
    overall_score: float  # 0-1
    pattern_risk: float
    threat_risk: float
    industry_risk: float
    age_risk: float
    factors: List[str]
    confidence: float

    _ALIASES = {'risk_score': 'overall_score'}

    @property
    def risk_level(self):
        s = self.overall_score
        if s >= 0.8:
            return 'critical'
        if s >= 0.6:
            return 'high'
        if s >= 0.4:
            return 'medium'
        if s >= 0.2:
            return 'low'
        return 'minimal'


@dataclass
class PredictionResult(_DictLikeMixin):
    """Result of compromise timeline prediction."""
    predicted_date: Optional[datetime]
    confidence: float
    risk_level: str
    contributing_factors: List[str]
    days_until_predicted: Optional[int]


@dataclass
class RotationPlan(_DictLikeMixin):
    """Recommended rotation plan for a credential."""
    should_rotate: bool
    urgency: str  # 'none', 'low', 'medium', 'high', 'critical'
    recommended_date: Optional[datetime]
    reasons: List[str]
    new_password_requirements: Dict

    @property
    def action(self) -> str:
        """Map urgency to the action vocabulary used by callers/tests."""
        mapping = {
            'critical': 'rotate_immediately',
            'high': 'rotate_soon',
            'medium': 'schedule_rotation',
            'low': 'monitor',
            'none': 'no_action',
        }
        return mapping.get(self.urgency, 'monitor')


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
        password: str = None,
        user_id: int = None,
        credential_domain: str = '',
        credential_age_days: int = 0,
        domain: str = None,
        age_days: int = None,
        fingerprint: PatternFingerprint = None,
    ):
        """
        Calculate comprehensive exposure risk for a credential.

        Combines pattern analysis, threat intelligence, industry
        context, and credential age into an overall risk score.

        Args:
            password: The password to analyze. Optional — prefer
                ``fingerprint`` for the zero-knowledge path. When given, the
                structural fingerprint is derived locally (server-side use /
                tests only); it is never accepted over the network.
            user_id: The user's ID
            credential_domain: Domain/service for this credential
            credential_age_days: Age of the credential in days
            fingerprint: A pre-computed :class:`PatternFingerprint` (client
                fingerprint path). Takes precedence over ``password``.

        Returns:
            RiskScore with detailed breakdown
        """
        # Accept alias kwargs used by tests
        if domain is not None and not credential_domain:
            credential_domain = domain
        if age_days is not None and not credential_age_days:
            credential_age_days = age_days

        pattern = (
            fingerprint
            if fingerprint is not None
            else self.pattern_engine.analyze_password(password or '')
        )
        return self._risk_from_pattern(
            pattern, user_id, credential_domain, credential_age_days
        )

    def calculate_exposure_risk_from_fingerprint(
        self,
        fingerprint: PatternFingerprint,
        user_id: int = None,
        credential_domain: str = '',
        credential_age_days: int = 0,
    ):
        """Zero-knowledge exposure-risk entry point.

        Identical math to :meth:`calculate_exposure_risk` but only ever takes
        an irreversible structural fingerprint — no plaintext path.
        """
        return self._risk_from_pattern(
            fingerprint, user_id, credential_domain, credential_age_days
        )

    def _risk_from_pattern(
        self,
        pattern: PatternFingerprint,
        user_id: int = None,
        credential_domain: str = '',
        credential_age_days: int = 0,
    ):
        """Score exposure risk from an already-computed pattern fingerprint.

        Shared by both the (server-side/test) password path and the
        zero-knowledge client-fingerprint path. Reads only structural fields,
        so it is agnostic to how the fingerprint was produced.
        """
        factors = []

        # 1. Pattern Risk
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
        password: str = None,
        user_id: int = None,
        credential_domain: str = '',
        credential_age_days: int = 0,
        domain: str = None,
        age_days: int = None,
        fingerprint: PatternFingerprint = None,
    ) -> PredictionResult:
        if domain is not None and not credential_domain:
            credential_domain = domain
        if age_days is not None and not credential_age_days:
            credential_age_days = age_days
        return self._predict_compromise_timeline_impl(
            password, user_id, credential_domain, credential_age_days,
            fingerprint=fingerprint,
        )

    def _predict_compromise_timeline_impl(
        self,
        password: str,
        user_id: int,
        credential_domain: str,
        credential_age_days: int,
        fingerprint: PatternFingerprint = None,
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
            password, user_id, credential_domain, credential_age_days,
            fingerprint=fingerprint,
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
        password: str = None,
        user_id: int = None,
        credential_domain: str = '',
        credential_age_days: int = 0,
        domain: str = None,
        age_days: int = None,
        fingerprint: PatternFingerprint = None,
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

        if domain is not None and not credential_domain:
            credential_domain = domain
        if age_days is not None and not credential_age_days:
            credential_age_days = age_days

        # Get user's rotation threshold
        threshold = 0.8  # Default threshold
        if user_id is not None:
            try:
                user = User.objects.get(id=user_id)
                settings = PredictiveExpirationSettings.objects.get(user=user)
                threshold = settings.force_rotation_threshold
            except (User.DoesNotExist, PredictiveExpirationSettings.DoesNotExist):
                pass
        
        # Calculate risk
        risk = self.calculate_exposure_risk(
            password, user_id, credential_domain, credential_age_days,
            fingerprint=fingerprint,
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
        password: str = None,
        user_id: int = None,
        credential_domain: str = '',
        credential_age_days: int = 0,
        domain: str = None,
        age_days: int = None,
        fingerprint: PatternFingerprint = None,
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
        if domain is not None and not credential_domain:
            credential_domain = domain
        if age_days is not None and not credential_age_days:
            credential_age_days = age_days

        # Resolve the pattern once so requirement generation works on the
        # fingerprint path (where no plaintext password is available).
        req_pattern = (
            fingerprint
            if fingerprint is not None
            else self.pattern_engine.analyze_password(password or '')
        )

        # Check if rotation is needed
        should_rotate, reasons = self.should_force_rotation(
            password, user_id, credential_domain, credential_age_days,
            fingerprint=fingerprint,
        )

        if not should_rotate:
            # Still calculate prediction for planning
            prediction = self.predict_compromise_timeline(
                password, user_id, credential_domain, credential_age_days,
                fingerprint=fingerprint,
            )

            if prediction.risk_level in ['medium', 'high']:
                # Recommend proactive rotation
                return RotationPlan(
                    should_rotate=True,
                    urgency='low' if prediction.risk_level == 'medium' else 'medium',
                    recommended_date=prediction.predicted_date - timedelta(days=7)
                                     if prediction.predicted_date else None,
                    reasons=[f"Proactive rotation recommended: {prediction.risk_level} risk"],
                    new_password_requirements=self._generate_requirements(pattern=req_pattern),
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
            password, user_id, credential_domain, credential_age_days,
            fingerprint=fingerprint,
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
            new_password_requirements=self._generate_requirements(pattern=req_pattern),
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
            credential_id=credential_id,
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

    def _compute_salted_structure_hash(
        self,
        char_class_sequence: str,
        length_bucket: str,
    ) -> str:
        """Compute a per-deployment salted hash of the structure fingerprint.

        Salting with a deployment secret means that even if the rules table
        leaks, identical password *shapes* across users (or against a
        precomputed rainbow table of char-class sequences) cannot be matched.
        """
        salt = getattr(settings, 'PREDICTIVE_FINGERPRINT_SALT', '') or settings.SECRET_KEY
        payload = f"{salt}:{char_class_sequence}:{length_bucket}"
        return hashlib.sha256(payload.encode()).hexdigest()

    @transaction.atomic
    def create_expiration_rule_from_fingerprint(
        self,
        *,
        user_id: int,
        credential_id: str,
        credential_domain: str = '',
        domain_class: str = '',
        char_class_sequence: str,
        length: int = None,
        length_bucket: str = '',
        entropy_band: str = '',
        entropy_estimate: float = None,
        has_dictionary_base: bool = False,
        has_keyboard_pattern: bool = False,
        has_date_pattern: bool = False,
        has_leet: bool = False,
        structure_hash: str = '',
        credential_age_days: int = 0,
    ) -> 'PredictiveExpirationRule':
        """Create/update an expiration rule from a zero-knowledge fingerprint.

        This is the ingest counterpart to :meth:`create_expiration_rule`: it
        never receives a password. The browser computes the structural
        fingerprint locally and uploads only the irreversible fields below;
        the server scores risk and persists the structural metadata so the
        daily re-score task can refresh risk without ever needing plaintext.
        """
        from ..models import PredictiveExpirationRule
        from django.contrib.auth.models import User

        user = User.objects.get(id=user_id)

        fingerprint = build_fingerprint_from_metadata(
            char_class_sequence=char_class_sequence,
            length=length,
            entropy_band=entropy_band,
            entropy_estimate=entropy_estimate,
            has_dictionary_base=has_dictionary_base,
            has_keyboard_pattern=has_keyboard_pattern,
            has_date_pattern=has_date_pattern,
            has_leet=has_leet,
            structure_hash=structure_hash,
        )

        risk = self.calculate_exposure_risk_from_fingerprint(
            fingerprint, user_id, credential_domain, credential_age_days
        )
        prediction = self.predict_compromise_timeline(
            user_id=user_id,
            credential_domain=credential_domain,
            credential_age_days=credential_age_days,
            fingerprint=fingerprint,
        )
        rotation = self.generate_rotation_recommendation(
            user_id=user_id,
            credential_domain=credential_domain,
            credential_age_days=credential_age_days,
            fingerprint=fingerprint,
        )

        action_map = {
            'critical': 'rotate_immediately',
            'high': 'rotate_soon',
            'medium': 'plan_rotation',
            'low': 'monitor',
            'none': 'no_action',
        }
        recommended_action = action_map.get(rotation.urgency, 'no_action')

        rule, created = PredictiveExpirationRule.objects.update_or_create(
            user=user,
            credential_id=credential_id,
            defaults={
                'credential_domain': credential_domain,
                'domain_class': domain_class,
                'char_class_sequence': char_class_sequence,
                'structure_hash': self._compute_salted_structure_hash(
                    char_class_sequence, length_bucket
                ),
                'length_bucket': length_bucket,
                'entropy_band': entropy_band,
                'credential_age_days': credential_age_days,
                'has_dictionary_base': has_dictionary_base,
                'has_keyboard_pattern': has_keyboard_pattern,
                'has_date_pattern': has_date_pattern,
                'has_leet': has_leet,
                'risk_level': risk.risk_level,
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
                'is_active': True,
                'last_evaluated_at': timezone.now(),
            }
        )

        logger.info(
            f"{'Created' if created else 'Updated'} ZK expiration rule "
            f"for credential {credential_id}: {risk.risk_level} risk"
        )

        return rule

    @transaction.atomic
    def update_user_pattern_profile_from_fingerprints(
        self,
        user_id: int,
        fingerprints: List[Dict],
    ) -> None:
        """Aggregate a batch of client fingerprints into the user profile.

        Replaces the legacy stub that only bumped a timestamp. Computes the
        aggregate char-class distribution, length stats, and habit flags from
        the uploaded structural metadata — never from passwords.
        """
        from ..models import PasswordPatternProfile
        from django.contrib.auth.models import User

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            logger.warning(f"User {user_id} not found for pattern update")
            return

        profile, _ = PasswordPatternProfile.objects.get_or_create(user=user)

        if not fingerprints:
            profile.last_analysis_at = timezone.now()
            profile.save()
            return

        class_counts = {'U': 0, 'L': 0, 'D': 0, 'S': 0}
        lengths = []
        flags = {
            'uses_common_base_words': False,
            'uses_keyboard_patterns': False,
            'uses_date_patterns': False,
            'uses_leet_substitutions': False,
        }

        for fp in fingerprints:
            seq = fp.get('char_class_sequence', '') or ''
            for ch in seq:
                if ch in class_counts:
                    class_counts[ch] += 1
            lengths.append(fp.get('length') or len(seq))
            flags['uses_common_base_words'] |= bool(fp.get('has_dictionary_base'))
            flags['uses_keyboard_patterns'] |= bool(fp.get('has_keyboard_pattern'))
            flags['uses_date_patterns'] |= bool(fp.get('has_date_pattern'))
            flags['uses_leet_substitutions'] |= bool(fp.get('has_leet'))

        total_chars = sum(class_counts.values()) or 1
        profile.char_class_distribution = {
            'uppercase': class_counts['U'] / total_chars,
            'lowercase': class_counts['L'] / total_chars,
            'digits': class_counts['D'] / total_chars,
            'special': class_counts['S'] / total_chars,
        }
        if lengths:
            mean_len = sum(lengths) / len(lengths)
            profile.avg_password_length = mean_len
            profile.min_length_used = min(lengths)
            profile.max_length_used = max(lengths)
            profile.length_variance = (
                sum((x - mean_len) ** 2 for x in lengths) / len(lengths)
            )
        profile.uses_common_base_words = flags['uses_common_base_words']
        profile.uses_keyboard_patterns = flags['uses_keyboard_patterns']
        profile.uses_date_patterns = flags['uses_date_patterns']
        profile.uses_leet_substitutions = flags['uses_leet_substitutions']
        profile.total_passwords_analyzed = len(fingerprints)
        profile.weak_patterns_detected = sum(
            1 for fp in fingerprints
            if fp.get('has_dictionary_base') or fp.get('has_keyboard_pattern')
        )
        profile.last_analysis_at = timezone.now()
        profile.save()

        logger.info(
            f"Updated pattern profile for user {user_id} from "
            f"{len(fingerprints)} fingerprints"
        )

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
    
    def _generate_requirements(
        self,
        current_password: str = None,
        pattern: PatternFingerprint = None,
    ) -> Dict:
        """Generate requirements for a new password.

        Works from either a plaintext password (server-side/test path) or a
        pre-computed structural ``pattern`` (zero-knowledge fingerprint path),
        deriving the minimum length from the fingerprint's length so no
        plaintext is required.
        """
        if pattern is None:
            pattern = self.pattern_engine.analyze_password(current_password or '')

        requirements = {
            'min_length': max(16, pattern.length + 4),
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
