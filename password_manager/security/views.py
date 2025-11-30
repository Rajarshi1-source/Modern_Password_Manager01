from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from vault.models import EncryptedVaultItem, AuditLog
import json
import re
from django.utils import timezone
from django.shortcuts import render, get_object_or_404
from rest_framework.views import APIView
from django.contrib.auth.models import User
from django.db.models import Q, Count
from datetime import timedelta
from .tasks import check_for_breaches
from .services import hibp
from .notifications import send_breach_notification
from .models import (
    SocialMediaAccount, LoginAttempt, UserDevice, 
    SecurityAlert, UserNotificationSettings, AccountLockEvent
)
from .serializers import (
    SocialMediaAccountSerializer, LoginAttemptSerializer,
    UserDeviceSerializer, SecurityAlertSerializer,
    UserNotificationSettingsSerializer, AccountLockEventSerializer
)
from password_manager.api_utils import error_response, success_response

# Create your views here.

class SecurityViewSet(viewsets.ViewSet):
    """Security-related endpoints for password health and monitoring"""
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def password_health(self, request):
        """Check password health across the vault"""
        # Get all password items
        password_items = EncryptedVaultItem.objects.filter(
            user=request.user,
            item_type='password'
        )
        
        results = {
            'total_passwords': password_items.count(),
            'weak_passwords': 0,
            'reused_passwords': 0,
            'old_passwords': 0,
            'compromised_passwords': 0,
            'health_score': 100,  # Start with perfect score
            'items': []
        }
        
        # This analysis is done client-side because data is encrypted
        # Server just returns the items for client to analyze
        
        serializer = VaultItemSerializer(password_items, many=True)
        return success_response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def check_breached(self, request):
        """
        Check if password hashes are in known data breaches
        Using k-anonymity method to protect full password hashes
        """
        if not request.data.get('hash_prefixes'):
            return error_response('No hash prefixes provided', 
                           status_code=status.HTTP_400_BAD_REQUEST)
        
        hash_prefixes = request.data.get('hash_prefixes')
        
        # In a real implementation, this would use a service like HIBP API
        # with k-anonymity to check breached passwords without sending full hashes
        # Here's a simplified version:
        
        results = {}
        for prefix in hash_prefixes:
            # Call external breach API with prefix only
            # Return suffixes of matching hashes
            results[prefix] = []  # List of matching hash suffixes if any
            
        return success_response(results)

    @action(detail=False, methods=['get'])
    def health_check(self, request):
        """
        Check password health and security across vault items
        """
        if not request.user.is_authenticated:
            return error_response('Authentication required', 
                           status_code=status.HTTP_401_UNAUTHORIZED)
        
        # Get password items for the user
        password_items = EncryptedVaultItem.objects.filter(
            user=request.user,
            item_type='password',
            deleted=False
        )
        
        # In a real implementation, we would analyze password strength,
        # age, uniqueness, etc. This is a placeholder.
        analysis = {
            'total_passwords': password_items.count(),
            'weak_passwords': 0,
            'reused_passwords': 0,
            'old_passwords': 0,
            'compromised_passwords': 0,
            'overall_score': 100  # Default score
        }
        
        return success_response(analysis)

    @action(detail=False, methods=['get'])
    def audit_log(self, request):
        """
        Get security audit logs for the user
        """
        if not request.user.is_authenticated:
            return error_response('Authentication required', 
                           status_code=status.HTTP_401_UNAUTHORIZED)
        
        # Get most recent audit logs
        logs = AuditLog.objects.filter(user=request.user).order_by('-timestamp')[:50]
        
        # Serialize the logs
        log_data = []
        for log in logs:
            log_data.append({
                'id': log.id,
                'action': log.action,
                'timestamp': log.timestamp,
                'ip_address': log.ip_address,
                'status': log.status
            })
        
        return success_response(log_data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def health_check(request):
    """
    Simple endpoint to check if security module is working
    """
    return success_response({
        'status': 'success',
        'message': 'Security module is operational',
        'timestamp': timezone.now()
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def audit_log(request):
    """
    Get security audit logs for the user
    """
    if not request.user.is_authenticated:
        return error_response('Authentication required', 
                        status_code=status.HTTP_401_UNAUTHORIZED)
    
    # Get most recent audit logs
    logs = AuditLog.objects.filter(user=request.user).order_by('-timestamp')[:50]
    
    # Serialize the logs
    log_data = []
    for log in logs:
        log_data.append({
            'id': log.id,
            'action': log.action,
            'timestamp': log.timestamp,
            'ip_address': log.ip_address,
            'status': log.status
        })
    
    return success_response(log_data)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def check_password_breach(request):
    """Check if a password has been found in a data breach.
    
    For privacy, only the first 5 characters of the SHA-1 hash of the 
    password are sent to the API, and then checked locally against
    the returned list of hash suffixes.
    """
    password_hash = request.data.get('password_hash')
    
    if not password_hash:
        return error_response('Password hash is required', status_code=status.HTTP_400_BAD_REQUEST)
        
    try:
        # This should be a SHA-1 hash of the password
        is_breached, count = hibp.is_password_breached(password_hash)
        
        return success_response({
            'is_breached': is_breached,
            'count': count
        })
    except Exception as e:
        return error_response(str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def check_email_breach(request):
    """Check if an email has been found in a data breach."""
    email = request.data.get('email')
    
    if not email:
        return error_response('Email is required', status_code=status.HTTP_400_BAD_REQUEST)
        
    try:
        breaches = hibp.get_breached_sites_for_email(email)
        
        return success_response({
            'is_breached': len(breaches) > 0,
            'breaches': breaches
        })
    except Exception as e:
        return error_response(str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def security_dashboard(request):
    """Get security dashboard data for the user with caching"""
    from django.core.cache import cache
    
    try:
        user = request.user
        cache_key = f"security_dashboard_{user.id}"
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return Response(cached_data)
        
        # Get recent login attempts
        recent_attempts = LoginAttempt.objects.filter(
            Q(user=user) | Q(username_attempted=user.username),
            timestamp__gte=timezone.now() - timedelta(days=7)
        ).order_by('-timestamp')[:10]
        
        # Get active security alerts
        active_alerts = SecurityAlert.objects.filter(
            user=user,
            is_resolved=False
        ).order_by('-created_at')[:5]
        
        # Get user devices
        devices = UserDevice.objects.filter(user=user).order_by('-last_seen')
        
        # Get social media accounts
        social_accounts = SocialMediaAccount.objects.filter(user=user)
        
        # Calculate security metrics
        failed_attempts_today = recent_attempts.filter(
            status='failed',
            timestamp__gte=timezone.now() - timedelta(days=1)
        ).count()
        
        suspicious_attempts_week = recent_attempts.filter(
            is_suspicious=True
        ).count()
        
        locked_accounts = social_accounts.filter(status='locked').count()
        
        data = {
            'security_metrics': {
                'failed_attempts_today': failed_attempts_today,
                'suspicious_attempts_week': suspicious_attempts_week,
                'locked_accounts': locked_accounts,
                'total_social_accounts': social_accounts.count(),
                'trusted_devices': devices.filter(is_trusted=True).count()
            },
            'recent_attempts': LoginAttemptSerializer(recent_attempts, many=True).data,
            'active_alerts': SecurityAlertSerializer(active_alerts, many=True).data,
            'devices': UserDeviceSerializer(devices, many=True).data,
            'social_accounts': SocialMediaAccountSerializer(social_accounts, many=True).data
        }
        
        # Cache for 5 minutes
        cache.set(cache_key, data, 300)
        
        return success_response(data)
        
    except Exception as e:
        return error_response(f"Failed to load security dashboard: {str(e)}")

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def security_score(request):
    """Calculate and return user's security score"""
    try:
        user = request.user
        
        # Base score
        score = 100
        factors = {}
        
        # Check password items count
        password_items = EncryptedVaultItem.objects.filter(
            user=user,
            item_type='password',
            deleted=False
        ).count()
        
        # Check 2FA setup (simplified check)
        has_2fa = hasattr(user, 'userprofile') and getattr(user.userprofile, 'two_factor_enabled', False)
        
        # Check recent security incidents
        recent_alerts = SecurityAlert.objects.filter(
            user=user,
            is_resolved=False,
            created_at__gte=timezone.now() - timedelta(days=30)
        ).count()
        
        # Check failed login attempts
        recent_failed_attempts = LoginAttempt.objects.filter(
            Q(user=user) | Q(username_attempted=user.username),
            status='failed',
            timestamp__gte=timezone.now() - timedelta(days=7)
        ).count()
        
        # Check trusted devices
        trusted_devices = UserDevice.objects.filter(
            user=user,
            is_trusted=True
        ).count()
        
        # Calculate score adjustments
        if password_items < 5:
            score -= 20
            factors['few_passwords'] = 'Consider adding more passwords to your vault'
        
        if not has_2fa:
            score -= 25
            factors['no_2fa'] = 'Enable two-factor authentication for better security'
        
        if recent_alerts > 0:
            score -= min(recent_alerts * 10, 30)
            factors['unresolved_alerts'] = f'{recent_alerts} unresolved security alerts'
        
        if recent_failed_attempts > 5:
            score -= 15
            factors['failed_attempts'] = f'{recent_failed_attempts} failed login attempts in the last week'
        
        if trusted_devices == 0:
            score -= 10
            factors['no_trusted_devices'] = 'No trusted devices configured'
        
        # Ensure score doesn't go below 0
        score = max(0, score)
        
        return success_response({
            'score': score,
            'grade': 'A' if score >= 90 else 'B' if score >= 75 else 'C' if score >= 60 else 'D' if score >= 40 else 'F',
            'factors': factors,
            'metrics': {
                'password_count': password_items,
                'has_2fa': has_2fa,
                'recent_alerts': recent_alerts,
                'failed_attempts': recent_failed_attempts,
                'trusted_devices': trusted_devices
            }
        })
        
    except Exception as e:
        return error_response(f"Failed to calculate security score: {str(e)}")

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def devices_list(request):
    """Get user devices"""
    try:
        devices = UserDevice.objects.filter(user=request.user).order_by('-last_seen')
        return success_response({
            'devices': UserDeviceSerializer(devices, many=True).data
        })
        
    except Exception as e:
        return error_response(f"Failed to get devices: {str(e)}")

@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def device_detail(request, device_id):
    """Manage individual device"""
    try:
        device = get_object_or_404(UserDevice, device_id=device_id, user=request.user)
        
        if request.method == 'GET':
            return success_response(UserDeviceSerializer(device).data)
        
        elif request.method == 'PATCH':
            serializer = UserDeviceSerializer(device, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return success_response(
                    serializer.data,
                    message="Device updated successfully"
                )
            return error_response(
                "Invalid device data",
                details=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        elif request.method == 'DELETE':
            device.delete()
            return success_response(
                message="Device removed successfully",
                status_code=status.HTTP_204_NO_CONTENT
            )
        
    except Exception as e:
        return error_response(f"Failed to manage device: {str(e)}")

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def device_trust(request, device_id):
    """Mark a device as trusted"""
    try:
        device = get_object_or_404(UserDevice, device_id=device_id, user=request.user)
        device.is_trusted = True
        device.save()
        
        return success_response({
            'message': 'Device marked as trusted'
        })
        
    except Exception as e:
        return error_response(f"Failed to trust device: {str(e)}")

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def device_untrust(request, device_id):
    """Remove trust from a device"""
    try:
        device = get_object_or_404(UserDevice, device_id=device_id, user=request.user)
        device.is_trusted = False
        device.save()
        
        return success_response({
            'message': 'Device trust removed'
        })
        
    except Exception as e:
        return error_response(f"Failed to untrust device: {str(e)}")

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def social_account_lock(request, account_id):
    """Lock a specific social media account"""
    try:
        account = get_object_or_404(SocialMediaAccount, id=account_id, user=request.user)
        reason = request.data.get('reason', 'Manual lock by user')
        
        # Record lock event
        AccountLockEvent.objects.create(
            user=request.user,
            social_account=account,
            action='lock',
            reason=reason,
            auto_triggered=False,
            success=True
        )
        
        account.status = 'locked'
        account.save()
        
        return success_response({
            'message': 'Account locked successfully'
        })
        
    except Exception as e:
        return error_response(f"Failed to lock account: {str(e)}")

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def social_account_unlock(request, account_id):
    """Unlock a specific social media account"""
    try:
        account = get_object_or_404(SocialMediaAccount, id=account_id, user=request.user)
        
        # Record unlock event
        AccountLockEvent.objects.create(
            user=request.user,
            social_account=account,
            action='unlock',
            reason='Manual unlock by user',
            auto_triggered=False,
            success=True
        )
        
        account.status = 'active'
        account.save()
        
        return success_response({
            'message': 'Account unlocked successfully'
        })
        
    except Exception as e:
        return error_response(f"Failed to unlock account: {str(e)}")
