"""
Celery Tasks for Blockchain Anchoring

Periodic tasks for batching and anchoring commitments to Arbitrum blockchain
"""

from celery import shared_task
from celery.utils.log import get_task_logger
from django.conf import settings

logger = get_task_logger(__name__)


@shared_task(bind=True, max_retries=3)
def anchor_pending_commitments(self):
    """
    Celery beat task to anchor pending commitments to blockchain
    
    This task runs periodically (default: every 24 hours) to:
    1. Check if there are pending commitments
    2. Build a Merkle tree from the batch
    3. Submit the Merkle root to Arbitrum blockchain
    4. Store Merkle proofs in database
    
    Returns:
        str: Status message with transaction hash if successful
    """
    try:
        # Import here to avoid circular imports
        from .services.blockchain_anchor_service import BlockchainAnchorService
        from .models import PendingCommitment
        
        # Check if blockchain anchoring is enabled
        if not settings.BLOCKCHAIN_ANCHORING.get('ENABLED', False):
            logger.info("Blockchain anchoring is disabled in settings")
            return "Blockchain anchoring disabled"
        
        # Initialize service
        service = BlockchainAnchorService()
        
        # Check if we have pending commitments
        pending_count = PendingCommitment.objects.filter(is_anchored=False).count()
        
        if pending_count == 0:
            logger.info("No pending commitments to anchor")
            return "No pending commitments"
        
        logger.info(f"Found {pending_count} pending commitments. Initiating anchoring...")
        
        # Anchor the batch
        result = service.anchor_pending_batch()
        
        if result['success']:
            tx_hash = result['tx_hash']
            anchored_count = result['anchored_count']
            merkle_root = result['merkle_root']
            
            logger.info(
                f"✅ Successfully anchored {anchored_count} commitments. "
                f"TX: {tx_hash}, Merkle Root: {merkle_root}"
            )
            
            return f"Anchored {anchored_count} commitments: {tx_hash}"
        else:
            error_msg = result.get('error', 'Unknown error')
            logger.error(f"❌ Failed to anchor commitments: {error_msg}")
            
            # Retry with exponential backoff
            raise self.retry(countdown=60 * (2 ** self.request.retries))
            
    except Exception as exc:
        logger.exception(f"Error in anchor_pending_commitments task: {exc}")
        
        # Retry up to 3 times with exponential backoff
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
        else:
            logger.error("Max retries reached for anchoring task. Giving up.")
            return f"Failed after {self.max_retries} retries: {str(exc)}"


@shared_task
def verify_blockchain_anchors():
    """
    Verify existing blockchain anchors by checking on-chain status
    
    This task periodically verifies that anchored commitments are still
    valid on the blockchain and updates their status.
    """
    try:
        from .services.blockchain_anchor_service import BlockchainAnchorService
        from .models import BlockchainAnchor
        from django.utils import timezone
        from datetime import timedelta
        
        # Check if blockchain anchoring is enabled
        if not settings.BLOCKCHAIN_ANCHORING.get('ENABLED', False):
            return "Blockchain anchoring disabled"
        
        service = BlockchainAnchorService()
        
        # Get recent anchors (last 30 days) that haven't been verified recently
        cutoff_date = timezone.now() - timedelta(days=30)
        anchors = BlockchainAnchor.objects.filter(
            timestamp__gte=cutoff_date
        )[:100]  # Limit to 100 to avoid rate limits
        
        verified_count = 0
        failed_count = 0
        
        for anchor in anchors:
            try:
                is_valid = service.verify_commitment_on_chain(anchor.merkle_root)
                
                if is_valid:
                    verified_count += 1
                else:
                    failed_count += 1
                    logger.warning(f"Anchor {anchor.merkle_root} verification failed!")
                    
            except Exception as e:
                logger.error(f"Error verifying anchor {anchor.merkle_root}: {e}")
                failed_count += 1
        
        logger.info(f"Verified {verified_count} anchors, {failed_count} failed")
        return f"Verified: {verified_count}, Failed: {failed_count}"
        
    except Exception as exc:
        logger.exception(f"Error in verify_blockchain_anchors task: {exc}")
        return f"Error: {str(exc)}"


@shared_task
def verify_random_proofs(sample_size: int = None):
    """
    Phase C / C6: spot-check ``MerkleProof`` rows against the on-chain
    ``verifyCommitment`` view.

    The behavioral-recovery anchoring pipeline writes ``MerkleProof`` rows
    with ``verified=False`` and never flips them back to True — the
    ``verified`` column is the contract's "this proof was confirmed against
    the on-chain Merkle root" flag, and it stays unread until something
    actually does the on-chain check. This task is that something.

    Strategy:
    * Sample ``sample_size`` random verifiable, unverified proofs per run
      (default from settings ``BLOCKCHAIN_PROOF_VERIFY_SAMPLE``, falling
      back to 50). One run per day is plenty — this is a tripwire, not
      real-time verification.
    * Each call hits the RPC: keep ``sample_size`` low to stay under any
      free-tier rate limit.
    * Branch on ``verify_proof_on_chain_status`` (3 outcomes):
        - 'ok'        → set ``verified=True`` + ``verified_at=now()``.
        - 'mismatch'  → set ``verified=False`` (no timestamp bump —
                        ``verified_at`` means "when did this proof
                        verify", writing it on failure misleads
                        operators). Logger.error → Sentry alert; the
                        contract was redeployed at a new address, or
                        the anchor was reverted by a chain reorg.
        - 'rpc_error' → leave the proof row untouched, bump
                        ``failed_count``. A transient outage MUST NOT
                        be recorded as a divergence.

    Skipped when:
    * Blockchain anchoring is disabled in settings.
    * The proof is on a legacy SHA-256 anchor (``verifiable=False``) —
      those rows are pre-2026-05 and can't be on-chain verified.
    """
    try:
        from .services.blockchain_anchor_service import BlockchainAnchorService
        from .models import MerkleProof
        from django.utils import timezone

        if not settings.BLOCKCHAIN_ANCHORING.get('ENABLED', False):
            logger.info("verify_random_proofs: blockchain anchoring disabled")
            return "disabled"

        # Sanitise + clamp sample_size from both sources (settings env or
        # explicit task arg). Per CodeRabbit 2nd-pass review of PR #274:
        # the settings path was already guarded in
        # ``password_manager/settings/blockchain.py`` but a bad task arg
        # (string, negative, None-after-deserialisation from Celery)
        # would still slip through and either raise on the slice
        # ``[:sample_size]`` or silently disable the check (slice with
        # N <= 0 returns no rows). Clamp matches the settings-path
        # bounds [1, 1000].
        _SAMPLE_FLOOR, _SAMPLE_CEIL = 1, 1000
        _setting_default = int(
            getattr(settings, 'BLOCKCHAIN_PROOF_VERIFY_SAMPLE', 50)
        )
        _raw_sample = _setting_default if sample_size is None else sample_size
        try:
            sample_size = int(_raw_sample)
        except (TypeError, ValueError):
            logger.warning(
                "verify_random_proofs: invalid sample_size=%r; "
                "falling back to settings default=%d",
                _raw_sample, _setting_default,
            )
            sample_size = _setting_default
        sample_size = max(_SAMPLE_FLOOR, min(sample_size, _SAMPLE_CEIL))

        service = BlockchainAnchorService()
        if not service.enabled:
            logger.info("verify_random_proofs: anchor service not enabled")
            return "service_disabled"

        # `order_by('?')` is acceptable here — the candidate set is bounded
        # by the unverified-keccak slice (typically a few thousand rows in
        # production) and we only fetch `sample_size` of them. If the
        # candidate set ever grows large enough that `ORDER BY RANDOM()`
        # becomes slow, switch to TABLESAMPLE or PK-range sampling.
        candidates = list(
            MerkleProof.objects
            .filter(verified=False, verifiable=True)
            .select_related('blockchain_anchor')
            .order_by('?')[:sample_size]
        )

        if not candidates:
            logger.info("verify_random_proofs: no unverified proofs to check")
            return "no_candidates"

        verified_count = 0
        failed_count = 0
        mismatch_count = 0

        for proof in candidates:
            anchor = proof.blockchain_anchor
            if not anchor or not anchor.tx_hash:
                # Anchor never landed on-chain — cannot verify yet.
                continue

            # PR #274 review (Codex + CodeRabbit): branch on the
            # structured status so transient RPC errors don't masquerade
            # as data-divergence mismatch alerts. ``verify_proof_on_chain``
            # collapses both to ``False``; the new ``_status`` variant
            # returns 'ok' / 'mismatch' / 'rpc_error' / 'disabled'.
            try:
                status = service.verify_proof_on_chain_status(
                    proof.merkle_root,
                    proof.commitment_hash,
                    proof.proof or [],
                )
            except Exception as exc:  # noqa: BLE001 — last-resort safety net
                # The status method already catches Exception internally,
                # so this branch is defence-in-depth against future
                # refactors. Treat as transient.
                logger.error(
                    "verify_random_proofs: unexpected error verifying proof %s: %s",
                    proof.pk, exc,
                )
                failed_count += 1
                continue

            if status == 'rpc_error':
                # Transient — do NOT update verified / verified_at.
                # ``logger.error`` above (inside the service) already
                # surfaced the RPC failure; we just bump the counter so
                # the task summary reflects it.
                failed_count += 1
                continue

            if status == 'disabled':
                # Feature was checked enabled at the top of the task
                # but flipped off mid-run, or the bridge w3 went away.
                # Stop the loop — no point hitting the rest.
                logger.info(
                    "verify_random_proofs: service became disabled mid-run "
                    "(checked %d/%d proofs)", failed_count + verified_count + mismatch_count,
                    len(candidates),
                )
                break

            if status == 'ok':
                # Genuine confirmation — record verified + timestamp.
                proof.verified = True
                proof.verified_at = timezone.now()
                proof.save(update_fields=['verified', 'verified_at'])
                verified_count += 1
            else:  # status == 'mismatch'
                # Genuine data divergence between DB and chain. Record
                # verified=False but do NOT bump verified_at — that
                # field means "when did this proof successfully verify"
                # and writing it on a failure would mislead operators
                # triaging the alert downstream (CodeRabbit review).
                proof.verified = False
                proof.save(update_fields=['verified'])
                mismatch_count += 1
                # Phase F / F5 (2026-05): emit the mismatch with explicit
                # ``extra`` context so Sentry's structured event has the
                # fields an on-call engineer needs WITHOUT re-querying
                # the DB. The Sentry scrubber (Phase E / E1) won't
                # touch these keys — none of them match the
                # ``TOKEN`` / ``SECRET`` / ``KEY`` patterns. The
                # merkle_root + commitment_hash are public on-chain
                # data; tx_hash + anchor_id let the operator pivot
                # directly into Arbiscan / the DB without grepping logs.
                logger.error(
                    "verify_random_proofs: MISMATCH for proof %s "
                    "(anchor tx %s, merkle_root %s) — on-chain "
                    "verifyCommitment returned False",
                    proof.pk, anchor.tx_hash, proof.merkle_root,
                    extra={
                        'proof_pk': str(proof.pk),
                        'anchor_id': str(getattr(anchor, 'pk', '')),
                        'anchor_tx_hash': anchor.tx_hash,
                        'merkle_root': proof.merkle_root,
                        'commitment_hash': proof.commitment_hash,
                        'proof_leaf_index': proof.leaf_index,
                        'verifier_event_type': 'merkle_proof_mismatch',
                    },
                )

        logger.info(
            "verify_random_proofs: checked=%d verified=%d mismatch=%d rpc_failed=%d",
            len(candidates), verified_count, mismatch_count, failed_count,
        )
        return (
            f"checked={len(candidates)} verified={verified_count} "
            f"mismatch={mismatch_count} rpc_failed={failed_count}"
        )

    except Exception as exc:
        logger.exception(f"Error in verify_random_proofs task: {exc}")
        return f"Error: {exc}"


@shared_task
def cleanup_old_pending_commitments():
    """
    Clean up old pending commitments that failed to anchor
    
    Removes pending commitments older than 7 days that haven't been anchored.
    This prevents the pending table from growing indefinitely.
    """
    try:
        from .models import PendingCommitment
        from django.utils import timezone
        from datetime import timedelta
        
        # Delete pending commitments older than 7 days
        cutoff_date = timezone.now() - timedelta(days=7)
        deleted_count = PendingCommitment.objects.filter(
            created_at__lt=cutoff_date,
            is_anchored=False
        ).delete()[0]
        
        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} old pending commitments")
        
        return f"Cleaned up {deleted_count} old pending commitments"
        
    except Exception as exc:
        logger.exception(f"Error in cleanup_old_pending_commitments task: {exc}")
        return f"Error: {str(exc)}"

