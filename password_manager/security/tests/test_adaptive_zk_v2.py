"""
Adaptive Password — Zero-Knowledge v2 Tests (PR-3)
==================================================

Covers the v2 backend surface from docs/adaptive-password-zk-remediation-plan.md:

- the reject-plaintext validator (fail-closed, 422) — the correct version of
  the PR #315 nit;
- fingerprint + schema_version validation;
- record-session / apply v2 round-trips (no raw password stored);
- the preference-model export endpoint (aggregate, non-reversible signals only);
- v2 is the only contract: server-side /suggest/ is gone (410).
"""

from datetime import timedelta

from django.conf import settings
from django.test import TestCase
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.test import APITestCase, APIClient
from rest_framework import status

from security.models import (
    AdaptationFeedback,
    AdaptivePasswordConfig,
    PasswordAdaptation,
    TypingSession,
    UserTypingProfile,
)
from security.serializers.adaptive_serializers import (
    TypingSessionInputV2Serializer,
    ApplyAdaptationV2Serializer,
    PlaintextRejected,
    FingerprintKeyEraMismatch,
)
from security.services.adaptive_password_service import (
    AdaptivePasswordService,
    DEFAULT_MEMORABILITY_WEIGHTS,
    DEFAULT_OPTIMAL_LENGTH,
    MIN_SESSIONS_FOR_LENGTH_BAND,
    RHYTHM_BINS,
    normalize_memorability_weights,
    nudge_memorability_weights,
)

# A valid client fingerprint: unpadded base64url, 24 chars (see PR-1).
FP_ORIGINAL = 'AbCdEf0123456789-_GhIjKl'
FP_ADAPTED = 'ZyXwVu9876543210-_MnOpQr'


# =============================================================================
# Serializer: reject-plaintext validator (defense-in-depth, fail-closed)
# =============================================================================

class RejectPlaintextSerializerTests(TestCase):
    """The v2 serializers must reject any raw-password field with 422."""

    def test_record_serializer_rejects_password(self):
        """Record serializer rejects password."""
        serializer = TypingSessionInputV2Serializer(data={
            'schema_version': 2,
            'password': 'hunter2',  # forbidden
            'password_fingerprint': FP_ORIGINAL,
            'length_bucket': 2,
            'keystroke_timings': [100, 120],
        })
        with self.assertRaises(PlaintextRejected) as ctx:
            serializer.is_valid(raise_exception=True)
        self.assertEqual(ctx.exception.status_code, 422)

    def test_apply_serializer_rejects_original_and_adapted_password(self):
        """Apply serializer rejects original and adapted password."""
        for field in ('original_password', 'adapted_password'):
            serializer = ApplyAdaptationV2Serializer(data={
                'schema_version': 2,
                'original_fingerprint': FP_ORIGINAL,
                'adapted_fingerprint': FP_ADAPTED,
                'substitutions': [{'from': 'o', 'to': '0'}],
                field: 'plaintext-here',
            })
            with self.assertRaises(PlaintextRejected):
                serializer.is_valid(raise_exception=True)

    def test_plaintext_rejected_even_when_other_fields_missing(self):
        # Forbidden field is caught before required-field validation.
        """Plaintext rejected even when other fields missing."""
        serializer = TypingSessionInputV2Serializer(data={'password': 'x'})
        with self.assertRaises(PlaintextRejected):
            serializer.is_valid(raise_exception=True)


# =============================================================================
# Serializer: fingerprint + schema_version validation
# =============================================================================

class V2FieldValidationTests(TestCase):

    #: The user's current fingerprint key era, as the views supply it. Handed to
    #: each serializer as a FRESH dict (see `_context`) — DRF exposes the very
    #: object passed as `serializer.context`, so sharing one class-level dict
    #: would let any test that mutates it leak into every later test.
    #:
    #: Every construction here goes through the helpers below so the context is
    #: never accidentally omitted, which would fail closed with a 409
    #: (FingerprintKeyEraMismatch) instead of exercising the field under test.
    FP_KEY_VERSION = 1

    def _context(self):
        """A fresh serializer context (never shared between serializers)."""
        return {'fp_key_version': self.FP_KEY_VERSION}

    def _base_record(self, **overrides):
        """Build a base valid v2 record-session payload."""
        data = {
            'schema_version': 2,
            'fp_key_version': self.FP_KEY_VERSION,
            'password_fingerprint': FP_ORIGINAL,
            'length_bucket': 3,
            'keystroke_timings': [100, 120, 90],
        }
        data.update(overrides)
        return data

    def _record_serializer(self, context=None, **overrides):
        """Record serializer over a base payload, with the view's context."""
        return TypingSessionInputV2Serializer(
            data=self._base_record(**overrides),
            context=self._context() if context is None else context,
        )

    def _apply_serializer(self, **overrides):
        """Apply serializer over a base payload, with the view's context."""
        data = {
            'schema_version': 2,
            'fp_key_version': self.FP_KEY_VERSION,
            'original_fingerprint': FP_ORIGINAL,
            'adapted_fingerprint': FP_ADAPTED,
            'substitutions': [{'from': 'o', 'to': '0'}],
        }
        data.update(overrides)
        return ApplyAdaptationV2Serializer(data=data, context=self._context())

    def test_valid_record_payload(self):
        """Valid record payload."""
        serializer = self._record_serializer()
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_rejects_bad_fingerprint_charset(self):
        """Rejects bad fingerprint charset."""
        serializer = self._record_serializer(password_fingerprint='not valid! chars')
        self.assertFalse(serializer.is_valid())
        self.assertIn('password_fingerprint', serializer.errors)

    def test_rejects_short_fingerprint(self):
        """Rejects short fingerprint."""
        serializer = self._record_serializer(password_fingerprint='short')
        self.assertFalse(serializer.is_valid())
        self.assertIn('password_fingerprint', serializer.errors)

    def test_rejects_wrong_schema_version(self):
        """Rejects wrong schema version."""
        serializer = self._record_serializer(schema_version=1)
        self.assertFalse(serializer.is_valid())
        self.assertIn('schema_version', serializer.errors)

    def test_rejects_missing_schema_version(self):
        """Rejects missing schema version."""
        payload = self._base_record()
        payload.pop('schema_version')
        serializer = TypingSessionInputV2Serializer(data=payload, context=self._context())
        self.assertFalse(serializer.is_valid())
        self.assertIn('schema_version', serializer.errors)

    def test_rejects_missing_fp_key_version(self):
        """A payload without fp_key_version is a 400, not a silent accept."""
        payload = self._base_record()
        payload.pop('fp_key_version')
        serializer = TypingSessionInputV2Serializer(data=payload, context=self._context())
        self.assertFalse(serializer.is_valid())
        self.assertIn('fp_key_version', serializer.errors)

    def test_rejects_stale_fp_key_version_with_409(self):
        """A superseded key era raises 409, not a validation error."""
        # Client still on era 1; server has rotated to 7.
        serializer = self._record_serializer(
            context={'fp_key_version': 7}, fp_key_version=1
        )
        with self.assertRaises(FingerprintKeyEraMismatch) as ctx:
            serializer.is_valid(raise_exception=True)
        self.assertEqual(ctx.exception.status_code, 409)

    def test_missing_context_fails_closed(self):
        # If a view forgets to supply the era, reject rather than accept an
        # unverified one. Guards against a future endpoint silently skipping it.
        """Missing serializer context fails closed with 409."""
        serializer = TypingSessionInputV2Serializer(data=self._base_record())
        with self.assertRaises(FingerprintKeyEraMismatch):
            serializer.is_valid(raise_exception=True)

    def test_apply_rejects_equal_fingerprints(self):
        """Apply rejects equal fingerprints."""
        serializer = self._apply_serializer(adapted_fingerprint=FP_ORIGINAL)
        self.assertFalse(serializer.is_valid())

    def test_apply_rejects_non_class_substitution(self):
        """Apply rejects non class substitution."""
        # 'from' not single char
        serializer = self._apply_serializer(substitutions=[{'from': 'oo', 'to': '0'}])
        self.assertFalse(serializer.is_valid())

    def test_apply_rejects_extra_substitution_field(self):
        # Position/char metadata could reveal the password — reject extra keys.
        """Apply rejects extra substitution field."""
        serializer = self._apply_serializer(
            substitutions=[{'from': 'o', 'to': '0', 'position': 3}]
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn('substitutions', serializer.errors)

    def test_apply_rejects_non_finite_memorability_values(self):
        # DRF 3.16's FloatField min_value/max_value compare with </>, both
        # False against NaN, so bounds alone would let it through and the
        # strict JSON renderer would later blow up echoing it back.
        for field in (
            'memorability_improvement', 'memorability_score_before',
            'memorability_score_after',
        ):
            for bad in (float('nan'), float('inf'), float('-inf')):
                serializer = self._apply_serializer(**{field: bad})
                self.assertFalse(serializer.is_valid(), (field, bad))
                self.assertIn(field, serializer.errors, (field, bad))

    def test_apply_accepts_a_class_outside_the_leetspeak_baseline(self):
        # Deliberately NOT an allowlist of COMMON_SUBSTITUTIONS pairs: a
        # user's own evidence for a class the baseline never suggested is a
        # legitimate input to the bandit (see
        # adaptive_policy_service.policy_weights and
        # test_policy_weights_keeps_a_class_the_baseline_never_had). The
        # single-char/allowed-key shape is still enforced; the specific
        # character pair is not restricted.
        serializer = self._apply_serializer(substitutions=[{'from': 'z', 'to': '2'}])
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_apply_rejects_a_substitution_list_beyond_the_cap(self):
        # No max_length previously meant one request could create an
        # unbounded number of SubstitutionPolicyArm rows. The cap is generous
        # headroom above the 14 distinct (from, to) pairs in the shared
        # LEET_MAP baseline, not a tight allowlist around it (see the
        # previous test) — this exercises the boundary itself, not the
        # specific character pairs.
        from security.serializers.adaptive_serializers import MAX_SUBSTITUTION_CLASSES

        too_many = [
            {'from': chr(ord('a') + i % 26), 'to': str(i % 10)}
            for i in range(MAX_SUBSTITUTION_CLASSES + 1)
        ]
        serializer = self._apply_serializer(substitutions=too_many)
        self.assertFalse(serializer.is_valid())
        self.assertIn('substitutions', serializer.errors)

    def test_apply_accepts_a_substitution_list_at_the_cap(self):
        from security.serializers.adaptive_serializers import MAX_SUBSTITUTION_CLASSES

        exactly_at_cap = [
            {'from': chr(ord('a') + i % 26), 'to': str(i % 10)}
            for i in range(MAX_SUBSTITUTION_CLASSES)
        ]
        serializer = self._apply_serializer(substitutions=exactly_at_cap)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_record_rejects_a_substitution_classes_used_list_beyond_the_cap(self):
        # The same shared validator backs record-session's
        # substitution_classes_used, so the cap applies there too.
        from security.serializers.adaptive_serializers import MAX_SUBSTITUTION_CLASSES

        too_many = [
            {'from': chr(ord('a') + i % 26), 'to': str(i % 10)}
            for i in range(MAX_SUBSTITUTION_CLASSES + 1)
        ]
        serializer = self._record_serializer(substitution_classes_used=too_many)
        self.assertFalse(serializer.is_valid())
        self.assertIn('substitution_classes_used', serializer.errors)

    def test_apply_rejects_plaintext_preview(self):
        # A "preview" with no mask character is plaintext — reject it.
        """Apply rejects plaintext preview."""
        serializer = self._apply_serializer(
            previews={'original_masked': 'password', 'adapted_masked': 'passw0rd'}
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn('previews', serializer.errors)

    def test_apply_accepts_masked_preview(self):
        """Apply accepts masked preview."""
        serializer = self._apply_serializer(
            previews={'original_masked': 'pa***rd', 'adapted_masked': 'pa***rd'}
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)


# =============================================================================
# Service: preference-model export + v2 record/apply
# =============================================================================

class PreferenceModelServiceTests(TestCase):

    def setUp(self):
        """Set up the test user/fixtures."""
        self.user = User.objects.create_user('zkuser', password='testpass123')

    def test_export_baseline_without_profile(self):
        """Export baseline without profile."""
        from security.services.adaptive_password_service import AdaptivePasswordService
        model = AdaptivePasswordService(self.user).export_preference_model()
        self.assertEqual(model['model_version'], 0)
        # Baseline leetspeak weights present.
        self.assertIn('o', model['substitution_weights'])
        self.assertIn('0', model['substitution_weights']['o'])
        self.assertIn('memorability_params', model)
        # No password-derived data leaks into the model.
        self.assertNotIn('password', str(model).lower())

    def test_export_reflects_learned_preferences(self):
        """Export reflects learned preferences."""
        from security.models import UserTypingProfile
        from security.services.adaptive_password_service import AdaptivePasswordService

        UserTypingProfile.objects.create(
            user=self.user,
            total_sessions=12,
            preferred_substitutions={'a': '@'},
            substitution_confidence={'o->0': 0.95},
        )
        model = AdaptivePasswordService(self.user).export_preference_model()
        self.assertEqual(model['model_version'], 12)
        self.assertAlmostEqual(model['substitution_weights']['o']['0'], 0.95)
        # Explicit preference gets a strong weight.
        self.assertGreaterEqual(model['substitution_weights']['a']['@'], 0.9)

    def test_record_v2_stores_fingerprint_not_password(self):
        """Record v2 stores fingerprint not password."""
        from security.models import AdaptivePasswordConfig, TypingSession
        from security.services.adaptive_password_service import AdaptivePasswordService

        AdaptivePasswordConfig.objects.create(
            user=self.user, is_enabled=True, consent_given_at=timezone.now()
        )
        result = AdaptivePasswordService(self.user).record_typing_session_v2(
            password_fingerprint=FP_ORIGINAL,
            length_bucket=3,
            keystroke_timings=[100, 120, 90, 110],
            backspace_positions=[],
        )
        self.assertEqual(result['schema_version'], 2)
        session = TypingSession.objects.get(id=result['session_id'])
        self.assertEqual(session.password_fingerprint, FP_ORIGINAL)
        self.assertEqual(session.length_bucket, 3)
        # The legacy raw/derived-password columns no longer exist on the model.
        field_names = {f.name for f in session._meta.get_fields()}
        self.assertNotIn('password_hash_prefix', field_names)
        self.assertNotIn('password_length', field_names)

    def test_apply_v2_chains_by_fingerprint_and_masks_previews(self):
        """Apply v2 chains by fingerprint and masks previews."""
        from security.models import AdaptivePasswordConfig, PasswordAdaptation
        from security.services.adaptive_password_service import AdaptivePasswordService

        # apply is gated on opt-in, same as record.
        AdaptivePasswordConfig.objects.create(
            user=self.user, is_enabled=True, consent_given_at=timezone.now()
        )
        service = AdaptivePasswordService(self.user)
        result = service.apply_adaptation_v2(
            original_fingerprint=FP_ORIGINAL,
            adapted_fingerprint=FP_ADAPTED,
            substitution_classes=[{'from': 'o', 'to': '0', 'confidence': 0.9}],
            previews={'original_masked': 'pa***rd', 'adapted_masked': 'pa***rd'},
            memorability_improvement=0.15,
        )
        self.assertEqual(result['generation'], 1)
        adaptation = PasswordAdaptation.objects.get(id=result['adaptation_id'])
        self.assertEqual(adaptation.original_fingerprint, FP_ORIGINAL)
        self.assertEqual(adaptation.adapted_fingerprint, FP_ADAPTED)
        self.assertEqual(adaptation.original_masked, 'pa***rd')

        # A follow-up adaptation chains off the previous one (rollback support).
        second = service.apply_adaptation_v2(
            original_fingerprint=FP_ADAPTED,
            adapted_fingerprint='NewFp0123456789-_aAbBcC',
            substitution_classes=[{'from': 'a', 'to': '@'}],
        )
        self.assertEqual(second['generation'], 2)
        self.assertTrue(second['can_rollback'])

    def test_unique_active_adapted_fingerprint_enforced(self):
        """The DB rejects a second ACTIVE adaptation for the same fingerprint."""
        from security.models import PasswordAdaptation

        PasswordAdaptation.objects.create(
            user=self.user,
            original_fingerprint=FP_ORIGINAL,
            adapted_fingerprint=FP_ADAPTED,
            adaptation_type='substitution',
            confidence_score=0.8,
            status='active',
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PasswordAdaptation.objects.create(
                    user=self.user,
                    original_fingerprint='OtherFp0123456789-_xYz',
                    adapted_fingerprint=FP_ADAPTED,  # same active fingerprint → clash
                    adaptation_type='substitution',
                    confidence_score=0.8,
                    status='active',
                )

    def test_empty_fingerprint_rows_are_not_constrained(self):
        """The partial-unique constraint excludes empty-fingerprint rows, so any
        such rows (e.g. placeholder/pending) never collide with each other."""
        from security.models import PasswordAdaptation

        for generation in (1, 2):
            PasswordAdaptation.objects.create(
                user=self.user,
                adaptation_generation=generation,
                adaptation_type='substitution',
                confidence_score=0.8,
                status='active',  # adapted_fingerprint defaults to '' → excluded
            )
        self.assertEqual(
            PasswordAdaptation.objects.filter(user=self.user, status='active').count(), 2
        )

    def test_unique_active_original_fingerprint_prevents_fork(self):
        """At most one ACTIVE adaptation per original_fingerprint, so concurrent
        applies from the same head cannot fork the rollback chain."""
        from security.models import PasswordAdaptation

        PasswordAdaptation.objects.create(
            user=self.user,
            original_fingerprint=FP_ORIGINAL,
            adapted_fingerprint=FP_ADAPTED,
            adaptation_type='substitution',
            confidence_score=0.8,
            status='active',
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PasswordAdaptation.objects.create(
                    user=self.user,
                    original_fingerprint=FP_ORIGINAL,  # same active head → clash
                    adapted_fingerprint='DifferentFp0123456789-_x',
                    adaptation_type='substitution',
                    confidence_score=0.8,
                    status='active',
                )

    def test_record_v2_uses_explicit_success_over_backspaces(self):
        """An explicit success flag overrides the 'no backspaces' heuristic, so a
        corrected typo is not mis-recorded as a failed attempt."""
        from security.models import AdaptivePasswordConfig, TypingSession
        from security.services.adaptive_password_service import AdaptivePasswordService

        AdaptivePasswordConfig.objects.create(
            user=self.user, is_enabled=True, consent_given_at=timezone.now()
        )
        result = AdaptivePasswordService(self.user).record_typing_session_v2(
            password_fingerprint=FP_ORIGINAL,
            length_bucket=3,
            keystroke_timings=[100, 120, 90],
            backspace_positions=[2, 5],  # corrected typos...
            success=True,                 # ...but ultimately entered correctly
        )
        session = TypingSession.objects.get(id=result['session_id'])
        self.assertTrue(session.success)
        self.assertTrue(result['success'])

    def test_apply_v2_requires_opt_in(self):
        """apply_adaptation_v2 is gated on opt-in, like record (no config → error)."""
        from security.services.adaptive_password_service import AdaptivePasswordService

        result = AdaptivePasswordService(self.user).apply_adaptation_v2(
            original_fingerprint=FP_ORIGINAL,
            adapted_fingerprint=FP_ADAPTED,
            substitution_classes=[{'from': 'o', 'to': '0'}],
        )
        self.assertIn('error', result)


# =============================================================================
# API: flag gating, 410 deprecation, 422 reject-plaintext, preference-model
# =============================================================================

class ZKV2APITests(APITestCase):

    def setUp(self):
        """Set up the test user/fixtures."""
        self.user = User.objects.create_user('zkapi', password='testpass123')
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def _enable(self):
        """Enable the adaptive feature (opt-in) for the test user."""
        from security.models import AdaptivePasswordConfig
        AdaptivePasswordConfig.objects.create(
            user=self.user, is_enabled=True, consent_given_at=timezone.now()
        )

    def test_record_session_v2_rejects_plaintext_password(self):
        """Record session v2 rejects plaintext password."""
        self._enable()
        response = self.client.post('/api/security/adaptive/record-session/', {
            'schema_version': 2,
            'password': 'hunter2',
            'password_fingerprint': FP_ORIGINAL,
            'length_bucket': 2,
            'keystroke_timings': [100, 120],
        }, format='json')
        self.assertEqual(response.status_code, 422)

    def test_record_session_v2_success(self):
        """Record session v2 success."""
        self._enable()
        response = self.client.post('/api/security/adaptive/record-session/', {
            'schema_version': 2,
            'fp_key_version': 1,
            'password_fingerprint': FP_ORIGINAL,
            'length_bucket': 3,
            'keystroke_timings': [100, 120, 90, 110],
            'backspace_positions': [],
            'device_type': 'desktop',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['schema_version'], 2)
        # The serialized response never echoes a password.
        self.assertNotIn('password', {k for k in response.data if k != 'schema_version'})

    def test_record_session_v2_requires_schema_version(self):
        """Record session v2 requires schema version."""
        self._enable()
        response = self.client.post('/api/security/adaptive/record-session/', {
            'password_fingerprint': FP_ORIGINAL,
            'length_bucket': 3,
            'keystroke_timings': [100],
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_suggest_is_deprecated_under_v2(self):
        """Suggest is deprecated under v2."""
        response = self.client.post('/api/security/adaptive/suggest/', {
            'password': 'whatever',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_410_GONE)
        self.assertIn('preference-model', str(response.data))

    def test_apply_v2_rejects_plaintext(self):
        """Apply v2 rejects plaintext."""
        response = self.client.post('/api/security/adaptive/apply/', {
            'schema_version': 2,
            'original_fingerprint': FP_ORIGINAL,
            'adapted_fingerprint': FP_ADAPTED,
            'original_password': 'old',
            'adapted_password': 'new',
            'substitutions': [{'from': 'o', 'to': '0'}],
        }, format='json')
        self.assertEqual(response.status_code, 422)

    def test_apply_v2_success(self):
        """Apply v2 success."""
        self._enable()  # apply is gated on opt-in
        response = self.client.post('/api/security/adaptive/apply/', {
            'schema_version': 2,
            'fp_key_version': 1,
            'original_fingerprint': FP_ORIGINAL,
            'adapted_fingerprint': FP_ADAPTED,
            'substitutions': [{'from': 'o', 'to': '0', 'confidence': 0.9}],
            'previews': {'original_masked': 'pa***rd', 'adapted_masked': 'pa***rd'},
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['schema_version'], 2)

    def test_preference_model_endpoint(self):
        """Preference model endpoint."""
        response = self.client.get('/api/security/adaptive/preference-model/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('model_version', response.data)
        self.assertIn('substitution_weights', response.data)
        self.assertIn('memorability_params', response.data)

    def test_preference_model_requires_auth(self):
        """Preference model requires auth."""
        self.client.logout()
        response = self.client.get('/api/security/adaptive/preference-model/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_suggest_is_always_deprecated(self):
        # Server-side suggestion is removed under ZK v2 — /suggest/ is 410 Gone.
        """Suggest is always deprecated."""
        response = self.client.post('/api/security/adaptive/suggest/', {
            'password': 'testpassword123',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_410_GONE)


# =============================================================================
# Phase 4 — memorability model + error signals (plan §6, gaps B4/B3/B6)
# =============================================================================

class MemorabilityModelTests(TestCase):
    """The learned half of the memorability model (plan §4.2).

    Scoring itself is client-side (it needs the raw password); what the server
    owns is the *parameters* that feed the client's scorer, and publishing them.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username='memuser', password='testpass123'
        )
        AdaptivePasswordConfig.objects.create(
            user=self.user, is_enabled=True, fingerprint_salt='memsalt'
        )
        self.service = AdaptivePasswordService(self.user)

    def _sessions(self, bucket, successes, failures=0):
        for index in range(successes + failures):
            TypingSession.objects.create(
                user=self.user,
                password_fingerprint=f'fp-{bucket}-{index}',
                length_bucket=bucket,
                success=index < successes,
                error_positions=[],
                error_count=0,
                timing_profile={},
                total_time_ms=1000,
            )

    def test_optimal_length_band_defaults_without_enough_evidence(self):
        self._sessions(bucket=4, successes=MIN_SESSIONS_FOR_LENGTH_BAND - 1)
        params = self.service.export_preference_model()['memorability_params']
        self.assertEqual(
            (params['optimal_length_min'], params['optimal_length_max']),
            DEFAULT_OPTIMAL_LENGTH,
        )

    def test_optimal_length_band_follows_the_most_successful_bucket(self):
        # Bucket 4 covers lengths 16-19 and wins on SUCCESSES, not on raw
        # session count -- bucket 2 has more sessions but mostly failures, so
        # weighting the distribution by success rate is what decides this.
        self._sessions(bucket=2, successes=2, failures=40)
        self._sessions(bucket=4, successes=MIN_SESSIONS_FOR_LENGTH_BAND + 2)

        params = self.service.export_preference_model()['memorability_params']
        self.assertEqual(params['optimal_length_min'], 16)
        self.assertEqual(params['optimal_length_max'], 19)

    def test_optimal_length_band_ignores_the_sub_four_character_bucket(self):
        # Bucket 0 is 0-3 characters. Publishing "your optimal length is 0-3"
        # would steer the client's length-fit scorer toward unusable
        # passwords, and such sessions are far more likely truncated entries
        # than a real preference.
        self._sessions(bucket=0, successes=MIN_SESSIONS_FOR_LENGTH_BAND * 5)
        params = self.service.export_preference_model()['memorability_params']
        self.assertEqual(
            (params['optimal_length_min'], params['optimal_length_max']),
            DEFAULT_OPTIMAL_LENGTH,
        )

    def test_weights_default_until_feedback_moves_them(self):
        params = self.service.export_preference_model()['memorability_params']
        self.assertEqual(params['weights'], DEFAULT_MEMORABILITY_WEIGHTS)

    def test_partial_stored_weights_fall_back_rather_than_blending(self):
        # A half-learned blob merged with defaults is a third thing neither
        # side intended, so an incomplete dict is rejected wholesale.
        UserTypingProfile.objects.create(
            user=self.user, memorability_weights={'length': 0.9},
        )
        params = self.service.export_preference_model()['memorability_params']
        self.assertEqual(params['weights'], DEFAULT_MEMORABILITY_WEIGHTS)

    def test_non_finite_stored_weights_fall_back(self):
        # float('inf') >= 0 is True, so a bare non-negativity check would let
        # it through and normalize every other weight to 0.
        for bad in (float('inf'), float('nan'), -1.0, 'x'):
            weights = dict(DEFAULT_MEMORABILITY_WEIGHTS)
            weights['variety'] = bad
            self.assertEqual(
                normalize_memorability_weights(weights),
                DEFAULT_MEMORABILITY_WEIGHTS,
                f'{bad!r} should have been rejected',
            )

    def test_positive_feedback_raises_the_driving_feature_weight(self):
        adaptation = PasswordAdaptation.objects.create(
            user=self.user, adaptation_type='substitution',
            confidence_score=0.8, status='active',
            substitutions_applied={'0': {'from': 'o', 'to': '0'}},
            memorability_driver='variety',
        )
        feedback = AdaptationFeedback.objects.create(
            adaptation=adaptation, user=self.user, rating=5,
            memorability_improved=True,
        )

        before = DEFAULT_MEMORABILITY_WEIGHTS['variety']
        weights = nudge_memorability_weights(adaptation, feedback)

        self.assertIsNotNone(weights)
        self.assertGreater(weights['variety'], before)
        self.assertAlmostEqual(sum(weights.values()), 1.0, places=9)

    def test_negative_feedback_lowers_the_driving_feature_weight(self):
        adaptation = PasswordAdaptation.objects.create(
            user=self.user, adaptation_type='substitution',
            confidence_score=0.8, status='active',
            memorability_driver='pronounceable',
        )
        feedback = AdaptationFeedback.objects.create(
            adaptation=adaptation, user=self.user, rating=2,
            memorability_improved=False,
        )

        before = DEFAULT_MEMORABILITY_WEIGHTS['pronounceable']
        weights = nudge_memorability_weights(adaptation, feedback)

        self.assertIsNotNone(weights)
        self.assertLess(weights['pronounceable'], before)

    def test_unanswered_or_undriven_feedback_teaches_nothing(self):
        # `memorability_improved = None` is "we do not know", which is not the
        # same as "no". Nudging on a non-answer would learn from the absence
        # of data. Same for an adaptation with no driver (a pre-Phase-4
        # client, which cannot tell us which feature moved).
        undriven = PasswordAdaptation.objects.create(
            user=self.user, adaptation_type='substitution',
            confidence_score=0.8, status='active', memorability_driver='',
        )
        driven = PasswordAdaptation.objects.create(
            user=self.user, adaptation_type='substitution',
            confidence_score=0.8, status='active', memorability_driver='variety',
        )
        unanswered = AdaptationFeedback.objects.create(
            adaptation=driven, user=self.user, rating=4,
            memorability_improved=None,
        )
        answered = AdaptationFeedback.objects.create(
            adaptation=undriven, user=self.user, rating=4,
            memorability_improved=True,
        )

        self.assertIsNone(nudge_memorability_weights(driven, unanswered))
        self.assertIsNone(nudge_memorability_weights(undriven, answered))
        self.assertFalse(
            UserTypingProfile.objects.filter(user=self.user)
            .exclude(memorability_weights={}).exists()
        )

    def test_repeated_negative_feedback_never_drives_a_weight_to_zero(self):
        # Zero is an absorbing state once the weights are renormalized: a
        # feature at exactly 0 can never be nudged back up, so a long run of
        # one-sided feedback would permanently delete a feature from the model.
        adaptation = PasswordAdaptation.objects.create(
            user=self.user, adaptation_type='substitution',
            confidence_score=0.8, status='active', memorability_driver='variety',
        )
        # One feedback row, applied repeatedly: AdaptationFeedback is unique
        # per (adaptation, user), and it is the weekly task's
        # `policy_reward_applied_at` stamp -- not this function -- that makes a
        # real run apply each row exactly once. Driving the EMA directly is
        # what isolates the absorbing-state question from that stamp.
        feedback = AdaptationFeedback.objects.create(
            adaptation=adaptation, user=self.user, rating=1,
            memorability_improved=False,
        )
        for _ in range(200):
            weights = nudge_memorability_weights(adaptation, feedback)

        self.assertGreater(weights['variety'], 0.0)
        self.assertAlmostEqual(sum(weights.values()), 1.0, places=9)


class ErrorPositionExportTests(TestCase):
    """`error_prone_positions` finally reaches a consumer (plan §4.3, gap B3)."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='erruser', password='testpass123'
        )
        AdaptivePasswordConfig.objects.create(
            user=self.user, is_enabled=True, fingerprint_salt='errsalt'
        )
        self.service = AdaptivePasswordService(self.user)

    def test_positions_are_published_in_the_preference_model(self):
        UserTypingProfile.objects.create(
            user=self.user, error_prone_positions={'3': 0.4, '7': 0.15},
        )
        model = self.service.export_preference_model()
        self.assertEqual(model['error_prone_positions'], {'3': 0.4, '7': 0.15})

    def test_malformed_positions_are_dropped_not_coerced(self):
        # A junk key coerced to 0 would boost whatever sits at the start of
        # every password on the client side.
        # `'inf'` as a STRING, not float('inf'): the column carries a JSON_VALID
        # check constraint and a bare float infinity cannot be stored at all
        # (SQLite rejects the INSERT). The string round-trips as valid JSON and
        # `float('inf')` parses it right back to a non-finite value, so this
        # reaches the `math.isfinite` guard through a path that can actually
        # occur in stored data.
        UserTypingProfile.objects.create(
            user=self.user,
            error_prone_positions={
                'x': 0.5, '-1': 0.5, '2': 'nope', '4': 'inf', '5': 0.3,
            },
        )
        model = self.service.export_preference_model()
        self.assertEqual(model['error_prone_positions'], {'5': 0.3})

    def test_rates_are_clamped_into_zero_one(self):
        UserTypingProfile.objects.create(
            user=self.user, error_prone_positions={'1': 5.0, '2': -3.0},
        )
        model = self.service.export_preference_model()
        self.assertEqual(model['error_prone_positions'], {'1': 1.0, '2': 0.0})

    def test_empty_when_the_user_has_no_profile(self):
        model = self.service.export_preference_model()
        self.assertEqual(model['error_prone_positions'], {})


class DeadProfileFieldTests(TestCase):
    """`wpm_variance`, `rhythm_signature`, `common_error_types` (gap B6)."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='b6user', password='testpass123'
        )
        AdaptivePasswordConfig.objects.create(
            user=self.user, is_enabled=True, fingerprint_salt='b6salt'
        )
        self.service = AdaptivePasswordService(self.user)

    def _record(self, timings, backspaces=()):
        return self.service.record_typing_session_v2(
            password_fingerprint='fp-b6-' + str(len(timings)),
            length_bucket=3,
            keystroke_timings=list(timings),
            backspace_positions=list(backspaces),
            success=True,
        )

    def test_wpm_variance_is_written_and_grows_with_spread(self):
        self._record([100] * 12)
        profile = UserTypingProfile.objects.get(user=self.user)
        # First observation has no deviation to measure yet -- 0.0, not None,
        # so the field stops reading as "never written".
        self.assertEqual(profile.wpm_variance, 0.0)

        self._record([900] * 12)
        profile.refresh_from_db()
        self.assertGreater(profile.wpm_variance, 0.0)

    def test_rhythm_vector_is_scale_free(self):
        # Asserted on the pure helper, NOT end-to-end. `record_typing_session_v2`
        # runs every session through `PrivacyGuard.sanitize_pattern`, which adds
        # Laplace noise to the timing buckets before the profile ever sees them
        # -- so uniform input does not stay uniform downstream, and an
        # end-to-end "every bin is exactly 1.0" assertion measures the DP noise
        # rather than the scale-freeness it claims to test.
        fast = AdaptivePasswordService._rhythm_vector({i: 100 for i in range(16)})
        slow = AdaptivePasswordService._rhythm_vector({i: 700 for i in range(16)})

        self.assertEqual(len(fast), RHYTHM_BINS)
        self.assertEqual(fast, slow)
        for value in fast:
            self.assertAlmostEqual(value, 1.0, places=6)

        # A genuine shape difference DOES move the vector: slow start, fast end.
        ramp = AdaptivePasswordService._rhythm_vector(
            {i: (400 if i < 8 else 100) for i in range(16)}
        )
        self.assertGreater(ramp[0], ramp[-1])

    def test_rhythm_vector_sorts_string_keys_numerically(self):
        # TypingSession.timing_profile is a JSONField; if a caller ever
        # passes a stored profile back in, its keys arrive as STRINGS
        # ('0', '1', ..., '10', ...), not ints -- a lexicographic sort
        # would scramble the shape ('10' sorts before '2'). Same fixture
        # as the ramp case above (slow start, fast end), string-keyed, to
        # prove positions sort numerically regardless of key type.
        int_keyed = AdaptivePasswordService._rhythm_vector(
            {i: (400 if i < 8 else 100) for i in range(16)}
        )
        string_keyed = AdaptivePasswordService._rhythm_vector(
            {str(i): (400 if i < 8 else 100) for i in range(16)}
        )
        self.assertEqual(string_keyed, int_keyed)

    def test_rhythm_vector_handles_unusable_sessions(self):
        self.assertIsNone(AdaptivePasswordService._rhythm_vector({}))
        self.assertIsNone(AdaptivePasswordService._rhythm_vector({0: 0, 1: 0}))

    def test_rhythm_signature_is_persisted_with_a_fixed_length(self):
        self._record([100] * 16)
        profile = UserTypingProfile.objects.get(user=self.user)

        self.assertEqual(len(profile.rhythm_signature), RHYTHM_BINS)
        for value in profile.rhythm_signature:
            self.assertIsInstance(value, float)
            self.assertGreater(value, 0.0)

        # A second session of a different length must not change the vector's
        # length -- fixed bins are what make element-wise blending possible.
        self._record([120] * 5)
        profile.refresh_from_db()
        self.assertEqual(len(profile.rhythm_signature), RHYTHM_BINS)

    def test_common_error_types_classifies_adjacency(self):
        # Two corrections at adjacent positions read as a transposition; an
        # isolated one reads as a single-character (adjacent-key) slip.
        self._record([120] * 10, backspaces=[4, 5])
        profile = UserTypingProfile.objects.get(user=self.user)
        self.assertGreater(profile.common_error_types.get('transposition', 0), 0)
        self.assertAlmostEqual(sum(profile.common_error_types.values()), 1.0, places=6)

    def test_a_clean_session_does_not_rewrite_the_error_distribution(self):
        # Zero errors is not evidence about which error TYPE dominates.
        self._record([120] * 10, backspaces=[4, 5])
        profile = UserTypingProfile.objects.get(user=self.user)
        before = dict(profile.common_error_types)

        self._record([120] * 10, backspaces=[])
        profile.refresh_from_db()
        self.assertEqual(profile.common_error_types, before)

    def test_record_typing_session_does_not_clobber_concurrent_weight_nudge(self):
        """`_update_typing_profile` is the request-path writer, the third of
        three sites this same clobber bug was found and fixed on this PR.

        Same interleaving-forcing technique as `aggregate_typing_profiles`'
        regression test: patch `get_or_create` so a concurrent write lands
        between this method's read and its own later save, which its
        in-memory instance cannot see.
        """
        from unittest.mock import patch

        concurrent_weights = {
            'length': 0.05, 'patterns': 0.15, 'variety': 0.5, 'pronounceable': 0.3,
        }
        real_get_or_create = UserTypingProfile.objects.get_or_create

        def racing_get_or_create(*args, **kwargs):
            result = real_get_or_create(*args, **kwargs)
            UserTypingProfile.objects.filter(user=self.user).update(
                memorability_weights=concurrent_weights,
            )
            return result

        with patch.object(
            UserTypingProfile.objects, 'get_or_create',
            side_effect=racing_get_or_create,
        ):
            self._record([120] * 10, backspaces=[])

        profile = UserTypingProfile.objects.get(user=self.user)
        self.assertEqual(profile.total_sessions, 1)
        self.assertEqual(profile.memorability_weights, concurrent_weights)


class MemorabilityScorePersistenceTests(APITestCase):
    """The client's readings reach `PasswordAdaptation` (plan §4.1, gap B4)."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='scoreuser', password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        self.config = AdaptivePasswordConfig.objects.create(
            user=self.user, is_enabled=True, fingerprint_salt='scoresalt'
        )

    def _apply(self, **overrides):
        payload = {
            'schema_version': 2,
            'fp_key_version': self.config.fp_key_version,
            'original_fingerprint': 'AAAAAAAAAAAAAAAAAAAAAAAA',
            'adapted_fingerprint': 'BBBBBBBBBBBBBBBBBBBBBBBB',
            'substitutions': [{'from': 'o', 'to': '0', 'confidence': 0.9}],
            'previews': {'original_masked': 'pa***rd', 'adapted_masked': 'pa***rd'},
        }
        payload.update(overrides)
        return self.client.post(
            '/api/security/adaptive/apply/', payload, format='json'
        )

    def test_scores_are_persisted_and_reach_the_evolution_stats(self):
        response = self._apply(
            memorability_improvement=-0.30,
            memorability_score_before=0.55,
            memorability_score_after=0.25,
            memorability_driver='variety',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        adaptation = PasswordAdaptation.objects.get(user=self.user)
        self.assertAlmostEqual(adaptation.memorability_score_before, 0.55)
        self.assertAlmostEqual(adaptation.memorability_score_after, 0.25)
        self.assertEqual(adaptation.memorability_driver, 'variety')

        # The direct regression test for the always-0 bug: before Phase 4 both
        # columns were hard-None, so this average could never be anything else.
        stats = self.client.get('/api/security/adaptive/stats/')
        self.assertEqual(stats.status_code, status.HTTP_200_OK)
        self.assertAlmostEqual(
            stats.data['average_memorability_improvement'], -0.30, places=6
        )

    def test_a_positive_improvement_is_reported_as_non_zero(self):
        self._apply(
            memorability_score_before=0.40,
            memorability_score_after=0.55,
        )
        stats = self.client.get('/api/security/adaptive/stats/')
        self.assertAlmostEqual(
            stats.data['average_memorability_improvement'], 0.15, places=6
        )

    def test_scores_are_omitted_together_or_not_at_all(self):
        # get_evolution_stats keys off `before is not None` and would average a
        # delta against an implicit 0, so half a pair is worse than none.
        response = self._apply(memorability_score_after=0.25)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        adaptation = PasswordAdaptation.objects.get(user=self.user)
        self.assertIsNone(adaptation.memorability_score_before)
        self.assertIsNone(adaptation.memorability_score_after)

        stats = self.client.get('/api/security/adaptive/stats/')
        self.assertEqual(stats.data['average_memorability_improvement'], 0)

    def test_out_of_range_scores_are_rejected(self):
        for field in ('memorability_score_before', 'memorability_score_after'):
            response = self._apply(**{field: 1.5})
            self.assertEqual(
                response.status_code, status.HTTP_400_BAD_REQUEST, field
            )

    def test_reason_text_derives_delta_from_scores_not_the_raw_client_value(self):
        # Real gap (round 7 review): memorability_improvement and the
        # before/after pair are computed independently client-side, so
        # nothing guarantees they agree -- an inconsistent payload could
        # make the audit-trail reason text disagree with the scores actually
        # stored for the same row. Deliberately sending a WRONG improvement
        # (+0.99) alongside a correct, consistent before/after pair (delta
        # -0.30) proves the reason text uses the derived value, not the
        # client's raw one, once both scores are available -- closing the
        # gap without rejecting the request (rejecting would need to also
        # reject a lone score, which test_scores_are_omitted_together_or_
        # not_at_all already establishes as intentionally accepted).
        self._apply(
            memorability_improvement=0.99,
            memorability_score_before=0.55,
            memorability_score_after=0.25,
        )
        adaptation = PasswordAdaptation.objects.get(user=self.user)
        self.assertIn('Δ=-0.30', adaptation.reason)
        self.assertNotIn('Δ=+0.99', adaptation.reason)

    def test_reason_text_uses_the_raw_improvement_when_no_score_pair_is_sent(self):
        # A pre-Phase-4 client sends only the delta, no absolute scores --
        # nothing to derive from, so the raw value is still the best
        # available signal and must not be dropped.
        self._apply(memorability_improvement=0.42)
        adaptation = PasswordAdaptation.objects.get(user=self.user)
        self.assertIn('Δ=+0.42', adaptation.reason)

    def test_an_unknown_driver_is_rejected(self):
        # A free-text driver would accumulate weight against a key
        # export_preference_model never reads.
        response = self._apply(memorability_driver='vibes')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_a_pre_phase_four_client_still_records_an_adaptation(self):
        response = self._apply()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        adaptation = PasswordAdaptation.objects.get(user=self.user)
        self.assertIsNone(adaptation.memorability_score_before)
        self.assertEqual(adaptation.memorability_driver, '')

    def test_gdpr_export_includes_the_learned_memorability_fields(self):
        # A real gap: export_adaptive_data was written before Phase 4 and
        # never updated, so a GDPR export stopped being complete the moment
        # a user's first feedback nudged their memorability weights.
        self._apply(memorability_driver='variety')
        UserTypingProfile.objects.create(
            user=self.user,
            memorability_weights={'length': 0.1, 'patterns': 0.2,
                                   'variety': 0.4, 'pronounceable': 0.3},
            wpm_variance=12.5,
            common_error_types={'transposition': 1.0},
            rhythm_signature=[1.0] * RHYTHM_BINS,
        )

        export = self.client.get('/api/security/adaptive/export/').data

        self.assertEqual(
            export['typing_profile']['memorability_weights']['variety'], 0.4,
        )
        self.assertEqual(export['typing_profile']['wpm_variance'], 12.5)
        self.assertEqual(
            export['typing_profile']['common_error_types'], {'transposition': 1.0},
        )
        self.assertEqual(
            export['typing_profile']['rhythm_signature'], [1.0] * RHYTHM_BINS,
        )
        self.assertEqual(
            export['adaptations'][0]['memorability_driver'], 'variety',
        )

    def test_export_reports_a_zero_before_score_as_a_real_delta(self):
        # `before` truthy-checked instead of `is not None` would treat a real
        # 0.0 reading as "missing" and report null instead of the delta —
        # the same class of bug get_evolution_stats already guards against.
        self._apply(
            memorability_score_before=0.0,
            memorability_score_after=0.4,
        )

        export = self.client.get('/api/security/adaptive/export/').data

        self.assertAlmostEqual(
            export['adaptations'][0]['memorability_improvement'], 0.4, places=6
        )


# =============================================================================
# Phase 5 — suggestion cadence (plan §5.2, gap B5)
# =============================================================================

class SuggestionCadenceTests(APITestCase):
    """`should_suggest_adaptation()` finally has a non-test caller."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='cadenceuser', password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        self.config = AdaptivePasswordConfig.objects.create(
            user=self.user, is_enabled=True, fingerprint_salt='cadencesalt',
            suggestion_frequency_days=30,
        )

    def _config(self):
        response = self.client.get('/api/security/adaptive/config/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.data

    def test_due_when_no_suggestion_has_ever_been_made(self):
        self.assertTrue(self._config()['should_suggest'])

    def test_not_due_inside_the_cadence_window(self):
        self.config.last_suggestion_at = timezone.now() - timedelta(days=5)
        self.config.save()
        self.assertFalse(self._config()['should_suggest'])

    def test_due_again_once_the_window_has_passed(self):
        self.config.last_suggestion_at = timezone.now() - timedelta(days=31)
        self.config.save()
        self.assertTrue(self._config()['should_suggest'])

    def test_auto_suggest_off_overrides_a_due_cadence(self):
        # AND-ed server-side rather than left to the client to combine: a
        # client that reads one field and not the other must not be able to
        # nag a user who turned suggestions off.
        self.config.auto_suggest_enabled = False
        self.config.save()
        self.assertTrue(self.config.should_suggest_adaptation())
        self.assertFalse(self._config()['should_suggest'])

    def test_auto_apply_threshold_is_published(self):
        data = self._config()
        self.assertIn('auto_apply_high_confidence', data)
        self.assertEqual(
            data['auto_apply_threshold'],
            settings.ADAPTIVE_PASSWORD['AUTO_APPLY_THRESHOLD'],
        )

    def test_auto_apply_threshold_fails_safe_when_misconfigured(self):
        # 1.0 means "nothing is confident enough to auto-apply". Defaulting
        # low would silently auto-rotate credentials on a broken deployment.
        for bad in ('nonsense', None, -1, 5.0, float('nan')):
            with self.settings(
                ADAPTIVE_PASSWORD={
                    **settings.ADAPTIVE_PASSWORD, 'AUTO_APPLY_THRESHOLD': bad
                }
            ):
                self.assertEqual(self._config()['auto_apply_threshold'], 1.0, bad)
