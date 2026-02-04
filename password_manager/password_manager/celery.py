"""
Celery Configuration for Password Manager

This module configures Celery for asynchronous task processing.
Supports: background tasks, scheduled tasks, blockchain anchoring, ML operations, FHE operations

Usage:
    celery -A password_manager worker -l info
    celery -A password_manager beat -l info
"""

import os
from celery import Celery
from celery.schedules import crontab

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'password_manager.settings')

app = Celery('password_manager')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# Configure Celery settings
app.conf.update(
    # Task execution settings
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    
    # Task routing
    task_routes={
        'blockchain.*': {'queue': 'blockchain'},
        'ml_*': {'queue': 'ml'},
        'fhe_service.*': {'queue': 'fhe'},
    },
    
    # Task time limits (prevent hanging tasks)
    task_soft_time_limit=300,  # 5 minutes soft limit
    task_time_limit=600,  # 10 minutes hard limit
    
    # Task result settings
    result_expires=3600,  # Results expire after 1 hour
    result_backend_transport_options={
        'master_name': 'mymaster',
        'visibility_timeout': 3600,
    },
    
    # Worker settings
    worker_prefetch_multiplier=1,  # Disable prefetching for long-running tasks
    worker_max_tasks_per_child=1000,  # Restart worker after 1000 tasks to prevent memory leaks
    
    # Retry settings
    task_acks_late=True,  # Acknowledge task after it completes
    task_reject_on_worker_lost=True,  # Reject task if worker dies
    
    # Beat schedule for periodic tasks
    beat_schedule={
        # Password strength analysis (daily)
        'analyze-password-strength-daily': {
            'task': 'ml_security.tasks.analyze_all_passwords',
            'schedule': crontab(hour=2, minute=0),  # 2:00 AM daily
        },
        
        # Breach monitoring (every 6 hours)
        'check-data-breaches': {
            'task': 'ml_dark_web.tasks.check_compromised_passwords',
            'schedule': crontab(minute=0, hour='*/6'),  # Every 6 hours
        },
        
        # Blockchain anchoring (if enabled, hourly)
        'anchor-vault-to-blockchain': {
            'task': 'blockchain.tasks.anchor_pending_commitments',
            'schedule': crontab(minute=0),  # Every hour
        },
        
        # Clean up expired sessions (daily)
        'cleanup-expired-sessions': {
            'task': 'shared.tasks.cleanup_expired_sessions',
            'schedule': crontab(hour=3, minute=0),  # 3:00 AM daily
        },
        
        # Clean up old logs (weekly)
        'cleanup-old-logs': {
            'task': 'logging_manager.tasks.cleanup_old_logs',
            'schedule': crontab(day_of_week=0, hour=4, minute=0),  # Sunday 4:00 AM
        },
        
        # Update threat intelligence (daily)
        'update-threat-intel': {
            'task': 'ml_security.tasks.update_threat_intelligence',
            'schedule': crontab(hour=1, minute=30),  # 1:30 AM daily
        },
        
        # =================================================================
        # Genetic Password Evolution Tasks
        # =================================================================
        
        # Daily genetic evolution check (for premium users)
        'check-genetic-evolution-daily': {
            'task': 'security.tasks.daily_genetic_evolution_check',
            'schedule': crontab(hour=5, minute=0),  # 5:00 AM daily
        },
        
        # Cleanup expired genetic trials (daily)
        'cleanup-genetic-trials': {
            'task': 'security.tasks.cleanup_expired_genetic_trials',
            'schedule': crontab(hour=4, minute=30),  # 4:30 AM daily
        },
        
        # Refresh DNA provider OAuth tokens (weekly)
        'refresh-dna-tokens-weekly': {
            'task': 'security.tasks.refresh_dna_tokens',
            'schedule': crontab(day_of_week=6, hour=3, minute=0),  # Saturday 3:00 AM
        },
        
        # =================================================================
        # 🌑 Dark Protocol Network Tasks
        # =================================================================
        
        # Rotate anonymous routing paths (every 5 minutes)
        'dark-protocol-rotate-paths': {
            'task': 'dark_protocol.rotate_network_paths',
            'schedule': crontab(minute='*/5'),  # Every 5 minutes
        },
        
        # Health check network nodes (every minute)
        'dark-protocol-health-check': {
            'task': 'dark_protocol.health_check_nodes',
            'schedule': crontab(minute='*'),  # Every minute
        },
        
        # Generate cover traffic for active sessions (every 2 minutes)
        'dark-protocol-cover-traffic': {
            'task': 'dark_protocol.generate_cover_traffic',
            'schedule': crontab(minute='*/2'),  # Every 2 minutes
        },
        
        # Cleanup expired sessions and bundles (every 15 minutes)
        'dark-protocol-cleanup': {
            'task': 'dark_protocol.cleanup_expired_sessions',
            'schedule': crontab(minute='*/15'),  # Every 15 minutes
        },
        
        # Analyze traffic patterns for cover traffic learning (hourly)
        'dark-protocol-traffic-analysis': {
            'task': 'dark_protocol.analyze_traffic_patterns',
            'schedule': crontab(minute=0),  # Every hour
        },
    },
)


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task for testing Celery configuration."""
    print(f'Request: {self.request!r}')
    return 'Celery is working!'


@app.task(bind=True)
def test_task(self):
    """Test task for health checks."""
    return {
        'status': 'success',
        'message': 'Celery worker is healthy',
        'task_id': self.request.id
    }

