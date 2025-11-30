"""
FHE Service URL Configuration
"""

from django.urls import path
from . import views

app_name = 'fhe_service'

urlpatterns = [
    # Encryption endpoints
    path('encrypt/', views.encrypt_data, name='encrypt'),
    
    # Password strength endpoints
    path('strength-check/', views.strength_check, name='strength-check'),
    path('batch-strength/', views.batch_strength_check, name='batch-strength'),
    
    # Search endpoints
    path('search/', views.encrypted_search, name='search'),
    
    # Key management endpoints
    path('keys/generate/', views.generate_keys, name='generate-keys'),
    path('keys/', views.get_keys, name='get-keys'),
    
    # Status and metrics endpoints
    path('status/', views.fhe_status, name='status'),
    path('metrics/', views.fhe_metrics, name='metrics'),
]

