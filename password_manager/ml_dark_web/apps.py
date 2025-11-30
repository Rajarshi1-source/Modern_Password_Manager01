from django.apps import AppConfig


class MlDarkWebConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ml_dark_web'
    verbose_name = 'ML Dark Web Monitoring'
    
    def ready(self):
        """Initialize ML models when Django starts"""
        import ml_dark_web.signals  # Import signals if any

