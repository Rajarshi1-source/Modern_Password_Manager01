from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class SystemLog(models.Model):
    LOG_LEVELS = (
        ('DEBUG', 'Debug'),
        ('INFO', 'Info'),
        ('WARNING', 'Warning'),
        ('ERROR', 'Error'),
        ('CRITICAL', 'Critical'),
    )
    
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    level = models.CharField(max_length=10, choices=LOG_LEVELS, db_index=True)
    logger_name = models.CharField(max_length=100, db_index=True)
    message = models.TextField()
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    request_path = models.CharField(max_length=255, blank=True)
    request_method = models.CharField(max_length=10, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['timestamp', 'level']),
            models.Index(fields=['user', 'timestamp']),
        ]
        
    def __str__(self):
        return f"{self.timestamp} [{self.level}] {self.message[:50]}"

class RecoveryAttemptLog(models.Model):
    """
    Privacy-preserving log for account recovery attempts
    No personal data stored except for a reference to the user
    """
    ATTEMPT_TYPES = (
        ('validate_key', 'Validate Recovery Key'),
        ('get_vault', 'Get Encrypted Vault'),
        ('reset_password', 'Reset Password'),
        ('recovery_success', 'Recovery Success'),
    )
    
    ATTEMPT_RESULTS = (
        ('success', 'Success'),
        ('failure', 'Failure'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    attempt_type = models.CharField(max_length=20, choices=ATTEMPT_TYPES)
    result = models.CharField(max_length=10, choices=ATTEMPT_RESULTS)
    
    # Anonymized location data (country/region only)
    country_code = models.CharField(max_length=2, blank=True, null=True)
    region = models.CharField(max_length=2, blank=True, null=True)
    
    # Store only the browser family and OS family, not the specifics
    browser_family = models.CharField(max_length=20, blank=True, null=True)
    os_family = models.CharField(max_length=20, blank=True, null=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['timestamp']),
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['attempt_type', 'result']),
        ]
        
    def __str__(self):
        return f"{self.timestamp} - {self.attempt_type} ({self.result})"
    
    @classmethod
    def log_attempt(cls, user, attempt_type, result, request=None):
        """
        Log a recovery attempt with minimal data collection
        """
        # Create basic log entry
        log_entry = cls(
            user=user,
            attempt_type=attempt_type,
            result=result
        )
        
        # Add anonymous browser/OS data if request is available
        if request and request.META.get('HTTP_USER_AGENT'):
            from user_agents import parse
            ua_string = request.META.get('HTTP_USER_AGENT', '')
            
            try:
                user_agent = parse(ua_string)
                log_entry.browser_family = user_agent.browser.family
                log_entry.os_family = user_agent.os.family
            except:
                # Fail silently if parsing fails
                pass
            
        # Get country information if available
        if request and request.META.get('REMOTE_ADDR'):
            from django.contrib.gis.geoip2 import GeoIP2
            try:
                g = GeoIP2()
                ip = request.META.get('REMOTE_ADDR')
                if ip and ip != '127.0.0.1':
                    geo_data = g.city(ip)
                    if geo_data:
                        log_entry.country_code = geo_data.get('country_code')
                        log_entry.region = geo_data.get('region')
            except:
                # Fail silently if GeoIP lookup fails
                pass
        
        log_entry.save()
        return log_entry
