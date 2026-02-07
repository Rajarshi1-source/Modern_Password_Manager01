"""
rPPG Extractor
===============

Remote Photoplethysmography signal extraction for liveness detection.
Extracts blood volume pulse from video to verify living tissue.
"""

import logging
from typing import Dict, List, Optional, Tuple
import numpy as np
from collections import deque

logger = logging.getLogger(__name__)


class RPPGExtractor:
    """
    Remote PPG signal extractor.
    
    Extracts cardiovascular signals from facial video using
    chrominance-based method (CHROM). Detects blood volume changes
    that cannot be faked by photos, videos, or deepfakes.
    """
    
    # Processing parameters
    DEFAULT_FPS = 30
    WINDOW_SIZE_SECONDS = 10
    HR_MIN_BPM = 40
    HR_MAX_BPM = 180
    
    def __init__(self, fps: int = 30, window_size: int = 300):
        """
        Initialize rPPG extractor.
        
        Args:
            fps: Video frame rate
            window_size: Number of frames in sliding window
        """
        self.fps = fps
        self.window_size = window_size
        
        # Signal buffers
        self.rgb_buffer = deque(maxlen=window_size)
        self.ppg_buffer = deque(maxlen=window_size)
        self.timestamps = deque(maxlen=window_size)
        
        self.frame_count = 0
        
        logger.info(f"RPPGExtractor initialized (fps={fps})")
    
    def process_frame(
        self, 
        frame: np.ndarray, 
        roi_mask: Optional[np.ndarray] = None,
        timestamp: Optional[float] = None
    ) -> Optional[Dict]:
        """
        Process single video frame.
        
        Args:
            frame: RGB video frame
            roi_mask: Optional ROI mask for face region
            timestamp: Frame timestamp in ms
            
        Returns:
            Dict with ppg_value, heart_rate, spo2 if available
        """
        self.frame_count += 1
        
        if timestamp is None:
            timestamp = self.frame_count * (1000 / self.fps)
        
        # Extract ROI
        if roi_mask is not None:
            roi = frame[roi_mask > 0]
        else:
            # Use forehead region (top 1/3 of face area)
            h, w = frame.shape[:2]
            roi = frame[int(h*0.1):int(h*0.35), int(w*0.25):int(w*0.75)]
        
        if roi.size == 0:
            return None
        
        # Calculate mean RGB
        rgb_mean = np.mean(roi.reshape(-1, 3), axis=0)
        self.rgb_buffer.append(rgb_mean)
        self.timestamps.append(timestamp)
        
        # Extract PPG using CHROM method
        ppg = self._chrom_ppg(rgb_mean)
        self.ppg_buffer.append(ppg)
        
        result = {
            'ppg_value': float(ppg),
            'rgb_mean': tuple(rgb_mean.tolist()),
            'frame_number': self.frame_count,
            'timestamp_ms': timestamp,
        }
        
        # Calculate heart rate if enough samples
        if len(self.ppg_buffer) >= self.fps * 3:
            hr, hr_confidence = self._calculate_heart_rate()
            result['heart_rate_bpm'] = hr
            result['hr_confidence'] = hr_confidence
            
            # Calculate SpO2
            spo2, spo2_confidence = self._calculate_spo2()
            result['spo2'] = spo2
            result['spo2_confidence'] = spo2_confidence
        
        return result
    
    def _chrom_ppg(self, rgb: np.ndarray) -> float:
        """
        Extract PPG signal using chrominance method.
        
        The green channel has the strongest pulsatile signal
        due to hemoglobin absorption characteristics.
        """
        r, g, b = rgb
        
        # CHROM: Chrominance-based method
        # X = 3R - 2G, Y = 1.5R + G - 1.5B
        x = 3 * r - 2 * g
        y = 1.5 * r + g - 1.5 * b
        
        # Combine for final PPG signal
        ppg = x - y
        
        return ppg
    
    def _calculate_heart_rate(self) -> Tuple[Optional[float], float]:
        """Calculate heart rate from PPG signal."""
        signal = np.array(list(self.ppg_buffer))
        
        if len(signal) < self.fps * 2:
            return None, 0.0
        
        # Detrend
        signal = signal - np.mean(signal)
        
        # Band-pass filter (0.7-4 Hz = 42-240 BPM)
        signal = self._bandpass_filter(signal, 0.7, 4.0)
        
        if np.std(signal) < 0.001:
            return None, 0.0
        
        # Normalize
        signal = signal / np.std(signal)
        
        # FFT
        fft = np.fft.fft(signal)
        freqs = np.fft.fftfreq(len(signal), 1.0 / self.fps)
        
        # Find peaks in HR range
        hr_mask = (freqs >= 0.7) & (freqs <= 3.0)  # 42-180 BPM
        hr_freqs = freqs[hr_mask]
        hr_power = np.abs(fft[hr_mask])
        
        if len(hr_power) == 0:
            return None, 0.0
        
        # Find dominant frequency
        peak_idx = np.argmax(hr_power)
        peak_freq = hr_freqs[peak_idx]
        heart_rate = abs(peak_freq * 60)
        
        # Calculate confidence from peak prominence
        peak_power = hr_power[peak_idx]
        avg_power = np.mean(hr_power)
        confidence = min(1.0, peak_power / (avg_power * 3 + 0.001))
        
        # Validate HR range
        if not (self.HR_MIN_BPM <= heart_rate <= self.HR_MAX_BPM):
            return None, 0.0
        
        return float(heart_rate), float(confidence)
    
    def _calculate_spo2(self) -> Tuple[Optional[float], float]:
        """
        Estimate blood oxygen saturation (SpO2).
        
        Uses ratio of AC/DC components of red and infrared signals.
        With RGB camera, blue approximates IR behavior.
        """
        if len(self.rgb_buffer) < self.fps * 3:
            return None, 0.0
        
        rgb_data = np.array(list(self.rgb_buffer))
        red = rgb_data[:, 0]
        blue = rgb_data[:, 2]  # Approximate IR
        
        # AC (pulsatile) and DC (mean) components
        red_ac = np.std(red)
        red_dc = np.mean(red)
        blue_ac = np.std(blue)
        blue_dc = np.mean(blue)
        
        if red_dc < 1 or blue_dc < 1:
            return None, 0.0
        
        # Ratio of ratios
        r = (red_ac / red_dc) / (blue_ac / blue_dc + 0.001)
        
        # Empirical SpO2 curve (simplified)
        spo2 = 110 - 25 * r
        spo2 = max(70, min(100, spo2))
        
        # Confidence from signal quality
        confidence = min(1.0, (red_ac + blue_ac) / 10)
        
        return float(spo2), float(confidence)
    
    def _bandpass_filter(
        self, 
        signal: np.ndarray, 
        low_hz: float, 
        high_hz: float
    ) -> np.ndarray:
        """Apply bandpass filter."""
        try:
            from scipy.signal import butter, filtfilt
            
            nyquist = self.fps / 2
            low = low_hz / nyquist
            high = min(high_hz / nyquist, 0.99)
            
            if low >= high:
                return signal
            
            b, a = butter(2, [low, high], btype='band')
            return filtfilt(b, a, signal)
        except:
            # Fallback: simple detrending
            if len(signal) > 10:
                trend = np.convolve(signal, np.ones(10)/10, mode='same')
                return signal - trend
            return signal
    
    def get_signal_quality(self) -> float:
        """Get current signal quality estimate."""
        if len(self.ppg_buffer) < self.fps:
            return 0.0
        
        signal = np.array(list(self.ppg_buffer))
        
        # Check for variation
        if np.std(signal) < 0.1:
            return 0.0
        
        # Check for reasonable periodicity
        hr, confidence = self._calculate_heart_rate()
        
        return confidence if confidence else 0.3
    
    def reset(self):
        """Reset all buffers."""
        self.rgb_buffer.clear()
        self.ppg_buffer.clear()
        self.timestamps.clear()
        self.frame_count = 0
    
    def get_ppg_waveform(self) -> np.ndarray:
        """Get current PPG waveform."""
        return np.array(list(self.ppg_buffer))
    
    def is_living_tissue(self, min_confidence: float = 0.6) -> Tuple[bool, float]:
        """
        Determine if signal indicates living tissue.
        
        Returns:
            (is_living, confidence)
        """
        quality = self.get_signal_quality()
        
        if quality < min_confidence:
            return False, quality
        
        hr, hr_conf = self._calculate_heart_rate()
        spo2, spo2_conf = self._calculate_spo2()
        
        # Living tissue should have:
        # 1. Detectable heart rate in normal range
        # 2. SpO2 in normal range
        # 3. Sufficient signal quality
        
        is_living = (
            hr is not None and
            40 <= hr <= 180 and
            hr_conf > 0.4 and
            (spo2 is None or 90 <= spo2 <= 100)
        )
        
        confidence = (quality + hr_conf) / 2 if hr else quality
        
        return is_living, confidence
