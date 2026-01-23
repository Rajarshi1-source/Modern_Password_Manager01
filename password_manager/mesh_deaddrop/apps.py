"""
Mesh Dead Drop Django App Configuration
"""

from django.apps import AppConfig


class MeshDeaddropConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'mesh_deaddrop'
    verbose_name = 'Mesh Dead Drop Password Sharing'

    def ready(self):
        # Import signal handlers
        pass
