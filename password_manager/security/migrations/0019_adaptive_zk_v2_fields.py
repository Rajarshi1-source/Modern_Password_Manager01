"""Adaptive-password zero-knowledge v2 schema (PR-3).

Adds client-computed, server-opaque fingerprint columns + coarse length bucket
to TypingSession, and fingerprint + masked-preview columns to
PasswordAdaptation. Legacy v1 hash-prefix / exact-length columns are relaxed to
optional (kept for rollback; removed in PR-5). No data is backfilled — ZK
behavioural data is simply re-collected under the new contract.

See docs/adaptive-password-zk-remediation-plan.md (§6, §7).
"""

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("security", "0018_geneticpasswordcertificate_cert_version"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="passwordadaptation",
            name="adapted_fingerprint",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Client-keyed fingerprint of the ADAPTED password (opaque)",
                max_length=64,
            ),
        ),
        migrations.AddField(
            model_name="passwordadaptation",
            name="adapted_masked",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Masked preview of the adapted password (e.g. a0***yz)",
                max_length=64,
            ),
        ),
        migrations.AddField(
            model_name="passwordadaptation",
            name="original_fingerprint",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Client-keyed fingerprint of the ORIGINAL password (opaque)",
                max_length=64,
            ),
        ),
        migrations.AddField(
            model_name="passwordadaptation",
            name="original_masked",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Masked preview of the original password (e.g. ab***yz)",
                max_length=64,
            ),
        ),
        migrations.AddField(
            model_name="typingsession",
            name="length_bucket",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="Coarse length bucket = floor(len/4) (never the exact length)",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="typingsession",
            name="password_fingerprint",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Client-keyed HMAC fingerprint (base64url); opaque to server",
                max_length=64,
            ),
        ),
        migrations.AlterField(
            model_name="passwordadaptation",
            name="adapted_hash_prefix",
            field=models.CharField(
                blank=True,
                default="",
                help_text="LEGACY v1 only. Hash prefix of ADAPTED password",
                max_length=32,
            ),
        ),
        migrations.AlterField(
            model_name="passwordadaptation",
            name="password_hash_prefix",
            field=models.CharField(
                blank=True,
                default="",
                help_text="LEGACY v1 only. Hash prefix of ORIGINAL password",
                max_length=32,
            ),
        ),
        migrations.AlterField(
            model_name="typingsession",
            name="password_hash_prefix",
            field=models.CharField(
                blank=True,
                default="",
                help_text="LEGACY v1 only. Hash prefix for correlation (unused in ZK v2)",
                max_length=32,
            ),
        ),
        migrations.AlterField(
            model_name="typingsession",
            name="password_length",
            field=models.IntegerField(
                blank=True,
                help_text="LEGACY v1 only. Exact length (ZK v2 stores length_bucket instead)",
                null=True,
            ),
        ),
        migrations.AddIndex(
            model_name="passwordadaptation",
            index=models.Index(
                fields=["user", "original_fingerprint"],
                name="password_ad_user_id_308b7e_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="typingsession",
            index=models.Index(
                fields=["user", "password_fingerprint"],
                name="typing_sess_user_id_a86413_idx",
            ),
        ),
    ]
