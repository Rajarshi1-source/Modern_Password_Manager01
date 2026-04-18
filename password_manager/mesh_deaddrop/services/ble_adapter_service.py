"""
BLE Adapter Service
===================

Abstraction over Bluetooth Low Energy scanners / advertisers used by the
mesh dead drop feature.

Real handsets will supply a native adapter that talks to the OS radio. The
server needs a well-typed interface so background services (relay selection,
distribution, health probing) can be unit-tested against deterministic
in-memory adapters.

Two implementations ship today:

* :class:`BLEAdapter` — abstract base class defining the contract.
* :class:`SimulatedBLEAdapter` — in-process deterministic simulator backed by
  ``MeshNode`` rows. Scans return nearby nodes with synthetic RSSI derived
  from Haversine distance; advertise / write operations merely log.

A singleton :func:`get_default_adapter` helper returns either a simulator or
a user-supplied adapter registered via :func:`register_default_adapter` so
Celery tasks and services can stay adapter-agnostic.
"""

from __future__ import annotations

import abc
import logging
import math
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class BLEScanResult:
    """Represents one observed BLE advertisement."""

    node_id: str
    ble_address: str
    rssi: int
    observed_at: float = field(default_factory=time.time)
    service_uuids: List[str] = field(default_factory=list)
    manufacturer_data: Optional[bytes] = None

    def to_dict(self) -> Dict:
        return {
            "id": self.node_id,
            "ble_address": self.ble_address,
            "rssi": int(self.rssi),
            "observed_at": self.observed_at,
            "service_uuids": list(self.service_uuids),
        }


@dataclass
class BLETransferResult:
    success: bool
    bytes_transferred: int = 0
    duration_ms: Optional[int] = None
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Adapter interface
# ---------------------------------------------------------------------------

class BLEAdapter(abc.ABC):
    """Abstract BLE adapter contract."""

    @abc.abstractmethod
    def scan(self, timeout_seconds: float = 5.0) -> List[BLEScanResult]:
        """Return all nodes observed within ``timeout_seconds`` seconds."""

    @abc.abstractmethod
    def advertise(self, payload: bytes, interval_ms: int = 1000) -> None:
        """Advertise a payload on the mesh service characteristic."""

    @abc.abstractmethod
    def stop_advertising(self) -> None:
        ...

    @abc.abstractmethod
    def write_fragment(self, target_ble_address: str, fragment: bytes) -> BLETransferResult:
        """Write an encrypted fragment to a peer (GATT write)."""

    # Optional helpers -----------------------------------------------------

    def is_available(self) -> bool:
        """Return True if the underlying radio is ready. Default True."""
        return True


# ---------------------------------------------------------------------------
# Simulated adapter
# ---------------------------------------------------------------------------

class SimulatedBLEAdapter(BLEAdapter):
    """
    Deterministic in-process BLE simulator for tests / dev / ops dashboards.

    The simulator reads live :class:`MeshNode` rows, computes geodesic
    distance from ``observer_location`` and maps that distance to an RSSI
    value using a log-distance path-loss model::

        RSSI(d) = RSSI_ref - 10 * path_loss_exp * log10(d / d_ref)

    Nodes further than ``max_range_m`` are invisible. Writes and advertises
    are recorded to ``self.audit_log`` so tests can assert on them.
    """

    MESH_SERVICE_UUID = "0000dead-0000-1000-8000-00805f9b34fb"

    def __init__(
        self,
        observer_location: Optional[tuple] = None,
        max_range_m: float = 60.0,
        rssi_ref: int = -40,
        ref_distance_m: float = 1.0,
        path_loss_exp: float = 2.5,
        node_source: Optional[Callable[[], Iterable]] = None,
    ) -> None:
        self.observer_location = observer_location  # (lat, lon)
        self.max_range_m = float(max_range_m)
        self.rssi_ref = int(rssi_ref)
        self.ref_distance_m = float(ref_distance_m)
        self.path_loss_exp = float(path_loss_exp)
        self._node_source = node_source
        self._advertising = False
        self._last_payload: Optional[bytes] = None
        self.audit_log: List[Dict] = []

    # -- interface -----------------------------------------------------

    def is_available(self) -> bool:
        return True

    def scan(self, timeout_seconds: float = 5.0) -> List[BLEScanResult]:
        nodes = self._iter_nodes()
        now = time.time()
        results: List[BLEScanResult] = []
        for node in nodes:
            lat = getattr(node, "last_known_latitude", None)
            lon = getattr(node, "last_known_longitude", None)
            if self.observer_location and (lat is None or lon is None):
                continue

            distance = 0.0
            if self.observer_location and lat is not None and lon is not None:
                distance = self._haversine(
                    float(self.observer_location[0]),
                    float(self.observer_location[1]),
                    float(lat),
                    float(lon),
                )
                if distance > self.max_range_m:
                    continue

            rssi = self._rssi_for_distance(max(distance, self.ref_distance_m / 2))
            results.append(
                BLEScanResult(
                    node_id=str(getattr(node, "id", "")),
                    ble_address=getattr(node, "ble_address", "") or "",
                    rssi=rssi,
                    observed_at=now,
                    service_uuids=[self.MESH_SERVICE_UUID],
                )
            )
        return results

    def advertise(self, payload: bytes, interval_ms: int = 1000) -> None:
        self._advertising = True
        self._last_payload = bytes(payload)
        self.audit_log.append(
            {"op": "advertise", "bytes": len(self._last_payload), "interval_ms": interval_ms}
        )

    def stop_advertising(self) -> None:
        self._advertising = False
        self.audit_log.append({"op": "stop_advertising"})

    def write_fragment(self, target_ble_address: str, fragment: bytes) -> BLETransferResult:
        started = time.time()
        size = len(fragment or b"")
        self.audit_log.append(
            {"op": "write", "target": target_ble_address, "bytes": size}
        )
        # Simulator: always succeed.
        return BLETransferResult(
            success=True,
            bytes_transferred=size,
            duration_ms=int((time.time() - started) * 1000),
        )

    # -- internals -----------------------------------------------------

    def _iter_nodes(self):
        if self._node_source is not None:
            return list(self._node_source())

        try:
            from ..models import MeshNode

            return list(
                MeshNode.objects.filter(
                    is_online=True,
                    is_available_for_storage=True,
                )
            )
        except Exception:  # pragma: no cover - defensive (no DB yet)
            return []

    def _rssi_for_distance(self, distance_m: float) -> int:
        distance_m = max(float(distance_m), 0.01)
        loss = 10.0 * self.path_loss_exp * math.log10(distance_m / self.ref_distance_m)
        return int(round(self.rssi_ref - loss))

    @staticmethod
    def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        r = 6371000.0
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
        return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ---------------------------------------------------------------------------
# Adapter registry
# ---------------------------------------------------------------------------

_adapter_lock = threading.Lock()
_default_adapter: Optional[BLEAdapter] = None


def register_default_adapter(adapter: Optional[BLEAdapter]) -> None:
    """Install a process-wide default adapter (use ``None`` to reset)."""
    global _default_adapter
    with _adapter_lock:
        _default_adapter = adapter


def get_default_adapter() -> BLEAdapter:
    """Return the configured adapter or a fresh :class:`SimulatedBLEAdapter`."""
    global _default_adapter
    with _adapter_lock:
        if _default_adapter is None:
            _default_adapter = SimulatedBLEAdapter()
        return _default_adapter
