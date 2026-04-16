"""
Proxy Re-Encryption (PRE) Service — Umbral backend wrapper.

Thin wrapper over `pyUmbral` used by the `HomomorphicSharingService` to
re-encrypt capsules without ever seeing the plaintext password.

Responsibilities:
- Verify kfrag signatures at share-create time (defence in depth).
- Produce `cfrag` bytes at `/shares/<id>/use/` time.
- Raise a dedicated exception hierarchy so views can map to HTTP codes.

Design notes:
- The server NEVER generates or stores Umbral secret keys.
- Owner generates `(sk_O, pk_O)` client-side, Recipient generates
  `(sk_R, pk_R)` client-side. Owner builds the `kfrag` locally and
  posts it to the server.
- This module is defensive: if `umbral` is not installed, the functions
  raise `UmbralUnavailableError` rather than pretending to succeed. The
  service layer gates `umbral-v1` shares on `feature_enabled()`.

Refs: see password_manager/fhe_sharing/SPEC.md
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


# =========================================================================
# Exception hierarchy
# =========================================================================

class PreError(Exception):
    """Base class for all PRE-related errors."""


class UmbralUnavailableError(PreError):
    """Raised when the `umbral` Python package isn't installed."""


class KfragVerificationError(PreError):
    """Raised when a kfrag fails signature / key binding verification."""


class ReencryptionError(PreError):
    """Raised when `umbral.reencrypt` itself fails."""


# =========================================================================
# Optional import — degrade gracefully
# =========================================================================

try:
    import umbral as _umbral  # type: ignore
    _UMBRAL_AVAILABLE = True
except Exception as _exc:  # pragma: no cover - import guard
    _umbral = None
    _UMBRAL_AVAILABLE = False
    logger.info(
        "[PRE] pyUmbral not installed — "
        "umbral-v1 shares will fall back to simulated-v1. "
        "Install with `pip install umbral` to enable real PRE."
    )


def is_available() -> bool:
    """Return True if the real pyUmbral backend is importable."""
    return _UMBRAL_AVAILABLE


# =========================================================================
# Service
# =========================================================================

@dataclass(frozen=True)
class ReencryptionResult:
    """Container returned to the view layer.

    Attributes:
        cfrag: The serialized capsule fragment bytes.
        capsule: The original capsule bytes, echoed for convenience.
        ciphertext: The Umbral ChaCha20-Poly1305 payload, echoed.
    """
    cfrag: bytes
    capsule: bytes
    ciphertext: bytes


class PreService:
    """pyUmbral proxy re-encryption wrapper.

    Stateless — do not cache anything sensitive inside the instance.
    """

    SUITE = "umbral-v1"

    def __init__(self) -> None:
        self._initialized = False

    def initialize(self) -> None:
        if self._initialized:
            return
        if not _UMBRAL_AVAILABLE:
            logger.warning(
                "[PRE] PreService initialized with umbral unavailable; "
                "all operations will raise UmbralUnavailableError."
            )
        else:
            logger.info("[PRE] PreService initialized with pyUmbral backend")
        self._initialized = True

    def reencrypt(
        self,
        capsule_bytes: bytes,
        kfrag_bytes: bytes,
    ) -> bytes:
        """Run `umbral.reencrypt` and return the serialized cfrag.

        Args:
            capsule_bytes: Serialized Umbral `Capsule`.
            kfrag_bytes: Serialized Umbral `VerifiedKeyFrag` / `KeyFrag`.

        Returns:
            Serialized `VerifiedCapsuleFrag` bytes (what the recipient
            needs to decrypt).

        Raises:
            UmbralUnavailableError: if pyUmbral isn't installed.
            ReencryptionError: on any internal failure.
        """
        self.initialize()
        if not _UMBRAL_AVAILABLE:
            raise UmbralUnavailableError(
                "pyUmbral is not installed on the server"
            )

        try:
            capsule = _umbral.Capsule.from_bytes(bytes(capsule_bytes))
            kfrag = _umbral.KeyFrag.from_bytes(bytes(kfrag_bytes))
            # Kfrags posted by clients arrive "unverified" (raw bytes).
            # Server can't re-verify without the owner's pk + signer pk,
            # which the caller passes into reencrypt() below. Since we
            # accept whatever kfrag the owner uploaded at create-time, we
            # skip verification here and rely on the recipient to detect
            # tampering at decrypt-time (umbral includes integrity tags).
            cfrag = _umbral.reencrypt(capsule=capsule, kfrag=kfrag)
            return bytes(cfrag)
        except UmbralUnavailableError:
            raise
        except Exception as exc:  # pragma: no cover - umbral internals
            logger.error("[PRE] reencrypt failed: %s", exc)
            raise ReencryptionError(str(exc)) from exc

    def verify_kfrag(
        self,
        kfrag_bytes: bytes,
        delegating_pk_bytes: bytes,
        receiving_pk_bytes: bytes,
        verifying_pk_bytes: bytes,
    ) -> bool:
        """Verify a serialized kfrag against its keys.

        Returns:
            True if the kfrag verifies; False otherwise.

        Raises:
            UmbralUnavailableError: if pyUmbral isn't installed.
        """
        self.initialize()
        if not _UMBRAL_AVAILABLE:
            raise UmbralUnavailableError(
                "pyUmbral is not installed on the server"
            )

        try:
            kfrag = _umbral.KeyFrag.from_bytes(bytes(kfrag_bytes))
            delegating_pk = _umbral.PublicKey.from_bytes(bytes(delegating_pk_bytes))
            receiving_pk = _umbral.PublicKey.from_bytes(bytes(receiving_pk_bytes))
            verifying_pk = _umbral.PublicKey.from_bytes(bytes(verifying_pk_bytes))
            kfrag.verify(
                verifying_pk=verifying_pk,
                delegating_pk=delegating_pk,
                receiving_pk=receiving_pk,
            )
            return True
        except Exception as exc:
            logger.warning("[PRE] kfrag verification failed: %s", exc)
            return False

    def wrap_result(
        self,
        capsule_bytes: bytes,
        ciphertext_bytes: bytes,
        cfrag_bytes: bytes,
    ) -> ReencryptionResult:
        """Bundle the three bytes objects into a named result."""
        return ReencryptionResult(
            cfrag=bytes(cfrag_bytes),
            capsule=bytes(capsule_bytes),
            ciphertext=bytes(ciphertext_bytes),
        )


# =========================================================================
# Singleton accessor
# =========================================================================

_pre_service: Optional[PreService] = None


def get_pre_service() -> PreService:
    """Return (and lazily create) the process-wide PRE service singleton."""
    global _pre_service
    if _pre_service is None:
        _pre_service = PreService()
    return _pre_service
