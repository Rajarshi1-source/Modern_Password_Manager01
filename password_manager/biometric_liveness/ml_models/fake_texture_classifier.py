"""
Fake Texture Classifier
========================

GAN artifact detection model for identifying AI-generated faces.
"""

import logging
from typing import Dict, List, Optional
import numpy as np

logger = logging.getLogger(__name__)


class FakeTextureClassifier:
    """
    Classifier for detecting GAN-generated face artifacts.
    
    Detects synthetic faces from:
    - Texture inconsistencies
    - Frequency domain anomalies
    - Color distribution artifacts
    - Boundary blending issues
    """
    
    def __init__(self, model_path: Optional[str] = None, device: str = 'cpu'):
        """Initialize fake texture classifier."""
        self.model_path = model_path
        self.device = device
        self._initialized = False
        
        logger.info(f"FakeTextureClassifier initialized (device={device})")
    
    def classify(self, face_image: np.ndarray) -> Dict:
        """
        Classify face image as real or fake.
        
        Args:
            face_image: RGB face image
            
        Returns:
            Dict with fake_probability, confidence, artifacts
        """
        if face_image is None or face_image.size == 0:
            return {
                'fake_probability': 0.5,
                'confidence': 0.0,
                'artifacts': [],
            }
        
        artifacts = []
        scores = []
        
        # Texture analysis
        texture_score, texture_artifacts = self._analyze_texture(face_image)
        scores.append(texture_score)
        artifacts.extend(texture_artifacts)
        
        # Frequency analysis
        freq_score, freq_artifacts = self._analyze_frequency(face_image)
        scores.append(freq_score)
        artifacts.extend(freq_artifacts)
        
        # Color analysis
        color_score, color_artifacts = self._analyze_color(face_image)
        scores.append(color_score)
        artifacts.extend(color_artifacts)
        
        # Boundary analysis
        boundary_score, boundary_artifacts = self._analyze_boundaries(face_image)
        scores.append(boundary_score)
        artifacts.extend(boundary_artifacts)
        
        fake_probability = np.mean(scores)
        confidence = 1.0 - np.std(scores)
        
        return {
            'fake_probability': float(fake_probability),
            'confidence': float(confidence),
            'is_fake': fake_probability > 0.5,
            'artifacts': list(set(artifacts)),
            'texture_score': float(texture_score),
            'frequency_score': float(freq_score),
            'color_score': float(color_score),
            'boundary_score': float(boundary_score),
        }
    
    def _analyze_texture(self, image: np.ndarray) -> tuple:
        """Analyze texture for GAN artifacts."""
        artifacts = []
        
        gray = np.mean(image, axis=2) if len(image.shape) == 3 else image
        
        # Local variance analysis
        from scipy.ndimage import uniform_filter
        local_mean = uniform_filter(gray, size=5)
        local_sqr_mean = uniform_filter(gray ** 2, size=5)
        local_var = np.sqrt(np.maximum(local_sqr_mean - local_mean ** 2, 0))
        
        # Low variance regions (over-smoothed by GAN)
        smooth_ratio = np.mean(local_var < 5) 
        if smooth_ratio > 0.3:
            artifacts.append('over_smoothed_regions')
        
        # Abnormal texture uniformity
        global_std = np.std(gray)
        if global_std < 20:
            artifacts.append('unnaturally_uniform')
            return 0.8, artifacts
        
        score = smooth_ratio * 0.8 + (1 - global_std / 80) * 0.2
        return max(0, min(1, score)), artifacts
    
    def _analyze_frequency(self, image: np.ndarray) -> tuple:
        """Analyze frequency domain for GAN fingerprints."""
        artifacts = []
        
        gray = np.mean(image, axis=2) if len(image.shape) == 3 else image
        
        # FFT analysis
        fft = np.fft.fft2(gray)
        fft_shift = np.fft.fftshift(np.abs(fft))
        
        h, w = fft_shift.shape
        center_h, center_w = h // 2, w // 2
        
        # Analyze power spectrum
        low_freq = np.mean(fft_shift[center_h-10:center_h+10, center_w-10:center_w+10])
        high_freq = np.mean([
            np.mean(fft_shift[:10, :]),
            np.mean(fft_shift[-10:, :]),
            np.mean(fft_shift[:, :10]),
            np.mean(fft_shift[:, -10:])
        ])
        
        # GANs often lack high frequency detail
        if low_freq > 0:
            ratio = high_freq / low_freq
            if ratio < 0.01:
                artifacts.append('missing_high_frequencies')
                return 0.7, artifacts
        
        # Check for periodic artifacts (upsampling)
        quarter_h, quarter_w = h // 4, w // 4
        quarter_power = np.mean(fft_shift[quarter_h-5:quarter_h+5, quarter_w-5:quarter_w+5])
        center_power = np.mean(fft_shift[center_h-5:center_h+5, center_w-5:center_w+5])
        
        if center_power > 0 and quarter_power / center_power > 0.1:
            artifacts.append('periodic_upsample_artifacts')
            return 0.6, artifacts
        
        return 0.2, artifacts
    
    def _analyze_color(self, image: np.ndarray) -> tuple:
        """Analyze color distribution for anomalies."""
        artifacts = []
        
        if len(image.shape) != 3 or image.shape[2] < 3:
            return 0.5, artifacts
        
        r, g, b = image[:, :, 0], image[:, :, 1], image[:, :, 2]
        
        # Check channel correlations
        try:
            rg_corr = np.corrcoef(r.flatten(), g.flatten())[0, 1]
            rb_corr = np.corrcoef(r.flatten(), b.flatten())[0, 1]
            gb_corr = np.corrcoef(g.flatten(), b.flatten())[0, 1]
            
            # Extremely high correlation is suspicious
            avg_corr = (abs(rg_corr) + abs(rb_corr) + abs(gb_corr)) / 3
            if avg_corr > 0.98:
                artifacts.append('unnatural_color_correlation')
                return 0.7, artifacts
            
            # Very low correlation is also suspicious
            if avg_corr < 0.3:
                artifacts.append('unusual_color_independence')
                return 0.6, artifacts
                
        except:
            pass
        
        return 0.2, artifacts
    
    def _analyze_boundaries(self, image: np.ndarray) -> tuple:
        """Analyze for face-swap boundary artifacts."""
        artifacts = []
        
        h, w = image.shape[:2]
        
        if len(image.shape) == 3:
            # Compare center vs edge colors
            center = image[int(h*0.3):int(h*0.7), int(w*0.3):int(w*0.7)]
            edges = np.concatenate([
                image[:int(h*0.1), :].reshape(-1, 3),
                image[int(h*0.9):, :].reshape(-1, 3)
            ])
            
            center_mean = np.mean(center.reshape(-1, 3), axis=0)
            edge_mean = np.mean(edges, axis=0)
            
            color_diff = np.linalg.norm(center_mean - edge_mean)
            
            if color_diff > 40:
                artifacts.append('color_boundary_discontinuity')
                return 0.7, artifacts
        
        return 0.2, artifacts
    
    def classify_batch(self, images: List[np.ndarray]) -> List[Dict]:
        """Classify multiple images."""
        return [self.classify(img) for img in images]
