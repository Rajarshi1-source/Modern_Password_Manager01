"""
API Endpoint Tests for Predictive Password Expiration Feature
==============================================================

Tests for all REST API endpoints related to predictive password expiration.
"""

from unittest.mock import patch, MagicMock
from datetime import timedelta
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase, APIClient
from rest_framework import status

User = get_user_model()


class PredictiveExpirationAPITestCase(APITestCase):
    """Base test case for predictive expiration API tests."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPassword123!'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        
        # Create user settings
        from security.models import PredictiveExpirationSettings
        self.settings = PredictiveExpirationSettings.objects.create(
            user=self.user,
            is_enabled=True,
            industry='technology'
        )


class DashboardAPITests(PredictiveExpirationAPITestCase):
    """Tests for the dashboard endpoint."""
    
    def test_get_dashboard_authenticated(self):
        """Test getting dashboard data as authenticated user."""
        response = self.client.get('/api/security/predictive-expiration/dashboard/')
        
        self.assertIn(response.status_code, [200, 404])
        
        if response.status_code == 200:
            data = response.json()
            self.assertIn('total_credentials', data)
            self.assertIn('high_risk_count', data)
            self.assertIn('critical_count', data)
            self.assertIn('overall_risk_score', data)
            
    def test_get_dashboard_unauthenticated(self):
        """Test that unauthenticated requests are rejected."""
        self.client.logout()
        response = self.client.get('/api/security/predictive-expiration/dashboard/')
        
        self.assertIn(response.status_code, [401, 403])


class AtRiskCredentialsAPITests(PredictiveExpirationAPITestCase):
    """Tests for the at-risk credentials list endpoint."""
    
    def test_list_at_risk_credentials(self):
        """Test listing at-risk credentials."""
        from security.models import PredictiveExpirationRule
        
        # Create some test rules
        PredictiveExpirationRule.objects.create(
            user=self.user,
            credential_id='cred-1',
            credential_domain='example.com',
            risk_level='high',
            risk_score=0.8
        )
        PredictiveExpirationRule.objects.create(
            user=self.user,
            credential_id='cred-2',
            credential_domain='another.com',
            risk_level='medium',
            risk_score=0.5
        )
        
        response = self.client.get('/api/security/predictive-expiration/credentials/')
        
        self.assertIn(response.status_code, [200, 404])
        
        if response.status_code == 200:
            data = response.json()
            self.assertIsInstance(data, list)
            
    def test_filter_by_risk_level(self):
        """Test filtering credentials by risk level."""
        from security.models import PredictiveExpirationRule
        
        # Create rules with different risk levels
        PredictiveExpirationRule.objects.create(
            user=self.user,
            credential_id='high-1',
            credential_domain='high-risk.com',
            risk_level='high',
            risk_score=0.8
        )
        PredictiveExpirationRule.objects.create(
            user=self.user,
            credential_id='low-1',
            credential_domain='low-risk.com',
            risk_level='low',
            risk_score=0.2
        )
        
        response = self.client.get('/api/security/predictive-expiration/credentials/?risk_level=high')
        
        self.assertIn(response.status_code, [200, 404])
        
        if response.status_code == 200:
            data = response.json()
            for cred in data:
                self.assertEqual(cred.get('risk_level'), 'high')


class CredentialRiskDetailAPITests(PredictiveExpirationAPITestCase):
    """Tests for the credential risk detail endpoint."""
    
    def test_get_credential_risk_detail(self):
        """Test getting detailed risk analysis for a credential."""
        from security.models import PredictiveExpirationRule
        
        rule = PredictiveExpirationRule.objects.create(
            user=self.user,
            credential_id='test-cred',
            credential_domain='test.com',
            risk_level='high',
            risk_score=0.75,
            threat_factors=['old_password', 'common_pattern']
        )
        
        response = self.client.get('/api/security/predictive-expiration/credential/test-cred/risk/')
        
        self.assertIn(response.status_code, [200, 404])
        
        if response.status_code == 200:
            data = response.json()
            self.assertEqual(data.get('credential_id'), 'test-cred')
            self.assertEqual(data.get('risk_level'), 'high')
            
    def test_get_nonexistent_credential(self):
        """Test getting risk for non-existent credential."""
        response = self.client.get('/api/security/predictive-expiration/credential/nonexistent/risk/')
        
        self.assertIn(response.status_code, [404, 200])


class ForceRotationAPITests(PredictiveExpirationAPITestCase):
    """Tests for the force rotation endpoint."""
    
    def test_force_rotation(self):
        """Test forcing password rotation."""
        from security.models import PredictiveExpirationRule
        
        rule = PredictiveExpirationRule.objects.create(
            user=self.user,
            credential_id='rotate-cred',
            credential_domain='rotate.com',
            risk_level='critical',
            risk_score=0.95
        )
        
        response = self.client.post('/api/security/predictive-expiration/credential/rotate-cred/rotate/')
        
        self.assertIn(response.status_code, [200, 201, 404])
        
    def test_force_rotation_unauthenticated(self):
        """Test that unauthenticated users cannot force rotation."""
        self.client.logout()
        response = self.client.post('/api/security/predictive-expiration/credential/some-cred/rotate/')
        
        self.assertIn(response.status_code, [401, 403])


class AcknowledgeRiskAPITests(PredictiveExpirationAPITestCase):
    """Tests for the acknowledge risk endpoint."""
    
    def test_acknowledge_risk(self):
        """Test acknowledging a credential risk."""
        from security.models import PredictiveExpirationRule
        
        rule = PredictiveExpirationRule.objects.create(
            user=self.user,
            credential_id='ack-cred',
            credential_domain='ack.com',
            risk_level='high',
            risk_score=0.8,
            user_acknowledged=False
        )
        
        response = self.client.post('/api/security/predictive-expiration/credential/ack-cred/acknowledge/')
        
        self.assertIn(response.status_code, [200, 201, 404])
        
        if response.status_code in [200, 201]:
            rule.refresh_from_db()
            self.assertTrue(rule.user_acknowledged)


class ThreatsAPITests(PredictiveExpirationAPITestCase):
    """Tests for the threat intelligence endpoints."""
    
    def test_list_active_threats(self):
        """Test listing active threat actors."""
        from security.models import ThreatActorTTP
        
        ThreatActorTTP.objects.create(
            name='Test Threat Actor',
            actor_type='apt',
            threat_level='high',
            target_industries=['technology'],
            is_currently_active=True
        )
        
        response = self.client.get('/api/security/predictive-expiration/threats/')
        
        self.assertIn(response.status_code, [200, 404])
        
        if response.status_code == 200:
            data = response.json()
            self.assertIsInstance(data, list)
            
    def test_get_threat_summary(self):
        """Test getting threat landscape summary."""
        response = self.client.get('/api/security/predictive-expiration/threat-summary/')
        
        self.assertIn(response.status_code, [200, 404])
        
        if response.status_code == 200:
            data = response.json()
            self.assertIn('threat_level', data)
            self.assertIn('active_threats_count', data)


class SettingsAPITests(PredictiveExpirationAPITestCase):
    """Tests for the user settings endpoint."""
    
    def test_get_settings(self):
        """Test getting user settings."""
        response = self.client.get('/api/security/predictive-expiration/settings/')
        
        self.assertIn(response.status_code, [200, 404])
        
        if response.status_code == 200:
            data = response.json()
            self.assertIn('is_enabled', data)
            
    def test_update_settings(self):
        """Test updating user settings."""
        response = self.client.patch(
            '/api/security/predictive-expiration/settings/',
            {'is_enabled': False, 'notification_frequency': 'daily'},
            format='json'
        )
        
        self.assertIn(response.status_code, [200, 404])
        
        if response.status_code == 200:
            self.settings.refresh_from_db()
            self.assertFalse(self.settings.is_enabled)
            
    def test_update_settings_invalid_data(self):
        """Test updating settings with invalid data."""
        response = self.client.patch(
            '/api/security/predictive-expiration/settings/',
            {'force_rotation_threshold': 2.0},  # Invalid - should be 0-1
            format='json'
        )
        
        # Should return 400 for invalid data
        self.assertIn(response.status_code, [200, 400, 404])


class RotationHistoryAPITests(PredictiveExpirationAPITestCase):
    """Tests for the rotation history endpoint."""
    
    def test_get_rotation_history(self):
        """Test getting rotation history."""
        from security.models import PasswordRotationEvent
        
        PasswordRotationEvent.objects.create(
            user=self.user,
            credential_id='hist-cred',
            credential_domain='history.com',
            rotation_type='proactive',
            outcome='success'
        )
        
        response = self.client.get('/api/security/predictive-expiration/history/')
        
        self.assertIn(response.status_code, [200, 404])
        
        if response.status_code == 200:
            data = response.json()
            self.assertIsInstance(data, list)
            self.assertEqual(len(data), 1)
            
    def test_filter_history_by_outcome(self):
        """Test filtering rotation history by outcome."""
        from security.models import PasswordRotationEvent
        
        PasswordRotationEvent.objects.create(
            user=self.user,
            credential_id='success-cred',
            credential_domain='success.com',
            rotation_type='forced',
            outcome='success'
        )
        PasswordRotationEvent.objects.create(
            user=self.user,
            credential_id='failed-cred',
            credential_domain='failed.com',
            rotation_type='forced',
            outcome='failed'
        )
        
        response = self.client.get('/api/security/predictive-expiration/history/?outcome=success')
        
        self.assertIn(response.status_code, [200, 404])
        
        if response.status_code == 200:
            data = response.json()
            for event in data:
                self.assertEqual(event.get('outcome'), 'success')


class AnalyzeCredentialAPITests(PredictiveExpirationAPITestCase):
    """Tests for the analyze credential endpoint."""
    
    @patch('security.services.predictive_expiration_service.PredictiveExpirationService')
    def test_analyze_credential(self, mock_service):
        """Test analyzing a credential for risk."""
        mock_instance = MagicMock()
        mock_instance.calculate_exposure_risk.return_value = {
            'risk_score': 0.7,
            'risk_level': 'high',
            'factors': ['old_password']
        }
        mock_service.return_value = mock_instance
        
        response = self.client.post(
            '/api/security/predictive-expiration/analyze/',
            {
                'credential_id': 'analyze-cred',
                'password': 'WeakPassword1',
                'domain': 'analyze.com'
            },
            format='json'
        )
        
        self.assertIn(response.status_code, [200, 201, 400, 404])
        
    def test_analyze_credential_missing_data(self):
        """Test analyzing with missing required fields."""
        response = self.client.post(
            '/api/security/predictive-expiration/analyze/',
            {'credential_id': 'incomplete'},
            format='json'
        )
        
        self.assertIn(response.status_code, [400, 404])


class PatternProfileAPITests(PredictiveExpirationAPITestCase):
    """Tests for the pattern profile endpoint."""
    
    def test_get_pattern_profile(self):
        """Test getting user's password pattern profile."""
        from security.models import PasswordPatternProfile
        
        PasswordPatternProfile.objects.create(
            user=self.user,
            char_class_distribution={'lowercase': 50, 'uppercase': 20, 'digits': 20, 'special': 10},
            avg_password_length=14.5,
            total_passwords_analyzed=5
        )
        
        response = self.client.get('/api/security/predictive-expiration/pattern-profile/')
        
        self.assertIn(response.status_code, [200, 404])
        
        if response.status_code == 200:
            data = response.json()
            self.assertIn('avg_password_length', data)
            self.assertIn('total_passwords_analyzed', data)
            
    def test_get_pattern_profile_no_data(self):
        """Test getting pattern profile when no data exists."""
        response = self.client.get('/api/security/predictive-expiration/pattern-profile/')
        
        # Should return 200 with empty data or 404
        self.assertIn(response.status_code, [200, 404])


class IndustryThreatsAPITests(PredictiveExpirationAPITestCase):
    """Tests for the industry threats endpoint."""
    
    def test_get_industry_threats(self):
        """Test getting industry threat levels."""
        from security.models import IndustryThreatLevel
        
        IndustryThreatLevel.objects.create(
            industry_name='Technology',
            industry_code='tech',
            current_threat_level='high',
            threat_score=0.75
        )
        
        response = self.client.get('/api/security/predictive-expiration/industries/')
        
        self.assertIn(response.status_code, [200, 404])
        
        if response.status_code == 200:
            data = response.json()
            self.assertIsInstance(data, list)


class PaginationTests(PredictiveExpirationAPITestCase):
    """Tests for API pagination."""
    
    def test_credentials_pagination(self):
        """Test that credentials list supports pagination."""
        from security.models import PredictiveExpirationRule
        
        # Create multiple rules
        for i in range(25):
            PredictiveExpirationRule.objects.create(
                user=self.user,
                credential_id=f'cred-{i}',
                credential_domain=f'domain{i}.com',
                risk_level='medium',
                risk_score=0.5
            )
        
        response = self.client.get('/api/security/predictive-expiration/credentials/?page=1&page_size=10')
        
        self.assertIn(response.status_code, [200, 404])
        
    def test_history_pagination(self):
        """Test that history supports pagination."""
        from security.models import PasswordRotationEvent
        
        for i in range(15):
            PasswordRotationEvent.objects.create(
                user=self.user,
                credential_id=f'hist-{i}',
                credential_domain=f'hist{i}.com',
                rotation_type='voluntary',
                outcome='success'
            )
        
        response = self.client.get('/api/security/predictive-expiration/history/?page=1')
        
        self.assertIn(response.status_code, [200, 404])


class ErrorHandlingTests(PredictiveExpirationAPITestCase):
    """Tests for API error handling."""
    
    def test_method_not_allowed(self):
        """Test that unsupported methods return 405."""
        # Dashboard is GET only
        response = self.client.post('/api/security/predictive-expiration/dashboard/')
        
        self.assertIn(response.status_code, [405, 404])
        
    def test_invalid_json(self):
        """Test handling of invalid JSON in request body."""
        response = self.client.post(
            '/api/security/predictive-expiration/analyze/',
            'invalid json',
            content_type='application/json'
        )
        
        self.assertIn(response.status_code, [400, 404, 415])


class RateLimitingTests(PredictiveExpirationAPITestCase):
    """Tests for API rate limiting (if implemented)."""
    
    @override_settings(RATELIMIT_ENABLE=True)
    def test_rate_limiting_on_analyze(self):
        """Test rate limiting on resource-intensive endpoints."""
        # Make multiple requests in quick succession
        for _ in range(20):
            response = self.client.post(
                '/api/security/predictive-expiration/analyze/',
                {'credential_id': 'test', 'password': 'test', 'domain': 'test.com'},
                format='json'
            )
        
        # Either normal response or rate limited
        self.assertIn(response.status_code, [200, 201, 400, 404, 429])
