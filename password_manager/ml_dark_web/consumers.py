"""
WebSocket Consumer for Real-time Breach Alerts
Connects users to their personal alert channel for live notifications
"""

import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


class BreachAlertConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time breach alerts
    Connects users to their personal alert channel
    """
    
    async def connect(self):
        """Handle WebSocket connection"""
        try:
            # Get user from URL route
            self.user_id = self.scope['url_route']['kwargs']['user_id']
            self.room_group_name = f'user_{self.user_id}'
            
            # Get user from scope (set by auth middleware)
            self.user = self.scope.get('user')
            
            # Authenticate user
            if not self.user or self.user.is_anonymous:
                logger.warning(f"Unauthorized WebSocket connection attempt for user {self.user_id}")
                await self.close(code=4003)
                return
            
            # Verify user ID matches authenticated user
            if str(self.user.id) != str(self.user_id):
                logger.warning(f"User ID mismatch: {self.user.id} != {self.user_id}")
                await self.close(code=4003)
                return
            
            # Join room group
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )
            
            await self.accept()
            logger.info(f"User {self.user_id} connected to breach alerts WebSocket")
            
            # Send connection confirmation
            await self.send(text_data=json.dumps({
                'type': 'connection_established',
                'message': 'Connected to ML-powered breach alert system',
                'user_id': self.user_id,
                'timestamp': timezone.now().isoformat()
            }))
            
            # Send initial unread count
            unread_count = await self.get_unread_count(self.user_id)
            await self.send(text_data=json.dumps({
                'type': 'unread_count',
                'count': unread_count
            }))
            
        except Exception as e:
            logger.error(f"Error in WebSocket connect: {e}")
            await self.close(code=4000)
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        try:
            # Leave room group
            if hasattr(self, 'room_group_name'):
                await self.channel_layer.group_discard(
                    self.room_group_name,
                    self.channel_name
                )
                logger.info(f"User {self.user_id} disconnected from breach alerts WebSocket (code: {close_code})")
        except Exception as e:
            logger.error(f"Error in WebSocket disconnect: {e}")
    
    async def receive(self, text_data):
        """
        Receive message from WebSocket (client -> server)
        Handle client requests like ping/pong for keepalive
        """
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'ping':
                # Respond to keepalive ping
                await self.send(text_data=json.dumps({
                    'type': 'pong',
                    'timestamp': data.get('timestamp'),
                    'server_time': timezone.now().isoformat()
                }))
            
            elif message_type == 'get_unread_count':
                # Send current unread count
                count = await self.get_unread_count(self.user_id)
                await self.send(text_data=json.dumps({
                    'type': 'unread_count',
                    'count': count
                }))
            
            elif message_type == 'subscribe_to_updates':
                # Client is subscribing to real-time updates
                await self.send(text_data=json.dumps({
                    'type': 'subscription_confirmed',
                    'message': 'Subscribed to breach alerts'
                }))
            
            else:
                logger.warning(f"Unknown message type from user {self.user_id}: {message_type}")
        
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON received from user {self.user_id}: {e}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON format'
            }))
        except Exception as e:
            logger.error(f"Error processing message from user {self.user_id}: {e}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Internal server error'
            }))
    
    async def breach_alert(self, event):
        """
        Receive breach alert from room group (server -> client)
        This is called when a task sends a message to the group
        """
        try:
            message = event['message']
            
            # Send alert to WebSocket client
            await self.send(text_data=json.dumps({
                'type': 'breach_alert',
                'message': message,
                'timestamp': timezone.now().isoformat()
            }))
            
            logger.info(f"Breach alert sent to user {self.user_id}: {message.get('breach_id', 'N/A')}")
            
        except Exception as e:
            logger.error(f"Error sending breach alert to user {self.user_id}: {e}")
    
    async def alert_update(self, event):
        """
        Receive alert status update (e.g., marked as read)
        """
        try:
            message = event['message']
            
            await self.send(text_data=json.dumps({
                'type': 'alert_update',
                'message': message,
                'timestamp': timezone.now().isoformat()
            }))
            
            logger.info(f"Alert update sent to user {self.user_id}")
            
        except Exception as e:
            logger.error(f"Error sending alert update to user {self.user_id}: {e}")
    
    async def system_notification(self, event):
        """
        Send system notifications to user
        """
        try:
            message = event['message']
            
            await self.send(text_data=json.dumps({
                'type': 'system_notification',
                'message': message,
                'timestamp': timezone.now().isoformat()
            }))
            
        except Exception as e:
            logger.error(f"Error sending system notification to user {self.user_id}: {e}")
    
    # Database helpers
    @database_sync_to_async
    def get_unread_count(self, user_id):
        """Get unread breach alerts count"""
        try:
            from .models import MLBreachMatch
            
            return MLBreachMatch.objects.filter(
                user_id=user_id,
                is_active=True,
                alert_created=True
            ).exclude(
                is_resolved=True
            ).count()
            
        except Exception as e:
            logger.error(f"Error getting unread count for user {user_id}: {e}")
            return 0

