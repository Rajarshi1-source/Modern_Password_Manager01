"""Adds ZKSession and ZKSessionParticipant for multi-party ZK ceremonies."""

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import zk_proofs.models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("zk_proofs", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ZKSession",
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
                ("title", models.CharField(blank=True, default="", max_length=128)),
                ("description", models.TextField(blank=True, default="")),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("open", "Open"),
                            ("closed", "Closed"),
                            ("expired", "Expired"),
                        ],
                        default="open",
                        max_length=16,
                    ),
                ),
                (
                    "expires_at",
                    models.DateTimeField(
                        default=zk_proofs.models._default_session_expiry,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("closed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="zk_sessions_owned",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "reference_commitment",
                    models.ForeignKey(
                        help_text=(
                            "Commitment that invitees will prove equality against. "
                            "Must be owned by the session owner."
                        ),
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sessions_as_reference",
                        to="zk_proofs.zkcommitment",
                    ),
                ),
            ],
            options={
                "verbose_name": "ZK session",
                "verbose_name_plural": "ZK sessions",
            },
        ),
        migrations.CreateModel(
            name="ZKSessionParticipant",
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
                ("invited_email", models.EmailField(blank=True, default="", max_length=254)),
                (
                    "invited_label",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text=(
                            "Free-form label the owner uses to track the invitee "
                            "(e.g. 'Alice - Mobile')."
                        ),
                        max_length=128,
                    ),
                ),
                (
                    "invite_token",
                    models.CharField(
                        db_index=True,
                        default=zk_proofs.models._default_invite_token,
                        max_length=80,
                        unique=True,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("joined", "Joined"),
                            ("verified", "Verified"),
                            ("failed", "Failed"),
                            ("revoked", "Revoked"),
                        ],
                        default="pending",
                        max_length=16,
                    ),
                ),
                ("error_message", models.CharField(blank=True, default="", max_length=256)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("verified_at", models.DateTimeField(blank=True, null=True)),
                (
                    "attempt",
                    models.ForeignKey(
                        blank=True,
                        help_text="Most recent verification attempt recorded for this slot.",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="session_participants",
                        to="zk_proofs.zkverificationattempt",
                    ),
                ),
                (
                    "participant_commitment",
                    models.ForeignKey(
                        blank=True,
                        help_text="Commitment that the participant bound to this slot when they verified.",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="session_participations",
                        to="zk_proofs.zkcommitment",
                    ),
                ),
                (
                    "session",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="participants",
                        to="zk_proofs.zksession",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        help_text="Populated when the invitee accepts the token while authenticated.",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="zk_session_participations",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "ZK session participant",
                "verbose_name_plural": "ZK session participants",
            },
        ),
        migrations.AddIndex(
            model_name="zksession",
            index=models.Index(
                fields=["owner", "-created_at"],
                name="zk_proofs_zksess_owner_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="zksession",
            index=models.Index(
                fields=["status", "-created_at"],
                name="zk_proofs_zksess_status_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="zksessionparticipant",
            index=models.Index(
                fields=["session", "status"],
                name="zk_proofs_zkpart_sess_stat_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="zksessionparticipant",
            index=models.Index(
                fields=["user", "-created_at"],
                name="zk_proofs_zkpart_user_idx",
            ),
        ),
    ]
