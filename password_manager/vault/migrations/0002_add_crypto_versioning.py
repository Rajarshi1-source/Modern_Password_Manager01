# Generated migration for crypto versioning support

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('vault', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='encryptedvaultitem',
            name='crypto_version',
            field=models.IntegerField(
                default=1,
                help_text='Cryptographic algorithm version (1=legacy, 2=enhanced Argon2id+dual ECC)'
            ),
        ),
        migrations.AddField(
            model_name='encryptedvaultitem',
            name='crypto_metadata',
            field=models.JSONField(
                default=dict,
                blank=True,
                help_text='Cryptographic metadata (algorithm versions, parameters, public keys)'
            ),
        ),
        migrations.AddField(
            model_name='encryptedvaultitem',
            name='pqc_wrapped_key',
            field=models.BinaryField(
                null=True,
                blank=True,
                help_text='Post-quantum wrapped encryption key (for future PQC migration)'
            ),
        ),
    ]

