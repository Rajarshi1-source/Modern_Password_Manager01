"""
Audit fix C11 (2026-05): persist the per-reveal nonce and commitment
hash so on-chain `VaultUnlocked` events remain reconstructible after
the fact. Previously the nonce was generated inside the service and
thrown away; the on-chain anchor became an opaque 32-byte blob.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('smart_contracts', '0002_released_tx_hash'),
    ]

    operations = [
        migrations.AddField(
            model_name='smartcontractvault',
            name='reveal_nonce',
            field=models.BinaryField(
                blank=True,
                default=b'',
                help_text=(
                    '16-byte per-reveal nonce used for the on-chain commitment'
                ),
            ),
        ),
        migrations.AddField(
            model_name='smartcontractvault',
            name='reveal_commitment',
            field=models.CharField(
                blank=True,
                default='',
                help_text=(
                    'keccak256 commitment hash anchored on-chain (0x-prefixed)'
                ),
                max_length=66,
            ),
        ),
    ]
