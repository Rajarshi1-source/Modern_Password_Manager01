"""
Phase C / C4: GIN index on ``EncryptedVaultItem.tags``.

The ``tags`` field is a ``JSONField(default=list)``. Containment queries
(``tags__contains=['banking']`` and friends) currently full-scan the
table — a GIN index on the JSON value gives sub-millisecond lookups
even on large vaults.

Postgres-only:
* GIN indexes don't exist on SQLite (dev) or other vendors.
* The guard inspects ``connection.vendor`` at apply-time so the same
  migration is a no-op on non-Postgres environments.

``CREATE INDEX CONCURRENTLY``:
* Postgres requires concurrent index creation to run OUTSIDE a
  transaction. ``atomic = False`` on the migration disables Django's
  wrapping; the operation runs in its own statement.
* ``IF NOT EXISTS`` makes the migration idempotent in case the index
  was created out-of-band before the migration ran.
"""

from django.db import migrations


def create_gin_index(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    schema_editor.execute(
        'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_eitem_tags_gin '
        'ON vault_encryptedvaultitem USING gin (tags);'
    )


def drop_gin_index(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    schema_editor.execute(
        'DROP INDEX CONCURRENTLY IF EXISTS idx_eitem_tags_gin;'
    )


class Migration(migrations.Migration):

    # CREATE INDEX CONCURRENTLY cannot run inside a transaction block.
    atomic = False

    dependencies = [
        ('vault', '0013_vaultbackup_content_md5'),
    ]

    operations = [
        migrations.RunPython(create_gin_index, reverse_code=drop_gin_index),
    ]
