"""
Neuro-Feedback WebSocket Routing
================================

Defines WebSocket URL patterns for the neuro_feedback app.
"""

from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # Real-time neuro-feedback training
    re_path(
        r'ws/neuro-training/(?P<session_id>[a-f0-9-]+)/$',
        consumers.NeuroTrainingConsumer.as_asgi()
    ),
]
