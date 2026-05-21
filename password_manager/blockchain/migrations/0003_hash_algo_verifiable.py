"""
Audit fix C1 (2026-05): add hash-algorithm provenance to anchored rows.

The Python Merkle tree builder previously hashed with SHA-256 while both
the on-chain `CommitmentRegistry.verifyCommitment` function and the
in-memory `verify_proof_locally` helper used keccak256. The on-chain
roots stored for those rows are therefore unrecoverable by the new
verifier path.

This migration:

  1. Adds `BlockchainAnchor.hash_algo` (default 'keccak256') and
     `BlockchainAnchor.verifiable` (default True).
  2. Adds the same `verifiable` flag to `MerkleProof` so callers can
     filter without joining.
  3. Backfills every EXISTING row to hash_algo='sha256', verifiable=False
     so old proofs are clearly marked unrecoverable.

After this migration, operators with `BLOCKCHAIN_ENABLED=True` should run
`python manage.py rehash_pending_commitments` (added separately) to
re-enqueue any not-yet-anchored work for fresh keccak256 anchoring.
"""

from django.db import migrations, models


def mark_legacy_rows(apps, schema_editor):
    """Set existing rows to sha256/unverifiable in a single UPDATE each."""
    BlockchainAnchor = apps.get_model('blockchain', 'BlockchainAnchor')
    MerkleProof = apps.get_model('blockchain', 'MerkleProof')

    # The field defaults make new rows keccak256/verifiable=True; here we
    # only need to flip the rows that already exist.
    BlockchainAnchor.objects.all().update(hash_algo='sha256', verifiable=False)
    MerkleProof.objects.all().update(verifiable=False)


def reverse_mark_legacy(apps, schema_editor):
    """No-op: we don't pretend to know the original algorithm on rollback."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('blockchain', '0002_blockchainanchor_submitter_address_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='blockchainanchor',
            name='hash_algo',
            field=models.CharField(
                default='keccak256',
                help_text=(
                    "Hash algorithm used to build the Merkle tree for this batch. "
                    "Pre-2026-05 rows are 'sha256' and cannot be verified on-chain "
                    "(the contract expects keccak256). New batches use 'keccak256'."
                ),
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name='blockchainanchor',
            name='verifiable',
            field=models.BooleanField(
                default=True,
                help_text=(
                    "False for rows anchored before the hash-algorithm fix; their "
                    "on-chain merkle root is correct but cannot be matched by the "
                    "new verifier path. Re-anchor by enqueueing PendingCommitments."
                ),
            ),
        ),
        migrations.AddField(
            model_name='merkleproof',
            name='verifiable',
            field=models.BooleanField(
                default=True,
                help_text=(
                    "Mirrors BlockchainAnchor.verifiable so callers can filter "
                    "without joining. False for legacy SHA-256 proofs."
                ),
            ),
        ),
        migrations.RunPython(mark_legacy_rows, reverse_mark_legacy),
    ]
