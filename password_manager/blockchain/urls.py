"""
Blockchain App URL Configuration

API endpoints for blockchain verification and anchoring
"""

from django.urls import path
from . import views

app_name = 'blockchain'

urlpatterns = [
    # Commitment verification
    path(
        'verify-commitment/<uuid:commitment_id>/',
        views.verify_commitment,
        name='verify_commitment'
    ),
    
    # Anchoring status and control
    path(
        'anchor-status/',
        views.anchor_status,
        name='anchor_status'
    ),
    
    path(
        'trigger-anchor/',
        views.trigger_anchor,
        name='trigger_anchor'
    ),
    
    # User commitments
    path(
        'user-commitments/',
        views.user_commitments,
        name='user_commitments'
    ),
]

