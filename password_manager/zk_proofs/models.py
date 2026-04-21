"""
Persistence for ZK commitments, verification attempts, and multi-party
verification sessions.

``ZKCommitment`` stores one commitment per ``(user, scope_type, scope_id, scheme)``
tuple. Clients may update the stored commitment (e.g. on password rotation);
uniqueness prevents accidental duplicates.

``ZKVerificationAttempt`` is an append-only audit log of every verification
request. Useful for compliance reviews and debugging.

``ZKSession`` / ``ZKSessionParticipant`` model a multi-party verification
ceremony: an owner publishes a reference commitment and invites N other users
(via one-time tokens) to prove that their local commitment hides the same
secret. Each participant's proof is verified independently against the
reference, so no pairwise cross-user correlation is required and the session
owner's password is never revealed.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


def _commitment_fingerprint(blob: bytes) -> str:
    """Return a hex SHA-256 of a commitment payload for uniqueness indexing.

    ``BinaryField`` can't be part of a portable ``UniqueConstraint`` (MySQL
    BLOB columns require an index length; SQLite comparison semantics also
    differ). Indexing a short hex digest of the bytes gives us the same
    per-(user, commitment) uniqueness guarantee without vendor-specific DDL.
    """
    return hashlib.sha256(bytes(blob or b"")).hexdigest()


class ZKCommitment(models.Model):
    SCOPE_VAULT_ITEM = "vault_item"
    SCOPE_VAULT_BACKUP = "vault_backup"
    SCOPE_USER_PASSWORD = "user_password"

    SCOPE_CHOICES = [
        (SCOPE_VAULT_ITEM, "Vault Item"),
        (SCOPE_VAULT_BACKUP, "Vault Backup"),
        (SCOPE_USER_PASSWORD, "User Password"),
    ]

    SCHEME_COMMITMENT_SCHNORR_V1 = "commitment-schnorr-v1"
    SCHEME_CHOICES = [
        (SCHEME_COMMITMENT_SCHNORR_V1, "Pedersen + Schnorr (secp256k1)"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="zk_commitments",
    )
    scope_type = models.CharField(max_length=32, choices=SCOPE_CHOICES)
    scope_id = models.CharField(
        max_length=128,
        help_text=(
            "Opaque reference to the scoped object "
            "(vault item ID, backup ID, etc.)."
        ),
    )
    commitment = models.BinaryField(
        help_text="Provider-specific commitment payload (SEC1 33-byte point for commitment-schnorr-v1).",
    )
    commitment_fingerprint = models.CharField(
        max_length=64,
        default="",
        db_index=True,
        help_text=(
            "SHA-256 hex of ``commitment``. Used to enforce per-user "
            "uniqueness of commitment bytes, which blocks the D=0 equality-"
            "proof abuse where the same commitment is registered twice and "
            "then 'proven' equal to itself."
        ),
    )
    scheme = models.CharField(
        max_length=32,
        choices=SCHEME_CHOICES,
        default=SCHEME_COMMITMENT_SCHNORR_V1,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "scope_type", "scope_id", "scheme"],
                name="zk_proofs_zkcommitment_unique_scope",
            ),
            # Defence-in-depth against the Schnorr equality-proof degenerate
            # case: if a user could register the same commitment bytes in two
            # scope rows, a forged proof over D = C - C = 0 (point at
            # infinity) could previously verify. ``verify_equality`` now
            # rejects the infinity case explicitly; this constraint also
            # closes the door at write time.
            models.UniqueConstraint(
                fields=["user", "commitment_fingerprint"],
                name="zk_proofs_zkcommitment_unique_bytes",
            ),
        ]
        indexes = [
            models.Index(
                fields=["user", "scope_type"],
                name="zkp_zkco_user_scope_idx",
            ),
            models.Index(
                fields=["user", "-created_at"],
                name="zkp_zkco_user_created_idx",
            ),
        ]
        verbose_name = "ZK commitment"
        verbose_name_plural = "ZK commitments"

    def save(self, *args, **kwargs):
        # Keep ``commitment_fingerprint`` in lock-step with ``commitment``.
        # Deriving the digest inside ``save`` (rather than trusting callers)
        # guarantees the uniqueness constraint can't be bypassed by code
        # that forgets to set the field.
        self.commitment_fingerprint = _commitment_fingerprint(self.commitment)
        return super().save(*args, **kwargs)

    def __str__(self) -> str:  # pragma: no cover - admin helper only
        return f"ZKCommitment({self.scope_type}:{self.scope_id} user={self.user_id})"


class ZKVerificationAttempt(models.Model):
    """Append-only log of every ZK verification the server has performed."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="zk_verification_attempts",
    )
    commitment_a = models.ForeignKey(
        ZKCommitment,
        on_delete=models.CASCADE,
        related_name="verifications_as_a",
    )
    commitment_b = models.ForeignKey(
        ZKCommitment,
        on_delete=models.CASCADE,
        related_name="verifications_as_b",
        null=True,
        blank=True,
    )
    scheme = models.CharField(max_length=32)
    result = models.BooleanField()
    verifier_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="zk_verifications_performed",
        help_text="User who initiated the verification request (may differ from the commitment owner in multi-party flows).",
    )
    error_message = models.CharField(max_length=256, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["user", "-created_at"],
                name="zkp_zkve_user_created_idx",
            ),
            models.Index(
                fields=["result", "-created_at"],
                name="zkp_zkve_result_created_idx",
            ),
        ]
        verbose_name = "ZK verification attempt"
        verbose_name_plural = "ZK verification attempts"

    def __str__(self) -> str:  # pragma: no cover - admin helper only
        return f"ZKVerificationAttempt({self.id}, result={self.result})"


def _default_invite_token() -> str:
    """Random URL-safe invite token (mirrors the shared-folder pattern)."""
    return secrets.token_urlsafe(32)


def _default_session_expiry():
    return timezone.now() + timezone.timedelta(days=7)


class ZKSession(models.Model):
    """
    A multi-party ZK equality ceremony.

    The ``owner`` registers a ``reference_commitment`` (one of their own
    ``ZKCommitment`` rows) and invites other users to prove, via Schnorr
    equality, that their commitment hides the same secret. The ceremony is
    non-interactive from the server's perspective: each invited user
    independently submits a proof; the session's aggregate ``status`` is
    derived from the participant outcomes.
    """

    STATUS_OPEN = "open"
    STATUS_CLOSED = "closed"
    STATUS_EXPIRED = "expired"
    STATUS_CHOICES = [
        (STATUS_OPEN, "Open"),
        (STATUS_CLOSED, "Closed"),
        (STATUS_EXPIRED, "Expired"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="zk_sessions_owned",
    )
    reference_commitment = models.ForeignKey(
        ZKCommitment,
        on_delete=models.CASCADE,
        related_name="sessions_as_reference",
        help_text=(
            "Commitment that invitees will prove equality against. "
            "Must be owned by the session owner."
        ),
    )
    title = models.CharField(max_length=128, blank=True, default="")
    description = models.TextField(blank=True, default="")
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=STATUS_OPEN,
    )
    expires_at = models.DateTimeField(default=_default_session_expiry)
    created_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["owner", "-created_at"],
                name="zk_proofs_zksess_owner_idx",
            ),
            models.Index(
                fields=["status", "-created_at"],
                name="zk_proofs_zksess_status_idx",
            ),
        ]
        verbose_name = "ZK session"
        verbose_name_plural = "ZK sessions"

    def __str__(self) -> str:  # pragma: no cover
        return f"ZKSession({self.id}, owner={self.owner_id}, status={self.status})"

    def is_expired(self) -> bool:
        return self.expires_at is not None and timezone.now() >= self.expires_at

    def close(self) -> None:
        self.status = self.STATUS_CLOSED
        self.closed_at = timezone.now()
        self.save(update_fields=["status", "closed_at"])


class ZKSessionParticipant(models.Model):
    """
    Invitation slot within a ``ZKSession``.

    The row is created at invite time with a one-time ``invite_token`` and no
    submitted proof. When the invitee accepts and submits a valid proof, the
    slot is marked as ``verified`` and the proof payload is persisted for
    audit. A single slot may be retried on failure but locks after a
    successful verification.
    """

    STATUS_PENDING = "pending"
    STATUS_JOINED = "joined"
    STATUS_VERIFIED = "verified"
    STATUS_FAILED = "failed"
    STATUS_REVOKED = "revoked"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_JOINED, "Joined"),
        (STATUS_VERIFIED, "Verified"),
        (STATUS_FAILED, "Failed"),
        (STATUS_REVOKED, "Revoked"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        ZKSession,
        on_delete=models.CASCADE,
        related_name="participants",
    )
    invited_email = models.EmailField(blank=True, default="")
    invited_label = models.CharField(
        max_length=128,
        blank=True,
        default="",
        help_text="Free-form label the owner uses to track the invitee (e.g. 'Alice - Mobile').",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="zk_session_participations",
        help_text="Populated when the invitee accepts the token while authenticated.",
    )
    participant_commitment = models.ForeignKey(
        ZKCommitment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="session_participations",
        help_text="Commitment that the participant bound to this slot when they verified.",
    )
    invite_token = models.CharField(
        max_length=80,
        unique=True,
        default=_default_invite_token,
        db_index=True,
    )
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    attempt = models.ForeignKey(
        ZKVerificationAttempt,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="session_participants",
        help_text="Most recent verification attempt recorded for this slot.",
    )
    error_message = models.CharField(max_length=256, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["session", "status"],
                name="zk_proofs_zkpart_sess_stat_idx",
            ),
            models.Index(
                fields=["user", "-created_at"],
                name="zk_proofs_zkpart_user_idx",
            ),
        ]
        verbose_name = "ZK session participant"
        verbose_name_plural = "ZK session participants"

    def __str__(self) -> str:  # pragma: no cover
        return f"ZKSessionParticipant({self.id}, session={self.session_id}, status={self.status})"

    def mark_verified(self, attempt: ZKVerificationAttempt, commitment: ZKCommitment) -> None:
        self.status = self.STATUS_VERIFIED
        self.attempt = attempt
        self.participant_commitment = commitment
        self.error_message = ""
        self.verified_at = timezone.now()
        self.save(
            update_fields=[
                "status",
                "attempt",
                "participant_commitment",
                "error_message",
                "verified_at",
            ]
        )

    def mark_failed(self, attempt: ZKVerificationAttempt | None, reason: str) -> None:
        self.status = self.STATUS_FAILED
        self.attempt = attempt
        self.error_message = reason[:256]
        self.save(update_fields=["status", "attempt", "error_message"])
