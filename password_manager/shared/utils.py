"""
Utility functions for the Password Manager application.

This module contains helper functions and utilities that are used
across multiple apps in the password manager project.
"""

import re
import uuid
import hashlib
import secrets
import string
import base64
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
from typing import Optional, Dict, Any, List
from .constants import DEVICE_TYPES, PASSWORD_STRENGTH_LEVELS


def generate_secure_id(length: int = 32) -> str:
    """
    Generate a cryptographically secure random ID.
    
    Args:
        length (int): Length of the ID to generate
        
    Returns:
        str: Secure random ID
    """
    return secrets.token_urlsafe(length)


def generate_uuid() -> str:
    """
    Generate a UUID4 string.
    
    Returns:
        str: UUID4 string
    """
    return str(uuid.uuid4())


def hash_string(text: str, algorithm: str = 'sha256') -> str:
    """
    Hash a string using the specified algorithm.
    
    Args:
        text (str): Text to hash
        algorithm (str): Hash algorithm to use
        
    Returns:
        str: Hexadecimal hash string
    """
    if algorithm == 'sha256':
        return hashlib.sha256(text.encode()).hexdigest()
    elif algorithm == 'sha512':
        return hashlib.sha512(text.encode()).hexdigest()
    else:
        raise ValueError(f"Unsupported hash algorithm: {algorithm}")


def generate_random_password(
    length: int = 16,
    include_uppercase: bool = True,
    include_lowercase: bool = True,
    include_numbers: bool = True,
    include_symbols: bool = True,
    exclude_ambiguous: bool = True
) -> str:
    """
    Generate a random password with specified criteria.
    
    Args:
        length (int): Length of password
        include_uppercase (bool): Include uppercase letters
        include_lowercase (bool): Include lowercase letters
        include_numbers (bool): Include numbers
        include_symbols (bool): Include symbols
        exclude_ambiguous (bool): Exclude ambiguous characters
        
    Returns:
        str: Generated password
    """
    characters = ""
    
    if include_lowercase:
        chars = string.ascii_lowercase
        if exclude_ambiguous:
            chars = chars.replace('l', '').replace('o', '')
        characters += chars
    
    if include_uppercase:
        chars = string.ascii_uppercase
        if exclude_ambiguous:
            chars = chars.replace('I', '').replace('O', '')
        characters += chars
    
    if include_numbers:
        chars = string.digits
        if exclude_ambiguous:
            chars = chars.replace('0', '').replace('1', '')
        characters += chars
    
    if include_symbols:
        chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
        if exclude_ambiguous:
            chars = chars.replace('|', '').replace('`', '')
        characters += chars
    
    if not characters:
        raise ValueError("At least one character type must be included")
    
    # Ensure at least one character from each enabled type
    password = []
    if include_lowercase:
        password.append(secrets.choice(string.ascii_lowercase))
    if include_uppercase:
        password.append(secrets.choice(string.ascii_uppercase))
    if include_numbers:
        password.append(secrets.choice(string.digits))
    if include_symbols:
        password.append(secrets.choice("!@#$%^&*()_+-=[]{}|;:,.<>?"))
    
    # Fill remaining length with random characters
    for _ in range(length - len(password)):
        password.append(secrets.choice(characters))
    
    # Shuffle the password
    secrets.SystemRandom().shuffle(password)
    
    return ''.join(password)


def get_client_ip(request) -> str:
    """
    Extract client IP address from Django request.
    
    Args:
        request: Django request object
        
    Returns:
        str: Client IP address
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip or '127.0.0.1'


def get_user_agent_info(user_agent_string: str) -> Dict[str, str]:
    """
    Parse user agent string to extract device information.
    
    Args:
        user_agent_string (str): User agent string
        
    Returns:
        dict: Device information
    """
    ua = user_agent_string.lower()
    
    # Detect browser
    if 'chrome' in ua:
        browser = 'Chrome'
    elif 'firefox' in ua:
        browser = 'Firefox'
    elif 'safari' in ua and 'chrome' not in ua:
        browser = 'Safari'
    elif 'edge' in ua:
        browser = 'Edge'
    elif 'opera' in ua:
        browser = 'Opera'
    else:
        browser = 'Unknown'
    
    # Detect OS
    if 'windows' in ua:
        os = 'Windows'
    elif 'macintosh' in ua or 'mac os' in ua:
        os = 'macOS'
    elif 'linux' in ua:
        os = 'Linux'
    elif 'android' in ua:
        os = 'Android'
    elif 'iphone' in ua or 'ipad' in ua:
        os = 'iOS'
    else:
        os = 'Unknown'
    
    # Detect device type
    if 'mobile' in ua or 'android' in ua or 'iphone' in ua:
        device_type = DEVICE_TYPES['MOBILE']
    elif 'tablet' in ua or 'ipad' in ua:
        device_type = DEVICE_TYPES['TABLET']
    else:
        device_type = DEVICE_TYPES['DESKTOP']
    
    return {
        'browser': browser,
        'os': os,
        'device_type': device_type,
        'raw': user_agent_string[:200]  # Truncate to avoid issues
    }


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename for safe filesystem usage.
    
    Args:
        filename (str): Original filename
        
    Returns:
        str: Sanitized filename
    """
    # Remove or replace unsafe characters
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    
    # Remove control characters
    filename = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', filename)
    
    # Trim whitespace and dots
    filename = filename.strip(' .')
    
    # Ensure filename is not empty and not reserved
    if not filename or filename.upper() in [
        'CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4',
        'COM5', 'COM6', 'COM7', 'COM8', 'COM9', 'LPT1', 'LPT2',
        'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
    ]:
        filename = f'file_{generate_secure_id(8)}'
    
    # Limit length
    if len(filename) > 255:
        name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
        max_name_length = 255 - len(ext) - 1 if ext else 255
        filename = f"{name[:max_name_length]}.{ext}" if ext else name[:255]
    
    return filename


def time_ago(dt: datetime) -> str:
    """
    Convert datetime to human-readable "time ago" format.
    
    Args:
        dt (datetime): Datetime to convert
        
    Returns:
        str: Human-readable time string
    """
    now = timezone.now()
    diff = now - dt
    
    if diff.days > 365:
        years = diff.days // 365
        return f"{years} year{'s' if years != 1 else ''} ago"
    elif diff.days > 30:
        months = diff.days // 30
        return f"{months} month{'s' if months != 1 else ''} ago"
    elif diff.days > 0:
        return f"{diff.days} day{'s' if diff.days != 1 else ''} ago"
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    else:
        return "Just now"


def mask_sensitive_data(data: str, mask_char: str = '*', visible_chars: int = 4) -> str:
    """
    Mask sensitive data for display.
    
    Args:
        data (str): Data to mask
        mask_char (str): Character to use for masking
        visible_chars (int): Number of characters to leave visible at the end
        
    Returns:
        str: Masked data
    """
    if len(data) <= visible_chars:
        return mask_char * len(data)
    
    visible_part = data[-visible_chars:]
    masked_length = len(data) - visible_chars
    
    return mask_char * masked_length + visible_part


def cache_key_for_user(user_id: int, key: str) -> str:
    """
    Generate a cache key for user-specific data.
    
    Args:
        user_id (int): User ID
        key (str): Cache key suffix
        
    Returns:
        str: Full cache key
    """
    return f"user:{user_id}:{key}"


def cache_key_for_session(session_key: str, key: str) -> str:
    """
    Generate a cache key for session-specific data.
    
    Args:
        session_key (str): Session key
        key (str): Cache key suffix
        
    Returns:
        str: Full cache key
    """
    return f"session:{session_key}:{key}"


def is_safe_url(url: str, allowed_hosts: List[str] = None) -> bool:
    """
    Check if a URL is safe for redirects.
    
    Args:
        url (str): URL to check
        allowed_hosts (list): List of allowed hosts
        
    Returns:
        bool: True if URL is safe
    """
    if not url:
        return False
    
    # Check for dangerous schemes
    if url.startswith(('javascript:', 'data:', 'vbscript:')):
        return False
    
    # Allow relative URLs
    if url.startswith('/') and not url.startswith('//'):
        return True
    
    # Check against allowed hosts if provided
    if allowed_hosts:
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.hostname in allowed_hosts
        except Exception:
            return False
    
    return False


def truncate_string(text: str, max_length: int, suffix: str = '...') -> str:
    """
    Truncate a string to a maximum length with suffix.
    
    Args:
        text (str): Text to truncate
        max_length (int): Maximum length
        suffix (str): Suffix to add if truncated
        
    Returns:
        str: Truncated string
    """
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in bytes to human-readable string.
    
    Args:
        size_bytes (int): Size in bytes
        
    Returns:
        str: Formatted size string
    """
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size = float(size_bytes)
    
    while size >= 1024.0 and i < len(size_names) - 1:
        size /= 1024.0
        i += 1
    
    return f"{size:.1f} {size_names[i]}"


def validate_and_format_phone(phone: str) -> str:
    """
    Validate and format phone number.
    
    Args:
        phone (str): Phone number to format
        
    Returns:
        str: Formatted phone number
        
    Raises:
        ValueError: If phone number is invalid
    """
    # Remove all non-digit characters
    digits = re.sub(r'\D', '', phone)
    
    # Check length
    if len(digits) < 10 or len(digits) > 15:
        raise ValueError("Phone number must be 10-15 digits")
    
    # Format based on length
    if len(digits) == 10:
        # US number without country code
        return f"+1{digits}"
    elif len(digits) == 11 and digits.startswith('1'):
        # US number with country code
        return f"+{digits}"
    else:
        # International number
        return f"+{digits}"
