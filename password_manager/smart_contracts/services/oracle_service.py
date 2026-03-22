"""
Oracle Service — Chainlink Price Feed Integration
====================================================

Reads ETH/USD (and other) prices from Chainlink oracle contracts.
Includes caching to avoid excessive RPC calls.
"""

import logging
import time
from typing import Optional
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

# Cache key prefix
ORACLE_CACHE_PREFIX = 'smart_contracts:oracle:'


class OracleService:
    """
    Reads price data from Chainlink AggregatorV3Interface contracts.
    Supports caching to reduce RPC load.
    """

    def __init__(self):
        self.config = getattr(settings, 'SMART_CONTRACT_AUTOMATION', {})
        self.cache_ttl = self.config.get('ORACLE_CACHE_TTL_SECONDS', 300)

    def get_eth_usd_price(self) -> Optional[float]:
        """
        Get the current ETH/USD price from Chainlink oracle.

        Returns:
            Price in USD as float, or None if unavailable.
        """
        oracle_address = self.config.get('CHAINLINK_ETH_USD_ORACLE', '')
        if not oracle_address:
            logger.warning("CHAINLINK_ETH_USD_ORACLE not configured")
            return None

        return self._get_price_from_oracle(oracle_address, 'ETH/USD')

    def get_price(self, oracle_address: str, pair_name: str = 'UNKNOWN') -> Optional[float]:
        """
        Get price from any Chainlink oracle address.

        Args:
            oracle_address: Chainlink AggregatorV3 contract address
            pair_name: Human-readable pair name for logging

        Returns:
            Price as float (8 decimals), or None if unavailable.
        """
        return self._get_price_from_oracle(oracle_address, pair_name)

    def _get_price_from_oracle(self, oracle_address: str, pair_name: str) -> Optional[float]:
        """Internal: fetch price with caching."""
        cache_key = f"{ORACLE_CACHE_PREFIX}{oracle_address}"

        # Check cache first
        cached_price = cache.get(cache_key)
        if cached_price is not None:
            logger.debug(f"Oracle cache hit for {pair_name}: ${cached_price}")
            return cached_price

        # Fetch from blockchain
        try:
            from .web3_bridge import SmartContractWeb3Bridge
            bridge = SmartContractWeb3Bridge()

            if not bridge.w3:
                logger.warning("Web3 not available for oracle price check")
                return None

            # Chainlink AggregatorV3Interface ABI (latestRoundData only)
            aggregator_abi = [{
                "inputs": [],
                "name": "latestRoundData",
                "outputs": [
                    {"internalType": "uint80", "name": "roundId", "type": "uint80"},
                    {"internalType": "int256", "name": "answer", "type": "int256"},
                    {"internalType": "uint256", "name": "startedAt", "type": "uint256"},
                    {"internalType": "uint256", "name": "updatedAt", "type": "uint256"},
                    {"internalType": "uint80", "name": "answeredInRound", "type": "uint80"}
                ],
                "stateMutability": "view",
                "type": "function"
            }]

            from web3 import Web3
            oracle_contract = bridge.w3.eth.contract(
                address=Web3.to_checksum_address(oracle_address),
                abi=aggregator_abi
            )

            result = oracle_contract.functions.latestRoundData().call()
            answer = result[1]  # int256 answer

            if answer <= 0:
                logger.warning(f"Oracle returned non-positive price for {pair_name}")
                return None

            # Chainlink uses 8 decimals
            price = answer / 1e8

            # Cache the result
            cache.set(cache_key, price, self.cache_ttl)
            logger.info(f"Oracle price for {pair_name}: ${price:,.2f}")

            return price

        except Exception as e:
            logger.error(f"Oracle price fetch failed for {pair_name}: {e}")
            return None

    def clear_cache(self, oracle_address: str = None):
        """Clear oracle price cache."""
        if oracle_address:
            cache.delete(f"{ORACLE_CACHE_PREFIX}{oracle_address}")
        else:
            # Clear all oracle cache entries
            eth_oracle = self.config.get('CHAINLINK_ETH_USD_ORACLE', '')
            if eth_oracle:
                cache.delete(f"{ORACLE_CACHE_PREFIX}{eth_oracle}")
