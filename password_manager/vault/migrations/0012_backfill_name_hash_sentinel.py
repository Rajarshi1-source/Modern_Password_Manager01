"""
Audit fix M3 (2026-05): backfill ``EncryptedVaultItem.name_hash`` for
legacy rows that were created before migration 0008 added the column.

Background
----------
Migration 0008 added ``name_hash`` (and ``name_search``) with
``default=''``. New rows since then populate it via the FHE search /
PRE sharing flows; legacy rows still have the empty string. The
audit's M3 finding: if anyone ever runs ``filter(name_hash=...)`` for
an item's hash, EVERY legacy row matches the empty string and the
query returns the wrong set.

Backfilling to a sentinel value (``'__LEGACY__'``) makes legacy rows
match a known, non-empty token that no real hash will ever equal —
so a filter on a real hash never accidentally pulls in legacy rows.
Any future code path that genuinely wants to operate on legacy items
can filter on ``name_hash='__LEGACY__'`` explicitly.

Reverse migration is a no-op: we don't pretend to know which rows
were originally legacy after a backfill has been applied. If the
column is dropped, no harm.
"""

from django.db import migrations


_SENTINEL = '__LEGACY__'


def backfill_name_hash(apps, schema_editor):
    EncryptedVaultItem = apps.get_model('vault', 'EncryptedVaultItem')
    EncryptedVaultItem.objects.filter(name_hash='').update(
        name_hash=_SENTINEL,
    )


def reverse(apps, schema_editor):
    """No-op reverse — see module docstring."""
    return None


class Migration(migrations.Migration):

    # NB (PR #273 review, Codex P1): chain off the last main-branch
    # migration (`0010`) so this PR can land independent of Phase A
    # (#272), which is the one that adds `0011_usersalt_sync_version`.
    # When both PRs are merged Django will linearise the graph
    # automatically: `0011` (Phase A) and `0012` (Phase B) share
    # parent `0010` and can apply in either order.
    dependencies = [
        ('vault', '0010_backfill_user_salt_auth_hash'),
    ]

    operations = [
        migrations.RunPython(backfill_name_hash, reverse),
    ]
