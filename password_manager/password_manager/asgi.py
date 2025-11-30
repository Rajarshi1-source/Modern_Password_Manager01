"""
ASGI config for password_manager project.

It exposes the ASGI callable as a module-level variable named ``application``.
Includes WebSocket support via Django Channels for real-time breach alerts.

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
from ml_dark_web import routing

# ASGI application with WebSocket support
application = ProtocolTypeRouter({
    # Django's ASGI application handles traditional HTTP requests
    "http": django_asgi_app,
    
    # WebSocket chat handler with token authentication
    "websocket": AllowedHostsOriginValidator(
        TokenAuthMiddlewareStack(
            URLRouter(
                routing.websocket_urlpatterns
            )
        )
    ),
})
