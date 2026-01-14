"""
WebSocket Consumer for Real-time Adversarial Battle Updates
============================================================

Provides real-time WebSocket communication for:
- Live battle visualization updates
- Defense recommendations as they're generated
- Password strength feedback during typing
"""

import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.utils import timezone

logger = logging.getLogger(__name__)
User = get_user_model()


class AdversarialBattleConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time adversarial battle updates.
    
    Features:
    - Streams attack/defense actions as they happen
    - Sends defense recommendations in real-time
    - Updates strength meter during password typing
    - Provides battle replay capability
    """
    
    async def connect(self):
        """Handle WebSocket connection."""
        try:
            self.user_id = self.scope['url_route']['kwargs']['user_id']
            self.room_group_name = f'adversarial_{self.user_id}'
            
            # Get user from scope
            self.user = self.scope.get('user')
            
            # Authenticate
            if not self.user or self.user.is_anonymous:
                logger.warning(f"Unauthorized adversarial WebSocket attempt for user {self.user_id}")
                await self.close(code=4003)
                return
            
            # Verify user ID matches
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
            logger.info(f"User {self.user_id} connected to adversarial battle WebSocket")
            
            # Send connection confirmation
            await self.send(text_data=json.dumps({
                'type': 'connection_established',
                'message': 'Connected to Adversarial AI Defense System',
                'user_id': self.user_id,
                'timestamp': timezone.now().isoformat()
            }))
            
        except Exception as e:
            logger.error(f"Error in adversarial WebSocket connect: {e}")
            await self.close(code=4000)
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        try:
            if hasattr(self, 'room_group_name'):
                await self.channel_layer.group_discard(
                    self.room_group_name,
                    self.channel_name
                )
                logger.info(f"User {self.user_id} disconnected from adversarial WebSocket")
        except Exception as e:
            logger.error(f"Error in adversarial WebSocket disconnect: {e}")
    
    async def receive(self, text_data):
        """
        Receive message from WebSocket client.
        
        Supported message types:
        - ping: Keepalive ping
        - analyze_password: Request real-time password analysis
        - get_recommendations: Get personalized recommendations
        - start_battle: Start full adversarial battle
        """
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'ping':
                await self.send(text_data=json.dumps({
                    'type': 'pong',
                    'timestamp': timezone.now().isoformat()
                }))
            
            elif message_type == 'analyze_password':
                # Quick real-time analysis
                features = data.get('features', {})
                await self._handle_quick_analysis(features)
            
            elif message_type == 'start_battle':
                # Start full adversarial battle
                features = data.get('features', {})
                await self._handle_battle_start(features)
            
            elif message_type == 'get_recommendations':
                await self._handle_get_recommendations()
            
            else:
                logger.warning(f"Unknown message type: {message_type}")
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': f'Unknown message type: {message_type}'
                }))
        
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON from user {self.user_id}: {e}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON format'
            }))
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Internal server error'
            }))
    
    async def _handle_quick_analysis(self, features: dict):
        """Handle quick password analysis request."""
        from .ai_engines.game_engine import GameEngine
        
        try:
            engine = GameEngine()
            result = engine.get_quick_assessment(features)
            
            await self.send(text_data=json.dumps({
                'type': 'quick_analysis',
                'result': result,
                'timestamp': timezone.now().isoformat()
            }))
        except Exception as e:
            logger.error(f"Error in quick analysis: {e}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Analysis failed'
            }))
    
    async def _handle_battle_start(self, features: dict):
        """Handle full battle simulation request."""
        from .ai_engines.game_engine import GameEngine
        
        try:
            engine = GameEngine()
            
            # Send battle starting notification
            await self.send(text_data=json.dumps({
                'type': 'battle_starting',
                'message': 'Adversarial battle simulation starting...',
                'timestamp': timezone.now().isoformat()
            }))
            
            # Run battle
            result = await database_sync_to_async(engine.run_battle)(
                features,
                int(self.user_id)
            )
            
            # Send battle rounds one by one for animation
            for round_data in result.rounds:
                await self.send(text_data=json.dumps({
                    'type': 'battle_round',
                    'round': {
                        'number': round_data.round_number,
                        'attack': round_data.attack_used,
                        'attack_success': round_data.attack_success_prob,
                        'defense': round_data.defense_applied,
                        'defense_effectiveness': round_data.defense_effectiveness,
                        'winner': round_data.round_winner
                    },
                    'timestamp': timezone.now().isoformat()
                }))
            
            # Send final result
            await self.send(text_data=json.dumps({
                'type': 'battle_complete',
                'result': {
                    'battle_id': result.battle_id,
                    'outcome': result.outcome.value,
                    'attack_score': result.attack_score,
                    'defense_score': result.defense_score,
                    'crack_time': result.crack_time_human,
                    'vulnerabilities': result.key_vulnerabilities,
                    'strengths': result.key_strengths,
                    'recommendations': [
                        {
                            'title': r.title,
                            'description': r.description,
                            'priority': r.priority.value,
                            'actions': r.action_items
                        }
                        for r in result.recommendations
                    ]
                },
                'timestamp': timezone.now().isoformat()
            }))
            
        except Exception as e:
            logger.error(f"Error in battle simulation: {e}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Battle simulation failed'
            }))
    
    async def _handle_get_recommendations(self):
        """Handle recommendation request."""
        from .ai_engines.defender_ai import DefenderAI
        
        try:
            defender = DefenderAI()
            
            # Get user profile if available
            profile = await self._get_user_profile()
            
            recommendations = defender.get_recommendations(
                user_profile=profile
            )
            
            await self.send(text_data=json.dumps({
                'type': 'recommendations',
                'recommendations': [
                    {
                        'title': r.title,
                        'description': r.description,
                        'priority': r.priority.value,
                        'actions': r.action_items
                    }
                    for r in recommendations
                ],
                'timestamp': timezone.now().isoformat()
            }))
            
        except Exception as e:
            logger.error(f"Error getting recommendations: {e}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Failed to get recommendations'
            }))
    
    @database_sync_to_async
    def _get_user_profile(self):
        """Get user's defense profile from database."""
        try:
            from .models import UserDefenseProfile
            profile = UserDefenseProfile.objects.filter(user_id=self.user_id).first()
            if profile:
                return {
                    'overall_defense_score': profile.overall_defense_score,
                    'common_vulnerabilities': profile.common_vulnerabilities,
                    'strong_practices': profile.strong_practices
                }
        except Exception as e:
            logger.error(f"Error fetching user profile: {e}")
        return None
    
    # Group message handlers
    async def battle_update(self, event):
        """Handle battle update from channel layer."""
        await self.send(text_data=json.dumps({
            'type': 'battle_update',
            'message': event['message'],
            'timestamp': timezone.now().isoformat()
        }))
    
    async def recommendation_alert(self, event):
        """Handle new recommendation alert."""
        await self.send(text_data=json.dumps({
            'type': 'recommendation_alert',
            'message': event['message'],
            'timestamp': timezone.now().isoformat()
        }))
    
    async def trending_attack(self, event):
        """Handle trending attack notification."""
        await self.send(text_data=json.dumps({
            'type': 'trending_attack',
            'message': event['message'],
            'timestamp': timezone.now().isoformat()
        }))
