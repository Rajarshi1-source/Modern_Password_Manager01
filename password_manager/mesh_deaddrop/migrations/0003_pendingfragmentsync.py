"""
Migration: Add PendingFragmentSync queue for offline node delivery.
"""

from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('mesh_deaddrop', '0002_meshnode_total_uptime_hours'),
    ]

    operations = [
        migrations.CreateModel(
            name='PendingFragmentSync',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('encrypted_payload', models.BinaryField(blank=True, null=True, help_text='Optional pre-encrypted payload snapshot to deliver')),
                ('payload_hash', models.CharField(blank=True, default='', help_text='BLAKE3 hash of payload for integrity', max_length=128)),
                ('status', models.CharField(choices=[('queued', 'Queued'), ('delivering', 'Delivering'), ('delivered', 'Delivered'), ('failed', 'Failed'), ('cancelled', 'Cancelled')], default='queued', max_length=16)),
                ('retry_count', models.IntegerField(default=0)),
                ('max_retries', models.IntegerField(default=10)),
                ('last_attempt_at', models.DateTimeField(blank=True, null=True)),
                ('next_retry_at', models.DateTimeField(blank=True, null=True)),
                ('last_error', models.TextField(blank=True, default='')),
                ('queued_at', models.DateTimeField(auto_now_add=True)),
                ('delivered_at', models.DateTimeField(blank=True, null=True)),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
                ('node', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pending_syncs', to='mesh_deaddrop.meshnode')),
                ('fragment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pending_syncs', to='mesh_deaddrop.deaddropfragment')),
                ('dead_drop', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pending_syncs', to='mesh_deaddrop.deaddrop')),
            ],
            options={
                'db_table': 'mesh_pending_fragment_sync',
                'verbose_name': 'Pending Fragment Sync',
                'verbose_name_plural': 'Pending Fragment Syncs',
                'ordering': ['queued_at'],
            },
        ),
        migrations.AddIndex(
            model_name='pendingfragmentsync',
            index=models.Index(fields=['node', 'status'], name='mesh_sync_node_status_idx'),
        ),
        migrations.AddIndex(
            model_name='pendingfragmentsync',
            index=models.Index(fields=['status', 'next_retry_at'], name='mesh_sync_status_next_idx'),
        ),
        migrations.AddIndex(
            model_name='pendingfragmentsync',
            index=models.Index(fields=['dead_drop', 'status'], name='mesh_sync_drop_status_idx'),
        ),
        migrations.AddConstraint(
            model_name='pendingfragmentsync',
            constraint=models.UniqueConstraint(fields=('node', 'fragment'), name='uniq_pending_sync_per_node_fragment'),
        ),
    ]
