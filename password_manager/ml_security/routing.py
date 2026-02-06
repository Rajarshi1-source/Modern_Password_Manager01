"""
ML Security WebSocket Routing
==============================

Defines WebSocket URL patterns for the ml_security app,
specifically for real-time predictive intent features.
"""

from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # Real-time password predictions
    re_path(
        r'ws/predictions/$',
        consumers.PredictiveIntentConsumer.as_asgi()
    ),
]
