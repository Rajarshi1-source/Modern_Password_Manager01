"""
Neuro-Feedback Password Training Models
========================================

Django models for EEG-based password memory training:
- EEG device management
- Training session tracking
- Memory strength scoring
- Spaced repetition scheduling

@author Password Manager Team
@created 2026-02-07
"""

import uuid
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone


# =============================================================================
# EEG Device Management
# =============================================================================

class EEGDevice(models.Model):
    """Registered EEG headset device for a user."""
    
    DEVICE_TYPES = [
        ('muse', 'Muse Headband'),
        ('muse_2', 'Muse 2'),
        ('muse_s', 'Muse S'),
        ('neurosky', 'NeuroSky MindWave'),
        ('openbci', 'OpenBCI'),
        ('emotiv', 'Emotiv Insight'),
        ('other', 'Other Device'),
    ]
    
    STATUS_CHOICES = [
        ('paired', 'Paired'),
        ('calibrating', 'Calibrating'),
        ('ready', 'Ready'),
        ('disconnected', 'Disconnected'),
        ('error', 'Error'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='eeg_devices')
    
    device_type = models.CharField(max_length=20, choices=DEVICE_TYPES)
    device_name = models.CharField(max_length=100, help_text="User-assigned device name")
    device_id = models.CharField(max_length=100, help_text="Bluetooth/hardware ID")
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='disconnected')
    
    # Calibration data
    calibration_data = models.JSONField(
        default=dict,
        help_text="Device-specific calibration parameters"
    )
    baseline_alpha = models.FloatField(
        null=True, blank=True,
        help_text="User's baseline alpha power (8-12 Hz)"
    )
    baseline_theta = models.FloatField(
        null=True, blank=True,
        help_text="User's baseline theta power (4-8 Hz)"
    )
    signal_quality_threshold = models.FloatField(
        default=0.7,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Minimum acceptable signal quality"
    )
    
    # Metadata
    firmware_version = models.CharField(max_length=50, blank=True)
    battery_level = models.IntegerField(null=True, blank=True)
    last_connected_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-last_connected_at']
        unique_together = ['user', 'device_id']
    
    def __str__(self):
        return f"{self.device_name} ({self.get_device_type_display()}) - {self.user.username}"


# =============================================================================
# Training Sessions
# =============================================================================

class BrainwaveSession(models.Model):
    """Individual EEG training session."""
    
    SESSION_STATUS = [
        ('active', 'Active'),
        ('paused', 'Paused'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('error', 'Error'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='brainwave_sessions')
    device = models.ForeignKey(EEGDevice, on_delete=models.SET_NULL, null=True)
    
    status = models.CharField(max_length=20, choices=SESSION_STATUS, default='active')
    
    # Session timing
    started_at = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.IntegerField(default=0)
    
    # Aggregated brainwave metrics
    avg_alpha_power = models.FloatField(null=True, blank=True)
    avg_theta_power = models.FloatField(null=True, blank=True)
    avg_gamma_power = models.FloatField(null=True, blank=True)
    avg_focus_index = models.FloatField(null=True, blank=True)
    avg_signal_quality = models.FloatField(null=True, blank=True)
    
    # Training metrics
    passwords_trained = models.IntegerField(default=0)
    chunks_memorized = models.IntegerField(default=0)
    optimal_state_time = models.IntegerField(
        default=0,
        help_text="Seconds spent in optimal memory encoding state"
    )
    
    # Raw data (encrypted, stored externally)
    raw_data_reference = models.CharField(
        max_length=255, blank=True,
        help_text="Reference to encrypted EEG data storage"
    )
    
    # Session notes
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['started_at']),
        ]
    
    def __str__(self):
        return f"Session {self.id} - {self.user.username} ({self.status})"


class NeurofeedbackEvent(models.Model):
    """Real-time neurofeedback event during training."""
    
    EVENT_TYPES = [
        ('alpha_peak', 'Alpha Peak Detected'),
        ('theta_burst', 'Theta Burst'),
        ('gamma_spike', 'Gamma Spike'),
        ('focus_achieved', 'Focus State Achieved'),
        ('memory_ready', 'Memory Encoding Ready'),
        ('distraction', 'Distraction Detected'),
        ('fatigue', 'Mental Fatigue'),
        ('success', 'Successful Recall'),
        ('struggle', 'Recall Difficulty'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        BrainwaveSession,
        on_delete=models.CASCADE,
        related_name='events'
    )
    
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    timestamp = models.DateTimeField(default=timezone.now)
    
    # Event data
    alpha_power = models.FloatField(null=True, blank=True)
    theta_power = models.FloatField(null=True, blank=True)
    gamma_power = models.FloatField(null=True, blank=True)
    focus_index = models.FloatField(null=True, blank=True)
    
    # Context
    password_chunk_index = models.IntegerField(null=True, blank=True)
    feedback_given = models.CharField(max_length=50, blank=True)
    
    class Meta:
        ordering = ['timestamp']
        indexes = [
            models.Index(fields=['session', 'event_type']),
        ]


# =============================================================================
# Password Training Programs
# =============================================================================

class PasswordTrainingProgram(models.Model):
    """Multi-day training curriculum for memorizing a password."""
    
    PROGRAM_STATUS = [
        ('not_started', 'Not Started'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('paused', 'Paused'),
        ('abandoned', 'Abandoned'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='training_programs')
    vault_item = models.ForeignKey(
        'vault.EncryptedVaultItem',
        on_delete=models.CASCADE,
        related_name='training_programs'
    )
    
    status = models.CharField(max_length=20, choices=PROGRAM_STATUS, default='not_started')
    
    # Password info (hashed reference, not plaintext)
    password_hash = models.CharField(max_length=64, help_text="SHA-256 for verification")
    password_length = models.IntegerField()
    chunk_count = models.IntegerField(help_text="Number of 8-char chunks")
    
    # Training progress
    current_chunk = models.IntegerField(default=0)
    chunks_mastered = models.IntegerField(default=0)
    total_sessions = models.IntegerField(default=0)
    total_practice_time = models.IntegerField(default=0, help_text="Seconds")
    
    # Spaced repetition
    current_interval_days = models.FloatField(default=1.0)
    easiness_factor = models.FloatField(
        default=2.5,
        help_text="SuperMemo-style easiness factor"
    )
    next_review_at = models.DateTimeField(null=True, blank=True)
    last_reviewed_at = models.DateTimeField(null=True, blank=True)
    review_count = models.IntegerField(default=0)
    
    # Completion
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    target_completion_days = models.IntegerField(default=7)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['next_review_at']),
        ]
    
    def __str__(self):
        return f"Training for {self.vault_item} - {self.status}"


class MemoryStrengthScore(models.Model):
    """Tracks memory consolidation for each password chunk."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    program = models.ForeignKey(
        PasswordTrainingProgram,
        on_delete=models.CASCADE,
        related_name='memory_scores'
    )
    
    chunk_index = models.IntegerField(help_text="0-indexed chunk position")
    chunk_hash = models.CharField(max_length=64, help_text="Hash of chunk content")
    
    # Memory metrics
    strength_score = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Current memory strength (0-1)"
    )
    peak_strength = models.FloatField(default=0.0)
    decay_rate = models.FloatField(
        default=0.1,
        help_text="Forgetting curve decay rate"
    )
    
    # Learning history
    successful_recalls = models.IntegerField(default=0)
    failed_recalls = models.IntegerField(default=0)
    avg_recall_time_ms = models.IntegerField(null=True, blank=True)
    
    # Brainwave correlation
    best_alpha_correlation = models.FloatField(null=True, blank=True)
    encoding_quality = models.FloatField(
        null=True, blank=True,
        help_text="EEG-measured encoding quality"
    )
    
    # Timestamps
    first_exposure_at = models.DateTimeField(null=True, blank=True)
    last_practiced_at = models.DateTimeField(null=True, blank=True)
    mastered_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['chunk_index']
        unique_together = ['program', 'chunk_index']
    
    def __str__(self):
        return f"Chunk {self.chunk_index} - Strength: {self.strength_score:.2f}"
    
    @property
    def is_mastered(self):
        return self.strength_score >= 0.9


class SpacedRepetitionSchedule(models.Model):
    """Optimal review timing based on brain state and forgetting curve."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    program = models.ForeignKey(
        PasswordTrainingProgram,
        on_delete=models.CASCADE,
        related_name='schedules'
    )
    
    scheduled_at = models.DateTimeField()
    completed_at = models.DateTimeField(null=True, blank=True)
    skipped = models.BooleanField(default=False)
    
    # Scheduling factors
    interval_days = models.FloatField()
    predicted_strength = models.FloatField(
        help_text="Predicted memory strength at review time"
    )
    optimal_difficulty = models.FloatField(
        help_text="Target difficulty for optimal learning"
    )
    
    # Brain state recommendations
    recommended_time_of_day = models.CharField(max_length=20, blank=True)
    brain_state_recommendations = models.JSONField(
        default=dict,
        help_text="Optimal brain state for this review"
    )
    
    # Results
    actual_strength = models.FloatField(null=True, blank=True)
    session = models.ForeignKey(
        BrainwaveSession,
        on_delete=models.SET_NULL,
        null=True, blank=True
    )
    
    class Meta:
        ordering = ['scheduled_at']
        indexes = [
            models.Index(fields=['program', 'scheduled_at']),
        ]


# =============================================================================
# User Settings
# =============================================================================

class NeuroFeedbackSettings(models.Model):
    """User preferences for neuro-feedback training."""
    
    FEEDBACK_MODES = [
        ('visual', 'Visual Only'),
        ('audio', 'Audio Only'),
        ('haptic', 'Haptic Only'),
        ('combined', 'Combined'),
    ]
    
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='neuro_settings'
    )
    
    # Feature toggle
    is_enabled = models.BooleanField(default=True)
    
    # Device preferences
    preferred_device = models.ForeignKey(
        EEGDevice,
        on_delete=models.SET_NULL,
        null=True, blank=True
    )
    auto_connect = models.BooleanField(default=True)
    
    # Training preferences
    session_duration_minutes = models.IntegerField(
        default=15,
        validators=[MinValueValidator(5), MaxValueValidator(60)]
    )
    chunk_size = models.IntegerField(
        default=8,
        validators=[MinValueValidator(4), MaxValueValidator(16)]
    )
    daily_reminder = models.BooleanField(default=True)
    reminder_time = models.TimeField(null=True, blank=True)
    
    # Feedback preferences
    feedback_mode = models.CharField(
        max_length=20,
        choices=FEEDBACK_MODES,
        default='combined'
    )
    audio_volume = models.IntegerField(
        default=70,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    haptic_intensity = models.IntegerField(
        default=50,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    # Advanced
    alpha_threshold = models.FloatField(
        default=0.6,
        validators=[MinValueValidator(0.3), MaxValueValidator(0.9)]
    )
    binaural_beats_enabled = models.BooleanField(default=True)
    binaural_frequency = models.FloatField(
        default=10.0,
        help_text="Target frequency for alpha enhancement"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Neuro Settings for {self.user.username}"
