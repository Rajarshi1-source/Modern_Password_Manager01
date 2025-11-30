"""
Django app configuration for the shared utilities module.
"""

from django.apps import AppConfig


class SharedConfig(AppConfig):
    """
    Configuration for the shared utilities app.
    
    This app contains common utilities, validators, constants,
    and decorators used across the password manager project.
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'shared'
    verbose_name = 'Shared Utilities'
    
    def ready(self):
        """
        Called when the app is ready.
        Perform any initialization that should happen when Django starts.
        """
        # Import signals or perform other setup if needed
        pass
