from django.urls import path, include
from rest_framework.routers import DefaultRouter
from vault.views import ApiVaultItemViewSet, CrudVaultItemViewSet
from vault.views.folder_views import FolderViewSet
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.reverse import reverse
from . import views
from .views.backup_views import BackupViewSet

# Create a router and register our viewsets
router = DefaultRouter()

# API endpoints for basic CRUD operations with encryption
router.register(r'vault', CrudVaultItemViewSet, basename='vault')

# API endpoints for authentication and key management
router.register(r'', ApiVaultItemViewSet, basename='api-vault')

# API endpoints for folder management
router.register(r'folders', FolderViewSet, basename='folders')

# API endpoints for backup management
router.register(r'backups', BackupViewSet, basename='backup')

# Available endpoints:
# /vault/ - List and create vault items
# /vault/{id}/ - Retrieve, update, delete vault items
# /vault/sync/ - Sync vault items across devices
# /api/vault/get_salt/ - Get user's encryption salt
# /api/vault/verify_master_password/ - Verify master password

@api_view(['GET'])
def vault_root(request, format=None):
    """Entry point for vault endpoints"""
    return Response({
        'items': reverse('vault-items-list', request=request, format=format),
        'sync': reverse('vault-sync', request=request, format=format),
        'search': reverse('vault-search', request=request, format=format),
    })

# Update the existing router to include items
router.register(r'items', views.VaultItemViewSet, basename='vault-items')

# Combine all URL patterns
urlpatterns = [
    path('', vault_root, name='vault-root'),
    # Include all router-generated URLs
    path('', include(router.urls)),
    
    # Custom endpoints
    path('sync/', views.sync, name='vault-sync'),
    path('search/', views.search, name='vault-search'),
    
    # Include auth URLs for browsable API (optional)
    path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),
    path('create_backup/', BackupViewSet.as_view({'post': 'create_backup'}), name='create-backup'),
    path('restore_backup/<uuid:pk>/', BackupViewSet.as_view({'post': 'restore'}), name='restore-backup'),
    
    # Shared Folders API
    path('shared-folders/', include('vault.urls_shared_folders')),
]
