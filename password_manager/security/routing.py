"""
Security WebSocket Routing
==========================

Defines WebSocket URL patterns for the security app.
"""

from django.urls import re_path
from . import consumers
from .consumers.dark_protocol_consumer import DarkProtocolConsumer

websocket_urlpatterns = [
    re_path(
        r'ws/security/entanglement/$',
        consumers.EntanglementConsumer.as_asgi()
    ),
    # 🌑 Dark Protocol WebSocket for anonymous vault access
    re_path(
        r'ws/dark-protocol/(?P<session_id>[a-f0-9]+)/$',
        DarkProtocolConsumer.as_asgi()
    ),
]
