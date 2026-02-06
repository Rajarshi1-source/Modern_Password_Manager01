"""
URL Configuration for ML Security API
"""

from django.urls import path
from . import views
from . import predictive_intent_views

app_name = 'ml_security'

urlpatterns = [
    # Password Strength Prediction
    path('password-strength/predict/', views.predict_password_strength, name='predict_password_strength'),
    path('password-strength/history/', views.get_password_strength_history, name='password_strength_history'),
    path('password-strength/fhe/', views.predict_password_strength_fhe, name='predict_password_strength_fhe'),
    
    # Anomaly Detection
    path('anomaly/detect/', views.detect_session_anomaly, name='detect_anomaly'),
    path('behavior/profile/', views.get_user_behavior_profile, name='get_behavior_profile'),
    path('behavior/profile/update/', views.update_behavior_profile, name='update_behavior_profile'),
    
    # Threat Analysis
    path('threat/analyze/', views.analyze_threat, name='analyze_threat'),
    path('threat/history/', views.get_threat_history, name='threat_history'),
    
    # Batch Operations
    path('session/analyze/', views.batch_analyze_session, name='batch_analyze_session'),
    
    # ML Model Information
    path('models/info/', views.get_ml_model_info, name='ml_model_info'),
    
    # ==========================================================================
    # Predictive Intent
    # ==========================================================================
    path('intent/predictions/', predictive_intent_views.get_predictions, name='intent_predictions'),
    path('intent/context/', predictive_intent_views.send_context_signal, name='intent_context'),
    path('intent/feedback/', predictive_intent_views.record_prediction_feedback, name='intent_feedback'),
    path('intent/preloaded/', predictive_intent_views.get_preloaded_credentials, name='intent_preloaded'),
    path('intent/settings/', predictive_intent_views.get_intent_settings, name='intent_settings_get'),
    path('intent/settings/update/', predictive_intent_views.update_intent_settings, name='intent_settings_update'),
    path('intent/stats/', predictive_intent_views.get_intent_statistics, name='intent_stats'),
    path('intent/usage/', predictive_intent_views.record_usage, name='intent_usage'),
    
    # GDPR Data Privacy
    path('intent/export/', predictive_intent_views.export_prediction_data, name='intent_export'),
    path('intent/data/', predictive_intent_views.delete_prediction_data, name='intent_delete_data'),
]

