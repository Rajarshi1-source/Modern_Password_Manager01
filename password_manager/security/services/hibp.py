import requests
import hashlib
import logging
import time

logger = logging.getLogger(__name__)

# HIBP API endpoints
HIBP_API_URL = "https://haveibeenpwned.com/api/v3"
HIBP_PASSWORD_API_URL = "https://api.pwnedpasswords.com/range"

# Add your API key here if you have one
HIBP_API_KEY = ""  # Use environment variables in production

def hash_password(password):
    """
    Create SHA-1 hash of a password for checking against the HIBP API
    
    Args:
        password (str): The password to hash
        
    Returns:
        str: SHA-1 hash of the password in uppercase
    """
    sha1 = hashlib.sha1()
    sha1.update(password.encode('utf-8'))
    return sha1.hexdigest().upper()


def check_password_prefix(prefix):
    """
    Check if a password hash prefix appears in breached data
    
    Args:
        prefix (str): First 5 characters of SHA-1 hash
        
    Returns:
        dict: Dictionary of hash suffixes and occurrence counts
    """
    if not prefix or len(prefix) != 5:
        raise ValueError("Prefix must be exactly 5 characters")
    
    try:
        response = requests.get(f"{HIBP_PASSWORD_API_URL}/{prefix}")
        response.raise_for_status()
        
        # Parse response (format: hash_suffix:count)
        result = {}
        for line in response.text.splitlines():
            parts = line.split(':')
            if len(parts) == 2:
                hash_suffix = parts[0].strip()
                count = int(parts[1].strip())
                result[hash_suffix] = count
                
        return result
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error checking password breach: {str(e)}")
        # Return empty dict rather than failing
        return {}


def is_password_breached(password_hash):
    """
    Check if a password has been breached
    
    Args:
        password_hash (str): SHA-1 hash of the password or the password itself
        
    Returns:
        tuple: (bool, int) - Whether the password was breached and how many times
    """
    # If input is not a hash, hash it
    if len(password_hash) != 40 or not all(c in '0123456789abcdefABCDEF' for c in password_hash):
        password_hash = hash_password(password_hash)
    
    prefix = password_hash[:5]
    suffix = password_hash[5:]
    
    breach_data = check_password_prefix(prefix)
    
    if suffix.upper() in breach_data:
        return True, breach_data[suffix.upper()]
    
    return False, 0


def get_breached_sites_for_email(email, include_unverified=False):
    """
    Check if an email appears in any breached sites
    
    Args:
        email (str): Email to check
        include_unverified (bool): Whether to include unverified breaches
        
    Returns:
        list: List of breaches the email appears in
    """
    if not HIBP_API_KEY:
        # In production you should use an API key
        logger.warning("No HIBP API key provided. Email breach checks will be rate limited.")
        # Add delay to avoid rate limiting
        time.sleep(1.5)
    
    headers = {
        'User-Agent': 'SecureVault Password Manager',
        'hibp-api-key': HIBP_API_KEY
    }
    
    params = {
        'truncateResponse': 'false',
        'includeUnverified': 'true' if include_unverified else 'false'
    }
    
    try:
        response = requests.get(
            f"{HIBP_API_URL}/breachedaccount/{email}",
            headers=headers,
            params=params
        )
        
        if response.status_code == 404:
            # No breaches found
            return []
        
        response.raise_for_status()
        return response.json()
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error checking email breach: {str(e)}")
        # Return empty list rather than failing
        return [] 