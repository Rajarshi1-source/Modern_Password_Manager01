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
            'baseline_expression_patterns', 'baseline_gaze_pattern',
            'baseline_pulse_signature', 'baseline_thermal_signature',
            'baseline_expression_timing',
            'created_at', 'last_calibration_at'
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
            'id', 'challenge_type', 'sequence_number', 'difficulty',
            'challenge_data', 'expected_response', 'instruction',
            'challenge_status', 'time_limit_ms',
            'presented_at', 'completed_at', 'is_passed', 'score'
        ]
        read_only_fields = ['id', 'presented_at', 'completed_at', 'is_passed', 'score']


class ChallengeResponseSerializer(serializers.ModelSerializer):
    """Serializer for ChallengeResponse."""
    
    class Meta:
        model = ChallengeResponse
        fields = [
            'id', 'challenge', 'response_data',
            'reaction_time_ms', 'total_duration_ms',
            'face_detected', 'multiple_faces_detected',
            'blink_detected', 'micro_movement_detected', 'natural_skin_texture',
            'texture_liveness_score', 'depth_liveness_score', 'motion_liveness_score',
            'response_type', 'gaze_accuracy', 'expression_score', 'is_valid', 'score',
            'client_timestamp', 'server_received_at'
        ]
        read_only_fields = ['id', 'server_received_at']


class PulseOximetryReadingSerializer(serializers.ModelSerializer):
    """Serializer for PulseOximetryReading."""
    
    class Meta:
        model = PulseOximetryReading
        fields = [
            'id', 'session', 'timestamp', 'frame_number',
            'heart_rate_bpm', 'heart_rate_variability', 'spo2_estimate',
            'signal_quality', 'rgb_means', 'ppg_signal_segment',
            'is_consistent_with_living'
        ]
        read_only_fields = ['id', 'timestamp']


class ThermalReadingSerializer(serializers.ModelSerializer):
    """Serializer for ThermalReading."""
    
    class Meta:
        model = ThermalReading
        fields = [
            'id', 'session', 'timestamp', 'frame_number',
            'average_face_temp_c', 'temp_range_c',
            'has_natural_thermal_gradient', 'matches_living_tissue_range',
            'is_valid', 'heat_map_features'
        ]
        read_only_fields = ['id', 'timestamp']


class GazeTrackingDataSerializer(serializers.ModelSerializer):
    """Serializer for GazeTrackingData."""
    
    class Meta:
        model = GazeTrackingData
        fields = [
            'id', 'challenge', 'session', 'timestamp_ms', 'gaze_x', 'gaze_y',
            'target_x', 'target_y',
            'confidence', 'is_fixation', 'accuracy', 'head_pose'
        ]
        read_only_fields = ['id']


class MicroExpressionEventSerializer(serializers.ModelSerializer):
    """Serializer for MicroExpressionEvent."""
    
    class Meta:
        model = MicroExpressionEvent
        fields = [
            'id', 'session', 'timestamp', 'frame_number', 'duration_ms',
            'expression_type', 'action_units', 'intensity',
            'onset_natural', 'offset_natural', 'asymmetry_score', 'is_genuine'
        ]
        read_only_fields = ['id', 'timestamp']


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
            'pulse_oximetry_score', 'thermal_score', 'texture_artifact_score',
            'total_frames_processed', 'face_detection_rate',
            'verdict', 'verdict_reason',
            'challenges',
            'device_fingerprint', 'user_agent', 'ip_address'
        ]
        read_only_fields = [
            'id', 'user', 'created_at', 'started_at', 'completed_at',
            'overall_liveness_score', 'deepfake_probability', 'confidence',
            'verdict', 'verdict_reason'
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
