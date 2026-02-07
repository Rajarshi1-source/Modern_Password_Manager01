"""
Biometric Liveness Serializers
===============================

DRF serializers for liveness API.
"""

from rest_framework import serializers
from .models import (
    LivenessProfile, LivenessSession, LivenessChallenge,
    ChallengeResponse, PulseOximetryReading, ThermalReading,
    LivenessSettings, GazeTrackingData, MicroExpressionEvent
)


class LivenessProfileSerializer(serializers.ModelSerializer):
    """Serializer for LivenessProfile."""
    
    class Meta:
        model = LivenessProfile
        fields = [
            'id', 'user', 'is_calibrated', 'calibration_samples',
            'profile_confidence', 'liveness_threshold', 
            'baseline_expression_timing', 'baseline_gaze_patterns',
            'baseline_pulse_signature', 'created_at', 'last_calibration_at'
        ]
        read_only_fields = ['id', 'user', 'created_at']


class LivenessSettingsSerializer(serializers.ModelSerializer):
    """Serializer for LivenessSettings."""
    
    class Meta:
        model = LivenessSettings
        fields = [
            'id', 'user', 'enable_on_login', 'enable_on_sensitive_actions',
            'enable_pulse_detection', 'enable_thermal', 'challenge_difficulty',
            'extended_time', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']


class LivenessChallengeSerializer(serializers.ModelSerializer):
    """Serializer for LivenessChallenge."""
    
    class Meta:
        model = LivenessChallenge
        fields = [
            'id', 'challenge_type', 'sequence', 'status',
            'instruction', 'target_data', 'time_limit_ms',
            'started_at', 'completed_at'
        ]
        read_only_fields = ['id', 'started_at', 'completed_at']


class ChallengeResponseSerializer(serializers.ModelSerializer):
    """Serializer for ChallengeResponse."""
    
    class Meta:
        model = ChallengeResponse
        fields = [
            'id', 'challenge', 'response_type', 'response_data',
            'reaction_time_ms', 'gaze_accuracy', 'expression_score',
            'is_valid', 'score', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class PulseOximetryReadingSerializer(serializers.ModelSerializer):
    """Serializer for PulseOximetryReading."""
    
    class Meta:
        model = PulseOximetryReading
        fields = [
            'id', 'session', 'timestamp_ms', 'frame_number',
            'heart_rate_bpm', 'heart_rate_variability', 'spo2_estimate',
            'ppg_signal_quality', 'rgb_mean_values', 'is_valid'
        ]
        read_only_fields = ['id']


class ThermalReadingSerializer(serializers.ModelSerializer):
    """Serializer for ThermalReading."""
    
    class Meta:
        model = ThermalReading
        fields = [
            'id', 'session', 'timestamp_ms', 'frame_number',
            'average_temp_c', 'min_temp_c', 'max_temp_c',
            'has_natural_gradient', 'matches_living_tissue',
            'heat_map_features', 'is_valid'
        ]
        read_only_fields = ['id']


class GazeTrackingDataSerializer(serializers.ModelSerializer):
    """Serializer for GazeTrackingData."""
    
    class Meta:
        model = GazeTrackingData
        fields = [
            'id', 'session', 'timestamp_ms', 'gaze_x', 'gaze_y',
            'target_x', 'target_y', 'accuracy', 'head_pose',
            'confidence', 'is_fixation'
        ]
        read_only_fields = ['id']


class MicroExpressionEventSerializer(serializers.ModelSerializer):
    """Serializer for MicroExpressionEvent."""
    
    class Meta:
        model = MicroExpressionEvent
        fields = [
            'id', 'session', 'timestamp_ms', 'duration_ms',
            'expression_type', 'action_units', 'intensity',
            'naturalness_score', 'is_genuine'
        ]
        read_only_fields = ['id']


class LivenessSessionSerializer(serializers.ModelSerializer):
    """Serializer for LivenessSession."""
    
    challenges = LivenessChallengeSerializer(many=True, read_only=True)
    
    class Meta:
        model = LivenessSession
        fields = [
            'id', 'user', 'context', 'status', 'created_at', 
            'started_at', 'completed_at', 'expires_at',
            'overall_liveness_score', 'deepfake_probability', 'confidence',
            'micro_expression_score', 'gaze_tracking_score',
            'pulse_oximetry_score', 'thermal_score',
            'total_frames_processed', 'challenges',
            'device_fingerprint', 'ip_address', 'verdict', 'verdict_reason'
        ]
        read_only_fields = [
            'id', 'user', 'created_at', 'started_at', 'completed_at',
            'overall_liveness_score', 'deepfake_probability', 'confidence'
        ]


class LivenessSessionCreateSerializer(serializers.Serializer):
    """Serializer for creating a liveness session."""
    
    context = serializers.CharField(max_length=50, default='login')
    device_fingerprint = serializers.CharField(max_length=255, required=False, allow_blank=True)


class FrameSubmitSerializer(serializers.Serializer):
    """Serializer for submitting a video frame."""
    
    session_id = serializers.UUIDField()
    frame = serializers.CharField()  # Base64 encoded
    timestamp_ms = serializers.FloatField(default=0)
    width = serializers.IntegerField(default=640)
    height = serializers.IntegerField(default=480)


class ChallengeResponseSubmitSerializer(serializers.Serializer):
    """Serializer for submitting challenge response."""
    
    session_id = serializers.UUIDField()
    challenge_id = serializers.UUIDField(required=False)
    response = serializers.DictField()


class SessionCompleteSerializer(serializers.Serializer):
    """Serializer for session completion request."""
    
    session_id = serializers.UUIDField()


class LivenessResultSerializer(serializers.Serializer):
    """Serializer for liveness verification result."""
    
    session_id = serializers.UUIDField()
    is_verified = serializers.BooleanField()
    liveness_score = serializers.FloatField()
    verdict = serializers.CharField()
    confidence = serializers.FloatField()
    details = serializers.DictField(required=False)
