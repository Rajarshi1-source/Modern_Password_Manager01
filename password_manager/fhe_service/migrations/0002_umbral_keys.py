"""
Migration: add Umbral PRE (Proxy Re-Encryption) key fields to FHEKeyStore.

Adds public-key material for the Umbral-based "Homomorphic autofill
without decryption" feature. Secret keys stay client-side.

See password_manager/fhe_sharing/SPEC.md section 3.1.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fhe_service', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='fhekeystore',
            name='key_type',
            field=models.CharField(
                choices=[
                    ('concrete', 'Concrete-Python'),
                    ('seal_public', 'SEAL Public Key'),
                    ('seal_secret', 'SEAL Secret Key'),
                    ('seal_relin', 'SEAL Relinearization Key'),
                    ('seal_galois', 'SEAL Galois Key'),
                    ('umbral_pre', 'Umbral Proxy Re-Encryption'),
                ],
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='fhekeystore',
            name='umbral_public_key',
            field=models.BinaryField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='fhekeystore',
            name='umbral_verifying_key',
            field=models.BinaryField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='fhekeystore',
            name='umbral_signer_public_key',
            field=models.BinaryField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='fhekeystore',
            name='pre_schema_version',
            field=models.PositiveSmallIntegerField(default=1),
        ),
    ]
