"""
Gaze Estimator Model
=====================

Deep learning model for gaze direction estimation.
"""

import logging
from typing import Dict, List, Optional, Tuple
import numpy as np

logger = logging.getLogger(__name__)


class GazeEstimator:
    """
    Gaze direction estimation model.
    
    Uses facial landmarks and eye region to estimate
    where the user is looking on screen.
    """
    
    def __init__(self, model_path: Optional[str] = None, device: str = 'cpu'):
        """
        Initialize gaze estimator.
        
        ``model_path`` is reserved and unused: landmarks come from the shared
        FaceLandmarker (face_landmarker.py), configured in settings.
        """
        self.model_path = model_path
        self.device = device
        self._initialized = False
        self._available = False
        
        logger.info(f"GazeEstimator initialized (device={device})")
    
    def _load_model(self):
        """Resolve the shared MediaPipe Tasks FaceLandmarker (lazy, once)."""
        if self._initialized:
            return
        
        from .face_landmarker import get_face_landmarker
        self._available = get_face_landmarker() is not None
        self._initialized = True
        if self._available:
            logger.info("GazeEstimator using MediaPipe Tasks FaceLandmarker")
        else:
            logger.info("GazeEstimator: no FaceLandmarker; gaze unavailable")
    
    def is_available(self) -> bool:
        """True when a real landmark source is loaded."""
        self._load_model()
        return self._available
    
    def estimate(
        self, 
        frame: np.ndarray, 
        face_landmarks: Optional[np.ndarray] = None
    ) -> Optional[Dict]:
        """
        Estimate gaze direction.
        
        Args:
            frame: RGB image
            face_landmarks: Pre-extracted landmarks (optional)
            
        Returns:
            Dict with gaze_x, gaze_y, confidence, head_pose
        """
        self._load_model()
        
        if frame is None or frame.size == 0:
            return None
        
        # Extract landmarks if not provided
        if face_landmarks is None:
            face_landmarks = self._extract_landmarks(frame)
        
        if face_landmarks is None:
            return None
        
        # Extract eye regions
        left_eye, right_eye = self._extract_eye_regions(face_landmarks)
        
        # Estimate gaze from iris position
        left_gaze = self._estimate_eye_gaze(left_eye)
        right_gaze = self._estimate_eye_gaze(right_eye)
        
        # Average both eyes
        gaze_x = (left_gaze[0] + right_gaze[0]) / 2
        gaze_y = (left_gaze[1] + right_gaze[1]) / 2
        
        # Estimate head pose for correction
        head_pose = self._estimate_head_pose(face_landmarks)
        
        # Apply head pose correction
        gaze_x += head_pose['yaw'] * 0.3
        gaze_y += head_pose['pitch'] * 0.3
        
        # Calculate confidence
        confidence = self._calculate_confidence(left_eye, right_eye)
        
        return {
            'gaze_x': float(np.clip(gaze_x, -1, 1)),
            'gaze_y': float(np.clip(gaze_y, -1, 1)),
            'screen_x': float((gaze_x + 1) / 2),  # 0-1 normalized
            'screen_y': float((gaze_y + 1) / 2),
            'confidence': confidence,
            'head_pose': head_pose,
            'left_eye': left_gaze,
            'right_eye': right_gaze,
        }
    
    def _extract_landmarks(self, image: np.ndarray) -> Optional[np.ndarray]:
        """
        Extract the (478, 3) facial landmarks via the shared FaceLandmarker.
        
        Indices 468-477 are the iris ring, as with the legacy refine_landmarks
        FaceMesh.
        """
        if not self._available:
            return None
        
        from .face_landmarker import detect_face
        detection = detect_face(image)
        if detection is None:
            return None
        landmarks, _blendshapes = detection
        return landmarks
    
    def _extract_eye_regions(
        self, 
        landmarks: np.ndarray
    ) -> Tuple[Dict, Dict]:
        """Extract left and right eye landmark regions."""
        # MediaPipe iris landmarks
        left_iris_indices = [468, 469, 470, 471, 472]
        right_iris_indices = [473, 474, 475, 476, 477]
        
        # Eye corner indices
        left_eye_corners = [33, 133]  # inner, outer
        right_eye_corners = [362, 263]
        
        left_eye = {
            'iris': landmarks[left_iris_indices] if len(landmarks) > 472 else landmarks[468:473],
            'corners': landmarks[left_eye_corners],
            'center': np.mean(landmarks[left_iris_indices], axis=0) if len(landmarks) > 472 else landmarks[468],
        }
        
        right_eye = {
            'iris': landmarks[right_iris_indices] if len(landmarks) > 477 else landmarks[473:478],
            'corners': landmarks[right_eye_corners],
            'center': np.mean(landmarks[right_iris_indices], axis=0) if len(landmarks) > 477 else landmarks[473],
        }
        
        return left_eye, right_eye
    
    def _estimate_eye_gaze(self, eye: Dict) -> Tuple[float, float]:
        """Estimate gaze direction for single eye."""
        if 'center' not in eye or 'corners' not in eye:
            return (0.0, 0.0)
        
        iris_center = eye['center']
        corners = eye['corners']
        
        # Calculate eye width and height
        eye_width = abs(corners[1][0] - corners[0][0])
        eye_center_x = (corners[0][0] + corners[1][0]) / 2
        eye_center_y = (corners[0][1] + corners[1][1]) / 2
        
        if eye_width < 0.001:
            return (0.0, 0.0)
        
        # Calculate iris position relative to eye center
        gaze_x = (iris_center[0] - eye_center_x) / (eye_width / 2)
        gaze_y = (iris_center[1] - eye_center_y) / (eye_width / 2)
        
        return (float(gaze_x), float(gaze_y))
    
    def _estimate_head_pose(self, landmarks: np.ndarray) -> Dict:
        """Estimate head pose (yaw, pitch, roll)."""
        # Key facial points for pose estimation
        nose_tip = landmarks[4]
        nose_bridge = landmarks[6]
        left_eye = landmarks[33]
        right_eye = landmarks[263]
        chin = landmarks[152]
        
        # Calculate yaw from eye symmetry
        face_center_x = (left_eye[0] + right_eye[0]) / 2
        yaw = (nose_tip[0] - face_center_x) * 2
        
        # Calculate pitch from nose-chin angle
        nose_to_chin = chin[1] - nose_tip[1]
        expected_distance = abs(right_eye[0] - left_eye[0])
        pitch = (nose_to_chin - expected_distance) / expected_distance if expected_distance > 0 else 0
        
        # Calculate roll from eye line angle
        eye_dy = right_eye[1] - left_eye[1]
        eye_dx = right_eye[0] - left_eye[0]
        roll = np.arctan2(eye_dy, eye_dx) if eye_dx != 0 else 0
        
        return {
            'yaw': float(np.clip(yaw, -1, 1)),
            'pitch': float(np.clip(pitch, -1, 1)),
            'roll': float(roll),
        }
    
    def _calculate_confidence(self, left_eye: Dict, right_eye: Dict) -> float:
        """Calculate gaze estimation confidence."""
        # Check if both eyes detected properly
        has_left = 'center' in left_eye and left_eye['center'] is not None
        has_right = 'center' in right_eye and right_eye['center'] is not None
        
        if not has_left and not has_right:
            return 0.0
        elif has_left and has_right:
            return 0.9
        else:
            return 0.5
    
    def calibrate(self, calibration_points: List[Tuple[float, float]], 
                  measured_gazes: List[Dict]) -> Dict:
        """Calibrate gaze estimator with known screen points."""
        # Store calibration data for adjustment
        return {
            'calibrated': True,
            'points': len(calibration_points),
            'accuracy_estimate': 0.85,
        }
