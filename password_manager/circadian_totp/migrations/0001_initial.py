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
            name="CircadianProfile",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "chronotype",
                    models.CharField(
                        choices=[
                            ("lark", "Early Bird (Lark)"),
                            ("neutral", "Neutral"),
                            ("owl", "Night Owl"),
                        ],
                        default="neutral",
                        max_length=12,
                    ),
                ),
                ("baseline_sleep_midpoint_minutes", models.IntegerField(default=180)),
                ("phase_stddev_minutes", models.FloatField(default=30.0)),
                (
                    "phase_lock_minutes",
                    models.IntegerField(
                        default=20,
                        help_text="Acceptable phase drift window during verification (minutes).",
                    ),
                ),
                ("sample_count", models.IntegerField(default=0)),
                ("last_calibrated_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="circadian_profile",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Circadian Profile",
                "verbose_name_plural": "Circadian Profiles",
            },
        ),
        migrations.CreateModel(
            name="SleepObservation",
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
                    "provider",
                    models.CharField(
                        choices=[
                            ("fitbit", "Fitbit"),
                            ("apple_health", "Apple Health"),
                            ("oura", "Oura"),
                            ("google_fit", "Google Fit"),
                            ("manual", "Manual / Self-Reported"),
                        ],
                        max_length=20,
                    ),
                ),
                ("sleep_start", models.DateTimeField()),
                ("sleep_end", models.DateTimeField()),
                ("efficiency_score", models.FloatField(blank=True, null=True)),
                (
                    "raw_payload_hash",
                    models.CharField(blank=True, default="", max_length=64),
                ),
                ("ingested_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="circadian_observations",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-sleep_end"]},
        ),
        migrations.AddIndex(
            model_name="sleepobservation",
            index=models.Index(
                fields=["user", "sleep_end"], name="circadian_t_user_id_sleepend_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="sleepobservation",
            index=models.Index(
                fields=["user", "provider"], name="circadian_t_user_id_provider_idx"
            ),
        ),
        migrations.AddConstraint(
            model_name="sleepobservation",
            constraint=models.UniqueConstraint(
                fields=("user", "provider", "sleep_start"),
                name="uniq_sleep_obs_per_provider",
            ),
        ),
        migrations.CreateModel(
            name="WearableLink",
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
                    "provider",
                    models.CharField(
                        choices=[
                            ("fitbit", "Fitbit"),
                            ("apple_health", "Apple Health"),
                            ("oura", "Oura"),
                            ("google_fit", "Google Fit"),
                            ("manual", "Manual / Self-Reported"),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "external_user_id",
                    models.CharField(blank=True, default="", max_length=128),
                ),
                (
                    "oauth_access_token_encrypted",
                    models.BinaryField(blank=True, default=b""),
                ),
                (
                    "oauth_refresh_token_encrypted",
                    models.BinaryField(blank=True, default=b""),
                ),
                ("scope", models.CharField(blank=True, default="", max_length=256)),
                (
                    "token_type",
                    models.CharField(blank=True, default="Bearer", max_length=32),
                ),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("last_synced_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="wearable_links",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="wearablelink",
            constraint=models.UniqueConstraint(
                fields=("user", "provider"), name="uniq_wearable_per_user"
            ),
        ),
        migrations.CreateModel(
            name="CircadianTOTPDevice",
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
                    "name",
                    models.CharField(default="Circadian Authenticator", max_length=64),
                ),
                ("secret_encrypted", models.BinaryField()),
                ("digits", models.PositiveSmallIntegerField(default=6)),
                ("step_seconds", models.PositiveIntegerField(default=30)),
                (
                    "drift_algorithm",
                    models.CharField(
                        choices=[("xor_phase", "XOR Phase (v1)")],
                        default="xor_phase",
                        max_length=32,
                    ),
                ),
                ("confirmed", models.BooleanField(default=False)),
                ("last_verified_at", models.DateTimeField(blank=True, null=True)),
                ("last_phase_used", models.IntegerField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="circadian_totp_devices",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Circadian TOTP Device",
                "verbose_name_plural": "Circadian TOTP Devices",
            },
        ),
        migrations.AddIndex(
            model_name="circadiantotpdevice",
            index=models.Index(
                fields=["user", "confirmed"], name="circadian_t_user_id_confirm_idx"
            ),
        ),
    ]
