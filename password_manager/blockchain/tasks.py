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
        pending_count = PendingCommitment.objects.filter(anchored=False).count()
        
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
                is_valid = service.verify_anchor_on_chain(anchor.merkle_root, anchor.tx_hash)
                
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
            anchored=False
        ).delete()[0]
        
        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} old pending commitments")
        
        return f"Cleaned up {deleted_count} old pending commitments"
        
    except Exception as exc:
        logger.exception(f"Error in cleanup_old_pending_commitments task: {exc}")
        return f"Error: {str(exc)}"

