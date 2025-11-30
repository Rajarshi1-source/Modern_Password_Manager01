"""
A/B Testing URL Configuration
=============================

URL patterns for A/B testing API endpoints.
"""

from django.urls import path
from . import views

app_name = 'ab_testing'

urlpatterns = [
    # Get experiments and feature flags
    path('', views.get_experiments_and_flags, name='get_experiments_flags'),
    
    # Track metrics
    path('metrics/', views.track_experiment_metric, name='track_metric'),
    
    # Experiment results
    path('experiments/<str:experiment_name>/results/', views.get_experiment_results, name='experiment_results'),
    
    # User-specific endpoints
    path('user/experiments/', views.get_user_experiments, name='user_experiments'),
    path('user/flags/', views.get_user_feature_flags, name='user_flags'),
]

