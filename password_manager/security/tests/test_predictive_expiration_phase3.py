"""
Phase 3 tests — Predictive Password Expiration (zero-knowledge)
===============================================================

Phase 3 wires the proactive *client-side* rotation flow. The server only
records the rotation obligation; the password is regenerated, re-encrypted and
stored entirely in the browser. These tests lock the server-side ZK contract:

- the rotate endpoint accepts a reason only — there is no plaintext password
  field, so a new password can never reach the server (even if a client sends
  one, it is ignored and never persisted);
- the legacy plaintext ``analyze/`` endpoint stays gone (410).
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status

User = get_user_model()


class ForceRotationSerializerContractTests(TestCase):
    """The rotate serializer must not expose any plaintext-password field."""

    def test_serializer_has_no_password_field(self):
        from security.serializers.predictive_expiration_serializers import (
            ForceRotationSerializer,
        )
        fields = ForceRotationSerializer().fields
        self.assertIn('reason', fields)
        # Zero-knowledge: no field through which a secret could be submitted.
        self.assertNotIn('new_password', fields)
        self.assertFalse(
            any('password' in name for name in fields),
            f"Rotate serializer must expose no password field; got {list(fields)}",
        )


class ForceRotationEndpointTests(TestCase):
    """End-to-end: the rotate endpoint records an event, ZK-correctly."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='rotateuser',
            email='rotate@example.com',
            password='RotateTest123!',
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        from security.models import PredictiveExpirationRule
        self.rule = PredictiveExpirationRule.objects.create(
            user=self.user,
            credential_id='cred-rotate-1',
            credential_domain='other',
            risk_level='high',
            risk_score=0.85,
            recommended_action='rotate_immediately',
        )
        self.url = reverse(
            'predictive-expiration-force-rotation',
            kwargs={'id': 'cred-rotate-1'},
        )

    def test_rotate_records_event_with_reason_only(self):
        from security.models import PasswordRotationEvent

        resp = self.client.post(self.url, {'reason': 'Proactive rotation'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_202_ACCEPTED)

        event = PasswordRotationEvent.objects.get(user=self.user, credential_id='cred-rotate-1')
        self.assertEqual(event.trigger_reason, 'Proactive rotation')
        # The rule is acknowledged once a rotation is recorded.
        self.rule.refresh_from_db()
        self.assertTrue(self.rule.user_acknowledged)

    def test_rotate_ignores_any_submitted_password(self):
        """A client that wrongly sends a password gets no error and no leak:
        the field is unknown, so DRF drops it and nothing is persisted."""
        from security.models import PasswordRotationEvent

        resp = self.client.post(
            self.url,
            {'reason': 'r', 'new_password': 'ShouldBeIgnored#1'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_202_ACCEPTED)
        self.assertNotIn('new_password', resp.data)

        event = PasswordRotationEvent.objects.get(user=self.user, credential_id='cred-rotate-1')
        # The secret must not have landed in any recorded field.
        for value in (event.trigger_reason, str(event.threat_factors_at_rotation)):
            self.assertNotIn('ShouldBeIgnored#1', value or '')

    def test_analyze_endpoint_stays_gone(self):
        """The plaintext analyze path must remain removed (ZK)."""
        url = reverse('predictive-expiration-analyze')
        resp = self.client.post(url, {'password': 'whatever'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_410_GONE)
