"""
Biometric Liveness WebSocket Consumer
======================================

Real-time video streaming for liveness verification.
"""

import json
import base64
import logging
import numpy as np
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)


class LivenessConsumer(AsyncJsonWebsocketConsumer):
    """
    WebSocket consumer for real-time liveness verification.
    
    Receives video frames and returns liveness analysis in real-time.
    """
    
    async def connect(self):
        """Handle WebSocket connection."""
        self.session_id = self.scope['url_route']['kwargs'].get('session_id')
        self.user = self.scope.get('user')
        
        if not self.user or not self.user.is_authenticated:
            await self.close(code=4001)
            return
        
        if not self.session_id:
            await self.close(code=4002)
            return
        
        # Verify session belongs to user
        is_valid = await self.verify_session()
        if not is_valid:
            await self.close(code=4003)
            return
        
        await self.accept()

        # Share the same in-process session store as the REST views, so frames
        # and challenge responses land on the session created by start_session.
        # (Cross-process sharing between the WS and HTTP workers needs a
        # Redis-backed store -- Phase 3.)
        from .views import get_session_service
        self.service = get_session_service()
        
        await self.send_json({
            'type': 'connected',
            'session_id': self.session_id,
            'message': 'Liveness verification started'
        })
        
        logger.info(f"Liveness WebSocket connected: {self.session_id}")
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        logger.info(f"Liveness WebSocket disconnected: {self.session_id}, code: {close_code}")
    
    async def receive_json(self, content):
        """Handle incoming JSON messages."""
        msg_type = content.get('type')
        
        if msg_type == 'frame':
            await self.handle_frame(content)
        elif msg_type == 'challenge_response':
            await self.handle_challenge_response(content)
        elif msg_type == 'complete':
            await self.handle_complete()
        else:
            await self.send_json({'type': 'error', 'message': f'Unknown message type: {msg_type}'})
    
    async def handle_frame(self, content):
        """Process incoming video frame."""
        try:
            frame_b64 = content.get('frame')
            timestamp_ms = content.get('timestamp_ms', 0)
            try:
                width = int(content.get('width', 0) or 0)
                height = int(content.get('height', 0) or 0)
            except (TypeError, ValueError):
                width = height = 0

            if not frame_b64:
                await self.send_json({'type': 'error', 'message': 'Missing frame data'})
                return
            # Require explicit dimensions, matching the REST contract -- there is
            # no safe default resolution, and a wrong guess just corrupts the
            # reshape.
            if width <= 0 or height <= 0:
                await self.send_json({'type': 'error', 'message': 'Missing or invalid frame dimensions'})
                return

            # Decode frame (binascii.Error subclasses ValueError -> covers bad base64)
            try:
                frame_bytes = base64.b64decode(frame_b64, validate=True)
            except ValueError:
                await self.send_json({'type': 'error', 'message': 'Invalid frame encoding'})
                return
            frame = np.frombuffer(frame_bytes, dtype=np.uint8)

            try:
                frame = frame.reshape((height, width, 3))
            except ValueError:
                try:
                    frame = frame.reshape((height, width, 4))[:, :, :3]
                except ValueError:
                    await self.send_json({'type': 'error', 'message': 'Frame dimensions do not match data'})
                    return

            # Process frame
            result = await sync_to_async(self.service.process_frame)(
                self.session_id, frame, timestamp_ms
            )
            
            await self.send_json({
                'type': 'frame_result',
                'frame_number': result.get('frame_number', 0),
                'results': result.get('results', {}),
                'current_challenge': result.get('current_challenge', 0),
            })
            
        except Exception as e:
            logger.error(f"Frame processing error: {e}")
            await self.send_json({'type': 'error', 'message': 'internal_error'})
    
    async def handle_challenge_response(self, content):
        """Handle challenge response submission."""
        try:
            result = await sync_to_async(self.service.submit_challenge_response)(
                self.session_id, content.get('response', {})
            )
            if 'error' in result:
                await self.send_json({'type': 'error', 'message': result['error']})
                return
            # Keep the WS envelope type as 'challenge_result'; the service's own
            # 'type' (the challenge type, e.g. 'gaze') is surfaced separately so
            # it can't overwrite the message-routing type.
            challenge_type = result.pop('type', None)
            await self.send_json({
                'type': 'challenge_result',
                'challenge_type': challenge_type,
                **result,
            })
        except Exception as e:
            logger.error(f"Challenge response error: {e}")
            await self.send_json({'type': 'error', 'message': 'internal_error'})
    
    async def handle_complete(self):
        """Complete session and send final result."""
        try:
            result = await sync_to_async(self.service.complete_session)(self.session_id)
            
            await self.send_json({
                'type': 'session_complete',
                'is_verified': result.is_verified,
                'liveness_score': result.overall_liveness_score,
                'verdict': result.verdict,
                'confidence': result.confidence,
            })
            
            await self.close()
            
        except Exception as e:
            logger.error(f"Session completion error: {e}")
            await self.send_json({'type': 'error', 'message': 'internal_error'})
    
    @database_sync_to_async
    def verify_session(self):
        """Verify session exists and belongs to user."""
        from .models import LivenessSession
        try:
            session = LivenessSession.objects.get(id=self.session_id, user=self.user)
            return session.status in ['pending', 'in_progress']
        except LivenessSession.DoesNotExist:
            return False
