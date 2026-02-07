"""
Biometric Liveness WebSocket Routing
=====================================

WebSocket URL patterns for liveness verification.
"""

from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/liveness/(?P<session_id>[0-9a-f-]+)/$', consumers.LivenessConsumer.as_asgi()),
]
