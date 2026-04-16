"""
Migration: add real PRE (Umbral) payload fields to HomomorphicShare.

Introduces `cipher_suite` plus six binary fields (`capsule`,
`ciphertext`, `kfrag`, `delegating_pk`, `verifying_pk`,
`receiving_pk`). Legacy `encrypted_autofill_token` becomes nullable
so `cipher_suite='umbral-v1'` rows don't need to carry a dummy
payload.

See password_manager/fhe_sharing/SPEC.md sections 3.2 and 8.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fhe_sharing', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='homomorphicshare',
            name='encrypted_autofill_token',
            field=models.BinaryField(
                blank=True,
                null=True,
                help_text=(
                    "Legacy (simulated-v1) autofill circuit token. NULL "
                    "for rows where `cipher_suite='umbral-v1'`."
                ),
            ),
        ),
        migrations.AddField(
            model_name='homomorphicshare',
            name='cipher_suite',
            field=models.CharField(
                default='simulated-v1',
                db_index=True,
                max_length=24,
                help_text="Which ciphertext payload format this row uses.",
            ),
        ),
        migrations.AddField(
            model_name='homomorphicshare',
            name='capsule',
            field=models.BinaryField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='homomorphicshare',
            name='ciphertext',
            field=models.BinaryField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='homomorphicshare',
            name='kfrag',
            field=models.BinaryField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='homomorphicshare',
            name='delegating_pk',
            field=models.BinaryField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='homomorphicshare',
            name='verifying_pk',
            field=models.BinaryField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='homomorphicshare',
            name='receiving_pk',
            field=models.BinaryField(blank=True, null=True),
        ),
    ]
