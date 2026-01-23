"""
Mesh Dead Drop URL Patterns
============================

URL configuration for the mesh dead drop API.

@author Password Manager Team
@created 2026-01-22
"""

from django.urls import path
from .api.deaddrop_views import (
    DeadDropListView,
    DeadDropDetailView,
    DeadDropDistributeView,
    DeadDropCollectView,
    DeadDropCancelView,
    MeshNodeListView,
    MeshNodeDetailView,
    NearbyNodesView,
    NodePingView,
    NFCChallengeView,
    NFCVerifyView,
)

app_name = 'mesh_deaddrop'

urlpatterns = [
    # Dead Drop Management
    path('deaddrops/', DeadDropListView.as_view(), name='deaddrop-list'),
    path('deaddrops/<uuid:drop_id>/', DeadDropDetailView.as_view(), name='deaddrop-detail'),
    path('deaddrops/<uuid:drop_id>/distribute/', DeadDropDistributeView.as_view(), name='deaddrop-distribute'),
    path('deaddrops/<uuid:drop_id>/collect/', DeadDropCollectView.as_view(), name='deaddrop-collect'),
    path('deaddrops/<uuid:drop_id>/cancel/', DeadDropCancelView.as_view(), name='deaddrop-cancel'),
    
    # Mesh Nodes
    path('nodes/', MeshNodeListView.as_view(), name='node-list'),
    path('nodes/<uuid:node_id>/', MeshNodeDetailView.as_view(), name='node-detail'),
    path('nodes/<uuid:node_id>/ping/', NodePingView.as_view(), name='node-ping'),
    path('nodes/nearby/', NearbyNodesView.as_view(), name='nearby-nodes'),
    
    # NFC Verification
    path('nfc/challenge/', NFCChallengeView.as_view(), name='nfc-challenge'),
    path('nfc/verify/', NFCVerifyView.as_view(), name='nfc-verify'),
]
