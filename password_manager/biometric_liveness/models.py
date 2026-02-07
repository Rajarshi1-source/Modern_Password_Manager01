"""
Biometric Liveness Detection - Django Models
==============================================

Core models for deepfake-resistant biometric authentication using:
- Micro-expression analysis
- Gaze tracking with cognitive tasks
- Thermal imaging integration
- Pulse oximetry through camera (rPPG)

@author Password Manager Team
@created 2026-02-07
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid
from datetime import timedelta

User = get_user_model()


class LivenessProfile(models.Model):
    """
    User's baseline liveness patterns and biometric characteristics.
    
    Stores calibrated thresholds for micro-expressions, gaze patterns,
    pulse rhythms, and thermal signatures unique to the user.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='liveness_profile'
    )
    
    # Calibration status
    is_calibrated = models.BooleanField(
        default=False,
        help_text="Whether profile has been calibrated with baseline data"
    )
    calibration_samples = models.IntegerField(
        default=0,
        help_text="Number of calibration sessions completed"
    )
    last_calibration_at = models.DateTimeField(null=True, blank=True)
    
    # Baseline biometrics (encrypted/hashed)
    baseline_pulse_signature = models.JSONField(
        default=dict,
        help_text="Baseline rPPG pulse waveform characteristics"
    )
    baseline_gaze_pattern = models.JSONField(
        default=dict,
        help_text="Typical gaze movement patterns and fixation durations"
    )
    baseline_expression_patterns = models.JSONField(
        default=dict,
        help_text="Natural micro-expression timing and intensity"
    )
    baseline_thermal_signature = models.JSONField(
        default=dict,
        help_text="Facial thermal distribution pattern (if available)"
    )
    
    # Quality metrics
    profile_confidence = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Confidence level in profile accuracy (0-1)"
    )
    
    # Adaptive thresholds
    liveness_threshold = models.FloatField(
        default=0.85,
        validators=[MinValueValidator(0.5), MaxValueValidator(0.99)],
        help_text="Minimum liveness score required to pass"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Liveness Profile"
        verbose_name_plural = "Liveness Profiles"
    
    def __str__(self):
        status = "Calibrated" if self.is_calibrated else "Pending"
        return f"LivenessProfile({self.user.username}, {status})"


class LivenessSession(models.Model):
    """
    A biometric verification session with multiple liveness challenges.
    
    Sessions aggregate multiple detection methods to produce a
    composite liveness score.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('passed', 'Passed'),
        ('failed', 'Failed'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    ]
    
    CONTEXT_CHOICES = [
        ('login', 'Login Verification'),
        ('high_security', 'High Security Action'),
        ('enrollment', 'Initial Enrollment'),
        ('re_enrollment', 'Re-enrollment'),
        ('suspicious', 'Suspicious Activity'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='liveness_sessions'
    )
    
    # Session context
    context = models.CharField(
        max_length=20,
        choices=CONTEXT_CHOICES,
        default='login'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    
    # Challenge configuration
    required_challenges = models.JSONField(
        default=list,
        help_text="List of required challenge types for this session"
    )
    completed_challenges = models.IntegerField(default=0)
    
    # Timing
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()
    
    # Composite scores
    overall_liveness_score = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Aggregated liveness score from all challenges"
    )
    deepfake_probability = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Probability that input is a deepfake"
    )
    confidence = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Confidence in the verification result"
    )
    
    # Detection scores by method
    micro_expression_score = models.FloatField(default=0.0)
    gaze_tracking_score = models.FloatField(default=0.0)
    pulse_oximetry_score = models.FloatField(default=0.0)
    thermal_score = models.FloatField(default=0.0)
    texture_artifact_score = models.FloatField(default=0.0)
    
    # Frame statistics
    total_frames_processed = models.IntegerField(default=0)
    face_detection_rate = models.FloatField(default=0.0)
    
    # Device info
    device_fingerprint = models.CharField(max_length=256, blank=True)
    user_agent = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Liveness Session"
        verbose_name_plural = "Liveness Sessions"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"LivenessSession({self.id}, {self.status})"
    
    def is_expired(self):
        return timezone.now() > self.expires_at
    
    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(minutes=2)
        super().save(*args, **kwargs)


class LivenessChallenge(models.Model):
    """
    Individual liveness challenge within a verification session.
    
    Challenge types:
    - gaze: Track gaze point, follow on-screen targets
    - expression: Perform specific facial expressions
    - cognitive: Solve visual puzzles while being tracked
    - blink: Perform specific blink patterns
    """
    CHALLENGE_TYPE_CHOICES = [
        ('gaze', 'Gaze Tracking'),
        ('expression', 'Expression Analysis'),
        ('cognitive', 'Cognitive Task'),
        ('blink', 'Blink Detection'),
        ('pulse', 'Pulse Measurement'),
    ]
    
    DIFFICULTY_CHOICES = [
        ('easy', 'Easy'),
        ('medium', 'Medium'),
        ('hard', 'Hard'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        LivenessSession,
        on_delete=models.CASCADE,
        related_name='challenges'
    )
    
    # Challenge config
    challenge_type = models.CharField(
        max_length=20,
        choices=CHALLENGE_TYPE_CHOICES
    )
    difficulty = models.CharField(
        max_length=10,
        choices=DIFFICULTY_CHOICES,
        default='medium'
    )
    sequence_number = models.IntegerField(
        help_text="Order of this challenge in the session"
    )
    
    # Challenge data
    challenge_data = models.JSONField(
        default=dict,
        help_text="Challenge-specific instructions and parameters"
    )
    expected_response = models.JSONField(
        default=dict,
        help_text="Expected response patterns (hashed for security)"
    )
    
    # Timing
    time_limit_ms = models.IntegerField(
        default=5000,
        help_text="Maximum time allowed in milliseconds"
    )
    presented_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Results
    is_passed = models.BooleanField(null=True)
    score = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)]
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Liveness Challenge"
        verbose_name_plural = "Liveness Challenges"
        ordering = ['session', 'sequence_number']
        unique_together = ['session', 'sequence_number']
    
    def __str__(self):
        return f"Challenge({self.challenge_type}, #{self.sequence_number})"


class ChallengeResponse(models.Model):
    """
    User's response to a liveness challenge with extracted biometric data.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    challenge = models.OneToOneField(
        LivenessChallenge,
        on_delete=models.CASCADE,
        related_name='response'
    )
    
    # Response data
    response_data = models.JSONField(
        default=dict,
        help_text="Extracted response features"
    )
    
    # Timing metrics
    reaction_time_ms = models.IntegerField(
        help_text="Time from challenge display to first response"
    )
    total_duration_ms = models.IntegerField(
        help_text="Total time spent on challenge"
    )
    
    # Detection results
    face_detected = models.BooleanField(default=True)
    multiple_faces_detected = models.BooleanField(default=False)
    
    # Liveness indicators
    blink_detected = models.BooleanField(default=False)
    micro_movement_detected = models.BooleanField(default=False)
    natural_skin_texture = models.BooleanField(default=True)
    
    # Anti-spoofing scores
    texture_liveness_score = models.FloatField(default=0.0)
    depth_liveness_score = models.FloatField(default=0.0)
    motion_liveness_score = models.FloatField(default=0.0)
    
    # Timestamps
    client_timestamp = models.BigIntegerField()
    server_received_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Challenge Response"
        verbose_name_plural = "Challenge Responses"
    
    def __str__(self):
        return f"Response(Challenge: {self.challenge.challenge_type})"


class PulseOximetryReading(models.Model):
    """
    Remote photoplethysmography (rPPG) blood oxygen reading.
    
    Extracted from camera video to detect blood flow patterns
    that cannot be faked by deepfakes or static images.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        LivenessSession,
        on_delete=models.CASCADE,
        related_name='pulse_readings'
    )
    
    # Timing
    timestamp = models.DateTimeField(auto_now_add=True)
    frame_number = models.IntegerField()
    
    # Pulse data
    heart_rate_bpm = models.FloatField(
        null=True,
        blank=True,
        help_text="Estimated heart rate in BPM"
    )
    heart_rate_variability = models.FloatField(
        null=True,
        blank=True,
        help_text="Heart rate variability metric"
    )
    spo2_estimate = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
        help_text="Estimated SpO2 percentage"
    )
    
    # Signal quality
    signal_quality = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Quality of the rPPG signal (0-1)"
    )
    
    # Raw signals (for analysis)
    rgb_means = models.JSONField(
        default=list,
        help_text="RGB channel mean values from ROI"
    )
    ppg_signal_segment = models.JSONField(
        default=list,
        help_text="Extracted PPG signal segment"
    )
    
    # Liveness indicator
    is_consistent_with_living = models.BooleanField(
        default=True,
        help_text="Whether readings are consistent with living tissue"
    )
    
    class Meta:
        verbose_name = "Pulse Oximetry Reading"
        verbose_name_plural = "Pulse Oximetry Readings"
        ordering = ['session', 'frame_number']
    
    def __str__(self):
        return f"PulseReading(HR: {self.heart_rate_bpm}, SpO2: {self.spo2_estimate}%)"


class ThermalReading(models.Model):
    """
    Thermal imaging data point (when IR camera available).
    
    Detects screen-based attacks by checking for expected
    facial heat signatures.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        LivenessSession,
        on_delete=models.CASCADE,
        related_name='thermal_readings'
    )
    
    # Timing
    timestamp = models.DateTimeField(auto_now_add=True)
    frame_number = models.IntegerField()
    
    # Temperature data
    average_face_temp_c = models.FloatField(
        null=True,
        blank=True,
        help_text="Average facial temperature in Celsius"
    )
    temp_range_c = models.JSONField(
        default=dict,
        help_text="Min/max temperature range on face"
    )
    heat_map_features = models.JSONField(
        default=dict,
        help_text="Extracted thermal feature points"
    )
    
    # Liveness indicators
    has_natural_thermal_gradient = models.BooleanField(
        default=True,
        help_text="Natural temp gradient from nose/eyes to edges"
    )
    matches_living_tissue_range = models.BooleanField(
        default=True,
        help_text="Temperature in expected living tissue range"
    )
    
    class Meta:
        verbose_name = "Thermal Reading"
        verbose_name_plural = "Thermal Readings"
        ordering = ['session', 'frame_number']
    
    def __str__(self):
        return f"ThermalReading({self.average_face_temp_c}°C)"


class LivenessSettings(models.Model):
    """
    User preferences for liveness verification.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='liveness_settings'
    )
    
    # Feature toggles
    enable_on_login = models.BooleanField(
        default=False,
        help_text="Require liveness check on every login"
    )
    enable_on_sensitive_actions = models.BooleanField(
        default=True,
        help_text="Require for sensitive vault operations"
    )
    enable_pulse_detection = models.BooleanField(
        default=True,
        help_text="Enable rPPG pulse detection"
    )
    enable_thermal = models.BooleanField(
        default=False,
        help_text="Enable thermal camera (if available)"
    )
    
    # Difficulty
    challenge_difficulty = models.CharField(
        max_length=10,
        choices=[('easy', 'Easy'), ('medium', 'Medium'), ('hard', 'Hard')],
        default='medium'
    )
    
    # Accessibility
    extended_time = models.BooleanField(
        default=False,
        help_text="Allow extra time for challenges"
    )
    simplified_challenges = models.BooleanField(
        default=False,
        help_text="Use simplified challenge variants"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Liveness Settings"
        verbose_name_plural = "Liveness Settings"
    
    def __str__(self):
        return f"LivenessSettings({self.user.username})"


class GazeTrackingData(models.Model):
    """
    Gaze tracking data from cognitive challenge.
    
    Records eye movement patterns during challenge to verify
    real-time human attention and cognition.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    challenge = models.ForeignKey(
        LivenessChallenge,
        on_delete=models.CASCADE,
        related_name='gaze_data'
    )
    
    # Timing
    timestamp_ms = models.BigIntegerField(
        help_text="Milliseconds since challenge start"
    )
    
    # Gaze coordinates (normalized 0-1)
    gaze_x = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)]
    )
    gaze_y = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)]
    )
    
    # Target coordinates (if applicable)
    target_x = models.FloatField(null=True, blank=True)
    target_y = models.FloatField(null=True, blank=True)
    
    # Quality metrics
    confidence = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Confidence in gaze detection"
    )
    is_fixation = models.BooleanField(
        default=False,
        help_text="Whether this is a fixation point vs saccade"
    )
    
    class Meta:
        verbose_name = "Gaze Tracking Data"
        verbose_name_plural = "Gaze Tracking Data"
        ordering = ['challenge', 'timestamp_ms']
    
    def __str__(self):
        return f"GazeData({self.gaze_x:.2f}, {self.gaze_y:.2f})"


class MicroExpressionEvent(models.Model):
    """
    Detected micro-expression during liveness verification.
    
    Micro-expressions are involuntary facial movements that
    AI-generated faces have difficulty replicating naturally.
    """
    EXPRESSION_TYPES = [
        ('surprise', 'Surprise'),
        ('happy', 'Happy'),
        ('sad', 'Sad'),
        ('angry', 'Angry'),
        ('fear', 'Fear'),
        ('disgust', 'Disgust'),
        ('contempt', 'Contempt'),
        ('neutral', 'Neutral'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        LivenessSession,
        on_delete=models.CASCADE,
        related_name='expression_events'
    )
    
    # Timing
    timestamp = models.DateTimeField(auto_now_add=True)
    frame_number = models.IntegerField()
    duration_ms = models.IntegerField(
        help_text="Duration of micro-expression in milliseconds"
    )
    
    # Expression data
    expression_type = models.CharField(
        max_length=20,
        choices=EXPRESSION_TYPES
    )
    intensity = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Intensity of expression (0-1)"
    )
    
    # Action Units detected (FACS)
    action_units = models.JSONField(
        default=dict,
        help_text="Facial Action Coding System units detected"
    )
    
    # Naturalness indicators
    onset_natural = models.BooleanField(
        default=True,
        help_text="Whether onset timing appears natural"
    )
    offset_natural = models.BooleanField(
        default=True,
        help_text="Whether offset timing appears natural"
    )
    asymmetry_score = models.FloatField(
        default=0.0,
        help_text="Facial asymmetry (natural faces have some)"
    )
    
    class Meta:
        verbose_name = "Micro Expression Event"
        verbose_name_plural = "Micro Expression Events"
        ordering = ['session', 'frame_number']
    
    def __str__(self):
        return f"Expression({self.expression_type}, {self.intensity:.2f})"
