"""Verifiable Credential issuance.

Emits:
* a **JWT VC** (compact JWS, EdDSA) for maximum compatibility with the W3C
  VC Data Model 1.1 (https://www.w3.org/TR/vc-data-model/#jwt-encoding).
* a parallel **JSON-LD VC** (without an on-the-wire linked data proof in v1
  to avoid the heavy ``pyld`` dependency) suitable for storage + display.
"""

from __future__ import annotations

import base64
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone as _tz
from typing import Dict, List, Optional

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from django.utils import timezone as djtz

from ..models import CredentialSchema, IssuerKey, VerifiableCredential
from . import did_service

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Base64url helpers (keep local: PyJWT uses `jwt`, but we want a minimal JWS)
# ---------------------------------------------------------------------------


def _b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64u_json(obj) -> str:
    return _b64u(json.dumps(obj, separators=(",", ":"), sort_keys=True).encode("utf-8"))


# ---------------------------------------------------------------------------
# Schema bootstrap
# ---------------------------------------------------------------------------


_DEFAULT_SCHEMAS = {
    "VaultAccessCredential": {
        "name": "VaultAccessCredential",
        "json_schema": {
            "type": "object",
            "properties": {
                "tier": {"type": "string"},
                "grantedAt": {"type": "string", "format": "date-time"},
            },
            "required": ["tier"],
        },
    },
    "PasswordStrengthCredential": {
        "name": "PasswordStrengthCredential",
        "json_schema": {
            "type": "object",
            "properties": {"averageScore": {"type": "number"}},
            "required": ["averageScore"],
        },
    },
    "DeviceVerificationCredential": {
        "name": "DeviceVerificationCredential",
        "json_schema": {
            "type": "object",
            "properties": {"deviceId": {"type": "string"}},
            "required": ["deviceId"],
        },
    },
    "PasskeyOwnershipCredential": {
        "name": "PasskeyOwnershipCredential",
        "json_schema": {
            "type": "object",
            "properties": {"credentialId": {"type": "string"}},
            "required": ["credentialId"],
        },
    },
    "CircadianAuthCredential": {
        "name": "CircadianAuthCredential",
        "json_schema": {
            "type": "object",
            "properties": {"deviceId": {"type": "string"}},
            "required": ["deviceId"],
        },
    },
}


def ensure_schema(schema_id: str) -> CredentialSchema:
    """Return a :class:`CredentialSchema` row, creating defaults on first use."""
    tpl = _DEFAULT_SCHEMAS.get(schema_id, {"name": schema_id, "json_schema": {}})
    schema, _ = CredentialSchema.objects.get_or_create(
        schema_id=schema_id,
        defaults={
            "name": tpl["name"],
            "version": "1.0.0",
            "json_schema": tpl["json_schema"],
            "context_urls": [
                "https://www.w3.org/2018/credentials/v1",
                "https://www.w3.org/2018/credentials/examples/v1",
            ],
        },
    )
    return schema


# ---------------------------------------------------------------------------
# Issuance
# ---------------------------------------------------------------------------


def _validate_against_schema(subject: Dict, schema: CredentialSchema) -> None:
    """Lightweight validator: checks ``required`` top-level keys only.

    We intentionally avoid depending on ``jsonschema`` for this module's core
    path; the contract is enforced by the schema's ``required`` list.
    """
    req = schema.json_schema.get("required") if isinstance(schema.json_schema, dict) else None
    if not req:
        return
    missing = [k for k in req if k not in subject]
    if missing:
        raise ValueError(f"Credential subject missing required fields: {missing}")


def _sign_ed25519(private: Ed25519PrivateKey, message: bytes) -> bytes:
    return private.sign(message)


def _build_jwt_vc(
    issuer_did: str,
    subject_did: str,
    schema: CredentialSchema,
    credential_subject: Dict,
    kid: str,
    private_key: Ed25519PrivateKey,
    expires_at: Optional[datetime],
) -> str:
    now = int(djtz.now().timestamp())
    vc_id = f"urn:uuid:{uuid.uuid4()}"
    payload = {
        "iss": issuer_did,
        "sub": subject_did,
        "jti": vc_id,
        "nbf": now,
        "iat": now,
        "vc": {
            "@context": schema.context_urls
            or ["https://www.w3.org/2018/credentials/v1"],
            "id": vc_id,
            "type": ["VerifiableCredential", schema.schema_id],
            "issuer": issuer_did,
            "issuanceDate": datetime.fromtimestamp(now, tz=_tz.utc).isoformat(),
            "credentialSubject": {"id": subject_did, **credential_subject},
        },
    }
    if expires_at is not None:
        exp_ts = int(expires_at.timestamp())
        payload["exp"] = exp_ts
        payload["vc"]["expirationDate"] = expires_at.astimezone(_tz.utc).isoformat()
    header = {"alg": "EdDSA", "typ": "JWT", "kid": kid}
    signing_input = f"{_b64u_json(header)}.{_b64u_json(payload)}".encode("ascii")
    sig = _sign_ed25519(private_key, signing_input)
    return signing_input.decode("ascii") + "." + _b64u(sig)


def _build_jsonld_vc(
    issuer_did: str,
    subject_did: str,
    schema: CredentialSchema,
    credential_subject: Dict,
    issued_at: datetime,
    expires_at: Optional[datetime],
) -> Dict:
    doc = {
        "@context": schema.context_urls
        or ["https://www.w3.org/2018/credentials/v1"],
        "id": f"urn:uuid:{uuid.uuid4()}",
        "type": ["VerifiableCredential", schema.schema_id],
        "issuer": issuer_did,
        "issuanceDate": issued_at.astimezone(_tz.utc).isoformat(),
        "credentialSubject": {"id": subject_did, **credential_subject},
    }
    if expires_at is not None:
        doc["expirationDate"] = expires_at.astimezone(_tz.utc).isoformat()
    return doc


def issue_credential(
    subject_did: str,
    schema_id: str,
    credential_subject: Dict,
    validity_days: int = 365,
) -> VerifiableCredential:
    """Mint a VC and persist it. Does **not** fan out to storage backends -
    that is done asynchronously via :mod:`decentralized_identity.tasks`.
    """
    schema = ensure_schema(schema_id)
    _validate_against_schema(credential_subject, schema)

    key = did_service.ensure_issuer_key()
    from django.conf import settings as _settings

    issuer_did = getattr(
        _settings, "DID_ISSUER_DID", "did:web:api.securevault.com"
    )
    kid = f"{issuer_did}#{key.kid}"

    issued_at = djtz.now()
    expires_at = issued_at + timedelta(days=validity_days) if validity_days else None

    private_key = did_service.load_issuer_private_key(key)
    jwt_vc = _build_jwt_vc(
        issuer_did=issuer_did,
        subject_did=subject_did,
        schema=schema,
        credential_subject=credential_subject,
        kid=kid,
        private_key=private_key,
        expires_at=expires_at,
    )
    jsonld_vc = _build_jsonld_vc(
        issuer_did=issuer_did,
        subject_did=subject_did,
        schema=schema,
        credential_subject=credential_subject,
        issued_at=issued_at,
        expires_at=expires_at,
    )

    vc = VerifiableCredential.objects.create(
        subject_did=subject_did,
        issuer_did=issuer_did,
        schema=schema,
        jwt_vc=jwt_vc,
        jsonld_vc=jsonld_vc,
        status="active",
        expires_at=expires_at,
    )
    logger.info(
        "Issued VC id=%s schema=%s subject=%s", vc.id, schema_id, subject_did
    )
    return vc
