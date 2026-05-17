"""Add ``secret_type`` field to RecoveryShard for vault-DEK reuse."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("auth_module", "0007_recoveryshard_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="recoveryshard",
            name="secret_type",
            field=models.CharField(
                choices=[
                    ("passkey_private_key", "Passkey Private Key"),
                    ("vault_dek_seed", "Vault DEK Recovery Seed"),
                ],
                db_index=True,
                default="passkey_private_key",
                help_text=(
                    "What kind of secret this shard reconstructs. "
                    "Existing shards default to passkey_private_key."
                ),
                max_length=32,
            ),
        ),
    ]
