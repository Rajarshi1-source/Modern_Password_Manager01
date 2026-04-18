"""
Pending Fragment Sync Service
=============================

Helpers for enqueueing fragments to offline mesh nodes and flushing the
queue when nodes come back online. Works together with
:class:`mesh_deaddrop.models.PendingFragmentSync`, the websocket consumers
(which notify the device), and the Celery ``flush_pending_sync`` task.

Flow:

1. Distribution service assigns a fragment to a node that is currently
   offline. It calls :func:`enqueue_pending_sync` instead of writing over
   BLE / websocket directly.
2. A periodic Celery task (:func:`mesh_deaddrop.tasks.deaddrop_tasks.flush_pending_sync`)
   wakes up and calls :func:`flush_queue_for_online_nodes`, which batches
   queued syncs per node and broadcasts ``fragment_sync`` events over the
   websocket group — the device pulls the actual payload from the HTTP API.
3. When a device ACKs, it calls the ping endpoint with the delivered sync
   IDs; :func:`mark_delivered_by_device` finalises the rows.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Iterable, List, Optional

from django.db import IntegrityError, transaction
from django.utils import timezone

from ..models import DeadDrop, DeadDropFragment, MeshNode, PendingFragmentSync

logger = logging.getLogger(__name__)


@dataclass
class FlushResult:
    nodes_notified: int = 0
    syncs_touched: int = 0
    syncs_delivered: int = 0
    syncs_failed: int = 0


def enqueue_pending_sync(
    fragment: DeadDropFragment,
    node: MeshNode,
    *,
    encrypted_payload: Optional[bytes] = None,
    payload_hash: str = '',
    expires_in_hours: int = 72,
) -> PendingFragmentSync:
    """Queue a fragment for delivery to ``node``.

    Idempotent against (node, fragment): if a row exists it's reset to
    ``queued`` and the retry counter is preserved so poison-fragments don't
    re-enter the fast path without throttling.
    """

    expires_at = timezone.now() + timedelta(hours=max(1, int(expires_in_hours)))
    defaults = {
        'dead_drop': fragment.dead_drop,
        'status': 'queued',
        'encrypted_payload': bytes(encrypted_payload) if encrypted_payload else b'',
        'payload_hash': payload_hash or '',
        'expires_at': expires_at,
        'next_retry_at': timezone.now(),
        'last_error': '',
    }

    try:
        with transaction.atomic():
            obj, created = PendingFragmentSync.objects.update_or_create(
                node=node,
                fragment=fragment,
                defaults=defaults,
            )
    except IntegrityError:
        obj = PendingFragmentSync.objects.get(node=node, fragment=fragment)
        for k, v in defaults.items():
            setattr(obj, k, v)
        obj.save()
        created = False

    logger.info(
        "enqueue_pending_sync node=%s fragment=%s created=%s",
        node.id,
        fragment.id,
        created,
    )
    return obj


def flush_queue_for_node(node: MeshNode, *, batch_size: int = 25) -> FlushResult:
    """Notify one node of its queued syncs via websocket."""
    if not node.is_online:
        return FlushResult()

    queue = list(
        PendingFragmentSync.objects.filter(node=node, status='queued').order_by('queued_at')[:batch_size]
    )
    if not queue:
        return FlushResult()

    now = timezone.now()
    ids = []
    drop_ids = set()
    for sync in queue:
        sync.status = 'delivering'
        sync.last_attempt_at = now
        sync.retry_count += 1
        sync.save(update_fields=['status', 'last_attempt_at', 'retry_count'])
        ids.append(str(sync.fragment_id))
        drop_ids.add(str(sync.dead_drop_id))

    try:
        from ..consumers import broadcast_fragment_sync

        broadcast_fragment_sync(
            node.id,
            queued_ids=ids,
            drop_id=next(iter(drop_ids)) if len(drop_ids) == 1 else None,
        )
    except Exception:
        logger.exception("flush_pending_sync: broadcast failed for node=%s", node.id)

    return FlushResult(nodes_notified=1, syncs_touched=len(queue))


def flush_queue_for_online_nodes(*, batch_size: int = 25) -> FlushResult:
    """Scan all online nodes with queued work and broadcast sync events."""

    result = FlushResult()
    online_nodes = MeshNode.objects.filter(
        is_online=True,
        pending_syncs__status='queued',
    ).distinct()

    for node in online_nodes:
        partial = flush_queue_for_node(node, batch_size=batch_size)
        result.nodes_notified += partial.nodes_notified
        result.syncs_touched += partial.syncs_touched
    return result


def mark_delivered_by_device(node: MeshNode, sync_ids: Iterable[str]) -> int:
    """Mark syncs as delivered after the device ACKs them."""
    sync_ids = [str(i) for i in (sync_ids or [])]
    if not sync_ids:
        return 0

    updated = PendingFragmentSync.objects.filter(
        node=node,
        id__in=sync_ids,
        status__in=['delivering', 'queued'],
    ).update(
        status='delivered',
        delivered_at=timezone.now(),
    )
    if updated:
        logger.info("mark_delivered_by_device node=%s count=%s", node.id, updated)
    return int(updated)


def expire_stale_syncs() -> int:
    """Mark queued syncs whose ``expires_at`` is past as failed."""
    now = timezone.now()
    stale = PendingFragmentSync.objects.filter(
        status__in=['queued', 'delivering'],
        expires_at__lt=now,
    )
    count = stale.count()
    if count:
        stale.update(status='failed', last_error='expired before delivery')
        logger.info("expire_stale_syncs: expired=%s", count)
    return int(count)


def cancel_syncs_for_dead_drop(dead_drop: DeadDrop) -> int:
    """Cancel outstanding syncs for a cancelled/expired dead drop."""
    count = PendingFragmentSync.objects.filter(
        dead_drop=dead_drop,
        status__in=['queued', 'delivering'],
    ).update(status='cancelled', last_error='dead drop cancelled/expired')
    return int(count)
