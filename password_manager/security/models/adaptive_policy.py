"""
Adaptive Password Policy Models (Phase 3 — the bandit)
======================================================

Persistent state for the reinforcement-learning policy behind the Adaptive
Password feature. Before Phase 3, ``update_rl_model_from_feedback`` computed
per-substitution rewards and then *logged* them — there was no bandit, no
policy and no table (plan §0.2 gap B1). These two models are that table.

**Algorithm: Beta-Bernoulli Thompson sampling**, one arm per substitution class
(``from_char`` → ``to_char``). Chosen over a contextual method deliberately: a
user produces tens of adaptations, not thousands, so a contextual model would
overfit, while Thompson sampling gives principled exploration from two floats
per arm. The *server* keeps the posteriors and exports their means; the
*client* samples from them, so exploration stays on-device and
``/preference-model/`` remains deterministic and cacheable.

Zero-knowledge: an arm is a substitution *class* — the pair of characters
``o → 0``, never a position, never a password character in context. Nothing
here is derived from a password; the rewards that move these posteriors come
from accept/reject/rollback events and from typing behaviour keyed by opaque
fingerprints (see ``security/tasks/adaptive_tasks.py``).
"""

from django.contrib.auth.models import User
from django.db import models


# Beta(1, 1) — the uniform prior. An arm with no evidence has posterior mean
# 0.5 and is neither preferred nor avoided.
PRIOR_ALPHA = 1.0
PRIOR_BETA = 1.0

# Per-update time decay. Applied toward the prior rather than toward zero (see
# :meth:`SubstitutionPolicyArm.apply_reward`), so the policy tracks drift —
# which is what "co-evolves with you" actually has to mean — without the
# posterior ever leaving the valid Beta parameter range.
DEFAULT_DECAY = 0.98


def _decay_toward_prior(value: float, prior: float, decay: float) -> float:
    """Shrink accumulated *evidence* toward the prior, never past it.

    A literal reading of "decay both parameters by γ" (``alpha *= 0.98``) walks
    both parameters toward 0, which is not a valid Beta distribution and makes
    the posterior mean numerically unstable as the arm goes cold. Decaying the
    *excess over the prior* instead has the intended effect — an arm nobody
    touches relaxes back to "no opinion" — while keeping ``alpha, beta >= 1``.

    It also bounds growth without an arbitrary cap: with a reward of at most 1
    per update, the excess converges to ``1 / (1 - decay)`` (50 at γ=0.98), so
    an arm stays responsive to new evidence instead of ossifying.
    """
    return prior + (value - prior) * decay


class SubstitutionPolicyArm(models.Model):
    """Per-user Beta posterior over "does this substitution class help me?".

    One row per ``(user, from_char, to_char, fp_key_version)``. Arms are
    **era-scoped**: a fingerprint key rotation is a deliberate correlation
    reset (remediation plan §7), and the behavioural half of the reward is
    computed by joining ``TypingSession`` rows across two fingerprints — a
    join that is only meaningful inside a single era. Carrying a posterior
    across the rotation would import conclusions drawn from measurements the
    new era cannot reproduce.
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='substitution_policy_arms',
    )

    from_char = models.CharField(
        max_length=1,
        help_text="Original character of the substitution class (e.g. 'o')",
    )
    to_char = models.CharField(
        max_length=1,
        help_text="Substituted character of the class (e.g. '0')",
    )

    alpha = models.FloatField(
        default=PRIOR_ALPHA,
        help_text="Beta posterior alpha (accumulated success evidence + prior)",
    )
    beta = models.FloatField(
        default=PRIOR_BETA,
        help_text="Beta posterior beta (accumulated failure evidence + prior)",
    )
    pulls = models.PositiveIntegerField(
        default=0,
        help_text="How many rewards have been folded into this arm",
    )

    fp_key_version = models.PositiveIntegerField(
        default=1,
        help_text=(
            "Fingerprint key era (see AdaptivePasswordConfig.fp_key_version). "
            "Arms do not survive a rotation's correlation reset."
        ),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    last_updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'adaptive_substitution_policy_arm'
        verbose_name = 'Substitution Policy Arm'
        verbose_name_plural = 'Substitution Policy Arms'
        ordering = ['from_char', 'to_char']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'from_char', 'to_char', 'fp_key_version'],
                name='uniq_policy_arm_per_user_era',
            ),
        ]
        indexes = [
            # The export path reads every arm for one user in the current era.
            models.Index(fields=['user', 'fp_key_version'],
                         name='policy_arm_user_fpver_idx'),
        ]

    def __str__(self):
        return (
            f"{self.user.username}: {self.from_char}->{self.to_char} "
            f"(era {self.fp_key_version}, mean {self.posterior_mean:.2f})"
        )

    @property
    def posterior_mean(self) -> float:
        """Expected reward for this arm, ``alpha / (alpha + beta)``.

        Guarded against a zero denominator even though
        :func:`_decay_toward_prior` keeps both parameters at or above their
        priors: a row edited by hand in the admin, or restored from an older
        schema, should degrade to "no opinion" rather than raise.
        """
        total = self.alpha + self.beta
        if total <= 0:
            return 0.5
        return self.alpha / total

    def apply_reward(self, reward: float, decay: float = DEFAULT_DECAY):
        """Fold one reward in ``[0, 1]`` into the posterior, in memory.

        Decays first (so stale evidence loses weight before new evidence is
        added), then ``alpha += reward`` / ``beta += 1 - reward``. Does **not**
        save — the caller owns the transaction boundary, matching
        ``AdaptivePasswordConfig.ensure_fingerprint_salt``'s established
        contract in this feature.

        Args:
            reward: Observed reward, clamped into ``[0, 1]``.
            decay: Per-update decay toward the prior.

        Returns:
            This arm, for chaining.
        """
        r = min(1.0, max(0.0, float(reward)))
        self.alpha = _decay_toward_prior(self.alpha, PRIOR_ALPHA, decay) + r
        self.beta = _decay_toward_prior(self.beta, PRIOR_BETA, decay) + (1.0 - r)
        self.pulls += 1
        return self


class GlobalSubstitutionPrior(models.Model):
    """Cross-user Beta prior over a substitution class, for cold start.

    A user with no adaptations yet has nothing but the flat Beta(1, 1) on every
    arm, which makes the exported model identical to the old static leetspeak
    baseline. This table is the population-level answer to "which classes tend
    to work at all", used only until a user's own arm has evidence.

    Aggregated **exclusively** over users with
    ``AdaptivePasswordConfig.allow_centralized_training=True`` and passed
    through ``PrivacyGuard`` before being written, so an individual user's
    accept/reject pattern is not recoverable from it. Deliberately not
    era-scoped: eras are per-user, and this row describes the population.
    """

    from_char = models.CharField(max_length=1)
    to_char = models.CharField(max_length=1)

    alpha = models.FloatField(default=PRIOR_ALPHA)
    beta = models.FloatField(default=PRIOR_BETA)

    contributing_users = models.PositiveIntegerField(
        default=0,
        help_text="Consenting users folded into the most recent aggregation",
    )
    dp_epsilon = models.FloatField(
        null=True, blank=True,
        help_text="DP epsilon the noise for this row was drawn under",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    last_updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'adaptive_global_substitution_prior'
        verbose_name = 'Global Substitution Prior'
        verbose_name_plural = 'Global Substitution Priors'
        ordering = ['from_char', 'to_char']
        constraints = [
            models.UniqueConstraint(
                fields=['from_char', 'to_char'],
                name='uniq_global_prior_per_class',
            ),
        ]

    def __str__(self):
        return (
            f"global {self.from_char}->{self.to_char} "
            f"(mean {self.posterior_mean:.2f}, n={self.contributing_users})"
        )

    @property
    def posterior_mean(self) -> float:
        """Population mean for this class; 0.5 if the row is degenerate."""
        total = self.alpha + self.beta
        if total <= 0:
            return 0.5
        return self.alpha / total
