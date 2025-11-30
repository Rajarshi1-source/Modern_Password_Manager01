from django.apps import AppConfig


class BehavioralRecoveryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'behavioral_recovery'
    verbose_name = 'Behavioral Biometric Recovery'
    
    def ready(self):
        """
        Initialize behavioral recovery app
        """
        import behavioral_recovery.signals  # noqa

