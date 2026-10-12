from django.apps import AppConfig


class LoggingManagerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'logging_manager'

    def ready(self):
        from . import metrics
        metrics.register()
