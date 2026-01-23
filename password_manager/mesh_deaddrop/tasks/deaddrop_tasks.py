"""
Mesh Dead Drop Celery Tasks
============================

Background tasks for mesh dead drop automation:
- Expired dead drop cleanup
- Mesh node health checking
- Fragment rebalancing
- Notifications

@author Password Manager Team
@created 2026-01-22
"""

from celery import shared_task
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# Periodic Tasks
# =============================================================================

@shared_task(name='mesh_deaddrop.check_expired_deaddrops')
def check_expired_deaddrops():
    """
    Check for and mark expired dead drops.
    
    Runs every hour (configured in CELERY_BEAT_SCHEDULE).
    """
    from ..models import DeadDrop
    
    now = timezone.now()
    expired = DeadDrop.objects.filter(
        status__in=['pending', 'distributed', 'active'],
        expires_at__lt=now,
        is_active=True
    )
    
    count = expired.count()
    
    for dead_drop in expired:
        dead_drop.status = 'expired'
        dead_drop.is_active = False
        dead_drop.save()
        
        # Notify owner
        notify_owner_deaddrop_expired.delay(str(dead_drop.id))
        
        logger.info(f"Marked dead drop {dead_drop.id} as expired")
    
    if count > 0:
        logger.info(f"Expired {count} dead drops")
    
    return {'expired_count': count}


@shared_task(name='mesh_deaddrop.check_mesh_node_health')
def check_mesh_node_health():
    """
    Check mesh node health and mark offline nodes.
    
    Runs every 5 minutes (configured in CELERY_BEAT_SCHEDULE).
    """
    from ..models import MeshNode
    
    # Nodes not seen in 10 minutes are marked offline
    cutoff = timezone.now() - timedelta(minutes=10)
    
    stale_nodes = MeshNode.objects.filter(
        is_online=True,
        last_seen__lt=cutoff
    )
    
    count = stale_nodes.count()
    stale_nodes.update(is_online=False)
    
    if count > 0:
        logger.info(f"Marked {count} mesh nodes as offline")
        
        # Trigger rebalancing for affected dead drops
        rebalance_orphaned_fragments.delay()
    
    return {'offline_count': count}


@shared_task(name='mesh_deaddrop.rebalance_orphaned_fragments')
def rebalance_orphaned_fragments():
    """
    Rebalance fragments from offline nodes to online ones.
    
    Triggered when nodes go offline.
    """
    from ..models import DeadDrop
    from ..services import FragmentDistributionService
    
    service = FragmentDistributionService()
    
    # Find dead drops with fragments on offline nodes
    affected = DeadDrop.objects.filter(
        is_active=True,
        status='active',
        fragments__node__is_online=False
    ).distinct()
    
    total_rebalanced = 0
    
    for dead_drop in affected:
        rebalanced = service.rebalance_fragments(dead_drop)
        total_rebalanced += rebalanced
        
        if rebalanced > 0:
            logger.info(f"Rebalanced {rebalanced} fragments for dead drop {dead_drop.id}")
    
    return {'rebalanced_count': total_rebalanced}


@shared_task(name='mesh_deaddrop.cleanup_old_access_logs')
def cleanup_old_access_logs():
    """
    Clean up old access logs (older than 90 days).
    
    Runs daily.
    """
    from ..models import DeadDropAccess, FragmentTransfer
    
    cutoff = timezone.now() - timedelta(days=90)
    
    # Delete old access logs
    access_deleted, _ = DeadDropAccess.objects.filter(
        access_time__lt=cutoff
    ).delete()
    
    # Delete old transfer logs
    transfer_deleted, _ = FragmentTransfer.objects.filter(
        transfer_time__lt=cutoff
    ).delete()
    
    logger.info(f"Cleaned up {access_deleted} access logs and {transfer_deleted} transfer logs")
    
    return {
        'access_logs_deleted': access_deleted,
        'transfer_logs_deleted': transfer_deleted
    }


@shared_task(name='mesh_deaddrop.cleanup_location_cache')
def cleanup_location_cache():
    """
    Clean up old location cache entries (older than 24 hours).
    
    Runs every 6 hours.
    """
    from ..models import LocationVerificationCache
    
    cutoff = timezone.now() - timedelta(hours=24)
    
    deleted, _ = LocationVerificationCache.objects.filter(
        recorded_at__lt=cutoff
    ).delete()
    
    if deleted > 0:
        logger.info(f"Cleaned up {deleted} location cache entries")
    
    return {'deleted_count': deleted}


# =============================================================================
# Notification Tasks
# =============================================================================

@shared_task(name='mesh_deaddrop.notify_owner_deaddrop_expired')
def notify_owner_deaddrop_expired(dead_drop_id: str):
    """
    Notify dead drop owner that their drop has expired.
    """
    from ..models import DeadDrop
    
    try:
        dead_drop = DeadDrop.objects.select_related('owner').get(id=dead_drop_id)
    except DeadDrop.DoesNotExist:
        logger.error(f"Dead drop {dead_drop_id} not found")
        return
    
    if not dead_drop.owner.email:
        logger.warning(f"Owner of dead drop {dead_drop_id} has no email")
        return
    
    subject = f"Dead Drop Expired: {dead_drop.title}"
    message = f"""
Hello {dead_drop.owner.username},

Your dead drop "{dead_drop.title}" has expired and is no longer accessible.

The secret was not collected before the expiration time.

If you need to share the secret again, please create a new dead drop.

Best regards,
Password Manager Security Team
    """
    
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[dead_drop.owner.email],
            fail_silently=False,
        )
        logger.info(f"Sent expiration notification for dead drop {dead_drop_id}")
    except Exception as e:
        logger.error(f"Failed to send expiration email: {e}")


@shared_task(name='mesh_deaddrop.notify_recipient_deaddrop_ready')
def notify_recipient_deaddrop_ready(dead_drop_id: str):
    """
    Notify recipient that a dead drop is ready for collection.
    """
    from ..models import DeadDrop
    
    try:
        dead_drop = DeadDrop.objects.get(id=dead_drop_id)
    except DeadDrop.DoesNotExist:
        logger.error(f"Dead drop {dead_drop_id} not found")
        return
    
    if not dead_drop.recipient_email:
        logger.info(f"Dead drop {dead_drop_id} has no recipient email")
        return
    
    frontend_url = getattr(settings, 'FRONTEND_URL', 'https://app.example.com')
    
    subject = f"Secure Dead Drop Ready for Collection"
    message = f"""
Hello,

A secure dead drop has been created for you.

Title: {dead_drop.title}
Location Hint: {dead_drop.location_hint or "Not provided"}

To collect the secret:
1. Go to the designated location
2. Open the Password Manager app
3. Navigate to Dead Drops > Collect
4. Verify your location via GPS and Bluetooth

The dead drop expires on: {dead_drop.expires_at.strftime('%Y-%m-%d %H:%M UTC')}

Security Information:
- You must be physically present at the location
- Your device must detect nearby mesh nodes via Bluetooth
- GPS spoofing will be detected and blocked

If you were not expecting this message, please ignore it.

Best regards,
Password Manager Security Team
    """
    
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[dead_drop.recipient_email],
            fail_silently=False,
        )
        logger.info(f"Sent ready notification for dead drop {dead_drop_id}")
    except Exception as e:
        logger.error(f"Failed to send ready notification: {e}")


@shared_task(name='mesh_deaddrop.notify_owner_deaddrop_collected')
def notify_owner_deaddrop_collected(dead_drop_id: str, accessor_username: str = None):
    """
    Notify dead drop owner that their drop was collected.
    """
    from ..models import DeadDrop
    
    try:
        dead_drop = DeadDrop.objects.select_related('owner').get(id=dead_drop_id)
    except DeadDrop.DoesNotExist:
        logger.error(f"Dead drop {dead_drop_id} not found")
        return
    
    if not dead_drop.owner.email:
        return
    
    subject = f"Dead Drop Collected: {dead_drop.title}"
    message = f"""
Hello {dead_drop.owner.username},

Your dead drop "{dead_drop.title}" has been successfully collected.

Collection time: {dead_drop.collected_at.strftime('%Y-%m-%d %H:%M UTC') if dead_drop.collected_at else 'Unknown'}
Collected by: {accessor_username or 'Anonymous'}

The secret has been securely transmitted and the dead drop is now inactive.

Best regards,
Password Manager Security Team
    """
    
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[dead_drop.owner.email],
            fail_silently=False,
        )
        logger.info(f"Sent collection notification for dead drop {dead_drop_id}")
    except Exception as e:
        logger.error(f"Failed to send collection email: {e}")


# =============================================================================
# Celery Beat Schedule
# =============================================================================

CELERY_BEAT_SCHEDULE = {
    'check-expired-deaddrops': {
        'task': 'mesh_deaddrop.check_expired_deaddrops',
        'schedule': 3600.0,  # Every hour
    },
    'check-mesh-node-health': {
        'task': 'mesh_deaddrop.check_mesh_node_health',
        'schedule': 300.0,  # Every 5 minutes
    },
    'cleanup-old-access-logs': {
        'task': 'mesh_deaddrop.cleanup_old_access_logs',
        'schedule': 86400.0,  # Daily
    },
    'cleanup-location-cache': {
        'task': 'mesh_deaddrop.cleanup_location_cache',
        'schedule': 21600.0,  # Every 6 hours
    },
}
