"""Initial schema for the zk_proofs app."""

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ZKCommitment",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "scope_type",
                    models.CharField(
                        choices=[
                            ("vault_item", "Vault Item"),
                            ("vault_backup", "Vault Backup"),
                            ("user_password", "User Password"),
                        ],
                        max_length=32,
                    ),
                ),
                (
                    "scope_id",
                    models.CharField(
                        help_text=(
                            "Opaque reference to the scoped object "
                            "(vault item ID, backup ID, etc.)."
                        ),
                        max_length=128,
                    ),
                ),
                (
                    "commitment",
                    models.BinaryField(
                        help_text="Provider-specific commitment payload (SEC1 33-byte point for commitment-schnorr-v1).",
                    ),
                ),
                (
                    "scheme",
                    models.CharField(
                        choices=[
                            ("commitment-schnorr-v1", "Pedersen + Schnorr (secp256k1)"),
                        ],
                        default="commitment-schnorr-v1",
                        max_length=32,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="zk_commitments",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "ZK commitment",
                "verbose_name_plural": "ZK commitments",
            },
        ),
        migrations.CreateModel(
            name="ZKVerificationAttempt",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("scheme", models.CharField(max_length=32)),
                ("result", models.BooleanField()),
                (
                    "error_message",
                    models.CharField(blank=True, default="", max_length=256),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="zk_verification_attempts",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "commitment_a",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="verifications_as_a",
                        to="zk_proofs.zkcommitment",
                    ),
                ),
                (
                    "commitment_b",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="verifications_as_b",
                        to="zk_proofs.zkcommitment",
                    ),
                ),
                (
                    "verifier_user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="zk_verifications_performed",
                        to=settings.AUTH_USER_MODEL,
                        help_text=(
                            "User who initiated the verification request "
                            "(may differ from the commitment owner in multi-party flows)."
                        ),
                    ),
                ),
            ],
            options={
                "verbose_name": "ZK verification attempt",
                "verbose_name_plural": "ZK verification attempts",
            },
        ),
        migrations.AddConstraint(
            model_name="zkcommitment",
            constraint=models.UniqueConstraint(
                fields=("user", "scope_type", "scope_id", "scheme"),
                name="zk_proofs_zkcommitment_unique_scope",
            ),
        ),
        migrations.AddIndex(
            model_name="zkcommitment",
            index=models.Index(
                fields=["user", "scope_type"],
                name="zkp_zkco_user_scope_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="zkcommitment",
            index=models.Index(
                fields=["user", "-created_at"],
                name="zkp_zkco_user_created_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="zkverificationattempt",
            index=models.Index(
                fields=["user", "-created_at"],
                name="zkp_zkve_user_created_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="zkverificationattempt",
            index=models.Index(
                fields=["result", "-created_at"],
                name="zkp_zkve_result_created_idx",
            ),
        ),
    ]
