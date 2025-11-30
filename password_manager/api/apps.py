from django.apps import AppConfig


class ApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api'

    def ready(self):
        """
        Called when the app is ready - used for any initialization
        that should happen when Django starts
        """
        # Import signals or perform other setup if needed
        pass
