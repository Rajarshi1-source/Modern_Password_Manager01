"""Initial schema for ambient_auth."""

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
            name="AmbientProfile",
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
                ("device_fp", models.CharField(max_length=128)),
                ("local_salt_version", models.PositiveIntegerField(default=1)),
                ("centroid_json", models.JSONField(blank=True, default=dict)),
                ("signal_weights_json", models.JSONField(blank=True, default=dict)),
                ("samples_used", models.PositiveIntegerField(default=0)),
                ("last_observation_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ambient_profiles",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Ambient profile",
                "verbose_name_plural": "Ambient profiles",
            },
        ),
        migrations.CreateModel(
            name="AmbientContext",
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
                ("label", models.CharField(max_length=64)),
                ("centroid_json", models.JSONField(blank=True, default=dict)),
                ("radius", models.FloatField(default=0.35)),
                ("is_trusted", models.BooleanField(default=False)),
                ("samples_used", models.PositiveIntegerField(default=0)),
                ("last_matched_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "profile",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="contexts",
                        to="ambient_auth.ambientprofile",
                    ),
                ),
            ],
            options={
                "verbose_name": "Ambient context",
                "verbose_name_plural": "Ambient contexts",
            },
        ),
        migrations.CreateModel(
            name="AmbientObservation",
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
                    "surface",
                    models.CharField(
                        choices=[
                            ("web", "Web app"),
                            ("extension", "Browser extension"),
                            ("mobile", "React Native mobile"),
                        ],
                        max_length=16,
                    ),
                ),
                ("schema_version", models.PositiveIntegerField(default=1)),
                ("signal_availability", models.JSONField(blank=True, default=dict)),
                ("coarse_features_json", models.JSONField(blank=True, default=dict)),
                ("embedding_digest", models.CharField(blank=True, default="", max_length=256)),
                ("trust_score", models.FloatField(default=0.0)),
                ("novelty_score", models.FloatField(default=0.0)),
                ("reasons_json", models.JSONField(blank=True, default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "matched_context",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="observations",
                        to="ambient_auth.ambientcontext",
                    ),
                ),
                (
                    "profile",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="observations",
                        to="ambient_auth.ambientprofile",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ambient_observations",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Ambient observation",
                "verbose_name_plural": "Ambient observations",
            },
        ),
        migrations.CreateModel(
            name="AmbientSignalConfig",
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
                ("signal_key", models.CharField(max_length=32)),
                ("enabled", models.BooleanField(default=True)),
                ("enabled_on_surfaces", models.JSONField(blank=True, default=list)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ambient_signal_configs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Ambient signal config",
                "verbose_name_plural": "Ambient signal configs",
            },
        ),
        migrations.AddConstraint(
            model_name="ambientprofile",
            constraint=models.UniqueConstraint(
                fields=("user", "device_fp", "local_salt_version"),
                name="amb_profile_unique_dev_salt",
            ),
        ),
        migrations.AddIndex(
            model_name="ambientprofile",
            index=models.Index(
                fields=["user", "-updated_at"],
                name="amb_profile_user_upd_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="ambientcontext",
            index=models.Index(
                fields=["profile", "-updated_at"],
                name="amb_ctx_profile_upd_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="ambientcontext",
            index=models.Index(
                fields=["is_trusted"],
                name="amb_ctx_trusted_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="ambientobservation",
            index=models.Index(
                fields=["user", "-created_at"],
                name="amb_obs_user_created_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="ambientobservation",
            index=models.Index(
                fields=["profile", "-created_at"],
                name="amb_obs_profile_ctx_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="ambientsignalconfig",
            constraint=models.UniqueConstraint(
                fields=("user", "signal_key"),
                name="amb_signalcfg_unique",
            ),
        ),
        migrations.AddIndex(
            model_name="ambientsignalconfig",
            index=models.Index(
                fields=["user", "signal_key"],
                name="amb_signalcfg_user_idx",
            ),
        ),
    ]
