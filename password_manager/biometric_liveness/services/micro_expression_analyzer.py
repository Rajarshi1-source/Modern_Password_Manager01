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

    # AU45 intensity above which a frame counts as eyes-SHUT. Named so tests can
    # seed the sticky flag from the same rule observe() applies, instead of
    # duplicating the literal and silently drifting if it is ever retuned.
    BLINK_AU45_THRESHOLD = 0.5
    # ...and below which they count as clearly OPEN. A blink is only recorded on
    # an open->shut TRANSITION, so a still image of a face with closed eyes
    # cannot earn the blink half of the expression score: it never presents an
    # open frame, so there is no transition to observe. Scoring shut-ness alone
    # would hand a static photo 0.5 while the docstring below claims a photo
    # yields a "flat, blink-free AU track" -- exactly the kind of unearned
    # signal this feature is not allowed to fabricate. The gap between the two
    # thresholds is hysteresis, so per-frame landmark noise cannot manufacture a
    # transition on a genuinely static face.
    BLINK_OPEN_AU45_MAX = 0.2
    # How long after an open observation a shut one can still close a blink.
    # The open evidence MUST expire: left sticky for the session, an open frame
    # and an unrelated shut frame arriving much later -- after tracking loss,
    # from a different face, or from a second still image -- combined into a
    # "blink" that neither observation earned, which is a two-image replay for
    # half the expression score. Bounded by the physiology instead (a human
    # blink runs 100-400ms), so the two observations have to be close enough in
    # SERVER time to be one continuous eyelid movement.
    #
    # HONEST LIMIT, do not overstate it: this stops UNRELATED observations from
    # combining. It cannot authenticate that both frames show the same face, and
    # no rule over per-frame eye geometry can distinguish a live blink from a
    # crafted frame sequence delivered at video rate -- replay resistance is the
    # deepfake modality's job and the gaze challenge-response's, not this one's.
    BLINK_MAX_TRANSITION_MS = 400.0
    # Frame-to-frame face-continuity bounds, checked between the previous
    # observed frame and this one. Without them the transition window still
    # accepted an open frame from one face and a shut frame from ANOTHER, so long
    # as they arrived within 400ms with no dropout in between -- a cross-face or
    # two-image sequence read as one eyelid movement. Coarse on purpose: a real
    # head neither changes apparent size by a quarter nor slides half an
    # inter-ocular distance in one frame, while a cut between two faces
    # routinely does both. Erring loose matters more than erring tight -- a
    # fast-moving real user just loses that blink and blinks again.
    #
    # HONEST LIMIT -- it is SCALE AND POSITION ONLY, not identity. Anything
    # presented at the same size in the same place reads as one track: two
    # stills of the same person (open-eyed, closed-eyed), and equally two
    # DIFFERENT subjects whose faces happen to be aligned. Separating those is
    # face RE-IDENTIFICATION, which needs an identity model -- the deepfake
    # modality's job; a landmark-similarity tolerance guessed by eye would be
    # fabricated validation, the same reason the AU2/AU4 brow bands were left
    # uncalibrated rather than retuned. Pinned by
    # test_aligned_different_faces_still_form_a_blink and listed on the
    # model-provisioning checklist, because it only becomes reachable once a
    # FACE_LANDMARKER_MODEL makes this modality gate at all.
    FACE_CONTINUITY_MAX_SCALE_RATIO = 1.25
    FACE_CONTINUITY_MAX_SHIFT_IOD = 0.5

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
        # The previous frame's geometry, reduced to the only two things
        # _face_track_broken reads. Kept as scalars rather than the landmark
        # array because these DO cross a worker hand-off (see snapshot_state)
        # and 478x3 floats per save would not be worth it.
        self._prev_iod: Optional[float] = None
        self._prev_centre = None
        # Derived facts kept OUTSIDE the bounded au_history so a Redis hand-off
        # (which re-truncates history to the recent window on every save) cannot
        # erase a blink observed earlier in the session or shorten the frame
        # count -- that would score the same session differently per backend.
        self._blinked: bool = False
        # Server timestamp of the most recent OPEN-eye frame, or None when there
        # is no open observation a shut frame could still close a blink with --
        # the other half of the transition _blinked requires. A timestamp rather
        # than a flag so the evidence EXPIRES (see BLINK_MAX_TRANSITION_MS).
        self._last_open_ms: Optional[float] = None
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
            prev_landmarks: RESERVED hook for a future temporal AU. Accepted and
                ignored today: every AU below is computed from the current frame
                alone (AU45 included -- it is purely EAR-based). Kept in the
                signature because observe() threads the previous frame's
                landmarks through, so adding a temporal AU needs no plumbing.

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

        # AU45: Blink - low eye-aspect-ratio (real geometry, no temporal needed).
        # OMITTED when the eye geometry was not measurable (degenerate socket ->
        # ear is None). Reporting 0.0 there would read as "eyes clearly OPEN" and
        # manufacture the open-eye evidence a blink is closed against, out of a
        # frame where openness was never measured -- the same unearned signal
        # note_tracking_loss exists to discard. Absent means UNKNOWN; observe()
        # treats it as a tracking gap.
        if ear is not None:
            aus[45] = self._calculate_blink_intensity(landmarks, ear=ear)

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
        b = ear(self._IDX['eyeB_out'], self._IDX['eyeB_in'],
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

    # UNVALIDATED against real MediaPipe geometry -- the brow-gap bands below
    # (AU2 neutral 0.45 IOD, AU4 neutral 0.30 IOD) were chosen from anatomy, not
    # measured. The synthetic test fixture sits at a 0.10 IOD gap, which would
    # put AU4 at 0.8 and AU2 at 0.0 on a NEUTRAL face; if real landmarks land in
    # that range, AU4 saturates and AU2 pins every frame, so both contribute ~no
    # variance and get_session_expression_score's motion term quietly narrows to
    # AU1/12/25/26. That is latent, not live: expression is capability-gated on
    # has_real_landmark_source(), so it scores nothing until a FACE_LANDMARKER
    # model is provisioned. Whoever provisions one MUST re-measure these bands
    # against recorded faces before trusting the motion score -- and must not
    # simply retune them by eye, which would swap one unvalidated constant for
    # another while looking authoritative.
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
        if not aus:
            # Landmarks that yield no AUs tell us nothing about the eyes, which
            # is a tracking gap by another name -- same treatment.
            self.note_tracking_loss()
        if aus:
            # Must be read BEFORE _prev_landmarks is overwritten below.
            track_broken = self._face_track_broken(landmarks)
            self.au_history.append(aus)
            self.au_timestamps.append(float(timestamp_ms))
            self._prev_landmarks = np.asarray(landmarks)
            self._prev_iod = self._iod(landmarks)
            self._prev_centre = self._face_centre(landmarks)
            # Sticky derived facts (survive history truncation across a hand-off).
            self._au_frames_seen += 1
            if track_broken:
                # Visibly a different face than the previous frame, so whatever
                # open eye is pending belongs to someone else and must not pair
                # with this frame's shut eye. An OPEN reading below still records
                # fresh evidence -- this frame is fine, its predecessor is what
                # cannot be built on.
                self.note_tracking_loss()
            au45 = aus.get(45)
            now_ms = float(timestamp_ms)
            if au45 is None:
                # Eye openness was not measurable this frame (see
                # extract_action_units): unknown, NOT open.
                self.note_tracking_loss()
            elif au45 < self.BLINK_OPEN_AU45_MAX:
                self._last_open_ms = now_ms
            elif au45 > self.BLINK_AU45_THRESHOLD:
                # Shut. It closes a blink only if the eyes were seen OPEN within
                # the last BLINK_MAX_TRANSITION_MS of server time, i.e. the two
                # observations are close enough to be one eyelid movement rather
                # than two unrelated frames.
                if (self._last_open_ms is not None
                        and 0 <= now_ms - self._last_open_ms
                        <= self.BLINK_MAX_TRANSITION_MS):
                    self._blinked = True
                # Consumed either way: the next blink needs a fresh open frame,
                # so a long shut run cannot keep retrying against one open one.
                self._last_open_ms = None
        return aus

    def _face_centre(self, landmarks: np.ndarray):
        """Midpoint of the two outer eye corners -- the same pair _iod spans."""
        a = self._pt(landmarks, self._IDX['eyeA_out'])
        b = self._pt(landmarks, self._IDX['eyeB_out'])
        return (a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0

    def _face_track_broken(self, landmarks: np.ndarray) -> bool:
        """
        True when this frame's face cannot be a continuation of the last one's.

        Compares scale (inter-ocular distance) and position, both normalised by
        IOD so the test is invariant to face size and camera distance. See
        FACE_CONTINUITY_MAX_SCALE_RATIO for the bounds and for what this does
        NOT establish (identity).

        Degenerate geometry returns False rather than True: with no measurable
        IOD there is no evidence of a BREAK either, and that frame is already
        handled upstream -- an unmeasurable eye socket omits AU45, which observe()
        treats as a tracking gap. Returning True here would double-count it and
        make a genuinely unmeasurable frame indistinguishable from a face swap.

        Reads the two SNAPSHOTTED scalars, never _prev_landmarks: under Redis the
        analyzer is rebuilt from the blob on every locked call, so anything not
        carried in snapshot_state is None on arrival and this check would answer
        "no break" for every frame -- silently disabling itself on exactly the
        backend that makes cross-worker hand-offs possible.
        """
        iod_prev, centre_prev = self._prev_iod, self._prev_centre
        if iod_prev is None or centre_prev is None:
            return False
        iod_now = self._iod(landmarks)
        if iod_now < 1e-6 or iod_prev < 1e-6:
            return False
        if (max(iod_now / iod_prev, iod_prev / iod_now)
                > self.FACE_CONTINUITY_MAX_SCALE_RATIO):
            return True
        (cx, cy), (px, py) = self._face_centre(landmarks), centre_prev
        shift = float(np.hypot(cx - px, cy - py))
        return shift / iod_prev > self.FACE_CONTINUITY_MAX_SHIFT_IOD

    def note_tracking_loss(self) -> None:
        """
        Discard pending open-eye evidence because a frame showed no face.

        MUST be called for every frame the detector could not read, or the
        BLINK_MAX_TRANSITION_MS window alone is not enough: an open frame, a
        frame where tracking is lost, and a shut frame from a replayed image or
        a different subject can all land inside 400ms, and the shut one would
        close a "blink" that was never one continuous eyelid movement. Real
        eyelid closure does not lose the face, so a detection GAP between the
        open and shut observations is evidence AGAINST a blink, not neutral.

        Still does not prove the two frames show the SAME face -- nothing here
        compares identity (see BLINK_MAX_TRANSITION_MS).
        """
        self._last_open_ms = None

    # Frames needed before the expression modality can score at all.
    MIN_EXPRESSION_FRAMES = 15

    def get_session_expression_score(self) -> Optional[float]:
        """
        Session-level expression LIVENESS score from accumulated AU dynamics.

        Returns None -- so the modality is EXCLUDED, never defaulted to a passing
        value -- when no real landmark source is loaded or too few frames were
        observed. Otherwise scores temporal dynamics that a live face produces
        and a static photo/screen cannot: at least one open->shut blink
        TRANSITION within a blink's worth of server time, and natural variation
        in the brow/mouth AUs over the session. This is the real liveness signal
        (a photo yields a flat AU track with no transition -- including a photo
        of closed eyes, which shut-ness alone would have scored, and a pair of
        open/closed stills, which an unbounded transition would have scored),
        robust to exact per-AU calibration.

        NOT replay resistance: a recording of a real face blinking satisfies
        every term here, and nothing in this modality checks that consecutive
        frames show the same person. Defeating replay is the deepfake model's
        job and the gaze challenge-response's. Do not let this score be
        described as anti-spoof on its own.
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
            # Half of an in-flight transition: without it, a hand-off between
            # the open frame and the shut one would lose the blink. Carried as
            # the timestamp so the far side applies the same expiry window.
            'last_open_ms': self._last_open_ms,
            'au_frames_seen': self._au_frames_seen,
            # The face-continuity summary MUST cross the hand-off. Under Redis
            # the analyzer is rebuilt from this blob on every locked call, so
            # anything omitted here is None on arrival -- and _face_track_broken
            # answering "no break" for every frame would silently disable the
            # cross-face guard on the one backend where consecutive frames can
            # be handled by different workers.
            'prev_iod': self._prev_iod,
            'prev_centre': list(self._prev_centre) if self._prev_centre else None,
            # The full _prev_landmarks ARRAY is still not snapshotted: it is only
            # a hook for a future temporal AU (extract_action_units accepts it,
            # no calculator reads it), and ~1.4k floats (478x3) on EVERY
            # per-frame save is not worth carrying for that. The two scalars
            # above are what the continuity check actually reads; whoever adds a
            # temporal AU must add the array back here.
        }

    def restore_state(self, state: Dict) -> None:
        """Rehydrate expression accumulators produced by snapshot_state."""
        state = state or {}
        # Tolerant of malformed/older entries, matching
        # GazeTrackingService.restore_state: a rolling deploy can put two code
        # versions on the same Redis, and the AU track is a soft accumulator, so
        # skipping a bad frame beats 500-ing the request from deep inside
        # deserialize_session. The container is checked too -- a non-list would
        # otherwise raise from the comprehension itself, outside any guard.
        raw_history = state.get('au_history')
        if not isinstance(raw_history, (list, tuple)):
            raw_history = []
        restored = []
        for a in raw_history:
            try:
                values = {}
                for k, v in a.items():
                    value = float(v)
                    # float() happily accepts NaN and Infinity, and JSON
                    # round-trips both. Either poisons the motion score's
                    # np.var: NaN makes the whole session score NaN, and a huge
                    # value saturates the variance to a FULL motion pass. Every
                    # AU this class emits is np.clip'd to [0, 1], so bounding to
                    # that domain rejects nothing a real snapshot can contain.
                    if not np.isfinite(value) or not 0.0 <= value <= 1.0:
                        raise ValueError
                    values[int(k)] = value
                restored.append(values)
            except (AttributeError, TypeError, ValueError):
                continue
        self.au_history = deque(restored, maxlen=self.AU_HISTORY_FRAMES)
        raw_ts = state.get('au_timestamps')
        if not isinstance(raw_ts, (list, tuple)):
            raw_ts = []
        self.au_timestamps = deque(raw_ts, maxlen=self.AU_HISTORY_FRAMES)
        # `is True`, NOT bool(): every non-empty string is truthy, so a blob
        # carrying the STRING 'false' would restore _blinked as True and hand
        # out the blink half of the score for free. Of all the fields here this
        # is the one that must never fail open.
        self._blinked = state.get('blinked') is True
        # A blob written by a worker older than this field simply starts with no
        # open evidence: an in-flight transition is dropped across that one
        # deploy and the subject blinks again. Fail-closed is the right side to
        # err on for a liveness signal.
        try:
            raw_open = state.get('last_open_ms')
            self._last_open_ms = None if raw_open is None else float(raw_open)
            if self._last_open_ms is not None and not np.isfinite(self._last_open_ms):
                self._last_open_ms = None
        except (TypeError, ValueError):
            self._last_open_ms = None
        # Fall back to the restored history length for snapshots written before
        # this field existed (rolling deploy) -- or whose value is unusable, so
        # this coercion cannot be the one thing that still raises out of an
        # otherwise tolerant restore.
        try:
            self._au_frames_seen = int(
                state.get('au_frames_seen', len(self.au_history)))
        except (TypeError, ValueError):
            self._au_frames_seen = len(self.au_history)
        # Continuity summary. Anything unusable restores as None, which makes the
        # next frame's check abstain rather than pass -- the same fail-closed
        # side as an older blob that predates these fields.
        # NaN is the dangerous one here, not junk: every comparison against it is
        # False, so a NaN prev_iod walks straight past _face_track_broken's
        # `< 1e-6` guard and then answers "no break" for ANY face -- silently
        # disabling the cross-face check exactly as the missing snapshot did.
        try:
            raw_iod = state.get('prev_iod')
            self._prev_iod = None if raw_iod is None else float(raw_iod)
            if self._prev_iod is not None and not np.isfinite(self._prev_iod):
                self._prev_iod = None
        except (TypeError, ValueError):
            self._prev_iod = None
        raw_centre = state.get('prev_centre')
        self._prev_centre = None
        if isinstance(raw_centre, (list, tuple)) and len(raw_centre) == 2:
            try:
                centre = (float(raw_centre[0]), float(raw_centre[1]))
                if all(np.isfinite(c) for c in centre):
                    self._prev_centre = centre
            except (TypeError, ValueError):
                self._prev_centre = None
        # 'prev_landmarks' may still be present in a blob written by an older
        # worker mid-deploy; ignored, since no AU reads it (see snapshot_state).

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
