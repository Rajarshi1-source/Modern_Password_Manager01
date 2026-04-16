"""
Cryptographic plausible-deniability envelope (hidden-volume primitive).

This package implements the ``HiddenVaultBlob v1`` container format
defined in :doc:`SPEC.md`. It has no Django dependencies on purpose so
it can be used from management commands, tests, and the Celery worker
without importing the web stack.

Typical usage::

    from hidden_vault.envelope import encode, decode, TIERS

    blob = encode(
        real_password="MyR3alP@ss",
        real_payload=real_vault_json.encode(),
        decoy_password="MyF4keP@ss",
        decoy_payload=decoy_vault_json.encode(),
        tier=TIERS.TIER0_32K,
    )

    # Later, with only one of the two passwords:
    slot_index, plaintext = decode(blob, "MyR3alP@ss")

See :mod:`hidden_vault.envelope` for details.
"""

from .envelope import (
    TIERS,
    HiddenVaultError,
    WrongPasswordError,
    MalformedBlobError,
    PayloadTooLargeError,
    decode,
    encode,
    encode_deterministic,
    tier_bytes,
    slot_payload_len,
)

__all__ = [
    "TIERS",
    "HiddenVaultError",
    "WrongPasswordError",
    "MalformedBlobError",
    "PayloadTooLargeError",
    "decode",
    "encode",
    "encode_deterministic",
    "tier_bytes",
    "slot_payload_len",
]
