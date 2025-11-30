"""
Celery Tasks for Vault Operations

Background tasks for non-critical vault operations:
- Audit log processing
- Cache warming/cleanup
- Statistics computation
- Breach checking (async)
- Export generation

Note: Core encryption/decryption is NOT done here (client-side only)

Author: SecureVault Password Manager
Version: 2.0.0
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List

from celery import shared_task
from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)
User = get_user_model()


# =============================================================================
# AUDIT AND LOGGING TASKS
# =============================================================================

@shared_task(
    name='vault.tasks.process_audit_log',
    bind=True,
    max_retries=3,
    default_retry_delay=60
)
def process_audit_log(self, user_id: int, action: str, details: Dict = None):
    """
    Process and store audit log entries asynchronously.
    
    Args:
        user_id: User performing the action
        action: Action type (create, update, delete, access, etc.)
        details: Additional action details
    """
    try:
        from vault.models import AuditLog
        
        AuditLog.objects.create(
            user_id=user_id,
            action=action,
            item_type=details.get('item_type', 'unknown') if details else 'unknown',
            status='success',
            ip_address=details.get('ip_address') if details else None,
            user_agent=details.get('user_agent') if details else None,
            extra_data=details
        )
        
        logger.info(f"Audit log created: user={user_id}, action={action}")
        return {'status': 'success', 'user_id': user_id, 'action': action}
        
    except Exception as exc:
        logger.error(f"Audit log failed: {exc}")
        raise self.retry(exc=exc)


@shared_task(name='vault.tasks.cleanup_old_audit_logs')
def cleanup_old_audit_logs(days_to_keep: int = 90):
    """
    Clean up audit logs older than specified days.
    
    Args:
        days_to_keep: Number of days to retain logs
    """
    try:
        from vault.models import AuditLog
        
        cutoff_date = timezone.now() - timedelta(days=days_to_keep)
        deleted_count, _ = AuditLog.objects.filter(
            timestamp__lt=cutoff_date
        ).delete()
        
        logger.info(f"Cleaned up {deleted_count} old audit logs")
        return {'deleted': deleted_count}
        
    except Exception as exc:
        logger.error(f"Audit log cleanup failed: {exc}")
        raise


# =============================================================================
# CACHE MANAGEMENT TASKS
# =============================================================================

@shared_task(name='vault.tasks.warm_user_cache')
def warm_user_cache(user_id: int):
    """
    Pre-warm cache for a user (called after login).
    
    Caches:
    - User salt
    - Folder structure
    - Item statistics
    """
    try:
        from vault.services.vault_optimization_service import (
            vault_cache, VaultQueryOptimizer
        )
        from vault.models import UserSalt
        
        user = User.objects.get(id=user_id)
        
        # Cache salt
        try:
            salt_obj = UserSalt.objects.get(user_id=user_id)
            vault_cache.set_user_salt(user_id, salt_obj.get_salt_b64())
        except UserSalt.DoesNotExist:
            pass
        
        # Cache statistics
        stats = VaultQueryOptimizer.get_user_statistics(user)
        vault_cache.set_user_stats(user_id, stats)
        
        # Cache folders
        from vault.models.folder_models import VaultFolder
        folders = list(VaultFolder.objects.filter(
            user_id=user_id
        ).values('id', 'name', 'parent_id', 'icon'))
        vault_cache.set_user_folders(user_id, folders)
        
        logger.info(f"Cache warmed for user {user_id}")
        return {'status': 'success', 'user_id': user_id}
        
    except User.DoesNotExist:
        logger.warning(f"User {user_id} not found for cache warming")
        return {'status': 'user_not_found'}
    except Exception as exc:
        logger.error(f"Cache warming failed: {exc}")
        raise


@shared_task(name='vault.tasks.invalidate_user_cache')
def invalidate_user_cache(user_id: int):
    """
    Invalidate all cached data for a user (called on logout/password change).
    """
    try:
        from vault.services.vault_optimization_service import vault_cache
        
        vault_cache.invalidate_user_cache(user_id)
        
        logger.info(f"Cache invalidated for user {user_id}")
        return {'status': 'success', 'user_id': user_id}
        
    except Exception as exc:
        logger.error(f"Cache invalidation failed: {exc}")
        raise


@shared_task(name='vault.tasks.cleanup_expired_cache')
def cleanup_expired_cache():
    """
    Periodic task to clean up expired cache entries.
    Scheduled via Celery Beat.
    """
    try:
        # Django cache backends handle TTL internally
        # This task is for any custom cleanup needed
        
        # Clear any stale keys with pattern matching (if Redis)
        try:
            from django_redis import get_redis_connection
            redis_conn = get_redis_connection("default")
            
            # Find and delete expired vault keys
            keys = redis_conn.keys('vault:*')
            # Keys are auto-expired by Redis TTL, but we can force cleanup
            logger.info(f"Found {len(keys)} vault cache keys")
            
        except ImportError:
            # Not using Redis
            pass
        
        return {'status': 'success'}
        
    except Exception as exc:
        logger.error(f"Cache cleanup failed: {exc}")
        raise


# =============================================================================
# STATISTICS AND REPORTING TASKS
# =============================================================================

@shared_task(name='vault.tasks.compute_user_statistics')
def compute_user_statistics(user_id: int) -> Dict:
    """
    Compute comprehensive statistics for a user.
    """
    try:
        from vault.models.vault_models import EncryptedVaultItem
        from vault.models import AuditLog
        from django.db.models import Count
        from django.db.models.functions import TruncDate
        
        user = User.objects.get(id=user_id)
        
        # Item counts by type
        items_by_type = EncryptedVaultItem.objects.filter(
            user=user, deleted=False
        ).values('item_type').annotate(count=Count('id'))
        
        # Activity over last 30 days
        thirty_days_ago = timezone.now() - timedelta(days=30)
        activity = AuditLog.objects.filter(
            user=user,
            timestamp__gte=thirty_days_ago
        ).annotate(
            date=TruncDate('timestamp')
        ).values('date').annotate(count=Count('id'))
        
        stats = {
            'user_id': user_id,
            'items_by_type': {item['item_type']: item['count'] for item in items_by_type},
            'total_items': sum(item['count'] for item in items_by_type),
            'activity_30d': list(activity),
            'computed_at': timezone.now().isoformat()
        }
        
        # Cache the computed stats
        from vault.services.vault_optimization_service import vault_cache
        vault_cache.set_user_stats(user_id, stats)
        
        return stats
        
    except Exception as exc:
        logger.error(f"Statistics computation failed: {exc}")
        raise


@shared_task(name='vault.tasks.generate_security_report')
def generate_security_report(user_id: int) -> Dict:
    """
    Generate a security report for a user.
    
    Analyzes (on encrypted metadata only):
    - Number of items
    - Age of items
    - Folder organization
    
    Note: Password strength analysis happens client-side only.
    """
    try:
        from vault.models.vault_models import EncryptedVaultItem
        from django.db.models import Min, Max
        
        user = User.objects.get(id=user_id)
        
        items = EncryptedVaultItem.objects.filter(
            user=user, deleted=False
        )
        
        # Basic statistics
        total_count = items.count()
        oldest_item = items.aggregate(oldest=Min('created_at'))['oldest']
        newest_item = items.aggregate(newest=Max('created_at'))['newest']
        
        # Items without folders
        unfiled_count = items.filter(folder__isnull=True).count()
        
        report = {
            'user_id': user_id,
            'total_items': total_count,
            'oldest_item_date': oldest_item.isoformat() if oldest_item else None,
            'newest_item_date': newest_item.isoformat() if newest_item else None,
            'unfiled_items': unfiled_count,
            'organization_score': round((1 - unfiled_count / max(total_count, 1)) * 100, 1),
            'generated_at': timezone.now().isoformat()
        }
        
        return report
        
    except Exception as exc:
        logger.error(f"Security report generation failed: {exc}")
        raise


# =============================================================================
# DATA MAINTENANCE TASKS
# =============================================================================

@shared_task(name='vault.tasks.cleanup_deleted_items')
def cleanup_deleted_items(days_soft_deleted: int = 30):
    """
    Permanently delete items that have been soft-deleted for specified days.
    """
    try:
        from vault.models.vault_models import EncryptedVaultItem
        
        cutoff_date = timezone.now() - timedelta(days=days_soft_deleted)
        
        with transaction.atomic():
            deleted_count, _ = EncryptedVaultItem.objects.filter(
                deleted=True,
                deleted_at__lt=cutoff_date
            ).delete()
        
        logger.info(f"Permanently deleted {deleted_count} soft-deleted items")
        return {'deleted': deleted_count}
        
    except Exception as exc:
        logger.error(f"Deleted items cleanup failed: {exc}")
        raise


@shared_task(name='vault.tasks.update_crypto_version_metadata')
def update_crypto_version_metadata(user_id: int, old_version: int, new_version: int):
    """
    Update crypto version metadata for vault items.
    Called after client-side re-encryption.
    """
    try:
        from vault.models.vault_models import EncryptedVaultItem
        
        updated = EncryptedVaultItem.objects.filter(
            user_id=user_id,
            crypto_version=old_version,
            deleted=False
        ).update(crypto_version=new_version)
        
        logger.info(f"Updated crypto version for {updated} items (user={user_id})")
        return {'updated': updated, 'user_id': user_id}
        
    except Exception as exc:
        logger.error(f"Crypto version update failed: {exc}")
        raise


# =============================================================================
# BREACH CHECKING TASKS (Async)
# =============================================================================

@shared_task(
    name='vault.tasks.check_breach_status',
    bind=True,
    max_retries=3,
    rate_limit='10/m'  # Rate limit for external API
)
def check_breach_status(self, password_hash_prefix: str, user_id: int) -> Dict:
    """
    Check if a password hash prefix appears in breach databases.
    
    Uses Have I Been Pwned API (k-anonymity model):
    - Only hash prefix is sent
    - Full hash never leaves client
    
    Args:
        password_hash_prefix: First 5 chars of SHA-1 hash (from client)
        user_id: User ID for logging
    """
    import requests
    
    try:
        # Call HIBP API
        response = requests.get(
            f"https://api.pwnedpasswords.com/range/{password_hash_prefix}",
            headers={'Add-Padding': 'true'},
            timeout=5
        )
        
        if response.status_code == 200:
            # Return hash suffixes and counts
            hashes = {}
            for line in response.text.splitlines():
                suffix, count = line.split(':')
                hashes[suffix] = int(count)
            
            return {
                'prefix': password_hash_prefix,
                'hashes': hashes,
                'checked_at': timezone.now().isoformat()
            }
        else:
            logger.warning(f"HIBP API returned {response.status_code}")
            return {'error': f'API returned {response.status_code}'}
            
    except requests.Timeout:
        logger.warning("HIBP API timeout")
        raise self.retry(exc=Exception("API timeout"))
    except Exception as exc:
        logger.error(f"Breach check failed: {exc}")
        raise self.retry(exc=exc)


# =============================================================================
# EXPORT TASKS
# =============================================================================

@shared_task(name='vault.tasks.prepare_export')
def prepare_export(user_id: int, format: str = 'json') -> Dict:
    """
    Prepare vault export (encrypted blob only).
    
    The actual decryption happens client-side.
    This task just prepares the encrypted data for download.
    """
    try:
        from vault.models.vault_models import EncryptedVaultItem
        import json
        
        items = EncryptedVaultItem.objects.filter(
            user_id=user_id,
            deleted=False
        ).values(
            'item_id', 'item_type', 'encrypted_data',
            'favorite', 'created_at', 'updated_at'
        )
        
        export_data = {
            'version': '2.0',
            'format': 'encrypted',
            'exported_at': timezone.now().isoformat(),
            'items': list(items)
        }
        
        # Convert datetime objects to strings
        for item in export_data['items']:
            item['created_at'] = item['created_at'].isoformat()
            item['updated_at'] = item['updated_at'].isoformat()
        
        # Store in cache for download
        cache_key = f'export:{user_id}:{timezone.now().timestamp()}'
        cache.set(cache_key, json.dumps(export_data), 3600)  # 1 hour TTL
        
        return {
            'status': 'ready',
            'cache_key': cache_key,
            'item_count': len(export_data['items'])
        }
        
    except Exception as exc:
        logger.error(f"Export preparation failed: {exc}")
        raise


# =============================================================================
# SCHEDULED TASKS (Celery Beat)
# =============================================================================

# These are scheduled in settings.py CELERY_BEAT_SCHEDULE
# Example schedule:
# CELERY_BEAT_SCHEDULE = {
#     'cleanup-audit-logs-daily': {
#         'task': 'vault.tasks.cleanup_old_audit_logs',
#         'schedule': crontab(hour=2, minute=0),  # 2 AM daily
#     },
#     'cleanup-deleted-items-weekly': {
#         'task': 'vault.tasks.cleanup_deleted_items',
#         'schedule': crontab(hour=3, minute=0, day_of_week=0),  # Sunday 3 AM
#     },
#     'cleanup-cache-hourly': {
#         'task': 'vault.tasks.cleanup_expired_cache',
#         'schedule': crontab(minute=0),  # Every hour
#     },
# }

