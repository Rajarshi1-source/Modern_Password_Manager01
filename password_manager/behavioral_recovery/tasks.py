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
    Asynchronously encrypt commitment with ML-KEM-768
    
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
        commitment.encryption_algorithm = quantum_encrypted['algorithm']
        commitment.is_quantum_protected = quantum_crypto.is_quantum_protected(quantum_encrypted)
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
        # Only legacy base64 rows: this task base64-decodes encrypted_embedding.
        # Fallback rows (DEBUG/tests, 'fallback-aes256gcm') store b'' there,
        # would fail to parse on every run, and could fill the batch so later
        # legacy rows were never reached.
        old_commitments = BehavioralCommitment.objects.filter(
            is_quantum_protected=False,
            encryption_algorithm='base64',
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
                if not quantum_crypto.is_quantum_protected(quantum_encrypted):
                    # The non-PQ fallback (liboqs missing, simulation allowed)
                    # is not a migration: leave the row as it is so a later
                    # run with liboqs picks it up again.
                    logger.warning(
                        "Not migrating commitment %s: liboqs unavailable, got %s",
                        commitment.id, quantum_encrypted.get('algorithm'),
                    )
                    continue
                
                # Update commitment
                commitment.legacy_encrypted_embedding = commitment.encrypted_embedding
                commitment.quantum_encrypted_embedding = quantum_encrypted
                commitment.kyber_public_key = public_key
                commitment.encryption_algorithm = quantum_encrypted['algorithm']
                commitment.is_quantum_protected = quantum_crypto.is_quantum_protected(quantum_encrypted)
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



@shared_task
def start_behavioral_recovery(email, ip_address, user_agent):
    """
    The account-dependent half of POST /api/behavioral-recovery/initiate/.

    The view answers every email the same way and does the same synchronous
    work for each (validate, enqueue this task), so neither the response nor
    its timing says whether the email has an account. Here, an account with
    behavioral commitments gets an attempt and, by email, the link to it.
    """
    from types import SimpleNamespace

    from django.conf import settings
    from django.contrib.auth.models import User
    from django.core.mail import send_mail

    from .models import BehavioralCommitment, RecoveryAuditLog
    from .services import ChallengeGenerator, RecoveryOrchestrator

    # The first challenge is a typing one, and evaluating it needs an active
    # typing commitment: an account with only other commitment types could
    # never pass it
    user = User.objects.filter(email=email).first()
    if user is None or not BehavioralCommitment.objects.filter(
            user=user, challenge_type='typing', is_active=True).exists():
        return None

    request_meta = SimpleNamespace(META={'REMOTE_ADDR': ip_address, 'HTTP_USER_AGENT': user_agent})
    recovery_attempt = RecoveryOrchestrator().initiate_recovery(user, request_meta)
    ChallengeGenerator().generate_challenge(recovery_attempt, 'typing')
    RecoveryAuditLog.objects.create(
        recovery_attempt=recovery_attempt,
        event_type='recovery_initiated',
        ip_address=ip_address,
        user_agent=user_agent,
        details={'email': email}
    )

    # The link opens the frontend, which may be on another origin than the API
    link = (
        f"{settings.FRONTEND_URL.rstrip('/')}/password-recovery"
        f"?behavioral_attempt={recovery_attempt.attempt_id}"
    )
    days = (recovery_attempt.metadata or {}).get('recovery_config', {}).get('days', 5)
    sent = send_mail(
        'Behavioral recovery',
        'Someone started behavioral recovery for your account. If it was you, '
        f'open this link to complete the challenges over the next {days} days: {link}. '
        'Behavioral checks cannot restore access on their own: you will still '
        'need your recovery key. If it was not you, ignore this email.',
        None,
        [user.email],
        fail_silently=True,
    )
    if not sent:
        logger.warning(f"Behavioral recovery email not delivered for attempt {recovery_attempt.attempt_id}")
    return str(recovery_attempt.attempt_id)
