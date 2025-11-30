"""
URL Configuration for ML Security API
"""

from django.urls import path
from . import views

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
]

