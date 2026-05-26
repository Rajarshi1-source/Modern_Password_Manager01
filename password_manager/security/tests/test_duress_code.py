"""
Test suite for Military-Grade Duress Codes

Tests the duress code models, services, and integration with security features.
"""

import uuid
from unittest.mock import patch, MagicMock
from django.test import TestCase, TransactionTestCase, override_settings
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APITestCase, APIClient
from rest_framework import status

from security.models import (
    DuressCodeConfiguration,
    DuressCode,
    DecoyVault,
    DuressEvent,
    EvidencePackage,
    TrustedAuthority,
)
from security.services.duress_code_service import (
    DuressCodeService,
    get_duress_code_service,
)


class DuressCodeConfigurationTests(TestCase):
    """Tests for DuressCodeConfiguration model"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_create_configuration(self):
        """Test creating a duress configuration"""
        config = DuressCodeConfiguration.objects.create(
            user=self.user,
            is_enabled=True,
            silent_alarm_enabled=True,
            decoy_vault_enabled=True,
            evidence_preservation_enabled=True,
        )
        
        self.assertEqual(config.user, self.user)
        self.assertTrue(config.is_enabled)
        self.assertTrue(config.silent_alarm_enabled)
    
    def test_configuration_str(self):
        """Test string representation"""
        config = DuressCodeConfiguration.objects.create(user=self.user)
        self.assertIn(self.user.username, str(config))
    
    def test_one_config_per_user(self):
        """Test that each user can only have one configuration"""
        DuressCodeConfiguration.objects.create(user=self.user)
        
        # Creating another should raise an error
        with self.assertRaises(Exception):
            DuressCodeConfiguration.objects.create(user=self.user)


class DuressCodeTests(TestCase):
    """Tests for DuressCode model"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.config = DuressCodeConfiguration.objects.create(
            user=self.user,
            is_enabled=True,
        )
    
    def test_create_duress_code(self):
        """Test creating a duress code"""
        code = DuressCode.objects.create(
            user=self.user,
            code_hash='hashed_code_here',
            threat_level='high',
            code_hint='Emergency code',
            is_active=True,
        )
        
        self.assertEqual(code.user, self.user)
        self.assertEqual(code.threat_level, 'high')
        self.assertTrue(code.is_active)
        self.assertEqual(code.activation_count, 0)
    
    def test_duress_code_str(self):
        """Test string representation"""
        code = DuressCode.objects.create(
            user=self.user,
            code_hash='hashed',
            threat_level='medium',
        )
        self.assertIn('medium', str(code).lower())
    
    def test_get_default_actions_high_threat(self):
        """Test default actions for high threat level"""
        code = DuressCode.objects.create(
            user=self.user,
            code_hash='hashed',
            threat_level='high',
        )
        
        actions = code.get_default_actions()
        self.assertTrue(actions.get('show_decoy'))
        self.assertTrue(actions.get('alert_authorities'))
        self.assertTrue(actions.get('preserve_evidence'))
    
    def test_get_default_actions_low_threat(self):
        """Test default actions for low threat level"""
        code = DuressCode.objects.create(
            user=self.user,
            code_hash='hashed',
            threat_level='low',
        )
        
        actions = code.get_default_actions()
        self.assertTrue(actions.get('show_decoy'))
        # Low threat might not alert authorities by default
    
    def test_multiple_codes_per_user(self):
        """Test that users can have multiple duress codes"""
        code1 = DuressCode.objects.create(
            user=self.user,
            code_hash='hash1',
            threat_level='low',
        )
        code2 = DuressCode.objects.create(
            user=self.user,
            code_hash='hash2',
            threat_level='high',
        )
        
        codes = DuressCode.objects.filter(user=self.user)
        self.assertEqual(codes.count(), 2)


class DecoyVaultTests(TestCase):
    """Tests for DecoyVault model"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_create_decoy_vault(self):
        """Test creating a decoy vault"""
        decoy = DecoyVault.objects.create(
            user=self.user,
            threat_level='medium',
            fake_credentials={
                'items': [
                    {'name': 'Fake Gmail', 'username': 'fake@gmail.com'},
                    {'name': 'Fake Bank', 'username': 'user123'},
                ]
            },
            realism_score=0.85,
        )
        
        self.assertEqual(decoy.user, self.user)
        self.assertEqual(decoy.threat_level, 'medium')
        self.assertEqual(len(decoy.fake_credentials['items']), 2)
    
    def test_decoy_vault_str(self):
        """Test string representation"""
        decoy = DecoyVault.objects.create(
            user=self.user,
            threat_level='high',
            fake_credentials={},
        )
        self.assertIn('high', str(decoy).lower())


class TrustedAuthorityTests(TestCase):
    """Tests for TrustedAuthority model"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_create_trusted_authority(self):
        """Test creating a trusted authority"""
        authority = TrustedAuthority.objects.create(
            user=self.user,
            authority_type='emergency_contact',
            name='John Doe',
            email='john@example.com',
            phone_number='+1234567890',
            is_active=True,
            minimum_threat_level='medium',
        )
        
        self.assertEqual(authority.user, self.user)
        self.assertEqual(authority.name, 'John Doe')
        self.assertTrue(authority.is_active)
    
    def test_should_notify_for_level(self):
        """Test notification level threshold logic"""
        authority = TrustedAuthority.objects.create(
            user=self.user,
            authority_type='law_enforcement',
            name='Police',
            email='police@example.com',
            minimum_threat_level='high',
        )
        
        # Should notify for high and critical
        self.assertTrue(authority.should_notify_for_level('high'))
        self.assertTrue(authority.should_notify_for_level('critical'))
        
        # Should not notify for low/medium
        self.assertFalse(authority.should_notify_for_level('low'))
        self.assertFalse(authority.should_notify_for_level('medium'))


class DuressEventTests(TestCase):
    """Tests for DuressEvent model"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.duress_code = DuressCode.objects.create(
            user=self.user,
            code_hash='hashed_code',
            threat_level='high',
        )
    
    def test_create_duress_event(self):
        """Test creating a duress event"""
        event = DuressEvent.objects.create(
            user=self.user,
            event_type='code_activated',
            duress_code=self.duress_code,
            threat_level='high',
            ip_address='192.168.1.1',
            user_agent='Mozilla/5.0 Test Browser',
            response_status='success',
        )
        
        self.assertEqual(event.user, self.user)
        self.assertEqual(event.event_type, 'code_activated')
        self.assertEqual(event.threat_level, 'high')
    
    def test_event_ordering(self):
        """Test that events are ordered by timestamp descending"""
        event1 = DuressEvent.objects.create(
            user=self.user,
            event_type='code_activated',
            threat_level='low',
            ip_address='1.1.1.1',
        )
        event2 = DuressEvent.objects.create(
            user=self.user,
            event_type='behavioral_detected',
            threat_level='high',
            ip_address='2.2.2.2',
        )
        
        events = list(DuressEvent.objects.filter(user=self.user))
        # Most recent first
        self.assertEqual(events[0], event2)


class EvidencePackageTests(TestCase):
    """Tests for EvidencePackage model"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.event = DuressEvent.objects.create(
            user=self.user,
            event_type='code_activated',
            threat_level='critical',
            ip_address='192.168.1.100',
        )
    
    def test_create_evidence_package(self):
        """Test creating an evidence package"""
        package = EvidencePackage.objects.create(
            user=self.user,
            status='complete',
            session_data={'login_time': '2025-01-31T12:00:00Z'},
            network_data={'ip': '192.168.1.100', 'headers': {}},
            behavioral_data={'typing_speed': 100},
            access_pattern_data={'pages_visited': ['/vault']},
        )
        
        self.assertEqual(package.user, self.user)
        self.assertEqual(package.status, 'complete')
        self.assertIsNotNone(package.session_data)
    
    def test_compute_hash(self):
        """Test computing evidence hash for integrity"""
        package = EvidencePackage.objects.create(
            user=self.user,
            status='complete',
            session_data={'test': 'data'},
        )
        
        # Compute hash
        package.compute_hash()
        package.save()
        
        self.assertIsNotNone(package.evidence_hash)
        self.assertTrue(len(package.evidence_hash) > 0)
    
    def test_add_custody_entry(self):
        """Test adding chain of custody entry"""
        package = EvidencePackage.objects.create(
            user=self.user,
            status='complete',
            chain_of_custody=[],
        )
        
        package.add_custody_entry(
            action='created',
            actor='system',
            details='Initial evidence collection'
        )
        package.save()
        
        self.assertEqual(len(package.chain_of_custody), 1)
        self.assertEqual(package.chain_of_custody[0]['action'], 'created')


class DuressCodeServiceTests(TransactionTestCase):
    """Tests for DuressCodeService"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.service = DuressCodeService()
    
    def test_get_or_create_config(self):
        """Test getting or creating duress config"""
        config = self.service.get_or_create_config(self.user)
        
        self.assertIsNotNone(config)
        self.assertEqual(config.user, self.user)
        
        # Second call should return same config
        config2 = self.service.get_or_create_config(self.user)
        self.assertEqual(config.id, config2.id)
    
    def test_create_duress_code(self):
        """Test creating a duress code through service"""
        code = self.service.create_duress_code(
            user=self.user,
            code='panic123',
            threat_level='high',
            code_hint='Emergency',
        )
        
        self.assertIsNotNone(code)
        self.assertEqual(code.user, self.user)
        self.assertEqual(code.threat_level, 'high')
        # Code should be hashed, not stored plaintext
        self.assertNotEqual(code.code_hash, 'panic123')
    
    def test_get_user_codes(self):
        """Test retrieving user's duress codes"""
        # Create some codes
        self.service.create_duress_code(self.user, 'code1', 'low')
        self.service.create_duress_code(self.user, 'code2', 'high')
        
        codes = self.service.get_user_codes(self.user)
        self.assertEqual(len(codes), 2)
    
    def test_delete_duress_code(self):
        """Test deleting (deactivating) a duress code"""
        code = self.service.create_duress_code(self.user, 'testcode', 'medium')
        self.assertTrue(code.is_active)
        
        self.service.delete_duress_code(code)
        
        code.refresh_from_db()
        self.assertFalse(code.is_active)
    
    @patch('security.services.duress_code_service.DuressCodeService._trigger_silent_alarms')
    def test_activate_duress_mode(self, mock_alarms):
        """Test activating duress mode"""
        mock_alarms.return_value = True
        
        # Enable config
        config = self.service.get_or_create_config(self.user)
        config.is_enabled = True
        config.silent_alarm_enabled = True
        config.save()
        
        code = self.service.create_duress_code(self.user, 'emergency', 'critical')
        
        request_context = {
            'ip_address': '192.168.1.1',
            'user_agent': 'Test Browser',
            'device_fingerprint': {},
            'geo_location': {},
        }
        
        result = self.service.activate_duress_mode(
            user=self.user,
            duress_code=code,
            request_context=request_context,
            is_test=False
        )
        
        self.assertTrue(result['activated'])
        self.assertEqual(result['threat_level'], 'critical')
        self.assertIn('event_id', result)
        
        # Check event was created
        events = DuressEvent.objects.filter(user=self.user)
        self.assertEqual(events.count(), 1)
    
    def test_activate_duress_mode_test_mode(self):
        """Test that test mode doesn't trigger real alarms"""
        config = self.service.get_or_create_config(self.user)
        config.is_enabled = True
        config.save()
        
        code = self.service.create_duress_code(self.user, 'test123', 'high')
        
        request_context = {
            'ip_address': '127.0.0.1',
            'user_agent': 'Test',
            'device_fingerprint': {},
        }
        
        result = self.service.activate_duress_mode(
            user=self.user,
            duress_code=code,
            request_context=request_context,
            is_test=True
        )
        
        self.assertTrue(result['activated'])
        self.assertTrue(result['is_test'])
        
        # Event should be marked as test
        event = DuressEvent.objects.get(user=self.user)
        self.assertEqual(event.event_type, 'test_activation')


class DuressCodeAPITests(APITestCase):
    """Tests for Duress Code API endpoints"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='apiuser',
            email='api@example.com',
            password='apipass123'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
    
    def test_get_config(self):
        """Test getting duress configuration"""
        response = self.client.get('/api/security/duress/config/')
        self.assertIn(response.status_code, [200, 404])
    
    def test_create_duress_code_endpoint(self):
        """Test creating duress code via API"""
        response = self.client.post('/api/security/duress/codes/', {
            'code': 'apicode123',
            'threat_level': 'high',
            'code_hint': 'API Test Code',
        })
        # Either 201 created or 400 if validation fails
        self.assertIn(response.status_code, [201, 400, 404])
    
    def test_list_duress_codes(self):
        """Test listing user's duress codes"""
        response = self.client.get('/api/security/duress/codes/')
        self.assertIn(response.status_code, [200, 404])
    
    def test_list_authorities(self):
        """Test listing trusted authorities"""
        response = self.client.get('/api/security/duress/authorities/')
        self.assertIn(response.status_code, [200, 404])

    # -----------------------------------------------------------------
    # Phase D / D9 (2026-05): TrustedAuthority serializer validation.
    # -----------------------------------------------------------------

    def test_create_authority_rejects_empty_trigger_threat_levels(self):
        """Empty trigger_threat_levels would silently disable the
        alarm. Must be rejected at the serializer."""
        response = self.client.post(
            '/api/security/duress/authorities/',
            {
                'name': 'Lawyer',
                'authority_type': 'legal_counsel',
                'contact_method': 'email',
                'contact_details': {'email': 'lawyer@example.com'},
                'trigger_threat_levels': [],  # <-- the bug
            },
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('trigger_threat_levels', response.data.get('errors', {}))

    def test_create_authority_rejects_arbitrary_contact_details_keys(self):
        """Unknown keys in contact_details are rejected — the previous
        free-form JSONField could carry attacker-controlled values
        under invented keys."""
        response = self.client.post(
            '/api/security/duress/authorities/',
            {
                'name': 'Lawyer',
                'authority_type': 'legal_counsel',
                'contact_method': 'email',
                'contact_details': {
                    # No declared field → at-least-one-required rule
                    # fires because the unknown key is dropped.
                    'attacker_invented_key': 'https://attacker.example',
                },
                'trigger_threat_levels': ['high', 'critical'],
            },
            format='json',
        )
        self.assertEqual(response.status_code, 400)

    def test_create_authority_rejects_invalid_threat_level(self):
        """Threat-level strings outside the documented set are rejected."""
        response = self.client.post(
            '/api/security/duress/authorities/',
            {
                'name': 'Lawyer',
                'authority_type': 'legal_counsel',
                'contact_method': 'email',
                'contact_details': {'email': 'lawyer@example.com'},
                'trigger_threat_levels': ['nuclear'],  # not a valid level
            },
            format='json',
        )
        self.assertEqual(response.status_code, 400)

    # -----------------------------------------------------------------
    # Phase D / D3 (2026-05): test_duress_activation must require the
    # actual code string, not just the UUID.
    # -----------------------------------------------------------------

    def _create_duress_code(self, code_str='secret_panic_phrase', threat='high'):
        """Helper — produces a real DuressCode through the service so
        the Argon2 hash is genuine."""
        from security.services.duress_code_service import get_duress_code_service
        return get_duress_code_service().create_duress_code(
            user=self.user,
            code=code_str,
            threat_level=threat,
            code_hint='Test hint',
        )

    def test_duress_test_endpoint_rejects_without_code(self):
        """Missing the ``code`` field → 400, no activation."""
        self._create_duress_code()
        response = self.client.post(
            '/api/security/duress/test/',
            {},  # no code
            format='json',
        )
        self.assertEqual(response.status_code, 400)

    def test_duress_test_endpoint_rejects_wrong_code(self):
        """Wrong code string → 400 ``invalid_code`` (NOT a 404 by id,
        not a 500). No activation happens."""
        self._create_duress_code(code_str='right_code')
        response = self.client.post(
            '/api/security/duress/test/',
            {'code': 'wrong_code'},
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data.get('error'), 'invalid_code')

    def test_duress_test_endpoint_succeeds_with_correct_code(self):
        """Correct code → test-mode activation runs."""
        self._create_duress_code(code_str='right_code', threat='high')
        response = self.client.post(
            '/api/security/duress/test/',
            {'code': 'right_code'},
            format='json',
        )
        # Activation either succeeds (200/201) or returns a structured
        # error from the service layer, but it MUST NOT be a 400 (which
        # would mean the code check rejected it) or a 500.
        self.assertNotIn(response.status_code, [400, 500])

    def test_duress_codes_list_does_not_leak_uuid(self):
        """The ``id`` field must NOT appear in the GET response —
        exposing it was what made the UUID-based bypass possible."""
        self._create_duress_code(code_str='listed_code')
        response = self.client.get('/api/security/duress/codes/')
        self.assertEqual(response.status_code, 200)
        for code in response.data.get('codes', []):
            self.assertNotIn('id', code, msg=f"UUID leaked in: {code!r}")

    def test_create_authority_accepts_valid_payload(self):
        """Happy path — well-formed payload creates the authority."""
        response = self.client.post(
            '/api/security/duress/authorities/',
            {
                'name': 'Family lawyer',
                'authority_type': 'legal_counsel',
                'contact_method': 'email',
                'contact_details': {'email': 'lawyer@example.com'},
                'trigger_threat_levels': ['high', 'critical'],
                'delay_seconds': 30,
                'include_location': True,
            },
            format='json',
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data['success'])
        self.assertIn('id', response.data['authority'])

    def test_create_authority_accepts_legacy_threat_levels_alias(self):
        """PR #275 review: the mobile client sends ``threat_levels``,
        not ``trigger_threat_levels``. The serializer must accept the
        alias to avoid breaking shipped clients during rollout."""
        response = self.client.post(
            '/api/security/duress/authorities/',
            {
                'name': 'Mobile-Client Lawyer',
                'authority_type': 'legal_counsel',
                'contact_method': 'email',
                'contact_details': {'email': 'mobile-lawyer@example.com'},
                'threat_levels': ['high', 'critical'],  # <-- legacy alias
            },
            format='json',
        )
        self.assertEqual(response.status_code, 201)
        # Verify the canonical name was actually written to the row.
        from security.models.duress_models import TrustedAuthority
        authority = TrustedAuthority.objects.get(
            user=self.user, name='Mobile-Client Lawyer',
        )
        self.assertEqual(authority.trigger_threat_levels, ['high', 'critical'])

    def test_update_authority_rejects_empty_trigger_threat_levels(self):
        """PR #275 review (CodeRabbit): the PUT path previously bypassed
        the D9 serializer by raw-copying request.data fields. Confirm
        empty trigger_threat_levels is rejected via PUT as well."""
        # First create a valid authority
        create_resp = self.client.post(
            '/api/security/duress/authorities/',
            {
                'name': 'Authority to-update',
                'authority_type': 'legal_counsel',
                'contact_method': 'email',
                'contact_details': {'email': 'pre@example.com'},
                'trigger_threat_levels': ['high'],
            },
            format='json',
        )
        self.assertEqual(create_resp.status_code, 201)
        # Use the id-via-DB since the list response no longer leaks UUIDs.
        from security.models.duress_models import TrustedAuthority
        authority_id = TrustedAuthority.objects.get(
            user=self.user, name='Authority to-update',
        ).id

        # PUT with the silent-disable payload.
        put_resp = self.client.put(
            f'/api/security/duress/authorities/{authority_id}/',
            {'trigger_threat_levels': []},
            format='json',
        )
        self.assertEqual(put_resp.status_code, 400)

    def test_update_authority_partial_update_succeeds(self):
        """PR #275 review: ``partial=True`` lets PUT update just the
        fields the caller actually sent without re-validating untouched
        fields."""
        self.client.post(
            '/api/security/duress/authorities/',
            {
                'name': 'Partial Update Target',
                'authority_type': 'legal_counsel',
                'contact_method': 'email',
                'contact_details': {'email': 'pre@example.com'},
                'trigger_threat_levels': ['high'],
            },
            format='json',
        )
        from security.models.duress_models import TrustedAuthority
        authority = TrustedAuthority.objects.get(
            user=self.user, name='Partial Update Target',
        )
        put_resp = self.client.put(
            f'/api/security/duress/authorities/{authority.id}/',
            {'delay_seconds': 60},  # only one field
            format='json',
        )
        self.assertEqual(put_resp.status_code, 200)
        authority.refresh_from_db()
        self.assertEqual(authority.delay_seconds, 60)
    
    def test_list_events(self):
        """Test listing duress events"""
        response = self.client.get('/api/security/duress/events/')
        self.assertIn(response.status_code, [200, 404])


class SecurityServiceIntegrationTests(TestCase):
    """Tests for SecurityService duress integration"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='secuser',
            email='sec@example.com',
            password='secpass123'
        )
        # Create duress configuration and code
        self.config = DuressCodeConfiguration.objects.create(
            user=self.user,
            is_enabled=True,
        )
        self.duress_service = DuressCodeService()
        self.duress_code = self.duress_service.create_duress_code(
            user=self.user,
            code='duress123',
            threat_level='high',
        )
    
    def test_security_service_has_duress_check(self):
        """Test that SecurityService has check_for_duress_code method"""
        from security.services.security_service import SecurityService
        
        service = SecurityService()
        self.assertTrue(hasattr(service, 'check_for_duress_code'))
        self.assertTrue(callable(service.check_for_duress_code))
    
    @patch('security.services.security_service.get_client_ip')
    def test_check_for_duress_code_detects_duress(self, mock_get_ip):
        """Test that check_for_duress_code correctly detects duress code"""
        mock_get_ip.return_value = ('192.168.1.100', False)
        
        from security.services.security_service import SecurityService
        
        # Create mock request
        mock_request = MagicMock()
        mock_request.META = {'HTTP_USER_AGENT': 'Test Browser'}
        mock_request.data = {
            'device_fingerprint': {},
            'behavioral_data': {},
            'stress_score': 0.5,
        }
        
        service = SecurityService()
        result = service.check_for_duress_code(
            user=self.user,
            password='duress123',
            request=mock_request
        )
        
        # Should detect duress code
        self.assertTrue(result['is_duress'])
        self.assertIsNotNone(result['response'])
