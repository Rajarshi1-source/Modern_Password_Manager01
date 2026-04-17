"""Wearable provider adapters.

Each provider returns sleep observations that are persisted via the
:mod:`circadian_totp.services.circadian_totp_service` module. Only
``FitbitAdapter`` has a live OAuth integration by default; the rest support
server-side ingestion pushed by native mobile clients (Apple Health) or are
ready to be wired once API credentials are configured.
"""

from __future__ import annotations

from typing import Type

from .base import BaseAdapter
from .apple_health import AppleHealthAdapter
from .fitbit import FitbitAdapter
from .google_fit import GoogleFitAdapter
from .manual import ManualAdapter
from .oura import OuraAdapter

_REGISTRY: dict[str, Type[BaseAdapter]] = {
    "fitbit": FitbitAdapter,
    "apple_health": AppleHealthAdapter,
    "oura": OuraAdapter,
    "google_fit": GoogleFitAdapter,
    "manual": ManualAdapter,
}


def get_adapter(provider: str) -> BaseAdapter:
    try:
        cls = _REGISTRY[provider]
    except KeyError as exc:
        raise ValueError(f"Unknown wearable provider: {provider}") from exc
    return cls()


__all__ = [
    "BaseAdapter",
    "AppleHealthAdapter",
    "FitbitAdapter",
    "GoogleFitAdapter",
    "ManualAdapter",
    "OuraAdapter",
    "get_adapter",
]
