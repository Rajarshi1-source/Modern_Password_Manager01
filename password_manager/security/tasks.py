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
