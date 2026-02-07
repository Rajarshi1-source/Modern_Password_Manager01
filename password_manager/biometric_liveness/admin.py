"""
Biometric Liveness Admin
=========================

Django admin configuration for liveness models.
"""

from django.contrib import admin
from .models import (
    LivenessProfile, LivenessSession, LivenessChallenge,
    ChallengeResponse, PulseOximetryReading, ThermalReading,
    LivenessSettings, GazeTrackingData, MicroExpressionEvent
)


@admin.register(LivenessProfile)
class LivenessProfileAdmin(admin.ModelAdmin):
    """Admin for LivenessProfile."""
    
    list_display = [
        'user', 'is_calibrated', 'calibration_samples',
        'profile_confidence', 'last_calibration_at'
    ]
    list_filter = ['is_calibrated']
    search_fields = ['user__username', 'user__email']
    readonly_fields = ['created_at', 'updated_at', 'last_calibration_at']


@admin.register(LivenessSession)
class LivenessSessionAdmin(admin.ModelAdmin):
    """Admin for LivenessSession."""
    
    list_display = [
        'id', 'user', 'context', 'status', 
        'overall_liveness_score', 'created_at'
    ]
    list_filter = ['status', 'context']
    search_fields = ['user__username', 'id']
    readonly_fields = [
        'created_at', 'started_at', 'completed_at',
        'overall_liveness_score', 'deepfake_probability'
    ]
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Session Info', {
            'fields': ('user', 'context', 'status', 'device_fingerprint', 'ip_address')
        }),
        ('Timing', {
            'fields': ('created_at', 'started_at', 'completed_at', 'expires_at')
        }),
        ('Scores', {
            'fields': (
                'overall_liveness_score', 'deepfake_probability', 'confidence',
                'micro_expression_score', 'gaze_tracking_score',
                'pulse_oximetry_score', 'thermal_score'
            )
        }),
        ('Stats', {
            'fields': ('total_frames_processed', 'face_detection_rate')
        }),
    )


@admin.register(LivenessChallenge)
class LivenessChallengeAdmin(admin.ModelAdmin):
    """Admin for LivenessChallenge."""
    
    list_display = [
        'id', 'session', 'challenge_type', 'sequence_number', 'is_passed', 'score'
    ]
    list_filter = ['challenge_type', 'is_passed', 'difficulty']
    search_fields = ['session__id']


@admin.register(ChallengeResponse)
class ChallengeResponseAdmin(admin.ModelAdmin):
    """Admin for ChallengeResponse."""
    
    list_display = [
        'id', 'challenge', 'reaction_time_ms', 'face_detected', 
        'texture_liveness_score', 'server_received_at'
    ]
    list_filter = ['face_detected', 'blink_detected']
    readonly_fields = ['server_received_at']


@admin.register(PulseOximetryReading)
class PulseOximetryReadingAdmin(admin.ModelAdmin):
    """Admin for PulseOximetryReading."""
    
    list_display = [
        'id', 'session', 'heart_rate_bpm', 'spo2_estimate',
        'signal_quality', 'is_consistent_with_living'
    ]
    list_filter = ['is_consistent_with_living']


@admin.register(ThermalReading)
class ThermalReadingAdmin(admin.ModelAdmin):
    """Admin for ThermalReading."""
    
    list_display = [
        'id', 'session', 'average_face_temp_c', 
        'has_natural_thermal_gradient', 'matches_living_tissue_range'
    ]
    list_filter = ['has_natural_thermal_gradient', 'matches_living_tissue_range']


@admin.register(LivenessSettings)
class LivenessSettingsAdmin(admin.ModelAdmin):
    """Admin for LivenessSettings."""
    
    list_display = [
        'user', 'enable_on_login', 'enable_on_sensitive_actions',
        'enable_pulse_detection', 'challenge_difficulty'
    ]
    list_filter = ['enable_on_login', 'enable_on_sensitive_actions']
    search_fields = ['user__username', 'user__email']


@admin.register(GazeTrackingData)
class GazeTrackingDataAdmin(admin.ModelAdmin):
    """Admin for GazeTrackingData."""
    
    list_display = [
        'id', 'challenge', 'timestamp_ms', 'gaze_x', 'gaze_y',
        'confidence', 'is_fixation'
    ]
    list_filter = ['is_fixation']


@admin.register(MicroExpressionEvent)
class MicroExpressionEventAdmin(admin.ModelAdmin):
    """Admin for MicroExpressionEvent."""
    
    list_display = [
        'id', 'session', 'expression_type', 'intensity',
        'onset_natural', 'offset_natural'
    ]
    list_filter = ['expression_type', 'onset_natural', 'offset_natural']
