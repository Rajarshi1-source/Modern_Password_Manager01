"""Add the per-factor-type ACTIVE-row uniqueness invariant + auth_hash.

Two changes in one migration so the deploy is atomic:

1. ``auth_hash`` field on ``RecoveryWrappedDEK``. Used by the anonymous
   wrapped-DEK rotation endpoint to gate rotations on proof of
   recovery-secret possession. Default empty string for legacy rows
   from before the field existed; the rotation view rejects empty
   ``auth_hash`` values, forcing legacy users to re-enroll their
   factor before they can rotate via that path.

2. Partial unique constraint
   ``unique_active_factor_per_user_per_type`` on
   ``(user, factor_type) WHERE status='active'``. Without this, two
   concurrent first-time enrolls of the same ``(user, factor_type)``
   combination both find zero existing rows under their per-row
   ``select_for_update()`` locks and both succeed in inserting ACTIVE
   rows. The existing partial unique on ``recovery_key`` covers only
   that one factor_type; this generalises the invariant.

Step (2) is preceded by a ``RunPython`` data backfill that revokes
older duplicate ACTIVE rows for any ``(user, factor_type)`` group
already in the database. Without the backfill, ``AddConstraint``
would fail at migrate time on any deployment that previously
allowed duplicates (i.e., every deployment that ever ran the
non-recovery_key enroll path before this PR). The backfill keeps
the most recent row by ``created_at`` and revokes the rest.

The reverse migration is a no-op: the unique constraint and the
``auth_hash`` field can be dropped, but un-revoking the older rows
would be guesswork and not safe.
"""
from django.db import migrations, models


def backfill_unique_active_factor_per_type(apps, schema_editor):
    """Revoke duplicate ACTIVE rows so the new constraint can apply.

    For each ``(user, factor_type)`` group with multiple ACTIVE rows,
    keep the most recent (by ``created_at``) and mark the rest
    revoked. This is the conservative choice: the lookup view's
    pre-constraint behaviour was ``order_by('-created_at').first()``,
    so the row we keep is the one that was already being surfaced as
    "the active factor"; older rows were already invisible to
    anonymous recovery callers.
    """
    RecoveryWrappedDEK = apps.get_model('auth_module', 'RecoveryWrappedDEK')
    from django.db.models import Count
    from django.utils import timezone

    duplicate_groups = (
        RecoveryWrappedDEK.objects
        .filter(status='active')
        .values('user_id', 'factor_type')
        .annotate(c=Count('id'))
        .filter(c__gt=1)
    )
    now = timezone.now()
    for group in duplicate_groups:
        rows = list(
            RecoveryWrappedDEK.objects
            .filter(
                user_id=group['user_id'],
                factor_type=group['factor_type'],
                status='active',
            )
            .order_by('-created_at', '-id')
        )
        # rows[0] is the "winner" — leave it ACTIVE.
        for row in rows[1:]:
            row.status = 'revoked'
            row.revoked_at = now
            row.save(update_fields=['status', 'revoked_at'])


def noop_reverse(apps, schema_editor):
    """The reverse migration cannot un-revoke without losing
    information about which ones were "real" duplicates vs. genuine
    revocations. Intentionally a no-op."""


class Migration(migrations.Migration):

    dependencies = [
        ('auth_module', '0012_time_locked_recovery'),
    ]

    operations = [
        migrations.AddField(
            model_name='recoverywrappeddek',
            name='auth_hash',
            field=models.CharField(
                blank=True,
                db_index=True,
                default='',
                max_length=64,
                help_text=(
                    'SHA-256 of "rotation-auth-v1:" + recovery_secret. '
                    'Required at rotation; missing only on legacy rows '
                    'from before this field.'
                ),
            ),
        ),
        migrations.RunPython(
            backfill_unique_active_factor_per_type,
            noop_reverse,
        ),
        migrations.AddConstraint(
            model_name='recoverywrappeddek',
            constraint=models.UniqueConstraint(
                fields=['user', 'factor_type'],
                condition=models.Q(status='active'),
                name='unique_active_factor_per_user_per_type',
            ),
        ),
    ]
