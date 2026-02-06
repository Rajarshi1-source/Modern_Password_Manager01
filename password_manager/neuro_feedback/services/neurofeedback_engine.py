"""
Neurofeedback Engine
====================

Real-time feedback generation based on brain state:
- Audio feedback (binaural beats, reward tones)
- Visual feedback (color changes, animations)
- Haptic feedback patterns
- Adaptive difficulty adjustment

@author Password Manager Team
@created 2026-02-07
"""

import logging
import json
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum

from .brainwave_analyzer import BrainwaveMetrics, BrainState

logger = logging.getLogger(__name__)


class FeedbackType(Enum):
    """Types of neurofeedback."""
    VISUAL = "visual"
    AUDIO = "audio"
    HAPTIC = "haptic"
    COMBINED = "combined"


class FeedbackIntensity(Enum):
    """Feedback intensity levels."""
    SUBTLE = "subtle"
    MODERATE = "moderate"
    STRONG = "strong"


@dataclass
class VisualFeedback:
    """Visual feedback parameters."""
    color: str  # Hex color
    brightness: float  # 0-1
    pulse_rate: float  # Hz, 0 for static
    animation: str  # 'glow', 'pulse', 'wave', 'none'
    border_width: int  # pixels
    message: str


@dataclass
class AudioFeedback:
    """Audio feedback parameters."""
    tone_frequency: float  # Hz
    volume: float  # 0-1
    duration_ms: int
    binaural_enabled: bool
    binaural_frequency: float  # Hz (difference between left/right)
    sound_type: str  # 'tone', 'chime', 'nature', 'binaural'


@dataclass
class HapticFeedback:
    """Haptic feedback parameters (for mobile)."""
    pattern: str  # 'single', 'double', 'triple', 'long', 'rhythm'
    intensity: float  # 0-1
    duration_ms: int


@dataclass
class NeurofeedbackSignal:
    """Complete neurofeedback signal package."""
    timestamp: float
    brain_state: str
    memory_readiness: float
    
    visual: Optional[VisualFeedback] = None
    audio: Optional[AudioFeedback] = None
    haptic: Optional[HapticFeedback] = None
    
    # Training guidance
    show_content: bool = False
    message: str = ""
    encouragement: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for WebSocket transmission."""
        return {
            'timestamp': self.timestamp,
            'brain_state': self.brain_state,
            'memory_readiness': self.memory_readiness,
            'visual': {
                'color': self.visual.color,
                'brightness': self.visual.brightness,
                'pulse_rate': self.visual.pulse_rate,
                'animation': self.visual.animation,
                'border_width': self.visual.border_width,
                'message': self.visual.message,
            } if self.visual else None,
            'audio': {
                'tone_frequency': self.audio.tone_frequency,
                'volume': self.audio.volume,
                'duration_ms': self.audio.duration_ms,
                'binaural_enabled': self.audio.binaural_enabled,
                'binaural_frequency': self.audio.binaural_frequency,
                'sound_type': self.audio.sound_type,
            } if self.audio else None,
            'haptic': {
                'pattern': self.haptic.pattern,
                'intensity': self.haptic.intensity,
                'duration_ms': self.haptic.duration_ms,
            } if self.haptic else None,
            'show_content': self.show_content,
            'message': self.message,
            'encouragement': self.encouragement,
        }


class NeurofeedbackEngine:
    """
    Generates real-time neurofeedback based on brain state.
    
    Uses biofeedback principles to:
    - Reward optimal brain states for memory encoding
    - Guide users toward focused, relaxed attention
    - Provide immediate feedback on brain state changes
    """
    
    # Color scheme for brain states
    STATE_COLORS = {
        BrainState.UNFOCUSED: '#808080',     # Gray
        BrainState.RELAXED: '#4A90D9',       # Blue
        BrainState.FOCUSED: '#50C878',       # Green
        BrainState.MEMORY_READY: '#FFD700',  # Gold
        BrainState.ENCODING: '#FF8C00',      # Orange
        BrainState.RECALL: '#9370DB',        # Purple
        BrainState.FATIGUE: '#CD5C5C',       # Red
        BrainState.DISTRACTED: '#A9A9A9',    # Dark gray
    }
    
    # Audio tones for different states
    STATE_TONES = {
        BrainState.MEMORY_READY: 440.0,  # A4 - reward tone
        BrainState.FOCUSED: 523.25,      # C5 - positive
        BrainState.ENCODING: 392.0,      # G4 - active
        BrainState.RECALL: 659.25,       # E5 - success
    }
    
    # Binaural beat frequencies for brain entrainment
    BINAURAL_FREQUENCIES = {
        'alpha': 10.0,   # 10 Hz - relaxed focus
        'theta': 6.0,    # 6 Hz - memory encoding
        'beta': 18.0,    # 18 Hz - active concentration
    }
    
    def __init__(
        self,
        feedback_mode: str = 'combined',
        audio_volume: float = 0.7,
        haptic_intensity: float = 0.5,
        alpha_threshold: float = 0.6,
        binaural_enabled: bool = True
    ):
        """
        Initialize the neurofeedback engine.
        
        Args:
            feedback_mode: 'visual', 'audio', 'haptic', or 'combined'
            audio_volume: Base audio volume (0-1)
            haptic_intensity: Base haptic intensity (0-1)
            alpha_threshold: Alpha power threshold for memory-ready state
            binaural_enabled: Whether to use binaural beats
        """
        self.feedback_mode = feedback_mode
        self.audio_volume = audio_volume
        self.haptic_intensity = haptic_intensity
        self.alpha_threshold = alpha_threshold
        self.binaural_enabled = binaural_enabled
        
        # Track state for detecting transitions
        self._previous_state: Optional[BrainState] = None
        self._optimal_state_start: Optional[float] = None
        self._optimal_duration: float = 0.0
    
    # =========================================================================
    # Main Feedback Generation
    # =========================================================================
    
    def generate_feedback(
        self,
        metrics: BrainwaveMetrics,
        training_active: bool = True
    ) -> NeurofeedbackSignal:
        """
        Generate neurofeedback signal based on current brain metrics.
        
        Args:
            metrics: Current brainwave metrics
            training_active: Whether user is in active training
            
        Returns:
            NeurofeedbackSignal with all feedback components
        """
        import time
        
        state = metrics.brain_state
        is_optimal = state in [BrainState.MEMORY_READY, BrainState.FOCUSED, BrainState.ENCODING]
        
        # Track optimal state duration
        if is_optimal:
            if self._optimal_state_start is None:
                self._optimal_state_start = time.time()
            self._optimal_duration = time.time() - self._optimal_state_start
        else:
            self._optimal_state_start = None
            self._optimal_duration = 0.0
        
        # Detect state transition
        state_changed = state != self._previous_state
        self._previous_state = state
        
        # Generate feedback components
        visual = self._generate_visual_feedback(metrics, state_changed) if self.feedback_mode in ['visual', 'combined'] else None
        audio = self._generate_audio_feedback(metrics, state_changed) if self.feedback_mode in ['audio', 'combined'] else None
        haptic = self._generate_haptic_feedback(metrics, state_changed) if self.feedback_mode in ['haptic', 'combined'] else None
        
        # Determine if content should be shown
        show_content = is_optimal and self._optimal_duration >= 2.0  # 2 seconds in optimal state
        
        # Generate messages
        message = self._get_state_message(state, metrics)
        encouragement = self._get_encouragement(metrics, self._optimal_duration)
        
        return NeurofeedbackSignal(
            timestamp=metrics.timestamp,
            brain_state=state.value,
            memory_readiness=metrics.memory_readiness,
            visual=visual,
            audio=audio,
            haptic=haptic,
            show_content=show_content,
            message=message,
            encouragement=encouragement,
        )
    
    # =========================================================================
    # Visual Feedback
    # =========================================================================
    
    def _generate_visual_feedback(
        self,
        metrics: BrainwaveMetrics,
        state_changed: bool
    ) -> VisualFeedback:
        """Generate visual feedback based on brain state."""
        state = metrics.brain_state
        color = self.STATE_COLORS.get(state, '#808080')
        
        # Brightness based on signal quality and memory readiness
        brightness = 0.5 + (metrics.memory_readiness * 0.5)
        
        # Pulse rate based on focus level
        pulse_rate = 0.0
        if state == BrainState.MEMORY_READY:
            pulse_rate = 1.0  # Gentle pulse when ready
        elif state == BrainState.ENCODING:
            pulse_rate = 0.5
        
        # Animation type
        if state == BrainState.MEMORY_READY:
            animation = 'glow'
        elif state_changed:
            animation = 'pulse'
        else:
            animation = 'none'
        
        # Border width increases with memory readiness
        border_width = int(2 + metrics.memory_readiness * 6)
        
        # State-specific message
        message = self._get_visual_message(state)
        
        return VisualFeedback(
            color=color,
            brightness=brightness,
            pulse_rate=pulse_rate,
            animation=animation,
            border_width=border_width,
            message=message,
        )
    
    def _get_visual_message(self, state: BrainState) -> str:
        """Get visual indicator message for state."""
        messages = {
            BrainState.UNFOCUSED: "🔘",
            BrainState.RELAXED: "🔵",
            BrainState.FOCUSED: "🟢",
            BrainState.MEMORY_READY: "⭐",
            BrainState.ENCODING: "🧠",
            BrainState.RECALL: "💫",
            BrainState.FATIGUE: "😴",
            BrainState.DISTRACTED: "👀",
        }
        return messages.get(state, "")
    
    # =========================================================================
    # Audio Feedback
    # =========================================================================
    
    def _generate_audio_feedback(
        self,
        metrics: BrainwaveMetrics,
        state_changed: bool
    ) -> AudioFeedback:
        """Generate audio feedback including binaural beats."""
        state = metrics.brain_state
        
        # Base tone for state transitions
        tone_frequency = self.STATE_TONES.get(state, 0)
        
        # Volume based on readiness (quieter when not ready)
        volume = self.audio_volume * (0.3 + metrics.memory_readiness * 0.7)
        
        # Play tone only on positive state changes
        duration_ms = 0
        if state_changed and state in [BrainState.MEMORY_READY, BrainState.FOCUSED]:
            duration_ms = 200  # Short confirmation tone
        
        # Binaural beats for brain entrainment
        binaural_enabled = self.binaural_enabled
        binaural_frequency = self.BINAURAL_FREQUENCIES['alpha']  # Default to alpha
        
        if state == BrainState.ENCODING:
            binaural_frequency = self.BINAURAL_FREQUENCIES['theta']
        elif state == BrainState.FOCUSED:
            binaural_frequency = self.BINAURAL_FREQUENCIES['beta']
        
        # Sound type
        if duration_ms > 0:
            sound_type = 'chime'
        elif binaural_enabled:
            sound_type = 'binaural'
        else:
            sound_type = 'none'
        
        return AudioFeedback(
            tone_frequency=tone_frequency,
            volume=volume,
            duration_ms=duration_ms,
            binaural_enabled=binaural_enabled,
            binaural_frequency=binaural_frequency,
            sound_type=sound_type,
        )
    
    # =========================================================================
    # Haptic Feedback
    # =========================================================================
    
    def _generate_haptic_feedback(
        self,
        metrics: BrainwaveMetrics,
        state_changed: bool
    ) -> HapticFeedback:
        """Generate haptic feedback for mobile devices."""
        state = metrics.brain_state
        
        # Pattern based on state
        pattern = 'none'
        intensity = 0.0
        duration_ms = 0
        
        if state_changed:
            if state == BrainState.MEMORY_READY:
                pattern = 'double'
                intensity = self.haptic_intensity
                duration_ms = 100
            elif state == BrainState.FOCUSED:
                pattern = 'single'
                intensity = self.haptic_intensity * 0.7
                duration_ms = 50
            elif state == BrainState.RECALL:
                pattern = 'triple'
                intensity = self.haptic_intensity
                duration_ms = 150
            elif state == BrainState.DISTRACTED:
                pattern = 'long'
                intensity = self.haptic_intensity * 0.5
                duration_ms = 200
        
        return HapticFeedback(
            pattern=pattern,
            intensity=intensity,
            duration_ms=duration_ms,
        )
    
    # =========================================================================
    # Messages & Encouragement
    # =========================================================================
    
    def _get_state_message(self, state: BrainState, metrics: BrainwaveMetrics) -> str:
        """Get guidance message for current state."""
        messages = {
            BrainState.UNFOCUSED: "Take a deep breath and focus your attention",
            BrainState.RELAXED: "Good relaxation. Now gently focus on the task",
            BrainState.FOCUSED: "Great focus! Memory encoding will improve",
            BrainState.MEMORY_READY: "Perfect state! Your brain is ready to learn",
            BrainState.ENCODING: "Excellent! Memory is being encoded",
            BrainState.RECALL: "Accessing memory...",
            BrainState.FATIGUE: "You're getting tired. Consider a short break",
            BrainState.DISTRACTED: "Mind wandering detected. Refocus gently",
        }
        return messages.get(state, "")
    
    def _get_encouragement(self, metrics: BrainwaveMetrics, optimal_duration: float) -> str:
        """Get encouraging message based on performance."""
        if optimal_duration > 30:
            return "🏆 Amazing! 30+ seconds in optimal state!"
        elif optimal_duration > 15:
            return "🌟 Great job! Keep this focus!"
        elif optimal_duration > 5:
            return "✨ You're doing well!"
        elif metrics.memory_readiness > 0.7:
            return "💪 Almost there!"
        else:
            return ""
    
    # =========================================================================
    # Reward System
    # =========================================================================
    
    def generate_reward_signal(self, success: bool, quality: int) -> NeurofeedbackSignal:
        """
        Generate immediate reward feedback after successful recall.
        
        Args:
            success: Whether recall was successful
            quality: Quality rating 0-5
        """
        import time
        
        if success:
            color = '#FFD700' if quality >= 4 else '#50C878'
            tone = 523.25 if quality >= 4 else 440.0  # C5 or A4
            pattern = 'triple' if quality >= 4 else 'double'
            message = "🎉 Perfect!" if quality == 5 else "✅ Correct!"
        else:
            color = '#FFA500'  # Orange
            tone = 349.23  # F4
            pattern = 'single'
            message = "Try again!"
        
        return NeurofeedbackSignal(
            timestamp=time.time(),
            brain_state='reward',
            memory_readiness=1.0 if success else 0.0,
            visual=VisualFeedback(
                color=color,
                brightness=1.0,
                pulse_rate=2.0,
                animation='pulse',
                border_width=8,
                message=message,
            ),
            audio=AudioFeedback(
                tone_frequency=tone,
                volume=self.audio_volume,
                duration_ms=300,
                binaural_enabled=False,
                binaural_frequency=0,
                sound_type='chime',
            ),
            haptic=HapticFeedback(
                pattern=pattern,
                intensity=self.haptic_intensity,
                duration_ms=150,
            ),
            show_content=False,
            message=message,
            encouragement="Memory strengthened!" if success else "Let's practice more.",
        )
