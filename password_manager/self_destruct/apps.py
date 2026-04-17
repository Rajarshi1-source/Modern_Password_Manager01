from django.apps import AppConfig


class SelfDestructConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'self_destruct'
    verbose_name = 'Self-destructing passwords'
