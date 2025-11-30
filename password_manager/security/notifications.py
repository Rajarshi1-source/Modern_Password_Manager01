from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone
from vault.models import BreachAlert

def send_breach_notification(alert):
    """Send email notification for breach alert"""
    if alert.notified:
        return False
        
    try:
        context = {
            'user': alert.user,
            'alert': alert,
            'breach_date': alert.breach_date.strftime('%B %d, %Y'),
            'app_url': 'https://your-password-manager.com/security/alerts'
        }
        
        subject = f'SECURITY ALERT: {alert.breach_name} Data Breach'
        
        html_message = render_to_string('emails/breach_notification.html', context)
        plain_message = render_to_string('emails/breach_notification.txt', context)
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email='security@your-password-manager.com',
            recipient_list=[alert.user.email],
            html_message=html_message,
            fail_silently=False
        )
        
        # Update notification status
        alert.notified = True
        alert.notification_sent_at = timezone.now()
        alert.save()
        
        return True
    except Exception as e:
        print(f"Error sending notification: {str(e)}")
        return False

def process_pending_notifications():
    """Process all pending breach notifications"""
    pending_alerts = BreachAlert.objects.filter(
        notified=False, 
        resolved=False
    )
    
    sent_count = 0
    for alert in pending_alerts:
        if send_breach_notification(alert):
            sent_count += 1
    
    return sent_count
