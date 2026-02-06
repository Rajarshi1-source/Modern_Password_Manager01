"""
Neuro-Feedback URL Configuration
================================

URL routing for neuro-feedback API endpoints.
"""

from django.urls import path
from . import views

app_name = 'neuro_feedback'

urlpatterns = [
    # Device Management
    path('devices/', views.devices, name='devices'),
    path('devices/<uuid:device_id>/', views.device_detail, name='device_detail'),
    path('devices/<uuid:device_id>/calibrate/', views.calibrate_device, name='calibrate_device'),
    
    # Training Programs
    path('programs/', views.training_programs, name='programs'),
    path('programs/<uuid:program_id>/', views.training_program_detail, name='program_detail'),
    path('programs/<uuid:program_id>/start/', views.start_training_session, name='start_session'),
    path('programs/<uuid:program_id>/progress/', views.memory_progress, name='memory_progress'),
    
    # Schedule
    path('schedule/', views.review_schedule, name='schedule'),
    path('due/', views.due_reviews, name='due_reviews'),
    
    # Settings
    path('settings/', views.neuro_settings, name='settings'),
    
    # Statistics
    path('stats/', views.neuro_statistics, name='statistics'),
]
