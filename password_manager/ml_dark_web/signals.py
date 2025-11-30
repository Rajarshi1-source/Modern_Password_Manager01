"""
Django Signals for ML Dark Web Monitoring
"""

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model

from .models import MLBreachMatch, UserCredentialMonitoring
from .tasks import create_breach_alert

User = get_user_model()


@receiver(post_save, sender=MLBreachMatch)
def on_breach_match_created(sender, instance, created, **kwargs):
    """
    Automatically create alert when a breach match is detected
    """
    if created and not instance.alert_created:
        # Create alert async
        try:
            create_breach_alert.delay(instance.id)
        except Exception as e:
            # Gracefully handle Celery/Redis unavailability in development
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Could not queue breach alert task: {e}")


# Optional: Monitor new user registrations
@receiver(post_save, sender=User)
def on_user_created(sender, instance, created, **kwargs):
    """
    Optionally monitor new users' email automatically
    """
    if created and hasattr(instance, 'email') and instance.email:
        # Add user's email to monitoring (async)
        from .tasks import monitor_user_credentials
        try:
            monitor_user_credentials.delay(instance.id, [instance.email])
        except Exception as e:
            # Gracefully handle Celery/Redis unavailability in development
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Could not queue credential monitoring task: {e}")

