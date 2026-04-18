"""Initial schema for the social_recovery app."""

import uuid

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import social_recovery.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="RecoveryCircle",
            fields=[
                (
                    "circle_id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "threshold",
                    models.IntegerField(
                        validators=[
                            django.core.validators.MinValueValidator(2),
                            django.core.validators.MaxValueValidator(10),
                        ]
                    ),
                ),
                (
                    "total_vouchers",
                    models.IntegerField(
                        validators=[
                            django.core.validators.MinValueValidator(2),
                            django.core.validators.MaxValueValidator(20),
                        ]
                    ),
                ),
                ("secret_commitment", models.BinaryField()),
                ("salt", models.BinaryField(default=bytes)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("draft", "Draft"),
                            ("active", "Active"),
                            ("locked", "Locked"),
                            ("revoked", "Revoked"),
                        ],
                        default="draft",
                        max_length=20,
                    ),
                ),
                ("min_voucher_reputation", models.IntegerField(default=0)),
                ("min_total_stake", models.IntegerField(default=0)),
                (
                    "cooldown_hours",
                    models.IntegerField(
                        default=24,
                        validators=[
                            django.core.validators.MinValueValidator(0),
                            django.core.validators.MaxValueValidator(720),
                        ],
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("activated_at", models.DateTimeField(blank=True, null=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="social_recovery_circles",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Social Recovery Circle",
                "verbose_name_plural": "Social Recovery Circles",
                "db_table": "social_recovery_circle",
            },
        ),
        migrations.AddIndex(
            model_name="recoverycircle",
            index=models.Index(
                fields=["user", "status"], name="social_reco_user_id_7bf0cd_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="recoverycircle",
            index=models.Index(
                fields=["status"], name="social_reco_status_7cc2c3_idx"
            ),
        ),
        migrations.CreateModel(
            name="Voucher",
            fields=[
                (
                    "voucher_id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("did_string", models.CharField(blank=True, default="", max_length=255)),
                ("email", models.EmailField(blank=True, default="", max_length=254)),
                ("display_name", models.CharField(blank=True, default="", max_length=128)),
                ("ed25519_public_key", models.CharField(max_length=128)),
                ("relationship_label", models.CharField(blank=True, default="", max_length=64)),
                (
                    "vouch_weight",
                    models.IntegerField(
                        default=1,
                        validators=[
                            django.core.validators.MinValueValidator(1),
                            django.core.validators.MaxValueValidator(10),
                        ],
                    ),
                ),
                ("encrypted_shard_data", models.BinaryField()),
                ("encryption_metadata", models.JSONField(blank=True, default=dict)),
                ("share_index", models.IntegerField(default=1)),
                ("stake_amount", models.IntegerField(default=0)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending Acceptance"),
                            ("accepted", "Accepted"),
                            ("active", "Active"),
                            ("revoked", "Revoked"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                (
                    "invitation_token",
                    models.CharField(
                        default=social_recovery.models._make_invitation_token,
                        max_length=64,
                        unique=True,
                    ),
                ),
                ("invitation_expires_at", models.DateTimeField(blank=True, null=True)),
                ("accepted_at", models.DateTimeField(blank=True, null=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "circle",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="vouchers",
                        to="social_recovery.recoverycircle",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="social_voucher_roles",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Social Recovery Voucher",
                "verbose_name_plural": "Social Recovery Vouchers",
                "db_table": "social_recovery_voucher",
                "unique_together": {("circle", "share_index")},
            },
        ),
        migrations.AddIndex(
            model_name="voucher",
            index=models.Index(
                fields=["circle", "status"], name="social_reco_circle__9af1a2_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="voucher",
            index=models.Index(
                fields=["invitation_token"], name="social_reco_invitat_b41f05_idx"
            ),
        ),
        migrations.CreateModel(
            name="RelationshipCommitment",
            fields=[
                (
                    "commitment_id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("pedersen_commitment", models.BinaryField()),
                ("salt_hash", models.CharField(max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "circle",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="relationship_commitments",
                        to="social_recovery.recoverycircle",
                    ),
                ),
                (
                    "voucher",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="relationship_commitment",
                        to="social_recovery.voucher",
                    ),
                ),
            ],
            options={
                "db_table": "social_recovery_relationship_commitment",
            },
        ),
        migrations.CreateModel(
            name="SocialRecoveryRequest",
            fields=[
                (
                    "request_id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("initiator_email", models.EmailField(blank=True, default="", max_length=254)),
                ("initiator_ip", models.GenericIPAddressField(blank=True, null=True)),
                ("device_fingerprint", models.CharField(blank=True, default="", max_length=128)),
                ("geo", models.JSONField(blank=True, default=dict)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending Voucher Approvals"),
                            ("approved", "Approved"),
                            ("denied", "Denied"),
                            ("expired", "Expired"),
                            ("cancelled", "Cancelled"),
                            ("completed", "Completed"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("required_approvals", models.IntegerField()),
                ("received_approvals", models.IntegerField(default=0)),
                ("total_weight", models.IntegerField(default=0)),
                ("total_stake_committed", models.IntegerField(default=0)),
                ("challenge_nonce", models.CharField(max_length=64)),
                ("risk_score", models.FloatField(default=0.0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("expires_at", models.DateTimeField()),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "circle",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="requests",
                        to="social_recovery.recoverycircle",
                    ),
                ),
            ],
            options={
                "db_table": "social_recovery_request",
            },
        ),
        migrations.AddIndex(
            model_name="socialrecoveryrequest",
            index=models.Index(
                fields=["circle", "status"], name="social_reco_circle__f9b921_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="socialrecoveryrequest",
            index=models.Index(
                fields=["status", "expires_at"], name="social_reco_status_3c3eb8_idx"
            ),
        ),
        migrations.CreateModel(
            name="VouchAttestation",
            fields=[
                (
                    "attestation_id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("ed25519_signature", models.BinaryField()),
                ("signed_message", models.BinaryField()),
                ("zk_proof_T", models.BinaryField(blank=True, null=True)),
                ("zk_proof_s", models.BinaryField(blank=True, null=True)),
                ("fresh_commitment", models.BinaryField(blank=True, null=True)),
                ("vc_id", models.UUIDField(blank=True, null=True)),
                (
                    "decision",
                    models.CharField(
                        choices=[("approve", "Approve"), ("deny", "Deny")],
                        max_length=16,
                    ),
                ),
                ("stake_committed", models.IntegerField(default=0)),
                ("attested_at", models.DateTimeField(auto_now_add=True)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("user_agent", models.TextField(blank=True, default="")),
                (
                    "request",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="attestations",
                        to="social_recovery.socialrecoveryrequest",
                    ),
                ),
                (
                    "voucher",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="attestations",
                        to="social_recovery.voucher",
                    ),
                ),
            ],
            options={
                "db_table": "social_recovery_attestation",
                "unique_together": {("request", "voucher")},
            },
        ),
        migrations.AddIndex(
            model_name="vouchattestation",
            index=models.Index(
                fields=["request", "decision"], name="social_reco_request_1c91f0_idx"
            ),
        ),
        migrations.CreateModel(
            name="SocialRecoveryAuditLog",
            fields=[
                (
                    "entry_id",
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
                        ],
                        max_length=32,
                    ),
                ),
                ("event_data", models.JSONField(blank=True, default=dict)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("user_agent", models.TextField(blank=True, default="")),
                ("prev_hash", models.BinaryField(default=bytes)),
                ("entry_hash", models.BinaryField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "circle",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="audit_logs",
                        to="social_recovery.recoverycircle",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="social_recovery_audit_logs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "social_recovery_audit_log",
                "ordering": ["created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="socialrecoveryauditlog",
            index=models.Index(
                fields=["user", "-created_at"], name="social_reco_user_id_a1f2d4_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="socialrecoveryauditlog",
            index=models.Index(
                fields=["event_type", "-created_at"], name="social_reco_event_t_19ad03_idx"
            ),
        ),
    ]
