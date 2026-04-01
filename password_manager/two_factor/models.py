"""
Two-Factor Authentication Models

Provides TOTP (Time-based One-Time Password) device management
for traditional 2FA alongside biometric MFA.
"""

import time
import hmac
import hashlib
import struct
import base64
import os

from django.db import models
from django.conf import settings
from django.utils import timezone


class TOTPDevice(models.Model):
    """
    TOTP (Time-based One-Time Password) device for 2FA.
    
    Implements RFC 6238 TOTP for traditional two-factor authentication.
    Each user can have multiple TOTP devices (e.g., authenticator apps).
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='totp_devices'
    )
    
    # Device identification
    name = models.CharField(
        max_length=100,
        default='Authenticator',
        help_text='User-friendly device name (e.g., "Google Authenticator")'
    )
    
    # TOTP secret key (base32 encoded, 160 bits)
    key = models.CharField(
        max_length=80,
        help_text='Base32-encoded TOTP secret key'
    )
    
    # TOTP parameters (RFC 6238 defaults)
    digits = models.PositiveSmallIntegerField(
        default=6,
        help_text='Number of digits in the OTP (6 or 8)'
    )
    step = models.PositiveIntegerField(
        default=30,
        help_text='Time step in seconds'
    )
    t0 = models.PositiveIntegerField(
        default=0,
        help_text='Unix time start (usually 0)'
    )
    
    # Drift tolerance (number of time steps to allow for clock skew)
    tolerance = models.PositiveSmallIntegerField(
        default=1,
        help_text='Number of time steps to tolerate for clock skew'
    )
    
    # Last used counter (for replay protection)
    last_t = models.BigIntegerField(
        default=-1,
        help_text='Last successfully verified time step (replay protection)'
    )
    
    # Status
    confirmed = models.BooleanField(
        default=False,
        help_text='Whether the device has been confirmed by verifying a token'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'TOTP Device'
        verbose_name_plural = 'TOTP Devices'
        indexes = [
            models.Index(fields=['user', 'confirmed']),
        ]
    
    def __str__(self):
        status = 'confirmed' if self.confirmed else 'unconfirmed'
        return f'{self.name} ({status}) for {self.user}'
    
    @classmethod
    def generate_key(cls):
        """Generate a random base32-encoded TOTP secret key (160 bits / 20 bytes)."""
        random_bytes = os.urandom(20)
        return base64.b32encode(random_bytes).decode('utf-8')
    
    def _get_raw_key(self):
        """Decode the base32 key to raw bytes."""
        return base64.b32decode(self.key)
    
    def _generate_otp(self, t):
        """
        Generate a TOTP value for a given time step using HMAC-SHA1.
        Implements RFC 4226 (HOTP) with time-based counter.
        """
        raw_key = self._get_raw_key()
        # Pack counter as 8-byte big-endian
        msg = struct.pack('>Q', t)
        # HMAC-SHA1
        digest = hmac.new(raw_key, msg, hashlib.sha1).digest()
        # Dynamic truncation
        offset = digest[-1] & 0x0F
        code = struct.unpack('>I', digest[offset:offset + 4])[0]
        code &= 0x7FFFFFFF
        code %= 10 ** self.digits
        return code
    
    def _time_step(self, timestamp=None):
        """Calculate the current time step."""
        if timestamp is None:
            timestamp = time.time()
        return int((timestamp - self.t0) / self.step)
    
    def generate_token(self):
        """Generate the current TOTP token."""
        t = self._time_step()
        return str(self._generate_otp(t)).zfill(self.digits)
    
    def verify_token(self, token, tolerance=None):
        """
        Verify a TOTP token with drift tolerance.
        
        Args:
            token: The OTP string to verify.
            tolerance: Number of time steps to check before/after current.
                       Defaults to self.tolerance.
        
        Returns:
            bool: True if the token is valid.
        """
        if tolerance is None:
            tolerance = self.tolerance
        
        try:
            token_int = int(token)
        except (ValueError, TypeError):
            return False
        
        t_now = self._time_step()
        
        for offset in range(-tolerance, tolerance + 1):
            t = t_now + offset
            # Replay protection: reject already-used time steps
            if t <= self.last_t:
                continue
            if self._generate_otp(t) == token_int:
                # Update last used counter and timestamp
                self.last_t = t
                self.last_used_at = timezone.now()
                self.save(update_fields=['last_t', 'last_used_at'])
                return True
        
        return False
    
    def get_provisioning_uri(self, issuer='SecureVault'):
        """
        Generate an otpauth:// URI for QR code provisioning.
        
        Args:
            issuer: The service name shown in authenticator apps.
        
        Returns:
            str: otpauth://totp/ URI
        """
        from urllib.parse import quote
        
        label = quote(f'{issuer}:{self.user.email}')
        params = (
            f'secret={self.key}'
            f'&issuer={quote(issuer)}'
            f'&algorithm=SHA1'
            f'&digits={self.digits}'
            f'&period={self.step}'
        )
        return f'otpauth://totp/{label}?{params}'
