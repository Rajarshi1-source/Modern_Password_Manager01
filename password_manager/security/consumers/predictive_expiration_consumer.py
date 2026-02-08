"""
Predictive Expiration WebSocket Consumer
==========================================

Real-time WebSocket notifications for predictive password expiration alerts.
Sends notifications when:
- A credential's risk level changes to high/critical
- A forced rotation is required
- Threat intelligence updates affect user's credentials
"""

import json
import logging
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone

logger = logging.getLogger(__name__)


class PredictiveExpirationConsumer(AsyncJsonWebsocketConsumer):
    """
    WebSocket consumer for real-time predictive expiration updates.
    
    Message Types:
    - risk_alert: New high/critical risk detected
    - rotation_required: Forced rotation needed
    - threat_update: Threat landscape changed
    - risk_updated: Risk score changed for a credential
    - bulk_scan_complete: Daily scan completed
    """
    
    async def connect(self):
        """Handle WebSocket connection."""
        self.user = self.scope.get("user")
        
        if not self.user or not self.user.is_authenticated:
            logger.warning("Unauthenticated WebSocket connection attempt")
            await self.close()
            return
            
        self.user_group = f"predictive_expiration_{self.user.id}"
        
        # Join user's personal group
        await self.channel_layer.group_add(
            self.user_group,
            self.channel_name
        )
        
        # Join global threat updates group
        await self.channel_layer.group_add(
            "predictive_expiration_global",
            self.channel_name
        )
        
        await self.accept()
        
        logger.info(f"WebSocket connected for user {self.user.id}")
        
        # Send initial connection confirmation
        await self.send_json({
            "type": "connection_established",
            "message": "Connected to predictive expiration alerts",
            "timestamp": timezone.now().isoformat()
        })
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        if hasattr(self, 'user_group'):
            await self.channel_layer.group_discard(
                self.user_group,
                self.channel_name
            )
        
        await self.channel_layer.group_discard(
            "predictive_expiration_global",
            self.channel_name
        )
        
        logger.info(f"WebSocket disconnected: {close_code}")
    
    async def receive_json(self, content):
        """Handle incoming WebSocket messages."""
        message_type = content.get("type")
        
        if message_type == "subscribe":
            # Subscribe to specific credential updates
            credential_id = content.get("credential_id")
            if credential_id:
                await self.channel_layer.group_add(
                    f"credential_{credential_id}",
                    self.channel_name
                )
                await self.send_json({
                    "type": "subscribed",
                    "credential_id": credential_id
                })
        
        elif message_type == "unsubscribe":
            credential_id = content.get("credential_id")
            if credential_id:
                await self.channel_layer.group_discard(
                    f"credential_{credential_id}",
                    self.channel_name
                )
                await self.send_json({
                    "type": "unsubscribed",
                    "credential_id": credential_id
                })
        
        elif message_type == "ping":
            await self.send_json({
                "type": "pong",
                "timestamp": timezone.now().isoformat()
            })
    
    # =========================================================================
    # Event Handlers (called by channel layer group_send)
    # =========================================================================
    
    async def risk_alert(self, event):
        """Handle high/critical risk alert."""
        await self.send_json({
            "type": "risk_alert",
            "credential_id": event.get("credential_id"),
            "credential_domain": event.get("credential_domain"),
            "risk_level": event.get("risk_level"),
            "risk_score": event.get("risk_score"),
            "message": event.get("message"),
            "timestamp": event.get("timestamp", timezone.now().isoformat())
        })
    
    async def rotation_required(self, event):
        """Handle forced rotation requirement."""
        await self.send_json({
            "type": "rotation_required",
            "credential_id": event.get("credential_id"),
            "credential_domain": event.get("credential_domain"),
            "reason": event.get("reason"),
            "urgency": event.get("urgency", "high"),
            "timestamp": event.get("timestamp", timezone.now().isoformat())
        })
    
    async def threat_update(self, event):
        """Handle threat landscape update."""
        await self.send_json({
            "type": "threat_update",
            "threat_actor": event.get("threat_actor"),
            "threat_level": event.get("threat_level"),
            "affected_industries": event.get("affected_industries", []),
            "affected_credentials_count": event.get("affected_credentials_count", 0),
            "message": event.get("message"),
            "timestamp": event.get("timestamp", timezone.now().isoformat())
        })
    
    async def risk_updated(self, event):
        """Handle risk score change for a credential."""
        await self.send_json({
            "type": "risk_updated",
            "credential_id": event.get("credential_id"),
            "old_risk_level": event.get("old_risk_level"),
            "new_risk_level": event.get("new_risk_level"),
            "new_risk_score": event.get("new_risk_score"),
            "timestamp": event.get("timestamp", timezone.now().isoformat())
        })
    
    async def bulk_scan_complete(self, event):
        """Handle daily scan completion notification."""
        await self.send_json({
            "type": "bulk_scan_complete",
            "credentials_scanned": event.get("credentials_scanned", 0),
            "high_risk_count": event.get("high_risk_count", 0),
            "critical_count": event.get("critical_count", 0),
            "timestamp": event.get("timestamp", timezone.now().isoformat())
        })


# =============================================================================
# Helper Functions for Sending Notifications
# =============================================================================

async def send_risk_alert(user_id, credential_id, credential_domain, risk_level, risk_score, message=None):
    """Send a risk alert to a specific user."""
    from channels.layers import get_channel_layer
    channel_layer = get_channel_layer()
    
    await channel_layer.group_send(
        f"predictive_expiration_{user_id}",
        {
            "type": "risk_alert",
            "credential_id": str(credential_id),
            "credential_domain": credential_domain,
            "risk_level": risk_level,
            "risk_score": risk_score,
            "message": message or f"High risk detected for {credential_domain}",
            "timestamp": timezone.now().isoformat()
        }
    )


async def send_rotation_required(user_id, credential_id, credential_domain, reason, urgency="high"):
    """Send a rotation required notification to a specific user."""
    from channels.layers import get_channel_layer
    channel_layer = get_channel_layer()
    
    await channel_layer.group_send(
        f"predictive_expiration_{user_id}",
        {
            "type": "rotation_required",
            "credential_id": str(credential_id),
            "credential_domain": credential_domain,
            "reason": reason,
            "urgency": urgency,
            "timestamp": timezone.now().isoformat()
        }
    )


async def send_global_threat_update(threat_actor, threat_level, affected_industries, message=None):
    """Send a global threat update to all connected users."""
    from channels.layers import get_channel_layer
    channel_layer = get_channel_layer()
    
    await channel_layer.group_send(
        "predictive_expiration_global",
        {
            "type": "threat_update",
            "threat_actor": threat_actor,
            "threat_level": threat_level,
            "affected_industries": affected_industries,
            "message": message or f"New threat activity from {threat_actor}",
            "timestamp": timezone.now().isoformat()
        }
    )
