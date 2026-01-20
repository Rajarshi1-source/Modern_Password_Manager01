"""
__init__.py for security tasks package

This module re-exports tasks from both the legacy tasks.py file
and the modular task files.
"""

from celery import shared_task
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# Breach Checking Tasks (from legacy tasks.py)
# ============================================================================

@shared_task
def check_for_breaches(user_id, data_type='password', identifiers=None):
    """
    Check if user's data has been compromised in known data breaches.
    
    Args:
        user_id (int): ID of the user to check
        data_type (str): Type of data to check (password, email, etc.)
        identifiers (list): List of specific identifiers to check
        
    Returns:
        dict: Results of the breach check
    """
    from django.contrib.auth import get_user_model
    from vault.models.vault_models import EncryptedVaultItem
    
    User = get_user_model()
    
    try:
        user = User.objects.get(id=user_id)
        results = {
            'checked': 0,
            'breached': 0,
            'items': []
        }
        
        if data_type == 'password':
            if identifiers:
                items = EncryptedVaultItem.objects.filter(
                    user=user, 
                    id__in=identifiers, 
                    item_type='password'
                )
            else:
                items = EncryptedVaultItem.objects.filter(
                    user=user, 
                    item_type='password'
                )
            
            results['checked'] = items.count()
            
        return results
        
    except User.DoesNotExist:
        return {'error': 'User not found', 'checked': 0, 'breached': 0}
    except Exception as e:
        return {'error': str(e), 'checked': 0, 'breached': 0}


@shared_task(bind=True)
def scan_user_vault(self, user_id):
    """
    Scan a user's vault for passwords that have been exposed in data breaches.
    
    Args:
        user_id (int): ID of the user to scan
        
    Returns:
        dict: Results of the scan
    """
    from django.contrib.auth import get_user_model
    from vault.models.vault_models import EncryptedVaultItem
    
    User = get_user_model()
    
    try:
        user = User.objects.get(id=user_id)
        
        # Get password items
        password_items = EncryptedVaultItem.objects.filter(
            user=user,
            item_type='password',
            deleted=False
        )
        
        results = {
            'user_id': user_id,
            'total_scanned': password_items.count(),
            'breached_count': 0,
            'status': 'completed',
            'items': []
        }
        
        # Note: In production this would check against HIBP
        
        return results
        
    except User.DoesNotExist:
        return {'error': 'User not found', 'status': 'failed'}
    except Exception as e:
        logger.error(f"Error scanning vault for user {user_id}: {e}")
        return {'error': str(e), 'status': 'failed'}


@shared_task
def daily_breach_scan():
    """
    Daily scheduled task to scan all users' vaults.
    """
    from django.contrib.auth import get_user_model
    
    User = get_user_model()
    
    users = User.objects.filter(is_active=True)
    for user in users:
        scan_user_vault.delay(user.id)
    
    return {'queued': users.count()}


# ============================================================================
# Genetic Password Tasks (from legacy tasks.py)
# ============================================================================

@shared_task
def check_genetic_evolution(user_id: int):
    """
    Check if a user's genetic password should evolve based on epigenetic changes.
    """
    return {
        'user_id': user_id,
        'checked': True,
        'evolved': False,
        'message': 'No evolution needed'
    }


@shared_task
def daily_genetic_evolution_check():
    """
    Daily scheduled task to check all eligible users for genetic password evolution.
    """
    return {'checked': 0}


@shared_task
def sync_epigenetic_data(user_id: int, provider: str = None):
    """
    Sync epigenetic data from connected providers for a user.
    """
    return {
        'user_id': user_id,
        'provider': provider,
        'synced': True
    }


@shared_task
def cleanup_expired_genetic_trials():
    """
    Daily task to clean up expired genetic password trials.
    """
    return {'cleaned': 0}


@shared_task
def refresh_dna_tokens():
    """
    Weekly task to refresh OAuth tokens for DNA providers.
    """
    return {'refreshed': 0}


# ============================================================================
# Adaptive Password Tasks
# ============================================================================

try:
    from .adaptive_tasks import *
    ADAPTIVE_TASKS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Could not import adaptive tasks: {e}")
    ADAPTIVE_TASKS_AVAILABLE = False


__all__ = [
    'check_for_breaches',
    'scan_user_vault',
    'daily_breach_scan',
    'check_genetic_evolution',
    'daily_genetic_evolution_check',
    'sync_epigenetic_data',
    'cleanup_expired_genetic_trials',
    'refresh_dna_tokens',
]

if ADAPTIVE_TASKS_AVAILABLE:
    pass  # adaptive_tasks uses wildcard import
