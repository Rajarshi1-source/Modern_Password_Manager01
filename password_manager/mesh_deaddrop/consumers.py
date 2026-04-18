"""
Mesh Dead Drop WebSocket Consumers
===================================

Real-time channels for mesh node operators:

- ``/ws/mesh/node/<node_id>/`` — node-owner stream used to deliver:
    * ``fragment_sync`` events when new fragments are queued for a node
    * ``fragment_assigned`` events when distribution places a share on this node
    * ``deaddrop_collected`` notifications so caches can drop fragments
    * ``health_request`` pings that the device must answer

- ``/ws/mesh/deaddrop/<drop_id>/`` — owner stream that emits:
    * ``distribution_progress`` updates while fragments are fanning out
    * ``collection_attempt`` events for every :class:`DeadDropAccess`
    * ``health_update`` messages when node-level health changes

Authentication piggy-backs on :class:`ml_dark_web.middleware.TokenAuthMiddleware`
which accepts a JWT / DRF token via the ``?token=`` query string and attaches
the ``User`` to ``scope['user']``.

The consumers are intentionally thin — they only subscribe/unsubscribe to
Channels groups. Message emission is done from services / tasks via
``channel_layer.group_send`` (see :func:`broadcast_*` helpers).
"""

from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.utils import timezone

logger = logging.getLogger(__name__)


def node_group_name(node_id) -> str:
    """Channels group name for a specific mesh node."""
    return f"mesh_node_{node_id}"


def deaddrop_group_name(drop_id) -> str:
    """Channels group name for a specific dead drop."""
    return f"mesh_deaddrop_{drop_id}"


class _BaseMeshConsumer(AsyncJsonWebsocketConsumer):
    """Shared helpers for mesh consumers."""

    async def _reject(self, reason: str, code: int = 4001) -> None:
        logger.warning("mesh ws rejected: %s", reason)
        try:
            await self.accept()
            await self.send_json({"type": "error", "reason": reason})
        finally:
            await self.close(code=code)

    async def echo(self, event):
        """Forward every event whose ``type`` handler doesn't exist to the client."""
        payload = {k: v for k, v in event.items() if k != "type"}
        payload.setdefault("type", event.get("type"))
        await self.send_json(payload)


class MeshNodeConsumer(_BaseMeshConsumer):
    """
    WebSocket stream for a single mesh node.

    URL: ``/ws/mesh/node/<node_id>/?token=<jwt>``

    Only the user that owns the node may connect. Once connected the client
    receives fragment-sync, fragment-assigned, collection and health events
    routed by ``mesh_node_<id>`` channel groups.
    """

    group_name: Optional[str] = None
    node_id: Optional[UUID] = None

    async def connect(self):
        user = self.scope.get("user")
        if not user or not getattr(user, "is_authenticated", False):
            await self._reject("unauthenticated")
            return

        raw = self.scope["url_route"]["kwargs"].get("node_id")
        try:
            node_id = UUID(str(raw))
        except (TypeError, ValueError):
            await self._reject("invalid_node_id")
            return

        owns = await self._user_owns_node(user.id, node_id)
        if not owns:
            await self._reject("forbidden", code=4003)
            return

        self.node_id = node_id
        self.group_name = node_group_name(node_id)
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        await self.send_json(
            {
                "type": "connection_established",
                "scope": "node",
                "node_id": str(node_id),
                "timestamp": timezone.now().isoformat(),
            }
        )
        await self._mark_online(node_id)

    async def disconnect(self, close_code):
        if self.group_name:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
        if self.node_id:
            await self._mark_offline(self.node_id)

    async def receive_json(self, content, **kwargs):
        msg_type = content.get("type") if isinstance(content, dict) else None

        if msg_type == "ping":
            await self.send_json({"type": "pong", "timestamp": timezone.now().isoformat()})
            return

        if msg_type == "health_response":
            await self._record_health_response(self.node_id, content)
            return

        await self.send_json({"type": "error", "reason": "unknown_message_type"})

    async def fragment_sync(self, event):
        await self.echo(event)

    async def fragment_assigned(self, event):
        await self.echo(event)

    async def deaddrop_collected(self, event):
        await self.echo(event)

    async def health_request(self, event):
        await self.echo(event)

    @database_sync_to_async
    def _user_owns_node(self, user_id, node_id) -> bool:
        from .models import MeshNode

        return MeshNode.objects.filter(id=node_id, owner_id=user_id).exists()

    @database_sync_to_async
    def _mark_online(self, node_id) -> None:
        from .models import MeshNode

        MeshNode.objects.filter(id=node_id).update(is_online=True, last_seen=timezone.now())

    @database_sync_to_async
    def _mark_offline(self, node_id) -> None:
        from .models import MeshNode

        MeshNode.objects.filter(id=node_id).update(is_online=False)

    @database_sync_to_async
    def _record_health_response(self, node_id, payload) -> None:
        if not node_id:
            return
        from .models import MeshNode

        try:
            node = MeshNode.objects.get(id=node_id)
        except MeshNode.DoesNotExist:
            return

        node.last_seen = timezone.now()
        lat = payload.get("latitude")
        lon = payload.get("longitude")
        if lat is not None and lon is not None:
            node.last_known_latitude = lat
            node.last_known_longitude = lon
            node.location_updated_at = timezone.now()
        node.save(
            update_fields=[
                "last_seen",
                "last_known_latitude",
                "last_known_longitude",
                "location_updated_at",
            ]
        )


class DeadDropConsumer(_BaseMeshConsumer):
    """
    WebSocket stream for a dead drop's lifecycle events.

    URL: ``/ws/mesh/deaddrop/<drop_id>/?token=<jwt>``

    Only the drop owner may subscribe (recipients get a separate DRF polling
    endpoint today). Delivers:

    - ``distribution_progress`` as shares are placed on nodes
    - ``collection_attempt`` for each :class:`DeadDropAccess` (success + fail)
    - ``health_update`` summarising node-level state changes
    """

    group_name: Optional[str] = None
    drop_id: Optional[UUID] = None

    async def connect(self):
        user = self.scope.get("user")
        if not user or not getattr(user, "is_authenticated", False):
            await self._reject("unauthenticated")
            return

        raw = self.scope["url_route"]["kwargs"].get("drop_id")
        try:
            drop_id = UUID(str(raw))
        except (TypeError, ValueError):
            await self._reject("invalid_drop_id")
            return

        owns = await self._user_owns_drop(user.id, drop_id)
        if not owns:
            await self._reject("forbidden", code=4003)
            return

        self.drop_id = drop_id
        self.group_name = deaddrop_group_name(drop_id)
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        await self.send_json(
            {
                "type": "connection_established",
                "scope": "deaddrop",
                "drop_id": str(drop_id),
                "timestamp": timezone.now().isoformat(),
            }
        )

    async def disconnect(self, close_code):
        if self.group_name:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        if isinstance(content, dict) and content.get("type") == "ping":
            await self.send_json({"type": "pong", "timestamp": timezone.now().isoformat()})
            return
        await self.send_json({"type": "error", "reason": "unknown_message_type"})

    async def distribution_progress(self, event):
        await self.echo(event)

    async def collection_attempt(self, event):
        await self.echo(event)

    async def health_update(self, event):
        await self.echo(event)

    @database_sync_to_async
    def _user_owns_drop(self, user_id, drop_id) -> bool:
        from .models import DeadDrop

        return DeadDrop.objects.filter(id=drop_id, owner_id=user_id).exists()


# ---------------------------------------------------------------------------
# Synchronous helpers used by services / tasks to emit events.
# ---------------------------------------------------------------------------

def _group_send(group: str, event: dict) -> None:
    """Best-effort synchronous group_send wrapper."""
    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync

        layer = get_channel_layer()
        if layer is None:
            logger.debug("channel layer not configured; skipping event %s", event.get("type"))
            return
        async_to_sync(layer.group_send)(group, event)
    except Exception:  # pragma: no cover - defensive
        logger.exception("failed to emit mesh event %s", event.get("type"))


def broadcast_fragment_assigned(node_id, fragment_id, drop_id) -> None:
    """Notify the node that a new fragment was placed on it."""
    _group_send(
        node_group_name(node_id),
        {
            "type": "fragment_assigned",
            "node_id": str(node_id),
            "fragment_id": str(fragment_id),
            "drop_id": str(drop_id),
            "timestamp": timezone.now().isoformat(),
        },
    )


def broadcast_fragment_sync(node_id, queued_ids, drop_id=None) -> None:
    """Tell a node to pull its pending fragment sync queue."""
    _group_send(
        node_group_name(node_id),
        {
            "type": "fragment_sync",
            "node_id": str(node_id),
            "pending": [str(i) for i in queued_ids],
            "drop_id": str(drop_id) if drop_id else None,
            "timestamp": timezone.now().isoformat(),
        },
    )


def broadcast_deaddrop_collected(drop_id, accessor_id=None) -> None:
    """Broadcast to owner channel and each participating node that the drop was collected."""
    _group_send(
        deaddrop_group_name(drop_id),
        {
            "type": "collection_attempt",
            "drop_id": str(drop_id),
            "accessor_id": str(accessor_id) if accessor_id else None,
            "result": "collected",
            "timestamp": timezone.now().isoformat(),
        },
    )


def broadcast_distribution_progress(drop_id, placed, total) -> None:
    _group_send(
        deaddrop_group_name(drop_id),
        {
            "type": "distribution_progress",
            "drop_id": str(drop_id),
            "placed": int(placed),
            "total": int(total),
            "timestamp": timezone.now().isoformat(),
        },
    )


def broadcast_health_update(drop_id, summary: dict) -> None:
    payload = dict(summary) if summary else {}
    payload.update(
        {
            "type": "health_update",
            "drop_id": str(drop_id),
            "timestamp": timezone.now().isoformat(),
        }
    )
    _group_send(deaddrop_group_name(drop_id), payload)


def broadcast_health_request(node_id) -> None:
    _group_send(
        node_group_name(node_id),
        {
            "type": "health_request",
            "node_id": str(node_id),
            "timestamp": timezone.now().isoformat(),
        },
    )
