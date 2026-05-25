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


@override_settings(
    SMART_CONTRACT_AUTOMATION=SMART_CONTRACT_TEST_SETTINGS,
    SMART_CONTRACT_UNLOCK_ONCHAIN_ENABLED=True,
)
class SubmitUnlockAnchorSuccessPathTest(TestCase):
    """Exercise the happy path of ``submit_unlock_anchor`` without a chain.

    The bridge's ``build_and_send`` is mocked to return a fixed tx hash,
    and the ``enabled`` property is forced to True so we skip the live
    web3/contract preflight. ``eth_account.Account.create()`` generates a
    throwaway key just to demonstrate that the call site does not depend
    on the signing key itself — only on the mocked bridge response.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            email='dora@example.com', password='x' * 12,
        )
        self.vault = SmartContractVault.objects.create(
            user=self.user,
            title='Submit anchor vault',
            password_encrypted='ciphertext',
            status=VaultStatus.UNLOCKED,
        )

    def _make_service(self, fake_tx_hash: str) -> OnchainUnlockService:
        from eth_account import Account

        # Generate (but don't use) a key — the bridge is mocked, so no
        # signing actually happens. This documents that the service's
        # success path is decoupled from the signer.
        Account.create()

        svc = OnchainUnlockService()
        # Force ``enabled`` to True without standing up a real web3
        # provider / audit contract / signer trio. ``PropertyMock``
        # is the standard way to override a ``@property`` for the
        # duration of a test; the patcher restores the original on stop.
        enabled_patcher = mock.patch.object(
            OnchainUnlockService,
            'enabled',
            new_callable=mock.PropertyMock,
            return_value=True,
        )
        enabled_patcher.start()
        self.addCleanup(enabled_patcher.stop)

        # ``SmartContractWeb3Bridge`` is a singleton — earlier tests that
        # initialised it with ENABLED=False short-circuit __init__ before
        # ``self.audit_contract`` is even created. Force the attribute
        # onto the instance so ``submit_unlock_anchor`` (which reads
        # ``self.bridge.audit_contract`` regardless of the
        # PropertyMock-overridden ``enabled``) doesn't AttributeError.
        # The MagicMock sentinel is sufficient because ``build_and_send``
        # is itself mocked — the audit_contract is only forwarded as an
        # opaque first argument.
        svc.bridge.audit_contract = mock.MagicMock(name='audit_contract')
        svc.bridge.build_and_send = mock.MagicMock(return_value=fake_tx_hash)
        return svc

    def test_submit_persists_nonce_and_commitment_and_returns_tx_hash(self):
        fake_tx = '0x' + 'ab' * 32
        svc = self._make_service(fake_tx)

        tx_hash = svc.submit_unlock_anchor(self.vault, self.user.id)

        self.assertEqual(tx_hash, fake_tx)
        svc.bridge.build_and_send.assert_called_once()

        self.vault.refresh_from_db()
        # Nonce was minted and saved.
        self.assertTrue(bytes(self.vault.reveal_nonce or b''))
        self.assertEqual(len(bytes(self.vault.reveal_nonce)), 16)
        # Commitment was computed and persisted.
        self.assertTrue(self.vault.reveal_commitment)
        self.assertTrue(self.vault.reveal_commitment.startswith('0x'))
        self.assertEqual(len(self.vault.reveal_commitment), 2 + 64)

    def test_submit_is_idempotent_across_retries(self):
        """A retry MUST reuse the existing nonce — multiple Celery attempts
        on the same reveal cannot produce competing commitments."""
        fake_tx = '0x' + 'cd' * 32
        svc = self._make_service(fake_tx)

        svc.submit_unlock_anchor(self.vault, self.user.id)
        self.vault.refresh_from_db()
        first_nonce = bytes(self.vault.reveal_nonce)
        first_commitment = self.vault.reveal_commitment

        svc.submit_unlock_anchor(self.vault, self.user.id)
        self.vault.refresh_from_db()

        self.assertEqual(bytes(self.vault.reveal_nonce), first_nonce)
        self.assertEqual(self.vault.reveal_commitment, first_commitment)

    def test_finalize_persists_released_tx_hash_on_pending_receipt(self):
        """``finalize_unlock`` writes the tx hash to the vault row even
        when the receipt poll times out — the UI needs something to
        render while the chain confirms."""
        fake_tx = '0x' + 'ef' * 32
        svc = self._make_service(fake_tx)
        svc.wait_for_receipt = mock.MagicMock(return_value=None)

        result = svc.finalize_unlock(str(self.vault.id))

        self.assertEqual(result['status'], 'receipt_pending')
        self.assertEqual(result['tx_hash'], fake_tx)
        self.vault.refresh_from_db()
        self.assertEqual(self.vault.released_tx_hash, fake_tx)
        self.assertTrue(bytes(self.vault.reveal_nonce or b''))
