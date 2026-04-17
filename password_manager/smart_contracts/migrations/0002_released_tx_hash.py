"""Add released_tx_hash + released_at to SmartContractVault for the
hybrid on-chain reveal audit trail (VaultAuditLog contract).
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('smart_contracts', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='smartcontractvault',
            name='released_tx_hash',
            field=models.CharField(
                blank=True,
                default='',
                help_text='VaultAuditLog.anchorUnlock() transaction hash (0x-prefixed)',
                max_length=66,
            ),
        ),
        migrations.AddField(
            model_name='smartcontractvault',
            name='released_at',
            field=models.DateTimeField(
                blank=True,
                help_text='Wall-clock time the on-chain anchor was confirmed',
                null=True,
            ),
        ),
    ]
