"""DID method implementations: did:key (Ed25519) and did:web.

We deliberately avoid the third-party ``multiformats`` dependency and use a
minimal in-module base58btc implementation plus the Ed25519 multicodec prefix
``0xed 0x01`` so the resulting identifier is compatible with widely-deployed
libraries (e.g. ``@noble/ed25519`` + ``multiformats`` in the browser).
"""

from __future__ import annotations

import base64
import json
import logging
import secrets
from typing import Dict, Optional, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)
from django.conf import settings
from django.db import transaction

from ..crypto_utils import decrypt_bytes, encrypt_bytes
from ..models import IssuerKey, UserDID

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Base58btc (bitcoin alphabet) encoding - small helper, no external dep
# ---------------------------------------------------------------------------

_B58_ALPHABET = b"123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def _b58encode(data: bytes) -> str:
    n = int.from_bytes(data, "big")
    out = bytearray()
    while n > 0:
        n, rem = divmod(n, 58)
        out.append(_B58_ALPHABET[rem])
    # Preserve leading zero bytes (each encoded as '1').
    pad = 0
    for b in data:
        if b == 0:
            pad += 1
        else:
            break
    return ("1" * pad) + out[::-1].decode("ascii")


def _b58decode(text: str) -> bytes:
    n = 0
    for ch in text:
        idx = _B58_ALPHABET.find(ch.encode("ascii"))
        if idx < 0:
            raise ValueError(f"Invalid base58 character: {ch}")
        n = n * 58 + idx
    raw = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    pad = 0
    for ch in text:
        if ch == "1":
            pad += 1
        else:
            break
    return b"\x00" * pad + raw


# Multicodec prefix for Ed25519 public keys per the multicodec table.
_ED25519_MULTICODEC_PREFIX = b"\xed\x01"


def multibase_encode_ed25519_pub(public_key_bytes: bytes) -> str:
    """Return the ``z...`` multibase identifier for an Ed25519 public key."""
    if len(public_key_bytes) != 32:
        raise ValueError("Ed25519 public key must be 32 bytes")
    return "z" + _b58encode(_ED25519_MULTICODEC_PREFIX + public_key_bytes)


def multibase_decode(multibase: str) -> bytes:
    if not multibase or multibase[0] != "z":
        raise ValueError("Only base58btc multibase ('z...') is supported")
    raw = _b58decode(multibase[1:])
    if not raw.startswith(_ED25519_MULTICODEC_PREFIX):
        raise ValueError("Not an Ed25519 multibase key")
    return raw[len(_ED25519_MULTICODEC_PREFIX) :]


# ---------------------------------------------------------------------------
# did:key
# ---------------------------------------------------------------------------


def create_did_key_from_public_key(public_key_bytes: bytes) -> str:
    """Return the ``did:key:z...`` identifier for an Ed25519 public key."""
    return "did:key:" + multibase_encode_ed25519_pub(public_key_bytes)


def public_key_from_did_key(did: str) -> bytes:
    prefix = "did:key:"
    if not did.startswith(prefix):
        raise ValueError("Not a did:key identifier")
    return multibase_decode(did[len(prefix) :])


def did_document_for_did_key(did: str) -> Dict:
    pub = public_key_from_did_key(did)
    kid = f"{did}#{multibase_encode_ed25519_pub(pub)}"
    return {
        "@context": [
            "https://www.w3.org/ns/did/v1",
            "https://w3id.org/security/suites/ed25519-2020/v1",
        ],
        "id": did,
        "verificationMethod": [
            {
                "id": kid,
                "type": "Ed25519VerificationKey2020",
                "controller": did,
                "publicKeyMultibase": multibase_encode_ed25519_pub(pub),
            }
        ],
        "authentication": [kid],
        "assertionMethod": [kid],
    }


# ---------------------------------------------------------------------------
# did:web
# ---------------------------------------------------------------------------


def did_document_for_did_web(issuer_key: IssuerKey) -> Dict:
    did_web = f"did:web:{issuer_key.did_web_identifier}" if issuer_key.did_web_identifier else ""
    if not did_web:
        did_web = getattr(settings, "DID_ISSUER_DID", "did:web:api.securevault.com")
    kid = f"{did_web}#{issuer_key.kid}"
    return {
        "@context": [
            "https://www.w3.org/ns/did/v1",
            "https://w3id.org/security/suites/ed25519-2020/v1",
        ],
        "id": did_web,
        "verificationMethod": [
            {
                "id": kid,
                "type": "Ed25519VerificationKey2020",
                "controller": did_web,
                "publicKeyMultibase": issuer_key.public_key_multibase,
            }
        ],
        "authentication": [kid],
        "assertionMethod": [kid],
    }


def resolve_did(did: str) -> Dict:
    """Resolve a DID to its DID Document."""
    if did.startswith("did:key:"):
        return did_document_for_did_key(did)
    if did.startswith("did:web:"):
        key = IssuerKey.objects.filter(is_active=True).first()
        if key is None:
            raise ValueError("No active issuer key")
        return did_document_for_did_web(key)
    raise ValueError(f"Unsupported DID method in: {did}")


# ---------------------------------------------------------------------------
# Issuer key lifecycle
# ---------------------------------------------------------------------------


@transaction.atomic
def ensure_issuer_key() -> IssuerKey:
    """Return the active issuer key, creating one on first use."""
    key = IssuerKey.objects.filter(is_active=True).first()
    if key is not None:
        return key
    private = Ed25519PrivateKey.generate()
    public_bytes = private.public_key().public_bytes(
        Encoding.Raw, PublicFormat.Raw
    )
    private_bytes = private.private_bytes(
        Encoding.Raw, PrivateFormat.Raw, NoEncryption()
    )
    kid = "vault-issuer-" + secrets.token_hex(4)
    did_web_host = getattr(settings, "DID_ISSUER_DID", "did:web:api.securevault.com")
    did_web_identifier = did_web_host[len("did:web:") :] if did_web_host.startswith("did:web:") else did_web_host
    key = IssuerKey.objects.create(
        kid=kid,
        did_web_identifier=did_web_identifier,
        public_key_multibase=multibase_encode_ed25519_pub(public_bytes),
        private_key_encrypted=encrypt_bytes(private_bytes),
    )
    return key


def load_issuer_private_key(key: IssuerKey) -> Ed25519PrivateKey:
    raw = decrypt_bytes(key.private_key_encrypted)
    return Ed25519PrivateKey.from_private_bytes(raw)


# ---------------------------------------------------------------------------
# User DID registration + signature verification
# ---------------------------------------------------------------------------


def register_user_did(
    user, did_string: str, public_key_multibase: str, make_primary: bool = True
) -> UserDID:
    # Validate that the declared multibase matches the DID. ``did:key`` binds
    # the key into the identifier itself, so the two must agree exactly.
    if did_string.startswith("did:key:"):
        expected = "did:key:" + public_key_multibase
        if expected != did_string:
            raise ValueError("did_string does not match publicKeyMultibase")
    elif did_string.startswith("did:web:"):
        # ``did:web`` resolves its verification method over HTTPS; a user
        # cannot assert a key for an arbitrary domain without controlling it.
        # Require the domain to be on an allow-list so a user cannot register,
        # say, ``did:web:example.com`` with a self-chosen public key and have
        # the rest of the app treat them as that issuer.
        web_identifier = did_string[len("did:web:"):]
        allowed = set(
            getattr(settings, "DID_WEB_REGISTRATION_ALLOWLIST", []) or []
        )
        if not allowed or web_identifier not in allowed:
            raise ValueError(
                "did:web domain is not in DID_WEB_REGISTRATION_ALLOWLIST; "
                "resolve the DID document over HTTPS and register the bound "
                "key server-side instead."
            )
        # When the host *is* allow-listed, require the declared key to match
        # an active ``IssuerKey`` row for that identifier.
        if not IssuerKey.objects.filter(
            is_active=True,
            did_web_identifier=web_identifier,
            public_key_multibase=public_key_multibase,
        ).exists():
            raise ValueError(
                "publicKeyMultibase does not match any active IssuerKey for "
                "this did:web identifier"
            )
    else:
        raise ValueError(f"Unsupported DID method in: {did_string}")

    with transaction.atomic():
        if make_primary:
            UserDID.objects.filter(user=user, is_primary=True).update(is_primary=False)
        obj, _ = UserDID.objects.update_or_create(
            user=user,
            did_string=did_string,
            defaults={
                "public_key_multibase": public_key_multibase,
                "is_primary": make_primary,
            },
        )
    return obj


def verify_signature(did: str, message: bytes, signature: bytes) -> bool:
    """Verify an Ed25519 signature by the DID's public key."""
    try:
        pub_bytes = public_key_from_did_key(did)
    except ValueError:
        # did:web or other - only did:key supported for user signatures in v1
        return False
    try:
        Ed25519PublicKey.from_public_bytes(pub_bytes).verify(signature, message)
        return True
    except InvalidSignature:
        return False
    except Exception:  # pragma: no cover - defensive
        logger.exception("signature verification raised")
        return False
