"""
Audit fix M2 (2026-05): pin `BlockchainAnchor.batch_size` to the same
``1..10000`` window the on-chain ``CommitmentRegistry.anchorCommitment``
enforces. Validators are checked by Django form / serializer layers
(no SQL constraint is added — the contract is the source of truth and
existing rows are presumed compliant).
"""

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('blockchain', '0003_hash_algo_verifiable'),
    ]

    operations = [
        migrations.AlterField(
            model_name='blockchainanchor',
            name='batch_size',
            field=models.IntegerField(
                help_text='Number of commitments in this batch (1..10000)',
                validators=[
                    django.core.validators.MinValueValidator(1),
                    django.core.validators.MaxValueValidator(10000),
                ],
            ),
        ),
    ]
