"""
Predictive Intent WebSocket Consumer
=====================================

Real-time WebSocket consumer for pushing password predictions
to browser extension and mobile app.

Features:
- Context signal processing with instant prediction response
- Preloaded credential delivery
- Real-time feedback collection

@author Password Manager Team
@created 2026-02-07
"""

import json
import logging
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)


class PredictiveIntentConsumer(AsyncJsonWebsocketConsumer):
    """
    WebSocket consumer for real-time predictive intent features.
    
    Handles:
    - Context signals from browser extension
    - Prediction delivery
    - Feedback collection
    """
    
    async def connect(self):
        """Handle WebSocket connection."""
        self.user = self.scope.get('user')
        
        if not self.user or not self.user.is_authenticated:
            await self.close(code=4001)
            return
        
        self.user_id = self.user.id
        self.room_name = f"predictions_{self.user_id}"
        
        # Join user-specific room
        await self.channel_layer.group_add(
            self.room_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Send connection confirmation
        await self.send_json({
            'type': 'connection_established',
            'user_id': self.user_id,
            'timestamp': timezone.now().isoformat(),
        })
        
        logger.info(f"Predictive intent WebSocket connected for user {self.user_id}")
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        if hasattr(self, 'room_name'):
            await self.channel_layer.group_discard(
                self.room_name,
                self.channel_name
            )
        
        logger.info(f"Predictive intent WebSocket disconnected: {close_code}")
    
    async def receive_json(self, content):
        """Handle incoming JSON messages."""
        message_type = content.get('type')
        
        handlers = {
            'context_signal': self.handle_context_signal,
            'get_predictions': self.handle_get_predictions,
            'feedback': self.handle_feedback,
            'ping': self.handle_ping,
        }
        
        handler = handlers.get(message_type)
        if handler:
            try:
                await handler(content)
            except Exception as e:
                logger.error(f"Error handling {message_type}: {e}")
                await self.send_json({
                    'type': 'error',
                    'message': str(e),
                    'original_type': message_type,
                })
        else:
            await self.send_json({
                'type': 'error',
                'message': f'Unknown message type: {message_type}',
            })
    
    async def handle_context_signal(self, content):
        """
        Process context signal and return predictions.
        
        Expected content:
        {
            "type": "context_signal",
            "domain": "example.com",
            "url_hash": "sha256...",
            "page_title": "Login Page",
            "form_fields": ["username", "password"],
            "device_type": "desktop"
        }
        """
        result = await self.process_context_signal(
            domain=content.get('domain', ''),
            url_hash=content.get('url_hash'),
            page_title=content.get('page_title'),
            form_fields=content.get('form_fields'),
            time_on_page=content.get('time_on_page', 0),
            is_new_tab=content.get('is_new_tab', False),
            device_type=content.get('device_type', 'desktop'),
        )
        
        await self.send_json({
            'type': 'context_response',
            'signal_id': result.get('signal_id'),
            'should_predict': result.get('analysis', {}).get('should_predict', False),
            'login_probability': result.get('analysis', {}).get('login_probability', 0),
            'predictions': result.get('predictions', []),
            'timestamp': timezone.now().isoformat(),
        })
    
    async def handle_get_predictions(self, content):
        """
        Get predictions for current context.
        
        Expected content:
        {
            "type": "get_predictions",
            "domain": "example.com"
        }
        """
        predictions = await self.get_predictions(
            domain=content.get('domain', '')
        )
        
        await self.send_json({
            'type': 'predictions',
            'predictions': predictions,
            'timestamp': timezone.now().isoformat(),
        })
    
    async def handle_feedback(self, content):
        """
        Record feedback on a prediction.
        
        Expected content:
        {
            "type": "feedback",
            "prediction_id": "uuid",
            "feedback_type": "used|dismissed|wrong",
            "time_to_use_ms": 1500
        }
        """
        success = await self.record_feedback(
            prediction_id=content.get('prediction_id'),
            feedback_type=content.get('feedback_type'),
            time_to_use_ms=content.get('time_to_use_ms'),
        )
        
        await self.send_json({
            'type': 'feedback_recorded',
            'success': success,
            'prediction_id': content.get('prediction_id'),
        })
    
    async def handle_ping(self, content):
        """Respond to ping with pong."""
        await self.send_json({
            'type': 'pong',
            'timestamp': timezone.now().isoformat(),
        })
    
    # =========================================================================
    # Database Operations (async wrappers)
    # =========================================================================
    
    @database_sync_to_async
    def process_context_signal(self, **kwargs):
        """Process context signal in database."""
        from .services.predictive_intent_service import get_predictive_intent_service
        
        service = get_predictive_intent_service()
        return service.process_context_signal(
            user=self.user,
            **kwargs
        )
    
    @database_sync_to_async
    def get_predictions(self, domain):
        """Get predictions from database."""
        from .services.predictive_intent_service import get_predictive_intent_service
        
        service = get_predictive_intent_service()
        context = {
            'current_domain': domain,
            'hour_of_day': timezone.now().hour,
            'day_of_week': timezone.now().weekday(),
        }
        
        predictions = service.get_predictions(self.user, context)
        
        return [
            {
                'id': str(p.id),
                'vault_item_id': str(p.predicted_vault_item_id),
                'confidence': round(p.confidence_score, 3),
                'reason': p.prediction_reason,
                'rank': p.rank,
            }
            for p in predictions
        ]
    
    @database_sync_to_async
    def record_feedback(self, prediction_id, feedback_type, time_to_use_ms=None):
        """Record feedback in database."""
        from .services.predictive_intent_service import get_predictive_intent_service
        
        if not prediction_id or not feedback_type:
            return False
        
        service = get_predictive_intent_service()
        feedback = service.record_feedback(
            user=self.user,
            prediction_id=prediction_id,
            feedback_type=feedback_type,
            time_to_use_ms=time_to_use_ms,
        )
        
        return feedback is not None
    
    # =========================================================================
    # Push notifications (called from other parts of the app)
    # =========================================================================
    
    async def prediction_ready(self, event):
        """
        Handle prediction ready event (pushed from service).
        
        Called when new predictions are generated that should
        be pushed to the client.
        """
        await self.send_json({
            'type': 'prediction_push',
            'predictions': event.get('predictions', []),
            'trigger_domain': event.get('trigger_domain'),
            'timestamp': timezone.now().isoformat(),
        })
    
    async def credential_preloaded(self, event):
        """
        Handle credential preloaded event.
        
        Notifies client that a credential is ready for instant access.
        """
        await self.send_json({
            'type': 'credential_ready',
            'vault_item_id': event.get('vault_item_id'),
            'confidence': event.get('confidence'),
            'requires_biometric': event.get('requires_biometric', False),
            'timestamp': timezone.now().isoformat(),
        })


# =============================================================================
# Utility Functions
# =============================================================================

async def push_predictions_to_user(user_id: int, predictions: list, trigger_domain: str = None):
    """
    Push predictions to a user's WebSocket connection.
    
    Can be called from views or Celery tasks to send real-time updates.
    
    Args:
        user_id: User ID
        predictions: List of prediction dicts
        trigger_domain: Domain that triggered the predictions
    """
    from channels.layers import get_channel_layer
    
    channel_layer = get_channel_layer()
    room_name = f"predictions_{user_id}"
    
    await channel_layer.group_send(
        room_name,
        {
            'type': 'prediction_ready',
            'predictions': predictions,
            'trigger_domain': trigger_domain,
        }
    )


async def push_credential_ready(user_id: int, vault_item_id: str, confidence: float, requires_biometric: bool = False):
    """
    Notify user that a credential is preloaded and ready.
    
    Args:
        user_id: User ID
        vault_item_id: Vault item ID
        confidence: Confidence score
        requires_biometric: Whether biometric is required
    """
    from channels.layers import get_channel_layer
    
    channel_layer = get_channel_layer()
    room_name = f"predictions_{user_id}"
    
    await channel_layer.group_send(
        room_name,
        {
            'type': 'credential_preloaded',
            'vault_item_id': vault_item_id,
            'confidence': confidence,
            'requires_biometric': requires_biometric,
        }
    )
