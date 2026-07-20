"""
Pulse Oximetry Service (rPPG)
==============================

Remote photoplethysmography (rPPG) for liveness detection.

Extracts a heart-rate pulse signal from facial video. A live face with real
blood flow produces a coherent pulse waveform; a static photo or screen replay
does not, so the presence and plausibility of the signal is used as a passive
presentation-attack signal (defense-in-depth, not an unbeatable guarantee).

SpO2 (blood oxygen) CANNOT be derived from a standard RGB webcam -- real SpO2
requires calibrated dual-wavelength (red + infrared) hardware. SpO2 is therefore
only populated when an external pulse-oximeter reading is ingested via
``ingest_hardware_spo2()``; otherwise it is absent and excluded from scoring.

Features:
- Extract PPG (pulse) signal from facial video
- Estimate heart rate and variability
- Accept SpO2 only from real external oximeter hardware
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

    # Hardware SpO2 is only emitted while fresh and of acceptable quality: a
    # stalled/disconnected oximeter must not keep contributing a stale reading.
    MAX_SPO2_AGE_MS = 5000
    MIN_SPO2_QUALITY = 0.3
    
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
        # SpO2 is only ever set from a real external pulse-oximeter reading
        # (see ingest_hardware_spo2). It is NEVER derived from webcam RGB.
        self.current_spo2: Optional[float] = None
        self.hardware_spo2: Optional[float] = None
        self.hardware_spo2_quality: float = 0.0
        self.hardware_spo2_timestamp_ms: Optional[float] = None

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
        
        # Need enough samples for the rPPG heart-rate analysis. SpO2 does NOT
        # depend on that buffer -- it comes from external oximeter hardware -- so
        # a fresh relayed reading still surfaces during the warm-up window.
        if len(self.ppg_buffer) < self.fps * 3:  # 3 seconds minimum
            return PulseReading(
                timestamp_ms=timestamp_ms,
                frame_number=self.frame_count,
                rgb_means=rgb_means,
                ppg_value=ppg_value,
                heart_rate_bpm=None,
                heart_rate_variability=None,
                spo2_estimate=self._current_hardware_spo2(timestamp_ms),
                signal_quality=0.0
            )
        
        # Calculate vital signs. Heart rate comes from the rPPG signal; SpO2 is
        # NOT derived from RGB -- it is only present if real oximeter hardware
        # has reported a reading (see ingest_hardware_spo2).
        heart_rate, hrv, hr_quality = self._calculate_heart_rate()
        spo2 = self._current_hardware_spo2(timestamp_ms)

        signal_quality = hr_quality

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
    
    def ingest_hardware_spo2(
        self,
        spo2_percent: Optional[float],
        quality: float = 1.0,
        timestamp_ms: Optional[float] = None,
    ) -> None:
        """
        Ingest a real SpO2 reading from an external pulse-oximeter device.

        This is the ONLY path by which SpO2 enters the pipeline. Real blood
        oxygen saturation requires calibrated dual-wavelength (red + infrared)
        hardware and cannot be recovered from a standard RGB webcam, so we never
        estimate it from video. Readings typically arrive over Bluetooth GATT
        (Pulse Oximeter Service 0x1822 / PLX) and are relayed by the client; that
        client relay path (WS message + BLE pairing UI) is wired in Phase 2.

        Args:
            spo2_percent: Measured oxygen saturation (0-100), or None to clear.
            quality: Device-reported signal quality/confidence in [0, 1].
            timestamp_ms: Reading timestamp; defaults to the latest frame time.
        """
        if spo2_percent is None:
            # Device disconnected / reading invalidated: clear so a stale value
            # is not copied into subsequent PulseReadings.
            self._clear_hardware_spo2()
            return
        # Resolve the sample timestamp against our frame clock (explicit value,
        # else the latest frame time).
        sample_timestamp_ms = (
            timestamp_ms if timestamp_ms is not None
            else (self.timestamps[-1] if self.timestamps else None)
        )
        # Reject malformed samples outright rather than clamping them into a
        # valid-looking value (e.g. 150 -> 100) or storing an unverifiable
        # timestamp: bogus or undatable SpO2 must never enter scoring.
        if not (
            np.isfinite(spo2_percent) and 0.0 <= spo2_percent <= 100.0
            and np.isfinite(quality) and 0.0 <= quality <= 1.0
            and sample_timestamp_ms is not None and np.isfinite(sample_timestamp_ms)
        ):
            self._clear_hardware_spo2()
            return
        self.hardware_spo2 = float(spo2_percent)
        self.hardware_spo2_quality = float(quality)
        self.hardware_spo2_timestamp_ms = float(sample_timestamp_ms)
        self.current_spo2 = self.hardware_spo2

    def has_hardware_spo2(self) -> bool:
        """True only when a real external oximeter reading has been ingested."""
        return self.hardware_spo2 is not None

    def _clear_hardware_spo2(self) -> None:
        """Drop any ingested hardware SpO2 reading and its metadata."""
        self.hardware_spo2 = None
        self.hardware_spo2_quality = 0.0
        self.hardware_spo2_timestamp_ms = None
        self.current_spo2 = None

    def _current_hardware_spo2(self, timestamp_ms: float) -> Optional[float]:
        """
        Return the ingested hardware SpO2 only while it is fresh and of
        acceptable quality; otherwise None, so a stalled/disconnected device does
        not keep contributing the same stale value to every new PulseReading.
        """
        if self.hardware_spo2 is None:
            return None
        if self.hardware_spo2_quality < self.MIN_SPO2_QUALITY:
            return None
        ts = self.hardware_spo2_timestamp_ms
        # No / non-finite timestamp => freshness cannot be verified. Fail safe.
        if ts is None or not np.isfinite(timestamp_ms):
            return None
        age_ms = timestamp_ms - ts
        # Reject stale (too old) and impossible (future-dated) readings.
        if age_ms < 0 or age_ms > self.MAX_SPO2_AGE_MS:
            return None
        return self.hardware_spo2
    
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
        
        # SpO2 only contributes when a real external oximeter reading is present
        # (see ingest_hardware_spo2). It is never derived from webcam RGB, so in
        # the webcam-only case it is excluded from the score rather than filled
        # with a neutral value that would silently inflate it.
        component_scores = [hr_range_score, hr_variability_score]
        spo2_values = [r.spo2_estimate for r in valid_readings if r.spo2_estimate is not None]
        if spo2_values:
            spo2_mean = np.mean(spo2_values)
            spo2_score = 1.0 if self.NORMAL_SPO2_RANGE[0] <= spo2_mean <= self.NORMAL_SPO2_RANGE[1] else 0.3
            component_scores.append(spo2_score)

        # Overall consistency (averaged over the components that actually applied)
        consistency_score = float(np.mean(component_scores))

        return {
            'is_valid': consistency_score > 0.6,
            'consistency_score': consistency_score,
            'average_hr': hr_mean,
            'hr_variability': hr_std,
            'average_spo2': float(np.mean(spo2_values)) if spo2_values else None,
            'spo2_source': 'hardware' if spo2_values else None,
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
        # Clear any ingested hardware SpO2 so a reading from a previous session
        # cannot leak into the next one (this service is reused via reset()).
        self._clear_hardware_spo2()
