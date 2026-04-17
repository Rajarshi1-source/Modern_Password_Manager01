"""Models for decentralized identity + W3C Verifiable Credentials.

Design principles:
* Private keys for user DIDs are NEVER persisted server-side. We only store
  the public key / DID identifier.
* Issuer private key material is encrypted at rest with a Fernet key derived
  from ``SECRET_KEY`` via :mod:`.crypto_utils`.
* Every VC is emitted as a JWT (compact JWS) for broad tooling compatibility
  and also as a canonical JSON-LD document for verifiers that prefer linked
  data proofs.
"""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


VC_STATUS_CHOICES = (
    ("active", "Active"),
    ("revoked", "Revoked"),
    ("suspended", "Suspended"),
)


KEY_ALGORITHM_CHOICES = (
    ("Ed25519", "Ed25519"),
)


class IssuerKey(models.Model):
    """Server-side signing key used to issue Verifiable Credentials."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kid = models.CharField(max_length=128, unique=True)
    did_web_identifier = models.CharField(max_length=255, blank=True, default="")
    public_key_multibase = models.CharField(max_length=128)
    private_key_encrypted = models.BinaryField()
    algorithm = models.CharField(
        max_length=16, choices=KEY_ALGORITHM_CHOICES, default="Ed25519"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    rotated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"IssuerKey<{self.kid} {self.algorithm} active={self.is_active}>"


class UserDID(models.Model):
    """A DID owned by an end user. Private key never leaves the client."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="dids",
    )
    did_string = models.CharField(max_length=255, unique=True)
    public_key_multibase = models.CharField(max_length=128)
    algorithm = models.CharField(
        max_length=16, choices=KEY_ALGORITHM_CHOICES, default="Ed25519"
    )
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["user", "is_primary"])]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"UserDID<{self.did_string}>"


class CredentialSchema(models.Model):
    """A JSON-Schema describing the ``credentialSubject`` of a VC type."""

    schema_id = models.CharField(max_length=128, primary_key=True)
    name = models.CharField(max_length=128)
    version = models.CharField(max_length=32, default="1.0.0")
    json_schema = models.JSONField(default=dict)
    context_urls = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.name}@{self.version}"


class VerifiableCredential(models.Model):
    """A credential issued by this vault to a user's DID."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subject_did = models.CharField(max_length=255, db_index=True)
    issuer_did = models.CharField(max_length=255)
    schema = models.ForeignKey(
        CredentialSchema, on_delete=models.PROTECT, related_name="credentials"
    )
    jwt_vc = models.TextField(help_text="Compact JWS VC-JWT.")
    jsonld_vc = models.JSONField(default=dict)
    status = models.CharField(
        max_length=16, choices=VC_STATUS_CHOICES, default="active"
    )
    issued_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    revocation_list_index = models.PositiveIntegerField(null=True, blank=True)
    storage_refs = models.JSONField(
        default=dict,
        help_text="{'ipfs_cid', 'arweave_tx', 'chain_anchor_tx'}",
    )

    class Meta:
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["subject_did", "status"]),
        ]
        ordering = ["-issued_at"]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"VC<{self.schema_id} {self.subject_did} {self.status}>"


class VCPresentation(models.Model):
    """Verifiable Presentation asserted by a holder to a relying party."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    holder_did = models.CharField(max_length=255, db_index=True)
    presented_to = models.CharField(max_length=255, blank=True, default="")
    vp_jwt = models.TextField(blank=True, default="")
    zk_proof_ref = models.CharField(max_length=128, blank=True, default="")
    disclosed_fields = models.JSONField(default=list)
    verified = models.BooleanField(default=False)
    verification_errors = models.JSONField(default=list)
    presented_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"VP<{self.holder_did} verified={self.verified}>"


class SignInChallenge(models.Model):
    """Nonce issued for the Sign-in-with-DID flow."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    did_string = models.CharField(max_length=255, db_index=True)
    nonce = models.CharField(max_length=128, unique=True)
    expires_at = models.DateTimeField()
    consumed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["did_string", "consumed"])]


class RevocationList(models.Model):
    """StatusList2021-compatible revocation list."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    list_id = models.CharField(max_length=64, unique=True)
    size = models.PositiveIntegerField(default=131072)
    encoded_list = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"RevocationList<{self.list_id}>"
