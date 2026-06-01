# Audit Group D / finding #15: certificate signature-format version.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('security', '0017_add_missing_model_fields'),
    ]

    operations = [
        # Step 1: add the column, backfilling pre-rollout rows as legacy
        # (1). preserve_default=False keeps this 1 out of the migration's
        # historical field state so it's a one-off backfill value only.
        migrations.AddField(
            model_name='geneticpasswordcertificate',
            name='cert_version',
            field=models.IntegerField(
                default=1,
                help_text='Certificate signature format version (1=legacy, 2=canonical JSON)',
            ),
            preserve_default=False,
        ),
        # Step 2: set the field's real default to 2 (canonical JSON) in
        # both the DB and the migration state, so the graph matches
        # models.py (no spurious AlterField on `makemigrations --check`)
        # and new rows that omit cert_version default to v2. Existing rows
        # backfilled in step 1 keep their value of 1.
        migrations.AlterField(
            model_name='geneticpasswordcertificate',
            name='cert_version',
            field=models.IntegerField(
                default=2,
                help_text='Certificate signature format version (1=legacy, 2=canonical JSON)',
            ),
        ),
    ]
