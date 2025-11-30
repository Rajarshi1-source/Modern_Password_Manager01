"""
FHE Service Django App Configuration
"""

from django.apps import AppConfig


class FheServiceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'fhe_service'
    verbose_name = 'Fully Homomorphic Encryption Service'

    def ready(self):
        """Initialize FHE services on app startup."""
        # Import signals if any
        pass

