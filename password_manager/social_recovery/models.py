"""Social Proof-Based Recovery models.

The data model mirrors the shape of :mod:`auth_module.quantum_recovery_models`
but is specialised for *social* web-of-trust recovery rather than quantum
device/biometric shards. Key differences:

* Vouchers may be existing :class:`~django.contrib.auth.models.User` records
  *or* external principals addressed by a W3C DID string + Ed25519 public key.
* Each voucher is bound to a Pedersen commitment (anti-Sybil relationship
  fingerprint) so later attestations require a Schnorr equality proof.
* The audit log maintains an actual previous-row hash chain (``prev_hash`` +
  ``entry_hash``) instead of the per-row SHA-256 used elsewhere.
"""
from __future__ import annotations

import hashlib
import secrets as _secrets
import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


def _make_invitation_token() -> str:
    """Module-level default so migrations can serialize it."""
    return _secrets.token_urlsafe(32)


# ---------------------------------------------------------------------------
# Recovery Circle
# ---------------------------------------------------------------------------


class RecoveryCircle(models.Model):
    """A user's web-of-trust recovery configuration.

    A circle is an (M-of-N) Shamir split of the master recovery secret, where
    each share is encrypted to a :class:`Voucher` public key and released only
    after the voucher submits a valid signature + ZK equality proof.
    """

    STATUS_CHOICES = (
        ("draft", "Draft"),
        ("active", "Active"),
        ("locked", "Locked"),
        ("revoked", "Revoked"),
    )

    circle_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="social_recovery_circles",
    )

    threshold = models.IntegerField(
        validators=[MinValueValidator(2), MaxValueValidator(10)],
        help_text="Minimum number of vouchers required (M in M-of-N)",
    )
    total_vouchers = models.IntegerField(
        validators=[MinValueValidator(2), MaxValueValidator(20)],
        help_text="Total vouchers enrolled (N in M-of-N)",
    )

    # Pedersen commitment of the master recovery seed; 33-byte compressed
    # point on secp256k1 to match zk_proofs/crypto/schnorr.py.
    secret_commitment = models.BinaryField(
        help_text="Pedersen commitment of the master recovery seed (33 bytes)"
    )
    # Key-derivation salt used to bind the circle to the owner's login.
    salt = models.BinaryField(default=bytes)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")

    # Thresholds that act as Sybil defences:
    min_voucher_reputation = models.IntegerField(
        default=0,
        help_text="Minimum ReputationAccount.score required before a voucher "
        "can participate in a live recovery request.",
    )
    min_total_stake = models.IntegerField(
        default=0,
        help_text="Sum of stake units vouchers must collectively commit.",
    )
    cooldown_hours = models.IntegerField(
        default=24,
        validators=[MinValueValidator(0), MaxValueValidator(24 * 30)],
        help_text="Minimum time between consecutive live recovery requests.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    activated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "social_recovery_circle"
        verbose_name = "Social Recovery Circle"
        verbose_name_plural = "Social Recovery Circles"
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"Circle({self.user_id}, {self.status}, {self.threshold}-of-{self.total_vouchers})"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @property
    def is_active(self) -> bool:
        return self.status == "active"

    def active_vouchers(self):
        return self.vouchers.filter(status__in=("accepted", "active"))

    def activate_if_ready(self) -> bool:
        """Flip to ``active`` once every invited voucher has accepted."""
        if self.status != "draft":
            return False
        pending = self.vouchers.filter(status="pending").count()
        accepted = self.vouchers.filter(status__in=("accepted", "active")).count()
        if pending == 0 and accepted >= self.total_vouchers:
            self.status = "active"
            self.activated_at = timezone.now()
            self.save(update_fields=["status", "activated_at", "updated_at"])
            return True
        return False


# ---------------------------------------------------------------------------
# Voucher
# ---------------------------------------------------------------------------


class Voucher(models.Model):
    """A party that holds one shard of the circle's secret."""

    STATUS_CHOICES = (
        ("pending", "Pending Acceptance"),
        ("accepted", "Accepted"),
        ("active", "Active"),
        ("revoked", "Revoked"),
    )

    voucher_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    circle = models.ForeignKey(
        RecoveryCircle, on_delete=models.CASCADE, related_name="vouchers"
    )

    # Identity (at least one of these must be populated).
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="social_voucher_roles",
    )
    did_string = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="W3C DID (e.g. did:key:z...) for external vouchers",
    )
    email = models.EmailField(blank=True, default="")
    display_name = models.CharField(max_length=128, blank=True, default="")

    # Ed25519 public key in ``z...`` multibase form (same shape as
    # decentralized_identity.UserDID.public_key_multibase).
    ed25519_public_key = models.CharField(max_length=128)

    relationship_label = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="Free-form label such as 'spouse', 'lawyer', 'co-founder'.",
    )
    vouch_weight = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Relative weight this voucher contributes toward the quorum.",
    )

    # Encrypted Shamir share + metadata. The share itself is a hex-encoded
    # ``ShamirSecretSharer`` string wrapped with XChaCha20-Poly1305 under a key
    # derived from the voucher's Ed25519 public key (X25519 key agreement).
    encrypted_shard_data = models.BinaryField()
    encryption_metadata = models.JSONField(default=dict, blank=True)
    share_index = models.IntegerField(
        help_text="Shamir share index (x-coordinate).",
        default=1,
    )

    stake_amount = models.IntegerField(
        default=0,
        help_text="Stake committed by the voucher (password_reputation units).",
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    invitation_token = models.CharField(
        max_length=64,
        unique=True,
        default=_make_invitation_token,
    )
    invitation_expires_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "social_recovery_voucher"
        verbose_name = "Social Recovery Voucher"
        verbose_name_plural = "Social Recovery Vouchers"
        unique_together = [("circle", "share_index")]
        indexes = [
            models.Index(fields=["circle", "status"]),
            models.Index(fields=["invitation_token"]),
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"Voucher({self.voucher_id}, {self.status})"

    @property
    def invitation_is_valid(self) -> bool:
        if self.status != "pending":
            return False
        if self.invitation_expires_at and timezone.now() > self.invitation_expires_at:
            return False
        return True


# ---------------------------------------------------------------------------
# Relationship commitment (anti-Sybil edge store)
# ---------------------------------------------------------------------------


class RelationshipCommitment(models.Model):
    """Per-voucher Pedersen commitment bound to the circle.

    At attestation time the voucher must submit a Schnorr equality proof
    linking a fresh commitment to this stored one. This makes it expensive for
    an attacker to impersonate a real voucher: they would need to forge both
    the Ed25519 signature *and* an equality proof for a secret they don't know.
    """

    commitment_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    circle = models.ForeignKey(
        RecoveryCircle,
        on_delete=models.CASCADE,
        related_name="relationship_commitments",
    )
    voucher = models.OneToOneField(
        Voucher, on_delete=models.CASCADE, related_name="relationship_commitment"
    )

    pedersen_commitment = models.BinaryField(
        help_text="33-byte compressed secp256k1 point (C = m*G + r*H)"
    )
    # The blinding factor ``r`` is deterministically derived from ``salt``. We
    # persist the raw salt so the voucher-side attestation flow can rebuild r1
    # and produce a valid Schnorr equality proof. The *message* component of
    # this commitment is public (a fingerprint of the voucher's public key plus
    # circle id), so knowledge of r does not reveal any secret -- it only lets
    # the legitimate voucher prove binding. An independent ``salt_hash`` is
    # still kept as an audit reference.
    salt = models.BinaryField(default=bytes, blank=True)
    salt_hash = models.CharField(max_length=64)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "social_recovery_relationship_commitment"


# ---------------------------------------------------------------------------
# Recovery request + attestations
# ---------------------------------------------------------------------------


class SocialRecoveryRequest(models.Model):
    """A live attempt to reconstruct the secret via voucher quorum."""

    STATUS_CHOICES = (
        ("pending", "Pending Voucher Approvals"),
        ("approved", "Approved"),
        ("denied", "Denied"),
        ("expired", "Expired"),
        ("cancelled", "Cancelled"),
        ("completed", "Completed"),
    )

    request_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    circle = models.ForeignKey(
        RecoveryCircle, on_delete=models.CASCADE, related_name="requests"
    )
    initiator_email = models.EmailField(blank=True, default="")

    # Context of the request for audit + risk scoring.
    initiator_ip = models.GenericIPAddressField(null=True, blank=True)
    device_fingerprint = models.CharField(max_length=128, blank=True, default="")
    geo = models.JSONField(default=dict, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    required_approvals = models.IntegerField()
    received_approvals = models.IntegerField(default=0)

    total_weight = models.IntegerField(default=0)
    total_stake_committed = models.IntegerField(default=0)

    challenge_nonce = models.CharField(max_length=64)
    risk_score = models.FloatField(default=0.0)

    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "social_recovery_request"
        indexes = [
            models.Index(fields=["circle", "status"]),
            models.Index(fields=["status", "expires_at"]),
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"RecoveryRequest({self.request_id}, {self.status})"

    @property
    def is_expired(self) -> bool:
        return self.status == "pending" and timezone.now() > self.expires_at


class VouchAttestation(models.Model):
    """A voucher's decision on a :class:`SocialRecoveryRequest`."""

    DECISION_CHOICES = (
        ("approve", "Approve"),
        ("deny", "Deny"),
    )

    attestation_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request = models.ForeignKey(
        SocialRecoveryRequest, on_delete=models.CASCADE, related_name="attestations"
    )
    voucher = models.ForeignKey(
        Voucher, on_delete=models.CASCADE, related_name="attestations"
    )

    ed25519_signature = models.BinaryField()
    signed_message = models.BinaryField()

    # Schnorr equality proof linking a fresh commitment to the stored
    # RelationshipCommitment for this voucher.
    zk_proof_T = models.BinaryField(null=True, blank=True)
    zk_proof_s = models.BinaryField(null=True, blank=True)
    fresh_commitment = models.BinaryField(null=True, blank=True)

    # Optional ``SocialVouch`` VC linking this attestation to an issuer.
    vc_id = models.UUIDField(null=True, blank=True)

    decision = models.CharField(max_length=16, choices=DECISION_CHOICES)
    stake_committed = models.IntegerField(default=0)

    attested_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default="")

    class Meta:
        db_table = "social_recovery_attestation"
        unique_together = [("request", "voucher")]
        indexes = [
            models.Index(fields=["request", "decision"]),
        ]


# ---------------------------------------------------------------------------
# Audit log (true hash-chained)
# ---------------------------------------------------------------------------


class SocialRecoveryAuditLog(models.Model):
    """Tamper-evident append-only audit log for the social_recovery app.

    Each row stores a hash that commits to the previous row's ``entry_hash``
    plus this row's payload. The very first row carries ``prev_hash = b""``.
    """

    EVENT_CHOICES = (
        ("circle_created", "Circle Created"),
        ("voucher_invited", "Voucher Invited"),
        ("voucher_accepted", "Voucher Accepted"),
        ("voucher_revoked", "Voucher Revoked"),
        ("request_initiated", "Request Initiated"),
        ("attestation_recorded", "Attestation Recorded"),
        ("attestation_rejected", "Attestation Rejected"),
        ("request_completed", "Request Completed"),
        ("request_cancelled", "Request Cancelled"),
        ("stake_slashed", "Stake Slashed"),
    )

    entry_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="social_recovery_audit_logs",
    )
    circle = models.ForeignKey(
        RecoveryCircle,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )

    event_type = models.CharField(max_length=32, choices=EVENT_CHOICES)
    event_data = models.JSONField(default=dict, blank=True)

    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default="")

    prev_hash = models.BinaryField(default=bytes)
    entry_hash = models.BinaryField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "social_recovery_audit_log"
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["event_type", "-created_at"]),
        ]

    @staticmethod
    def compute_entry_hash(
        *,
        prev_hash: bytes,
        user_id: int | None,
        circle_id: uuid.UUID | None,
        event_type: str,
        event_data: dict,
        created_at_iso: str,
    ) -> bytes:
        import json

        payload = json.dumps(
            {
                "u": user_id,
                "c": str(circle_id) if circle_id else None,
                "e": event_type,
                "d": event_data,
                "t": created_at_iso,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        h = hashlib.sha256()
        h.update(bytes(prev_hash or b""))
        h.update(payload)
        return h.digest()
