"""
Predictive Intent API Views
============================

REST API endpoints for AI-powered password prediction:
- Get predictions for current context
- Process context signals
- Manage settings
- Record feedback
- Get statistics

@author Password Manager Team
@created 2026-02-06
"""

import logging
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone

from password_manager.api_utils import success_response, error_response
from .services.predictive_intent_service import get_predictive_intent_service
from .predictive_intent_models import (
    IntentPrediction,
    PreloadedCredential,
    PredictionFeedback,
    PredictiveIntentSettings,
    PasswordUsagePattern,
)

logger = logging.getLogger(__name__)


# =============================================================================
# PREDICTIONS
# =============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_predictions(request):
    """
    Get current password predictions based on context.
    
    Query Parameters:
    - domain: Current domain (optional)
    - include_expired: Include expired predictions (default: false)
    
    Returns:
    {
        "success": true,
        "predictions": [
            {
                "id": "uuid",
                "vault_item_id": "uuid",
                "vault_item_name": "...",
                "confidence": 0.85,
                "reason": "time_pattern",
                "rank": 1,
                "expires_at": "datetime"
            }
        ]
    }
    """
    try:
        service = get_predictive_intent_service()
        
        domain = request.query_params.get('domain', '')
        include_expired = request.query_params.get('include_expired', 'false').lower() == 'true'
        
        # Build context from query params
        context = {
            'current_domain': domain,
            'hour_of_day': timezone.now().hour,
            'day_of_week': timezone.now().weekday(),
        }
        
        # Get predictions
        predictions = service.get_predictions(request.user, context)
        
        # Serialize
        prediction_data = []
        for pred in predictions:
            item = pred.predicted_vault_item
            prediction_data.append({
                'id': str(pred.id),
                'vault_item_id': str(item.id),
                'vault_item_name': item.encrypted_data[:50] + '...' if item.encrypted_data else 'Unknown',
                'vault_item_type': item.item_type,
                'confidence': round(pred.confidence_score, 3),
                'reason': pred.prediction_reason,
                'reason_details': pred.reason_details,
                'rank': pred.rank,
                'trigger_domain': pred.trigger_domain,
                'expires_at': pred.expires_at.isoformat(),
            })
        
        return success_response({
            'predictions': prediction_data,
            'generated_at': timezone.now().isoformat(),
        })
        
    except Exception as e:
        logger.error(f"Failed to get predictions: {e}")
        return error_response(
            "Failed to get predictions",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# =============================================================================
# CONTEXT SIGNALS
# =============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_context_signal(request):
    """
    Send a context signal for prediction triggering.
    
    POST Data:
    {
        "domain": "example.com",
        "url_hash": "sha256 hash" (optional),
        "page_title": "Login - Example" (optional),
        "form_fields": ["username", "password"] (optional),
        "time_on_page": 5 (seconds, optional),
        "is_new_tab": false (optional),
        "device_type": "desktop" (optional)
    }
    
    Returns:
    {
        "success": true,
        "signal_id": "uuid",
        "should_predict": true,
        "predictions": [...],
        "login_probability": 0.85
    }
    """
    try:
        service = get_predictive_intent_service()
        
        domain = request.data.get('domain', '')
        if not domain:
            return error_response("Domain is required")
        
        result = service.process_context_signal(
            user=request.user,
            domain=domain,
            url_hash=request.data.get('url_hash'),
            page_title=request.data.get('page_title'),
            form_fields=request.data.get('form_fields'),
            time_on_page=request.data.get('time_on_page', 0),
            is_new_tab=request.data.get('is_new_tab', False),
            device_type=request.data.get('device_type', 'desktop'),
        )
        
        return success_response({
            'signal_id': result['signal_id'],
            'should_predict': result['analysis']['should_predict'],
            'login_probability': result['analysis']['login_probability'],
            'domain_category': result['analysis']['domain_category'],
            'predictions': result['predictions'],
        })
        
    except Exception as e:
        logger.error(f"Failed to process context signal: {e}")
        return error_response(
            "Failed to process context signal",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# =============================================================================
# FEEDBACK
# =============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def record_prediction_feedback(request):
    """
    Record feedback on a prediction.
    
    POST Data:
    {
        "prediction_id": "uuid",
        "feedback_type": "used|dismissed|wrong|helpful|not_helpful",
        "time_to_use_ms": 1500 (optional),
        "alternative_item_id": "uuid" (optional),
        "rating": 4 (optional, 1-5),
        "comment": "..." (optional)
    }
    
    Returns:
    {
        "success": true,
        "feedback_id": "uuid"
    }
    """
    try:
        service = get_predictive_intent_service()
        
        prediction_id = request.data.get('prediction_id')
        feedback_type = request.data.get('feedback_type')
        
        if not prediction_id or not feedback_type:
            return error_response("prediction_id and feedback_type are required")
        
        valid_types = ['used', 'dismissed', 'wrong', 'helpful', 'not_helpful', 'timeout', 'alternative']
        if feedback_type not in valid_types:
            return error_response(f"Invalid feedback_type. Must be one of: {valid_types}")
        
        # Get alternative item if provided
        alternative_item = None
        alt_id = request.data.get('alternative_item_id')
        if alt_id:
            from vault.models import EncryptedVaultItem
            try:
                alternative_item = EncryptedVaultItem.objects.get(
                    id=alt_id,
                    user=request.user,
                    deleted=False,
                )
            except EncryptedVaultItem.DoesNotExist:
                pass
        
        feedback = service.record_feedback(
            user=request.user,
            prediction_id=prediction_id,
            feedback_type=feedback_type,
            time_to_use_ms=request.data.get('time_to_use_ms'),
            alternative_item=alternative_item,
            rating=request.data.get('rating'),
            comment=request.data.get('comment'),
        )
        
        if feedback is None:
            return error_response("Prediction not found", status_code=status.HTTP_404_NOT_FOUND)
        
        return success_response({
            'feedback_id': str(feedback.id),
        })
        
    except Exception as e:
        logger.error(f"Failed to record feedback: {e}")
        return error_response(
            "Failed to record feedback",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# =============================================================================
# PRELOADED CREDENTIALS
# =============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_preloaded_credentials(request):
    """
    Get preloaded credentials ready for instant access.
    
    Returns:
    {
        "success": true,
        "preloaded": [
            {
                "id": "uuid",
                "vault_item_id": "uuid",
                "confidence": 0.9,
                "requires_biometric": false,
                "expires_at": "datetime"
            }
        ]
    }
    """
    try:
        preloaded = PreloadedCredential.objects.filter(
            user=request.user,
            expires_at__gt=timezone.now(),
            was_used=False,
        ).select_related('vault_item', 'prediction').order_by('-confidence_at_preload')[:10]
        
        preloaded_data = [
            {
                'id': str(p.id),
                'vault_item_id': str(p.vault_item_id),
                'confidence': round(p.confidence_at_preload, 3),
                'reason': p.preload_reason,
                'requires_biometric': p.requires_biometric,
                'expires_at': p.expires_at.isoformat(),
            }
            for p in preloaded
        ]
        
        return success_response({
            'preloaded': preloaded_data,
        })
        
    except Exception as e:
        logger.error(f"Failed to get preloaded credentials: {e}")
        return error_response(
            "Failed to get preloaded credentials",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# =============================================================================
# SETTINGS
# =============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_intent_settings(request):
    """
    Get user's predictive intent settings.
    
    Returns:
    {
        "success": true,
        "settings": {
            "is_enabled": true,
            "min_confidence_threshold": 0.7,
            ...
        }
    }
    """
    try:
        service = get_predictive_intent_service()
        settings_obj = service.get_or_create_settings(request.user)
        
        return success_response({
            'settings': {
                'is_enabled': settings_obj.is_enabled,
                'learn_from_vault_access': settings_obj.learn_from_vault_access,
                'learn_from_autofill': settings_obj.learn_from_autofill,
                'show_predictions': settings_obj.show_predictions,
                'min_confidence_threshold': settings_obj.min_confidence_threshold,
                'preload_confidence_threshold': settings_obj.preload_confidence_threshold,
                'max_predictions_shown': settings_obj.max_predictions_shown,
                'max_preloaded': settings_obj.max_preloaded,
                'excluded_domains': settings_obj.excluded_domains,
                'pattern_retention_days': settings_obj.pattern_retention_days,
                'notify_high_confidence': settings_obj.notify_high_confidence,
            }
        })
        
    except Exception as e:
        logger.error(f"Failed to get intent settings: {e}")
        return error_response(
            "Failed to get settings",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def update_intent_settings(request):
    """
    Update user's predictive intent settings.
    
    PUT/PATCH Data:
    {
        "is_enabled": true,
        "min_confidence_threshold": 0.7,
        ...
    }
    
    Returns:
    {
        "success": true,
        "settings": {...}
    }
    """
    try:
        service = get_predictive_intent_service()
        
        settings_obj = service.update_settings(
            request.user,
            **request.data
        )
        
        return success_response({
            'settings': {
                'is_enabled': settings_obj.is_enabled,
                'learn_from_vault_access': settings_obj.learn_from_vault_access,
                'learn_from_autofill': settings_obj.learn_from_autofill,
                'show_predictions': settings_obj.show_predictions,
                'min_confidence_threshold': settings_obj.min_confidence_threshold,
                'preload_confidence_threshold': settings_obj.preload_confidence_threshold,
                'max_predictions_shown': settings_obj.max_predictions_shown,
                'max_preloaded': settings_obj.max_preloaded,
                'excluded_domains': settings_obj.excluded_domains,
                'pattern_retention_days': settings_obj.pattern_retention_days,
                'notify_high_confidence': settings_obj.notify_high_confidence,
            }
        })
        
    except Exception as e:
        logger.error(f"Failed to update intent settings: {e}")
        return error_response(
            "Failed to update settings",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# =============================================================================
# STATISTICS
# =============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_intent_statistics(request):
    """
    Get prediction statistics for the user.
    
    Returns:
    {
        "success": true,
        "statistics": {
            "total_predictions": 150,
            "predictions_used": 120,
            "accuracy": 80.0,
            ...
        }
    }
    """
    try:
        service = get_predictive_intent_service()
        stats = service.get_statistics(request.user)
        
        return success_response({
            'statistics': stats,
        })
        
    except Exception as e:
        logger.error(f"Failed to get statistics: {e}")
        return error_response(
            "Failed to get statistics",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# =============================================================================
# USAGE PATTERN RECORDING
# =============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def record_usage(request):
    """
    Record a password usage event for learning.
    
    POST Data:
    {
        "vault_item_id": "uuid",
        "domain": "example.com",
        "access_method": "browse|search|autofill|prediction|quick_access",
        "device_fingerprint": "hash" (optional),
        "previous_item_id": "uuid" (optional),
        "time_to_access_ms": 1500 (optional)
    }
    
    Returns:
    {
        "success": true,
        "pattern_id": "uuid"
    }
    """
    try:
        service = get_predictive_intent_service()
        
        vault_item_id = request.data.get('vault_item_id')
        domain = request.data.get('domain', '')
        
        if not vault_item_id:
            return error_response("vault_item_id is required")
        
        from vault.models import EncryptedVaultItem
        try:
            vault_item = EncryptedVaultItem.objects.get(
                id=vault_item_id,
                user=request.user,
                deleted=False,
            )
        except EncryptedVaultItem.DoesNotExist:
            return error_response("Vault item not found", status_code=status.HTTP_404_NOT_FOUND)
        
        # Get previous item if provided
        previous_item = None
        prev_id = request.data.get('previous_item_id')
        if prev_id:
            try:
                previous_item = EncryptedVaultItem.objects.get(
                    id=prev_id,
                    user=request.user,
                    deleted=False,
                )
            except EncryptedVaultItem.DoesNotExist:
                pass
        
        pattern = service.learn_usage_pattern(
            user=request.user,
            vault_item=vault_item,
            domain=domain,
            access_method=request.data.get('access_method', 'browse'),
            device_fingerprint=request.data.get('device_fingerprint'),
            previous_item=previous_item,
            time_to_access_ms=request.data.get('time_to_access_ms'),
        )
        
        if pattern is None:
            return success_response({
                'pattern_id': None,
                'message': 'Learning disabled or domain excluded',
            })
        
        return success_response({
            'pattern_id': str(pattern.id),
        })
        
    except Exception as e:
        logger.error(f"Failed to record usage: {e}")
        return error_response(
            "Failed to record usage",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
