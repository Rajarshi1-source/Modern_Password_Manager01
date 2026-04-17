"""Initial migration for ultrasonic_pairing."""

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
            name='PairingSession',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('purpose', models.CharField(choices=[('device_enroll', 'Enroll a new device on this account'), ('item_share', 'In-person one-shot vault item transfer')], max_length=20)),
                ('status', models.CharField(choices=[('awaiting_responder', 'Waiting for responder to claim nonce'), ('claimed', 'Responder has claimed; awaiting SAS confirmation'), ('confirmed', 'Both sides confirmed shared secret'), ('delivered', 'Terminal action (share/enroll) complete'), ('expired', 'TTL exceeded before completion'), ('failed', 'Verification or protocol failure')], default='awaiting_responder', max_length=24)),
                ('initiator_pub_key', models.BinaryField()),
                ('responder_pub_key', models.BinaryField(blank=True, null=True)),
                ('nonce', models.BinaryField()),
                ('nonce_key', models.CharField(max_length=12, unique=True)),
                ('sas_hmac', models.BinaryField(blank=True, null=True)),
                ('payload_ciphertext', models.BinaryField(blank=True, null=True)),
                ('payload_nonce', models.BinaryField(blank=True, null=True)),
                ('payload_vault_item_id', models.CharField(blank=True, default='', max_length=64)),
                ('created_at', models.DateTimeField(default=timezone.now)),
                ('expires_at', models.DateTimeField(db_index=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('initiator', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='initiated_pairings', to=settings.AUTH_USER_MODEL)),
                ('responder', models.ForeignKey(blank=True, null=True, on_delete=models.deletion.SET_NULL, related_name='claimed_pairings', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'ultrasonic_pairing_sessions',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='pairingsession',
            index=models.Index(fields=['initiator', 'status'], name='up_session_init_st_idx'),
        ),
        migrations.AddIndex(
            model_name='pairingsession',
            index=models.Index(fields=['status', 'expires_at'], name='up_session_st_exp_idx'),
        ),
        migrations.CreateModel(
            name='PairingEvent',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('kind', models.CharField(max_length=32)),
                ('ip', models.GenericIPAddressField(blank=True, null=True)),
                ('user_agent', models.CharField(blank=True, default='', max_length=255)),
                ('detail', models.CharField(blank=True, default='', max_length=255)),
                ('created_at', models.DateTimeField(db_index=True, default=timezone.now)),
                ('actor', models.ForeignKey(blank=True, null=True, on_delete=models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('session', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='events', to='ultrasonic_pairing.pairingsession')),
            ],
            options={
                'db_table': 'ultrasonic_pairing_events',
                'ordering': ['-created_at'],
            },
        ),
    ]
