"""
Gaze Tracking Service
======================

Eye tracking with cognitive load tasks for liveness detection.
AI-generated faces cannot solve novel real-time cognitive problems.

Features:
- Track gaze point from video frames
- Generate cognitive challenges (follow target, solve puzzles)
- Validate human-like gaze patterns
- Detect screen/photo-based attacks via gaze behavior
"""

import logging
import random
import math
from collections import deque
from typing import ClassVar, Deque, Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import numpy as np

logger = logging.getLogger(__name__)


class CognitiveTaskType(Enum):
    """Types of cognitive tasks for gaze verification."""
    FOLLOW_TARGET = 'follow_target'
    FIND_OBJECT = 'find_object'
    READ_TEXT = 'read_text'
    COUNT_ITEMS = 'count_items'
    TRACE_PATH = 'trace_path'


@dataclass
class GazePoint:
    """Single gaze measurement."""
    x: float  # Normalized 0-1
    y: float  # Normalized 0-1
    timestamp_ms: float
    confidence: float
    is_fixation: bool
    pupil_diameter: Optional[float] = None


@dataclass
class CognitiveTask:
    """Cognitive challenge definition."""
    task_type: CognitiveTaskType
    instruction: str
    target_positions: List[Tuple[float, float]]  # Expected gaze targets
    time_limit_ms: int
    expected_sequence: Optional[List[int]] = None  # Order of targets
    correct_answer: Optional[str] = None


@dataclass
class TaskResult:
    """Result of a cognitive task."""
    task_type: CognitiveTaskType
    is_passed: bool
    accuracy_score: float
    reaction_time_ms: float
    gaze_path_similarity: float
    human_likelihood_score: float


class GazeTrackingService:
    """
    Gaze tracking service for liveness verification.
    
    Uses eye tracking to:
    1. Verify human presence (natural saccades and fixations)
    2. Present cognitive tasks that require real-time solving
    3. Detect artificial/pre-recorded gaze patterns
    """
    
    # Configuration
    DEFAULT_FIXATION_THRESHOLD_MS = 100  # Min duration for fixation
    DEFAULT_SACCADE_VELOCITY_THRESHOLD = 30  # deg/sec
    NATURAL_SACCADE_AMPLITUDE_RANGE = (2, 45)  # degrees

    # Per-session gaze track window: the append cap and the snapshot cap are the
    # same number so both backends hold identical history.
    GAZE_HISTORY_POINTS = 256

    # Normalized distance within which a gaze sample counts as ON a target.
    # Shared by accuracy, reaction time and path similarity: all three describe
    # the same "looked at target i" event, so if they disagreed a sample could
    # score as on-target for one metric and off-target for another.
    TARGET_HIT_RADIUS = 0.15

    # The trained gaze estimator is a PROCESS-WIDE resource, held at CLASS scope
    # so every instance observes the same has_real_gaze_model() state: the
    # capabilities singleton (which get_capabilities queries but which never
    # processes frames) AND each per-session service used for scoring/completion.
    # If it were per-instance, the singleton would never load a model while
    # per-session instances did, so capabilities would advertise gaze unavailable
    # while sessions actively scored it (and the client would suppress the
    # challenge UI). Loading it once class-wide also avoids duplicating a large
    # model per session.
    _gaze_model = None

    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize gaze tracking service.

        Args:
            config: Configuration options
        """
        self.config = config or {}
        # Bounded at the APPEND side, to the same window snapshot_state
        # serializes, so an in-memory session and one handed off through Redis
        # hold identical history. Scoring-neutral: _classify_gaze_event only
        # reads the previous point, never the whole track.
        self.gaze_history: Deque[GazePoint] = deque(maxlen=self.GAZE_HISTORY_POINTS)
        self.current_task: Optional[CognitiveTask] = None

        # Task parameters
        self.num_tracking_points = self.config.get('gaze_tracking_points', 9)
        self.task_timeout_ms = self.config.get('cognitive_task_timeout_ms', 5000)

        logger.info("GazeTrackingService initialized")

    def _init_gaze_model(self):
        """Lazily bind the shared face landmarker as the gaze estimator (idempotent)."""
        # The real gaze estimator is the shared MediaPipe Tasks FaceLandmarker
        # (iris landmarks 468-477). Stored on the CLASS -- per the round-23
        # contract -- so the capabilities singleton and every per-session
        # instance report the same has_real_gaze_model() state. The loader owns
        # the double-checked load lock AND a load-attempted sentinel, so this
        # call is lock-free on every frame whether the model is loaded or
        # permanently absent (the round-29 constraint). Without the model asset
        # configured, get_face_landmarker() returns None and gaze stays
        # unavailable everywhere -- never a placeholder.
        if GazeTrackingService._gaze_model is not None:
            return
        from ..ml_models.face_landmarker import get_face_landmarker
        model = get_face_landmarker()
        if model is not None:
            GazeTrackingService._gaze_model = model

    def has_real_gaze_model(self) -> bool:
        """
        True only when a genuinely trained gaze estimator is loaded.

        Resolves the shared (class-level) model first so the answer reflects the
        real operational capability even on the singleton -- which get_capabilities
        queries but which never processes frames. Without a model estimate_gaze
        cannot measure real eye position, so gaze must not gate a liveness verdict
        (a placeholder position would be a fabricated signal); callers use this to
        keep gaze capability-gated.
        """
        self._init_gaze_model()
        return GazeTrackingService._gaze_model is not None
    
    def estimate_gaze(
        self, 
        frame: np.ndarray,
        face_landmarks: Optional[np.ndarray] = None
    ) -> Optional[GazePoint]:
        """
        Estimate gaze point from video frame.
        
        Args:
            frame: RGB image frame
            face_landmarks: Pre-detected facial landmarks
            
        Returns:
            Estimated gaze point or None
        """
        # Do not fabricate a gaze position. Without the real landmarker loaded
        # there is nothing to measure with, so we report "no observation" and
        # gaze simply does not contribute to the verdict. (has_real_gaze_model
        # resolves the shared model itself, so no separate init call here.)
        if not self.has_real_gaze_model():
            return None

        try:
            # Reuse landmarks already extracted this frame (the expression
            # analyzer runs the same shared landmarker) when they carry the
            # iris ring (478-point set); otherwise run the landmarker here.
            # Never fall back to anything that does not measure the real eyes.
            landmarks = None
            if face_landmarks is not None and len(face_landmarks) >= 478:
                landmarks = np.asarray(face_landmarks)
            else:
                from ..ml_models.face_landmarker import detect_face
                detection = detect_face(frame)
                if detection is not None:
                    landmarks, _ = detection
            if landmarks is None:
                return None

            gaze = self._gaze_from_landmarks(landmarks)
            if gaze is None:
                return None
            gaze_x, gaze_y, confidence = gaze

            # Determine if fixation or saccade
            is_fixation = self._classify_gaze_event(gaze_x, gaze_y)

            gaze_point = GazePoint(
                x=gaze_x,
                y=gaze_y,
                timestamp_ms=self._get_current_time_ms(),
                confidence=confidence,
                is_fixation=is_fixation,
                # No real pupil detector (iris diameter is not pupil diameter);
                # report nothing rather than inventing a measurement.
                pupil_diameter=None,
            )

            self.gaze_history.append(gaze_point)
            return gaze_point

        except Exception as e:
            logger.error(f"Gaze estimation failed: {e}")
            return None

    # MediaPipe FaceMesh indices (478-point set with iris refinement).
    # "Eye A"/"Eye B" rather than left/right: side naming differs between
    # references, and nothing verdict-relevant depends on which is which --
    # only that the two eyes are measured consistently.
    _EYE_A: ClassVar[Dict[str, int]] = {
        'iris': 468, 'corner1': 33, 'corner2': 133, 'top': 159, 'bottom': 145}
    _EYE_B: ClassVar[Dict[str, int]] = {
        'iris': 473, 'corner1': 362, 'corner2': 263, 'top': 386, 'bottom': 374}

    @classmethod
    def _gaze_from_landmarks(
        cls, landmarks: np.ndarray
    ) -> Optional[Tuple[float, float, float]]:
        """
        Normalized gaze point from iris-in-socket geometry -- a REAL measurement.

        For each eye, the iris center's position between the eye corners
        (horizontal) and between the lids (vertical) tracks where the eye is
        pointed; averaging both eyes cancels head-pose noise to first order.
        Coordinates are IMAGE-space (uncalibrated): per-user calibration and
        any client mirror-flip handling are tracked follow-ups -- they affect
        sensitivity/orientation of a real measurement, not whether one exists.

        Confidence derives from measurement conditions (eye openness and the
        iris staying inside the socket bounds), so occluded/blinking frames
        score low instead of being trusted equally.

        Returns (gaze_x, gaze_y, confidence) in [0, 1], or None when the
        geometry is degenerate (closed eyes, zero-size face, missing iris ring).
        """
        lm = np.asarray(landmarks, dtype=np.float64)
        if lm.ndim != 2 or lm.shape[0] < 478:
            return None

        def eye_ratios(idx):
            iris = lm[idx['iris']]
            c1, c2 = lm[idx['corner1']], lm[idx['corner2']]
            top, bottom = lm[idx['top']], lm[idx['bottom']]
            x_lo, x_hi = min(c1[0], c2[0]), max(c1[0], c2[0])
            width = x_hi - x_lo
            height = bottom[1] - top[1]
            if width < 1e-6 or height < 1e-6:
                return None  # degenerate/closed eye: nothing to measure
            hx = (iris[0] - x_lo) / width       # 0..1 across the eye opening
            vy = (iris[1] - top[1]) / height    # 0..1 between the lids
            openness = height / width           # ~0.25-0.4 for an open eye
            return hx, vy, openness

        a = eye_ratios(cls._EYE_A)
        b = eye_ratios(cls._EYE_B)
        if a is None or b is None:
            return None

        gaze_x = float(np.clip((a[0] + b[0]) / 2, 0.0, 1.0))
        gaze_y = float(np.clip((a[1] + b[1]) / 2, 0.0, 1.0))

        # Openness in a normal open-eye band and iris within the socket bounds
        # => trustworthy sample; blinking or off-model geometry decays it.
        openness = (a[2] + b[2]) / 2
        open_score = float(np.clip(openness / 0.25, 0.0, 1.0))
        in_bounds = all(-0.2 <= r <= 1.2 for r in (a[0], b[0], a[1], b[1]))
        confidence = round(open_score * (1.0 if in_bounds else 0.4), 4)
        if confidence <= 0.0:
            return None
        return gaze_x, gaze_y, confidence

    def _classify_gaze_event(self, gaze_x: float, gaze_y: float) -> bool:
        """Classify current gaze as fixation or saccade."""
        if len(self.gaze_history) < 2:
            return True  # Assume fixation for first points
        
        prev = self.gaze_history[-1]
        
        # Calculate velocity
        time_diff = self._get_current_time_ms() - prev.timestamp_ms
        if time_diff <= 0:
            return True
        
        distance = math.sqrt((gaze_x - prev.x)**2 + (gaze_y - prev.y)**2)
        velocity = distance / (time_diff / 1000)  # per second
        
        # Low velocity = fixation
        return velocity < 0.5  # Threshold in normalized units

    def _get_current_time_ms(self) -> float:
        """Get current timestamp in milliseconds."""
        import time
        return time.time() * 1000
    
    def generate_cognitive_task(
        self, 
        task_type: Optional[CognitiveTaskType] = None,
        difficulty: str = 'medium'
    ) -> CognitiveTask:
        """
        Generate a cognitive challenge for gaze verification.
        
        Args:
            task_type: Specific task type or random
            difficulty: easy/medium/hard
            
        Returns:
            Generated cognitive task
        """
        if task_type is None:
            task_type = random.choice(list(CognitiveTaskType))
        
        if task_type == CognitiveTaskType.FOLLOW_TARGET:
            return self._generate_follow_target_task(difficulty)
        elif task_type == CognitiveTaskType.FIND_OBJECT:
            return self._generate_find_object_task(difficulty)
        elif task_type == CognitiveTaskType.COUNT_ITEMS:
            return self._generate_count_items_task(difficulty)
        elif task_type == CognitiveTaskType.TRACE_PATH:
            return self._generate_trace_path_task(difficulty)
        else:
            return self._generate_follow_target_task(difficulty)
    
    def _generate_follow_target_task(self, difficulty: str) -> CognitiveTask:
        """Generate a target-following task."""
        num_points = {'easy': 5, 'medium': 7, 'hard': 9}[difficulty]
        time_limit = {'easy': 6000, 'medium': 5000, 'hard': 4000}[difficulty]
        
        # Generate random target positions
        positions = []
        for _ in range(num_points):
            x = random.uniform(0.1, 0.9)
            y = random.uniform(0.1, 0.9)
            positions.append((x, y))
        
        return CognitiveTask(
            task_type=CognitiveTaskType.FOLLOW_TARGET,
            instruction="Follow the moving dot with your eyes",
            target_positions=positions,
            time_limit_ms=time_limit,
            expected_sequence=list(range(num_points))
        )
    
    def _generate_find_object_task(self, difficulty: str) -> CognitiveTask:
        """Generate an object-finding task."""
        num_objects = {'easy': 3, 'medium': 5, 'hard': 7}[difficulty]
        
        positions = []
        for _ in range(num_objects):
            x = random.uniform(0.1, 0.9)
            y = random.uniform(0.1, 0.9)
            positions.append((x, y))
        
        return CognitiveTask(
            task_type=CognitiveTaskType.FIND_OBJECT,
            instruction="Find and look at each highlighted object",
            target_positions=positions,
            time_limit_ms=8000,
            correct_answer=str(num_objects)
        )
    
    def _generate_count_items_task(self, difficulty: str) -> CognitiveTask:
        """Generate a counting task."""
        count = {'easy': 3, 'medium': 5, 'hard': 7}[difficulty]
        
        positions = []
        for _ in range(count):
            x = random.uniform(0.1, 0.9)
            y = random.uniform(0.1, 0.9)
            positions.append((x, y))
        
        return CognitiveTask(
            task_type=CognitiveTaskType.COUNT_ITEMS,
            instruction=f"Count the blue circles",
            target_positions=positions,
            time_limit_ms=6000,
            correct_answer=str(count)
        )
    
    def _generate_trace_path_task(self, difficulty: str) -> CognitiveTask:
        """Generate a path-tracing task."""
        num_waypoints = {'easy': 4, 'medium': 6, 'hard': 8}[difficulty]
        
        # Generate a smooth path
        positions = []
        for i in range(num_waypoints):
            angle = (i / num_waypoints) * 2 * math.pi
            radius = 0.3 + random.uniform(-0.1, 0.1)
            x = 0.5 + radius * math.cos(angle)
            y = 0.5 + radius * math.sin(angle)
            positions.append((x, y))
        
        return CognitiveTask(
            task_type=CognitiveTaskType.TRACE_PATH,
            instruction="Trace the path with your eyes from start to end",
            target_positions=positions,
            time_limit_ms=7000,
            expected_sequence=list(range(num_waypoints))
        )
    
    def validate_task_response(
        self,
        task: CognitiveTask,
        gaze_data: List[GazePoint],
        user_answer: Optional[str] = None,
        challenge_start_ms: Optional[float] = None,
    ) -> TaskResult:
        """
        Validate user's gaze response to cognitive task.

        Args:
            task: The cognitive task
            gaze_data: Recorded gaze points during task
            user_answer: User's explicit answer (for counting tasks)
            challenge_start_ms: Server epoch ms the challenge window opened. When
                given, reaction_time_ms is the real latency from onset to the
                first on-target gaze; omitted (legacy callers/tests) leaves it 0.

        Returns:
            Task validation result
        """
        if not gaze_data:
            return TaskResult(
                task_type=task.task_type,
                is_passed=False,
                accuracy_score=0.0,
                reaction_time_ms=0,
                gaze_path_similarity=0.0,
                human_likelihood_score=0.0
            )

        # Order the track ONCE. Path similarity and reaction time both need
        # time-ordered samples, and accuracy's one-sample-per-target consumption
        # is likewise better spent oldest-first; sorting per metric repeated the
        # same O(n log n) over a track that can hold a whole challenge window.
        ordered = sorted(gaze_data, key=lambda g: g.timestamp_ms)

        # Calculate metrics
        accuracy = self._calculate_gaze_accuracy(task, ordered)
        path_similarity = self._calculate_path_similarity(task, ordered)
        # Real reaction latency: onset -> first on-target gaze. Only computed
        # when the caller supplies the server-owned challenge start; otherwise 0
        # (never the first sample's absolute epoch timestamp, which is not a
        # reaction time).
        reaction_time = self._calculate_reaction_time(task, ordered, challenge_start_ms)
        human_score = self._calculate_human_likelihood(ordered)
        
        # If the task has a correct answer, a matching answer is REQUIRED. A
        # missing/blank answer must not pass the cognitive part for free.
        # user_answer is untyped client input, so coerce to str before strip().
        answer_correct = True
        if task.correct_answer:
            answer_correct = (
                user_answer is not None
                and str(user_answer).strip() == task.correct_answer
            )
        
        # Determine if passed. Path similarity only applies to tasks that define
        # an expected trajectory (expected_sequence); answer-based tasks
        # (FIND_OBJECT/COUNT_ITEMS) have none, so _calculate_path_similarity
        # returns 0.0 for them and an unconditional check would always fail.
        is_passed = (
            accuracy > 0.6 and
            (not task.expected_sequence or path_similarity > 0.5) and
            human_score > 0.6 and
            answer_correct
        )
        
        return TaskResult(
            task_type=task.task_type,
            is_passed=is_passed,
            accuracy_score=accuracy,
            reaction_time_ms=reaction_time,
            gaze_path_similarity=path_similarity,
            human_likelihood_score=human_score
        )
    
    def _calculate_gaze_accuracy(
        self,
        task: CognitiveTask,
        gaze_data: List[GazePoint]
    ) -> float:
        """
        Fraction of targets the user actually looked at.

        Each gaze sample can satisfy at most ONE target: with overlapping or
        nearby targets, a single fixation must not tick off several of them, or
        a stream that parks on one point would spuriously "hit" a cluster. A
        matched sample is consumed so the next target needs a different one.
        """
        if not task.target_positions or not gaze_data:
            return 0.0

        threshold = self.TARGET_HIT_RADIUS
        used = [False] * len(gaze_data)
        hits = 0

        for target_x, target_y in task.target_positions:
            for i, gaze in enumerate(gaze_data):
                if used[i]:
                    continue
                distance = math.sqrt(
                    (gaze.x - target_x)**2 + (gaze.y - target_y)**2
                )
                if distance < threshold:
                    used[i] = True
                    hits += 1
                    break

        return hits / len(task.target_positions)

    def _calculate_reaction_time(
        self,
        task: CognitiveTask,
        gaze_data: List[GazePoint],
        challenge_start_ms: Optional[float],
    ) -> float:
        """
        Latency (ms) from challenge onset to the first on-target gaze.

        ``gaze_data`` must already be time-ordered (validate_task_response sorts
        once for every metric); "first" means first in that order.

        Returns 0.0 when the caller did not provide the onset time, or no sample
        ever landed on a target. Never returns an absolute epoch timestamp.
        """
        if challenge_start_ms is None or not task.target_positions:
            return 0.0
        threshold = self.TARGET_HIT_RADIUS
        for gaze in gaze_data:
            for target_x, target_y in task.target_positions:
                if math.hypot(gaze.x - target_x, gaze.y - target_y) < threshold:
                    return max(0.0, float(gaze.timestamp_ms - challenge_start_ms))
        return 0.0

    def _calculate_path_similarity(
        self,
        task: CognitiveTask,
        gaze_data: List[GazePoint]
    ) -> float:
        """
        Similarity between the expected target order and the observed gaze path.

        Walks the time-ordered gaze samples and counts how many targets were
        visited (within a radius) in the task's expected sequence -- each target
        matched only by a sample occurring after the previous target's match. A
        recorded or synthetic track that ignores the server-randomized order, or
        supplies no ordered movement, scores low. Returns the fraction matched.

        ``gaze_data`` must already be time-ordered (validate_task_response sorts
        once for every metric); the ordering IS the signal here.
        """
        order = task.expected_sequence
        if not order or not task.target_positions or len(gaze_data) < 2:
            return 0.0

        points = gaze_data
        radius = self.TARGET_HIT_RADIUS
        matched = 0
        search_from = 0
        for ti in order:
            if ti >= len(task.target_positions):
                continue
            tx, ty = task.target_positions[ti]
            for j in range(search_from, len(points)):
                if math.hypot(points[j].x - tx, points[j].y - ty) <= radius:
                    matched += 1
                    search_from = j + 1
                    break
        return matched / len(order)
    
    def _calculate_human_likelihood(self, gaze_data: List[GazePoint]) -> float:
        """
        Analyze gaze patterns for human-like characteristics.
        
        Human gaze shows:
        - Natural saccades and fixations
        - Some jitter during fixations
        - Variable velocity
        - Anticipatory movements
        """
        if len(gaze_data) < 5:
            return 0.5
        
        # Check fixation/saccade ratio (humans fixate ~90% of time)
        fixations = sum(1 for g in gaze_data if g.is_fixation)
        fixation_ratio = fixations / len(gaze_data)
        fixation_score = 1.0 if 0.7 <= fixation_ratio <= 0.95 else 0.5
        
        # Check for micro-saccades during fixations
        jitter_score = self._analyze_fixation_jitter(gaze_data)
        
        # Check velocity distribution
        velocity_score = self._analyze_velocity_distribution(gaze_data)
        
        # Confidence distribution (should vary naturally)
        confidence_scores = [g.confidence for g in gaze_data]
        confidence_variance = np.var(confidence_scores)
        natural_variance = 1.0 if 0.01 < confidence_variance < 0.1 else 0.5
        
        return (fixation_score + jitter_score + velocity_score + natural_variance) / 4
    
    def _analyze_fixation_jitter(self, gaze_data: List[GazePoint]) -> float:
        """Analyze micro-movements during fixations (natural for humans)."""
        fixations = [g for g in gaze_data if g.is_fixation]
        if len(fixations) < 3:
            return 0.5
        
        # Calculate position variance during fixations
        x_vals = [g.x for g in fixations]
        y_vals = [g.y for g in fixations]
        
        jitter = (np.std(x_vals) + np.std(y_vals)) / 2
        
        # Natural jitter is small but non-zero
        if 0.005 < jitter < 0.05:
            return 1.0
        elif 0.001 < jitter < 0.1:
            return 0.7
        else:
            return 0.3
    
    def _analyze_velocity_distribution(self, gaze_data: List[GazePoint]) -> float:
        """Analyze gaze velocity distribution."""
        if len(gaze_data) < 3:
            return 0.5
        
        velocities = []
        for i in range(1, len(gaze_data)):
            prev = gaze_data[i-1]
            curr = gaze_data[i]
            time_diff = curr.timestamp_ms - prev.timestamp_ms
            if time_diff > 0:
                dist = math.sqrt((curr.x - prev.x)**2 + (curr.y - prev.y)**2)
                velocities.append(dist / (time_diff / 1000))
        
        if not velocities:
            return 0.5
        
        # Human gaze has bimodal velocity (low for fixations, high for saccades)
        # Perfect uniform velocity is suspicious
        cv = np.std(velocities) / (np.mean(velocities) + 0.001)
        
        if cv > 0.5:  # High variability is natural
            return 1.0
        elif cv > 0.2:
            return 0.7
        else:
            return 0.3
    
    def get_liveness_score(self, task_results: List[TaskResult]) -> float:
        """
        Calculate overall gaze-based liveness score.
        
        Returns:
            Liveness score 0-1
        """
        if not task_results:
            return 0.0
        
        # Weight factors
        accuracy_weight = 0.3
        human_likelihood_weight = 0.5
        path_similarity_weight = 0.2
        
        scores = []
        for result in task_results:
            score = (
                accuracy_weight * result.accuracy_score +
                human_likelihood_weight * result.human_likelihood_score +
                path_similarity_weight * result.gaze_path_similarity
            )
            scores.append(score)

        # float() so the score is JSON-native: np.mean yields np.float64, which
        # json.dumps cannot serialize -- it would break persisting a completed
        # verdict on the Redis session store and the Celery retry payload.
        return float(np.mean(scores))
    
    def clear_history(self):
        """Clear gaze history for new session."""
        self.gaze_history = deque(maxlen=self.GAZE_HISTORY_POINTS)
        self.current_task = None

    def snapshot_state(self) -> Dict:
        """
        JSON-safe per-session state for the cross-process session store.

        Only gaze_history is per-session accumulator state (used by
        _classify_gaze_event for velocity/fixation continuity). The loaded model
        is a process-wide CLASS resource, so it is deliberately NOT snapshotted.
        No truncation here -- gaze_history is already capped at
        GAZE_HISTORY_POINTS on append, so the payload is bounded and the far side
        receives exactly what this side holds.
        """
        return {
            'gaze_history': [
                {
                    'x': g.x, 'y': g.y, 'timestamp_ms': g.timestamp_ms,
                    'confidence': g.confidence, 'is_fixation': g.is_fixation,
                    'pupil_diameter': g.pupil_diameter,
                }
                for g in self.gaze_history
            ],
        }

    def restore_state(self, state: Dict) -> None:
        """
        Rehydrate per-session gaze state produced by snapshot_state.

        Tolerant of malformed/older entries (a rolling deploy can put two code
        versions on the same Redis): a bad point is skipped rather than failing
        the whole restore -- gaze history is a soft, best-effort accumulator, so
        degrading it beats 500-ing the request.
        """
        restored = []
        # Guard the CONTAINER as well as each entry: a non-iterable (or a dict
        # from a differently-shaped writer) would raise from the `for` itself,
        # outside the per-entry guard below, and fail the whole request.
        raw = (state or {}).get('gaze_history')
        if not isinstance(raw, (list, tuple)):
            raw = []
        def _finite(value):
            """float() accepts NaN/Infinity and json round-trips both, so a
            bare conversion would admit numbers that poison the fixation and
            dispersion arithmetic downstream while looking validated."""
            out = float(value)
            if not np.isfinite(out):
                raise ValueError
            return out

        for p in raw:
            try:
                restored.append(GazePoint(
                    x=_finite(p['x']), y=_finite(p['y']),
                    timestamp_ms=_finite(p['timestamp_ms']),
                    confidence=_finite(p['confidence']),
                    # `is True`, not truthiness: is_fixation is COUNTED
                    # (`sum(1 for g in gaze_data if g.is_fixation)`), so the
                    # string 'false' would restore as a fixation.
                    is_fixation=p['is_fixation'] is True,
                    pupil_diameter=p.get('pupil_diameter'),
                ))
            except (KeyError, TypeError, ValueError):
                continue
        self.gaze_history = deque(restored, maxlen=self.GAZE_HISTORY_POINTS)
