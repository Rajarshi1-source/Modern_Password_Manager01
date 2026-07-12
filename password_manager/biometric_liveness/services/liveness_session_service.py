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

    # Minimum number of valid rPPG readings before the pulse modality counts.
    MIN_PULSE_READINGS = 5
    # Minimum number of independent live modalities required to verify. Below
    # this the session fails closed (INSUFFICIENT_SIGNAL) rather than passing.
    MIN_MODALITIES = 2

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
    
    def _new_session_services(self) -> Dict:
        """
        Build a fresh set of stateful detectors for a single session.

        The service object itself is a process-wide singleton (get_session_service
        uses lru_cache), so per-frame accumulators (rPPG buffers, deepfake frame
        history, gaze history, ingested hardware SpO2) must live per session --
        otherwise a second session's create_session would clobber a first
        session's in-progress state.
        """
        return {
            'expression': MicroExpressionAnalyzer(),
            'gaze': GazeTrackingService({
                'gaze_tracking_points': self.config.get('GAZE_TRACKING_POINTS', 9),
                'cognitive_task_timeout_ms': self.config.get('COGNITIVE_TASK_TIMEOUT_MS', 5000),
            }),
            'pulse': PulseOximetryService(),
            'thermal': ThermalImagingService({
                'thermal_enabled': self.config.get('THERMAL_ENABLED', False),
            }),
            'deepfake': DeepfakeDetector(),
        }

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
            # Per-session accumulation of REAL signals. complete_session scores
            # only the modalities that actually populated these during the run.
            'pulse_readings': [],
            'deepfake_probs': [],          # advisory (heuristic) — never gates
            'deepfake_model_probs': [],     # model-derived only — may gate/veto
            'expression_au_frames': 0,
            'gaze_samples': 0,
            'gaze_task_results': [],
            'thermal_readings': [],
        }

        # Isolated per-session detectors so a concurrent session cannot clobber
        # this one's accumulated state (see _new_session_services).
        session['services'] = self._new_session_services()

        self.active_sessions[session_id] = session

        logger.info(f"Created liveness session {session_id} for user {user_id}")
        
        return {
            'session_id': session_id,
            'challenges': [
                # Client-facing view: the CognitiveTask object is deliberately
                # excluded (kept server-side for scoring); data carries the
                # targets/time-limit the client needs to render the challenge.
                {'type': c['type'], 'instruction': c['instruction'], 'data': c.get('data', {})}
                for c in challenges
            ],
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
                    # Retained server-side (never sent to the client) so the
                    # response can be scored against these exact randomized
                    # targets in submit_challenge_response.
                    'cognitive_task': task,
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

        # Defensive: ensure per-session accumulators exist even if this session
        # dict was created outside create_session (e.g. a future shared-store
        # path), so frame accumulation below can never KeyError.
        session.setdefault('pulse_readings', [])
        session.setdefault('deepfake_probs', [])
        session.setdefault('deepfake_model_probs', [])
        session.setdefault('expression_au_frames', 0)
        session.setdefault('gaze_samples', 0)

        # Run all detection services. Use this session's OWN detector instances
        # so accumulated per-frame state never mixes with another session's.
        # (Plain get + conditional build: setdefault would construct a throwaway
        # detector set on every frame because its default arg is evaluated eagerly.)
        results = {}
        svc = session.get('services')
        if svc is None:
            svc = self._new_session_services()
            session['services'] = svc

        # Extract landmarks if not provided
        if face_landmarks is None:
            face_landmarks = svc['expression'].extract_landmarks(frame)

        # Micro-expression analysis
        if face_landmarks is not None:
            aus = svc['expression'].extract_action_units(face_landmarks)
            results['expression'] = {'action_units': aus}
            if aus:
                session['expression_au_frames'] += 1

        # Gaze tracking
        gaze_point = svc['gaze'].estimate_gaze(frame, face_landmarks)
        if gaze_point:
            results['gaze'] = {
                'x': gaze_point.x,
                'y': gaze_point.y,
                'confidence': gaze_point.confidence,
            }
            session['gaze_samples'] += 1

        # Pulse oximetry
        pulse_reading = svc['pulse'].process_frame(frame, timestamp_ms, face_landmarks)
        if pulse_reading:
            results['pulse'] = {
                'heart_rate': pulse_reading.heart_rate_bpm,
                'spo2': pulse_reading.spo2_estimate,
                'quality': pulse_reading.signal_quality,
            }
            # Only readings with a resolved heart rate count as real pulse signal.
            if pulse_reading.heart_rate_bpm is not None:
                session['pulse_readings'].append(pulse_reading)

        # Deepfake detection (heuristic output is advisory until a real model
        # is loaded -- see complete_session).
        deepfake_analysis = svc['deepfake'].analyze_frame(frame, None, timestamp_ms)
        results['deepfake'] = {
            'is_fake': deepfake_analysis.is_fake,
            'probability': deepfake_analysis.fake_probability,
        }
        session['deepfake_probs'].append(deepfake_analysis.fake_probability)
        # Only probabilities that actually came from a trained model may gate the
        # verdict later; heuristic output stays advisory (see complete_session).
        if getattr(deepfake_analysis, 'model_derived', False):
            session.setdefault('deepfake_model_probs', []).append(deepfake_analysis.fake_probability)
        
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

        # Base weights per modality. A modality participates in the final score
        # ONLY when it produced real data during the session; absent modalities
        # are excluded and the remaining weights are renormalised. This replaces
        # the previous behaviour of feeding fixed placeholder values (a hardcoded
        # 0.7 expression score, empty-list calls returning neutral 0.3/0.5), which
        # let a session with no genuine signal inherit a passing score.
        base_weights = {
            'gaze': 0.30,
            'pulse': 0.25,
            'expression': 0.20,
            'deepfake': 0.15,
            'thermal': 0.10,
        }
        modality_scores: Dict[str, float] = {}

        # --- Gaze (cognitive challenge/response) ------------------------------
        # Real gaze liveness comes from evaluated challenge responses. Absent
        # those (no responses submitted), gaze contributes nothing.
        gaze_results = session.get('gaze_task_results', [])
        if gaze_results:
            modality_scores['gaze'] = self.gaze_service.get_liveness_score(gaze_results)

        # --- Pulse (rPPG heart rate) ------------------------------------------
        pulse_readings = session.get('pulse_readings', [])
        if len(pulse_readings) >= self.MIN_PULSE_READINGS:
            modality_scores['pulse'] = self.pulse_service.get_liveness_score(pulse_readings)

        # --- Micro-expression -------------------------------------------------
        # A real expression score requires detected MicroExpression sequences and
        # temporal analysis (Phase 2). Until that pipeline produces them, this
        # modality reports no data and is excluded rather than guessed.
        expression_score = session.get('expression_score')
        if expression_score is not None:
            modality_scores['expression'] = expression_score

        # --- Deepfake detection -----------------------------------------------
        # Only genuinely model-derived probabilities may gate the verdict. The
        # heuristic detector is advisory-only (reported in details), so its output
        # is excluded from scoring even if a model object is later assigned but
        # inference is not actually routed through it.
        deepfake_probs = session.get('deepfake_probs', [])
        deepfake_probability = float(np.mean(deepfake_probs)) if deepfake_probs else None
        model_probs = session.get('deepfake_model_probs', [])
        model_deepfake_probability = float(np.mean(model_probs)) if model_probs else None
        if model_deepfake_probability is not None:
            modality_scores['deepfake'] = 1.0 - model_deepfake_probability

        # --- Thermal ----------------------------------------------------------
        thermal_readings = session.get('thermal_readings', [])
        if self.thermal_service.is_available() and thermal_readings:
            modality_scores['thermal'] = self.thermal_service.get_liveness_score(thermal_readings)

        # Aggregate over present modalities only, with renormalised weights.
        present_weights = {m: base_weights[m] for m in modality_scores}
        total_weight = sum(present_weights.values())
        if total_weight > 0:
            overall = sum(
                modality_scores[m] * (present_weights[m] / total_weight)
                for m in modality_scores
            )
        else:
            overall = 0.0

        threshold = self.config.get('LIVENESS_THRESHOLD', 0.85)

        # Fail closed: require at least MIN_MODALITIES independent live signals
        # before a session can verify. No signal => INSUFFICIENT_SIGNAL, not pass.
        sufficient_signal = len(modality_scores) >= self.MIN_MODALITIES
        is_verified = sufficient_signal and overall >= threshold

        if not sufficient_signal:
            verdict = 'INSUFFICIENT_SIGNAL'
        elif overall >= 0.9:
            verdict = 'HIGH_CONFIDENCE_LIVE'
        elif overall >= threshold:
            verdict = 'VERIFIED_LIVE'
        elif overall >= 0.6:
            verdict = 'LOW_CONFIDENCE'
        else:
            verdict = 'SUSPECTED_FAKE'

        # Hard veto: a genuinely model-derived fake finding must fail the verdict
        # outright, rather than being averaged in and potentially outvoted by the
        # other modalities. Keyed on model-derived provenance (not merely a model
        # object being present), so heuristic output can never trigger it.
        if (
            model_deepfake_probability is not None
            and model_deepfake_probability >= self.deepfake_detector.FAKE_THRESHOLD
        ):
            is_verified = False
            verdict = 'SUSPECTED_FAKE'

        duration_ms = 0
        if session['started_at']:
            duration_ms = (session['completed_at'] - session['started_at']).total_seconds() * 1000

        return SessionResult(
            session_id=session_id,
            is_verified=is_verified,
            overall_liveness_score=overall,
            # Advisory only when the deepfake model is heuristic; 0.0 when no data.
            deepfake_probability=deepfake_probability if deepfake_probability is not None else 0.0,
            # Confidence reflects how many modalities actually contributed.
            confidence=float(len(modality_scores) / len(base_weights)),
            micro_expression_score=modality_scores.get('expression', 0.0),
            gaze_tracking_score=modality_scores.get('gaze', 0.0),
            pulse_oximetry_score=modality_scores.get('pulse', 0.0),
            thermal_score=modality_scores.get('thermal', 0.0),
            texture_artifact_score=(1.0 - deepfake_probability) if deepfake_probability is not None else 0.0,
            total_frames_processed=session['frames_processed'],
            duration_ms=duration_ms,
            verdict=verdict,
            details={
                'modalities_present': sorted(modality_scores.keys()),
                'modality_scores': modality_scores,
                'deepfake_advisory_probability': deepfake_probability,
                'deepfake_gates_verdict': 'deepfake' in modality_scores,
            },
        )
    
    def submit_challenge_response(self, session_id: str, response: Dict) -> Dict:
        """
        Evaluate a user's response to a cognitive challenge.

        For gaze challenges this scores the recorded gaze track against the
        session's randomized targets (accuracy, path similarity, human-likelihood)
        via the session's gaze service and records a real TaskResult -- which is
        what lets gaze contribute to the verdict in complete_session. A recorded
        or deepfake stream cannot follow the unpredictable targets in real time.
        """
        session = self.active_sessions.get(session_id)
        if not session:
            return {'error': 'Session not found'}
        if timezone.now() > session['expires_at']:
            session['status'] = 'expired'
            return {'error': 'Session expired'}

        challenges = session.get('challenges', [])
        idx = session.get('current_challenge_idx', 0)
        seq = response.get('sequence', idx)
        challenge = next((c for c in challenges if c.get('sequence') == seq), None)
        if challenge is None:
            return {'error': 'Unknown challenge'}

        summary: Dict = {'type': challenge['type'], 'sequence': seq, 'passed': None}

        if challenge['type'] == 'gaze':
            task = challenge.get('cognitive_task')
            gaze_data = self._parse_gaze_data(response.get('gaze_data', []))
            if task is not None:
                svc = session.get('services')
                if svc is None:
                    svc = self._new_session_services()
                    session['services'] = svc
                result = svc['gaze'].validate_task_response(
                    task, gaze_data, response.get('answer')
                )
                session.setdefault('gaze_task_results', []).append(result)
                summary['passed'] = bool(result.is_passed)
                summary['accuracy'] = float(result.accuracy_score)

        # Advance to the next challenge.
        session['current_challenge_idx'] = min(idx + 1, len(challenges))
        summary['next_challenge'] = session['current_challenge_idx'] < len(challenges)
        return summary

    def _parse_gaze_data(self, raw) -> List:
        """
        Convert client gaze samples into GazePoint objects, skipping malformed
        entries. The payload is never trusted to be well-formed.
        """
        from .gaze_tracking_service import GazePoint
        points: List = []
        if not isinstance(raw, list):
            return points
        for p in raw:
            if not isinstance(p, dict):
                continue
            try:
                points.append(GazePoint(
                    x=float(p['x']),
                    y=float(p['y']),
                    timestamp_ms=float(p.get('timestamp_ms', 0.0)),
                    confidence=float(p.get('confidence', 1.0)),
                    is_fixation=bool(p.get('is_fixation', False)),
                    pupil_diameter=(float(p['pupil_diameter'])
                                    if p.get('pupil_diameter') is not None else None),
                ))
            except (KeyError, TypeError, ValueError):
                continue
        return points

    def get_capabilities(self) -> Dict:
        """
        Report which liveness modalities are genuinely operational server-side.

        A modality is only advertised as gating the verdict when its real
        capability is present: deepfake detection needs a loaded model, thermal
        needs a configured IR source, and SpO2 can never come from the server at
        all (it requires client-side pulse-oximeter hardware). The client merges
        this with its own hardware detection (camera, BLE oximeter, thermal cam)
        so it only surfaces checks that can actually be performed.
        """
        deepfake_real = self.deepfake_detector.has_real_model()
        thermal_available = self.thermal_service.is_available()
        return {
            'modalities': {
                # Camera-based checks: the server implements them; the client
                # still needs a working camera to supply frames.
                'gaze': {
                    'available': True, 'source': 'camera', 'gates_verdict': True,
                    'note': 'Scored from the cognitive challenge-response.',
                },
                'pulse_rppg': {
                    'available': True, 'source': 'camera', 'gates_verdict': True,
                    'note': 'Heart rate only; SpO2 is never derived from webcam.',
                },
                # Captured today but not yet scored: complete_session only scores
                # expression once session['expression_score'] is populated, which
                # lands in a later Phase 2 step. gates_verdict=False matches the
                # scorer until then.
                'micro_expression': {
                    'available': True, 'source': 'camera', 'gates_verdict': False,
                    'note': 'Captured but not yet scored; gates the verdict in a later Phase 2 step.',
                },
                # Model-gated: heuristic output is advisory until a real model loads.
                'deepfake': {
                    'available': deepfake_real,
                    'source': 'model',
                    'advisory_only': not deepfake_real,
                    'gates_verdict': deepfake_real,
                },
                # Hardware-gated: never provided by the server.
                'spo2': {
                    'available': False,
                    'source': 'external_hardware',
                    'requires': 'ble_pulse_oximeter',
                    'gates_verdict': False,
                },
                'thermal': {
                    'available': thermal_available,
                    'source': 'thermal_camera',
                    'requires': 'ir_thermal_source',
                    'gates_verdict': thermal_available,
                },
            },
            'min_modalities_required': self.MIN_MODALITIES,
            'liveness_threshold': self.config.get('LIVENESS_THRESHOLD', 0.85),
        }

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
