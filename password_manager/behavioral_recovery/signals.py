"""
Behavioral Recovery Signals

Handles automatic behavioral profile initialization and updates
"""

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def initialize_behavioral_profile(sender, instance, created, **kwargs):
    """
    Initialize behavioral profile for new users
    """
    if created:
        logger.info(f"Initializing behavioral profile for user: {instance.username}")
        # Profile will be built during normal usage

