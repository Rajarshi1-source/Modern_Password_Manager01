from django.urls import path, include
from rest_framework import routers
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.reverse import reverse
from . import views
from .api.darkWebEndpoints import DarkWebViewSet
from .api.account_protection import AccountProtectionViewSet, SocialMediaAccountViewSet

@api_view(['GET'])
def security_root(request, format=None):
    """Entry point for security endpoints"""
    return Response({
        'dashboard': reverse('security-dashboard', request=request, format=format),
        'score': reverse('security-score', request=request, format=format),
        'devices': reverse('security-devices', request=request, format=format),
        'social-accounts': reverse('security-social-accounts-list', request=request, format=format),
        'dark-web': reverse('security-dark-web-list', request=request, format=format),
        'health-check': reverse('security-health-check', request=request, format=format),
        'audit-log': reverse('security-audit-log', request=request, format=format),
    })

# Create a router for viewsets
router = routers.DefaultRouter()
router.register(r'dark-web', DarkWebViewSet, basename='security-dark-web')
router.register(r'social-accounts', SocialMediaAccountViewSet, basename='security-social-accounts')

urlpatterns = [
    path('', security_root, name='security-root'),
    path('', include(router.urls)),
    
    # Security Dashboard endpoints
    path('dashboard/', views.security_dashboard, name='security-dashboard'),
    path('score/', views.security_score, name='security-score'),
    
    # Device Management endpoints
    path('devices/', views.devices_list, name='security-devices'),
    path('devices/<str:device_id>/', views.device_detail, name='security-device-detail'),
    path('devices/<str:device_id>/trust/', views.device_trust, name='security-device-trust'),
    path('devices/<str:device_id>/untrust/', views.device_untrust, name='security-device-untrust'),
    
    # Social Account Management endpoints (additional to the viewset)
    path('social-accounts/<int:account_id>/lock/', views.social_account_lock, name='security-social-account-lock'),
    path('social-accounts/<int:account_id>/unlock/', views.social_account_unlock, name='security-social-account-unlock'),
    
    # Other endpoints
    path('health-check/', views.health_check, name='security-health-check'),
    path('audit-log/', views.audit_log, name='security-audit-log'),
]
