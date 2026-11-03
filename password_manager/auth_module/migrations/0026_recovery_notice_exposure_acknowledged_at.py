from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('auth_module', '0025_recovery_attempt_password_rotated_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='recoverynotice',
            name='exposure_acknowledged_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
