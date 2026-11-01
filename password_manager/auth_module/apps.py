from django.apps import AppConfig


class AuthModuleConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'auth_module'

    def ready(self):
        from django.contrib.auth import get_user_model
        from django.db.models.signals import post_save

        from .recovery_notice import clear_stale_lock

        post_save.connect(clear_stale_lock, sender=get_user_model(),
                          dispatch_uid='auth_module.clear_stale_lock')
