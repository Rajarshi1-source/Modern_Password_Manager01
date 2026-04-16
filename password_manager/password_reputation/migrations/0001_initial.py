"""Initial schema for password_reputation."""

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
            name="AnchorBatch",
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
                ("adapter", models.CharField(max_length=32)),
                ("merkle_root", models.CharField(max_length=66)),
                ("batch_size", models.PositiveIntegerField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("draft", "Draft"),
                            ("submitted", "Submitted"),
                            ("confirmed", "Confirmed"),
                            ("failed", "Failed"),
                            ("skipped", "Skipped (null adapter)"),
                        ],
                        default="draft",
                        max_length=16,
                    ),
                ),
                ("tx_hash", models.CharField(blank=True, default="", max_length=80)),
                ("block_number", models.BigIntegerField(blank=True, null=True)),
                ("network", models.CharField(blank=True, default="", max_length=32)),
                ("error_message", models.CharField(blank=True, default="", max_length=256)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                ("confirmed_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "verbose_name": "Anchor batch",
                "verbose_name_plural": "Anchor batches",
            },
        ),
        migrations.CreateModel(
            name="ReputationAccount",
            fields=[
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        primary_key=True,
                        related_name="reputation_account",
                        serialize=False,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                ("score", models.IntegerField(default=0)),
                ("tokens", models.BigIntegerField(default=0)),
                ("proofs_accepted", models.PositiveIntegerField(default=0)),
                ("proofs_rejected", models.PositiveIntegerField(default=0)),
                ("last_proof_at", models.DateTimeField(blank=True, null=True)),
                ("last_breach_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "Reputation account",
                "verbose_name_plural": "Reputation accounts",
            },
        ),
        migrations.CreateModel(
            name="ReputationProof",
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
                    "scheme",
                    models.CharField(
                        choices=[("commitment-claim-v1", "Commitment + entropy claim (v1)")],
                        default="commitment-claim-v1",
                        max_length=48,
                    ),
                ),
                ("scope_id", models.CharField(max_length=128)),
                ("commitment", models.BinaryField()),
                ("claimed_entropy_bits", models.PositiveIntegerField()),
                (
                    "status",
                    models.CharField(
                        choices=[("accepted", "Accepted"), ("rejected", "Rejected")],
                        max_length=16,
                    ),
                ),
                ("score_delta", models.IntegerField(default=0)),
                ("tokens_delta", models.BigIntegerField(default=0)),
                ("error_message", models.CharField(blank=True, default="", max_length=256)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reputation_proofs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Reputation proof",
                "verbose_name_plural": "Reputation proofs",
            },
        ),
        migrations.CreateModel(
            name="ReputationEvent",
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
                    "event_type",
                    models.CharField(
                        choices=[
                            ("proof_accepted", "Proof accepted"),
                            ("proof_rejected", "Proof rejected"),
                            ("bonus", "Bonus"),
                            ("slash", "Slash"),
                            ("anchor_confirmed", "Anchor confirmed"),
                        ],
                        max_length=32,
                    ),
                ),
                ("score_delta", models.IntegerField(default=0)),
                ("tokens_delta", models.BigIntegerField(default=0)),
                ("leaf_hash", models.BinaryField()),
                (
                    "anchor_status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("included", "Included in batch"),
                            ("confirmed", "Confirmed on-chain"),
                            ("failed", "Anchoring failed"),
                            ("skipped", "Adapter skipped"),
                        ],
                        default="pending",
                        max_length=16,
                    ),
                ),
                ("note", models.CharField(blank=True, default="", max_length=256)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "anchor_batch",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="events",
                        to="password_reputation.anchorbatch",
                    ),
                ),
                (
                    "proof",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="events",
                        to="password_reputation.reputationproof",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reputation_events",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Reputation event",
                "verbose_name_plural": "Reputation events",
            },
        ),
        migrations.AddConstraint(
            model_name="reputationproof",
            constraint=models.UniqueConstraint(
                fields=("user", "scope_id", "scheme"),
                name="pw_reputation_proof_unique_scope",
            ),
        ),
        migrations.AddIndex(
            model_name="reputationproof",
            index=models.Index(
                fields=["user", "-created_at"],
                name="pw_rep_proof_user_created_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="reputationproof",
            index=models.Index(
                fields=["status", "-created_at"],
                name="pw_rep_proof_status_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="reputationevent",
            index=models.Index(
                fields=["user", "-created_at"],
                name="pw_rep_evt_user_created_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="reputationevent",
            index=models.Index(
                fields=["anchor_status", "created_at"],
                name="pw_rep_evt_anchor_st_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="anchorbatch",
            index=models.Index(
                fields=["-created_at"],
                name="pw_rep_batch_created_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="anchorbatch",
            index=models.Index(
                fields=["status"],
                name="pw_rep_batch_status_idx",
            ),
        ),
    ]
