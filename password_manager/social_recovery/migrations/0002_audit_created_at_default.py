from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("social_recovery", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="socialrecoveryauditlog",
            name="created_at",
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
    ]
