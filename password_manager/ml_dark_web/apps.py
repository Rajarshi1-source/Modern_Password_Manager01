import os
import sys

from django.apps import AppConfig


class MlDarkWebConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ml_dark_web'
    verbose_name = 'ML Dark Web Monitoring'
    
    def ready(self):
        """Initialize ML models when Django starts"""
        # Skip in the reloader parent process — only load in the child worker
        if os.environ.get('RUN_MAIN') != 'true' and 'runserver' in sys.argv:
            return

        import ml_dark_web.signals  # noqa: F401 — Import signals for registration

