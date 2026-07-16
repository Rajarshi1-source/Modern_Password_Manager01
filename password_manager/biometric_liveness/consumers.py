"""
Biometric Liveness WebSocket Consumer
======================================

Real-time video streaming for liveness verification.
"""

import json
import logging
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from asgiref.sync import sync_to_async

from .frame_utils import decode_frame

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

            # Same decode contract as the REST path (explicit dimensions required).
            frame, decode_error = decode_frame(frame_b64, width, height)
            if decode_error:
                await self.send_json({'type': 'error', 'message': decode_error})
                return

            # Process frame. thread_sensitive=False so CPU-heavy frame analysis
            # for independent sessions runs concurrently instead of serializing
            # in asgiref's single thread-sensitive lane. Safe here: process_frame
            # is per-session-locked and touches no Django ORM / thread-locals.
            result = await sync_to_async(self.service.process_frame, thread_sensitive=False)(
                self.session_id, frame, timestamp_ms
            )

            # Surface real session-state errors (expired, already completed,
            # not found) instead of replying with an empty frame_result -- the
            # REST path returns 400 for these, and a WS client would otherwise
            # keep streaming with no idea the session stopped accepting frames.
            if 'error' in result:
                await self.send_json({'type': 'error', 'message': result['error']})
                return

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
            # thread_sensitive=False: per-session-locked, ORM-free gaze scoring
            # (see handle_frame) -- keep independent sessions off the single lane.
            result = await sync_to_async(self.service.submit_challenge_response, thread_sensitive=False)(
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
            # thread_sensitive=False: per-session-locked, ORM-free scoring (see
            # handle_frame). The DB mirror below stays on database_sync_to_async.
            result = await sync_to_async(self.service.complete_session, thread_sensitive=False)(self.session_id)

            # Mirror the verdict onto the DB row exactly as the REST path does,
            # so the row leaves pending/in_progress and the scores are recorded.
            await self.persist_result(result)

            await self.send_json({
                'type': 'session_complete',
                'is_verified': result.is_verified,
                'liveness_score': result.overall_liveness_score,
                'verdict': result.verdict,
                'confidence': result.confidence,
            })

            await self.close()

        except ValueError as e:
            # Session not found / already completed / expired -> a state error.
            # Do not echo the exception text back to the client.
            logger.warning(f"Session completion conflict: {e}")
            await self.send_json({'type': 'error', 'message': 'invalid_session_state'})
        except Exception as e:
            logger.error(f"Session completion error: {e}")
            await self.send_json({'type': 'error', 'message': 'internal_error'})

    @database_sync_to_async
    def persist_result(self, result):
        """Persist a finalized verdict (shared with the REST complete endpoint)."""
        from .views import persist_session_result
        persist_session_result(result)

    @database_sync_to_async
    def verify_session(self):
        """Verify session exists and belongs to user."""
        from .models import LivenessSession
        try:
            session = LivenessSession.objects.get(id=self.session_id, user=self.user)
            return session.status in ['pending', 'in_progress']
        except LivenessSession.DoesNotExist:
            return False
