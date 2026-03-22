from django.apps import AppConfig


class SmartContractsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'smart_contracts'
    verbose_name = 'Smart Contract Automation'

    def ready(self):
        """Initialize smart contract services when app is ready."""
        try:
            from .services.web3_bridge import SmartContractWeb3Bridge
            SmartContractWeb3Bridge()
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Could not initialize SmartContractWeb3Bridge: {e}")
