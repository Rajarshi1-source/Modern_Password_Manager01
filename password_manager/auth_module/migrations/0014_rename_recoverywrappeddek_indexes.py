"""Reconcile RecoveryWrappedDEK index names with the model (migration drift).

Django's auto-generated index names for this model drifted from what the prior
migration recorded, so ``makemigrations --check`` reported pending renames.
These are pure index renames — no schema or data change.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("auth_module", "0013_unique_active_factor_per_type"),
    ]

    operations = [
        migrations.RenameIndex(
            model_name="recoverywrappeddek",
            new_name="recovery_wr_user_id_fda5bd_idx",
            old_name="recovery_wr_user_id_2c9c0e_idx",
        ),
        migrations.RenameIndex(
            model_name="recoverywrappeddek",
            new_name="recovery_wr_user_id_5a4b47_idx",
            old_name="recovery_wr_user_id_4d1f3a_idx",
        ),
    ]
