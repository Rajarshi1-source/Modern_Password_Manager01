from django.apps import AppConfig


class FheSharingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'fhe_sharing'
    verbose_name = 'FHE Homomorphic Password Sharing'

    def ready(self):
        """Import signal handlers if any."""
        pass
