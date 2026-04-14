import hashlib
import requests
import logging
from django.conf import settings
from django.utils import timezone
from vault.models.vault_models import EncryptedVaultItem
from shared.circuit_breaker import hibp_breaker, CircuitBreakerOpen

logger = logging.getLogger(__name__)

class HIBPService:
    """Service for interacting with Have I Been Pwned API"""
    
    API_URL = "https://api.pwnedpasswords.com/range/"
    
    @classmethod
    def check_password_prefix(cls, prefix):
        """
        Check a SHA-1 password hash prefix against the HIBP API
        Uses k-anonymity model for privacy
        
        Args:
            prefix (str): First 5 characters of SHA-1 hash
            
        Returns:
            dict: Dictionary of hash suffixes to breach counts
        """
        try:
            hibp_breaker.before_call()

            headers = {"User-Agent": "PasswordManager-SecurityMonitor"}
            
            if hasattr(settings, 'HIBP_API_KEY') and settings.HIBP_API_KEY:
                headers["hibp-api-key"] = settings.HIBP_API_KEY
            
            response = requests.get(
                f"{cls.API_URL}{prefix}", 
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                result = {}
                lines = response.text.splitlines()
                for line in lines:
                    suffix, count = line.split(":")
                    result[suffix.strip()] = int(count.strip())
                hibp_breaker.on_success()
                return result
            
            if response.status_code == 404:
                hibp_breaker.on_success()
                return {}
            if response.status_code == 429:
                logger.warning("Rate limit exceeded when checking HIBP API")
                raise Exception("Rate limit exceeded for breach API")
            
            response.raise_for_status()

        except CircuitBreakerOpen as e:
            logger.warning(f"HIBP circuit breaker OPEN: {e}")
            return {}
        except requests.RequestException as e:
            hibp_breaker.on_failure(e)
            logger.error(f"Error checking HIBP API: {str(e)}")
            raise Exception(f"Error checking breach database: {str(e)}")
    
    @staticmethod
    def hash_password(password):
        """
        Generate SHA-1 hash of a password
        
        Args:
            password (str): Password to hash
            
        Returns:
            str: Uppercase SHA-1 hash
        """
        sha1 = hashlib.sha1(password.encode('utf-8'))
        return sha1.hexdigest().upper()
