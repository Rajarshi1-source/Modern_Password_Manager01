"""Integration tests for the ultrasonic pairing state machine.

Covers:
    * Happy path (initiate -> claim -> confirm)
    * Replay rejection (nonce already claimed)
    * TTL expiry (stale session cannot be claimed)
    * Wrong-responder confirm rejection
"""

from __future__ import annotations

import base64
import os
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from ultrasonic_pairing.models import (
    PairingPurpose,
    PairingSession,
    PairingStatus,
)
from ultrasonic_pairing.services import pairing_service as ps
from ultrasonic_pairing.tasks import expire_stale_sessions

User = get_user_model()


def _fake_pub() -> str:
    # 65-byte SEC1 uncompressed key. The server only checks the
    # leading 0x04 tag + length, so random fill is fine for tests.
    return base64.b64encode(b'\x04' + os.urandom(64)).decode()


def _fake_sas() -> str:
    return base64.b64encode(os.urandom(32)).decode()


@override_settings(ULTRASONIC_PAIRING_ENABLED=True, PAIRING_SESSION_TTL_SECONDS=120)
class HappyPathTest(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(email='alice@example.com', password='x' * 12)
        self.bob = User.objects.create_user(email='bob@example.com', password='x' * 12)

    def test_initiate_claim_confirm(self):
        session, nonce_b64 = ps.initiate(
            user=self.alice, pub_key_b64=_fake_pub(),
            purpose=PairingPurpose.ITEM_SHARE,
        )
        self.assertEqual(session.status, PairingStatus.AWAITING_RESPONDER)

        session2 = ps.claim(
            user=self.bob, nonce_b64=nonce_b64, pub_key_b64=_fake_pub(),
        )
        self.assertEqual(session2.id, session.id)
        self.assertEqual(session2.status, PairingStatus.CLAIMED)
        self.assertEqual(session2.responder_id, self.bob.id)

        session3 = ps.confirm(
            session_id=session.id, user=self.bob, sas_hmac_b64=_fake_sas(),
        )
        self.assertEqual(session3.status, PairingStatus.CONFIRMED)


@override_settings(ULTRASONIC_PAIRING_ENABLED=True, PAIRING_SESSION_TTL_SECONDS=120)
class ReplayAndTtlTest(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(email='alice2@example.com', password='x' * 12)
        self.bob = User.objects.create_user(email='bob2@example.com', password='x' * 12)
        self.eve = User.objects.create_user(email='eve@example.com', password='x' * 12)

    def test_replay_after_claim_is_rejected(self):
        _, nonce_b64 = ps.initiate(
            user=self.alice, pub_key_b64=_fake_pub(),
            purpose=PairingPurpose.DEVICE_ENROLL,
        )
        ps.claim(user=self.bob, nonce_b64=nonce_b64, pub_key_b64=_fake_pub())
        with self.assertRaises(ps.PairingError) as cm:
            ps.claim(user=self.eve, nonce_b64=nonce_b64, pub_key_b64=_fake_pub())
        self.assertEqual(cm.exception.code, 'already_claimed')

    def test_claim_after_ttl_expires(self):
        session, nonce_b64 = ps.initiate(
            user=self.alice, pub_key_b64=_fake_pub(),
            purpose=PairingPurpose.ITEM_SHARE,
        )
        # Force the session past its TTL.
        session.expires_at = timezone.now() - timedelta(seconds=1)
        session.save(update_fields=['expires_at'])

        with self.assertRaises(ps.PairingError) as cm:
            ps.claim(user=self.bob, nonce_b64=nonce_b64, pub_key_b64=_fake_pub())
        self.assertEqual(cm.exception.code, 'session_expired')

    def test_expire_stale_sessions_task_marks_rows(self):
        session, _ = ps.initiate(
            user=self.alice, pub_key_b64=_fake_pub(),
            purpose=PairingPurpose.DEVICE_ENROLL,
        )
        session.expires_at = timezone.now() - timedelta(seconds=1)
        session.save(update_fields=['expires_at'])

        flipped = expire_stale_sessions()
        self.assertEqual(flipped, 1)
        session.refresh_from_db()
        self.assertEqual(session.status, PairingStatus.EXPIRED)


@override_settings(ULTRASONIC_PAIRING_ENABLED=True, PAIRING_SESSION_TTL_SECONDS=120)
class WrongResponderTest(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(email='a3@example.com', password='x' * 12)
        self.bob = User.objects.create_user(email='b3@example.com', password='x' * 12)
        self.mallory = User.objects.create_user(email='m3@example.com', password='x' * 12)

    def test_confirm_from_wrong_user_rejected(self):
        session, nonce_b64 = ps.initiate(
            user=self.alice, pub_key_b64=_fake_pub(),
            purpose=PairingPurpose.DEVICE_ENROLL,
        )
        ps.claim(user=self.bob, nonce_b64=nonce_b64, pub_key_b64=_fake_pub())

        with self.assertRaises(ps.PairingError) as cm:
            ps.confirm(
                session_id=session.id, user=self.mallory,
                sas_hmac_b64=_fake_sas(),
            )
        self.assertEqual(cm.exception.code, 'wrong_responder')


@override_settings(ULTRASONIC_PAIRING_ENABLED=True, PAIRING_SESSION_TTL_SECONDS=120)
class ShareAndDeliverTest(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(email='a4@example.com', password='x' * 12)
        self.bob = User.objects.create_user(email='b4@example.com', password='x' * 12)

    def _run_to_confirmed(self):
        session, nonce_b64 = ps.initiate(
            user=self.alice, pub_key_b64=_fake_pub(),
            purpose=PairingPurpose.ITEM_SHARE,
        )
        ps.claim(user=self.bob, nonce_b64=nonce_b64, pub_key_b64=_fake_pub())
        ps.confirm(session_id=session.id, user=self.bob, sas_hmac_b64=_fake_sas())
        return session

    def test_share_and_delivered_single_shot(self):
        session = self._run_to_confirmed()
        ciphertext = base64.b64encode(b'ciphertext-blob-64bytes' * 2).decode()
        nonce = base64.b64encode(os.urandom(12)).decode()

        ps.attach_share_payload(
            session_id=session.id, user=self.alice,
            ciphertext_b64=ciphertext, nonce_b64=nonce,
            vault_item_id='vault-item-1',
        )
        payload = ps.fetch_share_payload(session_id=session.id, user=self.bob)
        self.assertEqual(payload['ciphertext'], ciphertext)
        self.assertEqual(payload['vault_item_id'], 'vault-item-1')

        # Second fetch must fail (delivered is terminal).
        with self.assertRaises(ps.PairingError) as cm:
            ps.fetch_share_payload(session_id=session.id, user=self.bob)
        self.assertEqual(cm.exception.code, 'invalid_state')
