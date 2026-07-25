"""
Cross-process liveness session store
=====================================

The liveness session service historically kept sessions in a per-worker dict
(``active_sessions``). That is correct only in a single process: with the REST
views and the WS consumer on separate workers/replicas, a session created by
one is invisible to the other. This module adds a Redis-backed store so session
state (accumulated rPPG buffers, gaze track, answered-challenge replay guard,
frozen verdict) is shared across every process, plus cross-process per-session
locking so two workers cannot score the same session concurrently.

The default backend stays the in-memory dict, byte-for-byte the prior behaviour,
so single-process deployments and the existing test-suite are unaffected. Redis
is opt-in via ``BIOMETRIC_LIVENESS['SESSION_STORE'] = 'redis'``.

Serialization is explicit (never pickle): the session dict holds dataclasses
(GazePoint, PulseReading, TaskResult, CognitiveTask, SessionResult), a datetime
per lifecycle field, a set (the replay guard) and per-session detector
instances. Each is converted to a JSON-safe form here; detectors round-trip via
their own snapshot_state/restore_state, and the loaded ML models are NOT
serialized (they are process-wide resources rebuilt on the far side).
"""

import json
import logging
import threading
import uuid
from datetime import datetime
from typing import Callable, Dict, List, Optional

from django.utils.dateparse import parse_datetime

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Dataclass (de)serialization
# --------------------------------------------------------------------------- #

def _dt(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value is not None else None


def _undt(value: Optional[str]) -> Optional[datetime]:
    return parse_datetime(value) if value else None


def _cognitive_task_to_json(task) -> Optional[Dict]:
    if task is None:
        return None
    return {
        'task_type': task.task_type.value,
        'instruction': task.instruction,
        'target_positions': [list(p) for p in task.target_positions],
        'time_limit_ms': task.time_limit_ms,
        'expected_sequence': task.expected_sequence,
        'correct_answer': task.correct_answer,
    }


def _cognitive_task_from_json(data) -> Optional[object]:
    if data is None:
        return None
    from .gaze_tracking_service import CognitiveTask, CognitiveTaskType
    return CognitiveTask(
        task_type=CognitiveTaskType(data['task_type']),
        instruction=data['instruction'],
        target_positions=[tuple(p) for p in data['target_positions']],
        time_limit_ms=data['time_limit_ms'],
        expected_sequence=data.get('expected_sequence'),
        correct_answer=data.get('correct_answer'),
    )


def _gaze_point_to_json(g) -> Dict:
    return {
        'x': g.x, 'y': g.y, 'timestamp_ms': g.timestamp_ms,
        'confidence': g.confidence, 'is_fixation': g.is_fixation,
        'pupil_diameter': g.pupil_diameter,
    }


def _gaze_point_from_json(d):
    from .gaze_tracking_service import GazePoint
    return GazePoint(
        x=d['x'], y=d['y'], timestamp_ms=d['timestamp_ms'],
        confidence=d['confidence'], is_fixation=d['is_fixation'],
        pupil_diameter=d.get('pupil_diameter'),
    )


def _pulse_reading_to_json(p) -> Dict:
    return {
        'timestamp_ms': p.timestamp_ms, 'frame_number': p.frame_number,
        'rgb_means': list(p.rgb_means), 'ppg_value': p.ppg_value,
        'heart_rate_bpm': p.heart_rate_bpm,
        'heart_rate_variability': p.heart_rate_variability,
        'spo2_estimate': p.spo2_estimate, 'signal_quality': p.signal_quality,
    }


def _pulse_reading_from_json(d):
    from .pulse_oximetry_service import PulseReading
    return PulseReading(
        timestamp_ms=d['timestamp_ms'], frame_number=d['frame_number'],
        rgb_means=tuple(d['rgb_means']), ppg_value=d['ppg_value'],
        heart_rate_bpm=d['heart_rate_bpm'],
        heart_rate_variability=d['heart_rate_variability'],
        spo2_estimate=d['spo2_estimate'], signal_quality=d['signal_quality'],
    )


def _task_result_to_json(r) -> Dict:
    return {
        'task_type': r.task_type.value, 'is_passed': r.is_passed,
        'accuracy_score': r.accuracy_score, 'reaction_time_ms': r.reaction_time_ms,
        'gaze_path_similarity': r.gaze_path_similarity,
        'human_likelihood_score': r.human_likelihood_score,
    }


def _task_result_from_json(d):
    from .gaze_tracking_service import TaskResult, CognitiveTaskType
    return TaskResult(
        task_type=CognitiveTaskType(d['task_type']), is_passed=d['is_passed'],
        accuracy_score=d['accuracy_score'], reaction_time_ms=d['reaction_time_ms'],
        gaze_path_similarity=d['gaze_path_similarity'],
        human_likelihood_score=d['human_likelihood_score'],
    )


def _session_result_to_json(r) -> Optional[Dict]:
    if r is None:
        return None
    return {
        'session_id': r.session_id, 'is_verified': r.is_verified,
        'overall_liveness_score': r.overall_liveness_score,
        'deepfake_probability': r.deepfake_probability, 'confidence': r.confidence,
        'micro_expression_score': r.micro_expression_score,
        'gaze_tracking_score': r.gaze_tracking_score,
        'pulse_oximetry_score': r.pulse_oximetry_score,
        'thermal_score': r.thermal_score,
        'texture_artifact_score': r.texture_artifact_score,
        'total_frames_processed': r.total_frames_processed,
        'duration_ms': r.duration_ms, 'verdict': r.verdict, 'details': r.details,
        'completed_at': _dt(r.completed_at),
    }


def _session_result_from_json(d) -> Optional[object]:
    if d is None:
        return None
    from .liveness_session_service import SessionResult
    return SessionResult(
        session_id=d['session_id'], is_verified=d['is_verified'],
        overall_liveness_score=d['overall_liveness_score'],
        deepfake_probability=d['deepfake_probability'], confidence=d['confidence'],
        micro_expression_score=d['micro_expression_score'],
        gaze_tracking_score=d['gaze_tracking_score'],
        pulse_oximetry_score=d['pulse_oximetry_score'],
        thermal_score=d['thermal_score'],
        texture_artifact_score=d['texture_artifact_score'],
        total_frames_processed=d['total_frames_processed'],
        duration_ms=d['duration_ms'], verdict=d['verdict'], details=d['details'],
        completed_at=_undt(d.get('completed_at')),
    )


def _services_to_json(services: Optional[Dict]) -> Dict:
    """Snapshot the stateful detectors (pulse/gaze/expression). Deepfake and
    thermal hold no verdict-relevant per-session state, so they are rebuilt
    fresh rather than serialized."""
    if not services:
        return {}
    out = {}
    for name in ('pulse', 'gaze', 'expression'):
        svc = services.get(name)
        if svc is not None and hasattr(svc, 'snapshot_state'):
            out[name] = svc.snapshot_state()
    return out


def _restore_services(services: Dict, snapshots: Dict) -> None:
    for name, state in (snapshots or {}).items():
        svc = services.get(name)
        if svc is not None and hasattr(svc, 'restore_state'):
            svc.restore_state(state)


def serialize_session(session: Dict) -> str:
    """Convert a live session dict to a JSON string for the shared store."""
    data = {
        'session_id': session['session_id'],
        'user_id': session.get('user_id'),
        'context': session.get('context'),
        'status': session.get('status'),
        'current_challenge_idx': session.get('current_challenge_idx', 0),
        'frames_processed': session.get('frames_processed', 0),
        'created_at': _dt(session.get('created_at')),
        'expires_at': _dt(session.get('expires_at')),
        'started_at': _dt(session.get('started_at')),
        'completed_at': _dt(session.get('completed_at')),
        'challenges': [
            {
                'type': c['type'], 'instruction': c.get('instruction'),
                'data': c.get('data', {}), 'sequence': c.get('sequence'),
                'cognitive_task': _cognitive_task_to_json(c.get('cognitive_task')),
            }
            for c in session.get('challenges', [])
        ],
        'pulse_readings': [_pulse_reading_to_json(p) for p in session.get('pulse_readings', [])],
        'deepfake_probs': list(session.get('deepfake_probs', [])),
        'deepfake_model_probs': list(session.get('deepfake_model_probs', [])),
        'expression_au_frames': session.get('expression_au_frames', 0),
        'gaze_samples': session.get('gaze_samples', 0),
        'gaze_track': [_gaze_point_to_json(g) for g in session.get('gaze_track', [])],
        'gaze_task_results': [_task_result_to_json(r) for r in session.get('gaze_task_results', [])],
        'thermal_readings': list(session.get('thermal_readings', [])),
        # A set is not JSON-native; store as a list, restore as a set.
        'answered_challenges': sorted(session.get('answered_challenges', set())),
        # JSON object keys are strings; the service uses int sequence keys.
        'challenge_activated_ms': {
            str(k): v for k, v in session.get('challenge_activated_ms', {}).items()
        },
        'failed_required_challenges': list(session.get('failed_required_challenges', [])),
        'expression_score': session.get('expression_score'),
        'result': _session_result_to_json(session.get('result')),
        'services': _services_to_json(session.get('services')),
    }
    # default=float is a belt-and-braces guard: the score producers are fixed at
    # source to return native floats, but a numpy scalar nested in
    # details['modality_scores'] (or added by future code) must never break the
    # single most important write in the flow -- persisting a completed verdict.
    return json.dumps(data, default=float)


def deserialize_session(blob: str, build_services: Callable[[], Dict]) -> Dict:
    """Rebuild a live session dict (incl. detector instances) from JSON."""
    data = json.loads(blob)
    services = build_services()
    _restore_services(services, data.get('services', {}))
    return {
        'session_id': data['session_id'],
        'user_id': data.get('user_id'),
        'context': data.get('context'),
        'status': data.get('status'),
        'current_challenge_idx': data.get('current_challenge_idx', 0),
        'frames_processed': data.get('frames_processed', 0),
        'created_at': _undt(data.get('created_at')),
        'expires_at': _undt(data.get('expires_at')),
        'started_at': _undt(data.get('started_at')),
        'completed_at': _undt(data.get('completed_at')),
        'challenges': [
            {
                'type': c['type'], 'instruction': c.get('instruction'),
                'data': c.get('data', {}), 'sequence': c.get('sequence'),
                'cognitive_task': _cognitive_task_from_json(c.get('cognitive_task')),
            }
            for c in data.get('challenges', [])
        ],
        'pulse_readings': [_pulse_reading_from_json(p) for p in data.get('pulse_readings', [])],
        'deepfake_probs': list(data.get('deepfake_probs', [])),
        'deepfake_model_probs': list(data.get('deepfake_model_probs', [])),
        'expression_au_frames': data.get('expression_au_frames', 0),
        'gaze_samples': data.get('gaze_samples', 0),
        'gaze_track': [_gaze_point_from_json(g) for g in data.get('gaze_track', [])],
        'gaze_task_results': [_task_result_from_json(r) for r in data.get('gaze_task_results', [])],
        'thermal_readings': list(data.get('thermal_readings', [])),
        'answered_challenges': set(data.get('answered_challenges', [])),
        'challenge_activated_ms': {
            int(k): v for k, v in data.get('challenge_activated_ms', {}).items()
        },
        'failed_required_challenges': list(data.get('failed_required_challenges', [])),
        'expression_score': data.get('expression_score'),
        'result': _session_result_from_json(data.get('result')),
        'services': services,
    }


# --------------------------------------------------------------------------- #
# Redis backend
# --------------------------------------------------------------------------- #

class RedisSessionStore:
    """
    Redis-backed shared session store with cross-process per-session locking.

    Layout:
      liveness:sess:<id>          JSON session, TTL = retention window
      liveness:live               SET of live (pending/in_progress) session ids
      liveness:ulive:<user_id>    SET of that user's live session ids
      liveness:lock:<id>          per-session mutex (SET NX PX, token value)
      liveness:clock              global lock guarding create capacity check

    Terminal/expired sessions are SREM'd from the live sets on save and left to
    TTL out of the session key, so no explicit age-eviction is needed. The live
    sets are self-healing: the capacity count drops ids whose session key no
    longer EXISTS (a crashed worker's leftover membership).
    """

    _KEY = 'liveness:sess:'
    _LIVE = 'liveness:live'
    _ULIVE = 'liveness:ulive:'
    _LOCK = 'liveness:lock:'
    _CREATE_LOCK = 'liveness:clock'

    def __init__(self, client, build_services: Callable[[], Dict],
                 retention_seconds: int, lock_ttl_ms: int = 15000):
        self.redis = client
        self._build_services = build_services
        self.retention_seconds = retention_seconds
        self.lock_ttl_ms = lock_ttl_ms
        # Per-session tokens for the currently-held lock on THIS thread, so
        # release only deletes a lock this call actually owns.
        self._local = threading.local()

    # -- session read/write ------------------------------------------------- #

    def load(self, session_id: str) -> Optional[Dict]:
        blob = self.redis.get(self._KEY + session_id)
        if blob is None:
            return None
        if isinstance(blob, bytes):
            blob = blob.decode('utf-8')
        return deserialize_session(blob, self._build_services)

    @staticmethod
    def _is_live(session: Dict) -> bool:
        """Pending/in_progress and not past its deadline."""
        from django.utils import timezone
        return (
            session.get('status') in ('pending', 'in_progress')
            and session.get('expires_at') is not None
            and session['expires_at'] > timezone.now()
        )

    def save(self, session_id: str, session: Dict) -> None:
        blob = serialize_session(session)
        is_live = self._is_live(session)
        if is_live:
            # Refresh the retention TTL while live so an active session never
            # expires mid-flight.
            self.redis.set(self._KEY + session_id, blob, ex=self.retention_seconds)
        else:
            # Terminal (or past-deadline): persist the frozen verdict but do NOT
            # renew the retention window -- keepttl lets it count down from when
            # the session was last live, so a client polling complete cannot keep
            # a terminal blob resident indefinitely by re-completing.
            self.redis.set(self._KEY + session_id, blob, keepttl=True)
            # KEEPTTL only PRESERVES an existing TTL; if the key had none -- it
            # expired+evicted between load and this save, or a first save that is
            # already terminal -- the blob would become PERSISTENT forever,
            # breaking the retention bound. Backfill retention with NX so an
            # existing countdown is untouched (no-op) but a TTL-less terminal
            # blob still expires (Redis 7+ EXPIRE NX).
            self.redis.expire(self._KEY + session_id, self.retention_seconds, nx=True)
        self._index_live(session_id, session, is_live)

    def delete(self, session_id: str) -> None:
        uid = self._local_user.get(session_id)
        if uid is None:
            # No cached owner (e.g. discard from a different worker): read it so
            # the user live-index entry is not orphaned.
            uid = self.owner_of(session_id)
        self.redis.delete(self._KEY + session_id)
        self.redis.srem(self._LIVE, session_id)
        if uid is not None:
            self.redis.srem(self._ULIVE + str(uid), session_id)

    def owner_of(self, session_id: str) -> Optional[int]:
        """Read only the owning user_id (no detector rebuild) for the frame path."""
        blob = self.redis.get(self._KEY + session_id)
        if blob is None:
            return None
        if isinstance(blob, bytes):
            blob = blob.decode('utf-8')
        try:
            return json.loads(blob).get('user_id')
        except (ValueError, TypeError):
            return None

    @property
    def _local_user(self) -> Dict:
        cache = getattr(self._local, 'user', None)
        if cache is None:
            cache = {}
            self._local.user = cache
        return cache

    def _index_live(self, session_id: str, session: Dict, is_live: bool) -> None:
        """Keep the live sets in sync with the session's current liveness."""
        uid = session.get('user_id')
        self._local_user[session_id] = uid
        ukey = self._ULIVE + str(uid)
        if is_live:
            self.redis.sadd(self._LIVE, session_id)
            self.redis.sadd(ukey, session_id)
            # Bound the index keys' lifetime to the retention window too.
            self.redis.pexpire(ukey, self.retention_seconds * 1000)
        else:
            self.redis.srem(self._LIVE, session_id)
            self.redis.srem(ukey, session_id)

    # -- per-session lock (SET NX PX + owned release) ----------------------- #

    def acquire(self, session_id: str) -> bool:
        token = uuid.uuid4().hex
        ok = self.redis.set(
            self._LOCK + session_id, token, nx=True, px=self.lock_ttl_ms)
        if ok:
            self._tokens[session_id] = token
            return True
        return False

    def release(self, session_id: str) -> None:
        token = self._tokens.pop(session_id, None)
        if token is None:
            return
        # Owned release: only delete if the lock still carries our token. The
        # get-then-delete window is bounded by lock_ttl_ms (>> a session op), and
        # a real deployment can swap in a Lua compare-and-delete; the in-process
        # RLock already serializes same-worker callers.
        current = self.redis.get(self._LOCK + session_id)
        if isinstance(current, bytes):
            current = current.decode('utf-8')
        if current == token:
            self.redis.delete(self._LOCK + session_id)

    @property
    def _tokens(self) -> Dict:
        cache = getattr(self._local, 'tokens', None)
        if cache is None:
            cache = {}
            self._local.tokens = cache
        return cache

    # -- capacity (atomic create) ------------------------------------------ #

    def count_live(self, user_id: int) -> tuple:
        """
        (global_live, user_live), self-healing stale membership.

        A crashed worker can leave a session id in the live sets after its
        session key TTLs out; drop those (key gone => not live) so they do not
        inflate the capacity count forever.
        """
        global_ids = [self._as_str(x) for x in self.redis.smembers(self._LIVE)]
        if global_ids:
            # Pipeline the existence checks into ONE round trip rather than one
            # EXISTS per member -- this runs while the global create-lock is held,
            # so N sequential round trips would serialize all cluster-wide creates
            # behind it.
            pipe = self.redis.pipeline()
            for sid in global_ids:
                pipe.exists(self._KEY + sid)
            present = pipe.execute()
            stale = [sid for sid, ok in zip(global_ids, present) if not ok]
            if stale:
                self.redis.srem(self._LIVE, *stale)
        live = self.redis.scard(self._LIVE)
        user_live = self.redis.scard(self._ULIVE + str(user_id))
        return live, user_live

    @staticmethod
    def _as_str(v):
        return v.decode('utf-8') if isinstance(v, bytes) else v

    def acquire_create_lock(self) -> bool:
        token = uuid.uuid4().hex
        ok = self.redis.set(self._CREATE_LOCK, token, nx=True, px=self.lock_ttl_ms)
        if ok:
            self._local.create_token = token
        return bool(ok)

    def release_create_lock(self) -> None:
        token = getattr(self._local, 'create_token', None)
        if token is None:
            return
        current = self._as_str(self.redis.get(self._CREATE_LOCK))
        if current == token:
            self.redis.delete(self._CREATE_LOCK)
        self._local.create_token = None
