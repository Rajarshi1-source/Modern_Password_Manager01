"""
Audit fix M8 (2026-05): record the client's Content-MD5 precommitment
on each cloud backup row so ``complete_cloud_upload`` can verify the
uploaded blob matches what was presigned.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('vault', '0012_backfill_name_hash_sentinel'),
    ]

    operations = [
        migrations.AddField(
            model_name='vaultbackup',
            name='content_md5',
            field=models.CharField(blank=True, default='', max_length=32),
        ),
    ]
