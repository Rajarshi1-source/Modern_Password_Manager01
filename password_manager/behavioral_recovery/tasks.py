"""
Celery Tasks for Behavioral Recovery

Async tasks for performance optimization, particularly for quantum crypto operations
"""

from celery import shared_task
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def async_quantum_encrypt_commitment(self, commitment_id, embedding_data):
    """
    Asynchronously encrypt commitment with Kyber-768
    
    Args:
        commitment_id: ID of BehavioralCommitment to encrypt
        embedding_data: Behavioral embedding data to encrypt
    
    Returns:
        commitment_id if successful
    """
    from .models import BehavioralCommitment
    from .services.quantum_crypto_service import get_quantum_crypto_service
    
    try:
        logger.info(f"Starting async quantum encryption for commitment {commitment_id}")
        
        # Get commitment
        commitment = BehavioralCommitment.objects.get(id=commitment_id)
        
        # Initialize quantum crypto
        quantum_crypto = get_quantum_crypto_service()
        
        # Generate Kyber keypair
        public_key, private_key = quantum_crypto.generate_keypair()
        
        # Encrypt with Kyber + AES
        quantum_encrypted = quantum_crypto.encrypt_behavioral_embedding(
            embedding_data,
            public_key
        )
        
        # Update commitment
        commitment.quantum_encrypted_embedding = quantum_encrypted
        commitment.kyber_public_key = public_key
        commitment.encryption_algorithm = 'kyber768-aes256gcm'
        commitment.is_quantum_protected = True
        commitment.save()
        
        logger.info(f"✅ Async quantum encryption completed for commitment {commitment_id}")
        return commitment_id
        
    except Exception as e:
        logger.error(f"Async quantum encryption failed for commitment {commitment_id}: {e}")
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))


@shared_task
def async_migrate_commitments_to_quantum(batch_size=50):
    """
    Background task to migrate old commitments to quantum encryption
    
    Args:
        batch_size: Number of commitments to process per run
    
    Returns:
        Number of commitments upgraded
    """
    from .models import BehavioralCommitment
    from .services.quantum_crypto_service import get_quantum_crypto_service
    import base64
    import json
    
    logger.info(f"Starting async migration of commitments to quantum (batch_size={batch_size})")
    
    try:
        # Get batch of non-quantum commitments
        old_commitments = BehavioralCommitment.objects.filter(
            is_quantum_protected=False
        )[:batch_size]
        
        if not old_commitments.exists():
            logger.info("No commitments to migrate")
            return 0
        
        quantum_crypto = get_quantum_crypto_service()
        upgraded = 0
        
        for commitment in old_commitments:
            try:
                # Decrypt old embedding
                decrypted_bytes = base64.b64decode(commitment.encrypted_embedding)
                decrypted_json = decrypted_bytes.decode('utf-8')
                embedding = json.loads(decrypted_json)
                
                # Re-encrypt with Kyber
                public_key, private_key = quantum_crypto.generate_keypair()
                quantum_encrypted = quantum_crypto.encrypt_behavioral_embedding(
                    embedding,
                    public_key
                )
                
                # Update commitment
                commitment.legacy_encrypted_embedding = commitment.encrypted_embedding
                commitment.quantum_encrypted_embedding = quantum_encrypted
                commitment.kyber_public_key = public_key
                commitment.encryption_algorithm = 'kyber768-aes256gcm'
                commitment.is_quantum_protected = True
                commitment.migrated_to_quantum = timezone.now()
                commitment.save()
                
                upgraded += 1
                
            except Exception as e:
                logger.error(f"Failed to migrate commitment {commitment.id}: {e}")
        
        logger.info(f"✅ Migrated {upgraded} commitments to quantum encryption")
        return upgraded
        
    except Exception as e:
        logger.error(f"Async migration task failed: {e}")
        return 0


@shared_task
def preload_quantum_crypto():
    """
    Preload quantum crypto service to warm up cache
    
    Useful for reducing first-time latency
    """
    try:
        from .services.quantum_crypto_service import get_quantum_crypto_service
        
        quantum_crypto = get_quantum_crypto_service()
        info = quantum_crypto.get_algorithm_info()
        
        logger.info(f"Quantum crypto preloaded: {info['algorithm']}")
        return info
        
    except Exception as e:
        logger.error(f"Failed to preload quantum crypto: {e}")
        return None

