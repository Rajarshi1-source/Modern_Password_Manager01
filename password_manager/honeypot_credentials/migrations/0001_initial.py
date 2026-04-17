"""Initial schema for the honeypot_credentials app."""

import uuid
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='HoneypotTemplate',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(help_text='Short identifier ("corporate-admin-backup").', max_length=128, unique=True)),
                ('fake_site_template', models.CharField(help_text='Format string with {domain} placeholder, e.g. "internal-portal.{domain}".', max_length=255)),
                ('fake_username_template', models.CharField(help_text='E.g. "admin_backup@{domain}".', max_length=255)),
                ('password_pattern', models.CharField(default='corporate', help_text='Generator pattern: "corporate" (Title + Year + !), "leet" (l33tspeak), or "phrase" (two-word phrase).', max_length=128)),
                ('description', models.TextField(blank=True, default='')),
                ('is_builtin', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
            ],
            options={
                'db_table': 'honeypot_templates',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='HoneypotCredential',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('label', models.CharField(help_text='Owner-facing label — never shown to an attacker.', max_length=255)),
                ('fake_username', models.CharField(max_length=255)),
                ('fake_site', models.CharField(max_length=255)),
                ('decoy_password_encrypted', models.BinaryField(help_text='Fernet-encrypted decoy password bytes.')),
                ('decoy_strategy', models.CharField(choices=[('static', 'Static decoy from template'), ('rotating', 'Rotating decoy (nightly refresh)'), ('from_template', 'Template-parameterised by user')], default='static', max_length=20)),
                ('is_active', models.BooleanField(default=True)),
                ('alert_channels', models.JSONField(blank=True, default=list, help_text='Subset of ["email","sms","webhook","signal"].')),
                ('last_rotated_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('template', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='credentials', to='honeypot_credentials.honeypottemplate')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='honeypot_credentials', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'honeypot_credentials',
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['user', 'is_active'], name='hp_user_active_idx'),
                    models.Index(fields=['fake_site'], name='hp_fake_site_idx'),
                ],
            },
        ),
        migrations.CreateModel(
            name='HoneypotAccessEvent',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('access_type', models.CharField(choices=[('list_view', 'Listed alongside real entries'), ('retrieve', 'Retrieved (detail fetch)'), ('copy', 'Copied to clipboard'), ('autofill', 'Browser autofill fired')], max_length=20)),
                ('ip', models.GenericIPAddressField(blank=True, null=True)),
                ('user_agent', models.CharField(blank=True, default='', max_length=512)),
                ('geo_country', models.CharField(blank=True, default='', max_length=64)),
                ('geo_city', models.CharField(blank=True, default='', max_length=128)),
                ('session_key', models.CharField(blank=True, default='', max_length=64)),
                ('alert_sent', models.BooleanField(default=False)),
                ('alert_errors', models.JSONField(blank=True, default=dict)),
                ('accessed_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('honeypot', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='access_events', to='honeypot_credentials.honeypotcredential')),
            ],
            options={
                'db_table': 'honeypot_access_events',
                'ordering': ['-accessed_at'],
                'indexes': [
                    models.Index(fields=['honeypot', '-accessed_at'], name='hp_event_hp_time_idx'),
                    models.Index(fields=['ip', '-accessed_at'], name='hp_event_ip_time_idx'),
                ],
            },
        ),
    ]
