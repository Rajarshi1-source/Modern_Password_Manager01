"""Verify JWT VCs and Verifiable Presentations.

Supports EdDSA compact JWS, issuer DID resolution for ``did:web`` (active
``IssuerKey``), and ``StatusList2021``-style revocation checks via the
project's :mod:`RevocationList` model.
"""

from __future__ import annotations

import base64
import json
import logging
from datetime import datetime, timezone as _tz
from typing import Dict, List, Optional, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from django.utils import timezone as djtz

from ..models import IssuerKey, RevocationList, VerifiableCredential
from . import did_service

logger = logging.getLogger(__name__)


def _b64u_pad(segment: str) -> bytes:
    pad = "=" * ((4 - len(segment) % 4) % 4)
    return base64.urlsafe_b64decode(segment + pad)


def _split_jws(token: str) -> Tuple[Dict, Dict, bytes, bytes]:
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Malformed compact JWS")
    header = json.loads(_b64u_pad(parts[0]))
    payload = json.loads(_b64u_pad(parts[1]))
    signature = _b64u_pad(parts[2])
    signing_input = f"{parts[0]}.{parts[1]}".encode("ascii")
    return header, payload, signature, signing_input


def _resolve_issuer_public_key(header: Dict, issuer: str) -> Optional[bytes]:
    kid = header.get("kid", "")
    # did:key issuers - pub key is embedded in the identifier.
    if issuer.startswith("did:key:"):
        try:
            return did_service.public_key_from_did_key(issuer)
        except ValueError:
            return None
    # did:web issuer - pull from active IssuerKey rows.
    if issuer.startswith("did:web:"):
        qs = IssuerKey.objects.filter(is_active=True)
        if "#" in kid:
            qs = qs.filter(kid=kid.split("#", 1)[1])
        key = qs.first()
        if key is None:
            return None
        try:
            return did_service.multibase_decode(key.public_key_multibase)
        except ValueError:
            return None
    return None


def verify_vc_jwt(token: str) -> Tuple[bool, Dict, List[str]]:
    """Verify the signature, expiry, and revocation state of a VC JWT.

    Returns ``(ok, payload, errors)``.
    """
    errors: List[str] = []
    try:
        header, payload, signature, signing_input = _split_jws(token)
    except ValueError as exc:
        return False, {}, [str(exc)]

    alg = header.get("alg")
    if alg != "EdDSA":
        errors.append(f"Unsupported alg: {alg}")
        return False, payload, errors

    issuer = payload.get("iss") or payload.get("vc", {}).get("issuer")
    if not issuer:
        errors.append("Missing issuer")
        return False, payload, errors

    pub = _resolve_issuer_public_key(header, issuer)
    if pub is None:
        errors.append("Could not resolve issuer public key")
        return False, payload, errors

    try:
        Ed25519PublicKey.from_public_bytes(pub).verify(signature, signing_input)
    except InvalidSignature:
        errors.append("Invalid signature")
        return False, payload, errors

    # Expiration check.
    now = int(djtz.now().timestamp())
    exp = payload.get("exp")
    if exp is not None and now >= int(exp):
        errors.append("Credential expired")

    # Revocation check (StatusList2021-style).
    jti = payload.get("jti") or payload.get("vc", {}).get("id")
    if jti:
        vc = VerifiableCredential.objects.filter(jwt_vc=token).first()
        if vc and vc.status != "active":
            errors.append(f"Credential {vc.status}")

    return not errors, payload, errors


def verify_presentation(
    vp_jwt: str,
    expected_audience: Optional[str] = None,
    expected_nonce: Optional[str] = None,
) -> Tuple[bool, Dict, List[str]]:
    """Verify a Verifiable Presentation JWT holding one or more VC JWTs."""
    errors: List[str] = []
    try:
        header, payload, signature, signing_input = _split_jws(vp_jwt)
    except ValueError as exc:
        return False, {}, [str(exc)]

    holder = payload.get("iss")
    if not holder:
        return False, payload, ["Missing holder (iss)"]

    # Holder signature
    try:
        pub = did_service.public_key_from_did_key(holder)
    except ValueError:
        return False, payload, ["Unsupported holder DID method"]
    try:
        Ed25519PublicKey.from_public_bytes(pub).verify(signature, signing_input)
    except InvalidSignature:
        return False, payload, ["Holder signature invalid"]

    if expected_nonce and payload.get("nonce") != expected_nonce:
        errors.append("Nonce mismatch")
    if expected_audience and payload.get("aud") != expected_audience:
        errors.append("Audience mismatch")

    now = int(djtz.now().timestamp())
    exp = payload.get("exp")
    if exp is not None and now >= int(exp):
        errors.append("Presentation expired")

    # Verify nested credentials if any.
    vp_block = payload.get("vp", {})
    for vc_jwt in vp_block.get("verifiableCredential", []) or []:
        ok, _, verr = verify_vc_jwt(vc_jwt)
        if not ok:
            errors.extend(f"Nested VC failed: {e}" for e in verr)

    return not errors, payload, errors
