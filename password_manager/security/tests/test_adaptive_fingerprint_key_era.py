"""Adaptive-password fingerprint key era tests (Phase 1).

Covers the three things that made the zero-knowledge feature unrunnable or
unsafe before this change:

1. **Salt provisioning.** ``cryptoService.deriveFingerprintKey`` throws without a
   per-user salt, and nothing in the tree provided one. The salt must be minted,
   returned, and — critically — *stable*, because re-minting silently orphans
   every fingerprint the client already recorded.
2. **Key eras.** A stale client holding a pre-rotation key must be rejected (409)
   rather than allowed to write dead-era fingerprints into a live profile.
3. **The feature flag.** ``ADAPTIVE_PASSWORD['ENABLED']`` was read by no view, so
   the deployment kill switch did nothing.

See docs/epigenetic-adaptation-implementation-plan.md §3.
"""

import re
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from security.models import (
    AdaptivePasswordConfig,
    PasswordAdaptation,
    TypingSession,
)
from security.services.adaptive_password_service import AdaptivePasswordService

FP_ORIGINAL = 'AbCdEf0123456789-_XyZwQr'
FP_ADAPTED = 'ZyXwVu9876543210-_MnOpQr'
FP_THIRD = 'QqWwEe1122334455-_RrTtYy'

HEX_32 = re.compile(r'^[0-9a-f]{32}$')

ADAPTIVE_DISABLED = {
    'ENABLED': False,
    'DEFAULT_OPT_IN': False,
    'ADAPTATION_EXPIRY_DAYS': 7,
}


def _record_payload(fp_key_version=1, fingerprint=FP_ORIGINAL, **overrides):
    """A valid v2 record-session body."""
    payload = {
        'schema_version': 2,
        'fp_key_version': fp_key_version,
        'password_fingerprint': fingerprint,
        'length_bucket': 3,
        'keystroke_timings': [100, 120, 90, 110],
        'backspace_positions': [],
        'device_type': 'desktop',
    }
    payload.update(overrides)
    return payload


def _apply_payload(fp_key_version=1, original=FP_ORIGINAL, adapted=FP_ADAPTED,
                   **overrides):
    """A valid v2 apply body."""
    payload = {
        'schema_version': 2,
        'fp_key_version': fp_key_version,
        'original_fingerprint': original,
        'adapted_fingerprint': adapted,
        'substitutions': [{'from': 'o', 'to': '0', 'confidence': 0.9}],
        'previews': {'original_masked': 'pa***rd', 'adapted_masked': 'pa***rd'},
    }
    payload.update(overrides)
    return payload


# =============================================================================
# Model helpers
# =============================================================================

class FingerprintSaltModelTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user('saltmodel', password='testpass123')

    def test_new_salt_is_128_bit_hex(self):
        salt = AdaptivePasswordConfig.new_fingerprint_salt()
        self.assertRegex(salt, HEX_32)

    def test_ensure_is_idempotent(self):
        # The whole point: re-enabling must not re-base existing fingerprints.
        config = AdaptivePasswordConfig.objects.create(user=self.user)
        first = config.ensure_fingerprint_salt()
        self.assertEqual(config.ensure_fingerprint_salt(), first)

    def test_rotate_changes_salt_and_bumps_version(self):
        config = AdaptivePasswordConfig.objects.create(user=self.user)
        original = config.ensure_fingerprint_salt()
        new_version = config.rotate_fingerprint_key()

        self.assertEqual(new_version, 2)
        self.assertEqual(config.fp_key_version, 2)
        self.assertNotEqual(config.fingerprint_salt, original)
        self.assertRegex(config.fingerprint_salt, HEX_32)


# =============================================================================
# Salt provisioning over the API
# =============================================================================

class FingerprintSaltProvisioningTests(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user('saltapi', password='testpass123')
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_enable_returns_a_salt(self):
        response = self.client.post(
            '/api/security/adaptive/enable/', {'consent': True}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertRegex(response.data['fingerprint_salt'], HEX_32)
        self.assertEqual(response.data['fp_key_version'], 1)

    def test_re_enabling_keeps_the_same_salt(self):
        # A second salt would orphan every fingerprint recorded under the first,
        # and nothing downstream could detect it — the rows would simply stop
        # matching. This is the single most important property of the mint path.
        first = self.client.post(
            '/api/security/adaptive/enable/', {'consent': True}, format='json'
        ).data['fingerprint_salt']
        second = self.client.post(
            '/api/security/adaptive/enable/', {'consent': True}, format='json'
        ).data['fingerprint_salt']
        self.assertEqual(first, second)

    def test_enable_rejects_out_of_range_frequency_days(self):
        for bad in (0, -5, 366, 1000):
            with self.subTest(suggestion_frequency_days=bad):
                response = self.client.post(
                    '/api/security/adaptive/enable/',
                    {'consent': True, 'suggestion_frequency_days': bad},
                    format='json',
                )
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertFalse(
                    AdaptivePasswordConfig.objects.filter(user=self.user).exists()
                )

    def test_enable_rejects_out_of_range_epsilon(self):
        for bad in (0.0, 0.05, 1.1, 99):
            with self.subTest(differential_privacy_epsilon=bad):
                response = self.client.post(
                    '/api/security/adaptive/enable/',
                    {'consent': True, 'differential_privacy_epsilon': bad},
                    format='json',
                )
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertFalse(
                    AdaptivePasswordConfig.objects.filter(user=self.user).exists()
                )

    def test_enable_rejects_non_numeric_frequency_days(self):
        response = self.client.post(
            '/api/security/adaptive/enable/',
            {'consent': True, 'suggestion_frequency_days': 'not-a-number'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_enable_accepts_boundary_values(self):
        # 1 and 365 are the documented inclusive bounds for frequency_days;
        # 0.1 and 1.0 for epsilon. Off-by-one here would silently narrow the
        # accepted range below what AdaptivePasswordConfig's own help_text
        # promises.
        for frequency_days, epsilon in ((1, 0.1), (365, 1.0)):
            with self.subTest(frequency_days=frequency_days, epsilon=epsilon):
                response = self.client.post(
                    '/api/security/adaptive/enable/',
                    {
                        'consent': True,
                        'suggestion_frequency_days': frequency_days,
                        'differential_privacy_epsilon': epsilon,
                    },
                    format='json',
                )
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                config = AdaptivePasswordConfig.objects.get(user=self.user)
                self.assertEqual(config.suggestion_frequency_days, frequency_days)
                self.assertEqual(config.differential_privacy_epsilon, epsilon)

    def test_config_returns_salt_and_era(self):
        self.client.post(
            '/api/security/adaptive/enable/', {'consent': True}, format='json'
        )
        response = self.client.get('/api/security/adaptive/config/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertRegex(response.data['fingerprint_salt'], HEX_32)
        self.assertEqual(response.data['fp_key_version'], 1)

    def test_config_self_heals_a_saltless_config(self):
        # security/admin_adaptive.py lets an admin flip is_enabled directly,
        # bypassing the /enable/ mint path. Such a config must not be handed to
        # a client that then cannot derive a key at all.
        AdaptivePasswordConfig.objects.create(
            user=self.user, is_enabled=True, consent_given_at=timezone.now()
        )
        response = self.client.get('/api/security/adaptive/config/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertRegex(response.data['fingerprint_salt'], HEX_32)
        self.assertRegex(
            AdaptivePasswordConfig.objects.get(user=self.user).fingerprint_salt,
            HEX_32,
        )

    def test_config_self_heal_is_stable_across_reads(self):
        AdaptivePasswordConfig.objects.create(
            user=self.user, is_enabled=True, consent_given_at=timezone.now()
        )
        first = self.client.get('/api/security/adaptive/config/').data['fingerprint_salt']
        second = self.client.get('/api/security/adaptive/config/').data['fingerprint_salt']
        self.assertEqual(first, second)

    def test_unconfigured_user_gets_no_salt(self):
        response = self.client.get('/api/security/adaptive/config/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['enabled'])
        self.assertNotIn('fingerprint_salt', response.data)


# =============================================================================
# Key era enforcement
# =============================================================================

class FingerprintKeyEraTests(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user('erauser', password='testpass123')
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.config = AdaptivePasswordConfig.objects.create(
            user=self.user,
            is_enabled=True,
            consent_given_at=timezone.now(),
            fingerprint_salt=AdaptivePasswordConfig.new_fingerprint_salt(),
        )

    def test_record_rejects_stale_era_with_409(self):
        self.config.fp_key_version = 3
        self.config.save(update_fields=['fp_key_version'])

        response = self.client.post(
            '/api/security/adaptive/record-session/',
            _record_payload(fp_key_version=1),
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(TypingSession.objects.filter(user=self.user).count(), 0)

    def test_apply_rejects_stale_era_with_409(self):
        self.config.fp_key_version = 3
        self.config.save(update_fields=['fp_key_version'])

        response = self.client.post(
            '/api/security/adaptive/apply/',
            _apply_payload(fp_key_version=1),
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(PasswordAdaptation.objects.filter(user=self.user).count(), 0)

    def test_record_requires_fp_key_version(self):
        payload = _record_payload()
        payload.pop('fp_key_version')
        response = self.client.post(
            '/api/security/adaptive/record-session/', payload, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # -- TOCTOU: rotation commits between the view's era read (used to build
    # -- the serializer context) and the service's own write. The serializer
    # -- validation already passed at this point — these tests exercise the
    # -- *second* guard, at the service layer, that catches a config change in
    # -- that gap. A real HTTP-level race can't be reproduced deterministically
    # -- in a synchronous test; the service's expected_fp_key_version parameter
    # -- is the actual mechanism under test, so it's exercised directly.

    def test_record_service_rejects_era_that_changed_after_validation(self):
        self.config.fp_key_version = 2  # rotated after the (simulated) validation
        self.config.save(update_fields=['fp_key_version'])

        service = AdaptivePasswordService(self.user)
        result = service.record_typing_session_v2(
            password_fingerprint=FP_ORIGINAL,
            length_bucket=3,
            keystroke_timings=[100, 120],
            expected_fp_key_version=1,  # what the view/serializer validated
        )
        self.assertEqual(result.get('code'), 'fp_key_era_changed')
        self.assertEqual(TypingSession.objects.filter(user=self.user).count(), 0)

    def test_apply_service_rejects_era_that_changed_after_validation(self):
        self.config.fp_key_version = 2  # rotated after the (simulated) validation
        self.config.save(update_fields=['fp_key_version'])

        service = AdaptivePasswordService(self.user)
        result = service.apply_adaptation_v2(
            original_fingerprint=FP_ORIGINAL,
            adapted_fingerprint=FP_ADAPTED,
            substitution_classes=[{'from': 'o', 'to': '0'}],
            expected_fp_key_version=1,
        )
        self.assertEqual(result.get('code'), 'fp_key_era_changed')
        self.assertEqual(PasswordAdaptation.objects.filter(user=self.user).count(), 0)

    def test_expected_fp_key_version_none_skips_the_check(self):
        # Backward-compat: existing callers that don't pass the parameter (e.g.
        # direct service use outside the HTTP layer) must not be newly broken.
        service = AdaptivePasswordService(self.user)
        result = service.record_typing_session_v2(
            password_fingerprint=FP_ORIGINAL,
            length_bucket=3,
            keystroke_timings=[100, 120],
        )
        self.assertNotIn('error', result)
        self.assertEqual(TypingSession.objects.filter(user=self.user).count(), 1)

    def test_record_view_maps_era_changed_to_409_not_400(self):
        # Simulate the race end-to-end: the view reads era=1 for the serializer
        # context (so client-side validation passes), but by the time the
        # service does its own fresh read, the config has moved to era=2.
        with patch(
            'security.api.adaptive_password_views._current_fp_key_version',
            return_value=1,
        ):
            self.config.fp_key_version = 2
            self.config.save(update_fields=['fp_key_version'])

            response = self.client.post(
                '/api/security/adaptive/record-session/',
                _record_payload(fp_key_version=1),
                format='json',
            )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data.get('code'), 'fp_key_era_changed')
        self.assertEqual(TypingSession.objects.filter(user=self.user).count(), 0)

    def test_apply_view_maps_era_changed_to_409_not_400(self):
        with patch(
            'security.api.adaptive_password_views._current_fp_key_version',
            return_value=1,
        ):
            self.config.fp_key_version = 2
            self.config.save(update_fields=['fp_key_version'])

            response = self.client.post(
                '/api/security/adaptive/apply/',
                _apply_payload(fp_key_version=1),
                format='json',
            )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data.get('code'), 'fp_key_era_changed')
        self.assertEqual(PasswordAdaptation.objects.filter(user=self.user).count(), 0)

    def test_era_is_stamped_from_the_server_not_the_payload(self):
        # The client value is only ever *compared*; the stored value comes from
        # the config. A client cannot backdate a row into a dead era.
        #
        # Note: the serializer rejects a payload/config mismatch (409) before
        # either view ever runs, so the payload and the config are necessarily
        # equal here — this test cannot distinguish "stamped from the payload"
        # from "stamped from the config" on its own. It exists to catch a
        # regression where the service reads a *stale* config value (e.g. one
        # fetched before the request instead of the row fetched fresh in the
        # service), which is why the assertion compares against a fresh
        # refresh_from_db() read rather than the literal 5.
        self.config.fp_key_version = 5
        self.config.save(update_fields=['fp_key_version'])

        record_response = self.client.post(
            '/api/security/adaptive/record-session/',
            _record_payload(fp_key_version=5),
            format='json',
        )
        apply_response = self.client.post(
            '/api/security/adaptive/apply/',
            _apply_payload(fp_key_version=5),
            format='json',
        )
        self.assertEqual(
            record_response.status_code, status.HTTP_200_OK, record_response.data
        )
        self.assertEqual(
            apply_response.status_code, status.HTTP_200_OK, apply_response.data
        )

        self.config.refresh_from_db()
        self.assertEqual(
            TypingSession.objects.get(user=self.user).fp_key_version,
            self.config.fp_key_version,
        )
        self.assertEqual(
            PasswordAdaptation.objects.get(user=self.user).fp_key_version,
            self.config.fp_key_version,
        )

    def test_plaintext_still_beats_the_era_check(self):
        # A ZK violation must be reported as such (422) even when the era is
        # also wrong — the era check must not mask the more serious finding.
        self.config.fp_key_version = 3
        self.config.save(update_fields=['fp_key_version'])

        response = self.client.post(
            '/api/security/adaptive/record-session/',
            _record_payload(fp_key_version=1, password='hunter2'),
            format='json',
        )
        self.assertEqual(response.status_code, 422)

    def test_preference_model_echoes_the_era(self):
        self.config.fp_key_version = 4
        self.config.save(update_fields=['fp_key_version'])
        response = self.client.get('/api/security/adaptive/preference-model/')
        self.assertEqual(response.data['fp_key_version'], 4)


# =============================================================================
# Rotation
# =============================================================================

class FingerprintKeyRotationTests(APITestCase):

    URL = '/api/security/adaptive/rotate-fingerprint-key/'

    def setUp(self):
        self.user = User.objects.create_user('rotuser', password='testpass123')
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.config = AdaptivePasswordConfig.objects.create(
            user=self.user,
            is_enabled=True,
            consent_given_at=timezone.now(),
            fingerprint_salt=AdaptivePasswordConfig.new_fingerprint_salt(),
        )

    def test_rotation_requires_confirmation(self):
        response = self.client.post(self.URL, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.config.refresh_from_db()
        self.assertEqual(self.config.fp_key_version, 1)

    def test_rotation_bumps_era_and_changes_salt(self):
        original_salt = self.config.fingerprint_salt

        response = self.client.post(self.URL, {'confirm': True}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['fp_key_version'], 2)
        self.assertNotEqual(response.data['fingerprint_salt'], original_salt)

        self.config.refresh_from_db()
        self.assertEqual(self.config.fp_key_version, 2)
        self.assertEqual(self.config.fingerprint_salt, response.data['fingerprint_salt'])

    def test_rotation_requires_a_config(self):
        AdaptivePasswordConfig.objects.filter(user=self.user).delete()
        response = self.client.post(self.URL, {'confirm': True}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_prior_era_rows_drop_out_of_history_and_stats(self):
        # Record + adapt under era 1, then rotate.
        self.client.post(
            '/api/security/adaptive/record-session/', _record_payload(), format='json'
        )
        self.client.post(
            '/api/security/adaptive/apply/', _apply_payload(), format='json'
        )
        self.assertEqual(
            len(self.client.get('/api/security/adaptive/history/').data['adaptations']), 1
        )

        self.client.post(self.URL, {'confirm': True}, format='json')

        history = self.client.get('/api/security/adaptive/history/').data
        stats = self.client.get('/api/security/adaptive/stats/').data
        self.assertEqual(history['count'], 0)
        self.assertEqual(stats['total_adaptations'], 0)
        self.assertEqual(stats['total_typing_sessions'], 0)

        # ...but the rows are still on disk, and still exported for GDPR.
        self.assertEqual(PasswordAdaptation.objects.filter(user=self.user).count(), 1)
        export = self.client.get('/api/security/adaptive/export/').data
        self.assertEqual(len(export['adaptations']), 1)
        self.assertEqual(export['adaptations'][0]['fp_key_version'], 1)

    def test_prior_era_adaptation_cannot_be_rolled_back(self):
        # Build a two-generation chain under era 1 so the head is rollbackable.
        self.client.post(
            '/api/security/adaptive/apply/', _apply_payload(), format='json'
        )
        second = self.client.post(
            '/api/security/adaptive/apply/',
            _apply_payload(original=FP_ADAPTED, adapted=FP_THIRD),
            format='json',
        )
        adaptation_id = second.data['adaptation_id']
        self.assertTrue(second.data['can_rollback'])

        self.client.post(self.URL, {'confirm': True}, format='json')

        response = self.client.post(
            '/api/security/adaptive/rollback/',
            {'adaptation_id': adaptation_id},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('not found', str(response.data).lower())

    def test_new_era_chain_starts_fresh(self):
        # The same fingerprint re-applied after a rotation must start a new
        # generation-1 chain, not be treated as a child of the dead-era head.
        self.client.post(
            '/api/security/adaptive/apply/', _apply_payload(), format='json'
        )
        self.client.post(self.URL, {'confirm': True}, format='json')

        response = self.client.post(
            '/api/security/adaptive/apply/',
            _apply_payload(fp_key_version=2, original=FP_ADAPTED, adapted=FP_THIRD),
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['generation'], 1)
        self.assertFalse(response.data['can_rollback'])


# =============================================================================
# Deployment feature flag
# =============================================================================

class AdaptiveFeatureFlagTests(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user('flaguser', password='testpass123')
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        AdaptivePasswordConfig.objects.create(
            user=self.user,
            is_enabled=True,
            consent_given_at=timezone.now(),
            fingerprint_salt=AdaptivePasswordConfig.new_fingerprint_salt(),
        )

    @override_settings(ADAPTIVE_PASSWORD=ADAPTIVE_DISABLED)
    def test_learning_surface_is_503_when_disabled(self):
        cases = [
            ('post', '/api/security/adaptive/enable/', {'consent': True}),
            ('get', '/api/security/adaptive/config/', None),
            ('post', '/api/security/adaptive/record-session/', _record_payload()),
            ('post', '/api/security/adaptive/apply/', _apply_payload()),
            ('get', '/api/security/adaptive/preference-model/', None),
            ('get', '/api/security/adaptive/profile/', None),
            ('get', '/api/security/adaptive/history/', None),
            ('get', '/api/security/adaptive/stats/', None),
            ('post', '/api/security/adaptive/rotate-fingerprint-key/', {'confirm': True}),
            # Mutates adaptation state, so it's on the learning surface (not the
            # GDPR surface asserted below) — the decorator must short-circuit
            # before the view ever looks at adaptation_id.
            ('post', '/api/security/adaptive/rollback/', {'adaptation_id': 1}),
        ]
        for method, url, payload in cases:
            with self.subTest(url=url):
                caller = getattr(self.client, method)
                response = (
                    caller(url, payload, format='json') if payload is not None
                    else caller(url)
                )
                self.assertEqual(
                    response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE
                )
                self.assertEqual(response.data['code'], 'feature_disabled')

    @override_settings(ADAPTIVE_PASSWORD=ADAPTIVE_DISABLED)
    def test_gdpr_endpoints_survive_the_kill_switch(self):
        # Erasure, portability and opt-out are rights, not features — they must
        # not become unreachable because an operator flipped the flag off.
        self.assertEqual(
            self.client.get('/api/security/adaptive/export/').status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            self.client.post(
                '/api/security/adaptive/disable/', {}, format='json'
            ).status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            self.client.delete('/api/security/adaptive/data/').status_code,
            status.HTTP_200_OK,
        )

    @override_settings(ADAPTIVE_PASSWORD={})
    def test_missing_settings_block_fails_closed(self):
        response = self.client.get('/api/security/adaptive/config/')
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)


# =============================================================================
# History endpoint: N+1 query regression
# =============================================================================

class AdaptationHistoryQueryTests(APITestCase):
    """get_adaptation_history's can_rollback() reads previous_adaptation (a FK)
    on every 'active' row with a non-null parent — a first-generation row has
    previous_adaptation_id IS NULL, which Django resolves without a query, so
    only *chained* (generation >= 2) active rows actually exercise the N+1.
    """

    def setUp(self):
        self.user = User.objects.create_user('historyuser', password='testpass123')
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        AdaptivePasswordConfig.objects.create(
            user=self.user,
            is_enabled=True,
            consent_given_at=timezone.now(),
            fingerprint_salt=AdaptivePasswordConfig.new_fingerprint_salt(),
        )

    def _build_two_generation_chain(self, original, adapted, third):
        """Apply twice so the resulting active row has a non-null parent."""
        self.client.post(
            '/api/security/adaptive/apply/',
            _apply_payload(original=original, adapted=adapted),
            format='json',
        )
        self.client.post(
            '/api/security/adaptive/apply/',
            _apply_payload(original=adapted, adapted=third),
            format='json',
        )

    def test_history_query_count_does_not_scale_with_chained_rows(self):
        self._build_two_generation_chain(FP_ORIGINAL, FP_ADAPTED, FP_THIRD)
        with CaptureQueriesContext(connection) as one_chain:
            response = self.client.get('/api/security/adaptive/history/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['adaptations']), 2)

        self._build_two_generation_chain(
            'Qq11Ww22Ee33Rr44-_Tt55Yy66', 'Uu77Ii88Oo99Pp00-_Aa11Ss22',
            'Dd33Ff44Gg55Hh66-_Jj77Kk88',
        )
        with CaptureQueriesContext(connection) as two_chains:
            response = self.client.get('/api/security/adaptive/history/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['adaptations']), 4)

        # A second independent chain (another chained-active row) must not add
        # a query — if it does, select_related('previous_adaptation') regressed
        # back to a lazy per-row lookup.
        self.assertEqual(len(one_chain.captured_queries), len(two_chains.captured_queries))
