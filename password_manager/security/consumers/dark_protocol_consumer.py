"""
Dark Protocol WebSocket Consumer
================================

Real-time bidirectional communication for dark protocol sessions.

Features:
- Receives encrypted garlic bundles
- Sends cover traffic continuously
- Handles session keep-alive
- Manages connection state

@author Password Manager Team
@created 2026-02-02
"""

import json
import logging
import asyncio
from datetime import timedelta
from typing import Optional

from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone

logger = logging.getLogger(__name__)


class DarkProtocolConsumer(AsyncJsonWebsocketConsumer):
    """
    WebSocket consumer for dark protocol real-time communication.
    
    Handles:
    - Session authentication and binding
    - Encrypted bundle transmission
    - Cover traffic generation
    - Connection health monitoring
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session_id: Optional[str] = None
        self.user = None
        self.cover_traffic_task: Optional[asyncio.Task] = None
        self.heartbeat_task: Optional[asyncio.Task] = None
        self.is_connected = False
    
    # =========================================================================
    # Connection Lifecycle
    # =========================================================================
    
    async def connect(self):
        """Handle WebSocket connection."""
        # Get session ID from URL
        self.session_id = self.scope['url_route']['kwargs'].get('session_id')
        
        if not self.session_id:
            await self.close(code=4001)
            return
        
        # Get user from scope
        self.user = self.scope.get('user')
        
        if not self.user or not self.user.is_authenticated:
            await self.close(code=4003)
            return
        
        # Verify session belongs to user
        session = await self._get_session()
        if not session:
            await self.close(code=4004)
            return
        
        # Join session group for broadcasts
        await self.channel_layer.group_add(
            f'dark_protocol_{self.session_id}',
            self.channel_name
        )
        
        await self.accept()
        self.is_connected = True
        
        # Start background tasks
        await self._start_background_tasks()
        
        # Send connection confirmation
        await self.send_json({
            'type': 'connected',
            'session_id': self.session_id,
            'timestamp': timezone.now().isoformat(),
        })
        
        logger.info(f"Dark protocol connection established for session {self.session_id[:8]}...")
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        self.is_connected = False
        
        # Cancel background tasks
        await self._stop_background_tasks()
        
        # Leave session group
        if self.session_id:
            await self.channel_layer.group_discard(
                f'dark_protocol_{self.session_id}',
                self.channel_name
            )
        
        logger.info(f"Dark protocol connection closed for session {self.session_id[:8] if self.session_id else 'unknown'}...")
    
    # =========================================================================
    # Message Handling
    # =========================================================================
    
    async def receive_json(self, content):
        """Handle incoming JSON messages."""
        message_type = content.get('type')
        
        handlers = {
            'bundle': self._handle_bundle,
            'heartbeat': self._handle_heartbeat,
            'request_cover': self._handle_cover_request,
            'terminate': self._handle_terminate,
        }
        
        handler = handlers.get(message_type)
        if handler:
            await handler(content)
        else:
            await self.send_json({
                'type': 'error',
                'message': f'Unknown message type: {message_type}',
            })
    
    async def _handle_bundle(self, content):
        """Handle incoming encrypted bundle."""
        bundle_data = content.get('data')
        
        if not bundle_data:
            await self.send_json({
                'type': 'error',
                'message': 'Missing bundle data',
            })
            return
        
        # Process bundle through dark protocol service
        try:
            result = await self._process_bundle(bundle_data)
            
            await self.send_json({
                'type': 'bundle_ack',
                'bundle_id': content.get('bundle_id'),
                'success': result.get('success', False),
                'timestamp': timezone.now().isoformat(),
            })
            
            # If there's a response, send it
            if result.get('response'):
                await self.send_json({
                    'type': 'bundle_response',
                    'bundle_id': content.get('bundle_id'),
                    'data': result['response'],
                })
                
        except Exception as e:
            logger.error(f"Bundle processing error: {e}")
            await self.send_json({
                'type': 'error',
                'message': 'Bundle processing failed',
            })
    
    async def _handle_heartbeat(self, content):
        """Handle heartbeat message."""
        await self._update_session_activity()
        
        await self.send_json({
            'type': 'heartbeat_ack',
            'timestamp': timezone.now().isoformat(),
        })
    
    async def _handle_cover_request(self, content):
        """Handle request for cover traffic."""
        count = content.get('count', 1)
        
        # Generate and send cover traffic
        cover_bundles = await self._generate_cover_traffic(count)
        
        for bundle in cover_bundles:
            await self.send_json({
                'type': 'cover',
                'data': bundle,
                'timestamp': timezone.now().isoformat(),
            })
    
    async def _handle_terminate(self, content):
        """Handle session termination request."""
        reason = content.get('reason', 'client_request')
        
        await self._terminate_session(reason)
        
        await self.send_json({
            'type': 'terminated',
            'timestamp': timezone.now().isoformat(),
        })
        
        await self.close()
    
    # =========================================================================
    # Background Tasks
    # =========================================================================
    
    async def _start_background_tasks(self):
        """Start background cover traffic and heartbeat tasks."""
        # Start cover traffic if enabled
        config = await self._get_config()
        if config and config.cover_traffic_enabled:
            self.cover_traffic_task = asyncio.create_task(
                self._cover_traffic_loop(config.cover_traffic_intensity)
            )
        
        # Start heartbeat
        self.heartbeat_task = asyncio.create_task(
            self._heartbeat_loop()
        )
    
    async def _stop_background_tasks(self):
        """Stop background tasks."""
        if self.cover_traffic_task:
            self.cover_traffic_task.cancel()
            try:
                await self.cover_traffic_task
            except asyncio.CancelledError:
                pass
        
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            try:
                await self.heartbeat_task
            except asyncio.CancelledError:
                pass
    
    async def _cover_traffic_loop(self, intensity: float):
        """Background loop for generating cover traffic."""
        import random
        
        # Calculate base interval from intensity (0.1 = rare, 1.0 = frequent)
        base_interval = 10.0 - (intensity * 8.0)  # 2-10 seconds
        
        while self.is_connected:
            try:
                # Add jitter
                jitter = random.uniform(-0.5, 0.5) * base_interval
                interval = max(1.0, base_interval + jitter)
                
                await asyncio.sleep(interval)
                
                if not self.is_connected:
                    break
                
                # Generate and send cover traffic
                cover = await self._generate_cover_traffic(1)
                if cover:
                    await self.send_json({
                        'type': 'cover',
                        'data': cover[0],
                        'timestamp': timezone.now().isoformat(),
                    })
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cover traffic error: {e}")
                await asyncio.sleep(5)  # Back off on error
    
    async def _heartbeat_loop(self):
        """Background loop for session heartbeat."""
        while self.is_connected:
            try:
                await asyncio.sleep(30)  # Heartbeat every 30 seconds
                
                if not self.is_connected:
                    break
                
                # Check if session is still valid
                session = await self._get_session()
                if not session or session.is_expired:
                    await self.send_json({
                        'type': 'session_expired',
                        'timestamp': timezone.now().isoformat(),
                    })
                    await self.close()
                    break
                
                # Update activity
                await self._update_session_activity()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
    
    # =========================================================================
    # Group Messages
    # =========================================================================
    
    async def session_message(self, event):
        """Handle messages sent to session group."""
        await self.send_json(event['content'])
    
    async def broadcast_to_session(self, message: dict):
        """Broadcast message to all connections in session."""
        await self.channel_layer.group_send(
            f'dark_protocol_{self.session_id}',
            {
                'type': 'session_message',
                'content': message,
            }
        )
    
    # =========================================================================
    # Database Operations
    # =========================================================================
    
    @database_sync_to_async
    def _get_session(self):
        """Get the garlic session from database."""
        from ..models.dark_protocol_models import GarlicSession
        
        try:
            return GarlicSession.objects.get(
                session_id=self.session_id,
                user=self.user,
            )
        except GarlicSession.DoesNotExist:
            return None
    
    @database_sync_to_async
    def _get_config(self):
        """Get user's dark protocol config."""
        from ..models.dark_protocol_models import DarkProtocolConfig
        
        try:
            return DarkProtocolConfig.objects.get(user=self.user)
        except DarkProtocolConfig.DoesNotExist:
            return None
    
    @database_sync_to_async
    def _update_session_activity(self):
        """Update session last activity timestamp."""
        from ..models.dark_protocol_models import GarlicSession
        
        GarlicSession.objects.filter(
            session_id=self.session_id
        ).update(last_activity_at=timezone.now())
    
    @database_sync_to_async
    def _process_bundle(self, bundle_data):
        """Process an encrypted bundle."""
        from ..services.dark_protocol_service import get_dark_protocol_service
        
        service = get_dark_protocol_service()
        
        # This would decrypt and process the bundle
        # For now, return success
        return {'success': True}
    
    @database_sync_to_async
    def _generate_cover_traffic(self, count: int):
        """Generate cover traffic bundles."""
        from ..services.cover_traffic_generator import get_cover_traffic_generator
        import base64
        
        generator = get_cover_traffic_generator()
        
        bundles = []
        for _ in range(count):
            message = generator.generate_cover_message()
            bundles.append({
                'id': message.message_id,
                'payload': base64.b64encode(message.payload).decode('ascii'),
                'size': message.size,
            })
        
        return bundles
    
    @database_sync_to_async
    def _terminate_session(self, reason: str):
        """Terminate the session."""
        from ..services.dark_protocol_service import get_dark_protocol_service
        
        service = get_dark_protocol_service()
        service.terminate_session(self.session_id, self.user)
