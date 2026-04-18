"""Convert ``credential_id`` from UUIDField to CharField.

Allows callers to pass external, non-UUID identifiers while still being able
to store UUIDs as strings.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("security", "0014_userdevice_ip_address_nullable"),
    ]

    operations = [
        migrations.AlterField(
            model_name="predictiveexpirationrule",
            name="credential_id",
            field=models.CharField(db_index=True, max_length=128),
        ),
        migrations.AlterField(
            model_name="passwordrotationevent",
            name="credential_id",
            field=models.CharField(db_index=True, max_length=128),
        ),
    ]
