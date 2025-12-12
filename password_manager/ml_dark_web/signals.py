"""
Django Signals for ML Dark Web Monitoring
"""

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.conf import settings
import logging

from .models import MLBreachMatch, UserCredentialMonitoring

logger = logging.getLogger(__name__)
User = get_user_model()


def _is_celery_available():
    """Check if Celery/Redis is available before queueing tasks"""
    # Skip Celery tasks in DEBUG mode if Redis is not configured
    if settings.DEBUG:
        try:
            import redis
            r = redis.Redis(host='localhost', port=6379, socket_connect_timeout=1)
            r.ping()
            return True
        except Exception:
            return False
    return True


@receiver(post_save, sender=MLBreachMatch)
def on_breach_match_created(sender, instance, created, **kwargs):
    """
    Automatically create alert when a breach match is detected
    """
    if created and not instance.alert_created:
        # FIX: Check if Celery is available before queueing
        if not _is_celery_available():
            logger.debug("Skipping breach alert task - Celery/Redis not available")
            return
        try:
            from .tasks import create_breach_alert
            create_breach_alert.delay(instance.id)
        except Exception as e:
            logger.warning(f"Could not queue breach alert task: {e}")


# Optional: Monitor new user registrations
@receiver(post_save, sender=User)
def on_user_created(sender, instance, created, **kwargs):
    """
    Optionally monitor new users' email automatically
    """
    if created and hasattr(instance, 'email') and instance.email:
        # FIX: Check if Celery is available before queueing
        if not _is_celery_available():
            logger.debug("Skipping credential monitoring task - Celery/Redis not available")
            return
        try:
            from .tasks import monitor_user_credentials
            monitor_user_credentials.delay(instance.id, [instance.email])
        except Exception as e:
            logger.warning(f"Could not queue credential monitoring task: {e}")

