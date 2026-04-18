"""Add ``name_hash``/``name_search`` and give ``item_id`` a default.

Callers (PRE sharing, FHE search flows) expect to populate these
searchable hashes without providing their own ``item_id`` each time.
"""

from django.db import migrations, models

import vault.models.vault_models as _vault_models


class Migration(migrations.Migration):

    dependencies = [
        ("vault", "0007_remove_encryptedvaultitem_idx_vault_user_active"),
    ]

    operations = [
        migrations.AddField(
            model_name="encryptedvaultitem",
            name="name_hash",
            field=models.CharField(blank=True, default="", max_length=128),
        ),
        migrations.AddField(
            model_name="encryptedvaultitem",
            name="name_search",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AlterField(
            model_name="encryptedvaultitem",
            name="item_id",
            field=models.CharField(
                default=_vault_models._generate_item_id,
                max_length=64,
                unique=True,
            ),
        ),
    ]
