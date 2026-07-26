"""
Micro-Expression Analyzer Service
===================================

Detects and analyzes facial micro-expressions using Facial Action Coding System (FACS).
AI-generated deepfakes struggle to replicate natural micro-expression timing and asymmetry.

Features:
- Extract facial Action Units (AUs)
- Detect involuntary micro-expressions
- Analyze temporal consistency and naturalness
- Score expression authenticity
"""

import logging
from collections import deque
from typing import ClassVar, Deque, Dict, List, Optional, Tuple
import numpy as np
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ExpressionType(Enum):
    """Basic emotion categories based on FACS."""
    NEUTRAL = 'neutral'
    SURPRISE = 'surprise'
    HAPPY = 'happy'
    SAD = 'sad'
    ANGRY = 'angry'
    FEAR = 'fear'
    DISGUST = 'disgust'
    CONTEMPT = 'contempt'


@dataclass
class ActionUnit:
    """Facial Action Unit representation."""
    au_number: int
    name: str
    intensity: float  # 0-1
    is_present: bool


@dataclass
class MicroExpression:
    """Detected micro-expression event."""
    expression_type: ExpressionType
    onset_frame: int
    apex_frame: int
    offset_frame: int
    duration_ms: float
    intensity: float
    action_units: List[ActionUnit]
    naturalness_score: float
    asymmetry_score: float


class MicroExpressionAnalyzer:
    """
    Analyzes facial micro-expressions for liveness detection.
    
    Micro-expressions are brief involuntary facial movements (< 500ms)
    that are difficult for deepfakes to generate naturally.
    """
    
    # Facial Action Units relevant for liveness detection
    # Session AU-track window. The scoring window, the append cap and the
    # snapshot cap are all this one number, so the motion score is computed over
    # identical data whichever backend the session lives in.
    AU_HISTORY_FRAMES = 512

    # AU45 intensity above which a frame counts as a blink. Named so tests can
    # seed the sticky flag from the same rule observe() applies, instead of
    # duplicating the literal and silently drifting if it is ever retuned.
    BLINK_AU45_THRESHOLD = 0.5

    TRACKED_AUS: ClassVar[Dict[int, str]] = {
        1: 'Inner Brow Raiser',
        2: 'Outer Brow Raiser',
        4: 'Brow Lowerer',
        5: 'Upper Lid Raiser',
        6: 'Cheek Raiser',
        7: 'Lid Tightener',
        9: 'Nose Wrinkler',
        10: 'Upper Lip Raiser',
        12: 'Lip Corner Puller',
        14: 'Dimpler',
        15: 'Lip Corner Depressor',
        17: 'Chin Raiser',
        20: 'Lip Stretcher',
        23: 'Lip Tightener',
        25: 'Lips Part',
        26: 'Jaw Drop',
        45: 'Blink',
    }
    
    # Expression to AU mappings
    EXPRESSION_AU_MAP: ClassVar[Dict[ExpressionType, List[int]]] = {
        ExpressionType.SURPRISE: [1, 2, 5, 26],
        ExpressionType.HAPPY: [6, 12],
        ExpressionType.SAD: [1, 4, 15, 17],
        ExpressionType.ANGRY: [4, 5, 7, 23],
        ExpressionType.FEAR: [1, 2, 4, 5, 20, 26],
        ExpressionType.DISGUST: [9, 10, 17],
        ExpressionType.CONTEMPT: [14],
    }
    
    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize the micro-expression analyzer.
        
        Args:
            config: Configuration options
        """
        self.config = config or {}
        self.frame_buffer: List[np.ndarray] = []
        self.landmark_history: List[np.ndarray] = []
        # Bounded at the APPEND side, to the same window snapshot_state
        # serializes. Appending without a cap while the snapshot truncated meant
        # the motion score was computed over the whole session in-memory but
        # over only the recent window after a Redis hand-off -- the same session
        # scoring differently per backend. deque(maxlen) is the same pattern
        # PulseOximetryService uses for its rPPG buffers.
        self.au_history: Deque[Dict[int, float]] = deque(maxlen=self.AU_HISTORY_FRAMES)
        self.fps = self.config.get('fps', 30)
        self.min_expression_duration_ms = self.config.get('min_duration_ms', 40)
        self.max_expression_duration_ms = self.config.get('max_duration_ms', 500)
        
        # Per-session temporal accumulators for the expression liveness score
        # (blink dynamics + AU variation over the session). Populated by
        # observe(); serialized by snapshot_state for the cross-process store.
        # (au_history is declared above with the other history buffers.)
        self.au_timestamps: Deque[float] = deque(maxlen=self.AU_HISTORY_FRAMES)
        self._prev_landmarks: Optional[np.ndarray] = None
        # Derived facts kept OUTSIDE the bounded au_history so a Redis hand-off
        # (which re-truncates history to the recent window on every save) cannot
        # erase a blink observed earlier in the session or shorten the frame
        # count -- that would score the same session differently per backend.
        self._blinked: bool = False
        self._au_frames_seen: int = 0

        logger.info("MicroExpressionAnalyzer initialized")

    def has_real_landmark_source(self) -> bool:
        """
        True only when the shared MediaPipe FaceLandmarker is actually loaded.

        Same process-wide resource the gaze estimator uses, so the singleton and
        every per-session instance agree. Without it, extract_landmarks yields
        None and the expression modality stays unavailable and excluded from
        scoring -- never a fabricated signal.
        """
        from ..ml_models.face_landmarker import get_face_landmarker
        return get_face_landmarker() is not None

    def extract_landmarks(self, frame: np.ndarray) -> Optional[np.ndarray]:
        """
        Extract facial landmarks from a video frame via the shared landmarker.

        Args:
            frame: RGB image frame (H, W, 3)

        Returns:
            Array of 478 landmarks (x, y, z), normalized, or None if no real
            landmark source is loaded or no face is detected. The 478-point set
            (468 face + 10 iris) is shared with the gaze estimator so a frame is
            detected once. Never fabricates landmarks.
        """
        from ..ml_models.face_landmarker import detect_face
        detection = detect_face(frame)
        if detection is None:
            return None
        landmarks, _blendshapes = detection
        return landmarks
    
    def extract_action_units(
        self, 
        landmarks: np.ndarray,
        prev_landmarks: Optional[np.ndarray] = None
    ) -> Dict[int, float]:
        """
        Extract Facial Action Unit intensities from landmarks.
        
        Args:
            landmarks: Current frame landmarks
            prev_landmarks: Previous frame landmarks for motion analysis
            
        Returns:
            Dict mapping AU number to intensity (0-1)
        """
        if landmarks is None:
            return {}

        # Two geometry primitives are shared by nearly every AU below: the
        # inter-ocular scale reference (6 helpers) and the eye-aspect ratio (4,
        # with AU6 pulling in the whole AU12 computation as well). Computing
        # them once per frame and threading them through halves the per-frame
        # trig on the hot path; each helper still computes its own when called
        # standalone, so no value changes.
        iod = self._iod(landmarks)
        ear = self._eye_aspect_ratio(landmarks)

        aus = {}

        # AU1: Inner Brow Raiser - vertical distance of inner brow points
        aus[1] = self._calculate_au1_intensity(landmarks, iod=iod)

        # AU2: Outer Brow Raiser
        aus[2] = self._calculate_au2_intensity(landmarks, iod=iod)

        # AU4: Brow Lowerer - brow depression
        aus[4] = self._calculate_au4_intensity(landmarks, iod=iod)

        # AU5: Upper Lid Raiser - eye opening
        aus[5] = self._calculate_au5_intensity(landmarks, ear=ear)

        # AU12: Lip Corner Puller - smile
        aus[12] = self._calculate_au12_intensity(landmarks, iod=iod)

        # AU6: Cheek Raiser - crow's feet wrinkles. Duchenne-gated on AU12, so
        # it reuses the value just computed rather than recomputing it.
        aus[6] = self._calculate_au6_intensity(landmarks, ear=ear, au12=aus[12])

        # AU25: Lips Part - mouth opening
        aus[25] = self._calculate_au25_intensity(landmarks, iod=iod)

        # AU26: Jaw Drop
        aus[26] = self._calculate_au26_intensity(landmarks, iod=iod)

        # AU45: Blink - low eye-aspect-ratio (real geometry, no temporal needed)
        aus[45] = self._calculate_blink_intensity(landmarks, prev_landmarks, ear=ear)

        return aus

    # MediaPipe FaceMesh canonical indices (468/478-point set).
    _IDX: ClassVar[Dict[str, int]] = {
        'eyeA_out': 33, 'eyeA_in': 133, 'eyeA_up': 159, 'eyeA_lo': 145,
        'eyeB_in': 362, 'eyeB_out': 263, 'eyeB_up': 386, 'eyeB_lo': 374,
        'brA_in': 107, 'brB_in': 336, 'brA_out': 70, 'brB_out': 300,
        'mouth_l': 61, 'mouth_r': 291, 'lip_up_in': 13, 'lip_lo_in': 14,
        'lip_up_out': 0, 'lip_lo_out': 17, 'nose_bridge': 6,
    }

    @staticmethod
    def _pt(landmarks: np.ndarray, i: int) -> np.ndarray:
        """Landmark i as a float point, or origin when the index is absent."""
        if i < len(landmarks):
            return np.asarray(landmarks[i], dtype=np.float64)
        return np.zeros(3, dtype=np.float64)

    def _iod(self, landmarks: np.ndarray) -> float:
        """
        Inter-ocular distance: the scale reference that makes AU intensities
        invariant to face size/camera distance. ~0 for degenerate (all-zero)
        landmarks, which makes every AU return 0.0 (no fabricated signal).
        """
        a = self._pt(landmarks, self._IDX['eyeA_out'])
        b = self._pt(landmarks, self._IDX['eyeB_out'])
        return float(np.hypot(a[0] - b[0], a[1] - b[1]))

    def _eye_aspect_ratio(self, landmarks: np.ndarray) -> Optional[float]:
        """Mean vertical/horizontal opening of both eyes (~0.3 open, <0.15 shut)."""
        def ear(out, inn, up, lo):
            po, pi = self._pt(landmarks, out), self._pt(landmarks, inn)
            pu, pl = self._pt(landmarks, up), self._pt(landmarks, lo)
            width = np.hypot(po[0] - pi[0], po[1] - pi[1])
            if width < 1e-6:
                return None
            return abs(pl[1] - pu[1]) / width
        a = ear(self._IDX['eyeA_out'], self._IDX['eyeA_in'],
                self._IDX['eyeA_up'], self._IDX['eyeA_lo'])
        b = ear(self._IDX['eyeB_in'], self._IDX['eyeB_out'],
                self._IDX['eyeB_up'], self._IDX['eyeB_lo'])
        if a is None or b is None:
            return None
        return (a + b) / 2

    def _calculate_au1_intensity(
        self, landmarks: np.ndarray, iod: Optional[float] = None
    ) -> float:
        """AU1 (Inner Brow Raiser): inner brows raised above the nose bridge."""
        iod = self._iod(landmarks) if iod is None else iod
        if iod < 1e-6:
            return 0.0
        brow = (self._pt(landmarks, self._IDX['brA_in'])[1]
                + self._pt(landmarks, self._IDX['brB_in'])[1]) / 2
        ref = self._pt(landmarks, self._IDX['nose_bridge'])[1]
        # Raised brow sits higher (smaller y) than the bridge; scale by iod.
        return float(np.clip((ref - brow) / iod - 0.35, 0.0, 1.0))

    def _brow_eye_gap(self, landmarks: np.ndarray, brow_idx: int, eye_up_idx: int,
                      iod: Optional[float] = None) -> float:
        """Vertical brow-to-upper-lid gap, normalized by inter-ocular distance."""
        iod = self._iod(landmarks) if iod is None else iod
        if iod < 1e-6:
            return 0.0
        brow = self._pt(landmarks, brow_idx)
        eye = self._pt(landmarks, eye_up_idx)
        return abs(eye[1] - brow[1]) / iod

    def _calculate_au2_intensity(
        self, landmarks: np.ndarray, iod: Optional[float] = None
    ) -> float:
        """AU2 (Outer Brow Raiser): outer brows lifted away from the eyes."""
        gap = (self._brow_eye_gap(landmarks, self._IDX['brA_out'], self._IDX['eyeA_up'], iod)
               + self._brow_eye_gap(landmarks, self._IDX['brB_out'], self._IDX['eyeB_up'], iod)) / 2
        if gap <= 0.0:
            return 0.0
        return float(np.clip((gap - 0.45) / 0.4, 0.0, 1.0))

    def _calculate_au4_intensity(
        self, landmarks: np.ndarray, iod: Optional[float] = None
    ) -> float:
        """AU4 (Brow Lowerer): inner brows pulled DOWN toward the eyes."""
        gap = (self._brow_eye_gap(landmarks, self._IDX['brA_in'], self._IDX['eyeA_up'], iod)
               + self._brow_eye_gap(landmarks, self._IDX['brB_in'], self._IDX['eyeB_up'], iod)) / 2
        if gap <= 0.0:
            return 0.0
        # Smaller gap => brow lowered. Below the neutral band => AU4 active.
        return float(np.clip((0.30 - gap) / 0.25, 0.0, 1.0))

    def _calculate_au5_intensity(
        self, landmarks: np.ndarray, ear: Optional[float] = None
    ) -> float:
        """AU5 (Upper Lid Raiser): eyes opened WIDER than neutral (high EAR)."""
        ear = self._eye_aspect_ratio(landmarks) if ear is None else ear
        if ear is None:
            return 0.0
        return float(np.clip((ear - 0.32) / 0.18, 0.0, 1.0))

    def _calculate_au6_intensity(
        self, landmarks: np.ndarray, ear: Optional[float] = None,
        au12: Optional[float] = None
    ) -> float:
        """
        AU6 (Cheek Raiser): lower-lid raise that narrows the eye during a genuine
        (Duchenne) smile -- approximated as eye narrowing that co-occurs with AU12.
        """
        ear = self._eye_aspect_ratio(landmarks) if ear is None else ear
        if ear is None:
            return 0.0
        narrowing = float(np.clip((0.28 - ear) / 0.18, 0.0, 1.0))
        if au12 is None:
            au12 = self._calculate_au12_intensity(landmarks)
        return float(narrowing * au12)

    def _calculate_au12_intensity(
        self, landmarks: np.ndarray, iod: Optional[float] = None
    ) -> float:
        """AU12 (Lip Corner Puller/Smile): mouth widened and corners raised."""
        iod = self._iod(landmarks) if iod is None else iod
        if iod < 1e-6:
            return 0.0
        left = self._pt(landmarks, self._IDX['mouth_l'])
        r = self._pt(landmarks, self._IDX['mouth_r'])
        up = self._pt(landmarks, self._IDX['lip_up_in'])
        lo = self._pt(landmarks, self._IDX['lip_lo_in'])
        width = np.hypot(left[0] - r[0], left[1] - r[1]) / iod
        mouth_center_y = (up[1] + lo[1]) / 2
        corner_y = (left[1] + r[1]) / 2
        # Smile widens the mouth AND lifts the corners above the lip center.
        raise_ratio = (mouth_center_y - corner_y) / iod
        width_score = np.clip((width - 0.95) / 0.4, 0.0, 1.0)
        raise_score = np.clip((raise_ratio + 0.02) / 0.12, 0.0, 1.0)
        return float(np.clip(0.5 * width_score + 0.5 * raise_score, 0.0, 1.0))

    def _calculate_au25_intensity(
        self, landmarks: np.ndarray, iod: Optional[float] = None
    ) -> float:
        """AU25 (Lips Part): inner-lip vertical gap."""
        iod = self._iod(landmarks) if iod is None else iod
        if iod < 1e-6:
            return 0.0
        up = self._pt(landmarks, self._IDX['lip_up_in'])
        lo = self._pt(landmarks, self._IDX['lip_lo_in'])
        gap = abs(lo[1] - up[1]) / iod
        return float(np.clip((gap - 0.02) / 0.15, 0.0, 1.0))

    def _calculate_au26_intensity(
        self, landmarks: np.ndarray, iod: Optional[float] = None
    ) -> float:
        """AU26 (Jaw Drop): large outer-lip vertical opening."""
        iod = self._iod(landmarks) if iod is None else iod
        if iod < 1e-6:
            return 0.0
        up = self._pt(landmarks, self._IDX['lip_up_out'])
        lo = self._pt(landmarks, self._IDX['lip_lo_out'])
        gap = abs(lo[1] - up[1]) / iod
        return float(np.clip((gap - 0.25) / 0.35, 0.0, 1.0))

    def _calculate_blink_intensity(
        self,
        landmarks: np.ndarray,
        prev_landmarks: Optional[np.ndarray] = None,
        ear: Optional[float] = None
    ) -> float:
        """AU45 (Blink): eyes closed => low eye-aspect-ratio."""
        ear = self._eye_aspect_ratio(landmarks) if ear is None else ear
        if ear is None:
            return 0.0
        # EAR ~0.30 open, ~0.10 shut. Higher intensity as the eye closes.
        return float(np.clip((0.22 - ear) / 0.15, 0.0, 1.0))

    def observe(self, landmarks: np.ndarray, timestamp_ms: float) -> Dict[int, float]:
        """
        Extract AUs for a frame AND accumulate them for the session-level
        expression liveness score. Uses the previous frame's landmarks for any
        temporal AU and remembers the current ones. Returns the per-frame AUs.
        """
        aus = self.extract_action_units(landmarks, self._prev_landmarks)
        if aus:
            self.au_history.append(aus)
            self.au_timestamps.append(float(timestamp_ms))
            self._prev_landmarks = np.asarray(landmarks)
            # Sticky derived facts (survive history truncation across a hand-off).
            self._au_frames_seen += 1
            if aus.get(45, 0.0) > self.BLINK_AU45_THRESHOLD:
                self._blinked = True
        return aus

    # Frames needed before the expression modality can score at all.
    MIN_EXPRESSION_FRAMES = 15

    def get_session_expression_score(self) -> Optional[float]:
        """
        Session-level expression LIVENESS score from accumulated AU dynamics.

        Returns None -- so the modality is EXCLUDED, never defaulted to a passing
        value -- when no real landmark source is loaded or too few frames were
        observed. Otherwise scores temporal dynamics that a live face produces
        and a static photo/screen cannot: at least one blink, and natural
        variation in the brow/mouth AUs over the session. This is the real
        liveness signal (a photo yields a flat, blink-free AU track), robust to
        exact per-AU calibration.
        """
        if not self.has_real_landmark_source():
            return None
        # Use the sticky frame count, not len(au_history): the history is bounded
        # and re-truncated on each Redis save, so counting it would under-report
        # after a hand-off.
        if self._au_frames_seen < self.MIN_EXPRESSION_FRAMES:
            return None

        # Blink dynamics: a live subject blinks. Read the sticky flag rather than
        # re-deriving from the (truncated) track, so a blink from early in the
        # session is not lost across a worker hand-off.
        blink_score = 1.0 if self._blinked else 0.0

        # Facial motion: brow/mouth AUs vary over time on a live face; a still
        # image gives a near-constant track (variance ~0).
        motion_aus = (1, 2, 4, 12, 25, 26)
        variances = []
        for au in motion_aus:
            track = [a.get(au, 0.0) for a in self.au_history]
            variances.append(float(np.var(track)))
        mean_var = float(np.mean(variances)) if variances else 0.0
        # ~0.0025 std (0.05 intensity swing) already reads as clearly live.
        motion_score = float(np.clip(mean_var / 0.0025, 0.0, 1.0))

        return float(0.5 * blink_score + 0.5 * motion_score)

    def snapshot_state(self) -> Dict:
        """
        JSON-safe per-session expression state for the cross-process store.

        The AU history and previous-frame landmarks ARE the session accumulator
        behind get_session_expression_score, so they must survive a REST<->WS
        worker hand-off. No truncation here: the accumulators are already capped
        at AU_HISTORY_FRAMES on append, so the payload is bounded AND the far
        side receives exactly what this side scored. The loaded landmarker is a
        process-wide resource and is not snapshotted.
        """
        return {
            'au_history': [
                {str(k): v for k, v in a.items()} for a in self.au_history
            ],
            'au_timestamps': list(self.au_timestamps),
            # Derived from the FULL history, so window truncation cannot rewrite
            # the blink evidence or the frame count on the far side of a hand-off.
            'blinked': self._blinked,
            'au_frames_seen': self._au_frames_seen,
            'prev_landmarks': (
                self._prev_landmarks.tolist()
                if self._prev_landmarks is not None else None
            ),
        }

    def restore_state(self, state: Dict) -> None:
        """Rehydrate expression accumulators produced by snapshot_state."""
        state = state or {}
        self.au_history = deque(
            ({int(k): float(v) for k, v in a.items()}
             for a in state.get('au_history', [])),
            maxlen=self.AU_HISTORY_FRAMES)
        self.au_timestamps = deque(
            state.get('au_timestamps', []), maxlen=self.AU_HISTORY_FRAMES)
        self._blinked = bool(state.get('blinked', False))
        # Fall back to the restored history length for snapshots written before
        # this field existed (rolling deploy).
        self._au_frames_seen = int(state.get('au_frames_seen', len(self.au_history)))
        prev = state.get('prev_landmarks')
        self._prev_landmarks = np.asarray(prev) if prev is not None else None

    def detect_micro_expressions(
        self,
        au_sequence: List[Dict[int, float]],
        timestamps: List[float]
    ) -> List[MicroExpression]:
        """
        Detect micro-expressions from a sequence of AU readings.
        
        Micro-expressions are characterized by:
        - Brief duration (40-500ms)
        - Rapid onset and offset
        - Often involve partial face activation
        
        Args:
            au_sequence: List of AU intensity dicts per frame
            timestamps: Corresponding timestamps in milliseconds
            
        Returns:
            List of detected micro-expressions
        """
        expressions = []
        
        if len(au_sequence) < 3:
            return expressions
        
        # Look for rapid AU changes indicating expression onset
        for au_num in self.TRACKED_AUS:
            intensities = [aus.get(au_num, 0) for aus in au_sequence]
            
            # Find peaks (potential expressions)
            peaks = self._find_intensity_peaks(intensities)
            
            for peak_idx in peaks:
                # Analyze the expression around this peak
                expr = self._analyze_expression_event(
                    au_sequence, timestamps, peak_idx, au_num
                )
                if expr:
                    expressions.append(expr)
        
        return expressions
    
    def _find_intensity_peaks(self, intensities: List[float]) -> List[int]:
        """Find peak indices in intensity sequence."""
        peaks = []
        threshold = 0.3
        
        for i in range(1, len(intensities) - 1):
            if (intensities[i] > threshold and 
                intensities[i] > intensities[i-1] and 
                intensities[i] > intensities[i+1]):
                peaks.append(i)
        
        return peaks
    
    def _analyze_expression_event(
        self,
        au_sequence: List[Dict[int, float]],
        timestamps: List[float],
        peak_idx: int,
        primary_au: int
    ) -> Optional[MicroExpression]:
        """Analyze a potential micro-expression event around a peak."""
        # Find onset and offset
        onset_idx = self._find_onset(au_sequence, peak_idx, primary_au)
        offset_idx = self._find_offset(au_sequence, peak_idx, primary_au)
        
        # Calculate duration
        duration_ms = timestamps[offset_idx] - timestamps[onset_idx]
        
        # Check if within micro-expression duration range
        if not (self.min_expression_duration_ms <= duration_ms <= self.max_expression_duration_ms):
            return None
        
        # Determine expression type
        expr_type = self._classify_expression(au_sequence[peak_idx])
        
        # Calculate naturalness (real expressions have characteristic timing)
        naturalness = self._calculate_naturalness(
            au_sequence[onset_idx:offset_idx+1],
            duration_ms
        )
        
        # Calculate asymmetry (real faces have natural asymmetry)
        asymmetry = self._calculate_asymmetry(au_sequence[peak_idx])
        
        # Get active AUs
        active_aus = [
            ActionUnit(
                au_number=au_num,
                name=self.TRACKED_AUS.get(au_num, f"AU{au_num}"),
                intensity=intensity,
                is_present=intensity > 0.2
            )
            for au_num, intensity in au_sequence[peak_idx].items()
            if intensity > 0.2
        ]
        
        return MicroExpression(
            expression_type=expr_type,
            onset_frame=onset_idx,
            apex_frame=peak_idx,
            offset_frame=offset_idx,
            duration_ms=duration_ms,
            intensity=au_sequence[peak_idx].get(primary_au, 0),
            action_units=active_aus,
            naturalness_score=naturalness,
            asymmetry_score=asymmetry
        )
    
    def _find_onset(
        self, 
        au_sequence: List[Dict[int, float]], 
        peak_idx: int, 
        au_num: int
    ) -> int:
        """Find the onset frame of an expression."""
        threshold = 0.1
        for i in range(peak_idx - 1, -1, -1):
            if au_sequence[i].get(au_num, 0) < threshold:
                return i + 1
        return 0
    
    def _find_offset(
        self, 
        au_sequence: List[Dict[int, float]], 
        peak_idx: int, 
        au_num: int
    ) -> int:
        """Find the offset frame of an expression."""
        threshold = 0.1
        for i in range(peak_idx + 1, len(au_sequence)):
            if au_sequence[i].get(au_num, 0) < threshold:
                return i - 1
        return len(au_sequence) - 1
    
    def _classify_expression(self, aus: Dict[int, float]) -> ExpressionType:
        """Classify expression type from AU pattern."""
        best_match = ExpressionType.NEUTRAL
        best_score = 0
        
        for expr_type, expr_aus in self.EXPRESSION_AU_MAP.items():
            score = sum(aus.get(au, 0) for au in expr_aus) / len(expr_aus)
            if score > best_score:
                best_score = score
                best_match = expr_type
        
        return best_match if best_score > 0.2 else ExpressionType.NEUTRAL
    
    def _calculate_naturalness(
        self, 
        au_segment: List[Dict[int, float]],
        duration_ms: float
    ) -> float:
        """
        Calculate naturalness score based on expression dynamics.
        
        Natural expressions have:
        - Smooth onset (not instantaneous)
        - Typical duration patterns
        - Gradual offset
        """
        # Check onset smoothness
        onset_score = 0.8  # Placeholder - would analyze gradient
        
        # Check duration appropriateness
        if 100 <= duration_ms <= 400:
            duration_score = 1.0
        elif 40 <= duration_ms <= 500:
            duration_score = 0.7
        else:
            duration_score = 0.3
        
        # Check temporal symmetry
        symmetry_score = 0.8  # Placeholder
        
        return (onset_score + duration_score + symmetry_score) / 3
    
    def _calculate_asymmetry(self, aus: Dict[int, float]) -> float:
        """
        Calculate facial asymmetry score.
        
        Real faces have natural asymmetry; perfectly symmetric 
        expressions may indicate synthetic generation.
        """
        # No real left/right AU comparison is implemented yet, so return 0.0
        # rather than a fabricated random value -- matching the AU-intensity
        # stubs. The previous np.random.uniform(0.1, 0.4) always landed inside
        # get_liveness_score's "natural" band, fabricating a perfect asymmetry
        # score on every call; 0.0 yields a neutral score instead. This modality
        # does not gate the verdict yet (session['expression_score'] is unset), so
        # it is dormant either way. Returns 0.0 (perfect symmetry) to 1.0 (high).
        return 0.0
    
    def analyze_temporal_consistency(
        self,
        expressions: List[MicroExpression],
        session_duration_ms: float
    ) -> Dict:
        """
        Analyze temporal consistency of expressions across session.
        
        Deepfakes often show:
        - Unnatural expression frequency
        - Missing expected micro-expressions
        - Temporal discontinuities
        
        Returns:
            Analysis results with consistency scores
        """
        if not expressions:
            return {
                'expression_count': 0,
                'expression_rate_per_minute': 0,
                'naturalness_average': 0,
                'temporal_consistency_score': 0.5,  # Unknown
                'is_suspicious': True,
                'reason': 'No expressions detected'
            }
        
        # Calculate expression rate
        duration_minutes = session_duration_ms / 60000
        rate = len(expressions) / max(duration_minutes, 0.1)
        
        # Natural rate is roughly 2-10 micro-expressions per minute
        rate_score = 1.0 if 2 <= rate <= 10 else 0.5
        
        # Average naturalness
        avg_naturalness = np.mean([e.naturalness_score for e in expressions])
        
        # Temporal spacing analysis
        spacing_score = self._analyze_expression_spacing(expressions)
        
        consistency_score = (rate_score + avg_naturalness + spacing_score) / 3
        
        return {
            'expression_count': len(expressions),
            'expression_rate_per_minute': rate,
            'naturalness_average': avg_naturalness,
            'temporal_consistency_score': consistency_score,
            'is_suspicious': consistency_score < 0.5,
            'reason': None if consistency_score >= 0.5 else 'Abnormal expression patterns'
        }
    
    def _analyze_expression_spacing(
        self, 
        expressions: List[MicroExpression]
    ) -> float:
        """Analyze spacing between expressions for naturalness."""
        if len(expressions) < 2:
            return 0.5
        
        # Calculate inter-expression intervals
        intervals = []
        for i in range(1, len(expressions)):
            interval = expressions[i].onset_frame - expressions[i-1].offset_frame
            intervals.append(interval)
        
        # Natural expressions are not perfectly regular
        if intervals:
            cv = np.std(intervals) / (np.mean(intervals) + 0.001)  # Coefficient of variation
            # Some variability (0.3-0.7) is natural
            if 0.3 <= cv <= 0.7:
                return 1.0
            elif 0.1 <= cv <= 0.9:
                return 0.7
            else:
                return 0.3
        
        return 0.5
    
    def get_liveness_score(
        self,
        expressions: List[MicroExpression],
        temporal_analysis: Dict
    ) -> float:
        """
        Calculate overall liveness score from micro-expression analysis.
        
        Returns:
            Liveness score 0-1 (higher = more likely live)
        """
        if not expressions:
            return 0.3  # Low score but not zero (might be stoic person)
        
        # Components
        naturalness_score = temporal_analysis.get('naturalness_average', 0)
        consistency_score = temporal_analysis.get('temporal_consistency_score', 0)
        
        # Average asymmetry (should be moderate, not zero or too high)
        asymmetries = [e.asymmetry_score for e in expressions]
        avg_asymmetry = np.mean(asymmetries)
        asymmetry_score = 1.0 if 0.1 <= avg_asymmetry <= 0.4 else 0.5
        
        # Weighted combination
        liveness_score = (
            0.4 * naturalness_score +
            0.3 * consistency_score +
            0.3 * asymmetry_score
        )
        
        return min(1.0, max(0.0, liveness_score))
