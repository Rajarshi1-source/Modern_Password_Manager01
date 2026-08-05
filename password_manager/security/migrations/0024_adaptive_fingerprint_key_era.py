"""Adaptive-password fingerprint key era (Phase 1).

Adds the non-secret per-user ``fingerprint_salt`` that seeds the CLIENT-side
Argon2id fingerprint KDF, plus an ``fp_key_version`` era stamp on the config and
on both fingerprint-keyed tables. Without the salt the zero-knowledge feature
cannot run at all: ``cryptoService.deriveFingerprintKey`` throws without one and
nothing in the tree provided it.

The two partial-unique constraints are re-scoped to include ``fp_key_version``
because a key rotation intentionally leaves the previous era's rows ``active``
for audit.

See docs/epigenetic-adaptation-implementation-plan.md §3.
"""

import secrets

from django.conf import settings
from django.db import migrations, models


def backfill_fingerprint_salts(apps, schema_editor):
    """Mint a salt for every pre-existing config that lacks one.

    Backfills disabled configs too, not just enabled ones: an admin can flip
    ``is_enabled`` directly through security/admin_adaptive.py, which never
    passes through the /enable/ endpoint that mints the salt. Leaving those rows
    blank would produce a config that is enabled but unusable.

    Bound to ``schema_editor.connection.alias`` rather than the default
    manager: this project's ``DATABASE_ROUTERS`` (``PrimaryReplicaRouter``)
    routes reads to a ``replica`` database when one is configured, which would
    otherwise make the read below look at a different connection than the one
    actually being migrated. ``bulk_update`` batches the writes instead of one
    UPDATE per row.
    """
    Config = apps.get_model('security', 'AdaptivePasswordConfig')
    db = schema_editor.connection.alias
    configs = list(Config.objects.using(db).filter(fingerprint_salt=''))
    for config in configs:
        config.fingerprint_salt = secrets.token_hex(16)
    if configs:
        Config.objects.using(db).bulk_update(
            configs, ['fingerprint_salt'], batch_size=500
        )


class Migration(migrations.Migration):

    dependencies = [
        ('security', '0023_passwordstructureprevalence'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='passwordadaptation',
            name='uniq_active_adapted_fp_per_user',
        ),
        migrations.RemoveConstraint(
            model_name='passwordadaptation',
            name='uniq_active_original_fp_per_user',
        ),
        migrations.AddField(
            model_name='adaptivepasswordconfig',
            name='fingerprint_salt',
            field=models.CharField(blank=True, default='', help_text='Non-secret per-user salt seeding the CLIENT fingerprint KDF. Useless without the master password (which is never transmitted).', max_length=64),
        ),
        migrations.AddField(
            model_name='adaptivepasswordconfig',
            name='fp_key_version',
            field=models.PositiveIntegerField(default=1, help_text='Fingerprint key era. Bumped when the salt is rotated (e.g. on master-password change) so fingerprints from different key eras are never correlated as if they described the same password.'),
        ),
        migrations.AddField(
            model_name='passwordadaptation',
            name='fp_key_version',
            field=models.PositiveIntegerField(default=1, help_text='Fingerprint key era (see AdaptivePasswordConfig.fp_key_version)'),
        ),
        migrations.AddField(
            model_name='typingsession',
            name='fp_key_version',
            field=models.PositiveIntegerField(default=1, help_text='Fingerprint key era (see AdaptivePasswordConfig.fp_key_version)'),
        ),
        migrations.AddIndex(
            model_name='passwordadaptation',
            index=models.Index(fields=['user', 'fp_key_version'], name='pwad_user_fpver_idx'),
        ),
        migrations.AddIndex(
            model_name='typingsession',
            index=models.Index(fields=['user', 'fp_key_version'], name='typing_sess_user_fpver_idx'),
        ),
        migrations.AddConstraint(
            model_name='passwordadaptation',
            constraint=models.UniqueConstraint(condition=models.Q(('status', 'active'), models.Q(('adapted_fingerprint', ''), _negated=True)), fields=('user', 'fp_key_version', 'adapted_fingerprint'), name='uniq_active_adapted_fp_per_user'),
        ),
        migrations.AddConstraint(
            model_name='passwordadaptation',
            constraint=models.UniqueConstraint(condition=models.Q(('status', 'active'), models.Q(('original_fingerprint', ''), _negated=True)), fields=('user', 'fp_key_version', 'original_fingerprint'), name='uniq_active_original_fp_per_user'),
        ),
        migrations.RunPython(
            backfill_fingerprint_salts,
            # No-op reverse: RunPython's reverse_code runs before AddField's own
            # reverse (RemoveField) in this same migration — operations reverse
            # bottom-to-top — so the column is dropped immediately after
            # regardless of what a blanking function did to its values first.
            # Empirically verified: migrate forward, set a salt, migrate back to
            # 0023, and the fingerprint_salt column is gone either way.
            migrations.RunPython.noop,
        ),
    ]
