"""
Biometric Liveness URL Routing
===============================

REST API URL patterns for liveness verification.
"""

from django.urls import path
from . import views

app_name = 'biometric_liveness'

urlpatterns = [
    # Session management
    path('session/start/', views.start_session, name='start_session'),
    path('session/complete/', views.complete_session, name='complete_session'),
    
    # Frame processing
    path('frame/', views.submit_frame, name='submit_frame'),
    
    # Challenges
    path('challenge/', views.get_challenge, name='get_challenge'),
    path('challenge/respond/', views.submit_challenge_response, name='submit_challenge_response'),
    
    # Profile & Settings
    path('profile/', views.get_profile, name='get_profile'),
    path('settings/', views.settings_view, name='settings'),
    
    # History
    path('history/', views.get_history, name='get_history'),
]
