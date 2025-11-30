"""
URL Configuration for Shared Folders API
"""

from django.urls import path
from vault.views import shared_folder_views as views
from vault.views import shared_folder_views_part2 as views2

urlpatterns = [
    # Folder Management
    path('', views.list_shared_folders, name='list_shared_folders'),
    path('create/', views.create_shared_folder, name='create_shared_folder'),
    path('<uuid:folder_id>/', views.folder_detail, name='folder_detail'),
    path('<uuid:folder_id>/leave/', views2.leave_folder, name='leave_folder'),
    path('<uuid:folder_id>/rotate-key/', views2.rotate_folder_key, name='rotate_folder_key'),
    
    # Member Management
    path('<uuid:folder_id>/invite/', views.invite_member, name='invite_member'),
    path('<uuid:folder_id>/members/', views.folder_members, name='folder_members'),
    path('<uuid:folder_id>/members/<uuid:member_id>/', views2.update_member_role, name='update_member_role'),
    path('<uuid:folder_id>/members/<uuid:member_id>/remove/', views2.remove_member, name='remove_member'),
    
    # Invitations
    path('invitations/pending/', views.pending_invitations, name='pending_invitations'),
    path('invitations/<str:invitation_token>/accept/', views.accept_invitation, name='accept_invitation'),
    path('invitations/<str:invitation_token>/decline/', views.decline_invitation, name='decline_invitation'),
    
    # Item Management
    path('<uuid:folder_id>/items/', views2.folder_items, name='folder_items'),
    path('<uuid:folder_id>/items/add/', views2.add_item_to_folder, name='add_item_to_folder'),
    path('<uuid:folder_id>/items/<uuid:item_id>/', views2.folder_item_detail, name='folder_item_detail'),
    
    # Activity Log
    path('<uuid:folder_id>/activity/', views2.folder_activity, name='folder_activity'),
]

