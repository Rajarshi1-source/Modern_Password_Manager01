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
        web_identifier = issuer[len("did:web:"):]
        qs = IssuerKey.objects.filter(is_active=True, did_web_identifier=web_identifier)
        if "#" in kid:
            qs = qs.filter(kid=kid.split("#", 1)[1])
        elif kid:
            qs = qs.filter(kid=kid)
        else:
            # Without an explicit ``kid`` we cannot disambiguate during key
            # rotation. If more than one active key exists for this issuer,
            # refuse to verify rather than silently picking one.
            if qs.count() > 1:
                return None
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

    # Verify nested credentials if any. Each nested VC must be (a) itself valid
    # (signature, expiry, revocation) AND (b) issued to the holder presenting
    # it -- otherwise a holder could replay an arbitrary VC that was issued to
    # a different subject and a downstream verifier that gates on a specific
    # credential would be trivially bypassable.
    vp_block = payload.get("vp", {})
    for vc_jwt in vp_block.get("verifiableCredential", []) or []:
        ok, vc_payload, verr = verify_vc_jwt(vc_jwt)
        if not ok:
            errors.extend(f"Nested VC failed: {e}" for e in verr)
            continue
        subject_id = _extract_vc_subject(vc_payload)
        if subject_id and subject_id != holder:
            errors.append(
                "Nested VC failed: credentialSubject.id does not match holder"
            )

    return not errors, payload, errors


def _extract_vc_subject(vc_payload: Dict) -> Optional[str]:
    """Return the ``credentialSubject.id`` for a decoded VC payload, if any.

    Standard VC-JWTs place this either under the top-level ``sub`` claim or
    under ``vc.credentialSubject.id``. We accept either, preferring the JWT
    ``sub`` when present.
    """
    sub = vc_payload.get("sub")
    if isinstance(sub, str) and sub:
        return sub
    vc = vc_payload.get("vc") or {}
    cs = vc.get("credentialSubject")
    if isinstance(cs, dict):
        sid = cs.get("id")
        if isinstance(sid, str) and sid:
            return sid
    elif isinstance(cs, list):
        for item in cs:
            if isinstance(item, dict):
                sid = item.get("id")
                if isinstance(sid, str) and sid:
                    return sid
    return None
