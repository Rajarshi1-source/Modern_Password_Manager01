"""Check registry for the vault self-pentest harness.

To add a check: implement a ``BaseCheck`` subclass in this package and append an
instance to ``CHECK_REGISTRY``. Order here is the order findings are collected
(severity-based sorting happens later in the service).
"""

from __future__ import annotations

from .base import BaseCheck, FindingResult
from .breach_exposure import BreachExposureCheck
from .missing_mfa import MissingMFACheck
from .stale_rotation import StaleRotationCheck
from .weak_reused_passwords import WeakReusedPasswordsCheck

CHECK_REGISTRY: list[BaseCheck] = [
    MissingMFACheck(),
    BreachExposureCheck(),
    WeakReusedPasswordsCheck(),
    StaleRotationCheck(),
]

__all__ = ['BaseCheck', 'FindingResult', 'CHECK_REGISTRY']
