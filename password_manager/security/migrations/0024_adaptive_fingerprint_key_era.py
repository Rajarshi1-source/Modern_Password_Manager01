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
    """
    Config = apps.get_model('security', 'AdaptivePasswordConfig')
    for config in Config.objects.filter(fingerprint_salt='').iterator():
        config.fingerprint_salt = secrets.token_hex(16)
        config.save(update_fields=['fingerprint_salt'])


def drop_fingerprint_salts(apps, schema_editor):
    """Reverse: blank the salts so a re-apply mints fresh ones.

    Deliberately destructive-on-reverse. Retaining a salt whose column is about
    to be dropped would let a later re-apply resurrect a stale key era.
    """
    Config = apps.get_model('security', 'AdaptivePasswordConfig')
    Config.objects.update(fingerprint_salt='')


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
            drop_fingerprint_salts,
        ),
    ]
