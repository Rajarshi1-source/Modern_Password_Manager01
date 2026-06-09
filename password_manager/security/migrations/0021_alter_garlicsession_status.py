"""Reconcile GarlicSession.status with the model (long-standing migration drift).

The model's default for ``status`` was changed from ``'establishing'`` (recorded
in migration 0010) to ``'active'`` without a follow-up migration, so
``makemigrations --check`` reported persistent drift. This records that default
change (an app-level default; no DB schema change).
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("security", "0020_adaptive_zk_v2_drop_legacy_columns"),
    ]

    operations = [
        migrations.AlterField(
            model_name="garlicsession",
            name="status",
            field=models.CharField(
                choices=[
                    ("establishing", "Establishing"),
                    ("active", "Active"),
                    ("suspended", "Suspended"),
                    ("terminated", "Terminated"),
                ],
                default="active",
                max_length=20,
            ),
        ),
    ]
