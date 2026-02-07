"""
Thermal Imaging Service
========================

Thermal/IR camera integration for liveness detection.
Detects screen-based attacks by analyzing heat signatures
that cannot be faked with photos or videos.

Features:
- Process thermal/IR frames
- Detect natural facial heat patterns
- Identify screen-based attacks (cold flat surface)
- Validate living tissue temperature range
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ThermalReading:
    """Single thermal measurement."""
    timestamp_ms: float
    frame_number: int
    average_temp_c: float
    min_temp_c: float
    max_temp_c: float
    has_natural_gradient: bool
    matches_living_tissue: bool
    heat_map_features: Dict


class ThermalImagingService:
    """
    Thermal imaging service for liveness detection.
    
    Uses infrared/thermal camera data to verify that the subject
    is a living person and not a screen, photo, or mask.
    """
    
    # Temperature thresholds for living tissue
    MIN_FACE_TEMP_C = 33.0  # Lower bound (cold room)
    MAX_FACE_TEMP_C = 38.0  # Upper bound (fever)
    CORE_TEMP_RANGE = (35.0, 37.5)  # Normal core face temp
    
    # Screen detection
    SCREEN_TEMP_UNIFORMITY_THRESHOLD = 0.5  # Low variance = screen
    
    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize thermal imaging service.
        
        Args:
            config: Configuration options
        """
        self.config = config or {}
        self.enabled = self.config.get('thermal_enabled', False)
        self.min_temp = self.config.get('thermal_min_temp_c', self.MIN_FACE_TEMP_C)
        self.max_temp = self.config.get('thermal_max_temp_c', self.MAX_FACE_TEMP_C)
        
        self.frame_count = 0
        self.readings: List[ThermalReading] = []
        
        logger.info(f"ThermalImagingService initialized (enabled={self.enabled})")
    
    def is_available(self) -> bool:
        """Check if thermal camera is available."""
        # Would check for actual thermal camera hardware
        return self.enabled
    
    def process_thermal_frame(
        self,
        thermal_frame: np.ndarray,
        timestamp_ms: float,
        face_region: Optional[Tuple[int, int, int, int]] = None
    ) -> Optional[ThermalReading]:
        """
        Process a thermal/IR frame.
        
        Args:
            thermal_frame: Thermal image (single channel, values in Celsius or raw)
            timestamp_ms: Frame timestamp
            face_region: Optional (x, y, w, h) face bounding box
            
        Returns:
            Thermal reading or None
        """
        if not self.enabled:
            return None
        
        self.frame_count += 1
        
        # Extract face region if provided
        if face_region is not None:
            x, y, w, h = face_region
            roi = thermal_frame[y:y+h, x:x+w]
        else:
            # Assume centered face
            h, w = thermal_frame.shape[:2]
            roi = thermal_frame[int(h*0.2):int(h*0.8), int(w*0.2):int(w*0.8)]
        
        if roi.size == 0:
            return None
        
        # Calculate temperature statistics
        avg_temp = float(np.mean(roi))
        min_temp = float(np.min(roi))
        max_temp = float(np.max(roi))
        
        # Check for natural thermal gradient
        has_gradient = self._detect_natural_gradient(roi)
        
        # Check if in living tissue range
        matches_living = self._matches_living_tissue(avg_temp, min_temp, max_temp)
        
        # Extract heat map features
        features = self._extract_heat_features(roi)
        
        reading = ThermalReading(
            timestamp_ms=timestamp_ms,
            frame_number=self.frame_count,
            average_temp_c=avg_temp,
            min_temp_c=min_temp,
            max_temp_c=max_temp,
            has_natural_gradient=has_gradient,
            matches_living_tissue=matches_living,
            heat_map_features=features
        )
        
        self.readings.append(reading)
        return reading
    
    def _detect_natural_gradient(self, thermal_roi: np.ndarray) -> bool:
        """
        Detect natural facial thermal gradient.
        
        Living faces have:
        - Warmer nose tip
        - Warmer periorbital region
        - Cooler periphery
        - Non-uniform temperature distribution
        """
        if thermal_roi.size < 100:
            return False
        
        # Calculate variance - screens are very uniform
        temp_std = np.std(thermal_roi)
        if temp_std < self.SCREEN_TEMP_UNIFORMITY_THRESHOLD:
            return False  # Too uniform, likely screen
        
        # Check for gradient from center to edges
        h, w = thermal_roi.shape
        center_region = thermal_roi[int(h*0.3):int(h*0.7), int(w*0.3):int(w*0.7)]
        edge_top = thermal_roi[:int(h*0.2), :]
        edge_bottom = thermal_roi[int(h*0.8):, :]
        
        center_temp = np.mean(center_region)
        edge_temp = (np.mean(edge_top) + np.mean(edge_bottom)) / 2
        
        # Center should be warmer than edges
        gradient = center_temp - edge_temp
        
        return gradient > 0.5  # At least 0.5°C difference
    
    def _matches_living_tissue(
        self, 
        avg_temp: float, 
        min_temp: float, 
        max_temp: float
    ) -> bool:
        """Check if temperature matches living tissue."""
        # Average in normal range
        if not (self.min_temp <= avg_temp <= self.max_temp):
            return False
        
        # Reasonable temperature spread
        temp_range = max_temp - min_temp
        if temp_range < 0.5 or temp_range > 8.0:
            return False
        
        return True
    
    def _extract_heat_features(self, thermal_roi: np.ndarray) -> Dict:
        """Extract thermal feature points for analysis."""
        h, w = thermal_roi.shape
        
        # Divide into regions
        regions = {
            'forehead': thermal_roi[:int(h*0.25), :],
            'eyes': thermal_roi[int(h*0.25):int(h*0.4), :],
            'nose': thermal_roi[int(h*0.4):int(h*0.6), int(w*0.3):int(w*0.7)],
            'cheeks': thermal_roi[int(h*0.4):int(h*0.7), :],
            'mouth_chin': thermal_roi[int(h*0.7):, :]
        }
        
        features = {}
        for region_name, region in regions.items():
            if region.size > 0:
                features[f'{region_name}_mean'] = float(np.mean(region))
                features[f'{region_name}_std'] = float(np.std(region))
        
        return features
    
    def detect_screen_attack(self, readings: List[ThermalReading]) -> Dict:
        """
        Detect if thermal data indicates screen-based attack.
        
        Screens show:
        - Very uniform temperature
        - Temperature outside living tissue range
        - No natural gradient
        - Constant temperature over time
        
        Returns:
            Detection result with confidence
        """
        if not readings:
            return {
                'is_screen': None,
                'confidence': 0.0,
                'reason': 'No thermal data'
            }
        
        # Check temperature uniformity
        uniformity_scores = []
        for r in readings:
            if r.max_temp_c - r.min_temp_c < 1.0:
                uniformity_scores.append(1.0)  # Suspicious
            else:
                uniformity_scores.append(0.0)
        
        # Check gradient presence
        gradient_scores = [0.0 if r.has_natural_gradient else 1.0 for r in readings]
        
        # Check living tissue match
        tissue_scores = [0.0 if r.matches_living_tissue else 1.0 for r in readings]
        
        # Check temporal consistency (screens are very stable)
        if len(readings) > 5:
            temps = [r.average_temp_c for r in readings]
            temp_variation = np.std(temps)
            # Very low variation is suspicious
            temporal_score = 1.0 if temp_variation < 0.1 else 0.0
        else:
            temporal_score = 0.5
        
        # Aggregate scores
        screen_probability = np.mean([
            np.mean(uniformity_scores) * 0.3,
            np.mean(gradient_scores) * 0.3,
            np.mean(tissue_scores) * 0.25,
            temporal_score * 0.15
        ])
        
        is_screen = screen_probability > 0.5
        
        reasons = []
        if np.mean(uniformity_scores) > 0.5:
            reasons.append('Uniform temperature')
        if np.mean(gradient_scores) > 0.5:
            reasons.append('No natural gradient')
        if np.mean(tissue_scores) > 0.5:
            reasons.append('Outside living tissue range')
        
        return {
            'is_screen': is_screen,
            'confidence': abs(screen_probability - 0.5) * 2,  # 0-1 confidence
            'probability': screen_probability,
            'reason': ', '.join(reasons) if reasons else None
        }
    
    def detect_mask_attack(self, readings: List[ThermalReading]) -> Dict:
        """
        Detect if thermal data indicates mask-based attack.
        
        Masks show:
        - Lower average temperature
        - Missing periorbital heat signature
        - Unnatural heat distribution
        
        Returns:
            Detection result with confidence
        """
        if not readings:
            return {
                'is_mask': None,
                'confidence': 0.0,
                'reason': 'No thermal data'
            }
        
        # Check for missing eye heat signature
        eye_signature_scores = []
        for r in readings:
            eye_mean = r.heat_map_features.get('eyes_mean', 0)
            cheek_mean = r.heat_map_features.get('cheeks_mean', 0)
            
            # Eyes should be warmer than cheeks
            if eye_mean > cheek_mean:
                eye_signature_scores.append(0.0)  # Normal
            else:
                eye_signature_scores.append(1.0)  # Suspicious
        
        # Check average temperature
        avg_temps = [r.average_temp_c for r in readings]
        mean_temp = np.mean(avg_temps)
        
        # Masks are typically cooler
        temp_score = 1.0 if mean_temp < 33.5 else 0.0
        
        mask_probability = np.mean([
            np.mean(eye_signature_scores) * 0.5,
            temp_score * 0.5
        ])
        
        return {
            'is_mask': mask_probability > 0.5,
            'confidence': abs(mask_probability - 0.5) * 2,
            'probability': mask_probability,
            'reason': 'Abnormal thermal pattern' if mask_probability > 0.5 else None
        }
    
    def get_liveness_score(self, readings: List[ThermalReading]) -> float:
        """
        Calculate thermal-based liveness score.
        
        Returns:
            Liveness score 0-1
        """
        if not readings:
            return 0.5  # Neutral if no thermal data
        
        screen_result = self.detect_screen_attack(readings)
        mask_result = self.detect_mask_attack(readings)
        
        # Start with base score
        score = 1.0
        
        # Reduce for screen detection
        if screen_result['is_screen']:
            score -= screen_result['confidence'] * 0.8
        
        # Reduce for mask detection
        if mask_result['is_mask']:
            score -= mask_result['confidence'] * 0.6
        
        # Check living tissue consistency
        valid_readings = [r for r in readings if r.matches_living_tissue]
        tissue_score = len(valid_readings) / len(readings)
        
        # Check gradient consistency
        gradient_readings = [r for r in readings if r.has_natural_gradient]
        gradient_score = len(gradient_readings) / len(readings)
        
        # Weighted combination
        final_score = (
            score * 0.4 +
            tissue_score * 0.3 +
            gradient_score * 0.3
        )
        
        return max(0.0, min(1.0, final_score))
    
    def reset(self):
        """Reset state for new session."""
        self.frame_count = 0
        self.readings = []
