"""
Wrapped-DEK Recovery Models (Layered Recovery Mesh — Unit 1: DB Foundation)

This module introduces the wrapped Data-Encryption-Key (DEK) primitive that
replaces the legacy ``RecoveryKey`` model's full-vault duplication design.

Threat / Trust Model
--------------------
The server is treated as honest-but-curious. It MUST NEVER observe:
  * The user's plaintext master password.
  * The plaintext DEK that protects vault entries.
  * Any unwrapped recovery secret (printable recovery key, Shamir share,
    time-locked release secret, passkey-derived secret, etc.).

To enforce this, the wrapped material is stored opaquely in a JSON ``blob``
field. The server treats ``blob`` as a black box: it never inspects, parses,
or attempts to decrypt the ``wrapped`` value inside it. All wrap / unwrap
operations happen client-side.

Self-Describing Blob Format
---------------------------
Every ``blob`` is a self-describing envelope so that clients across versions
can negotiate parameters without a server round-trip::

    {
      "v":          int,    # envelope schema version
      "kdf":        str,    # KDF identifier, e.g. "argon2id" or "pbkdf2-sha256"
      "kdf_params": {...},  # KDF tuning (memory, iterations, parallelism, ...)
      "salt":       str,    # base64 KDF salt
      "iv":         str,    # base64 AEAD nonce / IV
      "wrapped":    str,    # base64 AEAD-ciphertext of the DEK — opaque
    }

The server only reads/writes the JSON value as a whole. It never breaks the
zero-knowledge boundary by decoding ``wrapped``.

Stable ``dek_id`` Across Master-Password Rotations
--------------------------------------------------
``dek_id`` is the cryptographic identity of the underlying DEK. When the user
rotates their master password, the client re-wraps the *same* DEK under the
new master-derived KEK and updates ``VaultWrappedDEK.blob`` in place — the
``dek_id`` does NOT change. This is what allows recovery factors registered
under an older master password to still recover the vault: every active
``RecoveryWrappedDEK`` row references the same ``dek_id``, so any factor can
unwrap a copy of the DEK and the vault stays decryptable.

Multi-Factor Mesh
-----------------
``RecoveryWrappedDEK`` lets the same DEK be wrapped under multiple independent
KEKs (printable recovery key, social mesh / Shamir, time-locked self-recovery,
local passkey). Recovery succeeds if *any* factor's KEK can be reconstructed
client-side and used to unwrap its blob.
"""

import uuid

from django.contrib.auth.models import User
from django.db import models


class VaultWrappedDEK(models.Model):
    """
    Per-user DEK wrapped under the master-password-derived KEK.

    The ``blob`` is opaque to the server; ``dek_id`` is stable across
    master-password rotations (the client re-wraps the same DEK in place).
    """

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='vault_dek',
    )
    blob = models.JSONField(
        help_text="Self-describing envelope {v, kdf, kdf_params, salt, iv, wrapped}; "
                  "server never inspects 'wrapped'.",
    )
    dek_id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        db_index=True,
        help_text="Stable identity of the underlying DEK; unchanged across "
                  "master-password rotations.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    rotated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'vault_wrapped_dek'
        verbose_name = 'Vault Wrapped DEK'
        verbose_name_plural = 'Vault Wrapped DEKs'

    def __str__(self):
        return f"VaultWrappedDEK(user={self.user.username}, dek_id={self.dek_id})"


class RecoveryWrappedDEK(models.Model):
    """
    The same DEK wrapped under an independent recovery-factor KEK.

    Multiple rows per user are expected — one per active factor (printable
    recovery key, social mesh, time-locked, passkey). Each factor's KEK is
    reconstructed client-side; the server only stores opaque ciphertext.
    """

    class FactorType(models.TextChoices):
        RECOVERY_KEY = 'recovery_key', 'Printable Recovery Key'
        SOCIAL_MESH = 'social_mesh', 'Social Mesh (Shamir)'
        TIME_LOCKED = 'time_locked', 'Time-Locked Self-Recovery'
        PASSKEY = 'passkey', 'Local Passkey'

    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        REVOKED = 'revoked', 'Revoked'

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='recovery_factors',
    )
    factor_type = models.CharField(
        max_length=32,
        choices=FactorType.choices,
        db_index=True,
    )
    dek_id = models.UUIDField(
        db_index=True,
        help_text="Matches VaultWrappedDEK.dek_id — every active factor wraps "
                  "the same logical DEK.",
    )
    blob = models.JSONField(
        help_text="Self-describing envelope; server never inspects 'wrapped'.",
    )
    factor_meta = models.JSONField(
        default=dict,
        blank=True,
        help_text="Factor-specific public metadata (e.g. share index, unlock-after "
                  "timestamp, passkey credential id). Never contains secrets.",
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'recovery_wrapped_dek'
        verbose_name = 'Recovery Wrapped DEK'
        verbose_name_plural = 'Recovery Wrapped DEKs'
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['user', 'factor_type', 'status']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['user'],
                condition=models.Q(factor_type='recovery_key', status='active'),
                name='unique_active_recovery_key_per_user',
            ),
        ]

    def __str__(self):
        return (
            f"RecoveryWrappedDEK(user={self.user.username}, "
            f"factor={self.factor_type}, status={self.status})"
        )
