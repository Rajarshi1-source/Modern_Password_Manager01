"""
Tests for OnchainUnlockService commitment building.

We avoid live chain calls — ``enabled`` will be False in CI because
``VAULT_AUDIT_LOG_ADDRESS`` is empty.  These tests exercise the
deterministic path: commitment building, nonce handling, and the
no-op behaviour when the feature is disabled.
"""

from __future__ import annotations

import uuid
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from smart_contracts.models.vault import SmartContractVault, VaultStatus
from smart_contracts.services.onchain_unlock_service import OnchainUnlockService

User = get_user_model()


SMART_CONTRACT_TEST_SETTINGS = {
    'ENABLED': True,
    'TIMELOCKED_VAULT_ADDRESS': '',
    'VAULT_AUDIT_LOG_ADDRESS': '',
    'CHAINLINK_ETH_USD_ORACLE': '',
    'DEFAULT_CHECK_IN_INTERVAL_DAYS': 30,
    'DEFAULT_GRACE_PERIOD_DAYS': 7,
    'MAX_MULTI_SIG_SIGNERS': 10,
    'DAO_DEFAULT_QUORUM_PERCENT': 51,
    'DAO_VOTING_PERIOD_DAYS': 7,
    'ORACLE_CACHE_TTL_SECONDS': 300,
}


@override_settings(SMART_CONTRACT_AUTOMATION=SMART_CONTRACT_TEST_SETTINGS)
class CommitmentHashTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='carla@example.com', password='x' * 12,
        )
        self.vault = SmartContractVault.objects.create(
            user=self.user,
            title='Test vault',
            password_encrypted='ciphertext',
            status=VaultStatus.UNLOCKED,
        )

    def test_commitment_is_32_bytes(self):
        svc = OnchainUnlockService()
        h = svc.build_commitment_hash(self.vault, self.user.id, nonce=b'\x00' * 16)
        self.assertEqual(len(h), 32)

    def test_commitment_changes_with_nonce(self):
        svc = OnchainUnlockService()
        a = svc.build_commitment_hash(self.vault, self.user.id, nonce=b'\x01' * 16)
        b = svc.build_commitment_hash(self.vault, self.user.id, nonce=b'\x02' * 16)
        self.assertNotEqual(a, b)

    @override_settings(SMART_CONTRACT_UNLOCK_ONCHAIN_ENABLED=False)
    def test_submit_is_noop_when_flag_disabled(self):
        svc = OnchainUnlockService()
        self.assertIsNone(svc.submit_unlock_anchor(self.vault, self.user.id))

    def test_finalize_returns_vault_missing_for_unknown_id(self):
        svc = OnchainUnlockService()
        result = svc.finalize_unlock(str(uuid.uuid4()))
        self.assertEqual(result.get('status'), 'vault_missing')
