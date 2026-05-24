"""
Audit fix H6: add `UserSalt.sync_version` for optimistic concurrency on
vault sync.

Existing rows are backfilled to 0 (the default). Clients with an
existing token sending the new field as 0 will succeed on their first
sync after rollout; clients omitting the field entirely fall back to
row-lock-only mode (still safe — only loses optimistic concurrency
against a concurrent device).
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('vault', '0010_backfill_user_salt_auth_hash'),
    ]

    operations = [
        migrations.AddField(
            model_name='usersalt',
            name='sync_version',
            field=models.BigIntegerField(default=0),
        ),
    ]
