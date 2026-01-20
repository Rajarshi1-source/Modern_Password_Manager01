"""
ASGI config for password_manager project.

It exposes the ASGI callable as a module-level variable named ``application``.
Includes WebSocket support via Django Channels for real-time breach alerts
and adversarial AI password defense.

For more information on this file, see
https://docs.djangoproject.com/en/4.1/howto/deployment/asgi/
"""

import os
from django.core.asgi import get_asgi_application

# Set Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'password_manager.settings')

# Initialize Django ASGI application early to ensure apps are loaded
django_asgi_app = get_asgi_application()

# Import Channels routing after Django setup
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from ml_dark_web.middleware import TokenAuthMiddlewareStack

# Import WebSocket URL patterns from both apps
from ml_dark_web import routing as ml_dark_web_routing
from adversarial_ai import routing as adversarial_ai_routing
from security import routing as security_routing

# Combine WebSocket URL patterns
websocket_urlpatterns = (
    ml_dark_web_routing.websocket_urlpatterns +
    adversarial_ai_routing.websocket_urlpatterns +
    security_routing.websocket_urlpatterns
)

# ASGI application with WebSocket support
application = ProtocolTypeRouter({
    # Django's ASGI application handles traditional HTTP requests
    "http": django_asgi_app,
    
    # WebSocket handler with token authentication
    # Supports:
    # - /ws/breach-alerts/<user_id>/ (ml_dark_web)
    # - /ws/adversarial/<user_id>/ (adversarial_ai)
    "websocket": AllowedHostsOriginValidator(
        TokenAuthMiddlewareStack(
            URLRouter(
                websocket_urlpatterns
            )
        )
    ),
})
