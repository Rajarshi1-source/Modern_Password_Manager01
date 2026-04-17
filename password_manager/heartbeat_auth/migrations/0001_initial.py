"""Initial migration for heartbeat_auth."""

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
            name='HeartbeatProfile',
            fields=[
                ('status', models.CharField(choices=[('pending', 'Enrollment in progress'), ('enrolled', 'Ready to verify'), ('reset', 'Profile was wiped; needs re-enrollment')], default='pending', max_length=16)),
                ('enrollment_count', models.PositiveIntegerField(default=0)),
                ('baseline_mean', models.JSONField(blank=True, default=list)),
                ('baseline_cov', models.JSONField(blank=True, default=list)),
                ('baseline_rmssd', models.FloatField(blank=True, null=True)),
                ('baseline_sdnn', models.FloatField(blank=True, null=True)),
                ('baseline_mean_hr', models.FloatField(blank=True, null=True)),
                ('match_threshold', models.FloatField(default=0.75)),
                ('duress_rmssd_sigma', models.FloatField(default=2.0)),
                ('enrolled_at', models.DateTimeField(blank=True, null=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=models.deletion.CASCADE, primary_key=True, related_name='heartbeat_profile', serialize=False, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'heartbeat_profiles',
                'verbose_name': 'Heartbeat profile',
            },
        ),
        migrations.CreateModel(
            name='HeartbeatSession',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('session_type', models.CharField(choices=[('enroll', 'Enrollment reading'), ('verify', 'Verification reading')], max_length=10)),
                ('status', models.CharField(choices=[('pending', 'Upload received, not scored yet'), ('allowed', 'Matched baseline'), ('denied', 'Below match threshold'), ('duress', 'Match OK but stress signature tripped'), ('rejected', 'Reading quality too low')], default='pending', max_length=12)),
                ('match_score', models.FloatField(blank=True, null=True)),
                ('duress_probability', models.FloatField(blank=True, null=True)),
                ('duress_detected', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(default=timezone.now)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('user', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='heartbeat_sessions', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'heartbeat_sessions',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='heartbeatsession',
            index=models.Index(fields=['user', 'session_type'], name='hb_session_u_t_idx'),
        ),
        migrations.AddIndex(
            model_name='heartbeatsession',
            index=models.Index(fields=['user', 'status'], name='hb_session_u_s_idx'),
        ),
        migrations.CreateModel(
            name='HeartbeatReading',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('features', models.JSONField(default=dict)),
                ('rmssd', models.FloatField(blank=True, null=True)),
                ('sdnn', models.FloatField(blank=True, null=True)),
                ('mean_hr', models.FloatField(blank=True, null=True)),
                ('lf_hf_ratio', models.FloatField(blank=True, null=True)),
                ('pnn50', models.FloatField(blank=True, null=True)),
                ('rr_intervals', models.JSONField(blank=True, default=list)),
                ('capture_duration_s', models.FloatField(blank=True, null=True)),
                ('frame_rate', models.FloatField(blank=True, null=True)),
                ('captured_at', models.DateTimeField(default=timezone.now)),
                ('session', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='readings', to='heartbeat_auth.heartbeatsession')),
            ],
            options={
                'db_table': 'heartbeat_readings',
                'ordering': ['-captured_at'],
            },
        ),
        migrations.CreateModel(
            name='HeartbeatEvent',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('decision', models.CharField(max_length=12)),
                ('reason', models.CharField(blank=True, default='', max_length=64)),
                ('ip', models.GenericIPAddressField(blank=True, null=True)),
                ('created_at', models.DateTimeField(db_index=True, default=timezone.now)),
                ('session', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='events', to='heartbeat_auth.heartbeatsession')),
            ],
            options={
                'db_table': 'heartbeat_events',
                'ordering': ['-created_at'],
            },
        ),
    ]
