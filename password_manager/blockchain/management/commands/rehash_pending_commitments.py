"""
One-shot post-audit command to clear stale SHA-256 pending commitments
so the next anchor batch is built with the keccak256 hasher.

Usage:
    python manage.py rehash_pending_commitments [--dry-run]

Background:
    The pre-2026-05 codebase hashed Merkle leaves with SHA-256 while the
    on-chain contract expected keccak256. Any PendingCommitment row that
    was created against the old hasher carries a hash value that is
    incompatible with the new build pipeline. We don't try to recompute
    them in-place because the underlying BehavioralCommitment is the
    authoritative input — the next call to `add_commitment` will produce
    a fresh keccak256 hash for the same data.

This command:
    1. Deletes existing PendingCommitment rows with `is_anchored=False`.
    2. Re-enqueues a fresh commitment via add_commitment for any
       BehavioralCommitment that has no associated MerkleProof yet, so
       it gets anchored on the next batch with keccak256.

Anchored rows (`is_anchored=True`) are NOT touched — their old proofs are
already flagged `verifiable=False` by migration 0003 and surface as
`legacy_hash_mismatch` from the verify endpoint.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from blockchain.models import PendingCommitment, MerkleProof
from blockchain.services.blockchain_anchor_service import (
    get_blockchain_anchor_service,
)


class Command(BaseCommand):
    help = "Clear stale SHA-256 pending commitments and re-enqueue."

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help="Report counts without modifying the database.",
        )

    def handle(self, *args, **opts):
        dry_run = opts['dry_run']

        stale = PendingCommitment.objects.filter(is_anchored=False)
        stale_count = stale.count()

        self.stdout.write(
            f"Found {stale_count} pending commitment(s) to clear."
        )

        if dry_run:
            self.stdout.write(self.style.WARNING(
                "--dry-run set; not modifying the database."
            ))
            return

        # Snapshot the rows we plan to replace so the loop has stable
        # data to work from, but DO NOT delete the originals up front.
        # If `add_commitment` fails (anchoring disabled, lookup failure,
        # the process dies mid-loop) we want the pre-fix pending row to
        # remain so a future invocation can retry. Originals are deleted
        # one-by-one only after their replacement is successfully
        # persisted — added per CodeRabbit review.
        commitments_to_requeue = list(
            stale.select_related('user', 'commitment').values(
                'id',  # original PendingCommitment row pk
                'user_id',
                'commitment_id',
                'commitment__encrypted_embedding',
            )
        )

        service = get_blockchain_anchor_service()
        requeued = 0
        skipped_already_anchored = 0
        failed = 0

        for row in commitments_to_requeue:
            original_pk = row['id']

            # Skip if this commitment already has a verifiable proof
            # (could happen if some other batch ran in between).
            already_proven = MerkleProof.objects.filter(
                commitment_id=row['commitment_id'],
                verifiable=True,
            ).exists()
            if already_proven:
                # Safe to drop the stale row: a fresh verifiable proof
                # already exists for this commitment.
                with transaction.atomic():
                    PendingCommitment.objects.filter(pk=original_pk).delete()
                skipped_already_anchored += 1
                continue

            # encrypted_embedding is a BinaryField; coerce to hex for the
            # string-typed add_commitment helper, falling back to empty.
            raw = row['commitment__encrypted_embedding']
            if isinstance(raw, memoryview):
                raw = bytes(raw)
            encrypted_data = raw.hex() if isinstance(raw, (bytes, bytearray)) else (raw or '')

            # Replace the stale row with a fresh keccak256-hashed one
            # atomically: the new row is created inside the same
            # transaction that deletes the old. If `add_commitment`
            # raises or returns None (e.g. anchoring disabled), the
            # transaction rolls back and the original survives.
            try:
                with transaction.atomic():
                    new_hash = service.add_commitment(
                        user_id=row['user_id'],
                        commitment_id=row['commitment_id'],
                        encrypted_data=encrypted_data,
                    )
                    if not new_hash:
                        raise RuntimeError(
                            "add_commitment returned no hash; refusing to "
                            "delete the original pending row."
                        )
                    # Confirm the new row is durable before retiring the old.
                    if not PendingCommitment.objects.filter(
                        commitment_hash=new_hash
                    ).exists():
                        raise RuntimeError(
                            "Replacement PendingCommitment did not persist; "
                            "refusing to delete the original."
                        )
                    PendingCommitment.objects.filter(pk=original_pk).delete()
                requeued += 1
            except Exception as exc:
                self.stdout.write(self.style.WARNING(
                    f"Re-enqueue failed for PendingCommitment {original_pk}: "
                    f"{exc}. Original row preserved."
                ))
                failed += 1

        self.stdout.write(self.style.SUCCESS(
            f"Re-enqueued {requeued} commitment(s); "
            f"skipped {skipped_already_anchored} already-anchored; "
            f"failed {failed} (originals preserved)."
        ))
