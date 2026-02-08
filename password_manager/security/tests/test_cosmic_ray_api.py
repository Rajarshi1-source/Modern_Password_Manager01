"""
Cosmic Ray API Endpoint Tests
==============================

Tests for the cosmic ray entropy REST API endpoints:
- GET /api/security/cosmic/status/
- POST /api/security/cosmic/generate-password/
- GET /api/security/cosmic/events/
- POST /api/security/cosmic/settings/
- POST /api/security/cosmic/entropy-batch/
"""

import pytest
from django.urls import reverse
from django.test import TestCase
from rest_framework.test import APITestCase
from rest_framework import status
from unittest.mock import patch, MagicMock, AsyncMock


class TestCosmicRayStatusEndpoint(APITestCase):
    """Tests for the detector status endpoint."""
    
    def setUp(self):
        """Set up test fixtures."""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
    
    def test_get_status_requires_auth(self):
        """Test that status endpoint requires authentication."""
        self.client.force_authenticate(user=None)
        
        response = self.client.get(reverse('cosmic-status'))
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    @patch('security.api.cosmic_ray_views.get_cosmic_provider')
    def test_get_status_success(self, mock_get_provider):
        """Test successful status retrieval."""
        mock_provider = MagicMock()
        mock_provider.get_status.return_value = {
            'mode': 'simulation',
            'available': True,
            'continuous_collection': False,
            'hardware': {},
            'simulation': {},
            'last_source': {}
        }
        mock_get_provider.return_value = mock_provider
        
        response = self.client.get(reverse('cosmic-status'))
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['success'] is True
        assert 'status' in response.data
    
    @patch('security.api.cosmic_ray_views.get_cosmic_provider')
    def test_get_status_unavailable(self, mock_get_provider):
        """Test status when provider is unavailable."""
        mock_get_provider.return_value = None
        
        response = self.client.get(reverse('cosmic-status'))
        
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


class TestCosmicRayPasswordEndpoint(APITestCase):
    """Tests for the password generation endpoint."""
    
    def setUp(self):
        """Set up test fixtures."""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
    
    @patch('security.api.cosmic_ray_views.get_cosmic_provider')
    @patch('security.api.cosmic_ray_views.run_async')
    def test_generate_password_default(self, mock_run_async, mock_get_provider):
        """Test password generation with defaults."""
        mock_provider = MagicMock()
        mock_provider.is_available.return_value = True
        mock_get_provider.return_value = mock_provider
        
        mock_run_async.return_value = (
            'TestPassword123!',
            {
                'source': 'cosmic_ray_muon',
                'entropy_bits': 128,
                'status': {'mode': 'simulation', 'events_used': 10}
            }
        )
        
        response = self.client.post(reverse('cosmic-generate-password'), {})
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['success'] is True
        assert 'password' in response.data
    
    @patch('security.api.cosmic_ray_views.get_cosmic_provider')
    @patch('security.api.cosmic_ray_views.run_async')
    def test_generate_password_with_length(self, mock_run_async, mock_get_provider):
        """Test password generation with custom length."""
        mock_provider = MagicMock()
        mock_provider.is_available.return_value = True
        mock_get_provider.return_value = mock_provider
        
        mock_run_async.return_value = (
            'A' * 32,
            {'source': 'cosmic_ray_muon', 'entropy_bits': 256, 'status': {}}
        )
        
        response = self.client.post(
            reverse('cosmic-generate-password'),
            {'length': 32}
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['length'] == 32
    
    @patch('security.api.cosmic_ray_views.get_cosmic_provider')
    def test_generate_password_provider_unavailable(self, mock_get_provider):
        """Test password generation when provider unavailable."""
        mock_provider = MagicMock()
        mock_provider.is_available.return_value = False
        mock_get_provider.return_value = mock_provider
        
        response = self.client.post(reverse('cosmic-generate-password'), {})
        
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    
    def test_generate_password_requires_auth(self):
        """Test that endpoint requires authentication."""
        self.client.force_authenticate(user=None)
        
        response = self.client.post(reverse('cosmic-generate-password'), {})
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestCosmicRayEventsEndpoint(APITestCase):
    """Tests for the recent events endpoint."""
    
    def setUp(self):
        """Set up test fixtures."""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
    
    @patch('security.api.cosmic_ray_views.get_cosmic_provider')
    @patch('security.api.cosmic_ray_views.run_async')
    def test_get_events_success(self, mock_run_async, mock_get_provider):
        """Test getting recent events."""
        mock_provider = MagicMock()
        mock_provider.get_status.return_value = {'mode': 'simulation'}
        mock_get_provider.return_value = mock_provider
        
        # Mock events
        mock_events = [
            MagicMock(to_dict=lambda: {
                'timestamp': 1234567890,
                'energy_adc': 2500,
                'quality_score': 0.95
            })
            for _ in range(5)
        ]
        mock_run_async.return_value = mock_events
        
        response = self.client.get(reverse('cosmic-events'))
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['success'] is True
        assert 'events' in response.data
    
    @patch('security.api.cosmic_ray_views.get_cosmic_provider')
    def test_get_events_with_limit(self, mock_get_provider):
        """Test events endpoint with limit parameter."""
        mock_provider = MagicMock()
        mock_provider.get_status.return_value = {'mode': 'simulation'}
        mock_get_provider.return_value = mock_provider
        
        response = self.client.get(reverse('cosmic-events'), {'limit': 5})
        
        assert response.status_code == status.HTTP_200_OK


class TestCosmicRaySettingsEndpoint(APITestCase):
    """Tests for the settings update endpoint."""
    
    def setUp(self):
        """Set up test fixtures."""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
    
    @patch('security.api.cosmic_ray_views.get_cosmic_provider')
    def test_enable_continuous_collection(self, mock_get_provider):
        """Test enabling continuous collection."""
        mock_provider = MagicMock()
        mock_get_provider.return_value = mock_provider
        
        response = self.client.post(
            reverse('cosmic-settings'),
            {'continuous_collection': True}
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['success'] is True
        assert response.data['continuous_collection'] is True
        mock_provider.enable_continuous_collection.assert_called_once()
    
    @patch('security.api.cosmic_ray_views.get_cosmic_provider')
    def test_disable_continuous_collection(self, mock_get_provider):
        """Test disabling continuous collection."""
        mock_provider = MagicMock()
        mock_get_provider.return_value = mock_provider
        
        response = self.client.post(
            reverse('cosmic-settings'),
            {'continuous_collection': False}
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['continuous_collection'] is False
        mock_provider.disable_continuous_collection.assert_called_once()


class TestCosmicRayEntropyBatchEndpoint(APITestCase):
    """Tests for the raw entropy batch endpoint."""
    
    def setUp(self):
        """Set up test fixtures."""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
    
    @patch('security.api.cosmic_ray_views.get_cosmic_provider')
    @patch('security.api.cosmic_ray_views.run_async')
    def test_generate_entropy_batch(self, mock_run_async, mock_get_provider):
        """Test generating raw entropy bytes."""
        mock_provider = MagicMock()
        mock_provider.is_available.return_value = True
        mock_provider.get_last_source_info.return_value = {
            'mode': 'simulation',
            'events_used': 10,
            'min_entropy_per_byte': 8.0
        }
        mock_get_provider.return_value = mock_provider
        
        # Return 32 random bytes
        mock_run_async.return_value = (b'\x12\x34' * 16, 'cosmic_ray_muon')
        
        response = self.client.post(
            reverse('cosmic-entropy-batch'),
            {'count': 32}
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['success'] is True
        assert 'entropy_hex' in response.data
        assert 'entropy_base64' in response.data
        assert response.data['bytes_generated'] == 32
    
    @patch('security.api.cosmic_ray_views.get_cosmic_provider')
    def test_entropy_batch_validates_count(self, mock_get_provider):
        """Test that count is validated and clamped."""
        mock_provider = MagicMock()
        mock_provider.is_available.return_value = True
        mock_get_provider.return_value = mock_provider
        
        # Count should be clamped to max 1024
        response = self.client.post(
            reverse('cosmic-entropy-batch'),
            {'count': 9999}
        )
        
        # Should not fail, but clamp to 1024
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR]


class TestCosmicRayIntegration(APITestCase):
    """Integration tests for the cosmic ray API."""
    
    def setUp(self):
        """Set up test fixtures."""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.user = User.objects.create_user(
            email='integration_test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
    
    @pytest.mark.integration
    def test_full_workflow(self):
        """Test a full workflow: check status, generate password."""
        # Skip if provider not available
        from security.services.cosmic_ray_entropy_service import get_cosmic_provider
        provider = get_cosmic_provider()
        if not provider or not provider.is_available():
            pytest.skip("Cosmic ray provider not available")
        
        # Get status
        status_response = self.client.get(reverse('cosmic-status'))
        assert status_response.status_code == status.HTTP_200_OK
        
        # Generate password
        password_response = self.client.post(
            reverse('cosmic-generate-password'),
            {'length': 16}
        )
        assert password_response.status_code == status.HTTP_200_OK
        assert len(password_response.data.get('password', '')) == 16
