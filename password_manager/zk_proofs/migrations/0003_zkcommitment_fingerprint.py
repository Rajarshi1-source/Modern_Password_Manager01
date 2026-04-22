"""Add ``commitment_fingerprint`` + uniqueness on (user, commitment bytes).

Backfills the fingerprint for existing rows by hashing the stored
``commitment`` bytes; collisions are astronomically unlikely for a
SHA-256 over 33-byte SEC1 points, so the unique index creation is
effectively unconditional.
"""

from __future__ import annotations

import hashlib

from django.db import migrations, models


def _backfill_fingerprints(apps, schema_editor):
    ZKCommitment = apps.get_model("zk_proofs", "ZKCommitment")
    for row in ZKCommitment.objects.all().iterator():
        blob = bytes(row.commitment or b"")
        row.commitment_fingerprint = hashlib.sha256(blob).hexdigest()
        row.save(update_fields=["commitment_fingerprint"])


class Migration(migrations.Migration):

    dependencies = [
        ("zk_proofs", "0002_zksession_zksessionparticipant"),
    ]

    operations = [
        migrations.AddField(
            model_name="zkcommitment",
            name="commitment_fingerprint",
            field=models.CharField(
                default="",
                max_length=64,
                db_index=True,
                help_text=(
                    "SHA-256 hex of ``commitment``. Used to enforce per-user "
                    "uniqueness of commitment bytes, which blocks the D=0 "
                    "equality-proof abuse where the same commitment is "
                    "registered twice and then 'proven' equal to itself."
                ),
            ),
        ),
        migrations.RunPython(
            _backfill_fingerprints,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.AddConstraint(
            model_name="zkcommitment",
            constraint=models.UniqueConstraint(
                fields=("user", "commitment_fingerprint"),
                name="zk_proofs_zkcommitment_unique_bytes",
            ),
        ),
    ]
