"""
Cognitive Auth WebSocket Consumers
==================================

Real-time WebSocket communication for cognitive verification challenges.
Provides sub-millisecond timing precision for challenge delivery.

@author Password Manager Team
@created 2026-02-07
"""

import json
import hashlib
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone

from .models import CognitiveSession, CognitiveChallenge, ChallengeResponse
from .services import ReactionTimeAnalyzer, ImplicitMemoryDetector


class CognitiveVerificationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time cognitive verification.
    
    Handles:
    - Challenge delivery with precise timing
    - Response collection with millisecond timestamps
    - Real-time feedback to the client
    - Session management
    """
    
    async def connect(self):
        """Handle WebSocket connection."""
        self.session_id = self.scope['url_route']['kwargs']['session_id']
        self.room_group_name = f'cognitive_{self.session_id}'
        
        # Validate session
        self.session = await self.get_session()
        
        if not self.session:
            await self.close(code=4004)
            return
        
        if self.session.is_expired():
            await self.close(code=4010)
            return
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Send connection confirmation
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'session_id': self.session_id,
            'total_challenges': self.session.total_challenges,
            'challenges_completed': self.session.challenges_completed,
            'server_time': timezone.now().timestamp() * 1000,
        }))
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        """Handle incoming WebSocket messages."""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            handlers = {
                'request_challenge': self.handle_request_challenge,
                'submit_response': self.handle_submit_response,
                'ping': self.handle_ping,
            }
            
            handler = handlers.get(message_type)
            if handler:
                await handler(data)
            else:
                await self.send_error(f'Unknown message type: {message_type}')
        
        except json.JSONDecodeError:
            await self.send_error('Invalid JSON')
        except Exception as e:
            await self.send_error(str(e))
    
    async def handle_request_challenge(self, data):
        """Handle request for next challenge."""
        sequence_number = data.get('sequence_number', 1)
        
        challenge = await self.get_challenge(sequence_number)
        
        if not challenge:
            await self.send(text_data=json.dumps({
                'type': 'no_more_challenges',
                'message': 'All challenges completed',
            }))
            return
        
        # Mark as presented
        await self.mark_challenge_presented(challenge)
        
        # Send challenge
        await self.send(text_data=json.dumps({
            'type': 'challenge',
            'challenge_id': str(challenge.id),
            'challenge_type': challenge.challenge_type,
            'difficulty': challenge.difficulty,
            'sequence_number': challenge.sequence_number,
            'data': challenge.challenge_data,
            'time_limit_ms': challenge.time_limit_ms,
            'display_duration_ms': challenge.display_duration_ms,
            'presented_at': timezone.now().timestamp() * 1000,
        }))
    
    async def handle_submit_response(self, data):
        """Handle response submission with precise timing."""
        challenge_id = data.get('challenge_id')
        response_value = data.get('response', '')
        client_timestamp = data.get('client_timestamp', 0)
        reaction_time_ms = data.get('reaction_time_ms', 0)
        
        server_received = timezone.now().timestamp() * 1000
        
        challenge = await self.get_challenge_by_id(challenge_id)
        
        if not challenge:
            await self.send_error('Challenge not found')
            return
        
        # Verify response
        response_hash = hashlib.sha256(response_value.encode()).hexdigest()
        is_correct = response_hash == challenge.correct_answer_hash
        
        # Analyze response
        analysis = await self.analyze_response(
            reaction_time_ms,
            challenge.challenge_type,
            is_correct
        )
        
        # Save response
        await self.save_response(
            challenge,
            response_hash,
            is_correct,
            reaction_time_ms,
            client_timestamp,
            data.get('first_keystroke_ms'),
            data.get('total_input_duration_ms'),
            data.get('hesitation_count', 0),
            data.get('correction_count', 0),
            analysis
        )
        
        # Update session
        session_update = await self.update_session(is_correct)
        
        # Send result
        await self.send(text_data=json.dumps({
            'type': 'response_result',
            'challenge_id': challenge_id,
            'is_correct': is_correct,
            'reaction_time_ms': reaction_time_ms,
            'confidence': analysis.get('confidence', 0),
            'z_score': analysis.get('z_score', 0),
            'server_received_at': server_received,
            'challenges_completed': session_update['challenges_completed'],
            'challenges_passed': session_update['challenges_passed'],
            'is_session_complete': session_update['is_complete'],
        }))
        
        # If session complete, send final results
        if session_update['is_complete']:
            final_result = await self.finalize_session()
            await self.send(text_data=json.dumps({
                'type': 'session_complete',
                **final_result
            }))
    
    async def handle_ping(self, data):
        """Handle ping for timing synchronization."""
        await self.send(text_data=json.dumps({
            'type': 'pong',
            'client_time': data.get('client_time', 0),
            'server_time': timezone.now().timestamp() * 1000,
        }))
    
    async def send_error(self, message):
        """Send error message."""
        await self.send(text_data=json.dumps({
            'type': 'error',
            'message': message,
        }))
    
    # Database operations
    
    @database_sync_to_async
    def get_session(self):
        """Get session from database."""
        try:
            return CognitiveSession.objects.get(id=self.session_id)
        except CognitiveSession.DoesNotExist:
            return None
    
    @database_sync_to_async
    def get_challenge(self, sequence_number):
        """Get challenge by sequence number."""
        try:
            return CognitiveChallenge.objects.get(
                session_id=self.session_id,
                sequence_number=sequence_number
            )
        except CognitiveChallenge.DoesNotExist:
            return None
    
    @database_sync_to_async
    def get_challenge_by_id(self, challenge_id):
        """Get challenge by ID."""
        try:
            return CognitiveChallenge.objects.get(
                id=challenge_id,
                session_id=self.session_id
            )
        except CognitiveChallenge.DoesNotExist:
            return None
    
    @database_sync_to_async
    def mark_challenge_presented(self, challenge):
        """Mark challenge as presented."""
        challenge.is_presented = True
        challenge.presented_at = timezone.now()
        challenge.save()
    
    @database_sync_to_async
    def save_response(
        self, challenge, response_hash, is_correct, reaction_time_ms,
        client_timestamp, first_keystroke_ms, total_input_duration_ms,
        hesitation_count, correction_count, analysis
    ):
        """Save challenge response."""
        ChallengeResponse.objects.create(
            challenge=challenge,
            response_hash=response_hash,
            is_correct=is_correct,
            reaction_time_ms=reaction_time_ms,
            first_keystroke_ms=first_keystroke_ms,
            total_input_duration_ms=total_input_duration_ms,
            hesitation_count=hesitation_count,
            correction_count=correction_count,
            client_timestamp=client_timestamp,
            z_score=analysis.get('z_score', 0),
            is_anomalous=analysis.get('is_anomalous', False),
            confidence_score=analysis.get('confidence', 0),
        )
    
    @database_sync_to_async
    def update_session(self, is_correct):
        """Update session progress."""
        session = CognitiveSession.objects.get(id=self.session_id)
        session.challenges_completed += 1
        if is_correct:
            session.challenges_passed += 1
        session.save()
        
        return {
            'challenges_completed': session.challenges_completed,
            'challenges_passed': session.challenges_passed,
            'is_complete': session.challenges_completed >= session.total_challenges,
        }
    
    @database_sync_to_async
    def analyze_response(self, reaction_time_ms, challenge_type, is_correct):
        """Analyze response timing."""
        analyzer = ReactionTimeAnalyzer()
        metrics = analyzer.analyze_single_response(
            reaction_time_ms,
            challenge_type,
            is_correct
        )
        
        return {
            'z_score': metrics.z_score,
            'is_anomalous': metrics.is_anomalous,
            'confidence': metrics.confidence,
        }
    
    @database_sync_to_async
    def finalize_session(self):
        """Finalize session and compute results."""
        session = CognitiveSession.objects.get(id=self.session_id)
        session.status = 'completed'
        session.completed_at = timezone.now()
        
        # Get all responses
        responses = []
        for challenge in session.challenges.all():
            if hasattr(challenge, 'response'):
                resp = challenge.response
                responses.append({
                    'challenge_type': challenge.challenge_type,
                    'reaction_time_ms': resp.reaction_time_ms,
                    'is_correct': resp.is_correct,
                    'hesitation_count': resp.hesitation_count,
                    'correction_count': resp.correction_count,
                })
        
        # Analyze session
        analyzer = ReactionTimeAnalyzer()
        analysis = analyzer.analyze_session_responses(responses)
        
        # Detect implicit memory
        detector = ImplicitMemoryDetector()
        detection = detector.detect({}, responses)
        
        # Update session
        session.overall_score = analysis.get('accuracy', 0)
        session.confidence = analysis.get('confidence', 0)
        session.creator_probability = detection.creator_probability
        
        if detection.is_creator and session.overall_score >= 0.7:
            session.status = 'passed'
        else:
            session.status = 'failed'
        
        session.save()
        
        return {
            'status': session.status,
            'overall_score': session.overall_score,
            'creator_probability': detection.creator_probability,
            'confidence': session.confidence,
            'is_creator': detection.is_creator,
            'explanation': detection.explanation,
            'anomalies': detection.anomalies,
        }
