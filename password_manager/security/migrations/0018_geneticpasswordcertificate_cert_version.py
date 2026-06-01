# Audit Group D / finding #15: certificate signature-format version.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('security', '0017_add_missing_model_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='geneticpasswordcertificate',
            name='cert_version',
            field=models.IntegerField(
                default=1,
                help_text='Certificate signature format version (1=legacy, 2=canonical JSON)',
            ),
        ),
    ]
