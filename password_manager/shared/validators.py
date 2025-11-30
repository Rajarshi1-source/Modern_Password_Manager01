"""
Custom validators for the Password Manager application.

This module contains validation functions and classes that are used
across multiple apps to ensure data integrity and security.
"""

import re
import string
from django.core.exceptions import ValidationError
from django.core.validators import validate_email as django_validate_email
from django.utils.translation import gettext_lazy as _
from .constants import (
    MINIMUM_PASSWORD_LENGTH, MAXIMUM_PASSWORD_LENGTH,
    REGEX_PATTERNS, PASSWORD_STRENGTH_LEVELS
)


def validate_strong_password(password):
    """
    Validate that a password meets strong security requirements.
    
    Args:
        password (str): The password to validate
        
    Raises:
        ValidationError: If password doesn't meet requirements
    """
    if len(password) < MINIMUM_PASSWORD_LENGTH:
        raise ValidationError(
            _(f'Password must be at least {MINIMUM_PASSWORD_LENGTH} characters long.')
        )
    
    if len(password) > MAXIMUM_PASSWORD_LENGTH:
        raise ValidationError(
            _(f'Password must be no more than {MAXIMUM_PASSWORD_LENGTH} characters long.')
        )
    
    # Check for character diversity
    has_lower = any(c.islower() for c in password)
    has_upper = any(c.isupper() for c in password)
    has_digit = any(c.isdigit() for c in password)
    has_special = any(c in string.punctuation for c in password)
    
    missing_requirements = []
    if not has_lower:
        missing_requirements.append('lowercase letter')
    if not has_upper:
        missing_requirements.append('uppercase letter')
    if not has_digit:
        missing_requirements.append('number')
    if not has_special:
        missing_requirements.append('special character')
    
    if missing_requirements:
        raise ValidationError(
            _('Password must contain at least one: {}').format(
                ', '.join(missing_requirements)
            )
        )


def validate_username(username):
    """
    Validate username format and requirements.
    
    Args:
        username (str): The username to validate
        
    Raises:
        ValidationError: If username is invalid
    """
    if not re.match(REGEX_PATTERNS['USERNAME'], username):
        raise ValidationError(
            _('Username must be 3-30 characters long and contain only '
              'letters, numbers, underscores, and hyphens.')
        )


def validate_phone_number(phone):
    """
    Validate phone number format.
    
    Args:
        phone (str): The phone number to validate
        
    Raises:
        ValidationError: If phone number is invalid
    """
    if not re.match(REGEX_PATTERNS['PHONE'], phone):
        raise ValidationError(
            _('Phone number must be 9-15 digits and may start with +.')
        )


def validate_master_password(password):
    """
    Validate master password with extra security requirements.
    
    Args:
        password (str): The master password to validate
        
    Raises:
        ValidationError: If password doesn't meet master password requirements
    """
    # Use strong password validation as base
    validate_strong_password(password)
    
    # Additional requirements for master passwords
    if len(password) < 12:
        raise ValidationError(
            _('Master password must be at least 12 characters long.')
        )
    
    # Check for common patterns
    common_patterns = [
        'password', '123456', 'qwerty', 'admin', 'letmein',
        'welcome', 'monkey', 'dragon', '1234567890'
    ]
    
    lower_password = password.lower()
    for pattern in common_patterns:
        if pattern in lower_password:
            raise ValidationError(
                _('Master password cannot contain common patterns.')
            )


def calculate_password_strength(password):
    """
    Calculate password strength score.
    
    Args:
        password (str): The password to evaluate
        
    Returns:
        dict: Dictionary with strength score and feedback
    """
    score = 0
    feedback = []
    
    # Length scoring
    if len(password) >= 8:
        score += 1
    if len(password) >= 12:
        score += 1
    if len(password) >= 16:
        score += 1
    
    # Character diversity
    has_lower = any(c.islower() for c in password)
    has_upper = any(c.isupper() for c in password)
    has_digit = any(c.isdigit() for c in password)
    has_special = any(c in string.punctuation for c in password)
    
    char_types = sum([has_lower, has_upper, has_digit, has_special])
    score += char_types
    
    # Penalties for common patterns
    if password.lower() in ['password', '123456', 'qwerty']:
        score -= 2
        feedback.append('Avoid common passwords')
    
    # Check for repeated characters
    if len(set(password)) / len(password) < 0.5:
        score -= 1
        feedback.append('Avoid too many repeated characters')
    
    # Normalize score
    score = max(0, min(4, score))
    
    # Provide feedback
    if score == 0:
        strength = 'Very Weak'
        feedback.append('Password is too weak')
    elif score == 1:
        strength = 'Weak'
        feedback.append('Add more character types and length')
    elif score == 2:
        strength = 'Fair'
        feedback.append('Consider adding more characters')
    elif score == 3:
        strength = 'Good'
        feedback.append('Good password strength')
    else:
        strength = 'Strong'
        feedback.append('Excellent password strength')
    
    return {
        'score': score,
        'strength': strength,
        'feedback': feedback
    }


def validate_vault_item_name(name):
    """
    Validate vault item name.
    
    Args:
        name (str): The item name to validate
        
    Raises:
        ValidationError: If name is invalid
    """
    if not name or not name.strip():
        raise ValidationError(_('Item name cannot be empty.'))
    
    if len(name.strip()) > 100:
        raise ValidationError(_('Item name cannot exceed 100 characters.'))
    
    # Check for potentially dangerous characters
    dangerous_chars = ['<', '>', '"', "'", '&', '\n', '\r', '\t']
    if any(char in name for char in dangerous_chars):
        raise ValidationError(
            _('Item name contains invalid characters.')
        )


def validate_hex_color(value):
    """
    Validate hex color code.
    
    Args:
        value (str): The hex color code to validate
        
    Raises:
        ValidationError: If color code is invalid
    """
    if not re.match(r'^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$', value):
        raise ValidationError(
            _('Enter a valid hex color code (e.g., #FF0000 or #F00).')
        )


def validate_json_field(value):
    """
    Validate that a value can be serialized as JSON.
    
    Args:
        value: The value to validate
        
    Raises:
        ValidationError: If value cannot be serialized as JSON
    """
    try:
        import json
        json.dumps(value)
    except (TypeError, ValueError):
        raise ValidationError(_('Value must be JSON serializable.'))


def validate_device_fingerprint(fingerprint):
    """
    Validate device fingerprint format.
    
    Args:
        fingerprint (str): The device fingerprint to validate
        
    Raises:
        ValidationError: If fingerprint is invalid
    """
    if not fingerprint or len(fingerprint) < 10:
        raise ValidationError(
            _('Device fingerprint must be at least 10 characters long.')
        )
    
    if len(fingerprint) > 500:
        raise ValidationError(
            _('Device fingerprint cannot exceed 500 characters.')
        )


def validate_backup_name(name):
    """
    Validate backup name format.
    
    Args:
        name (str): The backup name to validate
        
    Raises:
        ValidationError: If name is invalid
    """
    if not name or not name.strip():
        raise ValidationError(_('Backup name cannot be empty.'))
    
    if len(name.strip()) > 200:
        raise ValidationError(_('Backup name cannot exceed 200 characters.'))
    
    # Check for file system unsafe characters
    unsafe_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
    if any(char in name for char in unsafe_chars):
        raise ValidationError(
            _('Backup name contains invalid characters.')
        )


class PasswordValidator:
    """
    Custom password validator class for Django password validation.
    """
    
    def validate(self, password, user=None):
        """
        Validate password.
        
        Args:
            password (str): The password to validate
            user: The user object (optional)
            
        Raises:
            ValidationError: If password is invalid
        """
        validate_strong_password(password)
    
    def get_help_text(self):
        """
        Return help text for password requirements.
        
        Returns:
            str: Help text for password requirements
        """
        return _(
            f'Your password must be at least {MINIMUM_PASSWORD_LENGTH} characters long '
            'and contain at least one lowercase letter, one uppercase letter, '
            'one number, and one special character.'
        )
