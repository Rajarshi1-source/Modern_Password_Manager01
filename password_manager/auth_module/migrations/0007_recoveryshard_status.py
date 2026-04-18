"""Add ``status`` field to RecoveryShard."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("auth_module", "0006_alter_recoveryauditlog_cryptographic_hash"),
    ]

    operations = [
        migrations.AddField(
            model_name="recoveryshard",
            name="status",
            field=models.CharField(
                choices=[
                    ("active", "Active"),
                    ("revoked", "Revoked"),
                    ("expired", "Expired"),
                    ("honeypot_triggered", "Honeypot Triggered"),
                ],
                db_index=True,
                default="active",
                max_length=32,
            ),
        ),
    ]
