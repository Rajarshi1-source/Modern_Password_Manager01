"""
Time-Lock Encryption Tests
===========================

Comprehensive tests for time-lock capsules, VDF service, 
password wills, and escrow agreements.

@author Password Manager Team
@created 2026-01-22
"""

import json
from datetime import timedelta
from unittest.mock import patch, MagicMock

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth.models import User
from rest_framework.test import APITestCase, APIClient
from rest_framework import status


# =============================================================================
# VDF Service Tests
# =============================================================================

class VDFServiceTests(TestCase):
    """Tests for the Verifiable Delay Function service."""
    
    def setUp(self):
        from security.services.vdf_service import VDFService
        self.vdf_service = VDFService(
            modulus_bits=512,  # Smaller for faster tests
            iterations_per_second=1000
        )
    
    def test_generate_params(self):
        """Test VDF parameter generation."""
        params = self.vdf_service.generate_params(delay_seconds=1)
        
        self.assertIsNotNone(params.modulus)
        self.assertIsNotNone(params.challenge)
        self.assertGreater(params.iterations, 0)
        self.assertGreater(params.modulus, 0)
    
    def test_estimate_iterations(self):
        """Test iteration estimation for different delays."""
        # 1 second
        iters_1s = self.vdf_service.estimate_iterations(1)
        self.assertEqual(iters_1s, 1000)
        
        # 10 seconds
        iters_10s = self.vdf_service.estimate_iterations(10)
        self.assertEqual(iters_10s, 10000)
    
    def test_estimate_time(self):
        """Test time estimation for different hardware."""
        estimates = self.vdf_service.estimate_time(100000)
        
        self.assertIn('laptop', estimates)
        self.assertIn('smartphone', estimates)
        self.assertIn('seconds', estimates['laptop'])
    
    def test_compute_small_vdf(self):
        """Test VDF computation with small iteration count."""
        params = self.vdf_service.generate_params(delay_seconds=1)
        params.iterations = 100  # Very small for testing
        
        output = self.vdf_service.compute(params)
        
        self.assertIsNotNone(output.output)
        self.assertIsNotNone(output.proof)
        self.assertGreater(output.computation_time, 0)
    
    def test_verify_vdf(self):
        """Test VDF verification."""
        params = self.vdf_service.generate_params(delay_seconds=1)
        params.iterations = 100
        
        output = self.vdf_service.compute(params)
        verification = self.vdf_service.verify(params, output)
        
        self.assertTrue(verification.is_valid)
        self.assertGreater(verification.verification_time_ms, 0)
    
    def test_invalid_proof_fails_verification(self):
        """Test that invalid proofs fail verification."""
        from security.services.vdf_service import VDFOutput
        
        params = self.vdf_service.generate_params(delay_seconds=1)
        params.iterations = 100
        
        # Create fake output
        fake_output = VDFOutput(
            output=12345,
            proof=67890,
            iterations=100,
            computation_time=1.0
        )
        
        verification = self.vdf_service.verify(params, fake_output)
        self.assertFalse(verification.is_valid)
    
    def test_progress_callback(self):
        """Test progress callback during computation."""
        params = self.vdf_service.generate_params(delay_seconds=1)
        params.iterations = 100
        
        progress_values = []
        def callback(progress, iterations):
            progress_values.append(progress)
        
        self.vdf_service.compute(params, progress_callback=callback)
        
        self.assertGreater(len(progress_values), 0)


# =============================================================================
# Time-Lock Capsule API Tests
# =============================================================================

class TimeLockCapsuleAPITests(APITestCase):
    """Tests for time-lock capsule API endpoints."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
    
    @patch('security.api.time_lock_views.time_lock_service')
    def test_create_capsule(self, mock_service):
        """Test creating a new time-lock capsule."""
        mock_service.create_time_lock.return_value = MagicMock(
            encrypted_data=b'encrypted',
            encryption_key_encrypted=b'key'
        )
        
        data = {
            'title': 'Test Capsule',
            'description': 'A test time-lock',
            'secret_data': 'my secret password',
            'delay_seconds': 3600,
            'mode': 'server',
            'capsule_type': 'general'
        }
        
        response = self.client.post('/api/security/timelock/capsules/', data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['title'], 'Test Capsule')
        self.assertEqual(response.data['status'], 'locked')
    
    def test_list_capsules(self):
        """Test listing user's capsules."""
        from security.models import TimeLockCapsule
        
        # Create test capsule
        TimeLockCapsule.objects.create(
            owner=self.user,
            title='Test Capsule',
            encrypted_data=b'data',
            encryption_key_encrypted=b'key',
            unlock_at=timezone.now() + timedelta(hours=1),
            delay_seconds=3600,
            mode='server',
            status='locked',
            capsule_type='general'
        )
        
        response = self.client.get('/api/security/timelock/capsules/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['capsules']), 1)
        self.assertEqual(response.data['locked_count'], 1)
    
    def test_get_capsule_status(self):
        """Test getting capsule status."""
        from security.models import TimeLockCapsule
        
        capsule = TimeLockCapsule.objects.create(
            owner=self.user,
            title='Status Test',
            encrypted_data=b'data',
            encryption_key_encrypted=b'key',
            unlock_at=timezone.now() + timedelta(hours=1),
            delay_seconds=3600,
            mode='server',
            status='locked',
            capsule_type='general'
        )
        
        response = self.client.get(f'/api/security/timelock/capsules/{capsule.id}/status/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'locked')
        self.assertFalse(response.data['can_unlock'])
        self.assertGreater(response.data['time_remaining_seconds'], 0)
    
    def test_unlock_early_fails(self):
        """Test that unlocking before time fails."""
        from security.models import TimeLockCapsule
        
        capsule = TimeLockCapsule.objects.create(
            owner=self.user,
            title='Early Unlock Test',
            encrypted_data=b'data',
            encryption_key_encrypted=b'key',
            unlock_at=timezone.now() + timedelta(hours=1),
            delay_seconds=3600,
            mode='server',
            status='locked',
            capsule_type='general'
        )
        
        response = self.client.post(f'/api/security/timelock/capsules/{capsule.id}/unlock/')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('still locked', response.data['error'])
    
    def test_unlock_ready_capsule(self):
        """Test unlocking a capsule that's ready."""
        from security.models import TimeLockCapsule
        
        capsule = TimeLockCapsule.objects.create(
            owner=self.user,
            title='Ready Capsule',
            encrypted_data=b'data',
            encryption_key_encrypted=b'key',
            unlock_at=timezone.now() - timedelta(hours=1),  # Past
            delay_seconds=3600,
            mode='server',
            status='locked',
            capsule_type='general'
        )
        
        response = self.client.post(f'/api/security/timelock/capsules/{capsule.id}/unlock/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        
        capsule.refresh_from_db()
        self.assertEqual(capsule.status, 'unlocked')
    
    def test_cancel_capsule(self):
        """Test cancelling a locked capsule."""
        from security.models import TimeLockCapsule
        
        capsule = TimeLockCapsule.objects.create(
            owner=self.user,
            title='Cancel Test',
            encrypted_data=b'data',
            encryption_key_encrypted=b'key',
            unlock_at=timezone.now() + timedelta(hours=1),
            delay_seconds=3600,
            mode='server',
            status='locked',
            capsule_type='general'
        )
        
        response = self.client.post(f'/api/security/timelock/capsules/{capsule.id}/cancel/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        capsule.refresh_from_db()
        self.assertEqual(capsule.status, 'cancelled')


# =============================================================================
# Password Will Tests
# =============================================================================

class PasswordWillAPITests(APITestCase):
    """Tests for password will functionality."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='willuser',
            email='will@example.com',
            password='testpass123'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
    
    @patch('security.api.time_lock_views.time_lock_service')
    def test_create_password_will(self, mock_service):
        """Test creating a password will."""
        mock_service.create_time_lock.return_value = MagicMock(
            encrypted_data=b'encrypted',
            encryption_key_encrypted=b'key'
        )
        
        data = {
            'title': 'My Digital Will',
            'secret_data': 'all my passwords here',
            'trigger_type': 'inactivity',
            'inactivity_days': 30,
            'check_in_reminder_days': 7,
            'beneficiaries': [
                {
                    'email': 'spouse@example.com',
                    'name': 'My Spouse',
                    'relationship': 'Spouse',
                    'access_level': 'full'
                }
            ],
            'notes': 'Please use these wisely'
        }
        
        response = self.client.post('/api/security/timelock/wills/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['trigger_type'], 'inactivity')
        self.assertEqual(response.data['inactivity_days'], 30)
    
    def test_list_wills(self):
        """Test listing password wills."""
        from security.models import TimeLockCapsule, PasswordWill
        
        capsule = TimeLockCapsule.objects.create(
            owner=self.user,
            title='Will Capsule',
            encrypted_data=b'data',
            encryption_key_encrypted=b'key',
            unlock_at=timezone.now() + timedelta(days=30),
            delay_seconds=2592000,
            mode='server',
            status='locked',
            capsule_type='will'
        )
        
        PasswordWill.objects.create(
            owner=self.user,
            capsule=capsule,
            trigger_type='inactivity',
            inactivity_days=30,
            is_active=True
        )
        
        response = self.client.get('/api/security/timelock/wills/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['wills']), 1)
        self.assertEqual(response.data['active_count'], 1)
    
    def test_check_in(self):
        """Test checking in to reset dead man's switch."""
        from security.models import TimeLockCapsule, PasswordWill
        
        old_time = timezone.now() - timedelta(days=10)
        
        capsule = TimeLockCapsule.objects.create(
            owner=self.user,
            title='Check-in Test',
            encrypted_data=b'data',
            encryption_key_encrypted=b'key',
            unlock_at=timezone.now() + timedelta(days=20),
            delay_seconds=2592000,
            mode='server',
            status='locked',
            capsule_type='will'
        )
        
        will = PasswordWill.objects.create(
            owner=self.user,
            capsule=capsule,
            trigger_type='inactivity',
            inactivity_days=30,
            last_check_in=old_time,
            is_active=True
        )
        
        response = self.client.post(f'/api/security/timelock/wills/{will.id}/checkin/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        
        will.refresh_from_db()
        self.assertGreater(will.last_check_in, old_time)


# =============================================================================
# Escrow Agreement Tests
# =============================================================================

class EscrowAPITests(APITestCase):
    """Tests for escrow agreement functionality."""
    
    def setUp(self):
        self.user1 = User.objects.create_user(
            username='party1', email='party1@example.com', password='pass123'
        )
        self.user2 = User.objects.create_user(
            username='party2', email='party2@example.com', password='pass123'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user1)
    
    @patch('security.api.time_lock_views.time_lock_service')
    def test_create_escrow(self, mock_service):
        """Test creating an escrow agreement."""
        mock_service.create_time_lock.return_value = MagicMock(
            encrypted_data=b'encrypted',
            encryption_key_encrypted=b'key'
        )
        
        data = {
            'title': 'Business Agreement',
            'description': 'Contract secrets',
            'secret_data': 'confidential terms',
            'release_condition': 'all_approve',
            'party_emails': ['party2@example.com']
        }
        
        response = self.client.post('/api/security/timelock/escrows/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['title'], 'Business Agreement')
    
    def test_approve_escrow(self):
        """Test approving an escrow release."""
        from security.models import TimeLockCapsule, EscrowAgreement
        
        capsule = TimeLockCapsule.objects.create(
            owner=self.user1,
            title='Escrow Capsule',
            encrypted_data=b'data',
            encryption_key_encrypted=b'key',
            unlock_at=timezone.now() + timedelta(days=30),
            delay_seconds=2592000,
            mode='server',
            status='locked',
            capsule_type='escrow'
        )
        
        escrow = EscrowAgreement.objects.create(
            capsule=capsule,
            title='Test Escrow',
            release_condition='all_approve'
        )
        escrow.parties.add(self.user1, self.user2)
        
        # Authenticate as party2 and approve
        self.client.force_authenticate(user=self.user2)
        
        response = self.client.post(f'/api/security/timelock/escrows/{escrow.id}/approve/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['approved'])
        
        escrow.refresh_from_db()
        self.assertIn(self.user2.id, escrow.approved_by)


# =============================================================================
# Model Tests
# =============================================================================

class TimeLockModelTests(TestCase):
    """Tests for time-lock models."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='modeltest',
            email='model@example.com',
            password='testpass123'
        )
    
    def test_capsule_time_remaining(self):
        """Test time_remaining_seconds property."""
        from security.models import TimeLockCapsule
        
        capsule = TimeLockCapsule.objects.create(
            owner=self.user,
            title='Time Test',
            encrypted_data=b'data',
            encryption_key_encrypted=b'key',
            unlock_at=timezone.now() + timedelta(hours=2),
            delay_seconds=7200,
            mode='server',
            status='locked',
            capsule_type='general'
        )
        
        # Should be approximately 7200 seconds
        self.assertGreater(capsule.time_remaining_seconds, 7000)
        self.assertLess(capsule.time_remaining_seconds, 7300)
    
    def test_capsule_is_ready_to_unlock(self):
        """Test is_ready_to_unlock property."""
        from security.models import TimeLockCapsule
        
        # Future capsule
        future_capsule = TimeLockCapsule.objects.create(
            owner=self.user,
            title='Future',
            encrypted_data=b'data',
            encryption_key_encrypted=b'key',
            unlock_at=timezone.now() + timedelta(hours=1),
            delay_seconds=3600,
            mode='server',
            status='locked',
            capsule_type='general'
        )
        self.assertFalse(future_capsule.is_ready_to_unlock)
        
        # Past capsule
        past_capsule = TimeLockCapsule.objects.create(
            owner=self.user,
            title='Past',
            encrypted_data=b'data',
            encryption_key_encrypted=b'key',
            unlock_at=timezone.now() - timedelta(hours=1),
            delay_seconds=3600,
            mode='server',
            status='locked',
            capsule_type='general'
        )
        self.assertTrue(past_capsule.is_ready_to_unlock)
    
    def test_password_will_days_until_trigger(self):
        """Test days_until_trigger calculation."""
        from security.models import TimeLockCapsule, PasswordWill
        
        capsule = TimeLockCapsule.objects.create(
            owner=self.user,
            title='Will Capsule',
            encrypted_data=b'data',
            encryption_key_encrypted=b'key',
            unlock_at=timezone.now() + timedelta(days=30),
            delay_seconds=2592000,
            mode='server',
            status='locked',
            capsule_type='will'
        )
        
        will = PasswordWill.objects.create(
            owner=self.user,
            capsule=capsule,
            trigger_type='inactivity',
            inactivity_days=30,
            last_check_in=timezone.now(),
            is_active=True
        )
        
        # Should be approximately 30 days
        self.assertGreater(will.days_until_trigger, 28)
        self.assertLess(will.days_until_trigger, 31)
    
    def test_escrow_can_release(self):
        """Test escrow can_release logic."""
        from security.models import TimeLockCapsule, EscrowAgreement
        
        capsule = TimeLockCapsule.objects.create(
            owner=self.user,
            title='Escrow Capsule',
            encrypted_data=b'data',
            encryption_key_encrypted=b'key',
            unlock_at=timezone.now() + timedelta(days=30),
            delay_seconds=2592000,
            mode='server',
            status='locked',
            capsule_type='escrow'
        )
        
        user2 = User.objects.create_user('user2', 'u2@example.com', 'pass')
        
        # All approve condition
        escrow = EscrowAgreement.objects.create(
            capsule=capsule,
            title='Test Escrow',
            release_condition='all_approve'
        )
        escrow.parties.add(self.user, user2)
        
        # No approvals yet
        self.assertFalse(escrow.can_release)
        
        # One approval
        escrow.approve(self.user.id)
        self.assertFalse(escrow.can_release)
        
        # Both approved
        escrow.approve(user2.id)
        self.assertTrue(escrow.can_release)
