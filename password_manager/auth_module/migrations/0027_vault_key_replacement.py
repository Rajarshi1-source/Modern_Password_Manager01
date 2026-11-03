from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('auth_module', '0026_recovery_notice_exposure_acknowledged_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='vaultwrappeddek',
            name='retired_keys',
            field=models.JSONField(blank=True, default=list, help_text="Replaced DEKs, oldest first: [{v, dek_id, iv, wrapped}], each encrypted under the DEK that replaced it; server never inspects 'wrapped'."),
        ),
        migrations.AddField(
            model_name='vaultwrappeddek',
            name='key_replaced_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='recoverynotice',
            name='event',
            field=models.CharField(choices=[('reset_requested', 'Password reset requested'), ('reset_completed', 'Password reset completed'), ('recovery_completed', 'Vault recovery completed'), ('passkey_recovery_started', 'Passkey recovery started'), ('passkey_recovery_completed', 'Passkey recovery completed'), ('guardian_recovery_started', 'Guardian recovery started'), ('guardian_recovery_completed', 'Guardian recovery completed'), ('social_recovery_started', 'Social recovery started'), ('social_recovery_completed', 'Social recovery completed'), ('account_unlocked', 'Account unlocked by support'), ('vault_key_replaced', 'Vault key replaced')], max_length=32),
        ),
    ]
