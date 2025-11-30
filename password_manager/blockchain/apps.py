from django.apps import AppConfig


class BlockchainConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'blockchain'
    verbose_name = 'Blockchain Anchoring'
    
    def ready(self):
        """Initialize blockchain services when app is ready"""
        try:
            from .services import BlockchainAnchorService
            # Initialize singleton instance
            BlockchainAnchorService()
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Could not initialize BlockchainAnchorService: {e}")
