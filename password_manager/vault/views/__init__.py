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

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def sync(request):
    """
    Synchronize vault items between devices
    """
    # Implementation for sync functionality
    # This is a placeholder - implement actual sync logic based on your requirements
    return success_response({
        "timestamp": timezone.now()
    }, message="Sync endpoint is working")

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
