"""Adaptive-password bandit tests (Phase 3).

Covers what turned the logging stub into a real, persistent policy:

1. **Reward shaping.** The composite reward's four components, the
   renormalization that happens when one of them has no signal, and the
   behavioural term computed by joining two opaque fingerprints.
2. **Both ends of the loop.** Applying an adaptation credits its arms;
   rolling one back drives them down. Before Phase 3 accepting a suggestion
   taught the model nothing at all.
3. **Convergence.** A class that always rewards must end up outranking one
   that never does — and the test that proves it must *fail* when the policy
   update is neutralized, or it proves nothing.
4. **Zero knowledge.** The behavioural query must touch no password-bearing
   column.

See docs/epigenetic-adaptation-implementation-plan.md §5.
"""

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from security.models import (
    AdaptationFeedback,
    AdaptivePasswordConfig,
    DEFAULT_DECAY,
    GlobalSubstitutionPrior,
    PasswordAdaptation,
    SubstitutionPolicyArm,
    TypingSession,
    UserTypingProfile,
    PRIOR_ALPHA,
    PRIOR_BETA,
)
from security.services.adaptive_password_service import (
    AdaptivePasswordService, PrivacyGuard,
)
from security.services.adaptive_policy_service import (
    ACCEPTANCE_REWARD,
    GLOBAL_PRIOR_STRENGTH,
    MIN_BEHAVIOURAL_SESSIONS,
    MIN_CONTRIBUTING_USERS,
    REWARD_WEIGHTS,
    ROLLBACK_REWARD,
    behavioural_reward,
    composite_reward,
    credit_adaptation,
    credit_arms,
    explicit_feedback_reward,
    policy_weights,
    rebuild_global_priors,
    substitution_classes,
)
from security.tasks.adaptive_tasks import update_rl_model_from_feedback

FP_ORIGINAL = 'AbCdEf0123456789-_XyZwQr'
FP_ADAPTED = 'ZyXwVu9876543210-_MnOpQr'


def _make_user(username, **config_kwargs):
    user = User.objects.create_user(username=username, password='irrelevant-to-this-test')
    AdaptivePasswordConfig.objects.create(
        user=user,
        is_enabled=True,
        consent_given_at=timezone.now(),
        fingerprint_salt='0123456789abcdef0123456789abcdef',
        **config_kwargs,
    )
    return user


def _make_adaptation(user, classes, status='active', fp_key_version=1, **kwargs):
    return PasswordAdaptation.objects.create(
        user=user,
        original_fingerprint=kwargs.pop('original_fingerprint', FP_ORIGINAL),
        adapted_fingerprint=kwargs.pop('adapted_fingerprint', FP_ADAPTED),
        fp_key_version=fp_key_version,
        adaptation_type='substitution',
        substitutions_applied={
            str(i): {'from': f, 'to': t} for i, (f, t) in enumerate(classes)
        },
        confidence_score=0.8,
        status=status,
        decided_at=timezone.now(),
        **kwargs,
    )


def _sessions(user, fingerprint, count, error_count, total_time_ms, fp_key_version=1):
    TypingSession.objects.bulk_create([
        TypingSession(
            user=user,
            password_fingerprint=fingerprint,
            fp_key_version=fp_key_version,
            length_bucket=3,
            success=True,
            error_count=error_count,
            error_positions=list(range(error_count)),
            total_time_ms=total_time_ms,
        )
        for _ in range(count)
    ])


class RewardShapingTests(TestCase):
    """The four components and how they combine."""

    def setUp(self):
        self.user = _make_user('reward-user')

    def test_substitution_classes_collapse_duplicates(self):
        # A password with three o->0 substitutions is ONE piece of evidence
        # about the o->0 arm, not three.
        adaptation = _make_adaptation(self.user, [('o', '0'), ('o', '0'), ('a', '@')])
        self.assertEqual(substitution_classes(adaptation), {('o', '0'), ('a', '@')})

    def test_explicit_feedback_reward_matches_the_pre_phase3_shaping(self):
        adaptation = _make_adaptation(self.user, [('o', '0')])
        cases = [
            (5, False, False, False, 1.0),
            (4, False, False, False, 1.0),
            (3, False, False, False, 0.5),
            (2, False, False, False, 0.0),
            (1, False, False, False, 0.0),
            # Bonuses stack and cap at 1.0.
            (3, True, True, True, 1.0),
            (1, True, False, False, 0.2),
        ]
        for rating, accuracy, memorability, speed, expected in cases:
            with self.subTest(rating=rating):
                feedback = AdaptationFeedback(
                    adaptation=adaptation,
                    user=self.user,
                    rating=rating,
                    typing_accuracy_improved=accuracy,
                    memorability_improved=memorability,
                    typing_speed_improved=speed,
                )
                self.assertAlmostEqual(explicit_feedback_reward(feedback), expected)

    def test_behavioural_term_needs_enough_sessions_on_both_sides(self):
        adaptation = _make_adaptation(self.user, [('o', '0')])

        # Nothing recorded yet.
        self.assertIsNone(behavioural_reward(adaptation))

        # Enough on the original side only.
        _sessions(self.user, FP_ORIGINAL, MIN_BEHAVIOURAL_SESSIONS, 3, 4000)
        self.assertIsNone(behavioural_reward(adaptation))

        # One short on the adapted side.
        _sessions(self.user, FP_ADAPTED, MIN_BEHAVIOURAL_SESSIONS - 1, 1, 3000)
        self.assertIsNone(behavioural_reward(adaptation))

        # Threshold reached on both.
        _sessions(self.user, FP_ADAPTED, 1, 1, 3000)
        self.assertIsNotNone(behavioural_reward(adaptation))

    def test_behavioural_term_rewards_fewer_errors_and_less_time(self):
        adaptation = _make_adaptation(self.user, [('o', '0')])
        _sessions(self.user, FP_ORIGINAL, 5, error_count=4, total_time_ms=8000)
        _sessions(self.user, FP_ADAPTED, 5, error_count=1, total_time_ms=4000)

        reward = behavioural_reward(adaptation)
        self.assertGreater(reward, 0.5)

    def test_behavioural_term_punishes_more_errors_and_more_time(self):
        adaptation = _make_adaptation(self.user, [('o', '0')])
        _sessions(self.user, FP_ORIGINAL, 5, error_count=1, total_time_ms=3000)
        _sessions(self.user, FP_ADAPTED, 5, error_count=5, total_time_ms=9000)

        self.assertLess(behavioural_reward(adaptation), 0.5)

    def test_behavioural_term_is_neutral_when_nothing_changed(self):
        adaptation = _make_adaptation(self.user, [('o', '0')])
        _sessions(self.user, FP_ORIGINAL, 5, error_count=2, total_time_ms=5000)
        _sessions(self.user, FP_ADAPTED, 5, error_count=2, total_time_ms=5000)

        self.assertAlmostEqual(behavioural_reward(adaptation), 0.5)

    def test_behavioural_term_is_era_scoped(self):
        # Sessions recorded under a superseded era describe fingerprints the
        # client can no longer derive; folding them in would score this
        # adaptation on measurements of a different password.
        adaptation = _make_adaptation(self.user, [('o', '0')], fp_key_version=2)
        _sessions(self.user, FP_ORIGINAL, 5, 4, 8000, fp_key_version=1)
        _sessions(self.user, FP_ADAPTED, 5, 1, 4000, fp_key_version=1)

        self.assertIsNone(behavioural_reward(adaptation))

        _sessions(self.user, FP_ORIGINAL, 5, 4, 8000, fp_key_version=2)
        _sessions(self.user, FP_ADAPTED, 5, 1, 4000, fp_key_version=2)
        self.assertIsNotNone(behavioural_reward(adaptation))

    def test_behavioural_query_touches_no_password_bearing_column(self):
        # Zero-knowledge assertion. The whole reward rests on being able to
        # measure improvement WITHOUT either password, so the SQL must name
        # only the opaque fingerprint and era columns.
        adaptation = _make_adaptation(self.user, [('o', '0')])
        _sessions(self.user, FP_ORIGINAL, 5, 4, 8000)
        _sessions(self.user, FP_ADAPTED, 5, 1, 4000)

        with CaptureQueriesContext(connection) as ctx:
            behavioural_reward(adaptation)

        sql = ' '.join(q['sql'] for q in ctx.captured_queries).lower()
        self.assertIn('password_fingerprint', sql)
        for forbidden in ('original_password', 'adapted_password', 'password_hash',
                          'plaintext', 'encrypted_password'):
            self.assertNotIn(forbidden, sql)

    def test_composite_renormalizes_when_components_are_missing(self):
        # With no feedback and no behavioural data, only acceptance (0.2) and
        # rollback (0.2) contribute. An active adaptation therefore scores 1.0
        # -- NOT 0.4 -- because the missing components are dropped rather than
        # implicitly scored zero.
        adaptation = _make_adaptation(self.user, [('o', '0')], status='active')
        reward, components = composite_reward(adaptation, feedback=None)

        self.assertIsNone(components['rating'])
        self.assertIsNone(components['behavioural'])
        self.assertAlmostEqual(reward, 1.0)

    def test_composite_uses_all_four_components_when_available(self):
        adaptation = _make_adaptation(self.user, [('o', '0')], status='active')
        _sessions(self.user, FP_ORIGINAL, 5, error_count=2, total_time_ms=5000)
        _sessions(self.user, FP_ADAPTED, 5, error_count=2, total_time_ms=5000)
        feedback = AdaptationFeedback.objects.create(
            adaptation=adaptation, user=self.user, rating=3,
        )

        reward, components = composite_reward(adaptation, feedback)

        self.assertEqual(components['rating'], 0.5)
        self.assertEqual(components['acceptance'], 1.0)
        self.assertEqual(components['rollback'], 1.0)
        self.assertAlmostEqual(components['behavioural'], 0.5)
        expected = (
            REWARD_WEIGHTS['rating'] * 0.5
            + REWARD_WEIGHTS['acceptance'] * 1.0
            + REWARD_WEIGHTS['rollback'] * 1.0
            + REWARD_WEIGHTS['behavioural'] * 0.5
        )
        self.assertAlmostEqual(reward, expected)

    def test_rollback_is_a_hard_zero_on_its_own_component(self):
        adaptation = _make_adaptation(self.user, [('o', '0')], status='rolled_back')
        _, components = composite_reward(adaptation, feedback=None)
        self.assertEqual(components['rollback'], 0.0)
        self.assertEqual(components['acceptance'], 0.0)


class ArmUpdateTests(TestCase):
    """Beta posterior mechanics."""

    def setUp(self):
        self.user = _make_user('arm-user')

    def test_a_fresh_arm_starts_at_the_flat_prior(self):
        arm = SubstitutionPolicyArm.objects.create(
            user=self.user, from_char='o', to_char='0', fp_key_version=1,
        )
        self.assertEqual(arm.alpha, PRIOR_ALPHA)
        self.assertEqual(arm.beta, PRIOR_BETA)
        self.assertAlmostEqual(arm.posterior_mean, 0.5)

    def test_positive_rewards_raise_the_posterior_and_negatives_lower_it(self):
        good = SubstitutionPolicyArm(user=self.user, from_char='o', to_char='0')
        bad = SubstitutionPolicyArm(user=self.user, from_char='a', to_char='4')
        for _ in range(20):
            good.apply_reward(1.0)
            bad.apply_reward(0.0)

        self.assertGreater(good.posterior_mean, 0.9)
        self.assertLess(bad.posterior_mean, 0.1)
        self.assertEqual(good.pulls, 20)

    def test_decay_relaxes_an_untouched_arm_back_toward_the_prior(self):
        arm = SubstitutionPolicyArm(user=self.user, from_char='o', to_char='0')
        for _ in range(30):
            arm.apply_reward(1.0)
        confident = arm.posterior_mean
        self.assertGreater(confident, 0.9)

        # 200 neutral windows: the excess over the prior decays geometrically.
        for _ in range(200):
            arm.apply_reward(0.5)

        self.assertLess(arm.posterior_mean, confident)
        self.assertAlmostEqual(arm.posterior_mean, 0.5, places=2)

    def test_parameters_never_leave_the_valid_beta_range(self):
        # Decaying *toward the prior* rather than toward zero is what keeps
        # this true; a literal `alpha *= gamma` would walk both parameters to
        # 0 and make posterior_mean numerically meaningless.
        arm = SubstitutionPolicyArm(user=self.user, from_char='o', to_char='0')
        for _ in range(500):
            arm.apply_reward(0.0)
        self.assertGreaterEqual(arm.alpha, PRIOR_ALPHA - 1e-9)
        self.assertGreater(arm.beta, PRIOR_BETA)

    def test_evidence_is_bounded_so_an_arm_stays_responsive(self):
        arm = SubstitutionPolicyArm(user=self.user, from_char='o', to_char='0')
        for _ in range(1000):
            arm.apply_reward(1.0)
        # Fixed point of decay-toward-prior with reward 1 is
        # PRIOR_ALPHA + 1 / (1 - DEFAULT_DECAY). Importing the constant
        # instead of hardcoding 0.98 means a future change to the decay rate
        # fails this assertion with a value mismatch pointing at the real
        # cause, not a silently-stale magic number.
        self.assertLess(arm.alpha, PRIOR_ALPHA + 1 / (1 - DEFAULT_DECAY) + 1e-6)

    def test_reward_is_clamped_into_the_unit_interval(self):
        arm = SubstitutionPolicyArm(user=self.user, from_char='o', to_char='0')
        arm.apply_reward(7.0)
        self.assertAlmostEqual(arm.alpha, PRIOR_ALPHA + 1.0)
        self.assertAlmostEqual(arm.beta, PRIOR_BETA)

    def test_credit_arms_is_era_scoped_and_idempotent_per_class(self):
        credit_arms(self.user, [('o', '0'), ('o', '0')], 1.0, fp_key_version=1)
        credit_arms(self.user, [('o', '0')], 1.0, fp_key_version=2)

        arms = SubstitutionPolicyArm.objects.filter(user=self.user, from_char='o')
        self.assertEqual(arms.count(), 2)
        self.assertEqual({a.fp_key_version for a in arms}, {1, 2})
        # The duplicated class in one call is one pull, not two.
        self.assertEqual(arms.get(fp_key_version=1).pulls, 1)


class LoopClosureTests(TestCase):
    """Applying and rolling back must actually move the policy (gap B2)."""

    def setUp(self):
        self.user = _make_user('loop-user')
        self.service = AdaptivePasswordService(self.user)

    def test_apply_adaptation_credits_an_acceptance_reward(self):
        self.assertEqual(SubstitutionPolicyArm.objects.count(), 0)

        result = self.service.apply_adaptation_v2(
            original_fingerprint=FP_ORIGINAL,
            adapted_fingerprint=FP_ADAPTED,
            substitution_classes=[{'from': 'o', 'to': '0', 'confidence': 0.9}],
            previews={'original_masked': 'ab***yz', 'adapted_masked': 'a0***yz'},
            expected_fp_key_version=1,
        )
        self.assertNotIn('error', result)

        arm = SubstitutionPolicyArm.objects.get(user=self.user, from_char='o', to_char='0')
        self.assertEqual(arm.pulls, 1)
        self.assertAlmostEqual(arm.alpha, PRIOR_ALPHA + ACCEPTANCE_REWARD)
        self.assertGreater(arm.posterior_mean, 0.5)

    def test_rollback_drives_the_posterior_down(self):
        first = self.service.apply_adaptation_v2(
            original_fingerprint=FP_ORIGINAL,
            adapted_fingerprint=FP_ADAPTED,
            substitution_classes=[{'from': 'o', 'to': '0'}],
            expected_fp_key_version=1,
        )
        second = self.service.apply_adaptation_v2(
            original_fingerprint=FP_ADAPTED,
            adapted_fingerprint='ThirdFingerprint12345678',
            substitution_classes=[{'from': 'o', 'to': '0'}],
            expected_fp_key_version=1,
        )
        self.assertNotIn('error', second)

        arm = SubstitutionPolicyArm.objects.get(user=self.user, from_char='o', to_char='0')
        after_accepts = arm.posterior_mean

        rollback = self.service.rollback_adaptation(second['adaptation_id'])
        self.assertNotIn('error', rollback)

        arm.refresh_from_db()
        self.assertLess(arm.posterior_mean, after_accepts)
        self.assertEqual(arm.pulls, 3)  # two applies + one rollback
        self.assertEqual(ROLLBACK_REWARD, 0.0)
        self.assertIsNotNone(first)

    def test_a_conflicting_arm_credit_never_blocks_the_password_change(self):
        # The credit is an opportunistic learning signal. Failing the user's
        # adaptation because of bandit bookkeeping would be the wrong trade —
        # and the signal is not lost, because the weekly task recomputes a full
        # composite reward from the adaptation's own status.
        from django.db import IntegrityError

        with patch(
            'security.services.adaptive_policy_service.credit_adaptation',
            side_effect=IntegrityError('concurrent arm write'),
        ):
            result = self.service.apply_adaptation_v2(
                original_fingerprint=FP_ORIGINAL,
                adapted_fingerprint=FP_ADAPTED,
                substitution_classes=[{'from': 'o', 'to': '0'}],
                expected_fp_key_version=1,
            )

        # The adaptation committed...
        self.assertNotIn('error', result)
        self.assertTrue(
            PasswordAdaptation.objects.filter(
                user=self.user, adapted_fingerprint=FP_ADAPTED, status='active',
            ).exists()
        )
        # ...and was NOT misreported as an adapted-fingerprint chain clash,
        # which is what the surrounding IntegrityError handler is about.
        self.assertNotIn('already exists', str(result))

    def test_a_lock_timeout_on_the_arm_credit_never_blocks_the_password_change(self):
        # credit_arms takes select_for_update() on SubstitutionPolicyArm, so
        # real contention can raise OperationalError (lock-wait timeout,
        # detected deadlock) rather than IntegrityError. The two are siblings
        # under django.db.DatabaseError -- neither is a subclass of the other
        # (confirmed via issubclass before this test was written) -- so a
        # handler scoped to only IntegrityError would let this one propagate
        # into the caller's transaction, exactly the failure mode
        # credit_adaptation_best_effort's own docstring says it exists to
        # prevent.
        from django.db import OperationalError

        with patch(
            'security.services.adaptive_policy_service.credit_adaptation',
            side_effect=OperationalError('lock wait timeout'),
        ):
            result = self.service.apply_adaptation_v2(
                original_fingerprint=FP_ORIGINAL,
                adapted_fingerprint=FP_ADAPTED,
                substitution_classes=[{'from': 'o', 'to': '0'}],
                expected_fp_key_version=1,
            )

        self.assertNotIn('error', result)
        self.assertTrue(
            PasswordAdaptation.objects.filter(
                user=self.user, adapted_fingerprint=FP_ADAPTED, status='active',
            ).exists()
        )

    def test_rollback_still_decays_the_profile_confidence_too(self):
        # The two writers feed different consumers; Phase 3 adds the arm credit
        # ALONGSIDE the pre-existing UserTypingProfile decay, not instead of it.
        UserTypingProfile.objects.create(
            user=self.user,
            substitution_confidence={'o->0': 0.8},
            preferred_substitutions={},
            error_prone_positions={},
        )
        self.service.apply_adaptation_v2(
            original_fingerprint=FP_ORIGINAL,
            adapted_fingerprint=FP_ADAPTED,
            substitution_classes=[{'from': 'o', 'to': '0'}],
            expected_fp_key_version=1,
        )
        second = self.service.apply_adaptation_v2(
            original_fingerprint=FP_ADAPTED,
            adapted_fingerprint='ThirdFingerprint12345678',
            substitution_classes=[{'from': 'o', 'to': '0'}],
            expected_fp_key_version=1,
        )
        self.service.rollback_adaptation(second['adaptation_id'])

        profile = UserTypingProfile.objects.get(user=self.user)
        self.assertAlmostEqual(profile.substitution_confidence['o->0'], 0.4)


class PreferenceModelExportTests(TestCase):
    """What the client actually ranks against."""

    def setUp(self):
        self.user = _make_user('export-user')
        self.service = AdaptivePasswordService(self.user)

    def test_a_cold_user_still_gets_the_leetspeak_baseline(self):
        model = self.service.export_preference_model()
        self.assertEqual(model['substitution_weights']['o']['0'], 0.6)
        self.assertEqual(model['weight_sources']['o->0'], 'baseline')
        self.assertEqual(model['exploration']['o']['0'], {'alpha': 1.0, 'beta': 1.0})

    def test_a_learned_arm_overrides_the_baseline(self):
        credit_arms(self.user, [('o', '0')], 1.0, fp_key_version=1)
        credit_arms(self.user, [('o', '0')], 1.0, fp_key_version=1)

        model = self.service.export_preference_model()
        arm = SubstitutionPolicyArm.objects.get(user=self.user, from_char='o')

        self.assertEqual(model['weight_sources']['o->0'], 'user_policy')
        self.assertAlmostEqual(model['substitution_weights']['o']['0'], arm.posterior_mean)
        self.assertGreater(model['substitution_weights']['o']['0'], 0.6)
        self.assertAlmostEqual(model['exploration']['o']['0']['alpha'], arm.alpha, places=5)

    def test_arms_from_a_superseded_era_are_not_exported(self):
        credit_arms(self.user, [('o', '0')], 1.0, fp_key_version=1)
        config = AdaptivePasswordConfig.objects.get(user=self.user)
        config.rotate_fingerprint_key()
        config.save(update_fields=['fingerprint_salt', 'fp_key_version'])

        model = self.service.export_preference_model()
        self.assertEqual(model['fp_key_version'], 2)
        self.assertEqual(model['weight_sources']['o->0'], 'baseline')
        self.assertEqual(model['substitution_weights']['o']['0'], 0.6)

    def test_the_global_prior_covers_a_cold_user_but_loses_to_their_own_arm(self):
        GlobalSubstitutionPrior.objects.create(
            from_char='o', to_char='0',
            alpha=PRIOR_ALPHA + GLOBAL_PRIOR_STRENGTH * 0.9,
            beta=PRIOR_BETA + GLOBAL_PRIOR_STRENGTH * 0.1,
            contributing_users=42,
        )

        cold = self.service.export_preference_model()
        self.assertEqual(cold['weight_sources']['o->0'], 'global_prior')
        self.assertGreater(cold['substitution_weights']['o']['0'], 0.6)

        # Now give this user their own (bad) experience with the class.
        for _ in range(10):
            credit_arms(self.user, [('o', '0')], 0.0, fp_key_version=1)

        warm = self.service.export_preference_model()
        self.assertEqual(warm['weight_sources']['o->0'], 'user_policy')
        self.assertLess(warm['substitution_weights']['o']['0'], 0.2)

    def test_profile_usage_outranks_the_population_but_not_the_users_own_arm(self):
        GlobalSubstitutionPrior.objects.create(
            from_char='o', to_char='0',
            alpha=PRIOR_ALPHA + GLOBAL_PRIOR_STRENGTH * 0.9,
            beta=PRIOR_BETA + GLOBAL_PRIOR_STRENGTH * 0.1,
            contributing_users=42,
        )
        UserTypingProfile.objects.create(
            user=self.user,
            substitution_confidence={'o->0': 0.35},
            preferred_substitutions={},
            error_prone_positions={},
        )

        model = self.service.export_preference_model()
        self.assertEqual(model['weight_sources']['o->0'], 'user_profile')
        self.assertAlmostEqual(model['substitution_weights']['o']['0'], 0.35)

    def test_policy_weights_keeps_a_class_the_baseline_never_had(self):
        # Evidence can arrive for a class outside COMMON_SUBSTITUTIONS via
        # feedback on an adaptation the baseline never suggested; dropping it
        # would silently discard a real observation.
        credit_arms(self.user, [('z', '2')], 1.0, fp_key_version=1)
        weights, exploration, sources = policy_weights(
            self.user, fp_key_version=1, baseline={'o': {'0': 0.6}},
        )
        self.assertIn('2', weights['z'])
        self.assertIn('2', exploration['z'])
        self.assertEqual(sources['z->2'], 'user_policy')


class PreferenceModelEndpointTests(APITestCase):
    """The serializer, not just the service.

    Every other export test calls ``export_preference_model`` directly, which
    would not notice a ``PreferenceModelSerializer`` field that quietly drops
    or mis-types the two new keys.
    """

    def setUp(self):
        self.user = _make_user('endpoint-user')
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_the_endpoint_returns_exploration_and_weight_sources(self):
        for _ in range(5):
            credit_arms(self.user, [('o', '0')], 1.0, fp_key_version=1)

        response = self.client.get('/api/security/adaptive/preference-model/')

        self.assertEqual(response.status_code, 200)
        arm = SubstitutionPolicyArm.objects.get(user=self.user, from_char='o')

        self.assertAlmostEqual(
            response.data['substitution_weights']['o']['0'], arm.posterior_mean, places=5,
        )
        self.assertAlmostEqual(
            response.data['exploration']['o']['0']['alpha'], arm.alpha, places=4,
        )
        self.assertAlmostEqual(
            response.data['exploration']['o']['0']['beta'], arm.beta, places=4,
        )
        self.assertEqual(response.data['weight_sources']['o->0'], 'user_policy')

    def test_the_response_carries_no_password_derived_data(self):
        credit_arms(self.user, [('o', '0')], 1.0, fp_key_version=1)
        _sessions(self.user, FP_ORIGINAL, 3, 1, 2000)

        response = self.client.get('/api/security/adaptive/preference-model/')

        body = str(response.data)
        for forbidden in (FP_ORIGINAL, FP_ADAPTED, 'fingerprint_salt',
                          'password', 'masked'):
            self.assertNotIn(forbidden, body)


class ConvergenceTests(TestCase):
    """The acceptance criterion: the exported model must diverge from baseline."""

    def setUp(self):
        self.user = _make_user('bandit-user')
        self.service = AdaptivePasswordService(self.user)

    def _simulate(self, rounds=200):
        """o->0 always rewards, a->4 never does."""
        for _ in range(rounds):
            credit_arms(self.user, [('o', '0')], 1.0, fp_key_version=1)
            credit_arms(self.user, [('a', '4')], 0.0, fp_key_version=1)

    def test_the_policy_converges_and_the_export_reflects_it(self):
        self._simulate()

        model = self.service.export_preference_model()
        good = model['substitution_weights']['o']['0']
        bad = model['substitution_weights']['a']['4']

        self.assertGreater(good, bad)
        # Calibration: with a reward of exactly 1 every round, the decayed
        # posterior converges on ~1/(1 + (1 - gamma)) rather than exactly 1.
        self.assertGreater(good, 0.95)
        self.assertLess(bad, 0.05)

        # And it genuinely diverged from the static baseline (o->0 is 0.6 and
        # a->4 is 0.4 there, since '4' is the secondary substitution for 'a').
        self.assertNotAlmostEqual(good, 0.6, places=2)
        self.assertNotAlmostEqual(bad, 0.4, places=2)

    def test_the_convergence_assertion_fails_when_the_update_is_neutralized(self):
        # A learning test that still holds against a no-op policy proves
        # nothing, so run the mutation as a test rather than doing it by hand
        # once and trusting it afterwards.
        #
        # The neutralized apply_reward still counts the pull. That detail is
        # load-bearing: `pulls` is what makes export_preference_model read the
        # arm at all. Leave it at 0 and the export silently falls back to the
        # static baseline, where 0.6 > 0.4 anyway -- so `good > bad` would pass
        # against a policy that learned nothing, which is precisely the
        # vacuous outcome this test exists to rule out.
        def no_op_reward(self, reward, decay=None):  # noqa: ARG001
            self.pulls += 1
            return self

        with patch.object(
            SubstitutionPolicyArm, 'apply_reward', autospec=True,
            side_effect=no_op_reward,
        ):
            self._simulate(rounds=50)

            model = self.service.export_preference_model()
            good = model['substitution_weights']['o']['0']
            bad = model['substitution_weights']['a']['4']

            # Confirm the export really is reading the arms, not the baseline.
            self.assertEqual(model['weight_sources']['o->0'], 'user_policy')
            self.assertEqual(model['weight_sources']['a->4'], 'user_policy')

            # Both stuck at the flat prior: unorderable.
            self.assertEqual(good, 0.5)
            self.assertEqual(bad, 0.5)
            with self.assertRaises(AssertionError):
                self.assertGreater(good, bad)


class WeeklyTaskTests(TestCase):
    """The Celery task that persists rewards."""

    def setUp(self):
        self.user = _make_user('task-user')

    def _feedback(self, rating=5, **kwargs):
        adaptation = _make_adaptation(self.user, [('o', '0')], **kwargs)
        return AdaptationFeedback.objects.create(
            adaptation=adaptation, user=self.user, rating=rating,
        )

    def test_the_task_persists_rewards_instead_of_logging_them(self):
        self._feedback(rating=5)

        result = update_rl_model_from_feedback()

        self.assertEqual(result['processed'], 1)
        self.assertEqual(result['arms_updated'], 1)
        arm = SubstitutionPolicyArm.objects.get(user=self.user, from_char='o')
        self.assertEqual(arm.pulls, 1)
        self.assertGreater(arm.posterior_mean, 0.5)

    def test_the_task_is_idempotent(self):
        self._feedback(rating=5)

        update_rl_model_from_feedback()
        arm = SubstitutionPolicyArm.objects.get(user=self.user, from_char='o')
        first_alpha, first_pulls = arm.alpha, arm.pulls

        # A Celery retry, or an overlapping beat, must not credit twice.
        second = update_rl_model_from_feedback()

        self.assertEqual(second['processed'], 0)
        arm.refresh_from_db()
        self.assertEqual(arm.pulls, first_pulls)
        self.assertAlmostEqual(arm.alpha, first_alpha)

    def test_the_task_stamps_the_feedback_row(self):
        feedback = self._feedback()
        self.assertIsNone(feedback.policy_reward_applied_at)

        update_rl_model_from_feedback()

        feedback.refresh_from_db()
        self.assertIsNotNone(feedback.policy_reward_applied_at)

    def test_the_task_picks_up_feedback_a_missed_beat_left_behind(self):
        # Selection is by "not yet applied", not by a rolling one-week window,
        # so a run that never happened does not lose that week's data.
        feedback = self._feedback()
        AdaptationFeedback.objects.filter(pk=feedback.pk).update(
            created_at=timezone.now() - timedelta(days=90),
        )

        result = update_rl_model_from_feedback()
        self.assertEqual(result['processed'], 1)

    def test_a_failing_row_does_not_stop_the_run_or_get_stamped(self):
        bad = self._feedback(rating=5)
        good = self._feedback(
            rating=5,
            original_fingerprint='OtherOriginalFp123456789',
            adapted_fingerprint='OtherAdaptedFp1234567890',
        )
        real_credit = credit_adaptation

        def explode(adaptation, reward):
            if adaptation.pk == bad.adaptation.pk:
                raise RuntimeError('simulated failure')
            return real_credit(adaptation, reward)

        # The task imports credit_adaptation inside the function body, so it
        # resolves the module attribute at call time — patching it here is what
        # the task actually sees.
        with patch(
            'security.services.adaptive_policy_service.credit_adaptation',
            side_effect=explode,
        ):
            result = update_rl_model_from_feedback()

        self.assertEqual(result['processed'], 1)
        self.assertEqual(result['skipped'], 1)
        bad.refresh_from_db()
        good.refresh_from_db()
        self.assertIsNone(bad.policy_reward_applied_at)
        self.assertIsNotNone(good.policy_reward_applied_at)

    def test_a_failing_prior_rebuild_does_not_discard_the_credited_batch(self):
        # Every feedback row's credit + stamp already committed in its own
        # transaction by the time rebuild_global_priors runs. A raise there
        # must not propagate past this point and lose the run's own stats —
        # the row-level work is not lost either way, but an uncaught
        # exception here would raise before the function returns anything at
        # all, including the arms_updated/processed counts an operator needs
        # to see whether the run actually worked.
        feedback = self._feedback(rating=5)

        # Same reason as the credit_adaptation patch above: the task imports
        # rebuild_global_priors inside the function body, so patching the
        # source module's attribute is what the task actually sees at call time.
        with patch(
            'security.services.adaptive_policy_service.rebuild_global_priors',
            side_effect=RuntimeError('simulated DP aggregation failure'),
        ):
            result = update_rl_model_from_feedback()

        self.assertEqual(result['processed'], 1)
        self.assertEqual(result['arms_updated'], 1)
        self.assertEqual(result['classes_written'], 0)
        self.assertEqual(result['classes_skipped'], 0)
        self.assertTrue(result['prior_rebuild_failed'])
        feedback.refresh_from_db()
        self.assertIsNotNone(feedback.policy_reward_applied_at)

    def test_batch_size_bounds_the_run_and_leftovers_are_picked_up_next_time(self):
        for i in range(3):
            adaptation = _make_adaptation(
                self.user, [('o', '0')],
                original_fingerprint=f'OrigFp{i}23456789012345678'[:24],
                adapted_fingerprint=f'AdaptFp{i}2345678901234567'[:24],
            )
            AdaptationFeedback.objects.create(
                adaptation=adaptation, user=self.user, rating=4,
            )

        first = update_rl_model_from_feedback(batch_size=2)
        self.assertEqual(first['processed'], 2)

        second = update_rl_model_from_feedback(batch_size=2)
        self.assertEqual(second['processed'], 1)


class GlobalPriorTests(TestCase):
    """Cross-user aggregation: consent, k-anonymity, DP."""

    def _contributors(self, n, reward, consenting=True, repeats=10, dp_epsilon=None):
        """Create `n` users who each rewarded o->0 `repeats` times.

        `repeats` matters: one credit of 1.0 only moves an arm from Beta(1, 1)
        to Beta(2, 1), a mean of 0.667 — a lightly-held opinion, and
        aggregating those gives a global prior around 0.64. Ten credits is a
        genuinely confident user (mean ~0.98), which is the population these
        assertions are about.

        `dp_epsilon`, when given, sets every contributor's own
        `differential_privacy_epsilon`. Since `rebuild_global_priors`
        overrides the guard's epsilon with the strictest contributing user's
        setting, a test built around `PrivacyGuard(epsilon=100.0)` for
        "negligible noise" must give its contributors a matching epsilon too,
        or the override silently substitutes the model default (0.5) and
        reintroduces real noise into a test that was designed around not
        having any.
        """
        for i in range(n):
            kwargs = {'allow_centralized_training': consenting}
            if dp_epsilon is not None:
                kwargs['differential_privacy_epsilon'] = dp_epsilon
            user = _make_user(f'contrib-{consenting}-{reward}-{i}', **kwargs)
            for _ in range(repeats):
                credit_arms(user, [('o', '0')], reward, fp_key_version=1)

    def test_a_class_below_the_k_anonymity_floor_is_not_published(self):
        self._contributors(MIN_CONTRIBUTING_USERS - 1, 1.0)

        stats = rebuild_global_priors(PrivacyGuard())

        self.assertEqual(stats['classes_written'], 0)
        self.assertEqual(GlobalSubstitutionPrior.objects.count(), 0)

    def test_non_consenting_users_never_contribute(self):
        self._contributors(MIN_CONTRIBUTING_USERS + 3, 1.0, consenting=False)

        stats = rebuild_global_priors(PrivacyGuard())

        self.assertEqual(stats['classes_written'], 0)
        self.assertEqual(GlobalSubstitutionPrior.objects.count(), 0)

    def test_enough_consenting_users_publish_a_prior_in_the_right_direction(self):
        # dp_epsilon=100.0 matches the guard below: rebuild_global_priors
        # overrides the guard's epsilon with the strictest CONTRIBUTOR's
        # setting, so the contributors need it too or the override falls back
        # to the model default (0.5) and this stops being a negligible-noise
        # test of the aggregation math.
        self._contributors(MIN_CONTRIBUTING_USERS + 5, 1.0, dp_epsilon=100.0)

        # Epsilon 100 => negligible Laplace noise, so this asserts the
        # aggregation is correct rather than asserting anything about the noise.
        stats = rebuild_global_priors(PrivacyGuard(epsilon=100.0))

        self.assertEqual(stats['classes_written'], 1)
        prior = GlobalSubstitutionPrior.objects.get(from_char='o', to_char='0')
        self.assertGreater(prior.posterior_mean, 0.8)
        self.assertEqual(prior.contributing_users, MIN_CONTRIBUTING_USERS + 5)
        self.assertEqual(prior.dp_epsilon, 100.0)

    def test_noise_is_actually_drawn_from_the_privacy_guard(self):
        self._contributors(MIN_CONTRIBUTING_USERS + 5, 1.0)
        guard = PrivacyGuard()
        before = guard.operations_count

        rebuild_global_priors(guard)

        self.assertGreater(guard.operations_count, before)

    def test_one_user_across_several_eras_cannot_clear_the_k_floor_alone(self):
        # Arms are era-scoped (SubstitutionPolicyArm is unique per
        # (user, from, to, fp_key_version)), so a user who rotates their
        # fingerprint key holds one arm per era for the same class. Counting
        # each arm as an independent contributor would let a single user
        # publish a population-level prior by rotating enough times, and would
        # break the sensitivity-1.0 bound the Laplace noise is calibrated for
        # (which assumes one bounded contribution per user).
        solo = _make_user('solo-rotator')
        for era in range(1, MIN_CONTRIBUTING_USERS + 2):
            for _ in range(10):
                credit_arms(solo, [('o', '0')], 1.0, fp_key_version=era)

        stats = rebuild_global_priors(PrivacyGuard(epsilon=100.0))

        self.assertEqual(stats['classes_written'], 0)
        self.assertEqual(GlobalSubstitutionPrior.objects.count(), 0)

    def test_untouched_arms_do_not_dilute_the_aggregate(self):
        # A Beta(1,1) arm has mean 0.5 by construction. Counting it would look
        # like a real contribution while dragging every class toward "no
        # opinion", and would also let a user who never used the feature
        # influence everyone else's cold start.
        self._contributors(MIN_CONTRIBUTING_USERS + 5, 1.0, dp_epsilon=100.0)
        for i in range(20):
            idle = _make_user(f'idle-{i}')
            SubstitutionPolicyArm.objects.create(
                user=idle, from_char='o', to_char='0', fp_key_version=1,
            )

        rebuild_global_priors(PrivacyGuard(epsilon=100.0))

        prior = GlobalSubstitutionPrior.objects.get(from_char='o', to_char='0')
        self.assertEqual(prior.contributing_users, MIN_CONTRIBUTING_USERS + 5)
        self.assertGreater(prior.posterior_mean, 0.8)

    def test_withdrawn_consent_retracts_a_previously_published_class(self):
        # A class that clears the k-anonymity floor in one run and then loses
        # enough contributors to opt-out must not keep serving the stale row
        # forever -- this is the one path where a user's data influences
        # someone ELSE's suggestions, so their withdrawal has to actually
        # reach the published artifact, not just stop feeding it.
        # differential_privacy_epsilon=100.0 matches the guard below, for the
        # same reason as _contributors' dp_epsilon parameter: the override
        # would otherwise fall back to the model default (0.5) and turn this
        # into a real-noise test of retraction logic that isn't the point here.
        #
        # Start well ABOVE the floor (8, not the bare 5) rather than exactly
        # at it. `noisy_count < MIN_CONTRIBUTING_USERS` compares a continuous
        # noised value against an integer floor: sitting exactly AT the floor
        # makes "still published" a coin flip on the sign of the noise alone,
        # independent of how small the noise SCALE is (any negative draw,
        # however tiny, crosses the integer boundary). This was found the
        # hard way -- an earlier version of this test used exactly
        # MIN_CONTRIBUTING_USERS and failed intermittently in CI for exactly
        # this reason, not because of any bug in the code under test.
        users = [
            _make_user(f'withdraw-{i}', allow_centralized_training=True,
                       differential_privacy_epsilon=100.0)
            for i in range(MIN_CONTRIBUTING_USERS + 3)
        ]
        for user in users:
            for _ in range(10):
                credit_arms(user, [('o', '0')], 1.0, fp_key_version=1)

        first = rebuild_global_priors(PrivacyGuard(epsilon=100.0))
        self.assertEqual(first['classes_written'], 1)
        self.assertTrue(
            GlobalSubstitutionPrior.objects.filter(from_char='o', to_char='0').exists()
        )

        # Four of the eight withdraw consent -- down to 4, clearly (not just
        # barely) below MIN_CONTRIBUTING_USERS=5. The asymmetry is deliberate:
        # landing 1 below the floor is robust (a large POSITIVE noise draw
        # would be needed to cross back over, unlike sitting AT the floor).
        AdaptivePasswordConfig.objects.filter(
            user__in=[u.pk for u in users[:4]]
        ).update(allow_centralized_training=False)

        second = rebuild_global_priors(PrivacyGuard(epsilon=100.0))

        self.assertEqual(second['classes_written'], 0)
        self.assertEqual(second['classes_retracted'], 1)
        self.assertFalse(
            GlobalSubstitutionPrior.objects.filter(from_char='o', to_char='0').exists()
        )

    def test_a_still_qualifying_class_is_not_retracted_by_an_unrelated_run(self):
        # Guards the fix above against being overly broad: retraction must be
        # scoped to classes that actually stopped qualifying, not everything
        # that isn't freshly rewritten by coincidence of dict ordering.
        self._contributors(MIN_CONTRIBUTING_USERS + 2, 1.0, dp_epsilon=100.0)

        first = rebuild_global_priors(PrivacyGuard(epsilon=100.0))
        self.assertEqual(first['classes_written'], 1)

        second = rebuild_global_priors(PrivacyGuard(epsilon=100.0))

        self.assertEqual(second['classes_written'], 1)
        self.assertEqual(second['classes_retracted'], 0)
        self.assertTrue(
            GlobalSubstitutionPrior.objects.filter(from_char='o', to_char='0').exists()
        )

    def test_the_strictest_contributing_users_epsilon_is_honoured(self):
        # A user who chose a stricter epsilon than the caller-supplied guard's
        # default did not consent to weaker noise on the one path where their
        # data leaves their account and shapes someone else's suggestions.
        #
        # This test is about epsilon SELECTION, not noise magnitude, so the
        # Laplace draw itself is patched to a no-op. Padding the population
        # does not make this safe on its own: at epsilon=0.1 (scale=10) a real
        # draw still has P(noise < -10) = 0.5*exp(-1) ~= 18% of pushing
        # noisy_count back under the k=5 floor regardless of population size,
        # since the tail of an unbounded Laplace distribution never vanishes.
        strict_user = _make_user('strict-epsilon', differential_privacy_epsilon=0.1)
        for _ in range(10):
            credit_arms(strict_user, [('o', '0')], 1.0, fp_key_version=1)
        for i in range(MIN_CONTRIBUTING_USERS + 9):
            user = _make_user(f'default-epsilon-{i}')
            for _ in range(10):
                credit_arms(user, [('o', '0')], 1.0, fp_key_version=1)

        # PrivacyGuard() defaults to epsilon=0.5; the strict user's 0.1 must
        # win despite that.
        with patch.object(
            PrivacyGuard, 'add_laplace_noise',
            lambda self, value, sensitivity=1.0: value,
        ):
            rebuild_global_priors(PrivacyGuard())

        prior = GlobalSubstitutionPrior.objects.get(from_char='o', to_char='0')
        self.assertEqual(prior.dp_epsilon, 0.1)

    def test_a_non_contributing_consenting_users_epsilon_does_not_leak_in(self):
        # A consenting user who has never touched the feature (zero pulls)
        # must not make an UNRELATED class's epsilon stricter than it needs
        # to be -- the scope is "contributed to THIS run", not "consented at
        # some point". Same patched-noise reasoning as the test above: at
        # epsilon=0.5 (scale=2) a real draw still has P(noise < -5) =
        # 0.5*exp(-2.5) ~= 4% of flaking this on noise, not epsilon selection.
        _make_user('idle-strict-epsilon', differential_privacy_epsilon=0.05)
        self._contributors(MIN_CONTRIBUTING_USERS + 5, 1.0)

        with patch.object(
            PrivacyGuard, 'add_laplace_noise',
            lambda self, value, sensitivity=1.0: value,
        ):
            rebuild_global_priors(PrivacyGuard())

        prior = GlobalSubstitutionPrior.objects.get(from_char='o', to_char='0')
        # _contributors doesn't set differential_privacy_epsilon, so every
        # actual contributor is on the model default (0.5).
        self.assertEqual(prior.dp_epsilon, 0.5)

    def test_nothing_qualifying_retracts_every_existing_row(self):
        # The degenerate case: a run where NO class clears the floor (e.g. a
        # transient issue with the consenting-user query) must still retract
        # everything published by a prior run, by the same rule that retracts
        # any single class -- privacy-first means failing closed on
        # publication, not leaving the last-known-good data indefinitely
        # stale. Recoverable: the next correct run republishes anything that
        # still genuinely qualifies.
        self._contributors(MIN_CONTRIBUTING_USERS + 2, 1.0, dp_epsilon=100.0)
        first = rebuild_global_priors(PrivacyGuard(epsilon=100.0))
        self.assertEqual(first['classes_written'], 1)

        SubstitutionPolicyArm.objects.all().delete()

        second = rebuild_global_priors(PrivacyGuard(epsilon=100.0))

        self.assertEqual(second['classes_written'], 0)
        self.assertEqual(second['classes_retracted'], 1)
        self.assertEqual(GlobalSubstitutionPrior.objects.count(), 0)
