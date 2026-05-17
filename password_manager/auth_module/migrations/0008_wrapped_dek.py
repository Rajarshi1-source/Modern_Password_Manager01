"""Add VaultWrappedDEK and RecoveryWrappedDEK models (Layered Recovery Mesh — Unit 1)."""

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('auth_module', '0007_recoveryshard_status'),
        # Use the swappable user reference so deployments with a custom
        # AUTH_USER_MODEL wire these FKs to the correct table.
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='VaultWrappedDEK',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('blob', models.JSONField(help_text="Self-describing envelope {v, kdf, kdf_params, salt, iv, wrapped}; server never inspects 'wrapped'.")),
                ('dek_id', models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, help_text='Stable identity of the underlying DEK; unchanged across master-password rotations.')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('rotated_at', models.DateTimeField(blank=True, null=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='vault_dek', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Vault Wrapped DEK',
                'verbose_name_plural': 'Vault Wrapped DEKs',
                'db_table': 'vault_wrapped_dek',
            },
        ),
        migrations.CreateModel(
            name='RecoveryWrappedDEK',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('factor_type', models.CharField(choices=[('recovery_key', 'Printable Recovery Key'), ('social_mesh', 'Social Mesh (Shamir)'), ('time_locked', 'Time-Locked Self-Recovery'), ('passkey', 'Local Passkey')], db_index=True, max_length=32)),
                ('dek_id', models.UUIDField(db_index=True, help_text='Matches VaultWrappedDEK.dek_id — every active factor wraps the same logical DEK.')),
                ('blob', models.JSONField(help_text="Self-describing envelope; server never inspects 'wrapped'.")),
                ('factor_meta', models.JSONField(blank=True, default=dict, help_text='Factor-specific public metadata (e.g. share index, unlock-after timestamp, passkey credential id). Never contains secrets.')),
                ('status', models.CharField(choices=[('active', 'Active'), ('revoked', 'Revoked')], default='active', max_length=16)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('last_used_at', models.DateTimeField(blank=True, null=True)),
                ('revoked_at', models.DateTimeField(blank=True, null=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='recovery_factors', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Recovery Wrapped DEK',
                'verbose_name_plural': 'Recovery Wrapped DEKs',
                'db_table': 'recovery_wrapped_dek',
            },
        ),
        migrations.AddIndex(
            model_name='recoverywrappeddek',
            index=models.Index(fields=['user', 'status'], name='recovery_wr_user_id_2c9c0e_idx'),
        ),
        migrations.AddIndex(
            model_name='recoverywrappeddek',
            index=models.Index(fields=['user', 'factor_type', 'status'], name='recovery_wr_user_id_4d1f3a_idx'),
        ),
        migrations.AddConstraint(
            model_name='recoverywrappeddek',
            constraint=models.UniqueConstraint(
                condition=models.Q(('factor_type', 'recovery_key'), ('status', 'active')),
                fields=('user',),
                name='unique_active_recovery_key_per_user',
            ),
        ),
    ]
