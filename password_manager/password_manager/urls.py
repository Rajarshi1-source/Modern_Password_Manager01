"""password_manager URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework import permissions
from django.conf import settings
from django.conf.urls.static import static
from api.health import health_check, readiness_check, liveness_check
# FIX: Import csrf_exempt for auth endpoints
from django.views.decorators.csrf import csrf_exempt

# API documentation schema
schema_view = get_schema_view(
   openapi.Info(
      title="Password Manager API",
      default_version='v1',
      description="API for secure password manager",
      terms_of_service="https://www.example.com/terms/",
      contact=openapi.Contact(email="contact@example.com"),
      license=openapi.License(name="Proprietary"),
   ),
   public=False,
   permission_classes=[permissions.IsAdminUser],
)

# Simple API root view
@require_http_methods(["GET"])
def api_root(request):
    return JsonResponse({
        'message': 'Password Manager API Server',
        'version': '1.0.0',
        'status': 'running',
        'endpoints': {
            'api': '/api/',
            'admin': '/admin/',
            'docs': '/docs/',
            'accounts': '/accounts/'
        }
    })

urlpatterns = [
    # Health check endpoints (for monitoring)
    # Root-level health checks (for container orchestration)
    path('health/', health_check, name='health-check'),
    path('ready/', readiness_check, name='readiness-check'),
    path('live/', liveness_check, name='liveness-check'),
    
    # API-level health check (for Docker/K8s health probes expecting /api/health/)
    path('api/health/', health_check, name='api-health-check'),
    
    # Django admin
    path('admin/', admin.site.urls),
    
    # FIX: Direct /auth/ route for frontend compatibility (mirrors /api/auth/)
    # This allows frontend to call /auth/register/ without needing to change paths
    path('auth/', include('auth_module.urls')),
    
    # API routes - this will use your structured API endpoints
    path('api/', include('api.urls')),
    
    # Blockchain API endpoints (Phase 2B.1)
    path('api/blockchain/', include('blockchain.urls')),
    
    # API documentation
    path('docs/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    
    # API root endpoint - serves API information instead of React app
    path('', api_root, name='api-root'),
    
    # Django AllAuth URLs - DISABLED for API-first/ASGI applications
    # These URLs provide HTML forms/redirects which aren't needed for SPA frontends.
    # OAuth functionality is available through /api/auth/oauth/ endpoints instead.
    # Keeping these disabled prevents HttpResponsePermanentRedirect ASGI errors.
    # path('accounts/', include('allauth.urls')),
    
    # Security API routes
    path('api/security/', include('security.urls')),
    
    # ML Security API routes
    path('api/ml-security/', include('ml_security.urls')),
    
    # Performance Monitoring API routes
    path('api/performance/', include('shared.urls')),
    
    # Analytics API routes
    path('api/analytics/', include('analytics.urls')),
    
    # A/B Testing API routes
    path('api/ab-testing/', include('ab_testing.urls')),
    
    # Email Masking API routes
    path('api/email-masking/', include('email_masking.urls')),
    
    # Behavioral Recovery API routes
    path('api/behavioral-recovery/', include('behavioral_recovery.urls')),
    
    # FHE (Fully Homomorphic Encryption) API routes
    path('api/fhe/', include('fhe_service.urls')),
    
    # Adversarial AI Password Defense API routes
    path('api/adversarial/', include('adversarial_ai.urls')),
    
    # Mesh Dead Drop Password Sharing API routes
    path('api/mesh/', include('mesh_deaddrop.urls')),
]

# Add static file serving for development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
