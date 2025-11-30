from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from vault.models import VaultFolder
from vault.serializer import FolderSerializer
from password_manager.api_utils import error_response, success_response

class FolderViewSet(viewsets.ModelViewSet):
    """API endpoints for vault folder management"""
    permission_classes = [IsAuthenticated]
    serializer_class = FolderSerializer
    
    def get_queryset(self):
        """Return only folders belonging to authenticated user"""
        return VaultFolder.objects.filter(user=self.request.user)
    
    def create(self, request):
        """Create a new folder"""
        serializer = self.get_serializer(data=request.data)
        
        if serializer.is_valid():
            # Save the folder
            folder = serializer.save(user=request.user)
            
            return success_response(serializer.data, status_code=status.HTTP_201_CREATED)
            
        return error_response(serializer.errors, status_code=status.HTTP_400_BAD_REQUEST)
        
    @action(detail=True, methods=['get'])
    def items(self, request, pk=None):
        """Get all items in a folder"""
        folder = self.get_object()
        items = folder.items.filter(deleted=False)
        
        from vault.serializer import VaultItemSerializer
        serializer = VaultItemSerializer(items, many=True)
        
        return success_response(serializer.data)
