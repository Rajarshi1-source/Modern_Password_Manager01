"""
Action Unit Detector
=====================

CNN-based Facial Action Unit (AU) detection model.
Detects micro-expressions using the Facial Action Coding System (FACS).
"""

import logging
from typing import Dict, List, Optional, Tuple
import numpy as np

logger = logging.getLogger(__name__)


class ActionUnitDetector:
    """
    Facial Action Unit detector using CNN.
    
    Detects AUs 1-28 for expression analysis:
    - AU1: Inner Brow Raiser
    - AU2: Outer Brow Raiser
    - AU4: Brow Lowerer
    - AU5: Upper Lid Raiser
    - AU6: Cheek Raiser
    - AU7: Lid Tightener
    - AU9: Nose Wrinkler
    - AU10: Upper Lip Raiser
    - AU12: Lip Corner Puller (smile)
    - AU14: Dimpler
    - AU15: Lip Corner Depressor
    - AU17: Chin Raiser
    - AU20: Lip Stretcher
    - AU23: Lip Tightener
    - AU25: Lips Part
    - AU26: Jaw Drop
    - AU28: Lip Suck
    """
    
    # Standard AU labels
    AU_LABELS = [
        'AU1', 'AU2', 'AU4', 'AU5', 'AU6', 'AU7', 'AU9', 'AU10',
        'AU12', 'AU14', 'AU15', 'AU17', 'AU20', 'AU23', 'AU25', 'AU26', 'AU28'
    ]
    
    def __init__(self, model_path: Optional[str] = None, device: str = 'cpu'):
        """
        Initialize AU detector.
        
        Args:
            model_path: Reserved for a trained AU model; unused. Landmarks come
                from the shared FaceLandmarker (face_landmarker.py), whose
                ``face_landmarker.task`` asset is configured in settings.
            device: 'cpu' or 'cuda'
        """
        self.model_path = model_path
        self.device = device
        self._available = False
        self._initialized = False
        
        logger.info(f"ActionUnitDetector initialized (device={device})")
    
    def _load_model(self):
        """Resolve the shared MediaPipe Tasks FaceLandmarker (lazy, once)."""
        if self._initialized:
            return
        
        from .face_landmarker import get_face_landmarker
        self._available = get_face_landmarker() is not None
        self._initialized = True
        if self._available:
            logger.info("ActionUnitDetector using MediaPipe Tasks FaceLandmarker")
        else:
            logger.info("ActionUnitDetector: no FaceLandmarker; AUs report inactive")
    
    def is_available(self) -> bool:
        """True when a real landmark source is loaded."""
        self._load_model()
        return self._available
    
    def detect(self, face_image: np.ndarray) -> Dict[str, float]:
        """
        Detect Action Units in face image.
        
        Args:
            face_image: RGB face image (h, w, 3)
            
        Returns:
            Dict mapping AU names to intensity (0-1)
        """
        self._load_model()
        
        if face_image is None or face_image.size == 0:
            return {au: 0.0 for au in self.AU_LABELS}
        
        try:
            # Extract landmarks
            landmarks = self._extract_landmarks(face_image)
            if landmarks is None:
                return {au: 0.0 for au in self.AU_LABELS}
            
            # Compute AUs from landmarks
            aus = self._compute_aus_from_landmarks(landmarks)
            return aus
            
        except Exception as e:
            logger.error(f"AU detection error: {e}")
            return {au: 0.0 for au in self.AU_LABELS}
    
    def _extract_landmarks(self, image: np.ndarray) -> Optional[np.ndarray]:
        """
        Extract the (478, 3) facial landmarks via the shared FaceLandmarker.
        
        Same 468 face + 10 iris topology as the legacy refine_landmarks
        FaceMesh, so the indices below are unchanged.
        """
        if not self._available:
            return None
        
        from .face_landmarker import detect_face
        detection = detect_face(image)
        if detection is None:
            return None
        landmarks, _blendshapes = detection
        return landmarks
    
    def _compute_aus_from_landmarks(self, landmarks: np.ndarray) -> Dict[str, float]:
        """Compute AU intensities from facial landmarks."""
        aus = {}
        
        # MediaPipe face mesh indices for key points
        # Eyebrows
        left_brow = landmarks[[70, 63, 105, 66, 107]]
        right_brow = landmarks[[300, 293, 334, 296, 336]]
        
        # Eyes
        left_eye_top = landmarks[159]
        left_eye_bottom = landmarks[145]
        right_eye_top = landmarks[386]
        right_eye_bottom = landmarks[374]
        
        # Mouth
        mouth_left = landmarks[61]
        mouth_right = landmarks[291]
        mouth_top = landmarks[13]
        mouth_bottom = landmarks[14]
        upper_lip = landmarks[0]
        lower_lip = landmarks[17]
        
        # Nose
        nose_tip = landmarks[4]
        
        # AU1 - Inner Brow Raiser (brow height)
        brow_height = np.mean([landmarks[66][1], landmarks[296][1]])
        aus['AU1'] = max(0, min(1, (0.3 - brow_height) * 5))
        
        # AU2 - Outer Brow Raiser
        outer_brow_height = np.mean([landmarks[107][1], landmarks[336][1]])
        aus['AU2'] = max(0, min(1, (0.3 - outer_brow_height) * 5))
        
        # AU4 - Brow Lowerer (brows close together)
        brow_distance = abs(landmarks[66][0] - landmarks[296][0])
        aus['AU4'] = max(0, min(1, (0.15 - brow_distance) * 10))
        
        # AU5 - Upper Lid Raiser (eye openness)
        eye_openness = (abs(left_eye_top[1] - left_eye_bottom[1]) + 
                       abs(right_eye_top[1] - right_eye_bottom[1])) / 2
        aus['AU5'] = max(0, min(1, eye_openness * 20))
        
        # AU6 - Cheek Raiser (smile with eyes)
        cheek_height = landmarks[50][1] - landmarks[101][1]
        aus['AU6'] = max(0, min(1, -cheek_height * 10))
        
        # AU7 - Lid Tightener
        aus['AU7'] = max(0, min(1, 1 - aus['AU5']))
        
        # AU9 - Nose Wrinkler
        nose_wrinkle = abs(landmarks[4][1] - landmarks[5][1])
        aus['AU9'] = max(0, min(1, nose_wrinkle * 20))
        
        # AU10 - Upper Lip Raiser
        upper_lip_height = mouth_top[1] - upper_lip[1]
        aus['AU10'] = max(0, min(1, -upper_lip_height * 10))
        
        # AU12 - Lip Corner Puller (smile)
        mouth_width = abs(mouth_left[0] - mouth_right[0])
        corner_height = (mouth_left[1] + mouth_right[1]) / 2 - mouth_top[1]
        aus['AU12'] = max(0, min(1, (mouth_width * 5 - corner_height * 10)))
        
        # AU14 - Dimpler
        aus['AU14'] = max(0, min(1, aus['AU12'] * 0.5))
        
        # AU15 - Lip Corner Depressor
        corner_drop = (mouth_left[1] + mouth_right[1]) / 2 - mouth_bottom[1]
        aus['AU15'] = max(0, min(1, corner_drop * 10))
        
        # AU17 - Chin Raiser
        chin_raise = landmarks[152][1] - lower_lip[1]
        aus['AU17'] = max(0, min(1, -chin_raise * 10))
        
        # AU20 - Lip Stretcher
        aus['AU20'] = max(0, min(1, mouth_width * 3 - 0.3))
        
        # AU23 - Lip Tightener
        lip_thickness = abs(mouth_top[1] - mouth_bottom[1])
        aus['AU23'] = max(0, min(1, (0.05 - lip_thickness) * 20))
        
        # AU25 - Lips Part
        lip_separation = abs(upper_lip[1] - lower_lip[1])
        aus['AU25'] = max(0, min(1, lip_separation * 15))
        
        # AU26 - Jaw Drop
        jaw_drop = landmarks[152][1] - landmarks[10][1]
        aus['AU26'] = max(0, min(1, jaw_drop * 5))
        
        # AU28 - Lip Suck
        aus['AU28'] = max(0, min(1, (0.02 - lip_thickness) * 50))
        
        return aus
    
    def detect_batch(self, face_images: List[np.ndarray]) -> List[Dict[str, float]]:
        """Detect AUs for multiple faces."""
        return [self.detect(img) for img in face_images]
    
    def get_expression_summary(self, aus: Dict[str, float]) -> str:
        """Get expression summary from AU activations."""
        # Detect primary expressions
        if aus.get('AU12', 0) > 0.5 and aus.get('AU6', 0) > 0.3:
            return 'genuine_smile'
        elif aus.get('AU12', 0) > 0.5:
            return 'social_smile'
        elif aus.get('AU1', 0) > 0.5 and aus.get('AU4', 0) > 0.3:
            return 'sad'
        elif aus.get('AU4', 0) > 0.5 and aus.get('AU7', 0) > 0.3:
            return 'angry'
        elif aus.get('AU1', 0) > 0.5 and aus.get('AU2', 0) > 0.5 and aus.get('AU5', 0) > 0.5:
            return 'surprised'
        elif aus.get('AU9', 0) > 0.5:
            return 'disgust'
        elif aus.get('AU1', 0) > 0.3 and aus.get('AU4', 0) > 0.3:
            return 'fear'
        else:
            return 'neutral'
