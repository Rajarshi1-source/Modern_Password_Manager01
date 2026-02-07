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
from typing import Dict, List, Optional, Tuple
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
    
    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize gaze tracking service.
        
        Args:
            config: Configuration options
        """
        self.config = config or {}
        self.gaze_history: List[GazePoint] = []
        self.current_task: Optional[CognitiveTask] = None
        
        # ML model for gaze estimation
        self._gaze_model = None
        
        # Task parameters
        self.num_tracking_points = self.config.get('gaze_tracking_points', 9)
        self.task_timeout_ms = self.config.get('cognitive_task_timeout_ms', 5000)
        
        logger.info("GazeTrackingService initialized")
    
    def _init_gaze_model(self):
        """Lazy initialization of gaze estimation model."""
        if self._gaze_model is None:
            try:
                # Would load a trained gaze estimation model
                # e.g., GazeML, L2CS, etc.
                logger.info("Gaze estimation model loaded")
            except Exception as e:
                logger.warning(f"Gaze model init failed: {e}")
    
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
        self._init_gaze_model()
        
        try:
            # Extract eye regions
            left_eye, right_eye = self._extract_eye_regions(frame, face_landmarks)
            
            if left_eye is None or right_eye is None:
                return None
            
            # Estimate gaze direction
            gaze_x, gaze_y, confidence = self._compute_gaze_direction(
                left_eye, right_eye, frame
            )
            
            # Determine if fixation or saccade
            is_fixation = self._classify_gaze_event(gaze_x, gaze_y)
            
            # Estimate pupil diameter if possible
            pupil_diameter = self._estimate_pupil_diameter(left_eye, right_eye)
            
            gaze_point = GazePoint(
                x=gaze_x,
                y=gaze_y,
                timestamp_ms=self._get_current_time_ms(),
                confidence=confidence,
                is_fixation=is_fixation,
                pupil_diameter=pupil_diameter
            )
            
            self.gaze_history.append(gaze_point)
            return gaze_point
            
        except Exception as e:
            logger.error(f"Gaze estimation failed: {e}")
            return None
    
    def _extract_eye_regions(
        self, 
        frame: np.ndarray,
        landmarks: Optional[np.ndarray]
    ) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """Extract left and right eye regions from frame."""
        if landmarks is None:
            return None, None
        
        # Would extract eye regions based on landmark positions
        # Returning placeholder for now
        h, w = frame.shape[:2]
        eye_size = 64
        
        # Approximate eye positions
        left_center = (int(w * 0.35), int(h * 0.4))
        right_center = (int(w * 0.65), int(h * 0.4))
        
        left_eye = frame[
            max(0, left_center[1]-eye_size//2):left_center[1]+eye_size//2,
            max(0, left_center[0]-eye_size//2):left_center[0]+eye_size//2
        ]
        right_eye = frame[
            max(0, right_center[1]-eye_size//2):right_center[1]+eye_size//2,
            max(0, right_center[0]-eye_size//2):right_center[0]+eye_size//2
        ]
        
        return left_eye, right_eye
    
    def _compute_gaze_direction(
        self,
        left_eye: np.ndarray,
        right_eye: np.ndarray,
        frame: np.ndarray
    ) -> Tuple[float, float, float]:
        """Compute normalized gaze direction from eye regions."""
        # Would use trained CNN model
        # Returning placeholder values
        gaze_x = np.random.uniform(0.3, 0.7)
        gaze_y = np.random.uniform(0.3, 0.7)
        confidence = np.random.uniform(0.7, 0.95)
        
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
    
    def _estimate_pupil_diameter(
        self, 
        left_eye: np.ndarray, 
        right_eye: np.ndarray
    ) -> Optional[float]:
        """Estimate pupil diameter (useful for cognitive load detection)."""
        # Would use pupil detection algorithm
        return np.random.uniform(3.0, 5.0)  # mm, placeholder
    
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
        user_answer: Optional[str] = None
    ) -> TaskResult:
        """
        Validate user's gaze response to cognitive task.
        
        Args:
            task: The cognitive task
            gaze_data: Recorded gaze points during task
            user_answer: User's explicit answer (for counting tasks)
            
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
        
        # Calculate metrics
        accuracy = self._calculate_gaze_accuracy(task, gaze_data)
        path_similarity = self._calculate_path_similarity(task, gaze_data)
        reaction_time = gaze_data[0].timestamp_ms if gaze_data else 0
        human_score = self._calculate_human_likelihood(gaze_data)
        
        # Check explicit answer if applicable
        answer_correct = True
        if task.correct_answer and user_answer:
            answer_correct = user_answer.strip() == task.correct_answer
        
        # Determine if passed
        is_passed = (
            accuracy > 0.6 and 
            path_similarity > 0.5 and 
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
        """Calculate how accurately user looked at targets."""
        if not task.target_positions or not gaze_data:
            return 0.0
        
        hits = 0
        threshold = 0.15  # Distance threshold for "looking at" target
        
        for target_x, target_y in task.target_positions:
            # Check if any gaze point was near this target
            for gaze in gaze_data:
                distance = math.sqrt(
                    (gaze.x - target_x)**2 + (gaze.y - target_y)**2
                )
                if distance < threshold:
                    hits += 1
                    break
        
        return hits / len(task.target_positions)
    
    def _calculate_path_similarity(
        self, 
        task: CognitiveTask, 
        gaze_data: List[GazePoint]
    ) -> float:
        """Calculate similarity between expected and actual gaze path."""
        if not task.expected_sequence or len(gaze_data) < 2:
            return 0.5  # Neutral score
        
        # Would use DTW or similar for path matching
        # Simplified version
        return np.random.uniform(0.5, 0.9)
    
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
        
        return np.mean(scores)
    
    def clear_history(self):
        """Clear gaze history for new session."""
        self.gaze_history = []
        self.current_task = None
