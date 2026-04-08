"""
Migration: Add total_uptime_hours to MeshNode
"""

from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('mesh_deaddrop', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='meshnode',
            name='total_uptime_hours',
            field=models.FloatField(
                default=0.0,
                help_text='Cumulative hours this node has been online',
                validators=[django.core.validators.MinValueValidator(0.0)],
            ),
        ),
    ]
