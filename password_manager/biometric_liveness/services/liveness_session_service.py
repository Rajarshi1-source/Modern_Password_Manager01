"""
Liveness Session Service
=========================

Orchestrates the complete liveness verification session.
Coordinates all detection services and aggregates results.
"""

import functools
import logging
import threading
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


class SessionCapacityError(Exception):
    """Raised when the in-memory session store is at capacity (see MAX_ACTIVE_SESSIONS)."""


class GazeChallengeIncompleteError(ValueError):
    """
    Completion attempted while a required, measurable gaze challenge is unanswered.

    Unlike the terminal state errors (already completed / expired), this is
    RETRYABLE: complete_session raises it BEFORE marking the session terminal, so
    the client can answer gaze and complete. Subclasses ValueError so existing
    ``except ValueError`` fallbacks still treat it as a client/state error, while
    transports that catch it first can signal retryability distinctly.
    """


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


def _with_session_lock(method):
    """
    Serialize a session-mutating method against other callers of the same session.

    The service is a process-wide singleton shared by the REST views and the WS
    consumer, and both run on worker threads, so concurrent frames/responses for
    one session would otherwise interleave -- losing accumulator updates and
    letting two racing complete_session calls both pass the terminal-state check
    and score the same session twice. Different sessions never contend.
    """
    @functools.wraps(method)
    def wrapper(self, session_id, *args, **kwargs):
        if session_id not in self.active_sessions:
            # Nothing to serialize, and creating a lock here would let a caller
            # replaying unknown/evicted ids grow _session_locks unboundedly
            # between evictions. Session ids are server-generated uuid4s, so no
            # concurrent create can be racing this exact id into existence.
            return method(self, session_id, *args, **kwargs)
        with self._session_lock(session_id):
            return method(self, session_id, *args, **kwargs)
    return wrapper


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
    # Slack allowed on a challenge response's ARRIVAL time (network latency), on
    # top of the task's own time limit. The gaze samples that get scored are
    # still cut strictly at the deadline, so this cannot buy extra track.
    CHALLENGE_RESPONSE_GRACE_MS = 2000
    # How long past its deadline a session is kept before eviction. The store is
    # a process-wide singleton, so entries must not accumulate for the worker's
    # lifetime; retention keeps the already-completed/expired guards effective
    # for the whole time a client could still be calling with that session id.
    SESSION_RETENTION_SECONDS = 300
    # Hard cap on concurrent in-memory sessions per worker. Eviction bounds age,
    # not cardinality: a burst of start_session calls would otherwise grow the
    # store (and its per-session detectors) unbounded until retention expires.
    # Config-overridable; generous relative to real concurrency (~7 min lifetime).
    MAX_ACTIVE_SESSIONS = 1000

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
        # Per-session locks (see _with_session_lock), guarded by _store_lock so
        # two threads racing on a brand-new session get the same lock object.
        self._store_lock = threading.Lock()
        self._session_locks: Dict[str, threading.RLock] = {}

        logger.info("LivenessSessionService initialized")

    def _session_lock(self, session_id: str) -> threading.RLock:
        """Get (or create) the lock guarding one session's state."""
        with self._store_lock:
            lock = self._session_locks.get(session_id)
            if lock is None:
                lock = threading.RLock()
                self._session_locks[session_id] = lock
            return lock

    def discard_session(self, session_id: str) -> None:
        """
        Drop an in-memory session and its lock (e.g. when its DB row could not be
        created). Without this, an orphaned session would hold a live capacity
        slot until age-eviction. Membership mutation stays under _store_lock.
        """
        with self._store_lock:
            self.active_sessions.pop(session_id, None)
            self._session_locks.pop(session_id, None)

    def _evict_stale_sessions(self) -> None:
        """
        Drop sessions whose deadline passed more than SESSION_RETENTION_SECONDS
        ago, plus any orphaned locks.

        Without this, every completed/expired session would live for the lifetime
        of the worker process. Eviction is deliberately NOT done at completion:
        the terminal-state guards (status == 'completed'/'expired') must keep
        rejecting late frames and re-scoring attempts, which needs the entry to
        survive until the client can no longer plausibly be using it.
        """
        cutoff = timezone.now() - timedelta(seconds=self.SESSION_RETENTION_SECONDS)
        # Mutate active_sessions under _store_lock, the SAME lock create_session
        # holds while iterating it for the capacity count. Popping here without
        # the lock would race that iteration -> RuntimeError: dictionary changed
        # size during iteration. All active_sessions membership changes (this
        # pop and create_session's insert) are serialized by _store_lock; per-
        # session content is separately guarded by _with_session_lock.
        with self._store_lock:
            stale = [
                sid for sid, s in self.active_sessions.items()
                if s.get('expires_at') and s['expires_at'] < cutoff
            ]
            for sid in stale:
                self.active_sessions.pop(sid, None)
            for sid in [s for s in list(self._session_locks) if s not in self.active_sessions]:
                self._session_locks.pop(sid, None)
        if stale:
            logger.info(f"Evicted {len(stale)} stale liveness sessions")

    @staticmethod
    def _now_ms() -> float:
        """
        Server wall-clock epoch milliseconds.

        Same clock GazeTrackingService stamps onto each observed GazePoint, so
        challenge windows and gaze samples are directly comparable.
        """
        return timezone.now().timestamp() * 1000

    def _record_failed_required_challenge(self, session: Dict, challenge: Dict) -> None:
        """
        Note that a REQUIRED challenge failed, so it vetoes the verdict.

        Call this only when the modality was MEASURABLE and the user still did
        not satisfy the challenge -- either it was scored and did not pass, or
        its window closed with nothing observed (a deliberate skip).

        Never call it when the modality simply cannot be measured (no estimator
        loaded). That is a capability gap, not a failure: the modality is absent
        and contributes nothing, whereas recording a failure would veto every
        session in the current capability-gated state. Callers own that check --
        see the gaze_capable gate in submit_challenge_response.
        """
        required = self.config.get('REQUIRED_CHALLENGES', ['gaze', 'expression', 'pulse'])
        ctype = challenge.get('type')
        if ctype in required:
            session.setdefault('failed_required_challenges', []).append(ctype)

    def _required_gaze_unanswered(self, session: Dict) -> bool:
        """
        True if a REQUIRED, MEASURABLE gaze challenge has no recorded response.

        The failed-challenge veto only covers challenges that were attempted and
        failed (see _record_failed_required_challenge). A client that never calls
        submit_challenge_response for gaze would otherwise skip the randomized
        challenge entirely and still verify on other modalities. Gaze is the only
        required challenge scored via an explicit response; expression/pulse are
        accumulated passively from frames.

        Gated on the SAME capability check as the veto: when no estimator is
        loaded gaze cannot be measured, so a missing response is a capability gap
        (absent modality), not a skip, and must not block completion -- otherwise
        every session would fail in the current capability-gated state.
        """
        required = self.config.get('REQUIRED_CHALLENGES', ['gaze', 'expression', 'pulse'])
        if 'gaze' not in required:
            return False
        gaze = (session.get('services') or {}).get('gaze')
        if gaze is None or not gaze.has_real_gaze_model():
            return False
        answered = session.get('answered_challenges', set())
        return any(
            c.get('type') == 'gaze' and c.get('sequence') not in answered
            for c in session.get('challenges', [])
        )

    def _activate_current_challenge(self, session: Dict) -> None:
        """
        Stamp the server-side start of the current challenge's response window.

        Recorded once per challenge (the first stamp wins) so a client cannot
        reopen a window by replaying whatever opened it.
        """
        activated = session.setdefault('challenge_activated_ms', {})
        idx = session.get('current_challenge_idx', 0)
        if any(c.get('sequence') == idx for c in session.get('challenges', [])):
            activated.setdefault(idx, self._now_ms())
    
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
        # Bound the in-memory store: evict aged-out sessions, then refuse new
        # ones past the hard cap so a burst of start_session calls cannot grow
        # the store (and its per-session detectors) without limit.
        self._evict_stale_sessions()

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
            'gaze_track': [],               # server-observed gaze (from frames)
            'gaze_task_results': [],
            'thermal_readings': [],
            'answered_challenges': set(),   # replay guard: seq answered at most once
            # sequence -> server epoch ms the challenge's response window opened.
            'challenge_activated_ms': {},
            # Required challenges that were actually scored and FAILED. These
            # veto the verdict (see complete_session). A challenge that could
            # not be observed at all is NOT listed here -- that is an absent
            # modality, not a failure.
            'failed_required_challenges': [],
        }

        # Isolated per-session detectors so a concurrent session cannot clobber
        # this one's accumulated state (see _new_session_services).
        session['services'] = self._new_session_services()

        # Capacity check and insert in ONE critical section: doing the check and
        # the insert in separate locked blocks would let two concurrent creators
        # both pass the check and both insert, exceeding MAX_ACTIVE_SESSIONS.
        # Count only LIVE (pending/in_progress) sessions: terminal records
        # (completed/expired) are retained briefly for the replay/late-frame
        # guards and cleared by age-eviction, so counting them would let a user
        # who rapidly creates+completes sessions exhaust the cap and 503 genuine
        # new starts despite zero in-progress work.
        max_sessions = self.config.get('MAX_ACTIVE_SESSIONS', self.MAX_ACTIVE_SESSIONS)
        with self._store_lock:
            live = sum(1 for s in self.active_sessions.values()
                       if s.get('status') in ('pending', 'in_progress'))
            if live >= max_sessions:
                raise SessionCapacityError('Liveness session capacity reached')
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
                # Restrict to the gaze-trajectory task: it needs no verbal answer
                # channel (which the client does not yet provide), so the gate is
                # purely gaze-to-target correlation for now. Answer-based tasks
                # (COUNT_ITEMS/FIND_OBJECT) return once that channel exists.
                from .gaze_tracking_service import CognitiveTaskType
                task = self.gaze_service.generate_cognitive_task(
                    CognitiveTaskType.FOLLOW_TARGET
                )
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

    @_with_session_lock
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
        
        # Terminal state first: a completed verdict is final and must not be
        # reclassified as 'expired' (that would defeat the re-scoring guard in
        # complete_session, which keys off status == 'completed').
        if session['status'] == 'completed':
            return {'error': 'Session already completed'}
        if timezone.now() > session['expires_at']:
            session['status'] = 'expired'
            return {'error': 'Session expired'}

        if session['status'] == 'pending':
            session['status'] = 'in_progress'
            session['started_at'] = timezone.now()
            # The first challenge's response window opens with the first frame:
            # that is the earliest point the client can be observed at all.
            self._activate_current_challenge(session)

        session['frames_processed'] += 1

        # Defensive: ensure per-session accumulators exist even if this session
        # dict was created outside create_session (e.g. a future shared-store
        # path), so frame accumulation below can never KeyError.
        session.setdefault('pulse_readings', [])
        session.setdefault('deepfake_probs', [])
        session.setdefault('deepfake_model_probs', [])
        session.setdefault('expression_au_frames', 0)
        session.setdefault('gaze_samples', 0)
        session.setdefault('gaze_track', [])
        session.setdefault('challenge_activated_ms', {})

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

        # Gaze tracking (server-observed). estimate_gaze only returns a point
        # when a real gaze estimator is loaded; that sample -- not any client-
        # supplied track -- is what the challenge is scored against.
        gaze_point = svc['gaze'].estimate_gaze(frame, face_landmarks)
        if gaze_point:
            # Keep estimate_gaze's server-assigned timestamp; do NOT trust the
            # client frame timestamp for the ordering/velocity used in scoring.
            results['gaze'] = {
                'x': gaze_point.x,
                'y': gaze_point.y,
                'confidence': gaze_point.confidence,
            }
            session['gaze_samples'] += 1
            session.setdefault('gaze_track', []).append(gaze_point)

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
    
    @_with_session_lock
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
        # A verdict is final. Refuse to re-score a completed session -- otherwise
        # a failing session could be upgraded by submitting more frames and
        # calling complete again.
        if session.get('status') == 'completed':
            raise ValueError('Session already completed')
        # An expired session must not be scored at all.
        if session.get('status') == 'expired' or timezone.now() > session['expires_at']:
            session['status'] = 'expired'
            raise ValueError('Session expired')

        # A required, measurable gaze challenge that was never answered blocks
        # verification. Raised (not vetoed) BEFORE the terminal transition so the
        # session stays retryable: an honest client that completed prematurely can
        # still answer gaze and finish, while a client that omits it cannot verify
        # on other modalities. "Never attempted" is not "detected fake", so this
        # is a state error, not a SUSPECTED_FAKE verdict (which the veto reserves
        # for challenges actually attempted and failed).
        if self._required_gaze_unanswered(session):
            raise GazeChallengeIncompleteError('Required gaze challenge incomplete')

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

        # Hard veto: failing a REQUIRED randomized challenge is a positive fake
        # signal. Dropping the modality alone would let the remaining modalities
        # (e.g. rPPG + a real deepfake model) still carry the session over the
        # threshold, so the cognitive challenge would stop being a real gate.
        failed_required = session.get('failed_required_challenges', [])
        if failed_required:
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
                'failed_required_challenges': sorted(set(failed_required)),
            },
        )
    
    @_with_session_lock
    def submit_challenge_response(self, session_id: str, response: Dict) -> Dict:
        """
        Evaluate a user's response to a cognitive challenge.

        For gaze challenges this scores the recorded gaze track against the
        session's randomized targets (accuracy, path similarity, human-likelihood)
        via the session's gaze service and records a real TaskResult -- which is
        what lets gaze contribute to the verdict in complete_session. A recorded
        or deepfake stream cannot follow the unpredictable targets in real time.
        """
        # Untrusted payload: an explicit null / non-object 'response' must not
        # reach .get() below (that raised AttributeError -> 500).
        if not isinstance(response, dict):
            response = {}
        session = self.active_sessions.get(session_id)
        if not session:
            return {'error': 'Session not found'}
        # Terminal state first (see process_frame): a completed verdict must not
        # be reclassified as expired.
        if session.get('status') == 'completed':
            return {'error': 'Session already completed'}
        if timezone.now() > session['expires_at']:
            session['status'] = 'expired'
            return {'error': 'Session expired'}

        challenges = session.get('challenges', [])
        idx = session.get('current_challenge_idx', 0)
        seq = response.get('sequence', idx)
        challenge = next((c for c in challenges if c.get('sequence') == seq), None)
        if challenge is None:
            return {'error': 'Unknown challenge'}
        # Replay guard: each challenge is answerable once, so a client cannot
        # re-consume one challenge to advance past (and skip) the others.
        answered = session.setdefault('answered_challenges', set())
        if seq in answered:
            return {'error': 'Challenge already answered'}

        summary: Dict = {'type': challenge['type'], 'sequence': seq}
        # A challenge is only consumed by a response that could actually be
        # evaluated. A premature response (window not open yet, or no gaze seen
        # so far while the window is still running) stays retryable -- consuming
        # it would let a client burn the challenge without ever being scored.
        consume = True

        if challenge['type'] == 'gaze':
            task = challenge.get('cognitive_task')
            svc = session.get('services')
            if svc is None:
                svc = self._new_session_services()
                session['services'] = svc
            # Whether gaze can be measured at all right now. When it cannot, a
            # missing track is a capability gap (absent modality); when it can,
            # a missing track means the user did not do the challenge.
            gaze_capable = svc['gaze'].has_real_gaze_model()
            # Score ONLY the server-observed gaze track (accumulated from the
            # submitted frames). A client-supplied track is ignored -- it can be
            # synthesized from the known target positions and would not prove
            # liveness. With no real gaze estimator loaded, no track exists, so
            # gaze records nothing and does not gate the verdict.
            activated_ms = session.get('challenge_activated_ms', {}).get(seq)
            now_ms = self._now_ms()
            if task is None or activated_ms is None:
                # Nothing was ever asked of the user; keep it retryable.
                summary['passed'] = False
                summary['reason'] = 'challenge_not_started'
                consume = False
            elif now_ms > activated_ms + task.time_limit_ms + self.CHALLENGE_RESPONSE_GRACE_MS:
                summary['passed'] = False
                summary['reason'] = 'challenge_window_expired'
                # The window closed unanswered. With gaze measurable, that is a
                # deliberate skip, not a capability gap -- veto it, or a client
                # could dodge the challenge and still verify on other modalities.
                if gaze_capable:
                    self._record_failed_required_challenge(session, challenge)
            else:
                # Cut the track to this challenge's own advertised window. The
                # targets are disclosed to the client, so scoring the whole
                # session-lifetime track would let a stream keep wandering until
                # it eventually covered them -- the time limit IS the challenge.
                deadline_ms = activated_ms + task.time_limit_ms
                window_track = [
                    g for g in session.get('gaze_track', [])
                    if activated_ms <= g.timestamp_ms <= deadline_ms
                ]
                if not window_track:
                    summary['passed'] = False
                    summary['reason'] = 'no_gaze_observed'
                    if now_ms <= deadline_ms:
                        # Still inside the window: too early to judge, retryable.
                        consume = False
                    elif gaze_capable:
                        # Window ran out with nothing observed -- same skip as above.
                        self._record_failed_required_challenge(session, challenge)
                else:
                    result = svc['gaze'].validate_task_response(
                        task, window_track, response.get('answer')
                    )
                    summary['passed'] = bool(result.is_passed)
                    summary['accuracy'] = float(result.accuracy_score)
                    # Only a PASSED challenge counts as a live gaze signal. A
                    # failed track (poor accuracy/human-likelihood, or a wrong
                    # answer) must not contribute a partial score to the verdict.
                    if result.is_passed:
                        session.setdefault('gaze_task_results', []).append(result)
                    else:
                        summary['reason'] = 'gaze_challenge_failed'
                        # We OBSERVED the user's gaze and it failed the
                        # randomized challenge -- a positive fake signal, not a
                        # missing one. Omitting the modality is not enough:
                        # other passing modalities could still carry the verdict
                        # over the threshold. Record it so completion vetoes.
                        self._record_failed_required_challenge(session, challenge)
        else:
            # Expression/pulse have no per-challenge verdict here.
            summary['status'] = 'acknowledged'

        if not consume:
            # Challenge stays current and unanswered; the client may retry it.
            summary['next_challenge'] = True
            return summary

        # Mark this challenge answered and point the index at the lowest
        # unanswered sequence (not merely the count), so a later request that
        # omits 'sequence' targets the right challenge even after an out-of-order
        # answer, and a skipped challenge still has to be completed.
        answered.add(seq)
        remaining = sorted(c['sequence'] for c in challenges if c['sequence'] not in answered)
        session['current_challenge_idx'] = remaining[0] if remaining else len(challenges)
        if remaining and session.get('status') == 'in_progress':
            # Open the next challenge's window only once frames are actually being
            # processed. If the session is still 'pending' (a response arrived
            # before any frame), opening the window now would let it count down --
            # and potentially expire -- before the first observable frame. The
            # first frame's process_frame activates the then-current challenge.
            self._activate_current_challenge(session)
        summary['next_challenge'] = bool(remaining)
        return summary

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
        gaze_real = self.gaze_service.has_real_gaze_model()
        return {
            'modalities': {
                # Camera-based checks: the server implements them; the client
                # still needs a working camera to supply frames.
                # Gaze reports available only once a real estimator is loaded:
                # without one estimate_gaze() returns nothing (unlike expression,
                # which captures real AU frames), so advertising it as available
                # would invite the client to render an unscoreable challenge.
                'gaze': {
                    'available': gaze_real, 'source': 'camera',
                    'gates_verdict': gaze_real,
                    'note': 'Server-observed gaze scored against the cognitive '
                            'challenge; available and gating only with a real estimator.',
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
