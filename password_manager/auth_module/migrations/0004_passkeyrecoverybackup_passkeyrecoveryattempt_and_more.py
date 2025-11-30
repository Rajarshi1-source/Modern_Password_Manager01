# Generated for Passkey Primary Recovery System
# Migration 0004: Primary Passkey Recovery Models

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('auth_module', '0003_passkeyrecoverysetup_recoveryattempt_recoveryshard_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='PasskeyRecoveryBackup',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('passkey_credential_id', models.BinaryField(help_text='ID of the passkey this backup is for')),
                ('encrypted_credential_data', models.BinaryField(help_text='Kyber + AES-GCM encrypted passkey credential data')),
                ('recovery_key_hash', models.CharField(max_length=128, help_text='SHA-256 hash of the recovery key for validation')),
                ('kyber_public_key', models.BinaryField(help_text="User's Kyber public key for this backup")),
                ('encryption_metadata', models.JSONField(default=dict, help_text='Metadata for decryption (salt, IV, etc.)')),
                ('device_name', models.CharField(blank=True, max_length=255, help_text='Name of the device this backup is for')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('last_verified_at', models.DateTimeField(blank=True, null=True, help_text='Last time this backup was verified')),
                ('is_active', models.BooleanField(default=True, help_text='Whether this backup is currently valid')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='passkey_recovery_backups', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Passkey Recovery Backup',
                'verbose_name_plural': 'Passkey Recovery Backups',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='PasskeyRecoveryAttempt',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[
                    ('initiated', 'Initiated'),
                    ('key_verified', 'Recovery Key Verified'),
                    ('decryption_success', 'Decryption Successful'),
                    ('recovery_complete', 'Recovery Complete'),
                    ('key_invalid', 'Invalid Recovery Key'),
                    ('decryption_failed', 'Decryption Failed'),
                    ('fallback_initiated', 'Fallback to Social Mesh Initiated'),
                    ('failed', 'Failed'),
                ], default='initiated', max_length=30)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True, help_text='IP address of recovery attempt')),
                ('user_agent', models.TextField(blank=True, help_text='Browser/device user agent')),
                ('initiated_at', models.DateTimeField(auto_now_add=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('failed_at', models.DateTimeField(blank=True, null=True)),
                ('fallback_recovery_attempt_id', models.IntegerField(blank=True, null=True, help_text='ID of social mesh recovery attempt if fallback was initiated')),
                ('failure_reason', models.TextField(blank=True, help_text='Reason for failure if recovery failed')),
                ('notes', models.TextField(blank=True, help_text='Additional notes or context')),
                ('backup', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='recovery_attempts', to='auth_module.passkeyrecoverybackup')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='passkey_primary_recovery_attempts', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Passkey Primary Recovery Attempt',
                'verbose_name_plural': 'Passkey Primary Recovery Attempts',
                'ordering': ['-initiated_at'],
            },
        ),
        migrations.CreateModel(
            name='RecoveryKeyRevocation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('revoked_at', models.DateTimeField(auto_now_add=True)),
                ('reason', models.TextField(blank=True, help_text='Reason for revocation')),
                ('new_backup_created', models.BooleanField(default=False, help_text='Whether a new backup was created after revocation')),
                ('backup', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='revocations', to='auth_module.passkeyrecoverybackup')),
                ('revoked_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Recovery Key Revocation',
                'verbose_name_plural': 'Recovery Key Revocations',
                'ordering': ['-revoked_at'],
            },
        ),
        # Indexes for performance
        migrations.AddIndex(
            model_name='passkeyrecoverybackup',
            index=models.Index(fields=['user', 'is_active'], name='auth_module_pkr_user_active_idx'),
        ),
        migrations.AddIndex(
            model_name='passkeyrecoverybackup',
            index=models.Index(fields=['recovery_key_hash'], name='auth_module_pkr_key_hash_idx'),
        ),
        migrations.AddIndex(
            model_name='passkeyrecoveryattempt',
            index=models.Index(fields=['user', 'status'], name='auth_module_pkra_user_status_idx'),
        ),
        migrations.AddIndex(
            model_name='passkeyrecoveryattempt',
            index=models.Index(fields=['initiated_at'], name='auth_module_pkra_initiated_idx'),
        ),
    ]

