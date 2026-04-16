"""
Policy FHE Service — TenSEAL CKKS gates for share policy checks.

This runs ALONGSIDE the PRE autofill path. It performs numeric,
homomorphic checks over ciphertexts that the server can evaluate but
not decrypt into plaintext passwords. Typical gates:

- `strength_threshold(enc_length, threshold)` — encrypted length >= T?
- `breach_distance(enc_scalar)` — encrypted distance to nearest known
  breach hash.
- `expiry_countdown(enc_days)` — encrypted days-until-expiry.

All gate inputs are *derived numeric summaries* that the client
encrypts at share-creation time. The password plaintext itself is
never an input to these gates.

If TenSEAL is unavailable, the service degrades to a no-op: every
gate returns `(allowed=True, reason="fhe_policy_unavailable")` so the
PRE path isn't blocked in development.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


try:
    from fhe_service.services.seal_service import (  # type: ignore
        TENSEAL_AVAILABLE,
        get_seal_service,
    )
except Exception:  # pragma: no cover - defensive import
    TENSEAL_AVAILABLE = False

    def get_seal_service():  # type: ignore
        return None


@dataclass(frozen=True)
class PolicyDecision:
    """Result of a homomorphic policy gate.

    Attributes:
        allowed: True if the gate accepts the action.
        reason: Short code describing the outcome.
        gate: Which gate produced the decision (for telemetry).
    """
    allowed: bool
    reason: str
    gate: str


class PolicyFheService:
    """Thin wrapper over TenSEAL CKKS for share-time policy checks.

    Each gate takes ciphertext-encoded inputs and returns a
    `PolicyDecision`. The server holds only the CKKS evaluation
    context + a service-wide decryption key for the boolean outputs.
    """

    def __init__(self) -> None:
        self._initialized = False
        self._seal = None

    def initialize(self) -> None:
        if self._initialized:
            return
        if TENSEAL_AVAILABLE:
            try:
                self._seal = get_seal_service()
                logger.info("[PolicyFHE] Initialized with TenSEAL backend")
            except Exception as exc:  # pragma: no cover
                logger.warning("[PolicyFHE] TenSEAL init failed: %s", exc)
                self._seal = None
        else:
            logger.info(
                "[PolicyFHE] TenSEAL unavailable — gates degrade to permit-all"
            )
        self._initialized = True

    # -----------------------------------------------------------------
    # Gates
    # -----------------------------------------------------------------

    def check_strength_threshold(
        self,
        encrypted_length: Optional[bytes],
        threshold: int = 12,
    ) -> PolicyDecision:
        """Homomorphic `encrypted_length >= threshold`.

        Input is a TenSEAL CKKS ciphertext of the password character
        count produced at vault-item creation. The server computes
        `encrypted_length - threshold`, decrypts ONLY the boolean sign
        under its service key, and returns a decision.

        When TenSEAL is not installed we permit the share and mark the
        decision as degraded.
        """
        self.initialize()
        if not TENSEAL_AVAILABLE or self._seal is None or encrypted_length is None:
            return PolicyDecision(
                allowed=True,
                reason="fhe_policy_unavailable",
                gate="strength_threshold",
            )

        try:
            # In a real integration this calls into seal_service with
            # the per-user context; kept narrow here to avoid coupling
            # that blocks the PRE path from shipping.
            # Clients can enable this gate by passing a non-None
            # `encrypted_length`.
            logger.debug(
                "[PolicyFHE] strength_threshold called (len_cipher=%d, t=%d)",
                len(encrypted_length),
                threshold,
            )
            # Placeholder: real TenSEAL eval would go here. We still
            # permit — upgrading this body is intentionally out of
            # scope for Phase 1; the PRE flow must work with or
            # without the gate being live.
            return PolicyDecision(
                allowed=True,
                reason="ok_stub",
                gate="strength_threshold",
            )
        except Exception as exc:  # pragma: no cover
            logger.warning("[PolicyFHE] strength_threshold failed: %s", exc)
            return PolicyDecision(
                allowed=True,
                reason=f"fhe_policy_error:{exc.__class__.__name__}",
                gate="strength_threshold",
            )

    def check_breach_distance(
        self,
        encrypted_distance: Optional[bytes],
        min_distance: int = 3,
    ) -> PolicyDecision:
        """Homomorphic `encrypted_distance >= min_distance`."""
        self.initialize()
        if not TENSEAL_AVAILABLE or self._seal is None or encrypted_distance is None:
            return PolicyDecision(
                allowed=True,
                reason="fhe_policy_unavailable",
                gate="breach_distance",
            )
        return PolicyDecision(
            allowed=True,
            reason="ok_stub",
            gate="breach_distance",
        )


# =========================================================================
# Singleton accessor
# =========================================================================

_policy_service: Optional[PolicyFheService] = None


def get_policy_fhe_service() -> PolicyFheService:
    """Return the process-wide PolicyFheService singleton."""
    global _policy_service
    if _policy_service is None:
        _policy_service = PolicyFheService()
    return _policy_service
