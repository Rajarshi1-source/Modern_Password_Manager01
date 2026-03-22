"""
Smart Contract Vault Tests
============================

Tests for vault service, condition engine, and API views.
"""

from datetime import timedelta
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase, APIClient
from rest_framework import status as http_status

from smart_contracts.models.vault import (
    SmartContractVault, VaultCondition, ConditionType, VaultStatus
)
from smart_contracts.models.governance import MultiSigGroup, MultiSigApproval, DAOProposal, DAOVote
from smart_contracts.models.escrow import EscrowAgreement, InheritancePlan
from smart_contracts.services.vault_service import VaultService
from smart_contracts.services.condition_engine import ConditionEngine

User = get_user_model()

SMART_CONTRACT_TEST_SETTINGS = {
    'ENABLED': True,
    'TIMELOCKED_VAULT_ADDRESS': '',
    'CHAINLINK_ETH_USD_ORACLE': '',
    'DEFAULT_CHECK_IN_INTERVAL_DAYS': 30,
    'DEFAULT_GRACE_PERIOD_DAYS': 7,
    'MAX_MULTI_SIG_SIGNERS': 10,
    'DAO_DEFAULT_QUORUM_PERCENT': 51,
    'DAO_VOTING_PERIOD_DAYS': 7,
    'ORACLE_CACHE_TTL_SECONDS': 300,
}


@override_settings(SMART_CONTRACT_AUTOMATION=SMART_CONTRACT_TEST_SETTINGS)
class VaultServiceTest(TestCase):
    """Tests for VaultService CRUD operations."""

    def setUp(self):
        self.service = VaultService()
        self.user = User.objects.create_user(
            username='vaultowner', email='owner@test.com', password='testpass123!'
        )
        self.user2 = User.objects.create_user(
            username='signer1', email='signer1@test.com', password='testpass123!'
        )
        self.user3 = User.objects.create_user(
            username='signer2', email='signer2@test.com', password='testpass123!'
        )
        self.beneficiary = User.objects.create_user(
            username='beneficiary', email='beneficiary@test.com', password='testpass123!'
        )

    def test_create_time_lock_vault(self):
        vault = self.service.create_vault(self.user, {
            'title': 'Time Lock Test',
            'password_encrypted': 'encrypted_data_here',
            'condition_type': ConditionType.TIME_LOCK,
            'unlock_at': timezone.now() + timedelta(days=7),
        })
        self.assertEqual(vault.condition_type, ConditionType.TIME_LOCK)
        self.assertEqual(vault.status, VaultStatus.ACTIVE)
        self.assertEqual(vault.user, self.user)
        self.assertIsNotNone(vault.unlock_at)

    def test_create_dead_mans_switch_vault(self):
        vault = self.service.create_vault(self.user, {
            'title': 'DMS Test',
            'password_encrypted': 'encrypted_data_here',
            'condition_type': ConditionType.DEAD_MANS_SWITCH,
            'check_in_interval_days': 30,
            'grace_period_days': 7,
            'beneficiary_email': 'heir@test.com',
        })
        self.assertEqual(vault.condition_type, ConditionType.DEAD_MANS_SWITCH)
        self.assertIsNotNone(vault.last_check_in)
        self.assertTrue(hasattr(vault, 'inheritance_plan'))

    def test_create_multi_sig_vault(self):
        vault = self.service.create_vault(self.user, {
            'title': 'Multi-Sig Test',
            'password_encrypted': 'encrypted_data_here',
            'condition_type': ConditionType.MULTI_SIG,
            'signer_ids': [self.user2.id, self.user3.id],
            'required_approvals': 2,
        })
        self.assertEqual(vault.condition_type, ConditionType.MULTI_SIG)
        self.assertTrue(hasattr(vault, 'multi_sig_group'))
        self.assertEqual(vault.multi_sig_group.required_approvals, 2)

    def test_create_dao_vote_vault(self):
        vault = self.service.create_vault(self.user, {
            'title': 'DAO Test',
            'password_encrypted': 'encrypted_data_here',
            'condition_type': ConditionType.DAO_VOTE,
            'voter_ids': [self.user2.id, self.user3.id],
            'voting_period_days': 7,
            'quorum_threshold': 5100,
        })
        self.assertEqual(vault.condition_type, ConditionType.DAO_VOTE)
        self.assertTrue(hasattr(vault, 'dao_proposal'))

    def test_create_escrow_vault(self):
        vault = self.service.create_vault(self.user, {
            'title': 'Escrow Test',
            'password_encrypted': 'encrypted_data_here',
            'condition_type': ConditionType.ESCROW,
            'beneficiary_user_id': self.beneficiary.id,
            'arbitrator_id': self.user2.id,
            'release_conditions': 'Upon completion of project X',
        })
        self.assertEqual(vault.condition_type, ConditionType.ESCROW)
        self.assertTrue(hasattr(vault, 'escrow_agreement'))

    def test_check_in(self):
        vault = self.service.create_vault(self.user, {
            'title': 'Check-In Test',
            'password_encrypted': 'encrypted_data_here',
            'condition_type': ConditionType.DEAD_MANS_SWITCH,
            'check_in_interval_days': 30,
            'grace_period_days': 7,
            'beneficiary_email': 'heir@test.com',
        })
        old_check_in = vault.last_check_in
        result = self.service.check_in(vault, self.user)
        vault.refresh_from_db()
        self.assertTrue(result['success'])
        self.assertGreater(vault.last_check_in, old_check_in)

    def test_check_in_wrong_user(self):
        vault = self.service.create_vault(self.user, {
            'title': 'Check-In Auth Test',
            'password_encrypted': 'encrypted_data_here',
            'condition_type': ConditionType.DEAD_MANS_SWITCH,
            'check_in_interval_days': 30,
            'beneficiary_email': 'heir@test.com',
        })
        with self.assertRaises(PermissionError):
            self.service.check_in(vault, self.user2)

    def test_cancel_vault(self):
        vault = self.service.create_vault(self.user, {
            'title': 'Cancel Test',
            'password_encrypted': 'encrypted_data_here',
            'condition_type': ConditionType.TIME_LOCK,
            'unlock_at': timezone.now() + timedelta(days=1),
        })
        result = self.service.cancel_vault(vault, self.user)
        vault.refresh_from_db()
        self.assertTrue(result['cancelled'])
        self.assertEqual(vault.status, VaultStatus.CANCELLED)

    def test_multi_sig_approval(self):
        vault = self.service.create_vault(self.user, {
            'title': 'Multi-Sig Approve Test',
            'password_encrypted': 'encrypted_data_here',
            'condition_type': ConditionType.MULTI_SIG,
            'signer_ids': [self.user2.id, self.user3.id],
            'required_approvals': 2,
        })
        result = self.service.approve_multi_sig(vault, self.user2)
        self.assertTrue(result['approved'])
        self.assertEqual(result['current_approvals'], 1)
        self.assertFalse(result['threshold_met'])

        result2 = self.service.approve_multi_sig(vault, self.user3)
        self.assertTrue(result2['threshold_met'])

    def test_dao_vote(self):
        vault = self.service.create_vault(self.user, {
            'title': 'DAO Vote Test',
            'password_encrypted': 'encrypted_data_here',
            'condition_type': ConditionType.DAO_VOTE,
            'voter_ids': [self.user2.id, self.user3.id],
            'quorum_threshold': 5100,
        })
        result = self.service.cast_vote(vault, self.user2, True)
        self.assertTrue(result['voted'])
        self.assertEqual(result['votes_for'], 1)


@override_settings(SMART_CONTRACT_AUTOMATION=SMART_CONTRACT_TEST_SETTINGS)
class ConditionEngineTest(TestCase):
    """Tests for ConditionEngine evaluation."""

    def setUp(self):
        self.engine = ConditionEngine()
        self.service = VaultService()
        self.user = User.objects.create_user(
            username='enginetest', email='engine@test.com', password='testpass123!'
        )
        self.user2 = User.objects.create_user(
            username='signer_eng', email='signer_eng@test.com', password='testpass123!'
        )
        self.user3 = User.objects.create_user(
            username='signer_eng2', email='signer_eng2@test.com', password='testpass123!'
        )

    def test_time_lock_not_met(self):
        vault = self.service.create_vault(self.user, {
            'title': 'TL Not Met',
            'password_encrypted': 'enc',
            'condition_type': ConditionType.TIME_LOCK,
            'unlock_at': timezone.now() + timedelta(days=7),
        })
        result = self.engine.evaluate(vault)
        self.assertFalse(result['met'])

    def test_time_lock_met(self):
        vault = self.service.create_vault(self.user, {
            'title': 'TL Met',
            'password_encrypted': 'enc',
            'condition_type': ConditionType.TIME_LOCK,
            'unlock_at': timezone.now() - timedelta(hours=1),
        })
        result = self.engine.evaluate(vault)
        self.assertTrue(result['met'])

    def test_dead_mans_switch_not_triggered(self):
        vault = self.service.create_vault(self.user, {
            'title': 'DMS Not Triggered',
            'password_encrypted': 'enc',
            'condition_type': ConditionType.DEAD_MANS_SWITCH,
            'check_in_interval_days': 30,
            'grace_period_days': 7,
            'beneficiary_email': 'heir@test.com',
        })
        result = self.engine.evaluate(vault)
        self.assertFalse(result['met'])

    def test_dead_mans_switch_triggered(self):
        vault = self.service.create_vault(self.user, {
            'title': 'DMS Triggered',
            'password_encrypted': 'enc',
            'condition_type': ConditionType.DEAD_MANS_SWITCH,
            'check_in_interval_days': 30,
            'grace_period_days': 7,
            'beneficiary_email': 'heir@test.com',
        })
        # Simulate old last check-in
        vault.last_check_in = timezone.now() - timedelta(days=40)
        vault.save()
        result = self.engine.evaluate(vault)
        self.assertTrue(result['met'])

    def test_multi_sig_not_met(self):
        vault = self.service.create_vault(self.user, {
            'title': 'MS Not Met',
            'password_encrypted': 'enc',
            'condition_type': ConditionType.MULTI_SIG,
            'signer_ids': [self.user2.id, self.user3.id],
            'required_approvals': 2,
        })
        result = self.engine.evaluate(vault)
        self.assertFalse(result['met'])


@override_settings(SMART_CONTRACT_AUTOMATION=SMART_CONTRACT_TEST_SETTINGS)
class SmartContractAPITest(APITestCase):
    """Tests for REST API endpoints."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='apitest', email='api@test.com', password='testpass123!'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_get_config(self):
        response = self.client.get('/api/smart-contracts/config/')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertIn('enabled', response.data)

    def test_list_vaults_empty(self):
        response = self.client.get('/api/smart-contracts/vaults/')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)

    def test_create_time_lock_vault(self):
        response = self.client.post('/api/smart-contracts/vaults/', {
            'title': 'API Time Lock',
            'password_encrypted': 'encrypted_test',
            'condition_type': 'time_lock',
            'unlock_at': (timezone.now() + timedelta(days=7)).isoformat(),
        }, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self.assertEqual(response.data['condition_type'], 'time_lock')

    def test_vault_detail(self):
        service = VaultService()
        vault = service.create_vault(self.user, {
            'title': 'Detail Test',
            'password_encrypted': 'enc',
            'condition_type': ConditionType.TIME_LOCK,
            'unlock_at': timezone.now() + timedelta(days=1),
        })
        response = self.client.get(f'/api/smart-contracts/vaults/{vault.id}/')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'Detail Test')

    def test_vault_conditions(self):
        service = VaultService()
        vault = service.create_vault(self.user, {
            'title': 'Conditions Test',
            'password_encrypted': 'enc',
            'condition_type': ConditionType.TIME_LOCK,
            'unlock_at': timezone.now() + timedelta(days=1),
        })
        response = self.client.get(f'/api/smart-contracts/vaults/{vault.id}/conditions/')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertIn('met', response.data)

    def test_unauthenticated_access(self):
        client = APIClient()  # No auth
        response = client.get('/api/smart-contracts/vaults/')
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)
