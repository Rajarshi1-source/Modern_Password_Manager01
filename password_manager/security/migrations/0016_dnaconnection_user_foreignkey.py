"""Relax ``DNAConnection.user`` from OneToOne to ForeignKey.

This lets a user record multiple provider connections over time (e.g., when
switching providers or retaining history), while the application layer keeps
only one ``is_active=True`` row per user.
"""

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("security", "0015_predictive_credential_id_char"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="dnaconnection",
            name="user",
            field=models.ForeignKey(
                on_delete=models.deletion.CASCADE,
                related_name="dna_connections",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
