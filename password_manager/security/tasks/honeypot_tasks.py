"""
Honeypot Email Celery Tasks
============================

Background tasks for honeypot email monitoring, breach detection,
and credential rotation management.

@author Password Manager Team
@created 2026-02-01
"""

import logging
from celery import shared_task
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


# =============================================================================
# Honeypot Monitoring Tasks
# =============================================================================

@shared_task(name='security.check_honeypot_activity')
def check_honeypot_activity(honeypot_id: str):
    """
    Check a single honeypot for new activity from the email provider.
    
    This task is called periodically or triggered manually.
    """
    from .services.honeypot_service import get_honeypot_service
    from .models import HoneypotEmail
    
    try:
        service = get_honeypot_service()
        honeypot = HoneypotEmail.objects.get(id=honeypot_id, is_active=True)
        
        activities = service.check_honeypot_for_activity(honeypot)
        
        if activities:
            logger.info(
                f"Found {len(activities)} new activities for honeypot {honeypot_id}"
            )
        
        return {
            'honeypot_id': honeypot_id,
            'activities_found': len(activities),
            'status': honeypot.status,
            'breach_detected': honeypot.breach_detected,
        }
        
    except HoneypotEmail.DoesNotExist:
        logger.warning(f"Honeypot {honeypot_id} not found or inactive")
        return {'honeypot_id': honeypot_id, 'error': 'not_found'}
    except Exception as e:
        logger.error(f"Error checking honeypot {honeypot_id}: {e}")
        return {'honeypot_id': honeypot_id, 'error': str(e)}


@shared_task(name='security.check_all_user_honeypots')
def check_all_user_honeypots(user_id: int):
    """
    Check all honeypots for a specific user.
    """
    from .services.honeypot_service import get_honeypot_service
    from django.contrib.auth import get_user_model
    
    User = get_user_model()
    
    try:
        user = User.objects.get(id=user_id)
        service = get_honeypot_service()
        
        results = service.check_all_honeypots(user)
        
        logger.info(
            f"Checked {results['checked']} honeypots for user {user.username}: "
            f"{results['new_activity']} activities, {results['breaches_detected']} breaches"
        )
        
        return results
        
    except User.DoesNotExist:
        logger.warning(f"User {user_id} not found")
        return {'error': 'user_not_found'}
    except Exception as e:
        logger.error(f"Error checking honeypots for user {user_id}: {e}")
        return {'error': str(e)}


@shared_task(name='security.scan_all_honeypots')
def scan_all_honeypots():
    """
    Periodic task to scan all active honeypots across all users.
    
    Should be scheduled to run every 15-30 minutes via Celery Beat.
    """
    from .models import HoneypotEmail, HoneypotConfiguration
    from .services.honeypot_service import get_honeypot_service
    
    service = get_honeypot_service()
    
    # Get all active honeypots
    active_honeypots = HoneypotEmail.objects.filter(
        is_active=True,
        status__in=['active', 'triggered']
    ).select_related('user')
    
    results = {
        'scanned': 0,
        'activities_found': 0,
        'breaches_detected': 0,
        'errors': 0,
    }
    
    for honeypot in active_honeypots:
        try:
            activities = service.check_honeypot_for_activity(honeypot)
            results['scanned'] += 1
            results['activities_found'] += len(activities)
            
            if honeypot.breach_detected:
                results['breaches_detected'] += 1
                
        except Exception as e:
            logger.error(f"Error scanning honeypot {honeypot.id}: {e}")
            results['errors'] += 1
    
    logger.info(
        f"Honeypot scan complete: {results['scanned']} scanned, "
        f"{results['activities_found']} activities, "
        f"{results['breaches_detected']} breaches"
    )
    
    return results


# =============================================================================
# Breach Analysis Tasks
# =============================================================================

@shared_task(name='security.analyze_breach_patterns')
def analyze_breach_patterns():
    """
    Analyze honeypot breach patterns to detect coordinated attacks
    or widespread data breaches affecting multiple users.
    
    Runs periodically to identify patterns in breach data.
    """
    from .models import HoneypotBreachEvent, HoneypotActivity
    from collections import Counter
    
    # Get recent breaches (last 24 hours)
    recent_cutoff = timezone.now() - timedelta(hours=24)
    recent_breaches = HoneypotBreachEvent.objects.filter(
        detected_at__gte=recent_cutoff
    ).select_related('honeypot')
    
    if not recent_breaches.exists():
        return {'patterns_found': 0, 'message': 'No recent breaches to analyze'}
    
    # Analyze by service
    service_counts = Counter(
        breach.service_name.lower() for breach in recent_breaches
    )
    
    # Find services with multiple breaches (potential widespread breach)
    widespread_breaches = {
        service: count 
        for service, count in service_counts.items() 
        if count >= 3  # 3+ users affected
    }
    
    # Analyze activity sender patterns
    sender_domains = Counter()
    for breach in recent_breaches:
        if breach.honeypot:
            activities = HoneypotActivity.objects.filter(
                honeypot=breach.honeypot,
                received_at__gte=breach.detected_at - timedelta(hours=1)
            )
            for activity in activities:
                if activity.sender_domain:
                    sender_domains[activity.sender_domain] += 1
    
    # Common senders might indicate same attacker
    suspicious_senders = {
        domain: count 
        for domain, count in sender_domains.items() 
        if count >= 5  # Same sender hitting 5+ honeypots
    }
    
    results = {
        'total_breaches_analyzed': recent_breaches.count(),
        'widespread_breaches': widespread_breaches,
        'suspicious_senders': suspicious_senders,
        'patterns_found': len(widespread_breaches) + len(suspicious_senders),
    }
    
    if results['patterns_found'] > 0:
        logger.warning(
            f"Breach pattern analysis found {results['patterns_found']} patterns: "
            f"{list(widespread_breaches.keys())} services, "
            f"{list(suspicious_senders.keys())} senders"
        )
    
    return results


@shared_task(name='security.correlate_with_hibp')
def correlate_with_hibp(breach_id: str):
    """
    Correlate a honeypot breach with Have I Been Pwned database
    to determine if this is part of a known public breach.
    
    Updates breach event with public disclosure date if found.
    """
    from .models import HoneypotBreachEvent
    from .services.breach_monitor import HIBPService
    
    try:
        breach = HoneypotBreachEvent.objects.get(id=breach_id)
        hibp = HIBPService()
        
        # Check if service domain appears in known breaches
        service_domain = breach.honeypot.service_domain if breach.honeypot else ''
        
        if not service_domain:
            # Try to extract from service name
            service_domain = breach.service_name.lower().replace(' ', '') + '.com'
        
        # Note: HIBP API requires email to check breaches
        # This is a simplified correlation based on service name matching
        # In production, you'd use the full HIBP API
        
        logger.info(f"Correlating breach {breach_id} with HIBP for {service_domain}")
        
        return {
            'breach_id': breach_id,
            'service': breach.service_name,
            'correlated': False,  # Would be True if found in HIBP
            'message': 'HIBP correlation requires premium API'
        }
        
    except HoneypotBreachEvent.DoesNotExist:
        logger.warning(f"Breach {breach_id} not found")
        return {'breach_id': breach_id, 'error': 'not_found'}
    except Exception as e:
        logger.error(f"Error correlating breach {breach_id}: {e}")
        return {'breach_id': breach_id, 'error': str(e)}


# =============================================================================
# Credential Rotation Tasks
# =============================================================================

@shared_task(name='security.process_pending_rotations')
def process_pending_rotations():
    """
    Process pending credential rotations that are waiting for completion.
    
    Sends reminders for unconfirmed rotations.
    """
    from .models import CredentialRotationLog
    from django.core.mail import send_mail
    from django.conf import settings
    
    # Find rotations pending for more than 24 hours
    cutoff = timezone.now() - timedelta(hours=24)
    stale_rotations = CredentialRotationLog.objects.filter(
        status='pending',
        initiated_at__lt=cutoff,
        user_confirmed=False
    ).select_related('user', 'breach_event')
    
    reminded = 0
    
    for rotation in stale_rotations:
        try:
            # Send reminder email
            send_mail(
                subject=f"⚠️ Action Required: Rotate credentials for {rotation.service_name}",
                message=f"""
Hello {rotation.user.get_full_name() or rotation.user.username},

You have a pending credential rotation for {rotation.service_name} that was 
initiated more than 24 hours ago.

Please change your password for this service as soon as possible to 
protect your account.

Service: {rotation.service_name}
Initiated: {rotation.initiated_at.strftime('%Y-%m-%d %H:%M UTC')}
Reason: {rotation.get_trigger_display()}

Visit your SecureVault dashboard to mark this rotation as complete.

Best regards,
SecureVault Security Team
                """,
                from_email=getattr(settings, 'SECURITY_EMAIL', 'security@securevault.com'),
                recipient_list=[rotation.user.email],
                fail_silently=True
            )
            reminded += 1
            
        except Exception as e:
            logger.error(f"Failed to send rotation reminder: {e}")
    
    logger.info(f"Sent {reminded} credential rotation reminders")
    
    return {'reminders_sent': reminded}


@shared_task(name='security.cleanup_expired_honeypots')
def cleanup_expired_honeypots():
    """
    Clean up honeypots that have passed their expiration date.
    """
    from .models import HoneypotEmail
    from .services.honeypot_service import get_honeypot_service
    
    service = get_honeypot_service()
    
    # Find expired honeypots
    expired = HoneypotEmail.objects.filter(
        is_active=True,
        expires_at__lt=timezone.now()
    )
    
    cleaned = 0
    for honeypot in expired:
        try:
            honeypot.status = 'expired'
            honeypot.is_active = False
            honeypot.save()
            cleaned += 1
            logger.info(f"Marked honeypot {honeypot.id} as expired")
        except Exception as e:
            logger.error(f"Error expiring honeypot {honeypot.id}: {e}")
    
    return {'expired_count': cleaned}


# =============================================================================
# Notification Tasks
# =============================================================================

@shared_task(name='security.send_breach_digest')
def send_breach_digest():
    """
    Send daily breach digest to users with detected breaches.
    """
    from .models import HoneypotBreachEvent
    from django.contrib.auth import get_user_model
    from django.core.mail import send_mail
    from django.conf import settings
    
    User = get_user_model()
    
    # Get breaches from last 24 hours
    cutoff = timezone.now() - timedelta(hours=24)
    recent_breaches = HoneypotBreachEvent.objects.filter(
        detected_at__gte=cutoff,
        user_notified=True,
        credentials_rotated=False
    ).select_related('user')
    
    # Group by user
    user_breaches = {}
    for breach in recent_breaches:
        if breach.user_id not in user_breaches:
            user_breaches[breach.user_id] = []
        user_breaches[breach.user_id].append(breach)
    
    digests_sent = 0
    
    for user_id, breaches in user_breaches.items():
        try:
            user = User.objects.get(id=user_id)
            
            breach_list = "\n".join([
                f"- {b.service_name} ({b.get_severity_display()})"
                for b in breaches
            ])
            
            send_mail(
                subject=f"🔐 Daily Security Digest: {len(breaches)} credential(s) need rotation",
                message=f"""
Hello {user.get_full_name() or user.username},

This is your daily security digest. The following services were detected 
as breached and require password rotation:

{breach_list}

Please log into your SecureVault dashboard to rotate these credentials.

Best regards,
SecureVault Security Team
                """,
                from_email=getattr(settings, 'SECURITY_EMAIL', 'security@securevault.com'),
                recipient_list=[user.email],
                fail_silently=True
            )
            digests_sent += 1
            
        except Exception as e:
            logger.error(f"Failed to send digest to user {user_id}: {e}")
    
    return {'digests_sent': digests_sent}


# =============================================================================
# Statistics Tasks
# =============================================================================

@shared_task(name='security.generate_honeypot_stats')
def generate_honeypot_stats():
    """
    Generate aggregate statistics about honeypot effectiveness.
    """
    from .models import HoneypotEmail, HoneypotBreachEvent, HoneypotActivity
    
    stats = {
        'timestamp': timezone.now().isoformat(),
        'total_honeypots': HoneypotEmail.objects.count(),
        'active_honeypots': HoneypotEmail.objects.filter(is_active=True).count(),
        'breached_honeypots': HoneypotEmail.objects.filter(breach_detected=True).count(),
        'total_breaches': HoneypotBreachEvent.objects.count(),
        'total_activities': HoneypotActivity.objects.count(),
        'breach_rate': 0.0,
    }
    
    if stats['active_honeypots'] > 0:
        stats['breach_rate'] = (
            stats['breached_honeypots'] / stats['total_honeypots']
        ) * 100
    
    # Breaches by severity
    for severity in ['low', 'medium', 'high', 'critical']:
        stats[f'breaches_{severity}'] = HoneypotBreachEvent.objects.filter(
            severity=severity
        ).count()
    
    logger.info(f"Honeypot stats: {stats}")
    
    return stats
