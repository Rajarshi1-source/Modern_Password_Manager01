"""Rewrite stored master-password auth_hash values as password-hasher records.

auth_module.UserSalt (and vault.UserSalt, see vault 0016) held the client's PBKDF2 output as
sent; a leak allowed offline guessing at PBKDF2 cost. Each raw value becomes
``make_password(base64(raw))`` (auth_module/auth_hash.py). The server has the
raw values, so no client is involved. Not reversible: the raw values are gone,
so a rollback is a database restore, or rolling forward. Reset links issued in
the hour before this runs stop working, because their token covers the stored
bytes: those users request a new link.
"""

from django.db import migrations


def hash_model_rows(model):
    from auth_module.auth_hash import is_hashed_record, make_auth_hash_record

    for row in model.objects.exclude(auth_hash=b'').iterator():
        raw = bytes(row.auth_hash or b'')
        if raw and not is_hashed_record(raw):
            # Conditional on the value just read: a concurrent change_master
            # is not overwritten with the old password's record.
            model.objects.filter(pk=row.pk, auth_hash=raw).update(
                auth_hash=make_auth_hash_record(raw))


def hash_rows(apps, schema_editor):
    # vault.UserSalt is rewritten by vault 0016_hash_auth_hash.
    hash_model_rows(apps.get_model('auth_module', 'UserSalt'))


class Migration(migrations.Migration):

    dependencies = [
        ('auth_module', '0021_recovery_notice'),
    ]

    operations = [
        migrations.RunPython(hash_rows),
    ]
