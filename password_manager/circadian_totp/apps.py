from django.apps import AppConfig


class CircadianTotpConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "circadian_totp"
    verbose_name = "Biological Clock-Based TOTP"
