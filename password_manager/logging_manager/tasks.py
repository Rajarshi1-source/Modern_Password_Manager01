"""Celery tasks for the logging_manager app.

These wrap the corresponding management commands so they can be invoked by
both Celery beat *and* K8s CronJobs (which call the manage.py commands
directly).
"""

from celery import shared_task
from django.core.management import call_command


@shared_task(name="logging_manager.tasks.cleanup_old_logs")
def cleanup_old_logs():
    """Delete SystemLog entries older than the configured retention window."""
    call_command("cleanup_old_logs")
