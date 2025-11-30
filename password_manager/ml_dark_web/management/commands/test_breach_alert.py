"""
Management command to test breach alert WebSocket functionality
"""

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.utils import timezone
import json

User = get_user_model()


class Command(BaseCommand):
    help = 'Send test breach alert to user via WebSocket'

    def add_arguments(self, parser):
        parser.add_argument(
            'user_id',
            type=int,
            help='User ID to send test alert to'
        )
        parser.add_argument(
            '--severity',
            type=str,
            default='HIGH',
            choices=['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'],
            help='Severity level of test alert'
        )
        parser.add_argument(
            '--confidence',
            type=float,
            default=0.95,
            help='Confidence score (0.0 to 1.0)'
        )

    def handle(self, *args, **options):
        user_id = options['user_id']
        severity = options['severity']
        confidence = options['confidence']
        
        # Validate user exists
        try:
            user = User.objects.get(id=user_id)
            self.stdout.write(f"Sending test alert to user: {user.username} (ID: {user_id})")
        except User.DoesNotExist:
            raise CommandError(f"User with ID {user_id} does not exist")
        
        # Get channel layer
        channel_layer = get_channel_layer()
        
        if not channel_layer:
            raise CommandError("Channel layer not configured. Please check CHANNEL_LAYERS in settings.py")
        
        # Prepare test message
        test_message = {
            'breach_id': f'TEST_BREACH_{timezone.now().strftime("%Y%m%d%H%M%S")}',
            'title': 'Test Security Breach Alert',
            'description': 'This is a test breach alert sent via management command.',
            'severity': severity,
            'confidence': confidence,
            'detected_at': timezone.now().isoformat(),
            'alert_id': 99999,
            'domain': 'example.com'
        }
        
        self.stdout.write(f"\nTest Alert Details:")
        self.stdout.write(f"  - Breach ID: {test_message['breach_id']}")
        self.stdout.write(f"  - Severity: {severity}")
        self.stdout.write(f"  - Confidence: {confidence * 100}%")
        self.stdout.write(f"  - Timestamp: {test_message['detected_at']}")
        
        # Send to user's WebSocket group
        try:
            async_to_sync(channel_layer.group_send)(
                f"user_{user_id}",
                {
                    'type': 'breach_alert',
                    'message': test_message
                }
            )
            
            self.stdout.write(
                self.style.SUCCESS(f'\n✓ Test alert successfully sent to user {user_id}')
            )
            self.stdout.write(
                self.style.WARNING('\nNote: User must be connected to WebSocket to receive the alert.')
            )
            
        except Exception as e:
            raise CommandError(f"Failed to send test alert: {str(e)}")

