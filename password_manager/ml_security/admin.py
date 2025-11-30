"""
Django Admin Interface for ML Security
"""

from django.contrib import admin
from .models import (
    PasswordStrengthPrediction,
    UserBehaviorProfile,
    AnomalyDetection,
    ThreatPrediction,
    MLModelMetadata,
    MLTrainingData
)


@admin.register(PasswordStrengthPrediction)
class PasswordStrengthPredictionAdmin(admin.ModelAdmin):
    list_display = ['user', 'strength', 'confidence_score', 'length', 'created_at']
    list_filter = ['strength', 'created_at', 'has_uppercase', 'has_lowercase', 'has_numbers', 'has_special']
    search_fields = ['user__username', 'user__email']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'password_hash')
        }),
        ('Prediction Results', {
            'fields': ('strength', 'confidence_score', 'guessability_score')
        }),
        ('Password Features', {
            'fields': ('length', 'entropy', 'character_diversity', 
                      'has_numbers', 'has_uppercase', 'has_lowercase', 
                      'has_special', 'contains_common_patterns')
        }),
        ('Metadata', {
            'fields': ('created_at',)
        }),
    )


@admin.register(UserBehaviorProfile)
class UserBehaviorProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'samples_used', 'last_trained', 'model_version']
    search_fields = ['user__username', 'user__email']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Temporal Patterns', {
            'fields': ('typical_login_hours', 'typical_login_days', 'avg_session_duration')
        }),
        ('Behavioral Patterns', {
            'fields': ('typing_speed_avg', 'typing_speed_std', 'mouse_movement_pattern')
        }),
        ('Location Patterns', {
            'fields': ('common_locations', 'common_ip_ranges')
        }),
        ('Device Patterns', {
            'fields': ('common_devices', 'common_browsers', 'common_os')
        }),
        ('Activity Patterns', {
            'fields': ('vault_access_frequency', 'password_update_frequency', 
                      'avg_passwords_accessed_per_session')
        }),
        ('Model Metadata', {
            'fields': ('last_trained', 'samples_used', 'model_version', 
                      'created_at', 'updated_at')
        }),
    )


@admin.register(AnomalyDetection)
class AnomalyDetectionAdmin(admin.ModelAdmin):
    list_display = ['user', 'anomaly_type', 'severity', 'anomaly_score', 'created_at']
    list_filter = ['anomaly_type', 'severity', 'created_at', 'was_false_positive']
    search_fields = ['user__username', 'session_id', 'ip_address']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Detection Information', {
            'fields': ('user', 'session_id', 'anomaly_type', 'severity')
        }),
        ('Scores', {
            'fields': ('anomaly_score', 'confidence')
        }),
        ('Context', {
            'fields': ('ip_address', 'location', 'device_fingerprint', 'user_agent')
        }),
        ('Analysis Details', {
            'fields': ('expected_values', 'actual_values', 'deviations'),
            'classes': ('collapse',)
        }),
        ('Response', {
            'fields': ('action_taken', 'was_false_positive', 'user_feedback')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'resolved_at')
        }),
    )


@admin.register(ThreatPrediction)
class ThreatPredictionAdmin(admin.ModelAdmin):
    list_display = ['user', 'threat_type', 'risk_level', 'recommended_action', 'created_at']
    list_filter = ['threat_type', 'created_at', 'recommended_action']
    search_fields = ['user__username', 'session_id', 'ip_address']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Threat Information', {
            'fields': ('user', 'session_id', 'threat_type')
        }),
        ('Risk Assessment', {
            'fields': ('threat_score', 'risk_level', 'recommended_action')
        }),
        ('Model Outputs', {
            'fields': ('sequence_features', 'spatial_features', 'temporal_features'),
            'classes': ('collapse',)
        }),
        ('CNN-LSTM Outputs', {
            'fields': ('cnn_output', 'lstm_output', 'final_prediction'),
            'classes': ('collapse',)
        }),
        ('Context', {
            'fields': ('ip_address', 'device_fingerprint')
        }),
        ('Response', {
            'fields': ('action_executed', 'was_true_positive')
        }),
        ('Metadata', {
            'fields': ('created_at',)
        }),
    )


@admin.register(MLModelMetadata)
class MLModelMetadataAdmin(admin.ModelAdmin):
    list_display = ['model_type', 'version', 'accuracy', 'training_date', 'is_active']
    list_filter = ['model_type', 'is_active', 'training_date']
    search_fields = ['version', 'notes']
    readonly_fields = ['training_date', 'last_used']
    
    fieldsets = (
        ('Model Information', {
            'fields': ('model_type', 'version', 'file_path', 'is_active')
        }),
        ('Performance Metrics', {
            'fields': ('accuracy', 'precision', 'recall', 'f1_score', 'auc_roc')
        }),
        ('Training Information', {
            'fields': ('training_samples', 'training_date', 'last_used')
        }),
        ('Configuration', {
            'fields': ('hyperparameters', 'feature_importance'),
            'classes': ('collapse',)
        }),
        ('Notes', {
            'fields': ('notes',)
        }),
    )


@admin.register(MLTrainingData)
class MLTrainingDataAdmin(admin.ModelAdmin):
    list_display = ['model_type', 'is_validated', 'weight', 'source', 'created_at']
    list_filter = ['model_type', 'is_validated', 'created_at']
    search_fields = ['model_type', 'source']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Training Data', {
            'fields': ('model_type', 'features', 'label', 'weight')
        }),
        ('Validation', {
            'fields': ('is_validated', 'validation_date', 'source')
        }),
        ('Metadata', {
            'fields': ('created_at',)
        }),
    )

