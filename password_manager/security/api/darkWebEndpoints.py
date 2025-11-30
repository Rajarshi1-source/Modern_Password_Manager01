from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from vault.models import BreachAlert
from security.services.breach_monitor import HIBPService
from security.tasks import scan_user_vault
from password_manager.throttling import PasswordCheckRateThrottle, SecurityOperationThrottle

class DarkWebViewSet(viewsets.ViewSet):
    """API endpoints for dark web monitoring and breach alerts"""
    permission_classes = [IsAuthenticated]
    throttle_classes = [PasswordCheckRateThrottle]
    
    @action(detail=False, methods=['post'])
    def check_password(self, request):
        """
        Check if a password hash prefix appears in breached data
        Using k-anonymity model to protect the full hash
        """
        hash_prefix = request.data.get('hash_prefix')
        if not hash_prefix or len(hash_prefix) != 5:
            return Response(
                {'error': 'Valid hash prefix required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Call HIBP API to get hash suffixes
            response = HIBPService.check_password_prefix(hash_prefix)
            return Response(response)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def get_breaches(self, request):
        """Get all breach alerts for the current user"""
        alerts = BreachAlert.objects.filter(user=request.user)
        
        # Serialize alerts
        result = []
        for alert in alerts:
            result.append({
                'id': alert.id,
                'breach_name': alert.breach_name,
                'breach_date': alert.breach_date,
                'breach_description': alert.breach_description,
                'data_type': alert.data_type,
                'identifier': alert.identifier,
                'exposed_data': alert.exposed_data,
                'severity': alert.severity,
                'detected_at': alert.detected_at,
                'resolved': alert.resolved,
                'resolved_at': alert.resolved_at,
                'notified': alert.notified,
                'notification_sent_at': alert.notification_sent_at
            })
            
        return Response(result)
    
    @action(detail=False, methods=['post'])
    def mark_resolved(self, request):
        """Mark a breach alert as resolved"""
        alert_id = request.data.get('alert_id')
        if not alert_id:
            return Response(
                {'error': 'Alert ID required'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            alert = BreachAlert.objects.get(id=alert_id, user=request.user)
            alert.resolved = True
            alert.resolved_at = timezone.now()
            alert.save()
            
            return Response({'status': 'success'})
            
        except BreachAlert.DoesNotExist:
            return Response(
                {'error': 'Alert not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['post'])
    def scan_vault(self, request):
        """Trigger a scan of the user's vault for breached credentials"""
        # Queue the task to scan user's vault
        task = scan_user_vault.delay(request.user.id)
        
        return Response({
            'status': 'started',
            'task_id': task.id
        })
    
    @action(detail=False, methods=['get'])
    def scan_status(self, request):
        """Get the status of a vault scan task"""
        task_id = request.query_params.get('task_id')
        if not task_id:
            return Response(
                {'error': 'Task ID required'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            # Check celery task status
            task = scan_user_vault.AsyncResult(task_id)
            
            if task.state == 'PENDING':
                response = {
                    'status': 'pending',
                    'progress': 0
                }
            elif task.state == 'SUCCESS':
                response = {
                    'status': 'completed',
                    'result': task.result
                }
            elif task.state == 'FAILURE':
                response = {
                    'status': 'failed',
                    'error': str(task.result)
                }
            else:
                response = {
                    'status': task.state,
                    'progress': task.info.get('progress', 0) if task.info else 0
                }
                
            return Response(response)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
