from django.apps import AppConfig


class AdversarialAiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'adversarial_ai'
    verbose_name = 'Adversarial AI Password Defense'
    
    def ready(self):
        # Import signals if needed
        pass
