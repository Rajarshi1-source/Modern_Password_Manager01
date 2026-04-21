from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('social_recovery', '0002_rename_social_reco_user_id_7bf0cd_idx_social_reco_user_id_ddf884_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='relationshipcommitment',
            name='salt',
            field=models.BinaryField(blank=True, default=bytes),
        ),
    ]
