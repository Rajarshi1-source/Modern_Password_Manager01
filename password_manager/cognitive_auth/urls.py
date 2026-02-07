"""
Cognitive Auth URL Configuration
================================

REST API endpoints for cognitive password verification.
"""

from django.urls import path
from . import views

app_name = 'cognitive_auth'

urlpatterns = [
    # Session management
    path('challenge/start/', views.start_verification_session, name='start-session'),
    path('challenge/respond/', views.submit_response, name='submit-response'),
    
    # Profile management
    path('profile/', views.get_profile, name='get-profile'),
    path('calibrate/', views.start_calibration, name='start-calibration'),
    
    # Settings
    path('settings/', views.get_settings, name='get-settings'),
    path('settings/update/', views.update_settings, name='update-settings'),
    
    # History
    path('history/', views.get_history, name='get-history'),
]
