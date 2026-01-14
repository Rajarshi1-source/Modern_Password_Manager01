"""
WebSocket URL routing for Adversarial AI module.
"""

from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(
        r'ws/adversarial/(?P<user_id>\d+)/$',
        consumers.AdversarialBattleConsumer.as_asgi()
    ),
]
