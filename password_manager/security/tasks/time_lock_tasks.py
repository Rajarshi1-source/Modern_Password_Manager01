"""
Time-Lock Background Tasks
===========================

Celery tasks for automated time-lock management:
- Checking capsule unlocks
- Dead man's switch monitoring
- Beneficiary notifications

@author Password Manager Team
@created 2026-01-22
"""

import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings

logger = logging.getLogger(__name__)


# =============================================================================
# Capsule Status Checks
# =============================================================================

@shared_task(name='time_lock.check_capsule_unlocks')
def check_capsule_unlocks():
    """
    Check for capsules that are ready to unlock.
    Runs every 5 minutes.
    
    Updates status and triggers notifications for:
    - Capsules that have reached unlock time
    - Capsules that are about to unlock (notification)
    """
    from security.models import TimeLockCapsule, CapsuleBeneficiary
    
    now = timezone.now()
    
    # Find capsules ready to unlock
    ready_capsules = TimeLockCapsule.objects.filter(
        status='locked',
        unlock_at__lte=now
    )
    
    unlocked_count = 0
    
    for capsule in ready_capsules:
        try:
            # Update status
            capsule.status = 'unlocked'
            capsule.opened_at = now
            capsule.save()
            
            unlocked_count += 1
            
            # Notify beneficiaries
            for beneficiary in capsule.beneficiaries.filter(notified_at__isnull=True):
                notify_beneficiary.delay(
                    capsule_id=str(capsule.id),
                    beneficiary_id=str(beneficiary.id)
                )
            
            logger.info(f"Capsule {capsule.id} auto-unlocked")
            
        except Exception as e:
            logger.error(f"Failed to unlock capsule {capsule.id}: {e}")
    
    # Find capsules unlocking soon (within 1 hour) and notify owners
    soon_unlock = TimeLockCapsule.objects.filter(
        status='locked',
        unlock_at__gt=now,
        unlock_at__lte=now + timedelta(hours=1)
    )
    
    for capsule in soon_unlock:
        # Could send notification to owner about upcoming unlock
        pass
    
    return {
        'unlocked': unlocked_count,
        'pending': soon_unlock.count()
    }


@shared_task(name='time_lock.check_expired_capsules')
def check_expired_capsules():
    """
    Mark old unlocked capsules as expired.
    Runs daily.
    """
    from security.models import TimeLockCapsule
    
    # Capsules unlocked more than 30 days ago can be marked expired
    expiry_date = timezone.now() - timedelta(days=30)
    
    expired = TimeLockCapsule.objects.filter(
        status='unlocked',
        opened_at__lte=expiry_date
    ).update(status='expired')
    
    logger.info(f"Marked {expired} capsules as expired")
    return {'expired': expired}


# =============================================================================
# Password Will Tasks (Dead Man's Switch)
# =============================================================================

@shared_task(name='time_lock.check_dead_mans_switches')
def check_dead_mans_switches():
    """
    Check for password wills that should trigger.
    Runs daily.
    
    For inactivity-based wills:
    - Send reminder X days before deadline
    - Trigger will if deadline passed
    """
    from security.models import PasswordWill
    
    now = timezone.now()
    results = {
        'reminders_sent': 0,
        'wills_triggered': 0
    }
    
    # Get active wills
    active_wills = PasswordWill.objects.filter(
        is_active=True,
        is_triggered=False
    ).select_related('capsule', 'owner')
    
    for will in active_wills:
        try:
            if will.trigger_type == 'inactivity':
                deadline = will.last_check_in + timedelta(days=will.inactivity_days)
                reminder_date = deadline - timedelta(days=will.check_in_reminder_days)
                
                # Check if should trigger
                if now >= deadline:
                    trigger_password_will.delay(str(will.id))
                    results['wills_triggered'] += 1
                    logger.info(f"Triggering will {will.id} for user {will.owner.username}")
                
                # Check if should send reminder
                elif now >= reminder_date and not will.reminder_sent:
                    send_will_reminder.delay(str(will.id))
                    results['reminders_sent'] += 1
            
            elif will.trigger_type == 'date':
                if now >= will.target_date:
                    trigger_password_will.delay(str(will.id))
                    results['wills_triggered'] += 1
                    
        except Exception as e:
            logger.error(f"Error checking will {will.id}: {e}")
    
    return results


@shared_task(name='time_lock.trigger_password_will')
def trigger_password_will(will_id: str):
    """
    Trigger a password will and notify beneficiaries.
    
    Args:
        will_id: UUID of the will to trigger
    """
    from security.models import PasswordWill
    
    try:
        will = PasswordWill.objects.select_related('capsule', 'owner').get(id=will_id)
        
        if will.is_triggered:
            logger.warning(f"Will {will_id} already triggered")
            return
        
        # Mark will as triggered
        will.is_triggered = True
        will.triggered_at = timezone.now()
        will.save()
        
        # Unlock the capsule
        capsule = will.capsule
        capsule.status = 'unlocked'
        capsule.opened_at = timezone.now()
        capsule.save()
        
        # Notify all beneficiaries
        for beneficiary in capsule.beneficiaries.all():
            notify_beneficiary.delay(
                capsule_id=str(capsule.id),
                beneficiary_id=str(beneficiary.id),
                is_will=True,
                personal_message=will.notes
            )
        
        will.beneficiaries_notified = True
        will.beneficiaries_notified_at = timezone.now()
        will.save()
        
        logger.info(f"Password will {will_id} triggered successfully")
        
        return {'success': True, 'beneficiaries_notified': capsule.beneficiaries.count()}
        
    except PasswordWill.DoesNotExist:
        logger.error(f"Will {will_id} not found")
        return {'success': False, 'error': 'Will not found'}
    except Exception as e:
        logger.error(f"Error triggering will {will_id}: {e}")
        return {'success': False, 'error': str(e)}


@shared_task(name='time_lock.send_will_reminder')
def send_will_reminder(will_id: str):
    """
    Send a reminder to the will owner to check in.
    
    Args:
        will_id: UUID of the will
    """
    from security.models import PasswordWill
    
    try:
        will = PasswordWill.objects.select_related('owner').get(id=will_id)
        
        if will.reminder_sent:
            return {'already_sent': True}
        
        days_remaining = will.days_until_trigger
        
        # Send email reminder
        subject = f"[Password Manager] Check-in Reminder - {days_remaining} days remaining"
        message = f"""
Hello {will.owner.username},

This is a reminder that your Password Will "{will.capsule.title}" will be triggered 
in {days_remaining} days if you don't check in.

To reset the timer, please log into your account and check in:
{settings.FRONTEND_URL}/security/wills/{will.id}/checkin

If you don't check in by the deadline, your passwords will be released to your 
designated beneficiaries.

Stay safe,
Password Manager Team
        """
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[will.owner.email],
            fail_silently=False
        )
        
        will.reminder_sent = True
        will.reminder_sent_at = timezone.now()
        will.save()
        
        logger.info(f"Sent check-in reminder for will {will_id}")
        
        return {'success': True, 'days_remaining': days_remaining}
        
    except PasswordWill.DoesNotExist:
        logger.error(f"Will {will_id} not found")
        return {'success': False}
    except Exception as e:
        logger.error(f"Error sending reminder for will {will_id}: {e}")
        return {'success': False, 'error': str(e)}


# =============================================================================
# Beneficiary Notifications
# =============================================================================

@shared_task(name='time_lock.notify_beneficiary')
def notify_beneficiary(
    capsule_id: str,
    beneficiary_id: str,
    is_will: bool = False,
    personal_message: str = ''
):
    """
    Notify a beneficiary that a capsule has been unlocked.
    
    Args:
        capsule_id: UUID of the unlocked capsule
        beneficiary_id: UUID of the beneficiary
        is_will: Whether this is a password will notification
        personal_message: Optional personal message from owner
    """
    from security.models import TimeLockCapsule, CapsuleBeneficiary
    
    try:
        beneficiary = CapsuleBeneficiary.objects.select_related('capsule').get(
            id=beneficiary_id,
            capsule_id=capsule_id
        )
        
        capsule = beneficiary.capsule
        
        if is_will:
            subject = f"[Password Manager] Password Will - Access Granted"
            message = f"""
Dear {beneficiary.name},

You have been designated as a beneficiary of a Password Will by the owner.
The will has been triggered, and you now have access to the contents.

Capsule: {capsule.title}
Access Level: {beneficiary.access_level.title()}

{f'Personal Message from Owner:{chr(10)}{personal_message}{chr(10)}' if personal_message else ''}

To access the contents, please visit:
{settings.FRONTEND_URL}/security/capsules/{capsule.id}/access?token={beneficiary.verification_token}

Please handle this sensitive information responsibly.

Password Manager Team
            """
        else:
            subject = f"[Password Manager] Time-Lock Capsule Unlocked"
            message = f"""
Dear {beneficiary.name},

A time-lock capsule you were designated as beneficiary for has been unlocked.

Capsule: {capsule.title}
Owner: {capsule.owner.username}
Access Level: {beneficiary.access_level.title()}

To access the contents, please visit:
{settings.FRONTEND_URL}/security/capsules/{capsule.id}/access?token={beneficiary.verification_token}

Password Manager Team
            """
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[beneficiary.email],
            fail_silently=False
        )
        
        # Mark as notified
        beneficiary.notified_at = timezone.now()
        beneficiary.save()
        
        logger.info(f"Notified beneficiary {beneficiary.email} for capsule {capsule_id}")
        
        return {'success': True, 'email': beneficiary.email}
        
    except CapsuleBeneficiary.DoesNotExist:
        logger.error(f"Beneficiary {beneficiary_id} not found for capsule {capsule_id}")
        return {'success': False}
    except Exception as e:
        logger.error(f"Error notifying beneficiary {beneficiary_id}: {e}")
        return {'success': False, 'error': str(e)}


# =============================================================================
# Escrow Tasks
# =============================================================================

@shared_task(name='time_lock.check_escrow_deadlines')
def check_escrow_deadlines():
    """
    Check for escrow agreements that have reached their deadline.
    Runs hourly.
    """
    from security.models import EscrowAgreement
    
    now = timezone.now()
    
    # Find escrows with passed approval deadlines
    expired = EscrowAgreement.objects.filter(
        is_released=False,
        is_disputed=False,
        approval_deadline__lte=now
    )
    
    auto_released = 0
    
    for escrow in expired:
        try:
            if escrow.can_release:
                escrow.release()
                auto_released += 1
                
                # Notify parties
                for party in escrow.parties.all():
                    send_mail(
                        subject=f"[Password Manager] Escrow Released: {escrow.title}",
                        message=f"The escrow agreement '{escrow.title}' has been released.",
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[party.email],
                        fail_silently=True
                    )
                    
        except Exception as e:
            logger.error(f"Error processing escrow {escrow.id}: {e}")
    
    return {'auto_released': auto_released}


# =============================================================================
# VDF Background Computation
# =============================================================================

@shared_task(name='time_lock.process_vdf_computation')
def process_vdf_computation(capsule_id: str):
    """
    Background VDF computation for hybrid mode capsules.
    
    This runs the VDF computation on the server for capsules
    that support both server and client unlock modes.
    
    Args:
        capsule_id: UUID of the capsule
    """
    from security.models import TimeLockCapsule, VDFProof
    from security.services.vdf_service import vdf_service, VDFParams
    
    try:
        capsule = TimeLockCapsule.objects.get(id=capsule_id)
        
        if capsule.mode not in ['client', 'hybrid']:
            logger.info(f"Capsule {capsule_id} doesn't need VDF computation")
            return
        
        if not capsule.puzzle_n or not capsule.puzzle_a or not capsule.puzzle_t:
            logger.error(f"Capsule {capsule_id} missing puzzle parameters")
            return
        
        # Build VDF params
        params = VDFParams(
            modulus=int(capsule.puzzle_n),
            challenge=int(capsule.puzzle_a),
            iterations=capsule.puzzle_t
        )
        
        logger.info(f"Starting VDF computation for capsule {capsule_id}")
        
        # Compute VDF
        output = vdf_service.compute(params)
        
        # Store proof
        VDFProof.objects.create(
            capsule=capsule,
            challenge=capsule.puzzle_a,
            output=str(output.output),
            proof=str(output.proof),
            modulus=capsule.puzzle_n,
            iterations=capsule.puzzle_t,
            verified=True,
            computation_time_seconds=output.computation_time,
            hardware_info=output.hardware_info
        )
        
        logger.info(f"VDF computation complete for capsule {capsule_id}")
        
        return {
            'success': True,
            'computation_time': output.computation_time
        }
        
    except TimeLockCapsule.DoesNotExist:
        logger.error(f"Capsule {capsule_id} not found")
        return {'success': False}
    except Exception as e:
        logger.error(f"VDF computation failed for capsule {capsule_id}: {e}")
        return {'success': False, 'error': str(e)}


# =============================================================================
# Task Scheduling Configuration (for Celery Beat)
# =============================================================================

CELERY_BEAT_SCHEDULE = {
    'check-capsule-unlocks': {
        'task': 'time_lock.check_capsule_unlocks',
        'schedule': 300.0,  # Every 5 minutes
    },
    'check-dead-mans-switches': {
        'task': 'time_lock.check_dead_mans_switches',
        'schedule': 86400.0,  # Daily
    },
    'check-expired-capsules': {
        'task': 'time_lock.check_expired_capsules',
        'schedule': 86400.0,  # Daily
    },
    'check-escrow-deadlines': {
        'task': 'time_lock.check_escrow_deadlines',
        'schedule': 3600.0,  # Hourly
    },
}
