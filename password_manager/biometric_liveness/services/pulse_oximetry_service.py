"""
Pulse Oximetry Service (rPPG)
==============================

Remote photoplethysmography for liveness detection.
Extracts pulse and blood oxygen patterns from camera video
that cannot be faked by deepfakes or static images.

Features:
- Extract PPG signal from facial video
- Estimate heart rate and variability
- Estimate SpO2 (blood oxygen)
- Validate physiological consistency
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import numpy as np
from collections import deque

logger = logging.getLogger(__name__)


@dataclass
class PulseReading:
    """Single pulse measurement."""
    timestamp_ms: float
    frame_number: int
    rgb_means: Tuple[float, float, float]
    ppg_value: float
    heart_rate_bpm: Optional[float]
    heart_rate_variability: Optional[float]
    spo2_estimate: Optional[float]
    signal_quality: float


class PulseOximetryService:
    """
    Remote photoplethysmography (rPPG) service.
    
    Extracts cardiovascular signals from facial video to verify
    that the subject is a living person with real blood flow.
    """
    
    # Signal processing parameters
    SAMPLE_RATE = 30  # fps
    WINDOW_SIZE_SECONDS = 10
    MIN_HR_BPM = 40
    MAX_HR_BPM = 180
    NORMAL_SPO2_RANGE = (95, 100)
    
    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize pulse oximetry service.
        
        Args:
            config: Configuration options
        """
        self.config = config or {}
        self.fps = self.config.get('fps', 30)
        self.window_size = int(self.fps * self.WINDOW_SIZE_SECONDS)
        
        # Signal buffers
        self.rgb_buffer: deque = deque(maxlen=self.window_size)
        self.ppg_buffer: deque = deque(maxlen=self.window_size)
        self.timestamps: deque = deque(maxlen=self.window_size)
        
        self.frame_count = 0
        self.current_hr: Optional[float] = None
        self.current_spo2: Optional[float] = None
        
        logger.info("PulseOximetryService initialized")
    
    def extract_roi(
        self, 
        frame: np.ndarray,
        face_landmarks: Optional[np.ndarray] = None
    ) -> Optional[np.ndarray]:
        """
        Extract region of interest (ROI) for pulse detection.
        
        Best ROI is forehead or cheeks - high blood vessel density.
        
        Args:
            frame: RGB video frame
            face_landmarks: Facial landmarks if available
            
        Returns:
            ROI image region or None
        """
        h, w = frame.shape[:2]
        
        if face_landmarks is not None and len(face_landmarks) > 100:
            # Use landmarks to find forehead region
            # MediaPipe indices for forehead area
            forehead_y = int(face_landmarks[10][1] * h)
            forehead_x = int(face_landmarks[10][0] * w)
            roi_size = int(h * 0.1)
            
            y1 = max(0, forehead_y - roi_size)
            y2 = forehead_y
            x1 = max(0, forehead_x - roi_size // 2)
            x2 = min(w, forehead_x + roi_size // 2)
        else:
            # Fallback: assume face in center, use upper region
            y1 = int(h * 0.2)
            y2 = int(h * 0.35)
            x1 = int(w * 0.3)
            x2 = int(w * 0.7)
        
        if y2 <= y1 or x2 <= x1:
            return None
        
        return frame[y1:y2, x1:x2]
    
    def process_frame(
        self, 
        frame: np.ndarray,
        timestamp_ms: float,
        face_landmarks: Optional[np.ndarray] = None
    ) -> Optional[PulseReading]:
        """
        Process a video frame and extract PPG signal.
        
        Args:
            frame: RGB video frame
            timestamp_ms: Frame timestamp
            face_landmarks: Optional facial landmarks
            
        Returns:
            Pulse reading or None
        """
        self.frame_count += 1
        
        # Extract ROI
        roi = self.extract_roi(frame, face_landmarks)
        if roi is None or roi.size == 0:
            return None
        
        # Calculate mean RGB values
        rgb_means = self._calculate_rgb_means(roi)
        self.rgb_buffer.append(rgb_means)
        self.timestamps.append(timestamp_ms)
        
        # Extract PPG signal component
        ppg_value = self._extract_ppg_value(rgb_means)
        self.ppg_buffer.append(ppg_value)
        
        # Need enough samples for analysis
        if len(self.ppg_buffer) < self.fps * 3:  # 3 seconds minimum
            return PulseReading(
                timestamp_ms=timestamp_ms,
                frame_number=self.frame_count,
                rgb_means=rgb_means,
                ppg_value=ppg_value,
                heart_rate_bpm=None,
                heart_rate_variability=None,
                spo2_estimate=None,
                signal_quality=0.0
            )
        
        # Calculate vital signs
        heart_rate, hrv, hr_quality = self._calculate_heart_rate()
        spo2, spo2_quality = self._estimate_spo2()
        
        signal_quality = (hr_quality + spo2_quality) / 2
        
        self.current_hr = heart_rate
        self.current_spo2 = spo2
        
        return PulseReading(
            timestamp_ms=timestamp_ms,
            frame_number=self.frame_count,
            rgb_means=rgb_means,
            ppg_value=ppg_value,
            heart_rate_bpm=heart_rate,
            heart_rate_variability=hrv,
            spo2_estimate=spo2,
            signal_quality=signal_quality
        )
    
    def _calculate_rgb_means(self, roi: np.ndarray) -> Tuple[float, float, float]:
        """Calculate mean RGB values from ROI."""
        means = np.mean(roi, axis=(0, 1))
        return (float(means[0]), float(means[1]), float(means[2]))
    
    def _extract_ppg_value(self, rgb_means: Tuple[float, float, float]) -> float:
        """
        Extract PPG signal value from RGB means.
        
        Green channel has strongest pulsatile signal due to
        hemoglobin absorption characteristics.
        """
        r, g, b = rgb_means
        
        # Chrominance-based extraction (CHROM method)
        # PPG ~ 3R - 2G (simplified)
        ppg = 3 * r - 2 * g
        
        return ppg
    
    def _calculate_heart_rate(self) -> Tuple[Optional[float], Optional[float], float]:
        """
        Calculate heart rate from PPG signal using FFT.
        
        Returns:
            (heart_rate_bpm, hrv, quality)
        """
        if len(self.ppg_buffer) < self.fps * 3:
            return None, None, 0.0
        
        signal = np.array(list(self.ppg_buffer))
        
        # Detrend and normalize
        signal = signal - np.mean(signal)
        
        # Apply bandpass filter (0.7-4 Hz for 40-240 BPM)
        signal = self._bandpass_filter(signal, 0.7, 4.0)
        
        if np.std(signal) < 0.001:
            return None, None, 0.0
        
        signal = signal / (np.std(signal) + 0.001)
        
        # FFT analysis
        fft = np.fft.fft(signal)
        freqs = np.fft.fftfreq(len(signal), 1.0 / self.fps)
        
        # Get positive frequencies in HR range
        pos_mask = (freqs >= 0.7) & (freqs <= 3.0)  # 42-180 BPM
        pos_freqs = freqs[pos_mask]
        pos_power = np.abs(fft[pos_mask])
        
        if len(pos_power) == 0:
            return None, None, 0.0
        
        # Find dominant frequency
        peak_idx = np.argmax(pos_power)
        peak_freq = pos_freqs[peak_idx]
        heart_rate = peak_freq * 60  # Convert Hz to BPM
        
        # Calculate signal quality from peak prominence
        peak_power = pos_power[peak_idx]
        avg_power = np.mean(pos_power)
        quality = min(1.0, peak_power / (avg_power * 3 + 0.001))
        
        # Estimate HRV from peak width
        hrv = self._estimate_hrv(signal)
        
        return heart_rate, hrv, quality
    
    def _bandpass_filter(
        self, 
        signal: np.ndarray, 
        low_hz: float, 
        high_hz: float
    ) -> np.ndarray:
        """Apply bandpass filter to signal."""
        try:
            from scipy.signal import butter, filtfilt
            
            nyquist = self.fps / 2
            low = low_hz / nyquist
            high = high_hz / nyquist
            
            if low >= high or high >= 1.0:
                return signal
            
            b, a = butter(2, [low, high], btype='band')
            return filtfilt(b, a, signal)
        except ImportError:
            # Fallback: simple moving average detrend
            window = int(self.fps / low_hz)
            if window > 1 and len(signal) > window:
                moving_avg = np.convolve(signal, np.ones(window)/window, mode='same')
                return signal - moving_avg
            return signal
    
    def _estimate_hrv(self, signal: np.ndarray) -> Optional[float]:
        """Estimate heart rate variability."""
        # Find peaks (R-peaks equivalent)
        peaks = self._find_peaks(signal)
        
        if len(peaks) < 3:
            return None
        
        # Calculate RR intervals
        rr_intervals = np.diff(peaks) / self.fps * 1000  # in ms
        
        # RMSSD (standard HRV metric)
        if len(rr_intervals) > 1:
            rr_diffs = np.diff(rr_intervals)
            rmssd = np.sqrt(np.mean(rr_diffs ** 2))
            return float(rmssd)
        
        return None
    
    def _find_peaks(self, signal: np.ndarray) -> np.ndarray:
        """Find peaks in signal."""
        peaks = []
        threshold = np.std(signal) * 0.5
        
        for i in range(1, len(signal) - 1):
            if (signal[i] > signal[i-1] and 
                signal[i] > signal[i+1] and 
                signal[i] > threshold):
                peaks.append(i)
        
        return np.array(peaks)
    
    def _estimate_spo2(self) -> Tuple[Optional[float], float]:
        """
        Estimate blood oxygen saturation (SpO2).
        
        Uses ratio of AC/DC components of red and infrared channels.
        With RGB camera, we approximate using R and B channels.
        
        Returns:
            (spo2_percentage, quality)
        """
        if len(self.rgb_buffer) < self.fps * 3:
            return None, 0.0
        
        rgb_data = np.array(list(self.rgb_buffer))
        
        red = rgb_data[:, 0]
        blue = rgb_data[:, 2]  # Blue approximates IR in some setups
        
        # Calculate AC (pulsatile) and DC (mean) components
        red_ac = np.std(red)
        red_dc = np.mean(red)
        blue_ac = np.std(blue)
        blue_dc = np.mean(blue)
        
        if red_dc < 1 or blue_dc < 1:
            return None, 0.0
        
        # Calculate ratio of ratios
        r = (red_ac / red_dc) / (blue_ac / blue_dc + 0.001)
        
        # Empirical SpO2 calibration curve
        # SpO2 = 110 - 25 * R (simplified, would be calibrated for production)
        spo2 = 110 - 25 * r
        spo2 = max(70, min(100, spo2))  # Clamp to reasonable range
        
        # Quality based on signal strength
        quality = min(1.0, (red_ac + blue_ac) / 10)
        
        return spo2, quality
    
    def validate_physiological_consistency(
        self,
        readings: List[PulseReading]
    ) -> Dict:
        """
        Validate that readings are physiologically consistent.
        
        Checks for:
        - Consistent heart rate
        - Normal SpO2 range
        - Natural variability
        - Absence of impossible patterns
        
        Returns:
            Validation results with scores
        """
        if not readings:
            return {
                'is_valid': False,
                'consistency_score': 0.0,
                'reason': 'No readings'
            }
        
        valid_readings = [r for r in readings if r.heart_rate_bpm is not None]
        
        if len(valid_readings) < 5:
            return {
                'is_valid': False,
                'consistency_score': 0.3,
                'reason': 'Insufficient valid readings'
            }
        
        # Check HR consistency
        hr_values = [r.heart_rate_bpm for r in valid_readings]
        hr_mean = np.mean(hr_values)
        hr_std = np.std(hr_values)
        
        # HR should be in normal range
        hr_range_score = 1.0 if self.MIN_HR_BPM <= hr_mean <= self.MAX_HR_BPM else 0.3
        
        # HR should have some natural variability but not too much
        hr_cv = hr_std / (hr_mean + 0.001)
        hr_variability_score = 1.0 if 0.02 <= hr_cv <= 0.15 else 0.5
        
        # Check SpO2
        spo2_values = [r.spo2_estimate for r in valid_readings if r.spo2_estimate]
        if spo2_values:
            spo2_mean = np.mean(spo2_values)
            spo2_score = 1.0 if self.NORMAL_SPO2_RANGE[0] <= spo2_mean <= self.NORMAL_SPO2_RANGE[1] else 0.3
        else:
            spo2_score = 0.5
        
        # Overall consistency
        consistency_score = (hr_range_score + hr_variability_score + spo2_score) / 3
        
        return {
            'is_valid': consistency_score > 0.6,
            'consistency_score': consistency_score,
            'average_hr': hr_mean,
            'hr_variability': hr_std,
            'average_spo2': np.mean(spo2_values) if spo2_values else None,
            'reason': None if consistency_score > 0.6 else 'Abnormal vital signs'
        }
    
    def get_liveness_score(self, readings: List[PulseReading]) -> float:
        """
        Calculate liveness score from pulse readings.
        
        Returns:
            Liveness score 0-1
        """
        validation = self.validate_physiological_consistency(readings)
        
        if not validation['is_valid']:
            return 0.3
        
        # Average signal quality
        qualities = [r.signal_quality for r in readings if r.signal_quality > 0]
        avg_quality = np.mean(qualities) if qualities else 0
        
        # Combined score
        score = (validation['consistency_score'] * 0.6 + avg_quality * 0.4)
        
        return min(1.0, max(0.0, score))
    
    def reset(self):
        """Reset buffers for new session."""
        self.rgb_buffer.clear()
        self.ppg_buffer.clear()
        self.timestamps.clear()
        self.frame_count = 0
        self.current_hr = None
        self.current_spo2 = None
