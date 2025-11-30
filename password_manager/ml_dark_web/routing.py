"""
WebSocket URL routing for ML Dark Web monitoring
"""

from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(
        r'ws/breach-alerts/(?P<user_id>\w+)/$',
        consumers.BreachAlertConsumer.as_asgi()
    ),
]

