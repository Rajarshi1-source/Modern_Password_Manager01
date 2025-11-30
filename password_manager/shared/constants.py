"""
Constants used throughout the Password Manager application.

This module contains application-wide constants, configuration values,
and enumerations that are shared across multiple apps.
"""

# Security constants
MINIMUM_PASSWORD_LENGTH = 8
MAXIMUM_PASSWORD_LENGTH = 128
PBKDF2_ITERATIONS = 100000
ARGON2_TIME_COST = 3
ARGON2_MEMORY_COST = 65536
ARGON2_PARALLELISM = 1

# Vault item types
VAULT_ITEM_TYPES = {
    'PASSWORD': 'password',
    'CARD': 'card', 
    'IDENTITY': 'identity',
    'NOTE': 'note',
}

# Security alert types
SECURITY_ALERT_TYPES = {
    'UNAUTHORIZED_LOGIN': 'unauthorized_login',
    'ACCOUNT_LOCKED': 'account_locked', 
    'SUSPICIOUS_ACTIVITY': 'suspicious_activity',
    'NEW_DEVICE': 'new_device',
    'LOCATION_ANOMALY': 'location_anomaly',
    'MULTIPLE_FAILURES': 'multiple_failures',
    'DATA_BREACH': 'data_breach',
}

# Security alert severities
SECURITY_ALERT_SEVERITIES = {
    'LOW': 'low',
    'MEDIUM': 'medium',
    'HIGH': 'high',
    'CRITICAL': 'critical',
}

# Two-factor authentication types
TWO_FACTOR_TYPES = {
    'TOTP': 'totp',
    'AUTHY': 'authy',
    'PUSH': 'push',
    'SMS': 'sms',
    'EMAIL': 'email',
}

# Login attempt statuses
LOGIN_ATTEMPT_STATUSES = {
    'SUCCESS': 'success',
    'FAILED': 'failed',
    'BLOCKED': 'blocked',
    'SUSPICIOUS': 'suspicious',
}

# Social media platforms
SOCIAL_MEDIA_PLATFORMS = {
    'FACEBOOK': 'facebook',
    'TWITTER': 'twitter',
    'INSTAGRAM': 'instagram',
    'LINKEDIN': 'linkedin',
    'GITHUB': 'github',
    'GOOGLE': 'google',
    'MICROSOFT': 'microsoft',
    'APPLE': 'apple',
}

# Social account statuses
SOCIAL_ACCOUNT_STATUSES = {
    'ACTIVE': 'active',
    'LOCKED': 'locked',
    'SUSPENDED': 'suspended',
    'MONITORING': 'monitoring',
}

# Notification channels
NOTIFICATION_CHANNELS = {
    'EMAIL': 'email',
    'SMS': 'sms',
    'PUSH': 'push',
    'IN_APP': 'in_app',
}

# Notification types
NOTIFICATION_TYPES = {
    'LOGIN_ALERT': 'login_alert',
    'DEVICE_ALERT': 'device_alert',
    'LOCATION_ALERT': 'location_alert',
    'SECURITY_ALERT': 'security_alert',
    'BREACH_ALERT': 'breach_alert',
}

# Password strength levels
PASSWORD_STRENGTH_LEVELS = {
    'VERY_WEAK': 0,
    'WEAK': 1,
    'FAIR': 2,
    'GOOD': 3,
    'STRONG': 4,
}

# Throttling scopes and rates
THROTTLE_SCOPES = {
    'AUTH': 'auth',
    'PASSWORD_CHECK': 'password_check',
    'SECURITY': 'security',
    'PASSKEY': 'passkey',
    'VAULT': 'vault',
}

# Default throttle rates (requests per time period)
DEFAULT_THROTTLE_RATES = {
    'ANON': '20/minute',
    'USER': '100/minute',
    'AUTH': '5/minute',
    'PASSWORD_CHECK': '10/hour',
    'SECURITY': '20/hour',
    'PASSKEY': '10/minute',
    'VAULT': '200/hour',
}

# Cache timeouts (in seconds)
CACHE_TIMEOUTS = {
    'SHORT': 300,      # 5 minutes
    'MEDIUM': 1800,    # 30 minutes
    'LONG': 3600,      # 1 hour
    'VERY_LONG': 86400, # 24 hours
}

# File size limits (in bytes)
FILE_SIZE_LIMITS = {
    'AVATAR': 2 * 1024 * 1024,     # 2MB
    'BACKUP': 100 * 1024 * 1024,   # 100MB
    'IMPORT': 50 * 1024 * 1024,    # 50MB
}

# Regular expressions for validation
REGEX_PATTERNS = {
    'EMAIL': r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
    'PHONE': r'^\+?1?\d{9,15}$',
    'USERNAME': r'^[a-zA-Z0-9_-]{3,30}$',
    'STRONG_PASSWORD': r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$',
}

# API response codes
API_RESPONSE_CODES = {
    'SUCCESS': 'success',
    'ERROR': 'error',
    'VALIDATION_ERROR': 'validation_error',
    'AUTHENTICATION_ERROR': 'authentication_error',
    'AUTHORIZATION_ERROR': 'authorization_error',
    'NOT_FOUND': 'not_found',
    'RATE_LIMITED': 'rate_limited',
    'SERVER_ERROR': 'server_error',
}

# Device types
DEVICE_TYPES = {
    'DESKTOP': 'desktop',
    'MOBILE': 'mobile',
    'TABLET': 'tablet',
    'UNKNOWN': 'unknown',
}

# Encryption algorithms
ENCRYPTION_ALGORITHMS = {
    'AES_256_GCM': 'aes-256-gcm',
    'CHACHA20_POLY1305': 'chacha20-poly1305',
    'AES_256_CBC': 'aes-256-cbc',
}

# Hash algorithms
HASH_ALGORITHMS = {
    'SHA256': 'sha256',
    'SHA512': 'sha512',
    'BLAKE2B': 'blake2b',
    'ARGON2': 'argon2',
    'PBKDF2': 'pbkdf2',
}
