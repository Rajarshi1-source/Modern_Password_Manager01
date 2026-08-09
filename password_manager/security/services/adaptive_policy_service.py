"""
Adaptive Password Policy Service (Phase 3 — the bandit)
=======================================================

The learning half of the Adaptive Password feature. Everything that reads or
writes ``SubstitutionPolicyArm`` / ``GlobalSubstitutionPrior`` lives here so
the Celery task stays thin and ``AdaptivePasswordService`` can credit an arm
without importing task code.

**Zero-knowledge.** Nothing in this module touches a password. The reward
signal is assembled from:

- explicit user feedback (a 1-5 rating and three booleans),
- the adaptation's own lifecycle status (accepted / rolled back), and
- typing behaviour joined across two **opaque keyed fingerprints**.

That last term is the one that makes this a real bandit rather than a
satisfaction survey, and it is the enabling insight of the whole ZK design
(plan §1.2): because ``PasswordAdaptation`` links
``original_fingerprint → adapted_fingerprint`` and ``TypingSession`` is keyed
by fingerprint, the server can measure *"did this user's error rate and entry
time actually improve after this adaptation"* without ever knowing either
password.
"""

import functools
import logging
import operator
from typing import Dict, Iterable, List, Optional, Set, Tuple

from django.db import DatabaseError, transaction
from django.db.models import Avg, Count, Min, Q

logger = logging.getLogger(__name__)


# =============================================================================
# Reward shaping
# =============================================================================

#: Component weights for the composite reward (plan §3.2). No ``acceptance``/
#: ``rollback`` entries: those lifecycle facts are already credited the moment
#: they happen, via ``credit_adaptation_best_effort`` in ``apply_adaptation_v2``
#: / ``rollback_adaptation`` (``ACCEPTANCE_REWARD`` / ``ROLLBACK_REWARD``
#: below). Folding ``acceptance_reward(adaptation)`` /
#: ``rollback_reward(adaptation)`` into this composite too would credit the
#: SAME status fact to the SAME arm a second time whenever a feedback row is
#: later processed for that adaptation -- not independent evidence, just the
#: original signal re-read and re-applied. The two functions stay as
#: standalone reward-shaping primitives (still directly tested) in case a
#: future caller needs "current lifecycle status as a reward" for something
#: that is not this composite.
REWARD_WEIGHTS = {
    'rating': 0.4,
    'behavioural': 0.2,
}

#: Minimum ``TypingSession`` rows required on *each* fingerprint before the
#: behavioural term is trusted. Below this the term is dropped entirely and the
#: remaining weights are renormalized, rather than contributing a noisy value.
MIN_BEHAVIOURAL_SESSIONS = 3

#: Immediate reward credited when an adaptation is applied. Deliberately only
#: modestly above the flat prior's mean of 0.5: the user took the suggestion up,
#: which is weak positive evidence, but whether it actually helped is not known
#: until feedback or typing behaviour arrives.
ACCEPTANCE_REWARD = 0.6

#: Immediate reward credited when an adaptation is rolled back. A hard zero, per
#: plan §3.2 — an undo is the strongest negative signal the feature can observe.
ROLLBACK_REWARD = 0.0

#: A global prior row is only written once this many consenting users have
#: contributed to the class. A k-anonymity floor on top of the Laplace noise:
#: DP bounds what a single contribution can reveal, this bounds how few
#: contributions a published number may be built from at all.
MIN_CONTRIBUTING_USERS = 5

#: Pseudo-observation count the aggregated global mean is expressed as. Keeps
#: the cold-start prior informative but never strong enough to outweigh a
#: user's own accumulated evidence.
GLOBAL_PRIOR_STRENGTH = 10.0

#: Ceiling on distinct SubstitutionPolicyArm rows one (user, fp_key_version)
#: era may hold. adaptive_serializers.MAX_SUBSTITUTION_CLASSES bounds how many
#: NEW classes one request can introduce (32), but nothing previously bounded
#: how many an authenticated user could accumulate across many requests over
#: time -- from/to are single Unicode characters, not restricted to a small
#: leet alphabet, so the reachable space is not naturally small. Generous
#: headroom above any realistic vocabulary (same reasoning as
#: MAX_SUBSTITUTION_CLASSES itself: a backstop, not a tight fit), while still
#: bounding the per-user row count that policy_weights loads in full on every
#: /preference-model/ call.
MAX_ARMS_PER_USER_ERA = 200


def _clamp01(value: float) -> float:
    """Clamp into ``[0, 1]``."""
    return min(1.0, max(0.0, float(value)))


def substitution_classes(adaptation) -> Set[Tuple[str, str]]:
    """Extract the distinct ``(from, to)`` classes an adaptation applied.

    ``substitutions_applied`` is a positional map (``{"0": {"from": ..., ...}}``)
    but an *arm* is a class, so duplicates collapse: a password with three
    ``o → 0`` substitutions is one piece of evidence about ``o → 0``, not three.
    """
    classes: Set[Tuple[str, str]] = set()
    for entry in (adaptation.substitutions_applied or {}).values():
        if not isinstance(entry, dict):
            continue
        from_char = entry.get('from')
        to_char = entry.get('to')
        if isinstance(from_char, str) and isinstance(to_char, str) and from_char and to_char:
            classes.add((from_char[:1], to_char[:1]))
    return classes


def explicit_feedback_reward(feedback) -> float:
    """Reward in ``[0, 1]`` from a user's explicit rating.

    Reuses the shaping the pre-Phase-3 task already computed and then threw
    away (``adaptive_tasks.py`` L167-184 as it stood): rating 4-5 → 1.0, 3 →
    0.5, 1-2 → 0.0, plus +0.2 / +0.2 / +0.1 for the three improvement booleans,
    capped at 1.0.
    """
    if feedback.rating >= 4:
        reward = 1.0
    elif feedback.rating == 3:
        reward = 0.5
    else:
        reward = 0.0

    if feedback.typing_accuracy_improved:
        reward += 0.2
    if feedback.memorability_improved:
        reward += 0.2
    if feedback.typing_speed_improved:
        reward += 0.1

    return _clamp01(reward)


def acceptance_reward(adaptation) -> float:
    """1.0 if the adaptation is the user's live password, else 0.0."""
    return 1.0 if adaptation.status == 'active' else 0.0


def rollback_reward(adaptation) -> float:
    """0.0 if the user undid the adaptation, else 1.0 (nothing went wrong)."""
    return 0.0 if adaptation.status == 'rolled_back' else 1.0


def _relative_improvement(before: float, after: float) -> float:
    """Map a lower-is-better metric pair onto ``[0, 1]``.

    ``0.5`` means "no change" and ``1.0`` means the metric went to zero. The
    score falls below ``0.5`` as the metric worsens, but not linearly with the
    ratio: an exact doubling scores ``0.25`` (verified:
    ``rel(1, 2) == 0.25``), and ``0.0`` is approached only as ``after`` grows
    arbitrarily larger than ``before`` — no finite ratio reaches it exactly
    (``rel(1, 100) ≈ 0.005``). Scaling by the larger of the two magnitudes
    keeps the result bounded and symmetric, so one pathological session cannot
    dominate the term.
    """
    denominator = max(abs(before), abs(after))
    if denominator <= 0:
        # Both zero: a perfect score before and after is no evidence either way.
        return 0.5
    return _clamp01(0.5 + 0.5 * ((before - after) / denominator))


def behavioural_reward(adaptation) -> Optional[float]:
    """Reward from typing behaviour on the two fingerprints, or ``None``.

    Compares mean ``error_count`` and mean ``total_time_ms`` of the sessions
    recorded against ``adapted_fingerprint`` with those recorded against
    ``original_fingerprint``. Returns ``None`` when either side has fewer than
    :data:`MIN_BEHAVIOURAL_SESSIONS` rows, so the caller renormalizes instead of
    folding in a reading built on one or two samples.

    Both predicates are scoped by the adaptation's own ``fp_key_version``,
    matching every other fingerprint-keyed query shipped in Phase 1 (the
    ``apply_adaptation_v2`` chain-parent lookup, ``rollback_adaptation``,
    ``get_adaptation_history``, ``get_evolution_stats``). A genuine cross-era
    fingerprint collision is not practically reachable — 144-bit HMAC output
    under an independently-rotated per-era key — so this is consistency and
    defense-in-depth rather than a live exploit path; the era columns exist
    precisely so a query never has to rely on that improbability.

    Note on the "before" sample: sessions on ``original_fingerprint`` are not
    restricted to those predating the adaptation. After a rollback the user is
    typing the original password again, and those sessions are legitimately
    part of how the original performs for them.
    """
    from ..models import TypingSession

    if not adaptation.original_fingerprint or not adaptation.adapted_fingerprint:
        return None

    # One query, grouped — not two round trips per adaptation in a loop.
    rows = (
        TypingSession.objects.filter(
            user_id=adaptation.user_id,
            fp_key_version=adaptation.fp_key_version,
            password_fingerprint__in=[
                adaptation.original_fingerprint,
                adaptation.adapted_fingerprint,
            ],
        )
        .values('password_fingerprint')
        .annotate(
            n=Count('id'),
            mean_errors=Avg('error_count'),
            mean_time=Avg('total_time_ms'),
        )
    )
    by_fingerprint = {row['password_fingerprint']: row for row in rows}

    before = by_fingerprint.get(adaptation.original_fingerprint)
    after = by_fingerprint.get(adaptation.adapted_fingerprint)
    if not before or not after:
        return None
    if before['n'] < MIN_BEHAVIOURAL_SESSIONS or after['n'] < MIN_BEHAVIOURAL_SESSIONS:
        return None

    components: List[float] = [
        _relative_improvement(before['mean_errors'] or 0.0, after['mean_errors'] or 0.0)
    ]
    # total_time_ms is nullable; Avg skips NULLs, so it can come back None even
    # with rows present. Only score it when both sides actually have timings.
    if before['mean_time'] is not None and after['mean_time'] is not None:
        components.append(_relative_improvement(before['mean_time'], after['mean_time']))

    return sum(components) / len(components)


def composite_reward(adaptation, feedback=None) -> Tuple[float, Dict[str, Optional[float]]]:
    """Weighted reward for an adaptation, plus the per-component breakdown.

    Deliberately only ``rating`` and ``behavioural``: acceptance and rollback
    are NOT included here even though ``acceptance_reward``/``rollback_reward``
    exist, because those lifecycle facts are already credited once, the moment
    they happen, by ``credit_adaptation_best_effort`` at apply/rollback time.
    Re-deriving them from ``adaptation.status`` here and folding them into this
    composite would credit the identical status fact to the same arm a second
    time on every feedback row processed for that adaptation -- not new
    evidence, the same one read twice. See ``REWARD_WEIGHTS``.

    Any component with no signal (no feedback row, or too few sessions for the
    behavioural term) is dropped and the surviving weights are renormalized, so
    a partially-observed adaptation is not implicitly scored 0 on what was
    never measured.

    Returns:
        ``(reward, components)`` where ``components`` maps every weight name to
        its raw value or ``None`` when it did not contribute. The breakdown is
        returned rather than logged so callers can assert on it in tests and
        surface it in the task result.
    """
    raw: Dict[str, Optional[float]] = {
        'rating': explicit_feedback_reward(feedback) if feedback is not None else None,
        'behavioural': behavioural_reward(adaptation),
    }

    contributing = {k: v for k, v in raw.items() if v is not None}
    total_weight = sum(REWARD_WEIGHTS[k] for k in contributing)
    if total_weight <= 0:
        # Both components absent (no feedback row, and too few sessions for
        # behavioural): genuinely no signal to score this adaptation on, not a
        # bug -- the caller (currently always with a real feedback row) simply
        # has no rating text and no behavioural data yet.
        return 0.5, raw

    reward = sum(REWARD_WEIGHTS[k] * v for k, v in contributing.items()) / total_weight
    return _clamp01(reward), raw


# =============================================================================
# Arm updates
# =============================================================================

def credit_arms(
    user,
    classes: Iterable[Tuple[str, str]],
    reward: float,
    fp_key_version: int,
) -> int:
    """Fold ``reward`` into one arm per substitution class. Returns arms touched.

    Locked, unlike the config reads elsewhere in this feature: this really is a
    read-modify-write cycle (read ``alpha``, decay it, add the reward, write it
    back), so two concurrent credits without a lock would lose one update
    outright. That is a different situation from ``record_typing_session_v2``'s
    config read, where the value is fetched once and reused — a lock there was
    considered and declined because nothing re-reads. Here something does.

    Runs in its own ``transaction.atomic()``; nesting inside a caller's atomic
    block (as ``apply_adaptation_v2`` does) makes it a savepoint, which is the
    intended behaviour — the credit commits or rolls back with the adaptation.

    Distinct (user, fp_key_version) arms are capped at ``MAX_ARMS_PER_USER_ERA``
    — see that constant's docstring. Existing arms keep being credited past
    the ceiling; only creating a brand-new one stops.

    The ceiling check itself needs a lock: reading ``existing_pairs`` and
    deciding there is headroom is a check-then-act, and two concurrent calls
    for the same user that both read before either commits can each see
    headroom for a *different* new class and together exceed the ceiling.
    Locking a stable one-row-per-user ``AdaptivePasswordConfig`` row first —
    the same "mint/allocate under a lock" pattern used elsewhere in this
    feature (see ``get_adaptive_config``'s salt self-heal) — serializes those
    calls around the check. A missing config row is not an error here: the
    lock is a no-op and the check runs exactly as it did before this was
    added, since nothing below actually reads the row's contents.
    """
    from ..models import AdaptivePasswordConfig, SubstitutionPolicyArm

    touched = 0
    with transaction.atomic():
        AdaptivePasswordConfig.objects.select_for_update().filter(user=user).first()

        existing_pairs = set(
            SubstitutionPolicyArm.objects.filter(
                user=user, fp_key_version=fp_key_version,
            ).values_list('from_char', 'to_char')
        )
        for from_char, to_char in sorted(set(classes)):
            is_new = (from_char, to_char) not in existing_pairs
            if is_new and len(existing_pairs) >= MAX_ARMS_PER_USER_ERA:
                # Ceiling reached: don't create another distinct arm this era.
                # Arms that already exist keep being credited normally below.
                continue
            arm, created = SubstitutionPolicyArm.objects.get_or_create(
                user=user,
                from_char=from_char,
                to_char=to_char,
                fp_key_version=fp_key_version,
            )
            if created:
                existing_pairs.add((from_char, to_char))
            # Re-read under the lock: get_or_create's returned instance may
            # predate a concurrent credit that has since committed.
            arm = SubstitutionPolicyArm.objects.select_for_update().get(pk=arm.pk)
            arm.apply_reward(reward)
            arm.save(update_fields=['alpha', 'beta', 'pulls', 'last_updated_at'])
            touched += 1
    return touched


def credit_adaptation(adaptation, reward: float) -> int:
    """Credit every class an adaptation applied, in that adaptation's own era."""
    classes = substitution_classes(adaptation)
    if not classes:
        return 0
    return credit_arms(
        adaptation.user,
        classes,
        reward,
        fp_key_version=adaptation.fp_key_version,
    )


def credit_adaptation_best_effort(adaptation, reward: float) -> int:
    """Credit an adaptation's arms without letting a conflict fail the caller.

    For the two *service* call sites (apply and rollback), the credit is an
    opportunistic learning signal, not part of what the user asked for. Two
    concurrent writers can make ``get_or_create`` surface an ``IntegrityError``
    it cannot recover from (its internal retry re-reads inside the same
    snapshot, which may not see the row the other transaction just committed);
    ``credit_arms``' own ``select_for_update()`` can also raise
    ``OperationalError`` on a lock-wait timeout or a detected deadlock under
    real contention. Both are ``django.db.DatabaseError`` (confirmed via
    ``issubclass`` — they are siblings, neither a subclass of the other, so a
    catch scoped to only one misses the other). Blocking a password change on
    either is the wrong trade, even though the signal genuinely IS lost on
    this rare path: ``composite_reward`` deliberately does not re-derive
    acceptance/rollback from ``adaptation.status`` (that would double-credit
    the common case, where this call succeeds, on every later feedback row —
    see ``composite_reward``'s own docstring), so there is no fallback that
    recovers a credit dropped here. Accepted trade: guaranteed double-counting
    on every successful call is worse than an occasional lost credit on a rare
    lock-contention failure.

    The credit still runs in a **savepoint of the caller's transaction**, so it
    cannot leave a credited arm behind for an adaptation that never committed —
    which is the reason plan §3.3 put it inside the atomic block in the first
    place. Only the opposite direction is relaxed.

    The weekly task deliberately does *not* use this: there, a swallowed
    failure would let the feedback row be stamped as applied while the reward
    was silently dropped.
    """
    try:
        with transaction.atomic():
            return credit_adaptation(adaptation, reward)
    except DatabaseError:
        logger.warning(
            'Policy arm credit skipped for adaptation %s (concurrent write or '
            'lock contention); this acceptance/rollback signal is lost, since '
            'composite_reward deliberately does not re-derive it from '
            'adaptation.status on a later pass.',
            adaptation.pk,
        )
        return 0


# =============================================================================
# Export — what the client actually ranks against
# =============================================================================

def policy_weights(
    user,
    fp_key_version: int,
    baseline: Dict[str, Dict[str, float]],
    user_overrides: Optional[Dict[str, Dict[str, float]]] = None,
):
    """Overlay the learned policy on a baseline weight table.

    Resolution order per substitution class, most specific first:

    1. the user's own **arm**, once it has at least one pull — outcome
       evidence, i.e. this class actually worked for this user;
    2. the caller's ``user_overrides`` — usage evidence from
       ``UserTypingProfile`` (which classes this user already reaches for);
    3. the DP-noised cross-user **global prior**, if one has been published;
    4. the static leetspeak ``baseline``.

    Population data ranks *below* both user-specific signals deliberately: the
    global prior exists to answer "which classes work at all" for a cold user,
    not to overrule something already observed about this one.

    Args:
        user: The user whose policy to read.
        fp_key_version: Era to read arms from — arms do not survive a rotation.
        baseline: ``{from: {to: weight}}`` starting point; not mutated.
        user_overrides: Optional user-specific weights outranking the global
            prior; not mutated.

    Returns:
        ``(weights, exploration, sources)``. ``exploration`` carries the raw
        ``{alpha, beta}`` per class so the **client** draws the Thompson sample,
        which keeps exploration on-device and leaves this endpoint
        deterministic and cacheable (plan §3.4). ``sources`` records which of
        the four levels answered each class, for the model's own metadata.
    """
    from ..models import GlobalSubstitutionPrior, SubstitutionPolicyArm

    weights = {
        from_char: dict(row) for from_char, row in baseline.items()
    }
    overrides = user_overrides or {}
    exploration: Dict[str, Dict[str, Dict[str, float]]] = {}
    sources: Dict[str, str] = {}

    arms_by_class = {
        (a.from_char, a.to_char): a
        for a in SubstitutionPolicyArm.objects.filter(
            user=user, fp_key_version=fp_key_version
        )
    }

    # Every class the baseline knows about, plus any the user has evidence on
    # (a class can enter via feedback on an adaptation the baseline never
    # suggested, and dropping it would silently discard real evidence).
    known_classes = {
        (from_char, to_char)
        for table in (baseline, overrides)
        for from_char, row in table.items()
        for to_char in row
    } | set(arms_by_class)

    # Bounded to classes this response can possibly use. GlobalSubstitutionPrior
    # grows with the whole population's distinct published classes (any pair
    # that clears the k-anonymity floor in rebuild_global_priors), not with
    # anything one /preference-model/ request needs — reading the whole table
    # on every call scales with the wrong thing. The __in/__in pair is a
    # superset filter (it can also match a from/to combination NOT in
    # known_classes), which is fine: the per-class loop below only ever reads
    # `globals_by_class.get((from_char, to_char))` for a class it is already
    # iterating from `known_classes`, so an extra fetched row is simply never
    # looked up.
    if known_classes:
        globals_by_class = {
            (p.from_char, p.to_char): p
            for p in GlobalSubstitutionPrior.objects.filter(
                from_char__in={c[0] for c in known_classes},
                to_char__in={c[1] for c in known_classes},
            )
        }
    else:
        globals_by_class = {}

    for from_char, to_char in sorted(known_classes):
        arm = arms_by_class.get((from_char, to_char))
        prior = globals_by_class.get((from_char, to_char))
        override = overrides.get(from_char, {}).get(to_char)

        # Only user_policy and global_prior are actual Beta posteriors --
        # accumulated evidence with a real (alpha, beta) shape worth Thompson
        # sampling around. user_profile (a UserTypingProfile usage signal)
        # and baseline (the static shared leetspeak table) are point
        # estimates with no evidence count behind them at all; tagging them
        # with the flat PRIOR_ALPHA/PRIOR_BETA prior would not express "some
        # uncertainty around this weight", it would silently replace the
        # weight with uniform noise once sampled -- alpha=beta=1 is a valid
        # posterior shape, not a "no data" sentinel, so the client's own
        # finite-and-positive usability check cannot distinguish the two.
        # Omitting the exploration entry for these sources is what actually
        # makes the client fall back to ranking by the reported weight, per
        # rankSuggestions' own documented fallback for a class with no
        # exploration entry.
        alpha = beta = None
        if arm is not None and arm.pulls > 0:
            weight = arm.posterior_mean
            alpha, beta = arm.alpha, arm.beta
            source = 'user_policy'
        elif override is not None:
            weight = override
            source = 'user_profile'
        elif prior is not None:
            weight = prior.posterior_mean
            alpha, beta = prior.alpha, prior.beta
            source = 'global_prior'
        else:
            weight = weights.get(from_char, {}).get(to_char)
            if weight is None:
                continue
            source = 'baseline'

        weights.setdefault(from_char, {})[to_char] = _clamp01(weight)
        if alpha is not None and beta is not None:
            exploration.setdefault(from_char, {})[to_char] = {
                'alpha': round(float(alpha), 6),
                'beta': round(float(beta), 6),
            }
        sources[f'{from_char}->{to_char}'] = source

    return weights, exploration, sources


# =============================================================================
# Global prior aggregation (consenting users only, DP-noised)
# =============================================================================

def rebuild_global_priors(privacy_guard) -> Dict[str, int]:
    """Recompute the cross-user cold-start priors under differential privacy.

    Only users with ``allow_centralized_training=True`` contribute — this is
    the single place in the feature where one user's learning influences
    another's, so the consent check is not optional and is applied at the
    query, not after.

    Each user contributes their arm's **posterior mean**, a value already
    bounded to ``[0, 1]``. That bounded contribution is what makes the Laplace
    sensitivity of the sum exactly 1.0 rather than the ~50 an un-clipped
    ``alpha`` would imply, so the same epsilon buys far less distortion.

    ``privacy_guard.epsilon`` is **overridden** before any noise is drawn, to
    the strictest (lowest) ``differential_privacy_epsilon`` among the users
    who actually contribute an arm this run. This is the one path where a
    user's own data leaves their account and shapes another user's
    suggestions, so a caller who requested epsilon=0.1 (strong) must not have
    their contribution folded in under whatever the caller-supplied guard's
    default happens to be — nobody's chosen protection level is weakened by
    someone else's default. Scoped to actual contributors of *this* run
    (not every enabled+consenting user) so an unrelated consenting user who
    has never touched the feature cannot make an unrelated class's epsilon
    stricter than it needs to be.

    Every class that fails to clear ``MIN_CONTRIBUTING_USERS`` in a given run
    is also **retracted** if a stale row from an earlier run still publishes
    it — a class can stop clearing the floor because contributors withdrew
    consent (``allow_centralized_training=False``) or deleted their data, and
    ``policy_weights`` has no other signal telling it that class is no longer
    backed by enough people. Leaving the old row in place would mean consent
    withdrawal never reaches the published artifact.

    Args:
        privacy_guard: A ``PrivacyGuard``; its ``delta`` and
            ``add_laplace_noise`` are used as given, but its ``epsilon`` is
            overridden as described above before any noise is drawn.

    Returns:
        ``{'classes_written': n, 'classes_skipped': m, 'classes_retracted': r}``.
    """
    from ..models import (
        AdaptivePasswordConfig, GlobalSubstitutionPrior, SubstitutionPolicyArm,
        PRIOR_ALPHA, PRIOR_BETA,
    )

    consenting_user_ids = AdaptivePasswordConfig.objects.filter(
        is_enabled=True,
        allow_centralized_training=True,
    ).values_list('user_id', flat=True)

    # Only arms with evidence: an untouched Beta(1,1) arm has mean 0.5 by
    # construction and would drag every class toward "no opinion" while looking
    # like a real contribution.
    arms = SubstitutionPolicyArm.objects.filter(
        user_id__in=consenting_user_ids, pulls__gt=0,
    ).only('from_char', 'to_char', 'alpha', 'beta', 'user_id', 'last_updated_at')

    # Arms are era-scoped (unique per user, class AND fp_key_version), so a
    # user who has rotated their fingerprint key holds one arm per era for the
    # same class. Keying only by class here would count each of those eras as
    # an independent contributor, letting a single user clear the
    # MIN_CONTRIBUTING_USERS floor alone by rotating enough times — and would
    # break the sensitivity-1.0 bound the Laplace noise below is calibrated
    # for, which assumes exactly one bounded contribution per user. Keep only
    # the most recently updated arm per (user, class) before aggregating.
    # Only (timestamp, posterior_mean) is kept per key, not the model
    # instance itself -- across the whole consenting population this
    # dictionary, not the iterator's chunk_size, sets the task's peak memory.
    latest_by_user_and_class: Dict[Tuple[str, str, int], Tuple[object, float]] = {}
    for arm in arms.iterator(chunk_size=1000):
        key = (arm.from_char, arm.to_char, arm.user_id)
        existing = latest_by_user_and_class.get(key)
        if existing is None or arm.last_updated_at > existing[0]:
            latest_by_user_and_class[key] = (arm.last_updated_at, arm.posterior_mean)

    per_class: Dict[Tuple[str, str], List[float]] = {}
    for (from_char, to_char, _user_id), (_ts, mean) in latest_by_user_and_class.items():
        per_class.setdefault((from_char, to_char), []).append(mean)

    # Honour the strictest privacy setting among the users actually
    # contributing this run, not the caller-supplied guard's own default
    # (0.5 unless overridden) and not every enabled+consenting user (which
    # would let someone who has never touched the feature make an unrelated
    # class's epsilon stricter than it needs to be). PrivacyGuard.epsilon is
    # a plain instance attribute read at call time by add_laplace_noise, so
    # mutating it here — before any noise is drawn — is sufficient; nothing
    # caches the earlier value.
    contributing_user_ids = {user_id for (_, _, user_id) in latest_by_user_and_class}
    if contributing_user_ids:
        strictest_epsilon = AdaptivePasswordConfig.objects.filter(
            user_id__in=contributing_user_ids,
        ).aggregate(Min('differential_privacy_epsilon'))['differential_privacy_epsilon__min']
        if strictest_epsilon is not None:
            privacy_guard.epsilon = strictest_epsilon

    written = 0
    skipped = 0
    published_classes = set()
    # The whole publish-and-retract cycle commits as one unit. Without this,
    # a process death partway through (OOM, SIGKILL, worker eviction) leaves
    # some classes freshly written and others untouched, AND skips the
    # retraction below entirely (it only runs after the loop completes) --
    # exactly the half-updated, never-retracted state this function's own
    # docstring says the retraction step exists to prevent. A rollback here
    # is cheap to retry: the next scheduled run recomputes from the same
    # underlying arms, so failing closed to the pre-run state is strictly
    # safer than publishing a partial one.
    with transaction.atomic():
        for (from_char, to_char), means in per_class.items():
            n = len(means)
            if n < MIN_CONTRIBUTING_USERS:
                skipped += 1
                continue

            # Sensitivity 1.0: one user can move the sum by at most 1.0 (their
            # mean is in [0, 1]) and the count by exactly 1.
            noisy_sum = privacy_guard.add_laplace_noise(sum(means), sensitivity=1.0)
            noisy_count = privacy_guard.add_laplace_noise(float(n), sensitivity=1.0)
            if noisy_count < MIN_CONTRIBUTING_USERS:
                skipped += 1
                continue

            mean = _clamp01(noisy_sum / noisy_count)
            GlobalSubstitutionPrior.objects.update_or_create(
                from_char=from_char,
                to_char=to_char,
                defaults={
                    'alpha': PRIOR_ALPHA + GLOBAL_PRIOR_STRENGTH * mean,
                    'beta': PRIOR_BETA + GLOBAL_PRIOR_STRENGTH * (1.0 - mean),
                    # The true count, not the noised one: this column is admin
                    # metadata about how much data backs the row, and
                    # publishing a noised count alongside a noised mean
                    # derived from it would spend privacy budget twice for no
                    # benefit. It is never exported to any client.
                    'contributing_users': n,
                    'dp_epsilon': privacy_guard.epsilon,
                    # last_updated_at is NOT set here: the field is
                    # auto_now=True, so Django overwrites whatever is passed
                    # at save() time regardless — an explicit value here was
                    # dead, misleading code, not a real timestamp override.
                },
            )
            written += 1
            published_classes.add((from_char, to_char))

        # Retract every previously-published row this run did not re-clear
        # the floor for. Without this, a class that stops having enough
        # consenting contributors (opt-out, GDPR deletion) stays served by
        # policy_weights as 'global_prior' forever — the one code path where
        # a user's data can influence someone else's suggestions would never
        # actually forget them.
        if published_classes:
            keep = functools.reduce(
                operator.or_,
                (Q(from_char=f, to_char=t) for f, t in published_classes),
            )
            retracted, _ = GlobalSubstitutionPrior.objects.exclude(keep).delete()
        else:
            # Nothing cleared the floor this run at all: every existing row
            # is stale by the same rule that retracts any single class.
            retracted, _ = GlobalSubstitutionPrior.objects.all().delete()

    logger.info(
        'Global substitution priors rebuilt: %s written, %s skipped, %s '
        'retracted (below k=%s)',
        written, skipped, retracted, MIN_CONTRIBUTING_USERS,
    )
    return {
        'classes_written': written,
        'classes_skipped': skipped,
        'classes_retracted': retracted,
    }
