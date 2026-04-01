import os
import sys

from django.apps import AppConfig


class MlSecurityConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ml_security'
    verbose_name = 'ML Security'
    
    def ready(self):
        """Initialize ML models on app startup"""
        # Skip in the reloader parent process — only load in the child worker
        if os.environ.get('RUN_MAIN') != 'true' and 'runserver' in sys.argv:
            return

        from .ml_models import load_models
        try:
            load_models()
        except Exception as e:
            print(f"Warning: Failed to load ML models: {e}")

