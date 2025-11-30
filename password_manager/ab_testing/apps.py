from django.apps import AppConfig


class AbTestingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ab_testing'
    verbose_name = 'A/B Testing & Feature Flags'

