from django.apps import AppConfig


class EmailMaskingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'email_masking'
    verbose_name = 'Email Masking & Alias Management'

