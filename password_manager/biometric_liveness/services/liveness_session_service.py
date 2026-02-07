"""
Liveness Session Service
=========================

Orchestrates the complete liveness verification session.
Coordinates all detection services and aggregates results.
"""

import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import uuid
import numpy as np

from .micro_expression_analyzer import MicroExpressionAnalyzer
from .gaze_tracking_service import GazeTrackingService
from .pulse_oximetry_service import PulseOximetryService
from .thermal_imaging_service import ThermalImagingService
from .deepfake_detector import DeepfakeDetector

logger = logging.getLogger(__name__)


@dataclass
class SessionConfig:
    """Configuration for liveness session."""
    required_challenges: List[str]
    liveness_threshold: float
    session_timeout_seconds: int
    enable_pulse: bool
    enable_thermal: bool


@dataclass
class SessionResult:
    """Final result of liveness session."""
    session_id: str
    is_verified: bool
    overall_liveness_score: float
    deepfake_probability: float
    confidence: float
    micro_expression_score: float
    gaze_tracking_score: float
    pulse_oximetry_score: float
    thermal_score: float
    texture_artifact_score: float
    total_frames_processed: int
    duration_ms: float
    verdict: str
    details: Dict


class LivenessSessionService:
    """
    Orchestrates liveness verification sessions.
    
    Coordinates multiple detection services:
    - MicroExpressionAnalyzer
    - GazeTrackingService
    - PulseOximetryService
    - ThermalImagingService
    - DeepfakeDetector
    """
    
    def __init__(self):
        """Initialize session service with all detectors."""
        self.config = self._load_config()
        
        # Initialize detection services
        self.expression_analyzer = MicroExpressionAnalyzer()
        self.gaze_service = GazeTrackingService({
            'gaze_tracking_points': self.config.get('GAZE_TRACKING_POINTS', 9),
            'cognitive_task_timeout_ms': self.config.get('COGNITIVE_TASK_TIMEOUT_MS', 5000),
        })
        self.pulse_service = PulseOximetryService()
        self.thermal_service = ThermalImagingService({
            'thermal_enabled': self.config.get('THERMAL_ENABLED', False),
        })
        self.deepfake_detector = DeepfakeDetector()
        
        # Session state
        self.active_sessions: Dict[str, Dict] = {}
        
        logger.info("LivenessSessionService initialized")
    
    def _load_config(self) -> Dict:
        """Load configuration from Django settings."""
        return getattr(settings, 'BIOMETRIC_LIVENESS', {
            'LIVENESS_THRESHOLD': 0.85,
            'DEEPFAKE_THRESHOLD': 0.70,
            'SESSION_TIMEOUT_SECONDS': 120,
            'REQUIRED_CHALLENGES': ['gaze', 'expression', 'pulse'],
            'GAZE_TRACKING_POINTS': 9,
            'COGNITIVE_TASK_TIMEOUT_MS': 5000,
            'THERMAL_ENABLED': False,
        })
    
    def create_session(self, user_id: int, context: str = 'login') -> Dict:
        """
        Create a new liveness verification session.
        
        Args:
            user_id: User ID
            context: Session context (login, high_security, enrollment)
            
        Returns:
            Session info dict
        """
        session_id = str(uuid.uuid4())
        
        # Generate cognitive challenges
        challenges = self._generate_challenges(context)
        
        session = {
            'session_id': session_id,
            'user_id': user_id,
            'context': context,
            'status': 'pending',
            'challenges': challenges,
            'current_challenge_idx': 0,
            'created_at': timezone.now(),
            'expires_at': timezone.now() + timedelta(seconds=self.config.get('SESSION_TIMEOUT_SECONDS', 120)),
            'frames_processed': 0,
            'started_at': None,
            'completed_at': None,
        }
        
        self.active_sessions[session_id] = session
        
        # Reset all services for new session
        self.expression_analyzer = MicroExpressionAnalyzer()
        self.gaze_service.clear_history()
        self.pulse_service.reset()
        self.thermal_service.reset()
        self.deepfake_detector.reset()
        
        logger.info(f"Created liveness session {session_id} for user {user_id}")
        
        return {
            'session_id': session_id,
            'challenges': [{'type': c['type'], 'instruction': c['instruction']} for c in challenges],
            'expires_at': session['expires_at'].isoformat(),
            'status': 'pending',
        }
    
    def _generate_challenges(self, context: str) -> List[Dict]:
        """Generate challenges for the session."""
        challenges = []
        
        required = self.config.get('REQUIRED_CHALLENGES', ['gaze', 'expression', 'pulse'])
        
        for i, challenge_type in enumerate(required):
            if challenge_type == 'gaze':
                task = self.gaze_service.generate_cognitive_task()
                challenges.append({
                    'type': 'gaze',
                    'instruction': task.instruction,
                    'data': {
                        'target_positions': task.target_positions,
                        'time_limit_ms': task.time_limit_ms,
                    },
                    'sequence': i,
                })
            elif challenge_type == 'expression':
                challenges.append({
                    'type': 'expression',
                    'instruction': 'Make the following expressions naturally: smile, then surprised',
                    'data': {'expressions': ['happy', 'surprise']},
                    'sequence': i,
                })
            elif challenge_type == 'pulse':
                challenges.append({
                    'type': 'pulse',
                    'instruction': 'Stay still and look at the camera for 10 seconds',
                    'data': {'duration_seconds': 10},
                    'sequence': i,
                })
        
        return challenges
    
    def process_frame(self, session_id: str, frame: np.ndarray, timestamp_ms: float, face_landmarks: Optional[np.ndarray] = None) -> Dict:
        """
        Process a video frame within a session.
        
        Args:
            session_id: Session ID
            frame: RGB video frame
            timestamp_ms: Frame timestamp
            face_landmarks: Optional pre-detected face landmarks
            
        Returns:
            Frame processing result
        """
        session = self.active_sessions.get(session_id)
        if not session:
            return {'error': 'Session not found'}
        
        if timezone.now() > session['expires_at']:
            session['status'] = 'expired'
            return {'error': 'Session expired'}
        
        if session['status'] == 'pending':
            session['status'] = 'in_progress'
            session['started_at'] = timezone.now()
        
        session['frames_processed'] += 1
        
        # Run all detection services
        results = {}
        
        # Extract landmarks if not provided
        if face_landmarks is None:
            face_landmarks = self.expression_analyzer.extract_landmarks(frame)
        
        # Micro-expression analysis
        if face_landmarks is not None:
            aus = self.expression_analyzer.extract_action_units(face_landmarks)
            results['expression'] = {'action_units': aus}
        
        # Gaze tracking
        gaze_point = self.gaze_service.estimate_gaze(frame, face_landmarks)
        if gaze_point:
            results['gaze'] = {
                'x': gaze_point.x,
                'y': gaze_point.y,
                'confidence': gaze_point.confidence,
            }
        
        # Pulse oximetry
        pulse_reading = self.pulse_service.process_frame(frame, timestamp_ms, face_landmarks)
        if pulse_reading:
            results['pulse'] = {
                'heart_rate': pulse_reading.heart_rate_bpm,
                'spo2': pulse_reading.spo2_estimate,
                'quality': pulse_reading.signal_quality,
            }
        
        # Deepfake detection
        deepfake_analysis = self.deepfake_detector.analyze_frame(frame, None, timestamp_ms)
        results['deepfake'] = {
            'is_fake': deepfake_analysis.is_fake,
            'probability': deepfake_analysis.fake_probability,
        }
        
        return {
            'frame_number': session['frames_processed'],
            'results': results,
            'current_challenge': session['current_challenge_idx'],
        }
    
    def complete_session(self, session_id: str) -> SessionResult:
        """
        Complete session and generate final verdict.
        
        Args:
            session_id: Session ID
            
        Returns:
            Final session result
        """
        session = self.active_sessions.get(session_id)
        if not session:
            raise ValueError('Session not found')
        
        session['status'] = 'completed'
        session['completed_at'] = timezone.now()
        
        # Aggregate scores from all services
        expression_score = 0.7  # Placeholder - would use analyzer results
        gaze_score = self.gaze_service.get_liveness_score([])
        pulse_score = self.pulse_service.get_liveness_score([])
        thermal_score = self.thermal_service.get_liveness_score([])
        deepfake_score = self.deepfake_detector.get_liveness_score()
        
        # Calculate overall liveness
        weights = {'expression': 0.2, 'gaze': 0.2, 'pulse': 0.25, 'thermal': 0.1, 'deepfake': 0.25}
        
        overall = (
            expression_score * weights['expression'] +
            gaze_score * weights['gaze'] +
            pulse_score * weights['pulse'] +
            thermal_score * weights['thermal'] +
            deepfake_score * weights['deepfake']
        )
        
        # Determine verdict
        threshold = self.config.get('LIVENESS_THRESHOLD', 0.85)
        is_verified = overall >= threshold
        
        if overall >= 0.9:
            verdict = 'HIGH_CONFIDENCE_LIVE'
        elif overall >= threshold:
            verdict = 'VERIFIED_LIVE'
        elif overall >= 0.6:
            verdict = 'LOW_CONFIDENCE'
        else:
            verdict = 'SUSPECTED_FAKE'
        
        duration_ms = 0
        if session['started_at']:
            duration_ms = (session['completed_at'] - session['started_at']).total_seconds() * 1000
        
        return SessionResult(
            session_id=session_id,
            is_verified=is_verified,
            overall_liveness_score=overall,
            deepfake_probability=1.0 - deepfake_score,
            confidence=0.8,
            micro_expression_score=expression_score,
            gaze_tracking_score=gaze_score,
            pulse_oximetry_score=pulse_score,
            thermal_score=thermal_score,
            texture_artifact_score=deepfake_score,
            total_frames_processed=session['frames_processed'],
            duration_ms=duration_ms,
            verdict=verdict,
            details={},
        )
    
    def get_session_status(self, session_id: str) -> Optional[Dict]:
        """Get current session status."""
        session = self.active_sessions.get(session_id)
        if not session:
            return None
        
        return {
            'session_id': session_id,
            'status': session['status'],
            'frames_processed': session['frames_processed'],
            'current_challenge': session['current_challenge_idx'],
            'is_expired': timezone.now() > session['expires_at'],
        }
