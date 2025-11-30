"""
Analytics URL Configuration
===========================

URL patterns for analytics API endpoints.
"""

from django.urls import path
from . import views

app_name = 'analytics'

urlpatterns = [
    # Event tracking
    path('events/', views.track_events, name='track_events'),
    
    # Dashboard
    path('dashboard/', views.get_analytics_dashboard, name='dashboard'),
    
    # User journey
    path('journey/', views.get_user_journey, name='journey'),
]

