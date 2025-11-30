from django.shortcuts import render
from vault.models.vault_models import EncryptedVaultItem  # Updated import
from rest_framework import routers
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.reverse import reverse
from django.urls import path, include
from django.http import JsonResponse

# Create your views here.

@api_view(['GET'])
def api_root(request, format=None):
    """
    Root entry point for the API, providing links to main endpoints
    """
    return Response({
        'auth': reverse('auth-root', request=request, format=format),
        'vault': reverse('vault-root', request=request, format=format),
        'security': reverse('security-root', request=request, format=format),
        'user': reverse('user-root', request=request, format=format),
    })


# Create a router that integrates views from other apps
api_router = routers.DefaultRouter()

# Include URLs from other apps - these will be included in the main urls.py
urlpatterns = [
    path('', api_root, name='api-root'),
    path('vault/', include('vault.urls')),
    path('auth/', include('auth_module.urls')),
    path('security/', include('security.urls')),
]
