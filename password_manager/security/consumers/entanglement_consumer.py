"""
Entanglement WebSocket Consumer
===============================

Real-time WebSocket notifications for quantum entanglement events.

Handles:
- Sync status updates
- Anomaly alerts
- Entropy health changes
"""

import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)


class EntanglementConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time entanglement updates.
    
    Provides:
    - Sync notifications when keys are synchronized
    - Anomaly alerts when issues are detected
    - Entropy status updates
    """
    
    async def connect(self):
        """Handle WebSocket connection."""
        self.user = self.scope.get("user")
        
        if not self.user or not self.user.is_authenticated:
            await self.close(code=4001)
            return
        
        self.user_group = f"entanglement_{self.user.id}"
        
        # Join user-specific group
        await self.channel_layer.group_add(
            self.user_group,
            self.channel_name
        )
        
        await self.accept()
        
        logger.info(f"WebSocket connected for user {self.user.id}")
        
        # Send initial connection status
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'message': 'Connected to entanglement notifications'
        }))
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        if hasattr(self, 'user_group'):
            await self.channel_layer.group_discard(
                self.user_group,
                self.channel_name
            )
        
        logger.info(f"WebSocket disconnected: {close_code}")
    
    async def receive(self, text_data):
        """Handle incoming WebSocket messages."""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'ping':
                await self.send(text_data=json.dumps({
                    'type': 'pong'
                }))
            elif message_type == 'subscribe_pair':
                pair_id = data.get('pair_id')
                if pair_id:
                    await self._subscribe_to_pair(pair_id)
        except json.JSONDecodeError:
            logger.error("Invalid JSON received")
    
    async def _subscribe_to_pair(self, pair_id: str):
        """Subscribe to updates for a specific pair."""
        pair_group = f"entanglement_pair_{pair_id}"
        await self.channel_layer.group_add(
            pair_group,
            self.channel_name
        )
        await self.send(text_data=json.dumps({
            'type': 'subscribed',
            'pair_id': pair_id
        }))
    
    # =========================================================================
    # Message Handlers (called by channel layer)
    # =========================================================================
    
    async def sync_notification(self, event):
        """Send sync status update to client."""
        await self.send(text_data=json.dumps({
            'type': 'sync_notification',
            'data': event['data']
        }))
    
    async def anomaly_alert(self, event):
        """Send anomaly alert to client."""
        await self.send(text_data=json.dumps({
            'type': 'anomaly_alert',
            'data': event['data']
        }))
    
    async def entropy_update(self, event):
        """Send entropy status update to client."""
        await self.send(text_data=json.dumps({
            'type': 'entropy_update',
            'data': event['data']
        }))
    
    async def pair_revoked(self, event):
        """Send pair revocation notification to client."""
        await self.send(text_data=json.dumps({
            'type': 'pair_revoked',
            'data': event['data']
        }))


# =========================================================================
# Helper functions for sending notifications from other parts of the app
# =========================================================================

async def send_sync_notification(user_id: int, pair_id: str, data: dict):
    """Send sync notification to user's WebSocket."""
    from channels.layers import get_channel_layer
    
    channel_layer = get_channel_layer()
    if channel_layer:
        await channel_layer.group_send(
            f"entanglement_{user_id}",
            {
                'type': 'sync_notification',
                'data': {
                    'pair_id': pair_id,
                    **data
                }
            }
        )


async def send_anomaly_alert(user_id: int, pair_id: str, anomaly_data: dict):
    """Send anomaly alert to user's WebSocket."""
    from channels.layers import get_channel_layer
    
    channel_layer = get_channel_layer()
    if channel_layer:
        await channel_layer.group_send(
            f"entanglement_{user_id}",
            {
                'type': 'anomaly_alert',
                'data': {
                    'pair_id': pair_id,
                    **anomaly_data
                }
            }
        )


async def send_entropy_update(user_id: int, pair_id: str, entropy_data: dict):
    """Send entropy update to user's WebSocket."""
    from channels.layers import get_channel_layer
    
    channel_layer = get_channel_layer()
    if channel_layer:
        await channel_layer.group_send(
            f"entanglement_{user_id}",
            {
                'type': 'entropy_update',
                'data': {
                    'pair_id': pair_id,
                    **entropy_data
                }
            }
        )


async def send_revocation_notice(user_id: int, pair_id: str, reason: str):
    """Send pair revocation notice to user's WebSocket."""
    from channels.layers import get_channel_layer
    
    channel_layer = get_channel_layer()
    if channel_layer:
        await channel_layer.group_send(
            f"entanglement_{user_id}",
            {
                'type': 'pair_revoked',
                'data': {
                    'pair_id': pair_id,
                    'reason': reason
                }
            }
        )
