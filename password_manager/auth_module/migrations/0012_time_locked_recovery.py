"""Migration for Tier 3 (Self-Time-Locked) recovery models.

Chains off 0011_merge_layered_recovery (the single leaf left after
0008_wrapped_dek and 0010_recoveryshard_secret_type were collapsed).
Additive table creation — no dependency on the schema added by 0008
or 0010 beyond the implicit merge ordering.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('auth_module', '0011_merge_layered_recovery'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='TimeLockedRecovery',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('server_half', models.BinaryField()),
                ('half_metadata', models.JSONField(blank=True, default=dict)),
                ('release_after', models.DateTimeField(blank=True, null=True)),
                ('canary_state', models.CharField(
                    choices=[
                        ('quiet', 'Quiet (no active recovery)'),
                        ('alerting', 'Alerting (delay running)'),
                        ('acknowledged', 'Legitimate user acknowledged'),
                        ('expired', 'Released; one-shot consumed'),
                    ],
                    default='quiet',
                    max_length=16,
                )),
                ('last_canary_sent', models.DateTimeField(blank=True, null=True)),
                ('canary_ack_token', models.CharField(blank=True, default='', max_length=64)),
                ('initiated_at', models.DateTimeField(blank=True, null=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('enrolled_at', models.DateTimeField(auto_now_add=True)),
                ('is_active', models.BooleanField(default=True)),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='time_locked_recoveries',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'db_table': 'time_locked_recovery',
            },
        ),
        migrations.AddIndex(
            model_name='timelockedrecovery',
            index=models.Index(fields=['user', 'is_active'], name='tlr_user_active_idx'),
        ),
        migrations.AddIndex(
            model_name='timelockedrecovery',
            index=models.Index(fields=['canary_state', 'last_canary_sent'], name='tlr_canary_idx'),
        ),
        migrations.CreateModel(
            name='ServerHalfReleaseLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('attempted_at', models.DateTimeField(auto_now_add=True)),
                ('succeeded', models.BooleanField(default=False)),
                ('refusal_reason', models.CharField(blank=True, default='', max_length=64)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('user_agent', models.CharField(blank=True, default='', max_length=255)),
                ('recovery', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='release_log',
                    to='auth_module.timelockedrecovery',
                )),
            ],
            options={
                'db_table': 'server_half_release_log',
            },
        ),
        migrations.AddIndex(
            model_name='serverhalfreleaselog',
            index=models.Index(fields=['recovery', 'attempted_at'], name='shrl_recovery_attempted_idx'),
        ),
    ]
