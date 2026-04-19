"""
Relay Trust Service
===================

Maintains the per-node trust score used by the distribution / collection
pipeline and exposes helpers that callers (views, Celery tasks, distribution
service) use to record relay outcomes.

Design
------
Trust is stored on :class:`MeshNode.trust_score` (0.0–1.0). The service
updates it with an **exponentially-weighted moving average (EWMA)** over
observed transfer outcomes, with auxiliary nudges for uptime, latency and
fraud signals::

    trust_new = (1 - alpha) * trust_old + alpha * observation

Observations are in [0.0, 1.0]:

- ``1.0`` for a successful transfer / ping
- ``0.0`` for a failed / timed-out transfer
- Latency-modulated values for slow-but-successful transfers

A dedicated :meth:`record_fraud` method slashes trust sharply (does not use
EWMA) when the node is caught tampering with fragments or replaying old
state — mirrors the social-recovery stake-slash pattern.

The service is intentionally stateless on the Python side: every call
updates the DB row, so it works identically from celery and from web
requests.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from ..models import MeshNode

logger = logging.getLogger(__name__)


@dataclass
class TrustSummary:
    """Snapshot of a node's trust state for API responses."""

    node_id: str
    trust_score: float
    successful_transfers: int
    failed_transfers: int
    total_uptime_hours: float
    is_online: bool
    last_seen: Optional[str]

    @classmethod
    def from_node(cls, node: MeshNode) -> "TrustSummary":
        return cls(
            node_id=str(node.id),
            trust_score=float(node.trust_score),
            successful_transfers=int(node.successful_transfers),
            failed_transfers=int(node.failed_transfers),
            total_uptime_hours=float(node.total_uptime_hours),
            is_online=bool(node.is_online),
            last_seen=node.last_seen.isoformat() if node.last_seen else None,
        )


class RelayTrustService:
    """Maintain EWMA-based trust for relay nodes.

    Alpha controls responsiveness: 0.05 is a reasonable default — a single
    failure nudges trust down by ~5% of the gap; 20 successes needed to
    recover most of the lost trust.
    """

    ALPHA_DEFAULT = 0.05
    ALPHA_FAST = 0.20  # used for fraud / duress signals
    LATENCY_GOOD_MS = 500.0
    LATENCY_BAD_MS = 5000.0
    FRAUD_FLOOR = 0.05

    def __init__(self, alpha: float = ALPHA_DEFAULT) -> None:
        if not 0 < alpha < 1:
            raise ValueError("alpha must be in (0, 1)")
        self.alpha = float(alpha)

    # -- observations --------------------------------------------------

    def record_success(
        self,
        node: MeshNode,
        duration_ms: Optional[int] = None,
        bytes_transferred: Optional[int] = None,
    ) -> TrustSummary:
        observation = self._latency_to_score(duration_ms)
        with transaction.atomic():
            MeshNode.objects.filter(pk=node.pk).update(
                successful_transfers=F("successful_transfers") + 1,
                last_seen=timezone.now(),
            )
            node.refresh_from_db()
            self._apply_ewma(node, observation, alpha=self.alpha)
        logger.debug(
            "relay-trust: success node=%s obs=%.3f new=%.3f",
            node.id,
            observation,
            node.trust_score,
        )
        return TrustSummary.from_node(node)

    def record_failure(
        self,
        node: MeshNode,
        *,
        reason: Optional[str] = None,
    ) -> TrustSummary:
        with transaction.atomic():
            MeshNode.objects.filter(pk=node.pk).update(
                failed_transfers=F("failed_transfers") + 1,
                last_seen=timezone.now(),
            )
            node.refresh_from_db()
            self._apply_ewma(node, 0.0, alpha=self.alpha)
        logger.info(
            "relay-trust: failure node=%s reason=%s new=%.3f",
            node.id,
            reason,
            node.trust_score,
        )
        return TrustSummary.from_node(node)

    def record_ping(self, node: MeshNode, uptime_delta_hours: float = 0.0) -> TrustSummary:
        if uptime_delta_hours < 0:
            uptime_delta_hours = 0.0
        with transaction.atomic():
            updates = {"is_online": True, "last_seen": timezone.now()}
            if uptime_delta_hours:
                MeshNode.objects.filter(pk=node.pk).update(
                    total_uptime_hours=F("total_uptime_hours") + uptime_delta_hours,
                    **updates,
                )
            else:
                MeshNode.objects.filter(pk=node.pk).update(**updates)
            node.refresh_from_db()
            # Mild positive nudge (cap observation at 0.8 so trust doesn't saturate on pings alone)
            self._apply_ewma(node, 0.8, alpha=self.alpha / 2)
        return TrustSummary.from_node(node)

    def record_fraud(self, node: MeshNode, reason: str = "") -> TrustSummary:
        """Hard slash for tamper / replay / signature-failure incidents."""
        with transaction.atomic():
            MeshNode.objects.filter(pk=node.pk).update(
                failed_transfers=F("failed_transfers") + 1,
                is_available_for_storage=False,
            )
            node.refresh_from_db()
            new_score = max(self.FRAUD_FLOOR, node.trust_score * 0.5 - 0.2)
            node.trust_score = float(new_score)
            node.save(update_fields=["trust_score"])
        logger.warning(
            "relay-trust: FRAUD slash node=%s reason=%s new=%.3f",
            node.id,
            reason,
            node.trust_score,
        )
        return TrustSummary.from_node(node)

    def recompute_baseline(self, node: MeshNode) -> TrustSummary:
        """Recompute trust purely from raw counters + uptime bonus (no EWMA)."""
        total = node.successful_transfers + node.failed_transfers
        base = (node.successful_transfers / total) if total else 0.5
        uptime_bonus = min(0.05, (float(node.total_uptime_hours) / 500.0) * 0.05)
        node.trust_score = float(min(1.0, base + uptime_bonus))
        node.save(update_fields=["trust_score"])
        return TrustSummary.from_node(node)

    # -- helpers -------------------------------------------------------

    def _apply_ewma(self, node: MeshNode, observation: float, *, alpha: float) -> None:
        observation = float(max(0.0, min(1.0, observation)))
        previous = float(node.trust_score)
        updated = (1.0 - alpha) * previous + alpha * observation
        updated = float(max(0.0, min(1.0, updated)))
        node.trust_score = updated
        node.save(update_fields=["trust_score"])

    def _latency_to_score(self, duration_ms: Optional[int]) -> float:
        if duration_ms is None:
            return 1.0
        if duration_ms <= self.LATENCY_GOOD_MS:
            return 1.0
        if duration_ms >= self.LATENCY_BAD_MS:
            return 0.6  # success but slow — still positive, strictly above neutral
        # linear interpolation 1.0 -> 0.5 between LATENCY_GOOD_MS and LATENCY_BAD_MS
        span = self.LATENCY_BAD_MS - self.LATENCY_GOOD_MS
        frac = (duration_ms - self.LATENCY_GOOD_MS) / span
        return max(0.5, 1.0 - 0.5 * frac)


# Module-level default for convenience.
relay_trust_service = RelayTrustService()
