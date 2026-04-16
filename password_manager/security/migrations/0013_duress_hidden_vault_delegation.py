"""Add hidden-vault delegation fields to DuressCode."""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("security", "0012_timelockcapsule_status_unlock_idx"),
        ("stegano_vault", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="duresscode",
            name="delegate_to_hidden_vault",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "If True, the decoy payload returned on duress comes from the"
                    " linked StegoVault's hidden-vault blob instead of the legacy"
                    " DecoyVault table."
                ),
            ),
        ),
        migrations.AddField(
            model_name="duresscode",
            name="hidden_vault_slot",
            field=models.PositiveSmallIntegerField(
                default=0,
                help_text=(
                    "Which HiddenVaultBlob slot (0 or 1) this duress code unlocks."
                ),
            ),
        ),
        migrations.AddField(
            model_name="duresscode",
            name="stego_vault",
            field=models.ForeignKey(
                blank=True,
                help_text=(
                    "Optional link to the steganographic container whose blob"
                    " this duress code decrypts."
                ),
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="duress_codes",
                to="stegano_vault.stegovault",
            ),
        ),
    ]
