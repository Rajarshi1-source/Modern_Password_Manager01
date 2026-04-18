"""
Mesh Dead Drop WebSocket Routing
=================================

URL patterns for the mesh dead drop websocket consumers. These get merged into
``password_manager/asgi.py``'s ``websocket_urlpatterns``. Authentication is
handled by the project-level ``TokenAuthMiddleware`` which expects
``?token=<jwt|drf-token>`` in the query string.
"""

from django.urls import re_path

from .consumers import DeadDropConsumer, MeshNodeConsumer


websocket_urlpatterns = [
    re_path(
        r"ws/mesh/node/(?P<node_id>[0-9a-f-]{36})/$",
        MeshNodeConsumer.as_asgi(),
    ),
    re_path(
        r"ws/mesh/deaddrop/(?P<drop_id>[0-9a-f-]{36})/$",
        DeadDropConsumer.as_asgi(),
    ),
]
