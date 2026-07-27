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


# Server-side compare-and-X for the session locks. Both run atomically inside
# Redis, which is the whole point: a client-side GET-then-DELETE can delete a
# lock that expired and was re-acquired by another worker between the two calls.
_RELEASE_LUA = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
end
return 0
"""

_RENEW_LUA = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('pexpire', KEYS[1], ARGV[2])
end
return 0
"""


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


def _thermal_reading_to_json(t) -> Dict:
    """
    ThermalReading -> JSON.

    Nothing populates session['thermal_readings'] yet (no ingest path calls
    process_thermal_frame), so this is pre-emptive: without it, the FIRST save
    after a thermal ingest lands would raise TypeError, because json.dumps'
    default=float cannot coerce a dataclass. Every other dataclass in the blob
    already round-trips through a converter; this closes the one gap.
    """
    return {
        'timestamp_ms': t.timestamp_ms, 'frame_number': t.frame_number,
        'average_temp_c': t.average_temp_c, 'min_temp_c': t.min_temp_c,
        'max_temp_c': t.max_temp_c,
        'has_natural_gradient': t.has_natural_gradient,
        'matches_living_tissue': t.matches_living_tissue,
        'heat_map_features': dict(t.heat_map_features or {}),
    }


def _thermal_reading_from_json(d):
    from .thermal_imaging_service import ThermalReading
    return ThermalReading(
        timestamp_ms=d['timestamp_ms'], frame_number=d['frame_number'],
        average_temp_c=d['average_temp_c'], min_temp_c=d['min_temp_c'],
        max_temp_c=d['max_temp_c'],
        has_natural_gradient=d['has_natural_gradient'],
        matches_living_tissue=d['matches_living_tissue'],
        heat_map_features=d.get('heat_map_features', {}),
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
    """
    Snapshot the stateful detectors (pulse/gaze/expression).

    Deepfake and thermal are deliberately NOT snapshotted:

    * thermal -- scoring calls ``get_liveness_score(session['thermal_readings'])``
      on the shared singleton, a stateless call over readings the session dict
      already carries, so the per-session instance holds nothing the verdict
      reads.
    * deepfake -- the values that reach the verdict (``deepfake_probs`` /
      ``deepfake_model_probs``) live in the session dict and ARE serialized. The
      detector's own ``frame_history`` is a bounded 30-frame window of raw ROI
      PIXELS feeding one advisory sub-score (temporal consistency, 25% of the
      heuristic probability that by design never gates). Serializing megabytes of
      pixels on every locked save -- i.e. every frame -- would dwarf the session
      blob and throttle the hot path far worse than the divergence it removes;
      the window refills within 3 frames after a worker hand-off. Its
      ``analysis_history`` is unbounded and read only by ``get_overall_verdict``,
      which the session service never calls.

    FUTURE COUPLING (deepfake): the "advisory" half of that argument holds only
    while ``model_derived`` stays False on the heuristic path. If a trained
    detector is wired in and reuses ``analyze_frame``'s ensemble -- which folds
    ``temporal_score`` (i.e. ``frame_history``) into the same
    ``fake_probability`` -- then a per-frame Redis hand-off, which resets that
    window and pins ``temporal_score`` at its <3-frame default of 0.5, starts
    moving a VERDICT-GATING number. Whoever lands that model must either derive
    the model probability independently of ``frame_history`` or snapshot the
    window here; leaving both as-is would silently make cross-worker scoring
    differ from single-worker scoring.
    """
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
        'thermal_readings': [
            _thermal_reading_to_json(t) for t in session.get('thermal_readings', [])],
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
        'thermal_readings': [
            _thermal_reading_from_json(t) for t in data.get('thermal_readings', [])],
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
      liveness:live               ZSET of live session ids, scored by deadline
      liveness:ulive:<user_id>    ZSET of that user's live ids, same scoring
      liveness:lock:<id>          per-session mutex (SET NX PX, token value)
      liveness:clock              global lock guarding create capacity check

    The live indexes are ZSETs scored by the session's ``expires_at`` epoch, not
    plain SETs, because membership has to expire on its OWN. A session leaves the
    index when it is SAVED terminal -- but an ABANDONED one is never saved again,
    so a set could only be pruned by asking whether the key still exists, and the
    key outlives the deadline by the whole retention window. Those corpses then
    counted against MAX_USER_ACTIVE_SESSIONS, locking a user out of new
    verifications for minutes; the in-memory backend never did that, because it
    counts with _is_live(). Scoring by deadline lets ZREMRANGEBYSCORE drop every
    past-deadline id in one command, with no session blobs read -- so the count
    matches _is_live() and the capacity check stays cheap under the create lock.
    An id whose key has already TTL'd out is necessarily past its deadline too
    (retention > session timeout), so the same prune covers a crashed worker's
    leftover membership.

    DEPLOYMENT MINIMUM: **Redis 7.0+**. The terminal-save path uses ``EXPIRE ...
    NX`` to backfill a retention TTL without disturbing an existing countdown,
    and the NX/XX/GT/LT arguments to EXPIRE only exist from 7.0. On an older
    server that call errors instead of silently no-op'ing, so the requirement is
    loud rather than latent -- but note the test double accepts the kwarg
    without modelling TTL at all, so the suite passing is NOT evidence that the
    target server is new enough.
    """

    _KEY = 'liveness:sess:'
    _OWNER = 'liveness:owner:'
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
        # Registered once; redis-py computes the SHA lazily and EVALSHAs with an
        # automatic EVAL fallback, so this costs no round trip at construction.
        self._release_script = client.register_script(_RELEASE_LUA)
        self._renew_script = client.register_script(_RENEW_LUA)

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
            # Tiny side key carrying just the owner. The per-frame authorization
            # check (views._owns_in_memory_session -> owner_of) would otherwise
            # GET and json-parse the ENTIRE session blob on every frame, on top
            # of the full load process_frame already does under the lock -- two
            # fetches and two parses of a payload that grows all session.
            uid = session.get('user_id')
            if uid is not None:
                self.redis.set(
                    self._OWNER + session_id, uid, ex=self.retention_seconds)
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
        # Read the owner rather than caching it per thread: delete() is the rare
        # discard path (a failed DB create), so one extra GET here is cheaper
        # than a per-thread map that every save appends to and nothing evicts --
        # that grew by one entry per session for the life of a worker thread.
        # Must run BEFORE the delete, while the owner is still readable.
        uid = self.owner_of(session_id)
        self.redis.delete(self._KEY + session_id, self._OWNER + session_id)
        self.redis.zrem(self._LIVE, session_id)
        if uid is not None:
            self.redis.zrem(self._ULIVE + str(uid), session_id)

    def _raw(self, session_id: str) -> Optional[Dict]:
        """
        Parse the stored JSON without rebuilding anything.

        ``load`` is the expensive path: it runs deserialize_session, which calls
        build_services() to construct a fresh detector set and then replays the
        rPPG/gaze/expression accumulators into it. Read-only callers that want a
        handful of scalar fields must not pay for that.
        """
        blob = self.redis.get(self._KEY + session_id)
        if blob is None:
            return None
        if isinstance(blob, bytes):
            blob = blob.decode('utf-8')
        try:
            data = json.loads(blob)
        except (ValueError, TypeError):
            return None
        return data if isinstance(data, dict) else None

    def owner_of(self, session_id: str) -> Optional[int]:
        """
        The owning user_id, for the per-frame authorization check.

        Served from the small side key written alongside a live session, so this
        stays O(1) instead of scaling with the session blob. Falls back to
        parsing the blob when that key is absent -- a session saved by a worker
        older than the side key (rolling deploy), or a terminal one whose owner
        key has aged out. Neither is on the frame hot path.
        """
        raw = self.redis.get(self._OWNER + session_id)
        if raw is not None:
            if isinstance(raw, bytes):
                raw = raw.decode('utf-8')
            try:
                return int(raw)
            except (TypeError, ValueError):
                pass
        data = self._raw(session_id)
        return data.get('user_id') if data is not None else None

    def status_of(self, session_id: str) -> Optional[Dict]:
        """
        Metadata-only read for the polled status endpoint (no detector rebuild).

        Returns the same four fields get_session_status reports on, with
        expires_at already parsed back to a datetime.
        """
        data = self._raw(session_id)
        if data is None:
            return None
        return {
            'status': data.get('status'),
            'frames_processed': data.get('frames_processed', 0),
            'current_challenge_idx': data.get('current_challenge_idx', 0),
            'expires_at': _undt(data.get('expires_at')),
        }

    def _index_live(self, session_id: str, session: Dict, is_live: bool) -> None:
        """
        Keep the live indexes in sync with the session's current liveness.

        The score IS the deadline, which is what lets count_live drop members
        that expired without anyone saving them again (see the class docstring).
        """
        uid = session.get('user_id')
        # Defensive: create_session always stamps user_id, but an unowned
        # session must not create a 'liveness:ulive:None' bucket -- no
        # count_live(user_id) would ever prune it by user.
        ukey = self._ULIVE + str(uid) if uid is not None else None
        if is_live:
            deadline = session['expires_at'].timestamp()
            self.redis.zadd(self._LIVE, {session_id: deadline})
            if ukey:
                self.redis.zadd(ukey, {session_id: deadline})
                # Bound the index keys' lifetime to the retention window too.
                self.redis.pexpire(ukey, self.retention_seconds * 1000)
        else:
            self.redis.zrem(self._LIVE, session_id)
            if ukey:
                self.redis.zrem(ukey, session_id)

    # -- per-session lock (SET NX PX + atomic owned release/renew) ---------- #

    def acquire(self, session_id: str) -> bool:
        token = uuid.uuid4().hex
        ok = self.redis.set(
            self._LOCK + session_id, token, nx=True, px=self.lock_ttl_ms)
        if ok:
            self._tokens[session_id] = token
            return True
        return False

    def release(self, session_id: str) -> None:
        """
        Drop the lock, but ONLY if it still carries this thread's token.

        The compare and the delete happen server-side in one Lua call. A
        client-side GET-then-DELETE has a window in which the lease expires and
        another worker acquires the lock between the two commands, so the
        original holder deletes the NEW owner's lock and a third worker can then
        enter the same session concurrently.
        """
        token = self._tokens.pop(session_id, None)
        if token is None:
            return
        self._release_script(keys=[self._LOCK + session_id], args=[token])

    def renew(self, session_id: str) -> bool:
        """
        Extend this thread's lease, returning False if it was already lost.

        Callers use the return value as a fencing check before writing: a False
        means the lock expired mid-operation and some other worker may already
        own (and have mutated) the session, so the caller's in-hand copy is
        stale and must not be saved over the newer state. Also atomic, for the
        same reason as release.
        """
        token = self._tokens.get(session_id)
        if token is None:
            return False
        return bool(self._renew_script(
            keys=[self._LOCK + session_id], args=[token, self.lock_ttl_ms]))

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
        (global_live, user_live), matching the in-memory backend's _is_live().

        Drops every past-deadline id first. An ABANDONED session is never saved
        again, so nothing else would ever remove it: it would keep consuming a
        capacity slot for the whole retention window and could lock its owner out
        of new verifications. Pruning by score costs two commands regardless of
        index size and reads no session blobs -- this runs while the global
        create-lock is held, so it must not scale with the number of live
        sessions.
        """
        from django.utils import timezone
        now = timezone.now().timestamp()
        self.redis.zremrangebyscore(self._LIVE, '-inf', now)
        ukey = self._ULIVE + str(user_id)
        self.redis.zremrangebyscore(ukey, '-inf', now)
        return self.redis.zcard(self._LIVE), self.redis.zcard(ukey)

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
        # Same atomic compare-and-delete as the per-session lock: releasing a
        # create-lock that has already expired into another creator's hands
        # would let two workers run the capacity check concurrently, which is
        # exactly what this lock exists to prevent.
        self._release_script(keys=[self._CREATE_LOCK], args=[token])
        self._local.create_token = None
