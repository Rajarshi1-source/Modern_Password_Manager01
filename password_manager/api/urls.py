from django.urls import path, include
from rest_framework import routers
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.reverse import reverse

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

urlpatterns = [
    path('', api_root, name='api-root'),
    path('auth/', include('auth_module.urls')),
    path('vault/', include('vault.urls')),
    path('security/', include('security.urls')),
    path('user/', include('user.urls')),  # You'll need to create this app
]
