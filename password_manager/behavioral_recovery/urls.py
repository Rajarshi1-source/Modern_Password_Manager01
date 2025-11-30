"""
URL Configuration for Behavioral Recovery API
"""

from django.urls import path
from . import views

app_name = 'behavioral_recovery'

urlpatterns = [
    # Recovery Flow Endpoints
    path('initiate/', views.initiate_recovery, name='initiate_recovery'),
    path('status/<uuid:attempt_id>/', views.get_recovery_status, name='get_recovery_status'),
    path('submit-challenge/', views.submit_challenge, name='submit_challenge'),
    path('complete/', views.complete_recovery, name='complete_recovery'),
    
    # Commitment Management
    path('setup-commitments/', views.setup_commitments, name='setup_commitments'),
    path('commitments/status/', views.get_commitment_status, name='get_commitment_status'),
    
    # Challenge Generation
    path('challenges/<uuid:attempt_id>/next/', views.get_next_challenge, name='get_next_challenge'),
    
    # ============================================================================
    # PHASE 2B.2: METRICS & A/B TESTING ENDPOINTS
    # ============================================================================
    
    # Metrics Dashboard
    path('metrics/dashboard/', views.recovery_metrics_dashboard, name='metrics_dashboard'),
    path('metrics/summary/', views.recovery_metrics_summary, name='metrics_summary'),
    
    # User Feedback
    path('feedback/', views.submit_recovery_feedback, name='submit_feedback'),
    
    # A/B Testing
    path('ab-tests/<str:experiment_name>/results/', views.get_ab_test_results, name='get_ab_test_results'),
    path('ab-tests/create/', views.create_recovery_experiments, name='create_experiments'),
]

