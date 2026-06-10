"""Reconcile DataSubjectRequest index names with the model (migration drift).

Django's auto-generated index names for this model drifted from what
0001_initial recorded, so ``makemigrations --check`` reported pending renames.
These are pure index renames — no schema or data change.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("gdpr_compliance", "0001_initial"),
    ]

    operations = [
        migrations.RenameIndex(
            model_name="datasubjectrequest",
            new_name="gdpr_compli_status_3b65ce_idx",
            old_name="gdpr_dsar_status_due_idx",
        ),
        migrations.RenameIndex(
            model_name="datasubjectrequest",
            new_name="gdpr_compli_request_d50ed6_idx",
            old_name="gdpr_dsar_type_sub_idx",
        ),
        migrations.RenameIndex(
            model_name="datasubjectrequest",
            new_name="gdpr_compli_subject_af0009_idx",
            old_name="gdpr_dsar_email_idx",
        ),
    ]
