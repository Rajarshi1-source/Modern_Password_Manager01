from django.apps import AppConfig


class BlockchainConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'blockchain'
    verbose_name = 'Blockchain Anchoring'
    
    def ready(self):
        """Initialize blockchain services when app is ready"""
        # Validate Chainlink oracle configuration for on-chain smart contract automation.
        # If smart contract automation is enabled but the oracle address is missing,
        # we fail loudly rather than silently defaulting to a Sepolia testnet oracle.
        from django.conf import settings as django_settings
        from django.core.exceptions import ImproperlyConfigured

        SMART_CONTRACT_AUTOMATION = getattr(django_settings, 'SMART_CONTRACT_AUTOMATION', {})
        if SMART_CONTRACT_AUTOMATION.get('ENABLED') and not SMART_CONTRACT_AUTOMATION.get('CHAINLINK_ETH_USD_ORACLE'):
            raise ImproperlyConfigured(
                "CHAINLINK_ETH_USD_ORACLE must be set when SMART_CONTRACTS_ENABLED=True. "
                "Sepolia testnet: 0x694AA1769357215DE4FAC081bf1f309aDC325306, "
                "Mainnet: 0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419"
            )

        try:
            from .services import BlockchainAnchorService
            # Initialize singleton instance
            BlockchainAnchorService()
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Could not initialize BlockchainAnchorService: {e}")
