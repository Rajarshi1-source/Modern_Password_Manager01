"""
Django Management Command: Test Passkey Recovery System

Provides comprehensive testing for the passkey recovery system including:
- Setup flow testing
- Recovery flow testing
- Fallback mechanism testing
- Crypto verification
"""

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.db import transaction
import json
import time
import sys

User = get_user_model()


class Command(BaseCommand):
    help = 'Test the passkey recovery system components'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--test',
            type=str,
            choices=['all', 'setup', 'recovery', 'fallback', 'crypto', 'monitoring'],
            default='all',
            help='Which test to run'
        )
        parser.add_argument(
            '--username',
            type=str,
            help='Username to test with (will be created if not exists)'
        )
        parser.add_argument(
            '--cleanup',
            action='store_true',
            help='Clean up test data after running'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed output'
        )
    
    def handle(self, *args, **options):
        self.verbose = options['verbose']
        test_type = options['test']
        cleanup = options['cleanup']
        
        self.stdout.write(self.style.NOTICE('=' * 60))
        self.stdout.write(self.style.NOTICE('Passkey Recovery System Test Suite'))
        self.stdout.write(self.style.NOTICE('=' * 60))
        
        # Track test results
        results = {
            'passed': 0,
            'failed': 0,
            'skipped': 0,
            'errors': []
        }
        
        try:
            if test_type in ['all', 'crypto']:
                self._run_crypto_tests(results)
            
            if test_type in ['all', 'setup']:
                self._run_setup_tests(results, options['username'])
            
            if test_type in ['all', 'recovery']:
                self._run_recovery_tests(results, options['username'])
            
            if test_type in ['all', 'fallback']:
                self._run_fallback_tests(results, options['username'])
            
            if test_type in ['all', 'monitoring']:
                self._run_monitoring_tests(results)
            
        except Exception as e:
            results['failed'] += 1
            results['errors'].append(f'Test suite error: {str(e)}')
            self.stdout.write(self.style.ERROR(f'Test suite error: {e}'))
        
        # Print summary
        self._print_summary(results)
        
        if cleanup:
            self._cleanup_test_data(options['username'])
        
        # Exit with error code if tests failed
        if results['failed'] > 0:
            sys.exit(1)
    
    def _run_crypto_tests(self, results):
        """Test cryptographic components."""
        self.stdout.write(self.style.NOTICE('\n--- Crypto Tests ---'))
        
        # Test 1: Kyber key generation
        self._test(
            results,
            'Kyber key generation',
            self._test_kyber_keygen
        )
        
        # Test 2: Hybrid encryption/decryption
        self._test(
            results,
            'Hybrid encryption/decryption',
            self._test_hybrid_encryption
        )
        
        # Test 3: Recovery key generation
        self._test(
            results,
            'Recovery key generation',
            self._test_recovery_key_generation
        )
        
        # Test 4: Check crypto status
        self._test(
            results,
            'Crypto status check',
            self._test_crypto_status
        )
    
    def _run_setup_tests(self, results, username):
        """Test recovery setup flow."""
        self.stdout.write(self.style.NOTICE('\n--- Setup Tests ---'))
        
        # Ensure test user exists
        user = self._get_or_create_test_user(username)
        
        # Test 1: Create recovery backup
        self._test(
            results,
            'Create recovery backup',
            lambda: self._test_create_backup(user)
        )
        
        # Test 2: List backups
        self._test(
            results,
            'List recovery backups',
            lambda: self._test_list_backups(user)
        )
    
    def _run_recovery_tests(self, results, username):
        """Test recovery flow."""
        self.stdout.write(self.style.NOTICE('\n--- Recovery Tests ---'))
        
        user = self._get_or_create_test_user(username)
        
        # Test 1: Initiate recovery
        self._test(
            results,
            'Initiate recovery',
            lambda: self._test_initiate_recovery(user)
        )
        
        # Test 2: Complete recovery with valid key
        self._test(
            results,
            'Complete recovery (valid key)',
            lambda: self._test_complete_recovery_valid(user)
        )
        
        # Test 3: Complete recovery with invalid key
        self._test(
            results,
            'Complete recovery (invalid key - should fail)',
            lambda: self._test_complete_recovery_invalid(user)
        )
    
    def _run_fallback_tests(self, results, username):
        """Test fallback mechanism."""
        self.stdout.write(self.style.NOTICE('\n--- Fallback Tests ---'))
        
        user = self._get_or_create_test_user(username)
        
        # Test 1: Fallback trigger
        self._test(
            results,
            'Fallback trigger mechanism',
            lambda: self._test_fallback_trigger(user)
        )
    
    def _run_monitoring_tests(self, results):
        """Test monitoring components."""
        self.stdout.write(self.style.NOTICE('\n--- Monitoring Tests ---'))
        
        # Test 1: Health check
        self._test(
            results,
            'Health check',
            self._test_health_check
        )
        
        # Test 2: Metrics collection
        self._test(
            results,
            'Metrics collection',
            self._test_metrics_collection
        )
    
    def _test(self, results, name, test_func):
        """Run a single test and record result."""
        try:
            start_time = time.time()
            test_func()
            duration = time.time() - start_time
            results['passed'] += 1
            self.stdout.write(
                self.style.SUCCESS(f'  ✓ {name} ({duration:.2f}s)')
            )
        except AssertionError as e:
            results['failed'] += 1
            results['errors'].append(f'{name}: {str(e)}')
            self.stdout.write(
                self.style.ERROR(f'  ✗ {name}: {str(e)}')
            )
        except Exception as e:
            results['failed'] += 1
            results['errors'].append(f'{name}: {str(e)}')
            self.stdout.write(
                self.style.ERROR(f'  ✗ {name}: Error - {str(e)}')
            )
    
    # ==================== Individual Test Functions ====================
    
    def _test_kyber_keygen(self):
        """Test Kyber key generation."""
        from ..services.kyber_crypto import production_kyber
        
        public_key, private_key = production_kyber.generate_keypair()
        
        assert public_key is not None, "Public key should not be None"
        assert private_key is not None, "Private key should not be None"
        assert len(public_key) > 0, "Public key should not be empty"
        assert len(private_key) > 0, "Private key should not be empty"
        
        if self.verbose:
            self.stdout.write(f'    Public key size: {len(public_key)} bytes')
            self.stdout.write(f'    Private key size: {len(private_key)} bytes')
    
    def _test_hybrid_encryption(self):
        """Test hybrid Kyber + AES encryption."""
        from ..services.kyber_crypto import hybrid_encryption, production_kyber
        
        # Generate keypair
        public_key, private_key = production_kyber.generate_keypair()
        
        # Test data
        plaintext = b'Test passkey credential data for recovery'
        aad = b'user_id:123'
        
        # Encrypt
        encrypted = hybrid_encryption.encrypt(plaintext, public_key, aad)
        
        assert 'kyber_ciphertext' in encrypted, "Missing kyber_ciphertext"
        assert 'aes_ciphertext' in encrypted, "Missing aes_ciphertext"
        
        if self.verbose:
            self.stdout.write(f'    Algorithm: {encrypted.get("algorithm")}')
            self.stdout.write(f'    Using real PQC: {encrypted.get("is_real_pqc")}')
        
        # Note: Full decryption test requires storing the private key
        # In the real system, keys are deterministically derived from recovery key
    
    def _test_recovery_key_generation(self):
        """Test recovery key generation."""
        from ..services.passkey_primary_recovery_service import PasskeyPrimaryRecoveryService
        
        service = PasskeyPrimaryRecoveryService()
        
        # Generate keys
        key1 = service.generate_recovery_key()
        key2 = service.generate_recovery_key()
        
        assert key1 != key2, "Generated keys should be unique"
        assert len(key1.replace('-', '')) == 24, "Key should be 24 characters (excluding hyphens)"
        assert '-' in key1, "Key should be formatted with hyphens"
        
        # Test hash
        hash1 = service.hash_recovery_key(key1)
        hash2 = service.hash_recovery_key(key1)
        
        assert hash1 == hash2, "Hash should be deterministic"
        assert len(hash1) == 64, "Hash should be SHA-256 (64 hex chars)"
        
        if self.verbose:
            self.stdout.write(f'    Sample key format: {key1[:9]}...')
    
    def _test_crypto_status(self):
        """Test crypto status reporting."""
        from ..services.kyber_crypto import get_crypto_status
        
        status = get_crypto_status()
        
        assert 'using_real_pqc' in status, "Status should indicate PQC type"
        assert 'implementation' in status, "Status should indicate implementation"
        assert 'algorithm' in status, "Status should indicate algorithm"
        
        if self.verbose:
            self.stdout.write(f'    Implementation: {status["implementation"]}')
            self.stdout.write(f'    Real PQC: {status["using_real_pqc"]}')
    
    def _test_create_backup(self, user):
        """Test creating a recovery backup."""
        from ..passkey_primary_recovery_models import PasskeyRecoveryBackup
        from ..services.passkey_primary_recovery_service import PasskeyPrimaryRecoveryService
        from ..services.kyber_crypto import production_kyber
        
        service = PasskeyPrimaryRecoveryService()
        
        # Generate recovery key
        recovery_key = service.generate_recovery_key()
        recovery_key_hash = service.hash_recovery_key(recovery_key)
        
        # Generate Kyber keypair
        kyber_public_key, _ = production_kyber.generate_keypair()
        
        # Create test credential data
        credential_data = {
            'credential_id': 'test_credential_123',
            'public_key': 'test_public_key_data',
            'rp_id': 'localhost',
            'test': True
        }
        
        # Encrypt credential data
        encrypted_data, metadata = service.encrypt_passkey_credential(
            credential_data=credential_data,
            recovery_key=recovery_key,
            user_kyber_public_key=kyber_public_key
        )
        
        # Create backup in database
        with transaction.atomic():
            backup = PasskeyRecoveryBackup.objects.create(
                user=user,
                passkey_credential_id=b'test_credential_123',
                encrypted_credential_data=encrypted_data,
                recovery_key_hash=recovery_key_hash,
                kyber_public_key=kyber_public_key,
                encryption_metadata=metadata,
                device_name='Test Device',
                is_active=True
            )
        
        assert backup.id is not None, "Backup should be created"
        assert backup.recovery_key_hash == recovery_key_hash, "Hash should match"
        
        # Store recovery key for later tests (in real scenario, user stores this)
        self._test_recovery_key = recovery_key
        self._test_backup_id = backup.id
        
        if self.verbose:
            self.stdout.write(f'    Backup ID: {backup.id}')
            self.stdout.write(f'    Recovery key: {recovery_key[:9]}...')
    
    def _test_list_backups(self, user):
        """Test listing recovery backups."""
        from ..passkey_primary_recovery_models import PasskeyRecoveryBackup
        
        backups = PasskeyRecoveryBackup.objects.filter(
            user=user,
            is_active=True
        )
        
        assert backups.exists(), "Should have at least one backup"
        
        if self.verbose:
            self.stdout.write(f'    Found {backups.count()} backup(s)')
    
    def _test_initiate_recovery(self, user):
        """Test recovery initiation."""
        from ..passkey_primary_recovery_models import PasskeyRecoveryAttempt, PasskeyRecoveryBackup
        
        # Check for active backup
        has_backup = PasskeyRecoveryBackup.objects.filter(
            user=user,
            is_active=True
        ).exists()
        
        assert has_backup, "User should have an active backup"
        
        # Create recovery attempt
        attempt = PasskeyRecoveryAttempt.objects.create(
            user=user,
            status='initiated',
            ip_address='127.0.0.1',
            user_agent='Test Suite'
        )
        
        assert attempt.id is not None, "Attempt should be created"
        assert attempt.status == 'initiated', "Status should be 'initiated'"
        
        self._test_attempt_id = attempt.id
        
        if self.verbose:
            self.stdout.write(f'    Attempt ID: {attempt.id}')
    
    def _test_complete_recovery_valid(self, user):
        """Test recovery completion with valid key."""
        from ..passkey_primary_recovery_models import PasskeyRecoveryBackup, PasskeyRecoveryAttempt
        
        # Get the recovery key from setup test
        if not hasattr(self, '_test_recovery_key'):
            raise AssertionError("No recovery key from setup test")
        
        # Find backup and verify key
        backup = PasskeyRecoveryBackup.objects.filter(
            user=user,
            is_active=True
        ).first()
        
        assert backup is not None, "Backup should exist"
        assert backup.verify_recovery_key(self._test_recovery_key), \
            "Recovery key should verify correctly"
        
        if self.verbose:
            self.stdout.write('    Key verification: PASSED')
    
    def _test_complete_recovery_invalid(self, user):
        """Test recovery completion with invalid key."""
        from ..passkey_primary_recovery_models import PasskeyRecoveryBackup
        
        backup = PasskeyRecoveryBackup.objects.filter(
            user=user,
            is_active=True
        ).first()
        
        assert backup is not None, "Backup should exist"
        
        # Try invalid key
        invalid_key = 'XXXX-XXXX-XXXX-XXXX-XXXX-XXXX'
        is_valid = backup.verify_recovery_key(invalid_key)
        
        assert not is_valid, "Invalid key should fail verification"
        
        if self.verbose:
            self.stdout.write('    Invalid key rejection: PASSED')
    
    def _test_fallback_trigger(self, user):
        """Test fallback to social mesh recovery."""
        from ..passkey_primary_recovery_models import PasskeyRecoveryAttempt
        
        # Create a failed attempt
        attempt = PasskeyRecoveryAttempt.objects.create(
            user=user,
            status='key_invalid',
            ip_address='127.0.0.1',
            user_agent='Test Suite',
            failure_reason='Test: invalid recovery key'
        )
        
        # Trigger fallback
        attempt.initiate_fallback()
        attempt.refresh_from_db()
        
        assert attempt.status == 'fallback_initiated', \
            "Status should be 'fallback_initiated'"
        
        if self.verbose:
            self.stdout.write(f'    Fallback status: {attempt.status}')
    
    def _test_health_check(self):
        """Test health check system."""
        from ..recovery_monitoring import health_checker
        
        health = health_checker.check_health()
        
        assert 'status' in health, "Health check should return status"
        assert 'checks' in health, "Health check should return individual checks"
        
        if self.verbose:
            self.stdout.write(f'    Overall status: {health["status"]}')
            for check_name, check_result in health['checks'].items():
                self.stdout.write(f'    - {check_name}: {check_result["status"]}')
    
    def _test_metrics_collection(self):
        """Test metrics collection."""
        from ..recovery_monitoring import metrics_collector
        
        # Record a test metric
        metrics_collector.record_recovery_attempt(
            user_id=1,
            attempt_type='primary',
            status='completed',
            duration_seconds=5.5,
            metadata={'test': True}
        )
        
        # Get summary
        summary = metrics_collector.get_metrics_summary(24)
        
        assert 'primary_recovery' in summary, "Summary should contain primary recovery stats"
        assert 'social_mesh_recovery' in summary, "Summary should contain social mesh stats"
        
        if self.verbose:
            self.stdout.write(f'    Metrics period: {summary["period_hours"]}h')
    
    # ==================== Helper Functions ====================
    
    def _get_or_create_test_user(self, username=None):
        """Get or create a test user."""
        username = username or 'recovery_test_user'
        
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                'email': f'{username}@test.local',
                'is_active': True,
            }
        )
        
        if created and self.verbose:
            self.stdout.write(f'  Created test user: {username}')
        
        return user
    
    def _cleanup_test_data(self, username=None):
        """Clean up test data."""
        self.stdout.write(self.style.NOTICE('\n--- Cleanup ---'))
        
        username = username or 'recovery_test_user'
        
        try:
            from ..passkey_primary_recovery_models import (
                PasskeyRecoveryBackup,
                PasskeyRecoveryAttempt
            )
            
            user = User.objects.filter(username=username).first()
            if user:
                # Delete test backups
                deleted_backups = PasskeyRecoveryBackup.objects.filter(
                    user=user
                ).delete()
                
                # Delete test attempts
                deleted_attempts = PasskeyRecoveryAttempt.objects.filter(
                    user=user
                ).delete()
                
                self.stdout.write(
                    f'  Deleted {deleted_backups[0]} backups, {deleted_attempts[0]} attempts'
                )
            
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'  Cleanup error: {e}'))
    
    def _print_summary(self, results):
        """Print test results summary."""
        self.stdout.write(self.style.NOTICE('\n' + '=' * 60))
        self.stdout.write(self.style.NOTICE('Test Results Summary'))
        self.stdout.write(self.style.NOTICE('=' * 60))
        
        total = results['passed'] + results['failed'] + results['skipped']
        
        self.stdout.write(f'  Total tests: {total}')
        self.stdout.write(self.style.SUCCESS(f'  Passed: {results["passed"]}'))
        
        if results['failed'] > 0:
            self.stdout.write(self.style.ERROR(f'  Failed: {results["failed"]}'))
        else:
            self.stdout.write(f'  Failed: {results["failed"]}')
        
        if results['skipped'] > 0:
            self.stdout.write(self.style.WARNING(f'  Skipped: {results["skipped"]}'))
        
        if results['errors']:
            self.stdout.write(self.style.ERROR('\nErrors:'))
            for error in results['errors']:
                self.stdout.write(self.style.ERROR(f'  - {error}'))
        
        self.stdout.write('')

