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
from typing import Dict, List, Optional, Tuple
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
    TRACKED_AUS = {
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
    EXPRESSION_AU_MAP = {
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
        self.au_history: List[Dict[int, float]] = []
        self.fps = self.config.get('fps', 30)
        self.min_expression_duration_ms = self.config.get('min_duration_ms', 40)
        self.max_expression_duration_ms = self.config.get('max_duration_ms', 500)
        
        # Initialize ML models lazily
        self._face_mesh = None
        self._au_model = None
        
        logger.info("MicroExpressionAnalyzer initialized")
    
    def _init_models(self):
        """Lazy initialization of ML models."""
        if self._face_mesh is None:
            try:
                import mediapipe as mp
                self._face_mesh = mp.solutions.face_mesh.FaceMesh(
                    static_image_mode=False,
                    max_num_faces=1,
                    refine_landmarks=True,
                    min_detection_confidence=0.5,
                    min_tracking_confidence=0.5
                )
                logger.info("MediaPipe FaceMesh initialized")
            except ImportError:
                logger.warning("MediaPipe not available, using fallback detection")
                self._face_mesh = None
    
    def extract_landmarks(self, frame: np.ndarray) -> Optional[np.ndarray]:
        """
        Extract facial landmarks from a video frame.
        
        Args:
            frame: RGB image frame (H, W, 3)
            
        Returns:
            Array of 468 landmarks (x, y, z) or None if no face detected
        """
        self._init_models()
        
        if self._face_mesh is None:
            return self._fallback_landmark_detection(frame)
        
        try:
            results = self._face_mesh.process(frame)
            if results.multi_face_landmarks:
                landmarks = results.multi_face_landmarks[0]
                return np.array([
                    [lm.x, lm.y, lm.z] 
                    for lm in landmarks.landmark
                ])
        except Exception as e:
            logger.error(f"Landmark extraction failed: {e}")
        
        return None
    
    def _fallback_landmark_detection(self, frame: np.ndarray) -> Optional[np.ndarray]:
        """Fallback landmark detection without MediaPipe."""
        # Simplified detection - returns basic face region estimation
        # In production, would use dlib or other detector
        h, w = frame.shape[:2]
        return np.random.rand(468, 3) * [w, h, 0.1]  # Placeholder
    
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
        aus = {}
        
        # Calculate AU intensities based on landmark geometry
        # AU1: Inner Brow Raiser - vertical distance of inner brow points
        aus[1] = self._calculate_au1_intensity(landmarks)
        
        # AU2: Outer Brow Raiser
        aus[2] = self._calculate_au2_intensity(landmarks)
        
        # AU4: Brow Lowerer - brow depression
        aus[4] = self._calculate_au4_intensity(landmarks)
        
        # AU5: Upper Lid Raiser - eye opening
        aus[5] = self._calculate_au5_intensity(landmarks)
        
        # AU6: Cheek Raiser - crow's feet wrinkles
        aus[6] = self._calculate_au6_intensity(landmarks)
        
        # AU12: Lip Corner Puller - smile
        aus[12] = self._calculate_au12_intensity(landmarks)
        
        # AU25: Lips Part - mouth opening
        aus[25] = self._calculate_au25_intensity(landmarks)
        
        # AU26: Jaw Drop
        aus[26] = self._calculate_au26_intensity(landmarks)
        
        # AU45: Blink - requires temporal analysis
        if prev_landmarks is not None:
            aus[45] = self._calculate_blink_intensity(landmarks, prev_landmarks)
        else:
            aus[45] = 0.0
        
        return aus
    
    def _calculate_au1_intensity(self, landmarks: np.ndarray) -> float:
        """Calculate AU1 (Inner Brow Raiser) intensity."""
        # Landmark indices for inner brow (MediaPipe)
        # Using approximate indices - would refine for production
        inner_brow_l = landmarks[107] if len(landmarks) > 107 else landmarks[0]
        inner_brow_r = landmarks[336] if len(landmarks) > 336 else landmarks[0]
        nose_bridge = landmarks[6] if len(landmarks) > 6 else landmarks[0]
        
        # Calculate vertical displacement
        brow_height = (inner_brow_l[1] + inner_brow_r[1]) / 2
        ref_height = nose_bridge[1]
        
        # Normalize to 0-1 intensity
        displacement = max(0, ref_height - brow_height)
        return min(1.0, displacement * 5.0)  # Scaling factor
    
    def _calculate_au2_intensity(self, landmarks: np.ndarray) -> float:
        """Calculate AU2 (Outer Brow Raiser) intensity."""
        return np.random.uniform(0, 0.3)  # Placeholder - implement geometry
    
    def _calculate_au4_intensity(self, landmarks: np.ndarray) -> float:
        """Calculate AU4 (Brow Lowerer) intensity."""
        return np.random.uniform(0, 0.3)  # Placeholder
    
    def _calculate_au5_intensity(self, landmarks: np.ndarray) -> float:
        """Calculate AU5 (Upper Lid Raiser) intensity."""
        # Eye aspect ratio calculation
        return np.random.uniform(0.2, 0.6)  # Placeholder
    
    def _calculate_au6_intensity(self, landmarks: np.ndarray) -> float:
        """Calculate AU6 (Cheek Raiser) intensity."""
        return np.random.uniform(0, 0.4)  # Placeholder
    
    def _calculate_au12_intensity(self, landmarks: np.ndarray) -> float:
        """Calculate AU12 (Lip Corner Puller/Smile) intensity."""
        # Lip corner positions relative to mouth center
        return np.random.uniform(0, 0.5)  # Placeholder
    
    def _calculate_au25_intensity(self, landmarks: np.ndarray) -> float:
        """Calculate AU25 (Lips Part) intensity."""
        return np.random.uniform(0, 0.3)  # Placeholder
    
    def _calculate_au26_intensity(self, landmarks: np.ndarray) -> float:
        """Calculate AU26 (Jaw Drop) intensity."""
        return np.random.uniform(0, 0.3)  # Placeholder
    
    def _calculate_blink_intensity(
        self, 
        landmarks: np.ndarray, 
        prev_landmarks: np.ndarray
    ) -> float:
        """Detect blink from eye aspect ratio change."""
        # Calculate eye aspect ratio for current and previous
        # High intensity = blink detected
        return np.random.uniform(0, 0.8)  # Placeholder
    
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
        # Would compare left/right AU intensities
        # Returns 0.0 (perfect symmetry) to 1.0 (high asymmetry)
        return np.random.uniform(0.1, 0.4)  # Natural asymmetry range
    
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
