"""Rate-limit regression tests for the public social-recovery endpoints.

Plan B coverage: a leaked voucher key (or any host with knowledge of a
recovery request id) must not be able to spam attestations until quorum
flips. ``VouchAttestationThrottle`` is the protection; these tests
demonstrate it on the live URL surface (DRF integration, not just unit
testing the throttle class).

Each test resets the Django cache in ``setUp`` so token-bucket state from
a previous test does not leak into the next.
"""
from __future__ import annotations

import uuid

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from social_recovery.models import (
    RecoveryCircle,
    SocialRecoveryAuditLog,
    SocialRecoveryRequest,
)


User = get_user_model()


@override_settings(SECURE_SSL_REDIRECT=False, DEBUG=True)
class VouchAttestationThrottleTests(TestCase):
    """End-to-end tests against the live URL surface."""

    ATTEST_URL_TEMPLATE = "/api/social-recovery/requests/{request_id}/attest/"
    INITIATE_URL = "/api/social-recovery/requests/"
    COMPLETE_URL_TEMPLATE = (
        "/api/social-recovery/requests/{request_id}/complete/"
    )

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        # The throttle works regardless of whether the rest of the view
        # succeeds — but we still need a circle + request to point at so
        # the view dispatches past ``get_object_or_404``. Pre-creating
        # the rows here keeps the throttle the only thing under test.
        self.owner = User.objects.create_user(
            username="throttle-owner",
            email="throttle-owner@example.com",
            password="x" * 12,
        )
        self.circle = RecoveryCircle.objects.create(
            user=self.owner,
            threshold=2,
            total_vouchers=3,
            secret_commitment=b"\x00" * 33,
            salt=b"\x00" * 32,
            status="active",
        )
        self.request = SocialRecoveryRequest.objects.create(
            circle=self.circle,
            initiator_email="recoverer@example.com",
            required_approvals=2,
            challenge_nonce="x" * 64,
            expires_at=timezone.now() + timezone.timedelta(hours=24),
            status="pending",
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _attest_url(self) -> str:
        return self.ATTEST_URL_TEMPLATE.format(request_id=self.request.request_id)

    def _attest_payload(self, voucher_id: str | None = None) -> dict:
        return {
            "voucher_id": voucher_id or str(uuid.uuid4()),
            "decision": "approve",
            "signature_b64": "AA==",
        }

    # ------------------------------------------------------------------
    # Core regression: 11th attestation from the same voucher is 429
    # ------------------------------------------------------------------
    def test_eleventh_attestation_from_same_voucher_returns_429(self):
        """Spec wording: "assert 11th attestation in 60s from the same
        voucher returns 429". The intermediate 10 calls may return any
        4xx status from the view (signature is bogus), but never 429 —
        which is the property we care about for this regression."""
        voucher_id = str(uuid.uuid4())
        url = self._attest_url()

        for i in range(10):
            response = self.client.post(
                url, self._attest_payload(voucher_id), format="json",
            )
            self.assertNotEqual(
                response.status_code, 429,
                f"unexpected 429 on attempt {i + 1} (throttle fired too early)",
            )

        # The 11th request from the same voucher exceeds 10/min and is
        # rejected by the throttle, regardless of payload validity.
        response = self.client.post(
            url, self._attest_payload(voucher_id), format="json",
        )
        self.assertEqual(response.status_code, 429)

    def test_throttle_audit_event_recorded_on_rejection(self):
        """The throttle emits an ``attestation_rate_limited`` audit row
        so operators see the rate-limit firing in the SoR's hash chain."""
        voucher_id = str(uuid.uuid4())
        url = self._attest_url()
        baseline = SocialRecoveryAuditLog.objects.filter(
            event_type="attestation_rate_limited",
        ).count()

        for _ in range(11):
            self.client.post(
                url, self._attest_payload(voucher_id), format="json",
            )

        recorded = SocialRecoveryAuditLog.objects.filter(
            event_type="attestation_rate_limited",
        ).count()
        self.assertGreater(
            recorded, baseline,
            "expected an attestation_rate_limited audit row after throttle fired",
        )
        last = (
            SocialRecoveryAuditLog.objects.filter(
                event_type="attestation_rate_limited",
            )
            .order_by("-created_at")
            .first()
        )
        self.assertEqual(last.event_data["view"], "AttestRequestView")
        self.assertIn("voucher:", last.event_data["resource_ident"])
        # At least one of the two buckets must have denied.
        self.assertFalse(
            last.event_data["bucket_resource_ok"]
            and last.event_data["bucket_ip_ok"],
        )

    # ------------------------------------------------------------------
    # Different voucher = different bucket: rotating ids does not bypass
    # the per-IP cap, but does NOT trigger the per-resource cap.
    # ------------------------------------------------------------------
    def test_different_vouchers_share_only_the_ip_bucket(self):
        """Two distinct vouchers from the same IP each get their own
        per-resource bucket — so 10 requests for voucher A do not affect
        voucher B's per-resource quota. (They DO share the per-IP cap,
        which is 50/hour by default and not the limiting factor here.)"""
        v_a = str(uuid.uuid4())
        v_b = str(uuid.uuid4())
        url = self._attest_url()

        # 10 successful (non-throttled) calls for voucher A.
        for _ in range(10):
            r = self.client.post(url, self._attest_payload(v_a), format="json")
            self.assertNotEqual(r.status_code, 429)
        # 11th for A is throttled.
        r = self.client.post(url, self._attest_payload(v_a), format="json")
        self.assertEqual(r.status_code, 429)
        # First request from voucher B sails through (their bucket is full).
        r = self.client.post(url, self._attest_payload(v_b), format="json")
        self.assertNotEqual(r.status_code, 429)

    def test_per_ip_cap_blocks_voucher_rotation_attack(self):
        """An attacker who rotates ``voucher_id`` to bypass the per-
        voucher cap is caught by the per-IP cap. Configure a tight IP
        rate so the test runs in reasonable time."""
        from password_manager import settings as pm_settings
        tight = {
            **pm_settings.REST_FRAMEWORK,
            "DEFAULT_THROTTLE_RATES": {
                **pm_settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"],
                "vouch_attestation": "10000/hour",  # not the limiter
                "vouch_attestation_ip": "5/min",
            },
        }
        url = self._attest_url()
        with override_settings(REST_FRAMEWORK=tight):
            cache.clear()
            for i in range(5):
                r = self.client.post(
                    url, self._attest_payload(str(uuid.uuid4())),
                    format="json",
                )
                self.assertNotEqual(r.status_code, 429, f"attempt {i + 1}")
            # 6th rotated-voucher request is throttled by the IP cap.
            r = self.client.post(
                url, self._attest_payload(str(uuid.uuid4())),
                format="json",
            )
            self.assertEqual(r.status_code, 429)

    # ------------------------------------------------------------------
    # InitiateRecoveryView and CompleteRequestView are also throttled.
    # ------------------------------------------------------------------
    def test_initiate_view_is_throttled(self):
        """``InitiateRecoveryView`` carries the same throttle. The
        per-circle bucket is keyed on the JSON payload's ``circle_id``."""
        payload = {"circle_id": str(self.circle.circle_id)}
        for i in range(10):
            r = self.client.post(self.INITIATE_URL, payload, format="json")
            self.assertNotEqual(r.status_code, 429, f"attempt {i + 1}")
        r = self.client.post(self.INITIATE_URL, payload, format="json")
        self.assertEqual(r.status_code, 429)

    def test_complete_view_is_throttled(self):
        """``CompleteRequestView`` carries the same throttle. The
        per-request bucket is keyed on the URL kwarg ``request_id``."""
        url = self.COMPLETE_URL_TEMPLATE.format(
            request_id=self.request.request_id,
        )
        payload = {
            "decrypted_shares": [
                {"voucher_id": str(uuid.uuid4()), "share": "ABCD"},
            ],
        }
        for i in range(10):
            r = self.client.post(url, payload, format="json")
            self.assertNotEqual(r.status_code, 429, f"attempt {i + 1}")
        r = self.client.post(url, payload, format="json")
        self.assertEqual(r.status_code, 429)

    # ------------------------------------------------------------------
    # Graceful failure modes
    # ------------------------------------------------------------------
    def test_malformed_voucher_id_falls_back_to_ip_only_bucket(self):
        """A malformed ``voucher_id`` should not crash the throttle —
        the per-resource bucket is simply skipped and the per-IP cap
        still applies. We verify with a tight IP rate."""
        from password_manager import settings as pm_settings
        tight = {
            **pm_settings.REST_FRAMEWORK,
            "DEFAULT_THROTTLE_RATES": {
                **pm_settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"],
                "vouch_attestation": "10000/hour",
                "vouch_attestation_ip": "3/min",
            },
        }
        url = self._attest_url()
        bad_payload = {"voucher_id": "not-a-uuid", "decision": "approve"}
        with override_settings(REST_FRAMEWORK=tight):
            cache.clear()
            for i in range(3):
                r = self.client.post(url, bad_payload, format="json")
                self.assertNotEqual(r.status_code, 429, f"attempt {i + 1}")
            r = self.client.post(url, bad_payload, format="json")
            self.assertEqual(r.status_code, 429)
