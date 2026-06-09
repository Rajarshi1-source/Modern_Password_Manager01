"""Adaptive-password zero-knowledge v2 cleanup (PR-5).

Drops the legacy v1 columns (and their indexes) that held server-side
password-derived material now that the adaptive endpoints are v2-only:
- TypingSession.password_hash_prefix, TypingSession.password_length
- PasswordAdaptation.password_hash_prefix, PasswordAdaptation.adapted_hash_prefix

Also adds a partial-unique constraint on the active (user, original_fingerprint)
so two concurrent /apply/ calls from the same current head can't fork the
rollback chain.

No backfill — the zero-knowledge fingerprint/feature columns added in 0019 are
the only password references the server keeps. See
docs/adaptive-password-zk-remediation-plan.md (§6, §7, §11).
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("security", "0019_adaptive_zk_v2_fields"),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name="passwordadaptation",
            name="password_ad_passwor_ce4328_idx",
        ),
        migrations.RemoveIndex(
            model_name="typingsession",
            name="typing_sess_passwor_8109ac_idx",
        ),
        migrations.RemoveField(
            model_name="passwordadaptation",
            name="adapted_hash_prefix",
        ),
        migrations.RemoveField(
            model_name="passwordadaptation",
            name="password_hash_prefix",
        ),
        migrations.RemoveField(
            model_name="typingsession",
            name="password_hash_prefix",
        ),
        migrations.RemoveField(
            model_name="typingsession",
            name="password_length",
        ),
        migrations.AddConstraint(
            model_name="passwordadaptation",
            constraint=models.UniqueConstraint(
                fields=["user", "original_fingerprint"],
                condition=models.Q(status="active") & ~models.Q(original_fingerprint=""),
                name="uniq_active_original_fp_per_user",
            ),
        ),
    ]
