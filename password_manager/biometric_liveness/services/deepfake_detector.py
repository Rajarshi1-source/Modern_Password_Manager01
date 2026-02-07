"""
Deepfake Detector Service
==========================

Ensemble detector for identifying AI-generated/manipulated faces.
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class DeepfakeAnalysis:
    """Analysis result from deepfake detection."""
    is_fake: bool
    fake_probability: float
    confidence: float
    texture_score: float
    temporal_score: float
    frequency_score: float
    blending_score: float
    artifacts_detected: List[str]


class DeepfakeDetector:
    """Ensemble deepfake detector using multiple techniques."""
    
    FAKE_THRESHOLD = 0.7
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.frame_history: List[np.ndarray] = []
        self.analysis_history: List[DeepfakeAnalysis] = []
        self._dcnn_model = None
        logger.info("DeepfakeDetector initialized")
    
    def analyze_frame(self, frame: np.ndarray, face_region: Optional[np.ndarray] = None, timestamp_ms: float = 0) -> DeepfakeAnalysis:
        """Analyze a single frame for deepfake indicators."""
        roi = face_region if face_region is not None else frame
        self.frame_history.append(roi.copy())
        if len(self.frame_history) > 30:
            self.frame_history.pop(0)
        
        texture_score, texture_artifacts = self._analyze_texture(roi)
        frequency_score, freq_artifacts = self._analyze_frequency_domain(roi)
        temporal_score = self._analyze_temporal_consistency()
        blending_score, blend_artifacts = self._analyze_blending(roi)
        
        all_artifacts = texture_artifacts + freq_artifacts + blend_artifacts
        fake_probability = (texture_score * 0.3 + frequency_score * 0.25 + temporal_score * 0.25 + blending_score * 0.2)
        confidence = 1.0 - np.std([texture_score, frequency_score, temporal_score, blending_score])
        
        analysis = DeepfakeAnalysis(
            is_fake=fake_probability > self.FAKE_THRESHOLD,
            fake_probability=fake_probability,
            confidence=confidence,
            texture_score=texture_score,
            temporal_score=temporal_score,
            frequency_score=frequency_score,
            blending_score=blending_score,
            artifacts_detected=all_artifacts
        )
        self.analysis_history.append(analysis)
        return analysis
    
    def _analyze_texture(self, roi: np.ndarray) -> Tuple[float, List[str]]:
        """Analyze texture for GAN artifacts."""
        if roi.size == 0:
            return 0.5, []
        gray = np.mean(roi, axis=2) if len(roi.shape) == 3 else roi
        lbp_var = np.var(gray) / 1000
        if lbp_var < 0.1:
            return 0.8, ['Unnatural texture uniformity']
        return 0.2, []
    
    def _analyze_frequency_domain(self, roi: np.ndarray) -> Tuple[float, List[str]]:
        """Analyze frequency domain for GAN signatures."""
        if roi.size == 0:
            return 0.5, []
        gray = np.mean(roi, axis=2) if len(roi.shape) == 3 else roi
        fft = np.fft.fft2(gray)
        fft_shift = np.fft.fftshift(np.abs(fft))
        h, w = fft_shift.shape
        low_freq = np.mean(fft_shift[h//2-10:h//2+10, w//2-10:w//2+10])
        high_freq = np.mean([np.mean(fft_shift[:10, :]), np.mean(fft_shift[-10:, :])])
        if low_freq > 0 and high_freq / low_freq < 0.01:
            return 0.8, ['Missing high-frequency details']
        return 0.2, []
    
    def _analyze_temporal_consistency(self) -> float:
        """Analyze temporal consistency across frames."""
        if len(self.frame_history) < 3:
            return 0.5
        scores = []
        for i in range(1, len(self.frame_history)):
            if self.frame_history[i-1].shape == self.frame_history[i].shape:
                diff = np.mean(np.abs(self.frame_history[i].astype(float) - self.frame_history[i-1].astype(float)))
                scores.append(0.8 if diff > 30 else 0.2)
        return np.mean(scores) if scores else 0.5
    
    def _analyze_blending(self, roi: np.ndarray) -> Tuple[float, List[str]]:
        """Analyze for face blending artifacts."""
        if roi.size == 0 or roi.shape[0] < 20:
            return 0.5, []
        h, w = roi.shape[:2]
        if len(roi.shape) == 3:
            inner = np.mean(roi[int(h*0.2):int(h*0.8), int(w*0.2):int(w*0.8)], axis=(0, 1))
            outer = np.mean(roi[:int(h*0.1), :], axis=(0, 1))
            if np.linalg.norm(inner - outer) > 50:
                return 0.8, ['Color discontinuity at boundaries']
        return 0.2, []
    
    def get_liveness_score(self) -> float:
        """Get liveness score (inverse of fake probability)."""
        if not self.analysis_history:
            return 0.5
        avg_prob = np.mean([a.fake_probability for a in self.analysis_history])
        return max(0.0, min(1.0, 1.0 - avg_prob))
    
    def reset(self):
        """Reset state for new session."""
        self.frame_history = []
        self.analysis_history = []
