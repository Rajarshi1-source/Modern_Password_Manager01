"""
Honeypot Email Breach Detection Tests
======================================

Comprehensive test suite for the honeypot email breach detection feature.
Covers models, services, API endpoints, and task execution.

@author Password Manager Team
@created 2026-02-01
"""

import json
import uuid
from datetime import timedelta
from unittest.mock import Mock, patch, MagicMock

from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status

from security.models import (
    HoneypotConfiguration,
    HoneypotEmail,
    HoneypotActivity,
    HoneypotBreachEvent,
    CredentialRotationLog,
)
from security.services.honeypot_service import HoneypotEmailService, get_honeypot_service
from security.services.honeypot_email_provider import (
    HoneypotEmailProvider,
    SimpleLoginProvider,
    AnonAddyProvider,
    CustomSMTPProvider,
)

User = get_user_model()


# =============================================================================
# Model Tests
# =============================================================================

class HoneypotConfigurationModelTests(TestCase):
    """Tests for HoneypotConfiguration model."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_create_configuration(self):
        """Test creating a honeypot configuration."""
        config = HoneypotConfiguration.objects.create(
            user=self.user,
            email_provider='simplelogin',
            auto_rotate_on_breach=False,
            require_confirmation=True
        )
        
        self.assertEqual(config.user, self.user)
        self.assertTrue(config.is_enabled)
        self.assertEqual(config.email_provider, 'simplelogin')
        self.assertFalse(config.auto_rotate_on_breach)
        self.assertTrue(config.require_confirmation)
    
    def test_honeypot_count_property(self):
        """Test honeypot_count property."""
        config = HoneypotConfiguration.objects.create(user=self.user)
        
        # Initially zero
        self.assertEqual(config.honeypot_count, 0)
        
        # Create some honeypots
        HoneypotEmail.objects.create(
            user=self.user,
            honeypot_address='hp1@test.com',
            service_name='Service 1',
            is_active=True
        )
        HoneypotEmail.objects.create(
            user=self.user,
            honeypot_address='hp2@test.com',
            service_name='Service 2',
            is_active=True
        )
        
        self.assertEqual(config.honeypot_count, 2)
    
    def test_can_create_honeypot_limit(self):
        """Test honeypot creation limit check."""
        config = HoneypotConfiguration.objects.create(
            user=self.user,
            max_honeypots=2
        )
        
        self.assertTrue(config.can_create_honeypot)
        
        # Create up to limit
        HoneypotEmail.objects.create(
            user=self.user,
            honeypot_address='hp1@test.com',
            service_name='Service 1'
        )
        HoneypotEmail.objects.create(
            user=self.user,
            honeypot_address='hp2@test.com',
            service_name='Service 2'
        )
        
        self.assertFalse(config.can_create_honeypot)


class HoneypotEmailModelTests(TestCase):
    """Tests for HoneypotEmail model."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_create_honeypot(self):
        """Test creating a honeypot email."""
        honeypot = HoneypotEmail.objects.create(
            user=self.user,
            honeypot_address='canary-abc123@sl.io',
            provider_alias_id='alias_123',
            service_name='Example Service',
            service_domain='example.com'
        )
        
        self.assertEqual(honeypot.status, 'active')
        self.assertTrue(honeypot.is_active)
        self.assertFalse(honeypot.breach_detected)
        self.assertEqual(honeypot.total_emails_received, 0)
    
    def test_record_activity(self):
        """Test recording activity on honeypot."""
        honeypot = HoneypotEmail.objects.create(
            user=self.user,
            honeypot_address='canary@sl.io',
            service_name='Test Service'
        )
        
        # Record activity
        honeypot.record_activity(is_spam=False)
        
        self.assertEqual(honeypot.total_emails_received, 1)
        self.assertEqual(honeypot.spam_emails_received, 0)
        self.assertIsNotNone(honeypot.first_activity_at)
        self.assertIsNotNone(honeypot.last_activity_at)
        self.assertEqual(honeypot.status, 'triggered')
        
        # Record spam
        honeypot.record_activity(is_spam=True)
        
        self.assertEqual(honeypot.total_emails_received, 2)
        self.assertEqual(honeypot.spam_emails_received, 1)
    
    def test_confirm_breach(self):
        """Test confirming a breach."""
        honeypot = HoneypotEmail.objects.create(
            user=self.user,
            honeypot_address='canary@sl.io',
            service_name='Breached Service'
        )
        
        honeypot.confirm_breach(confidence=0.95)
        
        self.assertTrue(honeypot.breach_detected)
        self.assertIsNotNone(honeypot.breach_detected_at)
        self.assertEqual(honeypot.breach_confidence, 0.95)
        self.assertEqual(honeypot.status, 'breached')
    
    def test_days_active(self):
        """Test days_active property."""
        honeypot = HoneypotEmail.objects.create(
            user=self.user,
            honeypot_address='canary@sl.io',
            service_name='Test Service'
        )
        
        # Just created, should be 0 days
        self.assertEqual(honeypot.days_active, 0)
    
    def test_is_expired(self):
        """Test expiration check."""
        honeypot = HoneypotEmail.objects.create(
            user=self.user,
            honeypot_address='canary@sl.io',
            service_name='Test Service',
            expires_at=timezone.now() - timedelta(days=1)
        )
        
        self.assertTrue(honeypot.is_expired)
        
        honeypot.expires_at = timezone.now() + timedelta(days=1)
        self.assertFalse(honeypot.is_expired)


class HoneypotActivityModelTests(TestCase):
    """Tests for HoneypotActivity model."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.honeypot = HoneypotEmail.objects.create(
            user=self.user,
            honeypot_address='canary@sl.io',
            service_name='Test Service'
        )
    
    def test_create_activity(self):
        """Test creating an activity record."""
        activity = HoneypotActivity.objects.create(
            honeypot=self.honeypot,
            activity_type='email_received',
            sender_address='spam@attacker.com',
            sender_domain='attacker.com',
            subject_hash=HoneypotActivity.hash_subject('You won $1M!!!'),
            subject_preview='You won $1M!!!',
            is_spam=True,
            spam_score=0.95
        )
        
        self.assertEqual(activity.honeypot, self.honeypot)
        self.assertTrue(activity.is_spam)
        self.assertEqual(len(activity.subject_hash), 64)  # SHA-256 length
    
    def test_hash_subject(self):
        """Test subject hashing."""
        subject = "Test Subject"
        hash1 = HoneypotActivity.hash_subject(subject)
        hash2 = HoneypotActivity.hash_subject(subject)
        
        # Same input should produce same hash
        self.assertEqual(hash1, hash2)
        
        # Different input should produce different hash
        hash3 = HoneypotActivity.hash_subject("Different Subject")
        self.assertNotEqual(hash1, hash3)
    
    def test_analyze_for_breach(self):
        """Test breach analysis."""
        activity = HoneypotActivity.objects.create(
            honeypot=self.honeypot,
            activity_type='spam_detected',
            sender_domain='attacker.com',
            is_spam=True,
            spam_score=0.9
        )
        
        indicators = activity.analyze_for_breach()
        
        self.assertTrue(activity.is_breach_indicator)
        self.assertIn('spam_from_unknown', indicators)


class HoneypotBreachEventModelTests(TestCase):
    """Tests for HoneypotBreachEvent model."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.honeypot = HoneypotEmail.objects.create(
            user=self.user,
            honeypot_address='canary@sl.io',
            service_name='Breached Service'
        )
    
    def test_create_breach_event(self):
        """Test creating a breach event."""
        breach = HoneypotBreachEvent.objects.create(
            user=self.user,
            honeypot=self.honeypot,
            service_name='Breached Service',
            severity='high',
            confidence_score=0.95
        )
        
        self.assertEqual(breach.status, 'detected')
        self.assertFalse(breach.credentials_rotated)
    
    def test_timeline_property(self):
        """Test breach timeline generation."""
        breach = HoneypotBreachEvent.objects.create(
            user=self.user,
            honeypot=self.honeypot,
            service_name='Test Service',
            first_activity_at=timezone.now() - timedelta(hours=2),
            detected_at=timezone.now() - timedelta(hours=1),
            notification_sent_at=timezone.now() - timedelta(minutes=30)
        )
        
        timeline = breach.timeline
        
        self.assertIsInstance(timeline, list)
        self.assertTrue(len(timeline) >= 2)
        
        events = [e['event'] for e in timeline]
        self.assertIn('detected', events)
        self.assertIn('first_activity', events)
    
    def test_days_before_public(self):
        """Test days_before_public calculation."""
        breach = HoneypotBreachEvent.objects.create(
            user=self.user,
            honeypot=self.honeypot,
            service_name='Test Service',
            detected_at=timezone.now() - timedelta(days=10),
            public_disclosure_at=timezone.now()
        )
        
        self.assertEqual(breach.days_before_public, 10)


class CredentialRotationLogModelTests(TestCase):
    """Tests for CredentialRotationLog model."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.honeypot = HoneypotEmail.objects.create(
            user=self.user,
            honeypot_address='canary@sl.io',
            service_name='Test Service'
        )
    
    def test_create_rotation_log(self):
        """Test creating a rotation log."""
        rotation = CredentialRotationLog.objects.create(
            user=self.user,
            honeypot=self.honeypot,
            service_name='Test Service',
            trigger='auto_breach'
        )
        
        self.assertEqual(rotation.status, 'pending')
        self.assertFalse(rotation.success)
    
    def test_mark_completed(self):
        """Test marking rotation as completed."""
        rotation = CredentialRotationLog.objects.create(
            user=self.user,
            honeypot=self.honeypot,
            service_name='Test Service'
        )
        
        rotation.mark_completed(success=True)
        
        self.assertEqual(rotation.status, 'completed')
        self.assertTrue(rotation.success)
        self.assertIsNotNone(rotation.completed_at)
    
    def test_mark_failed(self):
        """Test marking rotation as failed."""
        rotation = CredentialRotationLog.objects.create(
            user=self.user,
            honeypot=self.honeypot,
            service_name='Test Service'
        )
        
        rotation.mark_completed(success=False, error_message='Service unavailable')
        
        self.assertEqual(rotation.status, 'failed')
        self.assertFalse(rotation.success)
        self.assertEqual(rotation.error_message, 'Service unavailable')


# =============================================================================
# Service Tests
# =============================================================================

class HoneypotEmailServiceTests(TestCase):
    """Tests for HoneypotEmailService."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.service = HoneypotEmailService()
    
    def test_get_or_create_config(self):
        """Test getting or creating configuration."""
        config = self.service.get_or_create_config(self.user)
        
        self.assertIsInstance(config, HoneypotConfiguration)
        self.assertEqual(config.user, self.user)
        
        # Second call should return same config
        config2 = self.service.get_or_create_config(self.user)
        self.assertEqual(config.id, config2.id)
    
    def test_update_config(self):
        """Test updating configuration."""
        config = self.service.update_config(
            self.user,
            auto_rotate_on_breach=True,
            max_honeypots=100
        )
        
        self.assertTrue(config.auto_rotate_on_breach)
        self.assertEqual(config.max_honeypots, 100)
    
    @patch.object(HoneypotEmailProvider, 'create_honeypot_alias')
    def test_create_honeypot(self, mock_create_alias):
        """Test creating a honeypot."""
        mock_create_alias.return_value = ('canary-test@sl.io', 'alias_123')
        
        honeypot = self.service.create_honeypot(
            user=self.user,
            service_name='Test Service',
            service_domain='test.com',
            notes='Test notes'
        )
        
        self.assertEqual(honeypot.service_name, 'Test Service')
        self.assertEqual(honeypot.honeypot_address, 'canary-test@sl.io')
        self.assertEqual(honeypot.provider_alias_id, 'alias_123')
        self.assertEqual(honeypot.notes, 'Test notes')
        self.assertEqual(honeypot.status, 'active')
    
    @patch.object(HoneypotEmailProvider, 'create_honeypot_alias')
    def test_create_honeypot_limit_reached(self, mock_create_alias):
        """Test honeypot creation fails when limit reached."""
        # Set low limit
        self.service.update_config(self.user, max_honeypots=1)
        
        mock_create_alias.return_value = ('canary-1@sl.io', 'alias_1')
        
        # First one succeeds
        self.service.create_honeypot(
            user=self.user,
            service_name='Service 1'
        )
        
        # Second one should fail
        with self.assertRaises(ValueError) as context:
            self.service.create_honeypot(
                user=self.user,
                service_name='Service 2'
            )
        
        self.assertIn('limit reached', str(context.exception))
    
    def test_get_user_honeypots(self):
        """Test getting user's honeypots."""
        HoneypotEmail.objects.create(
            user=self.user,
            honeypot_address='hp1@sl.io',
            service_name='Service 1',
            status='active'
        )
        HoneypotEmail.objects.create(
            user=self.user,
            honeypot_address='hp2@sl.io',
            service_name='Service 2',
            status='breached'
        )
        
        # All honeypots
        all_honeypots = self.service.get_user_honeypots(self.user)
        self.assertEqual(len(all_honeypots), 2)
        
        # Filter by status
        active_only = self.service.get_user_honeypots(self.user, status='active')
        self.assertEqual(len(active_only), 1)
        self.assertEqual(active_only[0].service_name, 'Service 1')
    
    @patch.object(HoneypotEmailProvider, 'delete_honeypot_alias')
    def test_delete_honeypot(self, mock_delete_alias):
        """Test deleting a honeypot."""
        mock_delete_alias.return_value = True
        
        honeypot = HoneypotEmail.objects.create(
            user=self.user,
            honeypot_address='hp@sl.io',
            service_name='Test Service',
            provider_alias_id='alias_123'
        )
        
        result = self.service.delete_honeypot(honeypot)
        
        self.assertTrue(result)
        honeypot.refresh_from_db()
        self.assertFalse(honeypot.is_active)
        self.assertEqual(honeypot.status, 'disabled')
    
    def test_process_incoming_email(self):
        """Test processing incoming email."""
        honeypot = HoneypotEmail.objects.create(
            user=self.user,
            honeypot_address='canary@sl.io',
            service_name='Test Service'
        )
        
        with patch.object(self.service, '_send_activity_notification'):
            with patch.object(self.service, '_send_breach_notification'):
                activity, breach = self.service.process_incoming_email(
                    honeypot_address='canary@sl.io',
                    sender_address='spam@attacker.com',
                    subject='You won!!!',
                    is_spam=True,
                    spam_score=0.95
                )
        
        self.assertIsNotNone(activity)
        self.assertEqual(activity.honeypot, honeypot)
        self.assertTrue(activity.is_spam)
        self.assertTrue(breach)  # Spam should trigger breach
    
    def test_process_email_unknown_honeypot(self):
        """Test processing email for unknown honeypot."""
        result = self.service.process_incoming_email(
            honeypot_address='unknown@sl.io',
            sender_address='test@test.com',
            subject='Test'
        )
        
        self.assertEqual(result, (None, False))
    
    def test_get_breach_timeline(self):
        """Test getting breach timeline."""
        honeypot = HoneypotEmail.objects.create(
            user=self.user,
            honeypot_address='canary@sl.io',
            service_name='Test Service'
        )
        breach = HoneypotBreachEvent.objects.create(
            user=self.user,
            honeypot=honeypot,
            service_name='Test Service',
            severity='high'
        )
        
        timeline = self.service.get_breach_timeline(str(breach.id), self.user)
        
        self.assertIsNotNone(timeline)
        self.assertEqual(timeline['service_name'], 'Test Service')
        self.assertIn('timeline', timeline)
    
    def test_initiate_credential_rotation(self):
        """Test initiating credential rotation."""
        honeypot = HoneypotEmail.objects.create(
            user=self.user,
            honeypot_address='canary@sl.io',
            service_name='Test Service'
        )
        breach = HoneypotBreachEvent.objects.create(
            user=self.user,
            honeypot=honeypot,
            service_name='Test Service'
        )
        
        rotation = self.service.initiate_credential_rotation(breach)
        
        self.assertIsInstance(rotation, CredentialRotationLog)
        self.assertEqual(rotation.service_name, 'Test Service')
        self.assertEqual(rotation.status, 'pending')
    
    def test_confirm_credential_rotation(self):
        """Test confirming credential rotation."""
        honeypot = HoneypotEmail.objects.create(
            user=self.user,
            honeypot_address='canary@sl.io',
            service_name='Test Service'
        )
        breach = HoneypotBreachEvent.objects.create(
            user=self.user,
            honeypot=honeypot,
            service_name='Test Service'
        )
        rotation = CredentialRotationLog.objects.create(
            user=self.user,
            honeypot=honeypot,
            breach_event=breach,
            service_name='Test Service'
        )
        
        result = self.service.confirm_credential_rotation(rotation)
        
        self.assertTrue(result)
        rotation.refresh_from_db()
        breach.refresh_from_db()
        
        self.assertEqual(rotation.status, 'completed')
        self.assertTrue(rotation.success)
        self.assertTrue(breach.credentials_rotated)


# =============================================================================
# Provider Tests
# =============================================================================

class HoneypotEmailProviderTests(TestCase):
    """Tests for email provider integrations."""
    
    def test_simple_login_provider_init(self):
        """Test SimpleLogin provider initialization."""
        provider = SimpleLoginProvider('test_api_key')
        
        self.assertEqual(provider.api_key, 'test_api_key')
        self.assertIn('Authentication', provider._headers)
    
    @patch('security.services.honeypot_email_provider.httpx.post')
    def test_simple_login_create_alias(self, mock_post):
        """Test SimpleLogin alias creation."""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            'alias': 'test-alias@sl.io',
            'id': 12345
        }
        mock_post.return_value = mock_response
        
        provider = SimpleLoginProvider('test_api_key')
        email, alias_id = provider.create_alias('user_1', 'TestService')
        
        self.assertEqual(email, 'test-alias@sl.io')
        self.assertEqual(alias_id, '12345')
    
    def test_anonaddy_provider_init(self):
        """Test AnonAddy provider initialization."""
        provider = AnonAddyProvider('test_api_key')
        
        self.assertEqual(provider.api_key, 'test_api_key')
        self.assertIn('Authorization', provider._headers)
    
    @patch('security.services.honeypot_email_provider.httpx.post')
    def test_anonaddy_create_alias(self, mock_post):
        """Test AnonAddy alias creation."""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            'data': {
                'email': 'test@anonaddy.me',
                'id': 'uuid-123'
            }
        }
        mock_post.return_value = mock_response
        
        provider = AnonAddyProvider('test_api_key')
        email, alias_id = provider.create_alias('user_1', 'TestService')
        
        self.assertEqual(email, 'test@anonaddy.me')
        self.assertEqual(alias_id, 'uuid-123')
    
    def test_custom_smtp_create_alias(self):
        """Test custom SMTP provider alias creation."""
        provider = CustomSMTPProvider('mydomain.com', {})
        
        email, alias_id = provider.create_alias('user_1', 'TestService')
        
        self.assertIn('@mydomain.com', email)
        self.assertIn('hp-', email)  # Honeypot prefix


# =============================================================================
# API Tests
# =============================================================================

class HoneypotAPITests(APITestCase):
    """Tests for honeypot API endpoints."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
    
    def test_get_config(self):
        """Test getting honeypot configuration."""
        url = reverse('honeypot-config')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('is_enabled', response.data)
        self.assertIn('email_provider', response.data)
    
    def test_update_config(self):
        """Test updating configuration."""
        url = reverse('honeypot-config')
        response = self.client.put(url, {
            'auto_rotate_on_breach': True,
            'max_honeypots': 100
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify update
        config = HoneypotConfiguration.objects.get(user=self.user)
        self.assertTrue(config.auto_rotate_on_breach)
    
    @patch.object(HoneypotEmailProvider, 'create_honeypot_alias')
    def test_create_honeypot(self, mock_create):
        """Test creating a honeypot via API."""
        mock_create.return_value = ('canary@sl.io', 'alias_123')
        
        url = reverse('honeypot-list')
        response = self.client.post(url, {
            'service_name': 'Test Service',
            'service_domain': 'test.com'
        })
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('honeypot', response.data)
        self.assertEqual(response.data['honeypot']['service_name'], 'Test Service')
    
    def test_list_honeypots(self):
        """Test listing honeypots."""
        HoneypotEmail.objects.create(
            user=self.user,
            honeypot_address='hp1@sl.io',
            service_name='Service 1'
        )
        HoneypotEmail.objects.create(
            user=self.user,
            honeypot_address='hp2@sl.io',
            service_name='Service 2'
        )
        
        url = reverse('honeypot-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)
    
    def test_get_honeypot_detail(self):
        """Test getting honeypot details."""
        honeypot = HoneypotEmail.objects.create(
            user=self.user,
            honeypot_address='canary@sl.io',
            service_name='Test Service'
        )
        
        url = reverse('honeypot-detail', kwargs={'honeypot_id': honeypot.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('honeypot', response.data)
        self.assertIn('recent_activities', response.data)
    
    @patch.object(HoneypotEmailProvider, 'delete_honeypot_alias')
    def test_delete_honeypot(self, mock_delete):
        """Test deleting a honeypot."""
        mock_delete.return_value = True
        
        honeypot = HoneypotEmail.objects.create(
            user=self.user,
            honeypot_address='canary@sl.io',
            service_name='Test Service'
        )
        
        url = reverse('honeypot-detail', kwargs={'honeypot_id': honeypot.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        honeypot.refresh_from_db()
        self.assertFalse(honeypot.is_active)
    
    def test_list_breaches(self):
        """Test listing breach events."""
        honeypot = HoneypotEmail.objects.create(
            user=self.user,
            honeypot_address='canary@sl.io',
            service_name='Breached Service'
        )
        HoneypotBreachEvent.objects.create(
            user=self.user,
            honeypot=honeypot,
            service_name='Breached Service',
            severity='high'
        )
        
        url = reverse('honeypot-breaches')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
    
    def test_get_breach_detail(self):
        """Test getting breach details."""
        honeypot = HoneypotEmail.objects.create(
            user=self.user,
            honeypot_address='canary@sl.io',
            service_name='Breached Service'
        )
        breach = HoneypotBreachEvent.objects.create(
            user=self.user,
            honeypot=honeypot,
            service_name='Breached Service'
        )
        
        url = reverse('honeypot-breach-detail', kwargs={'breach_id': breach.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('timeline', response.data)
    
    def test_acknowledge_breach(self):
        """Test acknowledging a breach."""
        honeypot = HoneypotEmail.objects.create(
            user=self.user,
            honeypot_address='canary@sl.io',
            service_name='Breached Service'
        )
        breach = HoneypotBreachEvent.objects.create(
            user=self.user,
            honeypot=honeypot,
            service_name='Breached Service'
        )
        
        url = reverse('honeypot-breach-detail', kwargs={'breach_id': breach.id})
        response = self.client.patch(url, {'acknowledge': True})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        breach.refresh_from_db()
        self.assertTrue(breach.user_acknowledged)
    
    def test_initiate_rotation(self):
        """Test initiating credential rotation."""
        honeypot = HoneypotEmail.objects.create(
            user=self.user,
            honeypot_address='canary@sl.io',
            service_name='Breached Service'
        )
        breach = HoneypotBreachEvent.objects.create(
            user=self.user,
            honeypot=honeypot,
            service_name='Breached Service'
        )
        
        url = reverse('honeypot-breach-rotate', kwargs={'breach_id': breach.id})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('rotation_id', response.data)
    
    def test_list_activities(self):
        """Test listing activities."""
        honeypot = HoneypotEmail.objects.create(
            user=self.user,
            honeypot_address='canary@sl.io',
            service_name='Test Service'
        )
        HoneypotActivity.objects.create(
            honeypot=honeypot,
            activity_type='email_received',
            sender_domain='test.com'
        )
        
        url = reverse('honeypot-activities')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
    
    @patch.object(HoneypotEmailProvider, 'create_honeypot_alias')
    def test_bulk_create_honeypots(self, mock_create):
        """Test bulk creating honeypots."""
        mock_create.side_effect = [
            ('hp1@sl.io', 'alias_1'),
            ('hp2@sl.io', 'alias_2'),
        ]
        
        url = reverse('honeypot-bulk-create')
        response = self.client.post(url, {
            'services': [
                {'service_name': 'Service 1'},
                {'service_name': 'Service 2'}
            ]
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['created_count'], 2)


class HoneypotWebhookTests(APITestCase):
    """Tests for honeypot webhook endpoint."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        HoneypotConfiguration.objects.create(
            user=self.user,
            notify_on_any_activity=False,
            notify_on_breach=False
        )
        self.honeypot = HoneypotEmail.objects.create(
            user=self.user,
            honeypot_address='canary@simplelogin.com',
            service_name='Test Service'
        )
    
    @override_settings(DEBUG=True)
    def test_webhook_processes_email(self):
        """Test webhook processing incoming email."""
        url = reverse('honeypot-webhook')
        
        response = self.client.post(url, {
            'recipient': 'canary@simplelogin.com',
            'sender': 'spam@attacker.com',
            'subject': 'Spam Subject',
            'is_spam': True,
            'spam_score': 0.9
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['breach_detected'])
        
        # Verify activity was created
        self.assertTrue(
            HoneypotActivity.objects.filter(honeypot=self.honeypot).exists()
        )
    
    @override_settings(DEBUG=True)
    def test_webhook_unknown_honeypot(self):
        """Test webhook with unknown honeypot address."""
        url = reverse('honeypot-webhook')
        
        response = self.client.post(url, {
            'recipient': 'unknown@simplelogin.com',
            'sender': 'test@test.com',
            'subject': 'Test'
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


# =============================================================================
# Celery Task Tests
# =============================================================================

class HoneypotTaskTests(TestCase):
    """Tests for Celery background tasks."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    @patch('security.tasks.honeypot_tasks.get_honeypot_service')
    def test_check_honeypot_activity(self, mock_get_service):
        """Test check_honeypot_activity task."""
        from security.tasks.honeypot_tasks import check_honeypot_activity
        
        honeypot = HoneypotEmail.objects.create(
            user=self.user,
            honeypot_address='canary@sl.io',
            service_name='Test Service'
        )
        
        mock_service = Mock()
        mock_service.check_honeypot_for_activity.return_value = []
        mock_get_service.return_value = mock_service
        
        result = check_honeypot_activity(str(honeypot.id))
        
        self.assertEqual(result['honeypot_id'], str(honeypot.id))
        self.assertEqual(result['activities_found'], 0)
    
    @patch('security.tasks.honeypot_tasks.get_honeypot_service')
    def test_check_all_user_honeypots(self, mock_get_service):
        """Test check_all_user_honeypots task."""
        from security.tasks.honeypot_tasks import check_all_user_honeypots
        
        mock_service = Mock()
        mock_service.check_all_honeypots.return_value = {
            'checked': 2,
            'new_activity': 1,
            'breaches_detected': 0
        }
        mock_get_service.return_value = mock_service
        
        result = check_all_user_honeypots(self.user.id)
        
        self.assertEqual(result['checked'], 2)
    
    def test_analyze_breach_patterns(self):
        """Test analyze_breach_patterns task."""
        from security.tasks.honeypot_tasks import analyze_breach_patterns
        
        # Create some breaches
        for i in range(3):
            honeypot = HoneypotEmail.objects.create(
                user=self.user,
                honeypot_address=f'hp{i}@sl.io',
                service_name='Vulnerable Service'
            )
            HoneypotBreachEvent.objects.create(
                user=self.user,
                honeypot=honeypot,
                service_name='Vulnerable Service',
                severity='high'
            )
        
        result = analyze_breach_patterns()
        
        self.assertIn('widespread_breaches', result)
        # 3 breaches for same service should be detected
        self.assertIn('vulnerable service', result['widespread_breaches'])
    
    def test_cleanup_expired_honeypots(self):
        """Test cleanup_expired_honeypots task."""
        from security.tasks.honeypot_tasks import cleanup_expired_honeypots
        
        # Create expired honeypot
        expired = HoneypotEmail.objects.create(
            user=self.user,
            honeypot_address='expired@sl.io',
            service_name='Expired Service',
            expires_at=timezone.now() - timedelta(days=1)
        )
        
        # Create non-expired honeypot
        active = HoneypotEmail.objects.create(
            user=self.user,
            honeypot_address='active@sl.io',
            service_name='Active Service',
            expires_at=timezone.now() + timedelta(days=30)
        )
        
        result = cleanup_expired_honeypots()
        
        self.assertEqual(result['expired_count'], 1)
        
        expired.refresh_from_db()
        active.refresh_from_db()
        
        self.assertFalse(expired.is_active)
        self.assertEqual(expired.status, 'expired')
        self.assertTrue(active.is_active)
    
    def test_generate_honeypot_stats(self):
        """Test generate_honeypot_stats task."""
        from security.tasks.honeypot_tasks import generate_honeypot_stats
        
        # Create some test data
        HoneypotEmail.objects.create(
            user=self.user,
            honeypot_address='hp1@sl.io',
            service_name='Service 1'
        )
        honeypot = HoneypotEmail.objects.create(
            user=self.user,
            honeypot_address='hp2@sl.io',
            service_name='Service 2',
            breach_detected=True
        )
        HoneypotBreachEvent.objects.create(
            user=self.user,
            honeypot=honeypot,
            service_name='Service 2',
            severity='high'
        )
        
        result = generate_honeypot_stats()
        
        self.assertEqual(result['total_honeypots'], 2)
        self.assertEqual(result['breached_honeypots'], 1)
        self.assertEqual(result['total_breaches'], 1)
        self.assertIn('breach_rate', result)
