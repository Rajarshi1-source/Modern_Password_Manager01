"""
Audit fix C10 (2026-05): backfill the `auth_hash` on every existing
`vault.UserSalt` row from the authoritative `auth_module.UserSalt` row
written at registration.

Background:
    Two `UserSalt` models exist — one in `auth_module` (populated at
    register) and one in `vault` (populated on first vault access). The
    vault row was created via `get_or_create` with `auth_hash=b''`, and
    the old `verify_auth` view would WRITE whatever the caller posted
    into that empty slot. A JWT-bearing attacker could therefore claim a
    victim's vault.

    The view-side fix refuses to fall back. This data migration ensures
    legitimate users with a half-provisioned vault row are not locked
    out by that refusal — we copy the real auth_hash over before the
    code change takes effect.
"""

from django.db import migrations


def backfill_vault_auth_hash(apps, schema_editor):
    VaultSalt = apps.get_model('vault', 'UserSalt')
    AuthSalt = apps.get_model('auth_module', 'UserSalt')

    # Build a quick lookup from user_id → auth_hash bytes.
    auth_map = {row.user_id: bytes(row.auth_hash) for row in AuthSalt.objects.all()}

    # Update rows that are empty AND have an authoritative source.
    updated = 0
    for vs in VaultSalt.objects.all():
        current = bytes(vs.auth_hash or b'')
        if current and current != b'':
            continue
        seed = auth_map.get(vs.user_id)
        if seed:
            vs.auth_hash = seed
            vs.save(update_fields=['auth_hash'])
            updated += 1

    # Stash the count in the schema_editor for debugging; the migration
    # framework swallows print(), so a logger record is the safer signal.
    import logging
    logging.getLogger('vault.migrations').info(
        "0010_backfill_user_salt_auth_hash: updated %s vault.UserSalt rows", updated
    )


def reverse(apps, schema_editor):
    """Intentional no-op — we don't blank correct hashes back out."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('vault', '0009_alter_encryptedvaultitem_item_id_and_more'),
        ('auth_module', '0005_kyber_optimization_models'),
    ]

    operations = [
        migrations.RunPython(backfill_vault_auth_hash, reverse),
    ]
