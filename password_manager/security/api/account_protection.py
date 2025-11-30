from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta

from ..models import (
    SocialMediaAccount, LoginAttempt, UserDevice, 
    SecurityAlert, UserNotificationSettings, AccountLockEvent
)
from ..serializers import (
    SocialMediaAccountSerializer, LoginAttemptSerializer,
    UserDeviceSerializer, SecurityAlertSerializer,
    UserNotificationSettingsSerializer, AccountLockEventSerializer
)
from ..services.account_protection import account_protection_service
from password_manager.api_utils import error_response, success_response

class AccountProtectionViewSet(viewsets.ViewSet):
    """API endpoints for account protection and security monitoring"""
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def security_dashboard(self, request):
        """Get security dashboard data for the user"""
        try:
            user = request.user
            
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
            
            return success_response({
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
            })
            
        except Exception as e:
            return error_response(f"Failed to load security dashboard: {str(e)}")
    
    @action(detail=False, methods=['get', 'post'])
    def social_accounts(self, request):
        """Manage social media accounts"""
        if request.method == 'GET':
            accounts = SocialMediaAccount.objects.filter(user=request.user)
            serializer = SocialMediaAccountSerializer(accounts, many=True)
            return success_response({'accounts': serializer.data})
        
        elif request.method == 'POST':
            serializer = SocialMediaAccountSerializer(data=request.data)
            if serializer.is_valid():
                account = serializer.save(user=request.user)
                return success_response(
                    SocialMediaAccountSerializer(account).data,
                    message="Social media account added successfully",
                    status_code=status.HTTP_201_CREATED
                )
            return error_response(
                "Invalid account data",
                details=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['post'])
    def lock_accounts(self, request):
        """Manually lock social media accounts"""
        try:
            platform = request.data.get('platform')
            account_ids = request.data.get('account_ids', [])
            reason = request.data.get('reason', 'Manual lock by user')
            
            if platform:
                accounts = SocialMediaAccount.objects.filter(
                    user=request.user,
                    platform=platform,
                    status='active'
                )
            elif account_ids:
                accounts = SocialMediaAccount.objects.filter(
                    user=request.user,
                    id__in=account_ids,
                    status='active'
                )
            else:
                return error_response("Must specify platform or account_ids")
            
            locked_count = 0
            for account in accounts:
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
                locked_count += 1
            
            return success_response({
                'locked_count': locked_count,
                'message': f'Successfully locked {locked_count} account(s)'
            })
            
        except Exception as e:
            return error_response(f"Failed to lock accounts: {str(e)}")
    
    @action(detail=False, methods=['post'])
    def unlock_accounts(self, request):
        """Manually unlock social media accounts"""
        try:
            platform = request.data.get('platform')
            account_ids = request.data.get('account_ids', [])
            
            if platform:
                accounts = SocialMediaAccount.objects.filter(
                    user=request.user,
                    platform=platform,
                    status='locked'
                )
            elif account_ids:
                accounts = SocialMediaAccount.objects.filter(
                    user=request.user,
                    id__in=account_ids,
                    status='locked'
                )
            else:
                return error_response("Must specify platform or account_ids")
            
            unlocked_count = 0
            for account in accounts:
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
                unlocked_count += 1
            
            return success_response({
                'unlocked_count': unlocked_count,
                'message': f'Successfully unlocked {unlocked_count} account(s)'
            })
            
        except Exception as e:
            return error_response(f"Failed to unlock accounts: {str(e)}")
    
    @action(detail=False, methods=['get'])
    def login_attempts(self, request):
        """Get login attempt history"""
        try:
            days = int(request.query_params.get('days', 30))
            limit = int(request.query_params.get('limit', 50))
            
            attempts = LoginAttempt.objects.filter(
                Q(user=request.user) | Q(username_attempted=request.user.username),
                timestamp__gte=timezone.now() - timedelta(days=days)
            ).order_by('-timestamp')[:limit]
            
            return success_response({
                'attempts': LoginAttemptSerializer(attempts, many=True).data,
                'total_count': attempts.count()
            })
            
        except Exception as e:
            return error_response(f"Failed to get login attempts: {str(e)}")
    
    @action(detail=False, methods=['get'])
    def security_alerts(self, request):
        """Get security alerts"""
        try:
            include_resolved = request.query_params.get('include_resolved', 'false').lower() == 'true'
            limit = int(request.query_params.get('limit', 20))
            
            alerts = SecurityAlert.objects.filter(user=request.user)
            
            if not include_resolved:
                alerts = alerts.filter(is_resolved=False)
            
            alerts = alerts.order_by('-created_at')[:limit]
            
            return success_response({
                'alerts': SecurityAlertSerializer(alerts, many=True).data
            })
            
        except Exception as e:
            return error_response(f"Failed to get security alerts: {str(e)}")
    
    @action(detail=False, methods=['post'])
    def resolve_alert(self, request):
        """Resolve a security alert"""
        try:
            alert_id = request.data.get('alert_id')
            if not alert_id:
                return error_response("Alert ID is required")
            
            alert = get_object_or_404(SecurityAlert, id=alert_id, user=request.user)
            alert.is_resolved = True
            alert.resolved_at = timezone.now()
            alert.save()
            
            return success_response({
                'message': 'Alert resolved successfully'
            })
            
        except Exception as e:
            return error_response(f"Failed to resolve alert: {str(e)}")
    
    @action(detail=False, methods=['get', 'put'])
    def notification_settings(self, request):
        """Manage notification settings"""
        if request.method == 'GET':
            settings_obj = account_protection_service.get_user_notification_settings(request.user)
            serializer = UserNotificationSettingsSerializer(settings_obj)
            return success_response(serializer.data)
        
        elif request.method == 'PUT':
            settings_obj = account_protection_service.get_user_notification_settings(request.user)
            serializer = UserNotificationSettingsSerializer(settings_obj, data=request.data, partial=True)
            
            if serializer.is_valid():
                serializer.save()
                return success_response(
                    serializer.data,
                    message="Notification settings updated successfully"
                )
            
            return error_response(
                "Invalid settings data",
                details=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def devices(self, request):
        """Get user devices"""
        try:
            devices = UserDevice.objects.filter(user=request.user).order_by('-last_seen')
            return success_response({
                'devices': UserDeviceSerializer(devices, many=True).data
            })
            
        except Exception as e:
            return error_response(f"Failed to get devices: {str(e)}")
    
    @action(detail=False, methods=['post'])
    def trust_device(self, request):
        """Mark a device as trusted"""
        try:
            device_id = request.data.get('device_id')
            if not device_id:
                return error_response("Device ID is required")
            
            device = get_object_or_404(UserDevice, device_id=device_id, user=request.user)
            device.is_trusted = True
            device.save()
            
            return success_response({
                'message': 'Device marked as trusted'
            })
            
        except Exception as e:
            return error_response(f"Failed to trust device: {str(e)}")
    
    @action(detail=False, methods=['post'])
    def untrust_device(self, request):
        """Remove trust from a device"""
        try:
            device_id = request.data.get('device_id')
            if not device_id:
                return error_response("Device ID is required")
            
            device = get_object_or_404(UserDevice, device_id=device_id, user=request.user)
            device.is_trusted = False
            device.save()
            
            return success_response({
                'message': 'Device trust removed'
            })
            
        except Exception as e:
            return error_response(f"Failed to untrust device: {str(e)}")
    
    @action(detail=False, methods=['get'])
    def lock_events(self, request):
        """Get account lock/unlock events"""
        try:
            limit = int(request.query_params.get('limit', 20))
            
            events = AccountLockEvent.objects.filter(
                user=request.user
            ).order_by('-timestamp')[:limit]
            
            return success_response({
                'events': AccountLockEventSerializer(events, many=True).data
            })
            
        except Exception as e:
            return error_response(f"Failed to get lock events: {str(e)}")

class SocialMediaAccountViewSet(viewsets.ModelViewSet):
    """CRUD operations for social media accounts"""
    permission_classes = [IsAuthenticated]
    serializer_class = SocialMediaAccountSerializer
    
    def get_queryset(self):
        return SocialMediaAccount.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            self.perform_create(serializer)
            return success_response(
                serializer.data,
                message="Social media account created successfully",
                status_code=status.HTTP_201_CREATED
            )
        return error_response(
            "Invalid account data",
            details=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        
        if serializer.is_valid():
            self.perform_update(serializer)
            return success_response(
                serializer.data,
                message="Social media account updated successfully"
            )
        
        return error_response(
            "Invalid account data",
            details=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return success_response(
            message="Social media account deleted successfully",
            status_code=status.HTTP_204_NO_CONTENT
        ) 