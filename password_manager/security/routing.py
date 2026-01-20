"""
Security WebSocket Routing
==========================

Defines WebSocket URL patterns for the security app.
"""

from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(
        r'ws/security/entanglement/$',
        consumers.EntanglementConsumer.as_asgi()
    ),
]
