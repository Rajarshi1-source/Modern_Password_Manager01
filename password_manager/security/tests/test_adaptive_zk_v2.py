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

from django.test import TestCase
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.test import APITestCase, APIClient
from rest_framework import status

from security.serializers.adaptive_serializers import (
    TypingSessionInputV2Serializer,
    ApplyAdaptationV2Serializer,
    PlaintextRejected,
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

    def _base_record(self, **overrides):
        """Build a base valid v2 record-session payload."""
        data = {
            'schema_version': 2,
            'password_fingerprint': FP_ORIGINAL,
            'length_bucket': 3,
            'keystroke_timings': [100, 120, 90],
        }
        data.update(overrides)
        return data

    def test_valid_record_payload(self):
        """Valid record payload."""
        serializer = TypingSessionInputV2Serializer(data=self._base_record())
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_rejects_bad_fingerprint_charset(self):
        """Rejects bad fingerprint charset."""
        serializer = TypingSessionInputV2Serializer(
            data=self._base_record(password_fingerprint='not valid! chars')
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn('password_fingerprint', serializer.errors)

    def test_rejects_short_fingerprint(self):
        """Rejects short fingerprint."""
        serializer = TypingSessionInputV2Serializer(
            data=self._base_record(password_fingerprint='short')
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn('password_fingerprint', serializer.errors)

    def test_rejects_wrong_schema_version(self):
        """Rejects wrong schema version."""
        serializer = TypingSessionInputV2Serializer(
            data=self._base_record(schema_version=1)
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn('schema_version', serializer.errors)

    def test_rejects_missing_schema_version(self):
        """Rejects missing schema version."""
        payload = self._base_record()
        payload.pop('schema_version')
        serializer = TypingSessionInputV2Serializer(data=payload)
        self.assertFalse(serializer.is_valid())
        self.assertIn('schema_version', serializer.errors)

    def test_apply_rejects_equal_fingerprints(self):
        """Apply rejects equal fingerprints."""
        serializer = ApplyAdaptationV2Serializer(data={
            'schema_version': 2,
            'original_fingerprint': FP_ORIGINAL,
            'adapted_fingerprint': FP_ORIGINAL,  # same → invalid
            'substitutions': [{'from': 'o', 'to': '0'}],
        })
        self.assertFalse(serializer.is_valid())

    def test_apply_rejects_non_class_substitution(self):
        """Apply rejects non class substitution."""
        serializer = ApplyAdaptationV2Serializer(data={
            'schema_version': 2,
            'original_fingerprint': FP_ORIGINAL,
            'adapted_fingerprint': FP_ADAPTED,
            'substitutions': [{'from': 'oo', 'to': '0'}],  # 'from' not single char
        })
        self.assertFalse(serializer.is_valid())

    def test_apply_rejects_extra_substitution_field(self):
        # Position/char metadata could reveal the password — reject extra keys.
        """Apply rejects extra substitution field."""
        serializer = ApplyAdaptationV2Serializer(data={
            'schema_version': 2,
            'original_fingerprint': FP_ORIGINAL,
            'adapted_fingerprint': FP_ADAPTED,
            'substitutions': [{'from': 'o', 'to': '0', 'position': 3}],
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('substitutions', serializer.errors)

    def test_apply_rejects_plaintext_preview(self):
        # A "preview" with no mask character is plaintext — reject it.
        """Apply rejects plaintext preview."""
        serializer = ApplyAdaptationV2Serializer(data={
            'schema_version': 2,
            'original_fingerprint': FP_ORIGINAL,
            'adapted_fingerprint': FP_ADAPTED,
            'substitutions': [{'from': 'o', 'to': '0'}],
            'previews': {'original_masked': 'password', 'adapted_masked': 'passw0rd'},
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('previews', serializer.errors)

    def test_apply_accepts_masked_preview(self):
        """Apply accepts masked preview."""
        serializer = ApplyAdaptationV2Serializer(data={
            'schema_version': 2,
            'original_fingerprint': FP_ORIGINAL,
            'adapted_fingerprint': FP_ADAPTED,
            'substitutions': [{'from': 'o', 'to': '0'}],
            'previews': {'original_masked': 'pa***rd', 'adapted_masked': 'pa***rd'},
        })
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
