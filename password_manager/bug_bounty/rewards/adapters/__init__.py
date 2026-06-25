"""Payout adapter registry.

Adapters are keyed by their ``name``. ``get_payout_adapter`` resolves the
adapter a reward declares (``Reward.adapter``), falling back to ``manual`` for
any unknown name so a stale value can never crash a payout — it just settles
off-platform with no money moved.
"""

from __future__ import annotations

from .base import BasePayoutAdapter, ManualPayoutAdapter, PayoutResult

_DEFAULT = 'manual'

# name -> adapter instance. Register additional adapters (Phase 3) here.
_ADAPTERS: dict[str, BasePayoutAdapter] = {
    adapter.name: adapter for adapter in (ManualPayoutAdapter(),)
}


def get_payout_adapter(name: str | None) -> BasePayoutAdapter:
    """Return the adapter for ``name``, defaulting to the manual (no-money) one."""
    return _ADAPTERS.get(name or _DEFAULT, _ADAPTERS[_DEFAULT])


def available_adapters() -> list[str]:
    """Names of registered payout adapters (for validation/UI)."""
    return list(_ADAPTERS)


__all__ = [
    'BasePayoutAdapter',
    'ManualPayoutAdapter',
    'PayoutResult',
    'get_payout_adapter',
    'available_adapters',
]
