"""Make ``UserDevice.ip_address`` nullable.

Historically this column was non-null, but tests (and mobile/offline
flows) may register a device before its IP is known. The field is now
``null=True, blank=True`` to allow safe creation without knowing the IP.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("security", "0013_duress_hidden_vault_delegation"),
    ]

    operations = [
        migrations.AlterField(
            model_name="userdevice",
            name="ip_address",
            field=models.GenericIPAddressField(blank=True, null=True),
        ),
    ]
