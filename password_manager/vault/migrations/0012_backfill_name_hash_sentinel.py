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

    # Audit-trail: this dep originally chained off `0010` because Phase A
    # (#272) hadn't merged yet and `0011_usersalt_sync_version` only
    # existed on that branch. Phase A has since landed on main, so on
    # the post-merge tree both `0011` (Phase A) and this `0012`
    # (Phase B) shared parent `0010` — Django saw TWO leaf nodes
    # (`0011_usersalt_sync_version` and `0013_vaultbackup_content_md5`)
    # and refused to apply: "Conflicting migrations detected; multiple
    # leaf nodes in the migration graph". Re-chained onto `0011` to
    # linearise the graph: `0010 → 0011 → 0012 → 0013`. Single leaf,
    # no merge migration needed.
    dependencies = [
        ('vault', '0011_usersalt_sync_version'),
    ]

    operations = [
        migrations.RunPython(backfill_name_hash, reverse),
    ]
