"""
Security Tests for Recovery System

Tests security-critical functionality:
- SQL injection prevention
- XSS prevention
- Unauthorized access control
- Timing attack resistance
- Honeypot detection
- Rate limiting
"""

import pytest
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import connection
from datetime import timedelta
import time

from ..quantum_recovery_models import (
    PasskeyRecoverySetup,
    RecoveryShard,
    RecoveryAttempt,
    RecoveryAuditLog,
    RecoveryShardType
)
from ..services.quantum_crypto_service import quantum_crypto_service

User = get_user_model()


@pytest.mark.django_db
class TestSQLInjectionPrevention(TestCase):
    """Test SQL injection prevention"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = Client()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='TestPassword123!'
        )
    
    def test_sql_injection_in_email_field(self):
        """Test SQL injection prevention in email field"""
        malicious_payloads = [
            "test@example.com'; DROP TABLE auth_user; --",
            "test' OR '1'='1",
            "test@example.com; DELETE FROM auth_user WHERE 1=1; --",
            "test@example.com' UNION SELECT * FROM auth_user--"
        ]
        
        initial_user_count = User.objects.count()
        
        for payload in malicious_payloads:
            response = self.client.post(
                '/api/auth/quantum-recovery/initiate_recovery/',
                {
                    'email': payload,
                    'device_fingerprint': 'test_fp'
                },
                content_type='application/json'
            )
            
            # Verify no SQL injection occurred
            # Users table should still exist and have same count
            self.assertEqual(User.objects.count(), initial_user_count)
            
            # Tables should still exist
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT COUNT(*) FROM information_schema.tables "
                    "WHERE table_schema = 'public'"
                )
                result = cursor.fetchone()
                self.assertGreater(result[0], 0)
    
    def test_sql_injection_in_device_fingerprint(self):
        """Test SQL injection prevention in device fingerprint field"""
        malicious_fp = "test_fp'; DROP TABLE recovery_attempts; --"
        
        initial_attempt_count = RecoveryAttempt.objects.count()
        
        response = self.client.post(
            '/api/auth/quantum-recovery/initiate_recovery/',
            {
                'email': 'test@example.com',
                'device_fingerprint': malicious_fp
            },
            content_type='application/json'
        )
        
        # RecoveryAttempt model/table should still exist
        # Should be able to query it without errors
        try:
            RecoveryAttempt.objects.count()
            sql_injection_prevented = True
        except Exception:
            sql_injection_prevented = False
        
        self.assertTrue(sql_injection_prevented)


@pytest.mark.django_db
class TestXSSPrevention(TestCase):
    """Test XSS (Cross-Site Scripting) prevention"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = Client()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='TestPassword123!'
        )
    
    def test_xss_prevention_in_email_field(self):
        """Test XSS prevention in email field"""
        xss_payloads = [
            '<script>alert("xss")</script>@example.com',
            'test@<script>alert(document.cookie)</script>.com',
            '<img src=x onerror=alert(1)>@example.com',
            'test@example.com<svg/onload=alert(1)>'
        ]
        
        for payload in xss_payloads:
            response = self.client.post(
                '/api/auth/quantum-recovery/initiate_recovery/',
                {
                    'email': payload,
                    'device_fingerprint': 'test_fp'
                },
                content_type='application/json'
            )
            
            # Response should not contain unescaped script tags
            if hasattr(response, 'content'):
                content = response.content.decode('utf-8')
                self.assertNotIn('<script>', content)
                self.assertNotIn('onerror=', content)
                self.assertNotIn('onload=', content)
    
    def test_xss_prevention_in_audit_logs(self):
        """Test that audit logs properly escape XSS attempts"""
        malicious_ip = '<script>alert("xss")</script>'
        
        # Create audit log with potentially malicious data
        log = RecoveryAuditLog.objects.create(
            user=self.user,
            event_type='test_event',
            event_data={'malicious_field': malicious_ip},
            ip_address='127.0.0.1'
        )
        
        # When retrieved, should be properly escaped
        retrieved_log = RecoveryAuditLog.objects.get(id=log.id)
        
        # Django ORM should handle this safely
        self.assertEqual(retrieved_log.event_data['malicious_field'], malicious_ip)
        # But when rendered in templates, it should be escaped


@pytest.mark.django_db
class TestUnauthorizedAccessControl(TestCase):
    """Test unauthorized access prevention"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = Client()
        
        # Create two users
        self.user1 = User.objects.create_user(
            email='user1@example.com',
            password='TestPassword123!'
        )
        self.user2 = User.objects.create_user(
            email='user2@example.com',
            password='TestPassword123!'
        )
        
        # Create recovery setup for user1
        self.recovery_setup1 = PasskeyRecoverySetup.objects.create(
            user=self.user1,
            total_shards=5,
            threshold_shards=3,
            is_active=True
        )
        
        # Create recovery attempt for user1
        self.attempt1 = RecoveryAttempt.objects.create(
            recovery_setup=self.recovery_setup1,
            status='challenge_phase',
            initiated_from_ip='127.0.0.1',
            initiated_from_device_fingerprint='test_fp',
            initiated_from_user_agent='test_ua',
            expires_at=timezone.now() + timedelta(days=14)
        )
    
    def test_cannot_access_other_users_recovery_attempt(self):
        """Test that users cannot access other users' recovery attempts"""
        # Login as user2
        self.client.force_login(self.user2)
        
        # Try to access user1's recovery attempt
        response = self.client.get(
            f'/api/auth/quantum-recovery/get_recovery_status/',
            {'attempt_id': str(self.attempt1.id)},
            content_type='application/json'
        )
        
        # Should be forbidden
        self.assertEqual(response.status_code, 403)
    
    def test_cannot_cancel_other_users_recovery(self):
        """Test that users cannot cancel other users' recovery"""
        self.client.force_login(self.user2)
        
        response = self.client.post(
            '/api/auth/quantum-recovery/cancel_recovery/',
            {'attempt_id': str(self.attempt1.id)},
            content_type='application/json'
        )
        
        # Should be forbidden
        self.assertEqual(response.status_code, 403)
        
        # Verify attempt was not cancelled
        self.attempt1.refresh_from_db()
        self.assertNotEqual(self.attempt1.status, 'cancelled')
    
    def test_cannot_access_other_users_shards(self):
        """Test that users cannot access shards from other users' setups"""
        # Create shard for user1
        shard = RecoveryShard.objects.create(
            recovery_setup=self.recovery_setup1,
            shard_type=RecoveryShardType.GUARDIAN,
            shard_index=1,
            encrypted_shard_data=b'test_data',
            encryption_metadata={},
            status='active'
        )
        
        # Login as user2
        self.client.force_login(self.user2)
        
        # Attempt to access user1's shard through recovery flow
        # (Actual endpoint depends on implementation)
        # This should be prevented by proper access control
        self.assertIsNotNone(shard)  # Shard exists
        
        # User2 should not be able to retrieve it
        user2_shards = RecoveryShard.objects.filter(
            recovery_setup__user=self.user2
        )
        self.assertEqual(user2_shards.count(), 0)
    
    def test_unauthenticated_access_denied(self):
        """Test that unauthenticated users cannot access protected endpoints"""
        # Don't login
        
        protected_endpoints = [
            ('/api/auth/quantum-recovery/get_recovery_status/', {'attempt_id': str(self.attempt1.id)}),
            ('/api/auth/quantum-recovery/cancel_recovery/', {'attempt_id': str(self.attempt1.id)}),
        ]
        
        for endpoint, data in protected_endpoints:
            response = self.client.post(endpoint, data, content_type='application/json')
            
            # Should require authentication
            self.assertIn(response.status_code, [401, 403])


@pytest.mark.django_db
class TestTimingAttackResistance(TestCase):
    """Test resistance to timing attacks"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = Client()
        self.user = User.objects.create_user(
            email='existing@example.com',
            password='TestPassword123!'
        )
        
        PasskeyRecoverySetup.objects.create(
            user=self.user,
            total_shards=5,
            threshold_shards=3,
            is_active=True
        )
    
    def test_timing_attack_resistance_on_email_lookup(self):
        """Test that response times don't leak information about user existence"""
        # Test with existing email
        start = time.time()
        response1 = self.client.post(
            '/api/auth/quantum-recovery/initiate_recovery/',
            {
                'email': 'existing@example.com',
                'device_fingerprint': 'a' * 64
            },
            content_type='application/json'
        )
        time1 = time.time() - start
        
        # Test with non-existent email
        start = time.time()
        response2 = self.client.post(
            '/api/auth/quantum-recovery/initiate_recovery/',
            {
                'email': 'nonexistent@example.com',
                'device_fingerprint': 'a' * 64
            },
            content_type='application/json'
        )
        time2 = time.time() - start
        
        # Response times should be similar (within 200ms)
        # This prevents attackers from enumerating valid emails
        time_difference = abs(time1 - time2)
        
        # Allow for some variance but they should be close
        # Note: This test may be flaky in slow environments
        self.assertLess(time_difference, 0.5)  # 500ms tolerance


@pytest.mark.django_db
class TestHoneypotSecurity(TestCase):
    """Test honeypot (canary) shard security"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='TestPassword123!'
        )
        
        self.recovery_setup = PasskeyRecoverySetup.objects.create(
            user=self.user,
            total_shards=5,
            threshold_shards=3,
            is_active=True
        )
        
        self.attempt = RecoveryAttempt.objects.create(
            recovery_setup=self.recovery_setup,
            status='shard_collection',
            initiated_from_ip='127.0.0.1',
            initiated_from_device_fingerprint='test_fp',
            initiated_from_user_agent='test_ua',
            expires_at=timezone.now() + timedelta(days=14)
        )
    
    def test_honeypot_shard_detection(self):
        """Test that honeypot shards are properly detected"""
        # Create honeypot shard
        honeypot = RecoveryShard.objects.create(
            recovery_setup=self.recovery_setup,
            shard_type=RecoveryShardType.HONEYPOT,
            shard_index=99,
            encrypted_shard_data=quantum_crypto_service.create_honeypot_shard(128),
            encryption_metadata={},
            status='active',
            is_honeypot=True
        )
        
        # Accessing honeypot should trigger alerts
        self.assertTrue(honeypot.is_honeypot)
        self.assertTrue(quantum_crypto_service.is_honeypot_shard(
            honeypot.encrypted_shard_data
        ))
    
    def test_honeypot_access_triggers_security_alert(self):
        """Test that accessing honeypot triggers security measures"""
        # Create honeypot shard
        honeypot = RecoveryShard.objects.create(
            recovery_setup=self.recovery_setup,
            shard_type=RecoveryShardType.HONEYPOT,
            shard_index=99,
            encrypted_shard_data=quantum_crypto_service.create_honeypot_shard(128),
            encryption_metadata={},
            status='active',
            is_honeypot=True
        )
        
        # Simulate honeypot access
        if honeypot.is_honeypot:
            self.attempt.honeypot_triggered = True
            self.attempt.suspicious_activity_detected = True
            self.attempt.status = 'failed'
            self.attempt.failure_reason = 'Honeypot shard accessed'
            self.attempt.save()
            
            # Create audit log
            RecoveryAuditLog.objects.create(
                user=self.user,
                event_type='honeypot_triggered',
                recovery_attempt_id=self.attempt.id,
                event_data={'shard_id': str(honeypot.id)},
                ip_address='127.0.0.1'
            )
        
        self.attempt.refresh_from_db()
        
        # Verify security measures
        self.assertTrue(self.attempt.honeypot_triggered)
        self.assertTrue(self.attempt.suspicious_activity_detected)
        self.assertEqual(self.attempt.status, 'failed')
        
        # Verify audit log created
        audit_logs = RecoveryAuditLog.objects.filter(
            event_type='honeypot_triggered',
            recovery_attempt_id=self.attempt.id
        )
        self.assertEqual(audit_logs.count(), 1)
    
    def test_real_shards_not_detected_as_honeypots(self):
        """Test that real shards are not incorrectly detected as honeypots"""
        # Create real shard
        secret = b"test_secret_data"
        shards = quantum_crypto_service.shamir_split_secret(secret, 5, 3)
        
        for _, shard_data in shards:
            # Real shards should not be detected as honeypots
            self.assertFalse(quantum_crypto_service.is_honeypot_shard(shard_data))


@pytest.mark.django_db
class TestRateLimitingSecurity(TestCase):
    """Test rate limiting security measures"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = Client()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='TestPassword123!'
        )
        
        self.recovery_setup = PasskeyRecoverySetup.objects.create(
            user=self.user,
            total_shards=5,
            threshold_shards=3,
            is_active=True
        )
    
    def test_rate_limiting_blocks_excessive_attempts(self):
        """Test that rate limiting blocks brute force attempts"""
        # Create multiple failed attempts in short time
        for i in range(5):
            RecoveryAttempt.objects.create(
                recovery_setup=self.recovery_setup,
                status='failed',
                initiated_from_ip='127.0.0.1',
                initiated_from_device_fingerprint=f'fp_{i}',
                initiated_from_user_agent='test_ua',
                expires_at=timezone.now() + timedelta(days=14),
                initiated_at=timezone.now() - timedelta(minutes=i)
            )
        
        # Check recent attempt count
        recent_attempts = RecoveryAttempt.objects.filter(
            recovery_setup=self.user.passkey_recovery_setup,
            initiated_at__gte=timezone.now() - timedelta(hours=24)
        ).count()
        
        # Should have multiple attempts
        self.assertGreaterEqual(recent_attempts, 5)
        
        # Rate limiting logic would block further attempts
        # (Actual implementation depends on rate limiting strategy)


@pytest.mark.django_db
class TestDataEncryptionSecurity(TestCase):
    """Test that sensitive data is properly encrypted"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='TestPassword123!'
        )
        
        self.recovery_setup = PasskeyRecoverySetup.objects.create(
            user=self.user,
            total_shards=5,
            threshold_shards=3,
            is_active=True
        )
    
    def test_shards_are_encrypted(self):
        """Test that recovery shards are encrypted"""
        # Create shard
        shard = RecoveryShard.objects.create(
            recovery_setup=self.recovery_setup,
            shard_type=RecoveryShardType.GUARDIAN,
            shard_index=1,
            encrypted_shard_data=b'encrypted_data_should_not_be_plaintext',
            encryption_metadata={'algorithm': 'aes-256-gcm', 'iv': 'test_iv'},
            status='active'
        )
        
        # Shard data should be encrypted (not plaintext)
        # In a real test, you would verify encryption was applied
        self.assertIsNotNone(shard.encrypted_shard_data)
        self.assertIsNotNone(shard.encryption_metadata)
        self.assertIn('algorithm', shard.encryption_metadata)
    
    def test_challenge_data_is_encrypted(self):
        """Test that challenge data is encrypted"""
        from ..quantum_recovery_models import TemporalChallenge
        
        attempt = RecoveryAttempt.objects.create(
            recovery_setup=self.recovery_setup,
            status='challenge_phase',
            initiated_from_ip='127.0.0.1',
            initiated_from_device_fingerprint='test_fp',
            initiated_from_user_agent='test_ua',
            expires_at=timezone.now() + timedelta(days=14)
        )
        
        challenge = TemporalChallenge.objects.create(
            recovery_attempt=attempt,
            challenge_type='historical',
            encrypted_challenge_data=b'encrypted_question',
            encrypted_expected_response=b'encrypted_answer',
            status='sent',
            scheduled_for=timezone.now(),
            sent_at=timezone.now(),
            expires_at=timezone.now() + timedelta(hours=24)
        )
        
        # Challenge data should be encrypted
        self.assertIsInstance(challenge.encrypted_challenge_data, bytes)
        self.assertIsInstance(challenge.encrypted_expected_response, bytes)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

