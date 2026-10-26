"""Rewrite vault.UserSalt.auth_hash values as password-hasher records (see
auth_module/auth_hash.py and auth_module 0021_hash_auth_hash)."""

from importlib import import_module

from django.db import migrations


def hash_rows(apps, schema_editor):
    import_module('auth_module.migrations.0021_hash_auth_hash').hash_model_rows(
        apps.get_model('vault', 'UserSalt'))


class Migration(migrations.Migration):

    dependencies = [
        ('vault', '0015_auditlog_action_choices'),
    ]

    operations = [
        migrations.RunPython(hash_rows, migrations.RunPython.noop),
    ]
