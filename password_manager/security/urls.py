from django.urls import path, include
from rest_framework import routers
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.reverse import reverse
from . import views
from .api.darkWebEndpoints import DarkWebViewSet
from .api.account_protection import AccountProtectionViewSet, SocialMediaAccountViewSet
from .api import quantum_rng_views
from .api import genetic_password_views

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
        'quantum': reverse('quantum-generate-password', request=request, format=format),
        'genetic': reverse('genetic-generate-password', request=request, format=format),
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
    
    # Quantum Random Number Generator endpoints
    path('quantum/generate-password/', quantum_rng_views.generate_quantum_password, name='quantum-generate-password'),
    path('quantum/random-bytes/', quantum_rng_views.get_random_bytes, name='quantum-random-bytes'),
    path('quantum/certificate/<uuid:certificate_id>/', quantum_rng_views.get_certificate, name='quantum-certificate'),
    path('quantum/certificates/', quantum_rng_views.list_certificates, name='quantum-certificates'),
    path('quantum/pool-status/', quantum_rng_views.get_pool_status, name='quantum-pool-status'),
    
    # ==========================================================================
    # Genetic Password Evolution endpoints
    # ==========================================================================
    
    # DNA Provider Connection
    path('genetic/connect/', genetic_password_views.initiate_connection, name='genetic-connect'),
    path('genetic/callback/', genetic_password_views.oauth_callback, name='genetic-callback'),
    path('genetic/upload/', genetic_password_views.upload_dna_file, name='genetic-upload'),
    path('genetic/disconnect/', genetic_password_views.disconnect_dna, name='genetic-disconnect'),
    path('genetic/connection-status/', genetic_password_views.get_connection_status, name='genetic-connection-status'),
    
    # Password Generation
    path('genetic/generate-password/', genetic_password_views.generate_genetic_password, name='genetic-generate-password'),
    
    # Certificates
    path('genetic/certificate/<uuid:certificate_id>/', genetic_password_views.get_certificate, name='genetic-certificate'),
    path('genetic/certificates/', genetic_password_views.list_certificates, name='genetic-certificates'),
    
    # Epigenetic Evolution (Premium)
    path('genetic/evolution-status/', genetic_password_views.get_evolution_status, name='genetic-evolution-status'),
    path('genetic/trigger-evolution/', genetic_password_views.trigger_evolution, name='genetic-trigger-evolution'),
    
    # Preferences
    path('genetic/preferences/', genetic_password_views.update_preferences, name='genetic-preferences'),
    
    # Other endpoints
    path('health-check/', views.health_check, name='security-health-check'),
    path('audit-log/', views.audit_log, name='security-audit-log'),
]

