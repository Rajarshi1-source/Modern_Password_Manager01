"""Cross-link AmbientContext with security.GeofenceZone."""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ambient_auth", "0001_initial"),
        ("security", "0005_locationhistory_impossibletravelevent_geofencezone_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="ambientcontext",
            name="linked_geofence",
            field=models.ForeignKey(
                blank=True,
                help_text=(
                    "Optional cross-link to a GeofenceZone. If the user is "
                    "inside the linked zone, ambient trust may be treated "
                    "as corroborated."
                ),
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="ambient_contexts",
                to="security.geofencezone",
            ),
        ),
    ]
