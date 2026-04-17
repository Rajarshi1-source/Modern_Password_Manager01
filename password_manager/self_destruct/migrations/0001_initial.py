"""Initial migration for self_destruct app."""

import uuid

from django.conf import settings
from django.db import migrations, models
from django.utils import timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='SelfDestructPolicy',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('vault_item_id', models.UUIDField(db_index=True)),
                ('kinds', models.JSONField(default=list)),
                ('status', models.CharField(choices=[('active', 'Active'), ('expired', 'Expired (policy fired)'), ('revoked', 'Revoked by owner')], default='active', max_length=16)),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
                ('max_uses', models.PositiveIntegerField(blank=True, null=True)),
                ('access_count', models.PositiveIntegerField(default=0)),
                ('geofence_lat', models.FloatField(blank=True, null=True)),
                ('geofence_lng', models.FloatField(blank=True, null=True)),
                ('geofence_radius_m', models.PositiveIntegerField(blank=True, null=True)),
                ('last_accessed_at', models.DateTimeField(blank=True, null=True)),
                ('last_denied_reason', models.CharField(blank=True, default='', max_length=64)),
                ('created_at', models.DateTimeField(default=timezone.now)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='self_destruct_policies', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'self_destruct_policies',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='selfdestructpolicy',
            index=models.Index(fields=['user', 'status'], name='sd_policy_user_status_idx'),
        ),
        migrations.AddIndex(
            model_name='selfdestructpolicy',
            index=models.Index(fields=['expires_at'], name='sd_policy_expires_idx'),
        ),
        migrations.CreateModel(
            name='SelfDestructEvent',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('decision', models.CharField(max_length=16)),
                ('reason', models.CharField(blank=True, default='', max_length=64)),
                ('ip', models.GenericIPAddressField(blank=True, null=True)),
                ('lat', models.FloatField(blank=True, null=True)),
                ('lng', models.FloatField(blank=True, null=True)),
                ('created_at', models.DateTimeField(db_index=True, default=timezone.now)),
                ('policy', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='events', to='self_destruct.selfdestructpolicy')),
            ],
            options={
                'db_table': 'self_destruct_events',
                'ordering': ['-created_at'],
            },
        ),
    ]
