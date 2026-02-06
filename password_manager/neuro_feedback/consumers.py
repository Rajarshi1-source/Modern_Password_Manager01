"""
Neuro-Feedback WebSocket Consumer
=================================

Real-time WebSocket communication for:
- EEG data streaming
- Neurofeedback signals
- Training session orchestration
- Device calibration

@author Password Manager Team
@created 2026-02-07
"""

import logging
import json
import numpy as np
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone

logger = logging.getLogger(__name__)


class NeuroTrainingConsumer(AsyncJsonWebsocketConsumer):
    """
    WebSocket consumer for real-time neuro-feedback training sessions.
    
    Handles:
    - EEG data streaming from headset
    - Real-time brainwave analysis
    - Neurofeedback signal delivery
    - Training session coordination
    """
    
    async def connect(self):
        """Handle WebSocket connection."""
        self.user = self.scope.get('user')
        
        if not self.user or not self.user.is_authenticated:
            await self.close(code=4001)
            return
        
        self.session_id = self.scope['url_route']['kwargs'].get('session_id')
        self.user_id = self.user.id
        self.room_name = f"neuro_{self.user_id}"
        
        # Initialize services
        self.analyzer = None
        self.feedback_engine = None
        self.training_service = None
        self.active_program = None
        
        # Join user-specific room
        await self.channel_layer.group_add(
            self.room_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Send connection confirmation
        await self.send_json({
            'type': 'connection_established',
            'session_id': self.session_id,
            'timestamp': timezone.now().isoformat(),
        })
        
        logger.info(f"Neuro-feedback WebSocket connected for user {self.user_id}")
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        # End the session if active
        if self.session_id:
            await self._end_session()
        
        await self.channel_layer.group_discard(
            self.room_name,
            self.channel_name
        )
        
        logger.info(f"Neuro-feedback WebSocket disconnected for user {self.user_id}")
    
    async def receive_json(self, content):
        """Handle incoming WebSocket messages."""
        message_type = content.get('type')
        
        handlers = {
            'eeg_data': self._handle_eeg_data,
            'start_calibration': self._handle_start_calibration,
            'start_training': self._handle_start_training,
            'recall_attempt': self._handle_recall_attempt,
            'request_next_chunk': self._handle_next_chunk,
            'end_session': self._handle_end_session,
            'ping': self._handle_ping,
        }
        
        handler = handlers.get(message_type)
        if handler:
            try:
                await handler(content)
            except Exception as e:
                logger.error(f"Error handling message {message_type}: {e}")
                await self.send_json({
                    'type': 'error',
                    'message': str(e),
                })
        else:
            await self.send_json({
                'type': 'error',
                'message': f'Unknown message type: {message_type}',
            })
    
    # =========================================================================
    # EEG Data Processing
    # =========================================================================
    
    async def _handle_eeg_data(self, content):
        """
        Process incoming EEG data and generate feedback.
        
        Expected content:
        {
            'type': 'eeg_data',
            'channels': [[...], [...], ...],  # Multi-channel EEG samples
            'sample_rate': 256,
            'timestamp': 1234567890.123
        }
        """
        if not self.analyzer:
            await self._initialize_analyzer()
        
        # Convert to numpy array
        channels = content.get('channels', [])
        if not channels:
            return
        
        eeg_array = np.array(channels)
        
        # Analyze brainwave data
        metrics = self.analyzer.analyze(eeg_array)
        
        # Generate neurofeedback
        if not self.feedback_engine:
            await self._initialize_feedback_engine()
        
        feedback = self.feedback_engine.generate_feedback(
            metrics,
            training_active=self.active_program is not None
        )
        
        # Store event if in training
        if self.session_id and metrics.brain_state.value in ['memory_ready', 'encoding', 'recall']:
            await self._store_event(metrics)
        
        # Send feedback to client
        await self.send_json({
            'type': 'neurofeedback',
            'feedback': feedback.to_dict(),
            'metrics': {
                'alpha_power': metrics.alpha_power,
                'theta_power': metrics.theta_power,
                'gamma_power': metrics.gamma_power,
                'focus_index': metrics.focus_index,
                'memory_readiness': metrics.memory_readiness,
                'brain_state': metrics.brain_state.value,
                'signal_quality': metrics.signal_quality,
            },
        })
    
    async def _initialize_analyzer(self):
        """Initialize brainwave analyzer with user's calibration data."""
        from .services import BrainwaveAnalyzer
        
        baseline_alpha = 10.0
        baseline_theta = 6.0
        
        # Get calibration from device
        device = await self._get_preferred_device()
        if device and device.baseline_alpha:
            baseline_alpha = device.baseline_alpha
            baseline_theta = device.baseline_theta or 6.0
        
        self.analyzer = BrainwaveAnalyzer(
            baseline_alpha=baseline_alpha,
            baseline_theta=baseline_theta,
        )
    
    async def _initialize_feedback_engine(self):
        """Initialize neurofeedback engine with user settings."""
        from .services import NeurofeedbackEngine
        
        settings = await self._get_user_settings()
        
        self.feedback_engine = NeurofeedbackEngine(
            feedback_mode=settings.feedback_mode if settings else 'combined',
            audio_volume=settings.audio_volume / 100 if settings else 0.7,
            haptic_intensity=settings.haptic_intensity / 100 if settings else 0.5,
            alpha_threshold=settings.alpha_threshold if settings else 0.6,
            binaural_enabled=settings.binaural_beats_enabled if settings else True,
        )
    
    # =========================================================================
    # Calibration
    # =========================================================================
    
    async def _handle_start_calibration(self, content):
        """Start device calibration process."""
        device_id = content.get('device_id')
        
        if not device_id:
            await self.send_json({
                'type': 'error',
                'message': 'device_id required',
            })
            return
        
        # Update device status
        await self._update_device_status(device_id, 'calibrating')
        
        await self.send_json({
            'type': 'calibration_started',
            'instructions': [
                {'step': 1, 'text': 'Sit comfortably and relax', 'duration': 10},
                {'step': 2, 'text': 'Close your eyes gently', 'duration': 30},
                {'step': 3, 'text': 'Open your eyes and focus on the screen', 'duration': 30},
            ],
            'total_duration': 70,
        })
    
    # =========================================================================
    # Training Session
    # =========================================================================
    
    async def _handle_start_training(self, content):
        """Start a training session for password memorization."""
        program_id = content.get('program_id')
        password = content.get('password')  # Needed for chunk display
        
        if not program_id or not password:
            await self.send_json({
                'type': 'error',
                'message': 'program_id and password required',
            })
            return
        
        # Initialize training service
        from .services import MemoryTrainingService
        self.training_service = MemoryTrainingService(self.user)
        
        # Get program
        program = await self._get_program(program_id)
        if not program:
            await self.send_json({
                'type': 'error',
                'message': 'Program not found',
            })
            return
        
        self.active_program = program
        self._current_password = password  # Stored temporarily for session
        
        # Get session
        session = await self._get_session()
        
        # Start training
        training_session = self.training_service.start_training_session(
            program, password, session
        )
        
        await self.send_json({
            'type': 'training_started',
            'program_id': str(program.id),
            'total_chunks': training_session.total_chunks,
            'current_chunk': training_session.current_chunk,
            'message': training_session.feedback_message,
        })
    
    async def _handle_next_chunk(self, content):
        """Get next chunk to practice based on brain state."""
        if not self.active_program or not self.training_service:
            await self.send_json({
                'type': 'error',
                'message': 'No active training session',
            })
            return
        
        # Get current brain metrics
        if not self.analyzer:
            await self._initialize_analyzer()
        
        # Generate mock metrics if no EEG data
        from .services import BrainwaveMetrics, BrainState
        import time
        
        metrics = BrainwaveMetrics(
            timestamp=time.time(),
            brain_state=BrainState.FOCUSED,
            memory_readiness=0.7,
        )
        
        chunk, feedback_msg = self.training_service.get_next_chunk(
            self.active_program,
            self._current_password,
            metrics,
        )
        
        await self.send_json({
            'type': 'chunk_ready',
            'chunk': {
                'index': chunk.index,
                'content': chunk.content,
                'display_content': chunk.display_content,
                'strength': chunk.strength,
                'is_mastered': chunk.is_mastered,
            },
            'message': feedback_msg,
        })
    
    async def _handle_recall_attempt(self, content):
        """Handle user's recall attempt."""
        if not self.active_program or not self.training_service:
            await self.send_json({
                'type': 'error',
                'message': 'No active training session',
            })
            return
        
        chunk_index = content.get('chunk_index')
        user_input = content.get('input', '')
        response_time = content.get('response_time_ms', 5000)
        
        result = self.training_service.test_recall(
            self.active_program,
            chunk_index,
            user_input,
            self._current_password,
            response_time,
        )
        
        # Generate reward feedback
        if self.feedback_engine:
            reward = self.feedback_engine.generate_reward_signal(
                result.success,
                5 if result.success and response_time < 2000 else 3
            )
        else:
            reward = None
        
        await self.send_json({
            'type': 'recall_result',
            'success': result.success,
            'time_ms': result.time_ms,
            'strength_delta': result.strength_delta,
            'new_strength': result.new_strength,
            'feedback': result.feedback,
            'reward': reward.to_dict() if reward else None,
        })
    
    async def _handle_end_session(self, content):
        """End the current training session."""
        await self._end_session()
        
        await self.send_json({
            'type': 'session_ended',
            'message': 'Training session completed',
        })
    
    async def _end_session(self):
        """Clean up session resources."""
        if self.session_id:
            await self._update_session_status('completed')
        
        self.active_program = None
        self._current_password = None
    
    # =========================================================================
    # Utilities
    # =========================================================================
    
    async def _handle_ping(self, content):
        """Respond to ping."""
        await self.send_json({'type': 'pong'})
    
    @database_sync_to_async
    def _get_preferred_device(self):
        """Get user's preferred EEG device."""
        from .models import EEGDevice
        return EEGDevice.objects.filter(
            user=self.user,
            status__in=['ready', 'paired']
        ).order_by('-last_connected_at').first()
    
    @database_sync_to_async
    def _get_user_settings(self):
        """Get user's neuro-feedback settings."""
        from .models import NeuroFeedbackSettings
        try:
            return NeuroFeedbackSettings.objects.get(user=self.user)
        except NeuroFeedbackSettings.DoesNotExist:
            return None
    
    @database_sync_to_async
    def _update_device_status(self, device_id, status):
        """Update device status."""
        from .models import EEGDevice
        EEGDevice.objects.filter(id=device_id, user=self.user).update(status=status)
    
    @database_sync_to_async
    def _get_program(self, program_id):
        """Get training program."""
        from .models import PasswordTrainingProgram
        try:
            return PasswordTrainingProgram.objects.get(id=program_id, user=self.user)
        except PasswordTrainingProgram.DoesNotExist:
            return None
    
    @database_sync_to_async
    def _get_session(self):
        """Get brainwave session."""
        from .models import BrainwaveSession
        try:
            return BrainwaveSession.objects.get(id=self.session_id)
        except BrainwaveSession.DoesNotExist:
            return None
    
    @database_sync_to_async
    def _update_session_status(self, status):
        """Update session status."""
        from .models import BrainwaveSession
        BrainwaveSession.objects.filter(id=self.session_id).update(
            status=status,
            ended_at=timezone.now(),
        )
    
    @database_sync_to_async
    def _store_event(self, metrics):
        """Store neurofeedback event."""
        from .models import NeurofeedbackEvent, BrainwaveSession
        try:
            session = BrainwaveSession.objects.get(id=self.session_id)
            NeurofeedbackEvent.objects.create(
                session=session,
                event_type=metrics.brain_state.value,
                alpha_power=metrics.alpha_power,
                theta_power=metrics.theta_power,
                gamma_power=metrics.gamma_power,
                focus_index=metrics.focus_index,
            )
        except Exception as e:
            logger.error(f"Failed to store event: {e}")
