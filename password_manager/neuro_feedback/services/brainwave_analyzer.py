"""
Brainwave Analyzer Service
==========================

Processes raw EEG data to extract meaningful brain state metrics:
- Alpha power (relaxed focus, 8-12 Hz)
- Theta power (memory encoding, 4-8 Hz)
- Gamma bursts (memory recall, 30-100 Hz)
- Focus index
- Memory readiness detection

@author Password Manager Team
@created 2026-02-07
"""

import logging
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class BrainState(Enum):
    """Detected brain state classifications."""
    UNFOCUSED = "unfocused"
    RELAXED = "relaxed"
    FOCUSED = "focused"
    MEMORY_READY = "memory_ready"
    ENCODING = "encoding"
    RECALL = "recall"
    FATIGUE = "fatigue"
    DISTRACTED = "distracted"


@dataclass
class BrainwaveMetrics:
    """Extracted brainwave metrics from EEG data."""
    timestamp: float
    
    # Power bands (normalized 0-1)
    delta_power: float = 0.0   # 0.5-4 Hz (deep sleep)
    theta_power: float = 0.0   # 4-8 Hz (memory, drowsiness)
    alpha_power: float = 0.0   # 8-12 Hz (relaxed awareness)
    beta_power: float = 0.0    # 12-30 Hz (active thinking)
    gamma_power: float = 0.0   # 30-100 Hz (high-level processing)
    
    # Derived metrics
    focus_index: float = 0.0        # 0-1
    relaxation_index: float = 0.0   # 0-1
    memory_readiness: float = 0.0   # 0-1
    
    # State classification
    brain_state: BrainState = BrainState.UNFOCUSED
    
    # Quality
    signal_quality: float = 1.0
    artifact_detected: bool = False


@dataclass
class MemoryWindow:
    """Optimal window for memory encoding detected."""
    start_time: float
    duration_seconds: float
    quality_score: float
    alpha_theta_ratio: float
    recommended_chunk_size: int = 8


class BrainwaveAnalyzer:
    """
    Real-time brainwave signal processing and analysis.
    
    Uses frequency band power analysis to detect optimal
    brain states for memory encoding and recall.
    """
    
    # Frequency band definitions (Hz)
    BANDS = {
        'delta': (0.5, 4),
        'theta': (4, 8),
        'alpha': (8, 12),
        'beta': (12, 30),
        'gamma': (30, 100),
    }
    
    # Sampling rate (Hz) - common for consumer EEG
    SAMPLE_RATE = 256
    
    # Analysis window size
    WINDOW_SIZE = 256  # 1 second at 256 Hz
    
    def __init__(self, baseline_alpha: float = 10.0, baseline_theta: float = 6.0):
        """
        Initialize analyzer with user's baseline values.
        
        Args:
            baseline_alpha: User's baseline alpha frequency
            baseline_theta: User's baseline theta frequency
        """
        self.baseline_alpha = baseline_alpha
        self.baseline_theta = baseline_theta
        
        # Rolling buffers for temporal analysis
        self._alpha_history: List[float] = []
        self._theta_history: List[float] = []
        self._focus_history: List[float] = []
        
        self._history_length = 30  # Keep 30 seconds of history
    
    # =========================================================================
    # Core Analysis
    # =========================================================================
    
    def analyze(self, eeg_data: np.ndarray) -> BrainwaveMetrics:
        """
        Analyze a window of EEG data.
        
        Args:
            eeg_data: Raw EEG samples (shape: channels x samples)
            
        Returns:
            BrainwaveMetrics with extracted features
        """
        import time
        timestamp = time.time()
        
        # Check data quality
        artifact_detected = self._detect_artifacts(eeg_data)
        signal_quality = self._calculate_signal_quality(eeg_data)
        
        if artifact_detected or signal_quality < 0.5:
            return BrainwaveMetrics(
                timestamp=timestamp,
                signal_quality=signal_quality,
                artifact_detected=artifact_detected,
                brain_state=BrainState.DISTRACTED,
            )
        
        # Extract frequency band powers
        band_powers = self._compute_band_powers(eeg_data)
        
        # Calculate derived metrics
        focus_index = self._calculate_focus_index(band_powers)
        relaxation_index = self._calculate_relaxation_index(band_powers)
        memory_readiness = self._calculate_memory_readiness(band_powers)
        
        # Update history
        self._update_history(band_powers, focus_index)
        
        # Classify brain state
        brain_state = self._classify_state(band_powers, focus_index, memory_readiness)
        
        return BrainwaveMetrics(
            timestamp=timestamp,
            delta_power=band_powers['delta'],
            theta_power=band_powers['theta'],
            alpha_power=band_powers['alpha'],
            beta_power=band_powers['beta'],
            gamma_power=band_powers['gamma'],
            focus_index=focus_index,
            relaxation_index=relaxation_index,
            memory_readiness=memory_readiness,
            brain_state=brain_state,
            signal_quality=signal_quality,
            artifact_detected=artifact_detected,
        )
    
    def _compute_band_powers(self, eeg_data: np.ndarray) -> Dict[str, float]:
        """
        Compute power in each frequency band using FFT.
        """
        # Average across channels if multi-channel
        if eeg_data.ndim > 1:
            signal = np.mean(eeg_data, axis=0)
        else:
            signal = eeg_data
        
        # Apply Hanning window
        windowed = signal * np.hanning(len(signal))
        
        # Compute FFT
        fft = np.fft.rfft(windowed)
        power_spectrum = np.abs(fft) ** 2
        freqs = np.fft.rfftfreq(len(signal), 1 / self.SAMPLE_RATE)
        
        # Extract band powers
        band_powers = {}
        total_power = np.sum(power_spectrum)
        
        for band_name, (low_freq, high_freq) in self.BANDS.items():
            mask = (freqs >= low_freq) & (freqs < high_freq)
            band_power = np.sum(power_spectrum[mask])
            # Normalize by total power
            band_powers[band_name] = band_power / total_power if total_power > 0 else 0.0
        
        return band_powers
    
    # =========================================================================
    # Derived Metrics
    # =========================================================================
    
    def _calculate_focus_index(self, band_powers: Dict[str, float]) -> float:
        """
        Calculate focus index based on beta/theta ratio.
        
        Higher beta relative to theta indicates focused attention.
        """
        theta = band_powers.get('theta', 0.001)
        beta = band_powers.get('beta', 0)
        
        # Beta/theta ratio, normalized to 0-1
        ratio = beta / max(theta, 0.001)
        focus = min(ratio / 3.0, 1.0)  # Normalize, cap at 1
        
        return focus
    
    def _calculate_relaxation_index(self, band_powers: Dict[str, float]) -> float:
        """
        Calculate relaxation index based on alpha power.
        
        Higher alpha indicates relaxed but alert state.
        """
        alpha = band_powers.get('alpha', 0)
        beta = band_powers.get('beta', 0.001)
        
        # Alpha dominance indicates relaxation
        ratio = alpha / max(beta, 0.001)
        relaxation = min(ratio / 2.0, 1.0)
        
        return relaxation
    
    def _calculate_memory_readiness(self, band_powers: Dict[str, float]) -> float:
        """
        Calculate optimal memory encoding readiness.
        
        Based on research showing theta-alpha interaction during memory encoding.
        The ideal state has:
        - Moderate theta activity (hippocampal memory processing)
        - Strong alpha (cortical readiness)
        - Low beta (reduced analytical interference)
        """
        alpha = band_powers.get('alpha', 0)
        theta = band_powers.get('theta', 0)
        beta = band_powers.get('beta', 0.001)
        
        # Optimal alpha-theta combination
        at_product = alpha * theta * 4  # Scale up the product
        
        # Penalize high beta (overthinking)
        beta_penalty = max(0, 1 - beta * 2)
        
        readiness = min(at_product * beta_penalty, 1.0)
        
        return readiness
    
    # =========================================================================
    # State Classification
    # =========================================================================
    
    def _classify_state(
        self,
        band_powers: Dict[str, float],
        focus_index: float,
        memory_readiness: float
    ) -> BrainState:
        """Classify current brain state from metrics."""
        
        alpha = band_powers.get('alpha', 0)
        theta = band_powers.get('theta', 0)
        gamma = band_powers.get('gamma', 0)
        delta = band_powers.get('delta', 0)
        
        # Check for fatigue (high delta/theta)
        if delta > 0.4 or (theta > 0.4 and focus_index < 0.2):
            return BrainState.FATIGUE
        
        # Memory encoding state (high theta + moderate alpha)
        if memory_readiness > 0.7:
            return BrainState.MEMORY_READY
        
        # Active recall (gamma bursts)
        if gamma > 0.15 and theta > 0.2:
            return BrainState.RECALL
        
        # Encoding in progress
        if theta > 0.3 and alpha > 0.2:
            return BrainState.ENCODING
        
        # Focused state
        if focus_index > 0.6:
            return BrainState.FOCUSED
        
        # Relaxed state
        if alpha > 0.3 and focus_index < 0.4:
            return BrainState.RELAXED
        
        return BrainState.UNFOCUSED
    
    # =========================================================================
    # Signal Quality
    # =========================================================================
    
    def _detect_artifacts(self, eeg_data: np.ndarray) -> bool:
        """
        Detect motion artifacts, eye blinks, muscle activity.
        """
        if eeg_data.ndim > 1:
            signal = np.mean(eeg_data, axis=0)
        else:
            signal = eeg_data
        
        # Check for amplitude spikes (likely artifacts)
        max_amplitude = np.max(np.abs(signal))
        if max_amplitude > 150:  # microvolts threshold
            return True
        
        # Check for sudden changes (motion artifacts)
        diff = np.diff(signal)
        max_diff = np.max(np.abs(diff))
        if max_diff > 50:
            return True
        
        return False
    
    def _calculate_signal_quality(self, eeg_data: np.ndarray) -> float:
        """Calculate overall signal quality score (0-1)."""
        if eeg_data.ndim > 1:
            signal = np.mean(eeg_data, axis=0)
        else:
            signal = eeg_data
        
        # Check variance (too low = poor contact, too high = noise)
        variance = np.var(signal)
        variance_score = 1.0 if 10 < variance < 500 else 0.5
        
        # Check for flat signal (electrode issue)
        if variance < 1:
            return 0.1
        
        # Check frequency content
        fft = np.fft.rfft(signal)
        power = np.abs(fft) ** 2
        
        # Good EEG should have most power in 1-40 Hz range
        freqs = np.fft.rfftfreq(len(signal), 1 / self.SAMPLE_RATE)
        mask = (freqs >= 1) & (freqs <= 40)
        relevant_power = np.sum(power[mask])
        total_power = np.sum(power)
        
        frequency_score = relevant_power / total_power if total_power > 0 else 0
        
        return (variance_score + frequency_score) / 2
    
    # =========================================================================
    # History & Trends
    # =========================================================================
    
    def _update_history(self, band_powers: Dict[str, float], focus_index: float):
        """Update rolling history buffers."""
        self._alpha_history.append(band_powers.get('alpha', 0))
        self._theta_history.append(band_powers.get('theta', 0))
        self._focus_history.append(focus_index)
        
        # Trim to max length
        if len(self._alpha_history) > self._history_length:
            self._alpha_history = self._alpha_history[-self._history_length:]
            self._theta_history = self._theta_history[-self._history_length:]
            self._focus_history = self._focus_history[-self._history_length:]
    
    def detect_memory_window(self) -> Optional[MemoryWindow]:
        """
        Detect if we're in an optimal memory encoding window.
        
        Returns MemoryWindow if optimal conditions detected.
        """
        if len(self._alpha_history) < 5:
            return None
        
        # Calculate recent averages
        recent_alpha = np.mean(self._alpha_history[-5:])
        recent_theta = np.mean(self._theta_history[-5:])
        recent_focus = np.mean(self._focus_history[-5:])
        
        # Check for optimal conditions
        alpha_theta_ratio = recent_alpha / max(recent_theta, 0.001)
        
        # Good memory encoding: balanced alpha-theta, moderate focus
        if 0.8 < alpha_theta_ratio < 2.0 and recent_focus > 0.4:
            quality = (recent_alpha + recent_theta) / 2 * recent_focus
            
            return MemoryWindow(
                start_time=0,  # Would use actual timestamp
                duration_seconds=5,
                quality_score=min(quality * 2, 1.0),
                alpha_theta_ratio=alpha_theta_ratio,
                recommended_chunk_size=8 if quality > 0.5 else 4,
            )
        
        return None
    
    def get_trend(self, metric: str, window_seconds: int = 10) -> str:
        """Get trend direction for a metric (improving, stable, declining)."""
        history = {
            'alpha': self._alpha_history,
            'theta': self._theta_history,
            'focus': self._focus_history,
        }.get(metric, [])
        
        if len(history) < window_seconds:
            return 'stable'
        
        recent = history[-window_seconds:]
        first_half = np.mean(recent[:len(recent)//2])
        second_half = np.mean(recent[len(recent)//2:])
        
        diff = second_half - first_half
        
        if diff > 0.05:
            return 'improving'
        elif diff < -0.05:
            return 'declining'
        else:
            return 'stable'
