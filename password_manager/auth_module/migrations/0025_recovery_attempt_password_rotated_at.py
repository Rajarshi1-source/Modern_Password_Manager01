from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('auth_module', '0024_recovery_attempt_requester_token'),
    ]

    operations = [
        migrations.AddField(
            model_name='recoveryattempt',
            name='password_rotated_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
