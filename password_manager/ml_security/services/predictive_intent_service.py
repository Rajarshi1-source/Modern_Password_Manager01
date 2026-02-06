"""
Predictive Intent Service
==========================

Core service for AI-powered password prediction.

Orchestrates:
- Usage pattern learning
- Intent prediction generation
- Credential preloading
- Feedback collection

@author Password Manager Team
@created 2026-02-06
"""

import logging
import hashlib
import secrets
from datetime import timedelta
from typing import List, Dict, Any, Optional
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from django.contrib.auth.models import User

from ..predictive_intent_models import (
    PasswordUsagePattern,
    IntentPrediction,
    ContextSignal,
    PreloadedCredential,
    PredictionFeedback,
    PredictiveIntentSettings,
)
from vault.models import EncryptedVaultItem
from .intent_predictor import get_intent_predictor
from .context_analyzer import get_context_analyzer

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================

def get_predictive_config() -> Dict[str, Any]:
    """Get predictive intent configuration from settings."""
    return getattr(settings, 'PREDICTIVE_INTENT', {
        'ENABLED': True,
        'MIN_CONFIDENCE': 0.7,
        'MAX_PREDICTIONS': 5,
        'PRELOAD_COUNT': 3,
        'PATTERN_HISTORY_DAYS': 90,
        'PRELOAD_EXPIRY_MINUTES': 15,
        'LEARN_FROM_VAULT_ACCESS': True,
        'LEARN_FROM_AUTOFILL': True,
    })


# =============================================================================
# Predictive Intent Service
# =============================================================================

class PredictiveIntentService:
    """
    Service for AI-powered password prediction.
    
    Learns from user behavior and predicts which passwords
    will be needed, enabling instant access.
    """
    
    def __init__(self):
        self.config = get_predictive_config()
        self._intent_predictor = None
        self._context_analyzer = None
    
    @property
    def intent_predictor(self):
        """Lazy load intent predictor."""
        if self._intent_predictor is None:
            self._intent_predictor = get_intent_predictor()
        return self._intent_predictor
    
    @property
    def context_analyzer(self):
        """Lazy load context analyzer."""
        if self._context_analyzer is None:
            self._context_analyzer = get_context_analyzer()
        return self._context_analyzer
    
    # =========================================================================
    # Settings Management
    # =========================================================================
    
    def get_or_create_settings(self, user: User) -> PredictiveIntentSettings:
        """Get or create user's predictive intent settings."""
        settings_obj, created = PredictiveIntentSettings.objects.get_or_create(
            user=user,
            defaults={
                'is_enabled': True,
                'min_confidence_threshold': self.config.get('MIN_CONFIDENCE', 0.7),
                'max_predictions_shown': self.config.get('MAX_PREDICTIONS', 5),
            }
        )
        if created:
            logger.info(f"Created predictive intent settings for user {user.id}")
        return settings_obj
    
    def update_settings(self, user: User, **kwargs) -> PredictiveIntentSettings:
        """Update user's predictive intent settings."""
        settings_obj = self.get_or_create_settings(user)
        
        allowed_fields = [
            'is_enabled', 'learn_from_vault_access', 'learn_from_autofill',
            'show_predictions', 'min_confidence_threshold', 
            'preload_confidence_threshold', 'max_predictions_shown',
            'max_preloaded', 'excluded_domains', 'pattern_retention_days',
            'notify_high_confidence',
        ]
        
        for field, value in kwargs.items():
            if field in allowed_fields:
                setattr(settings_obj, field, value)
        
        settings_obj.save()
        logger.info(f"Updated predictive intent settings for user {user.id}")
        return settings_obj
    
    # =========================================================================
    # Pattern Learning
    # =========================================================================
    
    def learn_usage_pattern(
        self,
        user: User,
        vault_item: EncryptedVaultItem,
        domain: str,
        access_method: str = 'browse',
        device_fingerprint: str = None,
        location_hint: str = None,
        referrer_domain: str = None,
        previous_item: EncryptedVaultItem = None,
        session_position: int = 1,
        time_to_access_ms: int = None,
    ) -> PasswordUsagePattern:
        """
        Record a password usage pattern for learning.
        
        Args:
            user: The user
            vault_item: The accessed vault item
            domain: Domain where accessed
            access_method: How the password was accessed
            device_fingerprint: Device identifier (will be hashed)
            location_hint: Location hint (will be hashed)
            referrer_domain: Previous domain (will be hashed)
            previous_item: Previously accessed item in session
            session_position: Position in access sequence
            time_to_access_ms: Time to access in milliseconds
            
        Returns:
            Created PasswordUsagePattern
        """
        settings_obj = self.get_or_create_settings(user)
        
        # Check if learning is enabled
        if not settings_obj.is_enabled or not settings_obj.learn_from_vault_access:
            return None
        
        # Check excluded domains
        normalized_domain = self._normalize_domain(domain)
        if normalized_domain in settings_obj.excluded_domains:
            return None
        
        now = timezone.now()
        
        # Determine time of day
        hour = now.hour
        if 5 <= hour < 8:
            time_of_day = 'early_morning'
        elif 8 <= hour < 12:
            time_of_day = 'morning'
        elif 12 <= hour < 17:
            time_of_day = 'afternoon'
        elif 17 <= hour < 21:
            time_of_day = 'evening'
        elif 21 <= hour < 24:
            time_of_day = 'night'
        else:
            time_of_day = 'late_night'
        
        # Classify domain category
        domain_category = self.context_analyzer.classify_domain(domain)
        
        # Create pattern record
        pattern = PasswordUsagePattern.objects.create(
            user=user,
            vault_item=vault_item,
            access_time=now,
            day_of_week=now.weekday(),
            time_of_day=time_of_day,
            hour_of_day=hour,
            domain=normalized_domain,
            domain_category=domain_category or '',
            device_fingerprint_hash=self._hash_value(device_fingerprint) if device_fingerprint else '',
            location_hash=self._hash_value(location_hint) if location_hint else '',
            referrer_domain_hash=self._hash_value(referrer_domain) if referrer_domain else '',
            previous_vault_item=previous_item,
            session_sequence_position=session_position,
            access_method=access_method,
            time_to_access_ms=time_to_access_ms,
        )
        
        logger.debug(f"Recorded usage pattern for user {user.id}: {vault_item.id}")
        
        # Update vault item's last_used_at
        vault_item.last_used_at = now
        vault_item.save(update_fields=['last_used_at'])
        
        return pattern
    
    # =========================================================================
    # Prediction Generation
    # =========================================================================
    
    def get_predictions(
        self,
        user: User,
        context: Dict[str, Any],
        max_predictions: int = None,
    ) -> List[IntentPrediction]:
        """
        Get password predictions for the current context.
        
        Args:
            user: The user
            context: Current context (domain, time, etc.)
            max_predictions: Override max predictions
            
        Returns:
            List of IntentPrediction objects
        """
        settings_obj = self.get_or_create_settings(user)
        
        if not settings_obj.is_enabled or not settings_obj.show_predictions:
            return []
        
        # Check excluded domain
        current_domain = context.get('current_domain', '')
        if self._normalize_domain(current_domain) in settings_obj.excluded_domains:
            return []
        
        # Get historical patterns
        cutoff = timezone.now() - timedelta(
            days=settings_obj.pattern_retention_days
        )
        patterns = PasswordUsagePattern.objects.filter(
            user=user,
            access_time__gte=cutoff,
        ).select_related('vault_item', 'previous_vault_item').order_by('-access_time')[:1000]
        
        # Convert to dict format for predictor
        pattern_dicts = [
            {
                'vault_item_id': str(p.vault_item_id),
                'domain': p.domain,
                'domain_category': p.domain_category,
                'day_of_week': p.day_of_week,
                'hour_of_day': p.hour_of_day,
                'time_of_day': p.time_of_day,
                'previous_vault_item_id': str(p.previous_vault_item_id) if p.previous_vault_item_id else None,
            }
            for p in patterns
        ]
        
        # Enrich context
        now = timezone.now()
        enriched_context = {
            **context,
            'hour_of_day': context.get('hour_of_day', now.hour),
            'day_of_week': context.get('day_of_week', now.weekday()),
        }
        
        # Generate predictions
        max_preds = max_predictions or settings_obj.max_predictions_shown
        min_conf = settings_obj.min_confidence_threshold
        
        raw_predictions = self.intent_predictor.predict(
            user_id=user.id,
            context=enriched_context,
            usage_patterns=pattern_dicts,
            max_predictions=max_preds,
            min_confidence=min_conf,
        )
        
        if not raw_predictions:
            return []
        
        # Create IntentPrediction records
        predictions = []
        expires_at = timezone.now() + timedelta(
            minutes=self.config.get('PRELOAD_EXPIRY_MINUTES', 15)
        )
        
        with transaction.atomic():
            # Expire old predictions for this user
            IntentPrediction.objects.filter(
                user=user,
                expires_at__gt=timezone.now(),
                was_used__isnull=True,
            ).update(expires_at=timezone.now())
            
            for pred in raw_predictions:
                try:
                    vault_item = EncryptedVaultItem.objects.get(
                        id=pred['vault_item_id'],
                        user=user,
                        deleted=False,
                    )
                except EncryptedVaultItem.DoesNotExist:
                    continue
                
                prediction = IntentPrediction.objects.create(
                    user=user,
                    predicted_vault_item=vault_item,
                    confidence_score=pred['confidence'],
                    prediction_reason=pred.get('reason', 'combined'),
                    reason_details=pred.get('details', {}),
                    rank=pred.get('rank', 1),
                    trigger_domain=current_domain,
                    trigger_context=enriched_context,
                    expires_at=expires_at,
                )
                predictions.append(prediction)
        
        logger.info(
            f"Generated {len(predictions)} predictions for user {user.id} "
            f"on domain {current_domain}"
        )
        
        return predictions
    
    # =========================================================================
    # Context Signal Processing
    # =========================================================================
    
    def process_context_signal(
        self,
        user: User,
        domain: str,
        url_hash: str = None,
        page_title: str = None,
        form_fields: List[str] = None,
        time_on_page: int = 0,
        is_new_tab: bool = False,
        device_type: str = 'desktop',
    ) -> Dict[str, Any]:
        """
        Process a context signal and potentially generate predictions.
        
        Args:
            user: The user
            domain: Current domain
            url_hash: Hash of full URL
            page_title: Page title
            form_fields: Detected form fields
            time_on_page: Seconds on page
            is_new_tab: Whether new tab
            device_type: Device type
            
        Returns:
            Dict with analysis results and predictions
        """
        settings_obj = self.get_or_create_settings(user)
        
        if not settings_obj.is_enabled:
            return {'predictions': [], 'should_predict': False}
        
        # Analyze context
        analysis = self.context_analyzer.analyze_context(
            domain=domain,
            url_hash=url_hash,
            page_title=page_title,
            form_fields=form_fields,
            time_on_page=time_on_page,
            is_new_tab=is_new_tab,
            device_type=device_type,
        )
        
        # Record context signal
        signal = ContextSignal.objects.create(
            user=user,
            current_domain=domain,
            current_url_hash=url_hash or '',
            page_title_keywords=self.context_analyzer.extract_page_keywords(page_title or ''),
            active_form_detected=bool(form_fields),
            login_form_probability=analysis['login_probability'],
            form_fields_detected=form_fields or [],
            time_on_page_seconds=time_on_page,
            is_new_tab=is_new_tab,
            device_type=device_type,
        )
        
        # Generate predictions if appropriate
        predictions = []
        if analysis['should_predict']:
            context = {
                'current_domain': domain,
                'login_probability': analysis['login_probability'],
                'domain_category': analysis['domain_category'],
                'device_type': device_type,
            }
            predictions = self.get_predictions(user, context)
            
            # Mark signal as processed
            signal.predictions_generated = True
            signal.save(update_fields=['predictions_generated'])
        
        return {
            'signal_id': str(signal.id),
            'analysis': analysis,
            'predictions': [
                {
                    'id': str(p.id),
                    'vault_item_id': str(p.predicted_vault_item_id),
                    'confidence': p.confidence_score,
                    'reason': p.prediction_reason,
                    'rank': p.rank,
                }
                for p in predictions
            ],
        }
    
    # =========================================================================
    # Credential Preloading
    # =========================================================================
    
    def preload_credentials(
        self,
        user: User,
        session_key: bytes,
        session_key_id: str,
    ) -> List[PreloadedCredential]:
        """
        Preload high-confidence credentials for instant access.
        
        Args:
            user: The user
            session_key: Session encryption key
            session_key_id: Session key identifier
            
        Returns:
            List of preloaded credentials
        """
        settings_obj = self.get_or_create_settings(user)
        
        if not settings_obj.is_enabled:
            return []
        
        # Get recent high-confidence predictions
        predictions = IntentPrediction.objects.filter(
            user=user,
            expires_at__gt=timezone.now(),
            was_used__isnull=True,
            confidence_score__gte=settings_obj.preload_confidence_threshold,
        ).select_related('predicted_vault_item').order_by('-confidence_score')[:settings_obj.max_preloaded]
        
        preloaded = []
        expires_at = timezone.now() + timedelta(
            minutes=self.config.get('PRELOAD_EXPIRY_MINUTES', 15)
        )
        
        for prediction in predictions:
            # Check if already preloaded
            existing = PreloadedCredential.objects.filter(
                user=user,
                vault_item=prediction.predicted_vault_item,
                expires_at__gt=timezone.now(),
            ).exists()
            
            if existing:
                continue
            
            # In production, encrypt the credential with session key
            # For now, create placeholder
            iv = secrets.token_bytes(16)
            encrypted = b'placeholder_encrypted_credential'
            
            preload = PreloadedCredential.objects.create(
                user=user,
                vault_item=prediction.predicted_vault_item,
                prediction=prediction,
                encrypted_credential=encrypted,
                encryption_iv=iv,
                session_key_id=session_key_id,
                preload_reason=prediction.prediction_reason,
                confidence_at_preload=prediction.confidence_score,
                expires_at=expires_at,
                requires_biometric=settings_obj.preload_confidence_threshold < 0.9,
            )
            preloaded.append(preload)
        
        logger.info(f"Preloaded {len(preloaded)} credentials for user {user.id}")
        return preloaded
    
    # =========================================================================
    # Feedback Recording
    # =========================================================================
    
    def record_feedback(
        self,
        user: User,
        prediction_id: str,
        feedback_type: str,
        time_to_use_ms: int = None,
        alternative_item: EncryptedVaultItem = None,
        rating: int = None,
        comment: str = None,
    ) -> PredictionFeedback:
        """
        Record feedback on a prediction for model improvement.
        
        Args:
            user: The user
            prediction_id: Prediction ID
            feedback_type: Type of feedback
            time_to_use_ms: Time to use in ms
            alternative_item: Alternative item if used
            rating: Optional explicit rating
            comment: Optional user comment
            
        Returns:
            Created PredictionFeedback
        """
        try:
            prediction = IntentPrediction.objects.get(
                id=prediction_id,
                user=user,
            )
        except IntentPrediction.DoesNotExist:
            logger.warning(f"Prediction {prediction_id} not found")
            return None
        
        # Update prediction outcome
        was_correct = feedback_type in ['used', 'helpful']
        
        if feedback_type == 'used':
            prediction.was_used = True
            prediction.used_at = timezone.now()
        elif feedback_type == 'dismissed':
            prediction.was_dismissed = True
        elif feedback_type == 'alternative':
            prediction.alternative_item_used = alternative_item
        
        prediction.save()
        
        # Create feedback record
        feedback = PredictionFeedback.objects.create(
            prediction=prediction,
            user=user,
            feedback_type=feedback_type,
            was_correct=was_correct,
            time_to_use_ms=time_to_use_ms,
            alternative_item=alternative_item,
            explicit_rating=rating,
            user_comment=comment or '',
        )
        
        logger.info(
            f"Recorded feedback for prediction {prediction_id}: {feedback_type}"
        )
        
        return feedback
    
    # =========================================================================
    # Statistics
    # =========================================================================
    
    def get_statistics(self, user: User) -> Dict[str, Any]:
        """
        Get prediction statistics for a user.
        
        Args:
            user: The user
            
        Returns:
            Statistics dict
        """
        now = timezone.now()
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)
        
        # Prediction counts
        total_predictions = IntentPrediction.objects.filter(
            user=user
        ).count()
        
        predictions_used = IntentPrediction.objects.filter(
            user=user,
            was_used=True,
        ).count()
        
        predictions_dismissed = IntentPrediction.objects.filter(
            user=user,
            was_dismissed=True,
        ).count()
        
        # Calculate accuracy
        accuracy = 0.0
        if total_predictions > 0:
            accuracy = predictions_used / total_predictions
        
        # Recent trends
        recent_predictions = IntentPrediction.objects.filter(
            user=user,
            predicted_at__gte=week_ago,
        ).count()
        
        recent_used = IntentPrediction.objects.filter(
            user=user,
            was_used=True,
            predicted_at__gte=week_ago,
        ).count()
        
        recent_accuracy = 0.0
        if recent_predictions > 0:
            recent_accuracy = recent_used / recent_predictions
        
        # Pattern counts
        pattern_count = PasswordUsagePattern.objects.filter(
            user=user,
        ).count()
        
        # Top domains
        from django.db.models import Count
        top_domains = list(
            PasswordUsagePattern.objects.filter(
                user=user,
                access_time__gte=month_ago,
            ).values('domain').annotate(
                count=Count('id')
            ).order_by('-count')[:10]
        )
        
        return {
            'total_predictions': total_predictions,
            'predictions_used': predictions_used,
            'predictions_dismissed': predictions_dismissed,
            'accuracy': round(accuracy * 100, 1),
            'recent_accuracy': round(recent_accuracy * 100, 1),
            'pattern_count': pattern_count,
            'top_domains': top_domains,
            'is_enabled': self.get_or_create_settings(user).is_enabled,
        }
    
    # =========================================================================
    # Utility Methods
    # =========================================================================
    
    def _normalize_domain(self, domain: str) -> str:
        """Normalize domain for comparison."""
        if not domain:
            return ''
        
        domain = domain.lower().strip()
        
        for prefix in ['www.', 'mail.', 'login.', 'auth.', 'accounts.']:
            if domain.startswith(prefix):
                domain = domain[len(prefix):]
        
        return domain
    
    def _hash_value(self, value: str) -> str:
        """Create privacy-preserving hash."""
        if not value:
            return ''
        return hashlib.sha256(value.encode()).hexdigest()


# =============================================================================
# Service Singleton
# =============================================================================

_predictive_intent_service = None


def get_predictive_intent_service() -> PredictiveIntentService:
    """Get the predictive intent service singleton."""
    global _predictive_intent_service
    if _predictive_intent_service is None:
        _predictive_intent_service = PredictiveIntentService()
    return _predictive_intent_service
