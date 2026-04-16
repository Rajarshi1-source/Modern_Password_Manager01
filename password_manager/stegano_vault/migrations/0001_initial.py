"""Initial schema for stegano_vault."""

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import stegano_vault.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="StegoVault",
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
                    "label",
                    models.CharField(
                        default="Default",
                        help_text="User-facing name for this stego container.",
                        max_length=120,
                    ),
                ),
                (
                    "image",
                    models.FileField(
                        help_text="PNG bytes with HiddenVaultBlob embedded via LSB.",
                        max_length=512,
                        upload_to=stegano_vault.models._stego_image_upload_path,
                    ),
                ),
                (
                    "image_mime",
                    models.CharField(
                        default="image/png",
                        help_text="Locked to 'image/png' in v1; JPEG would destroy LSB payload.",
                        max_length=32,
                    ),
                ),
                (
                    "blob_size_tier",
                    models.PositiveSmallIntegerField(
                        choices=[
                            (0, "Tier 0 - 32 KiB"),
                            (1, "Tier 1 - 128 KiB"),
                            (2, "Tier 2 - 1 MiB"),
                        ],
                        default=0,
                    ),
                ),
                (
                    "crypto_ver",
                    models.PositiveSmallIntegerField(
                        default=1,
                        help_text="HiddenVaultBlob format version.",
                    ),
                ),
                (
                    "cover_hash",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text=(
                            "SHA-256 hex of the cover image before embedding. "
                            "Lets the user later compare against the original "
                            "to detect unexpected re-encoding by a hosting "
                            "provider."
                        ),
                        max_length=64,
                    ),
                ),
                ("schema_ver", models.PositiveSmallIntegerField(default=1)),
                ("notes", models.CharField(blank=True, default="", max_length=240)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("last_accessed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="stego_vaults",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Stego Vault",
                "verbose_name_plural": "Stego Vaults",
                "ordering": ("-updated_at",),
            },
        ),
        migrations.CreateModel(
            name="StegoAccessEvent",
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
                    "kind",
                    models.CharField(
                        choices=[
                            ("embed", "Embed"),
                            ("extract", "Extract"),
                            ("download", "Download"),
                            ("store", "Store"),
                            ("delete", "Delete"),
                            ("upgrade_duress", "Upgrade duress"),
                        ],
                        max_length=24,
                    ),
                ),
                ("surface", models.CharField(default="web", max_length=16)),
                ("ip", models.GenericIPAddressField(blank=True, null=True)),
                (
                    "user_agent",
                    models.CharField(blank=True, default="", max_length=240),
                ),
                ("details", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "stego_vault",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="access_events",
                        to="stegano_vault.stegovault",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="stego_events",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Stego Access Event",
                "verbose_name_plural": "Stego Access Events",
                "ordering": ("-created_at",),
            },
        ),
        migrations.AddIndex(
            model_name="stegovault",
            index=models.Index(
                fields=["user", "-updated_at"], name="stego_user_updated_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="stegovault",
            index=models.Index(
                fields=["user", "label"], name="stego_user_label_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="stegoaccessevent",
            index=models.Index(
                fields=["user", "-created_at"], name="stego_evt_user_at_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="stegoaccessevent",
            index=models.Index(
                fields=["stego_vault", "kind"], name="stego_evt_vault_kind_idx"
            ),
        ),
    ]
