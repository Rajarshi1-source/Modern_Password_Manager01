# Import views for easier access
from .api_views import VaultItemViewSet as ApiVaultItemViewSet
from .crud_views import VaultItemViewSet as CrudVaultItemViewSet

# Also export the original class names
from .api_views import VaultItemViewSet
from .crud_views import VaultItemViewSet as CrudVaultViewSet

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from password_manager.api_utils import error_response, success_response

# Audit-fix M7 (2026-05): the stub `sync(request)` function that
# previously lived here returned "Sync endpoint is working" with no
# real work — it shadowed the genuine `CrudVaultItemViewSet.sync`
# @action. The stub function has been deleted.
#
# PR D (2026-06): `sync` is now mounted explicitly at /api/vault/sync/
# via `path('sync/', CrudVaultItemViewSet.as_view({'post': 'sync'}),
# name='vault-sync')` in vault/urls.py — where the frontend already
# posts. The old `router.register(r'vault', CrudVaultItemViewSet, ...)`
# registration (which placed sync at the double-prefixed
# /api/vault/vault/sync/) was dropped as cruft.


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def search(request):
    """
    Search functionality for vault items
    """
    # Implementation for search functionality
    # This is a placeholder - implement actual search logic based on your requirements
    query = request.GET.get('q', '')
    
    return Response({
        "status": "success",
        "message": "Search endpoint is working",
        "query": query,
        "results": []  # Add actual search results here
    }) 
