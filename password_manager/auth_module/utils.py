import pyotp
import base64
import os
import string
import random
from datetime import datetime, timedelta
from django.utils import timezone
from .models import PushAuth
from .services.authy_service import authy_service

def generate_totp_secret():
    """Generate a random secret for TOTP"""
    return pyotp.random_base32()

def verify_totp_code(secret, code):
    """Verify a TOTP code against a secret"""
    totp = pyotp.TOTP(secret)
    return totp.verify(code)

def generate_backup_codes(count=8):
    """Generate backup codes for 2FA recovery"""
    codes = []
    for _ in range(count):
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
        # Format as XXXX-XXXX-XX
        formatted_code = f"{code[:4]}-{code[4:8]}-{code[8:]}"
        codes.append(formatted_code)
    return codes

def initiate_push_auth(user, request):
    """
    Initiate a push authentication request
    
    Args:
        user: User object
        request: HTTP request object
        
    Returns:
        PushAuth object if successful, None otherwise
    """
    try:
        from .models import TwoFactorAuth, PushAuth
        
        # Get user's 2FA settings
        tfa = TwoFactorAuth.objects.get(user=user)
        
        if not tfa.is_enabled or tfa.mfa_type != 'push':
            return None
            
        # Extract request info
        ip_address = get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        # Create message for push notification
        message = f"Login request from {ip_address}"
        
        # Send push request via Authy
        if tfa.authy_id:
            uuid = authy_service.send_approval_request(
                tfa.authy_id,
                message
            )
            
            if uuid:
                # Create PushAuth record
                push_auth = PushAuth.objects.create(
                    user=user,
                    request_id=generate_request_id(),
                    authy_uuid=uuid,
                    status='pending',
                    expires_at=timezone.now() + timedelta(minutes=2),
                    ip_address=ip_address,
                    user_agent=user_agent
                )
                
                return push_auth
        
        # If Authy push fails or no Authy ID, try direct push to device
        device, device_type = tfa.get_device_for_push()
        
        if device:
            # Create PushAuth record first
            push_auth = PushAuth.objects.create(
                user=user,
                request_id=generate_request_id(),
                status='pending',
                expires_at=timezone.now() + timedelta(minutes=2),
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            # Send push notification
            if device_type == 'apns':
                device.send_message(
                    message={"title": "Authentication Request", "body": message},
                    extra={"request_id": push_auth.request_id}
                )
            else:  # gcm
                device.send_message(
                    message,
                    extra={"request_id": push_auth.request_id}
                )
                
            return push_auth
            
        return None
        
    except Exception as e:
        print(f"Error initiating push auth: {str(e)}")
        return None

def check_push_auth_status(request_id):
    """
    Check the status of a push authentication request
    
    Args:
        request_id: ID of the push request
        
    Returns:
        str: Status of the request
    """
    try:
        push_auth = PushAuth.objects.get(request_id=request_id)
        
        # If already decided, return status
        if push_auth.status != 'pending':
            return push_auth.status
            
        # Check if expired
        if not push_auth.is_valid():
            push_auth.status = 'expired'
            push_auth.save()
            return 'expired'
            
        # If using Authy, check with Authy service
        if push_auth.authy_uuid:
            status = authy_service.check_approval_status(push_auth.authy_uuid)
            
            if status:
                push_auth.status = status
                push_auth.save()
                return status
        
        # Return current status
        return push_auth.status
        
    except PushAuth.DoesNotExist:
        return 'error'
    except Exception as e:
        print(f"Error checking push auth status: {str(e)}")
        return 'error'

def generate_request_id():
    """Generate a unique request ID for push auth"""
    import uuid
    return str(uuid.uuid4())

def get_client_ip(request):
    """Extract client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def constant_time_compare(a, b):
    """Compare two strings in constant time to prevent timing attacks"""
    from hmac import compare_digest
    return compare_digest(a, b)
