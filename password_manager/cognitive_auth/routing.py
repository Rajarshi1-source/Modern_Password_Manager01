"""
Cognitive Auth WebSocket Routing
================================

WebSocket URL routing for cognitive verification.
"""

from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(
        r'ws/cognitive/(?P<session_id>[0-9a-f-]+)/$',
        consumers.CognitiveVerificationConsumer.as_asgi()
    ),
]
