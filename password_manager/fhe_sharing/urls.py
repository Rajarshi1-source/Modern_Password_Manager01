"""
FHE Sharing URL Configuration
"""

from django.urls import path
from . import views

app_name = 'fhe_sharing'

urlpatterns = [
    # Share CRUD
    path('shares/', views.create_share, name='create-share'),
    path('shares/list/', views.list_shares, name='list-shares'),
    path('shares/<uuid:share_id>/', views.share_detail, name='share-detail'),
    path('shares/<uuid:share_id>/revoke/', views.revoke_share, name='revoke-share'),

    # Autofill Usage
    path('shares/<uuid:share_id>/use/', views.use_autofill, name='use-autofill'),

    # Received Shares
    path('received/', views.received_shares, name='received-shares'),

    # Access Logs
    path('shares/<uuid:share_id>/logs/', views.share_logs, name='share-logs'),

    # Share Groups
    path('groups/', views.create_group, name='create-group'),
    path('groups/list/', views.list_groups, name='list-groups'),

    # Service Status
    path('status/', views.sharing_status, name='status'),
]
