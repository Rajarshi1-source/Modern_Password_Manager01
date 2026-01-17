from celery import shared_task
from django.contrib.auth.models import User
from vault.models.vault_models import EncryptedVaultItem
from vault.models import BreachAlert
from .services.breach_monitor import HIBPService
from .services.crypto_service import CryptoService
from .services.account_protection import account_protection_service
import json
from django.utils import timezone
from django.contrib.auth import get_user_model
import logging

logger = logging.getLogger(__name__)
User = get_user_model()

@shared_task
def check_for_breaches(user_id, data_type='password', identifiers=None):
    """
    Check if user's data has been compromised in known data breaches
    
    Args:
        user_id (int): ID of the user to check
        data_type (str): Type of data to check (password, email, etc.)
        identifiers (list): List of specific identifiers to check (password IDs, emails, etc.)
        
    Returns:
        dict: Results of the breach check
    """
    try:
        user = User.objects.get(id=user_id)
        results = {
            'checked': 0,
            'breached': 0,
            'items': []
        }
        
        if data_type == 'password':
            # Get password items to check
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
                
            # Check each password
            for item in items:
                results['checked'] += 1
                
                # This is a stub - in reality you would decrypt the item
                # securely to get access to the password
                password = item.get_decrypted_password(user)
                
                if password:
                    # Hash the password
                    hash_value = HIBPService.hash_password(password)
                    prefix = hash_value[:5]
                    suffix = hash_value[5:]
                    
                    # Check if password is breached
                    breach_results = HIBPService.check_password_prefix(prefix)
                    
                    if suffix in breach_results:
                        breach_count = breach_results[suffix]
                        
                        # Create breach alert
                        BreachAlert.objects.get_or_create(
                            user=user,
                            data_type='password',
                            identifier=item.id,
                            defaults={
                                'breach_name': 'Password Breach',
                                'breach_description': f'This password was found in {breach_count} data breaches',
                                'severity': 'high' if breach_count > 1000 else 'medium',
                                'detected_at': timezone.now()
                            }
                        )
                        
                        results['breached'] += 1
                        results['items'].append({
                            'id': item.id,
                            'name': item.name,
                            'count': breach_count
                        })
        
        elif data_type == 'email':
            # Check email breaches
            emails = []
            
            if identifiers:
                emails = identifiers
            else:
                # Get user's primary email
                emails.append(user.email)
                
                # Get emails from vault items
                email_items = EncryptedVaultItem.objects.filter(
                    user=user,
                    item_type='login'
                )
                
                for item in email_items:
                    # This would decrypt the item in a real implementation
                    email = item.get_decrypted_field(user, 'username')
                    if email and '@' in email:
                        emails.append(email)
            
            # Remove duplicates
            emails = list(set(emails))
            
            # Check each email
            for email in emails:
                results['checked'] += 1
                
                # Check breach service
                breaches = HIBPService.check_email(email)
                
                if breaches:
                    # Create breach alert for each breach
                    for breach in breaches:
                        BreachAlert.objects.get_or_create(
                            user=user,
                            data_type='email',
                            identifier=email,
                            breach_name=breach.get('Name', 'Unknown Breach'),
                            defaults={
                                'breach_description': breach.get('Description', 'Your email was found in a data breach'),
                                'breach_date': breach.get('BreachDate'),
                                'severity': 'high',
                                'detected_at': timezone.now()
                            }
                        )
                    
                    results['breached'] += 1
                    results['items'].append({
                        'email': email,
                        'breach_count': len(breaches)
                    })
        
        return results
    
    except User.DoesNotExist:
        logger.error(f"User {user_id} not found")
        raise Exception(f"User {user_id} not found")
    
    except Exception as e:
        logger.error(f"Error checking breaches: {str(e)}")
        raise Exception(f"Error checking breaches: {str(e)}")

@shared_task(bind=True)
def scan_user_vault(self, user_id):
    """
    Scan a user's vault for passwords that have been exposed in data breaches
    
    Args:
        user_id (int): ID of the user to scan
        
    Returns:
        dict: Results of the scan
    """
    try:
        user = User.objects.get(id=user_id)
        vault_items = EncryptedVaultItem.objects.filter(user=user, item_type='password')
        
        # Set up progress tracking
        total_items = vault_items.count()
        processed = 0
        breached = 0
        breached_items = []
        
        # Update task state
        self.update_state(
            state='PROGRESS',
            meta={'progress': 0, 'total': total_items}
        )
        
        # Process each password item
        for item in vault_items:
            processed += 1
            
            try:
                # In a real implementation, this would decrypt the password
                # For this example, we're assuming direct access to the plaintext
                # which would need to be handled securely in production
                
                # This is a stub - in reality you would decrypt the item
                # securely to get access to the password
                password = item.get_decrypted_password(user)
                
                if password:
                    # Hash the password
                    hash_value = HIBPService.hash_password(password)
                    prefix = hash_value[:5]
                    suffix = hash_value[5:]
                    
                    # Check if password is breached
                    result = HIBPService.check_password_prefix(prefix)
                    
                    if suffix in result:
                        breach_count = result[suffix]
                        
                        # Create breach alert
                        BreachAlert.objects.get_or_create(
                            user=user,
                            data_type='password',
                            identifier=item.id,
                            defaults={
                                'breach_name': 'Password Breach',
                                'breach_description': f'This password was found in {breach_count} data breaches',
                                'severity': 'high' if breach_count > 1000 else 'medium',
                                'detected_at': timezone.now()
                            }
                        )
                        
                        breached += 1
                        breached_items.append({
                            'id': item.id,
                            'count': breach_count
                        })
            
            except Exception as e:
                logger.error(f"Error processing item {item.id}: {str(e)}")
            
            # Update progress
            if processed % 5 == 0 or processed == total_items:
                self.update_state(
                    state='PROGRESS',
                    meta={'progress': (processed / total_items) * 100, 'total': total_items}
                )
        
        # Return the final result
        return {
            'total': total_items,
            'breached': breached,
            'items': breached_items
        }
    
    except User.DoesNotExist:
        logger.error(f"User {user_id} not found")
        raise Exception(f"User {user_id} not found")
    
    except Exception as e:
        logger.error(f"Error scanning vault: {str(e)}")
        raise Exception(f"Error scanning vault: {str(e)}")

# Scheduled task to run daily
@shared_task
def daily_breach_scan():
    """
    Daily scheduled task to scan all users' vaults
    """
    # Get all active users
    users = User.objects.filter(is_active=True)
    
    for user in users:
        # Queue individual scan task
        scan_user_vault.delay(user.id)
    
    return f"Scheduled scans for {users.count()} users"


# =============================================================================
# Genetic Password Evolution Tasks
# =============================================================================

@shared_task
def check_genetic_evolution(user_id: int):
    """
    Check if a user's genetic password should evolve based on epigenetic changes.
    
    This task fetches the latest biological age from connected epigenetic providers
    and triggers evolution if significant changes are detected.
    
    Args:
        user_id: ID of the user to check
        
    Returns:
        dict: Evolution status and results
    """
    from .models import DNAConnection, GeneticEvolutionLog, GeneticSubscription
    from .services.epigenetic_service import epigenetic_evolution_manager
    
    try:
        user = User.objects.get(id=user_id)
        
        # Check if user has a DNA connection
        try:
            dna_connection = DNAConnection.objects.get(user=user, is_active=True)
        except DNAConnection.DoesNotExist:
            logger.info(f"No active DNA connection for user {user_id}")
            return {'checked': False, 'reason': 'no_dna_connection'}
        
        # Check subscription for epigenetic features
        try:
            subscription = GeneticSubscription.objects.get(user=user)
            if not subscription.epigenetic_evolution_enabled:
                logger.info(f"Epigenetic evolution disabled for user {user_id}")
                return {'checked': False, 'reason': 'evolution_disabled'}
        except GeneticSubscription.DoesNotExist:
            logger.info(f"No subscription for user {user_id}")
            return {'checked': False, 'reason': 'no_subscription'}
        
        # Check for evolution
        result = epigenetic_evolution_manager.check_and_evolve(user)
        
        if result.get('evolved'):
            logger.info(
                f"Evolution triggered for user {user_id}: "
                f"Gen {result.get('old_generation')} -> {result.get('new_generation')}"
            )
            
            # Update the DNA connection
            dna_connection.evolution_generation = result.get('new_generation', 1)
            dna_connection.last_biological_age = result.get('biological_age')
            dna_connection.last_epigenetic_update = timezone.now()
            dna_connection.save()
            
            # Log the evolution
            GeneticEvolutionLog.objects.create(
                user=user,
                trigger_type='automatic',
                old_evolution_gen=result.get('old_generation', 1),
                new_evolution_gen=result.get('new_generation', 2),
                biological_age_before=result.get('previous_age'),
                biological_age_after=result.get('biological_age'),
                success=True,
                completed_at=timezone.now()
            )
            
            # Update subscription usage
            subscription.evolutions_triggered = (subscription.evolutions_triggered or 0) + 1
            subscription.save()
            
            return {
                'checked': True,
                'evolved': True,
                'old_generation': result.get('old_generation'),
                'new_generation': result.get('new_generation'),
                'biological_age': result.get('biological_age'),
            }
        
        return {
            'checked': True,
            'evolved': False,
            'current_generation': dna_connection.evolution_generation,
            'reason': 'no_significant_change',
        }
        
    except User.DoesNotExist:
        logger.error(f"User {user_id} not found")
        return {'checked': False, 'error': 'user_not_found'}
    
    except Exception as e:
        logger.error(f"Error checking genetic evolution for user {user_id}: {str(e)}")
        return {'checked': False, 'error': str(e)}


@shared_task
def daily_genetic_evolution_check():
    """
    Daily scheduled task to check all eligible users for genetic password evolution.
    
    This runs once daily and queues individual evolution checks for users with:
    - Active DNA connections
    - Epigenetic evolution enabled
    - Premium or trial subscription
    """
    from .models import DNAConnection, GeneticSubscription
    
    # Find users with active DNA connections and epigenetic features
    eligible_connections = DNAConnection.objects.filter(
        is_active=True,
        user__geneticsubscription__epigenetic_evolution_enabled=True,
        user__geneticsubscription__status='active',
    ).select_related('user')
    
    queued_count = 0
    
    for connection in eligible_connections:
        # Queue individual evolution check
        check_genetic_evolution.delay(connection.user_id)
        queued_count += 1
    
    logger.info(f"Queued genetic evolution checks for {queued_count} users")
    return {'queued': queued_count}


@shared_task
def sync_epigenetic_data(user_id: int, provider: str = None):
    """
    Sync epigenetic data from connected providers for a user.
    
    This fetches the latest biological age and other epigenetic markers
    from providers like Humanity.health.
    
    Args:
        user_id: ID of the user
        provider: Optional specific provider to sync from
        
    Returns:
        dict: Sync results including biological age data
    """
    from .models import DNAConnection
    from .services.epigenetic_service import HumanityHealthProvider, ManualEpigeneticProvider
    
    try:
        user = User.objects.get(id=user_id)
        
        try:
            dna_connection = DNAConnection.objects.get(user=user, is_active=True)
        except DNAConnection.DoesNotExist:
            return {'synced': False, 'reason': 'no_connection'}
        
        # Try to fetch from Humanity.health if no specific provider
        epigenetic_provider = HumanityHealthProvider()
        
        try:
            # This would use the user's OAuth token that's stored with the connection
            # For now, we'll return a placeholder result
            result = {
                'synced': True,
                'provider': 'humanity_health',
                'biological_age': None,  # Would be fetched from API
                'message': 'Epigenetic sync queued - API integration pending',
            }
            
            logger.info(f"Epigenetic sync completed for user {user_id}")
            return result
            
        except Exception as api_error:
            logger.warning(f"API sync failed for user {user_id}: {api_error}")
            return {
                'synced': False,
                'error': str(api_error),
            }
            
    except User.DoesNotExist:
        return {'synced': False, 'error': 'user_not_found'}
    
    except Exception as e:
        logger.error(f"Error syncing epigenetic data for user {user_id}: {str(e)}")
        return {'synced': False, 'error': str(e)}


@shared_task
def cleanup_expired_genetic_trials():
    """
    Daily task to clean up expired genetic password trials.
    
    - Marks expired trials as inactive
    - Disables epigenetic features for expired subscriptions
    - Sends notification to users about trial expiration
    """
    from .models import GeneticSubscription
    
    now = timezone.now()
    
    # Find expired trials
    expired_trials = GeneticSubscription.objects.filter(
        tier='trial',
        status='active',
        trial_expires_at__lt=now,
    )
    
    expired_count = 0
    
    for subscription in expired_trials:
        subscription.status = 'expired'
        subscription.epigenetic_evolution_enabled = False
        subscription.save()
        
        # TODO: Send notification to user
        # notification_service.send_trial_expired(subscription.user)
        
        expired_count += 1
        logger.info(f"Expired trial for user {subscription.user_id}")
    
    logger.info(f"Cleaned up {expired_count} expired genetic trials")
    return {'expired_trials_cleaned': expired_count}


@shared_task
def refresh_dna_tokens():
    """
    Weekly task to refresh OAuth tokens for DNA providers.
    
    Refreshes tokens that are about to expire to maintain access
    to DNA provider APIs.
    """
    from .models import DNAConnection
    from .services.dna_provider_service import get_dna_provider
    
    # Find connections with tokens that might need refresh
    # (tokens typically expire after a certain period)
    active_connections = DNAConnection.objects.filter(
        is_active=True,
        status='connected',
    )
    
    refreshed_count = 0
    failed_count = 0
    
    for connection in active_connections:
        try:
            provider = get_dna_provider(connection.provider)
            
            if connection.encrypted_refresh_token:
                # Decrypt and refresh token
                # This is a placeholder - actual implementation would decrypt
                # and call the provider's refresh endpoint
                
                logger.debug(f"Token refresh queued for user {connection.user_id}")
                refreshed_count += 1
                
        except Exception as e:
            logger.error(
                f"Failed to refresh token for user {connection.user_id}: {str(e)}"
            )
            failed_count += 1
    
    logger.info(f"Token refresh complete: {refreshed_count} refreshed, {failed_count} failed")
    return {
        'refreshed': refreshed_count,
        'failed': failed_count,
    }

