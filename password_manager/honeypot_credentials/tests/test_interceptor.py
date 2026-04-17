"""
End-to-end tests for the honeypot interceptor.

These do not hit real vault items — we verify:

  * creating a honeypot yields an encrypted decoy password;
  * retrieving that id returns a decoy payload shaped like a vault item;
  * a HoneypotAccessEvent row is written per hit;
  * the list endpoint's masked entry never leaks the decoy password.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from honeypot_credentials.models import (
    HoneypotAccessEvent,
    HoneypotAccessType,
    HoneypotCredential,
)
from honeypot_credentials.services import HoneypotAccessInterceptor, HoneypotService

User = get_user_model()


class _FakeRequest:
    """Minimal request shim — interceptor only touches META + session."""

    def __init__(self, ip='203.0.113.9', ua='pytest'):
        self.META = {'REMOTE_ADDR': ip, 'HTTP_USER_AGENT': ua}
        self.session = type('S', (), {'session_key': ''})()


@override_settings(HONEYPOT_CREDENTIALS_ENABLED=True)
class HoneypotInterceptorTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='alice@example.com', password='x' * 12)
        self.service = HoneypotService()
        self.honeypot = self.service.create(user=self.user, label='admin-backup')
        self.interceptor = HoneypotAccessInterceptor()

    def test_create_encrypts_decoy(self):
        hp = HoneypotCredential.objects.get(id=self.honeypot.id)
        self.assertTrue(bytes(hp.decoy_password_encrypted))
        # The encrypted column must not contain the plaintext in the clear.
        self.assertNotIn(b'password', bytes(hp.decoy_password_encrypted).lower())

    def test_retrieve_returns_decoy_and_records_event(self):
        req = _FakeRequest()
        result = self.interceptor.intercept_retrieve(self.honeypot.id, req)

        self.assertIsNotNone(result)
        self.assertTrue(result.get('is_honeypot'))
        self.assertIn('password', result)
        # One event row per interception.
        self.assertEqual(
            HoneypotAccessEvent.objects.filter(honeypot=self.honeypot).count(),
            1,
        )

    def test_non_honeypot_id_returns_none(self):
        req = _FakeRequest()
        import uuid as _uuid
        result = self.interceptor.intercept_retrieve(_uuid.uuid4(), req)
        self.assertIsNone(result)

    def test_masked_list_entry_hides_credentials(self):
        masked = self.service.masked_list_entry(self.honeypot)
        self.assertNotIn('password', masked)
        self.assertNotIn('username', masked)
        self.assertEqual(masked['item_type'], 'password')

    def test_inactive_honeypot_does_not_trigger(self):
        self.honeypot.is_active = False
        self.honeypot.save(update_fields=['is_active'])
        result = self.interceptor.intercept_retrieve(self.honeypot.id, _FakeRequest())
        self.assertIsNone(result)
        self.assertFalse(
            HoneypotAccessEvent.objects.filter(honeypot=self.honeypot).exists()
        )

    def test_disabled_flag_short_circuits(self):
        with override_settings(HONEYPOT_CREDENTIALS_ENABLED=False):
            result = self.interceptor.intercept_retrieve(self.honeypot.id, _FakeRequest())
        self.assertIsNone(result)
