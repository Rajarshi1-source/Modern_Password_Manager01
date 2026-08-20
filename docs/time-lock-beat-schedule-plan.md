# Plan — Wire up the Time-Lock (Password Will / Dead Man's Switch) beat schedule

Branch: `fix/time-lock-beat-schedule-not-merged` (off `main`, independent of
the still-open PR #482 — disjoint code, no dependency)

## 1. The bug

`security/tasks/__init__.py` does:

```python
from .time_lock_tasks import (
    ...,
    CELERY_BEAT_SCHEDULE as TIME_LOCK_BEAT_SCHEDULE,
)
```

`TIME_LOCK_BEAT_SCHEDULE` is never referenced again anywhere (grepped
`celery.py` and this whole package). `time_lock_tasks.py` defines a real
`CELERY_BEAT_SCHEDULE` dict (line 507) with 4 entries for the Password Will /
Dead Man's Switch feature. None of them are merged into `celery.py`'s actual
`app.conf.beat_schedule`, so beat never asks for any of them — the tasks are
fully implemented and would run correctly if invoked, but nothing schedules
them.

This is a **different bug shape** than everything in PR #482: those were
wrong/missing task *names*. Here the names are already correct — the four
`@shared_task(name='time_lock.<func>')` decorators match
`CELERY_BEAT_SCHEDULE`'s task strings exactly, and the module is already
imported (unlike Dark Protocol in #482, which needed an import added). The
fix really is just: merge the dict in.

## 2. Why this needed its own investigation, not just a merge

Unlike Dark Protocol (pure DB bookkeeping, zero external effect until a user
opts in) or the genetic tasks (inert until a DNA provider is configured),
these four tasks have real, externally-visible consequences the moment they
run:

- `check_dead_mans_switches` → `trigger_password_will`: **unlocks a capsule
  and emails real beneficiaries** ("Access Granted... you now have access to
  the contents") with a link containing `beneficiary.verification_token`.
  This is the feature's entire point — revealing secrets to a beneficiary —
  so it's not a bug to do this. It's a risk in *when* it first happens.
- `check_escrow_deadlines` → auto-releases matching `EscrowAgreement` rows
  and emails all parties, same shape of consequence.
- `EMAIL_BACKEND` defaults to real SMTP
  (`django.core.mail.backends.smtp.EmailBackend`, confirmed in
  `settings/base.py`), not a console/dummy backend — so if SMTP credentials
  are configured, these are real emails, not simulated ones.
- **Zero existing test coverage of the task layer.** `security/tests/test_time_lock.py`
  covers the API and model layers (creating wills/escrows, `days_until_trigger`,
  `can_release`) but never invokes `check_dead_mans_switches`,
  `trigger_password_will`, `check_escrow_deadlines`, `check_capsule_unlocks`,
  `notify_beneficiary`, or `send_will_reminder` anywhere. This PR is the
  first time any of these six functions get run under test.

## 3. Safety audit

Verified schema correctness the same way as the genetic-task bugs in #482
(where wrong reverse-relation/field names caused crashes): read `PasswordWill`,
`EscrowAgreement` in `security/models/core.py` field-by-field against every
attribute the tasks reference (`last_check_in`, `inactivity_days`,
`check_in_reminder_days`, `is_active`/`is_triggered`, `reminder_sent`,
`beneficiaries_notified(_at)`, `notes`, `target_date`; `approval_deadline`,
`is_disputed`/`is_released`, `parties`, `can_release`/`release()`). All match
— **no field-name bug here**, unlike the genetic tasks. Confirmed the ORM
queries compile locally without `FieldError`.

**The one real residual risk, and it can't be fully closed from here: a
backlog on first run.** Because this beat entry has never existed, any
`PasswordWill` row with `is_active=True, is_triggered=False` whose deadline
(inactivity-based or a past `target_date`) has *already* elapsed — or any
`EscrowAgreement` with `approval_deadline` already passed AND `can_release`
true (an elapsed deadline alone isn't sufficient — see §7.2's review-fix for
why) — would all fire in a single batch on the very first beat tick after
this deploys, rather than each having fired individually at its own due
date. For a feature whose job is "reveal secrets to a beneficiary," a
surprise batch is a materially different experience than the intended
one-at-a-time behavior.

I have no access to production data to check whether such a backlog exists.
**This must be checked before deploying**, not just before merging:

```python
from datetime import timedelta
from security.models import PasswordWill, EscrowAgreement
from django.utils import timezone
now = timezone.now()

overdue_wills = [
    w for w in PasswordWill.objects.filter(is_active=True, is_triggered=False)
    if (w.trigger_type == 'inactivity' and now >= w.last_check_in + timedelta(days=w.inactivity_days))
    or (w.trigger_type == 'date' and w.target_date and now >= w.target_date)
]
# `approval_deadline__lte=now` alone isn't "releasable" -- check_escrow_deadlines
# itself queries this same filter, then gates the actual release on
# `escrow.can_release` (a property, not a method).
overdue_escrows = [
    e for e in EscrowAgreement.objects.filter(
        is_released=False, is_disputed=False, approval_deadline__lte=now,
    ).select_related('capsule')
    if e.can_release
]
```

(This snippet is illustrative — the actual pre-deploy tool is the
`check_time_lock_backlog` management command built in §5b, which implements
this exact logic.)

If either is non-empty, `check_dead_mans_switches` / `check_escrow_deadlines`
will trigger all of them on the first tick post-deploy (wills
unconditionally on their deadline; escrows only the `can_release`-true
subset — see above). Flagging this
prominently in the PR rather than silently shipping it — it's outside what
"wire up the schedule" can fix from the code alone, and it's the kind of
call (delay the two riskiest entries, backfill-mark old rows, or just
accept it) that depends on knowing the actual data, which I don't have
access to.

## 4. Changes

1. **`password_manager/password_manager/celery.py`** — merge
   `time_lock_tasks.CELERY_BEAT_SCHEDULE` (re-exported as
   `TIME_LOCK_BEAT_SCHEDULE` by `security/tasks/__init__.py`) into
   `app.conf.beat_schedule`.

   **First attempt was wrong and caught by testing, not review**: placing
   `from security.tasks import TIME_LOCK_BEAT_SCHEDULE` at celery.py module
   level (even positioned after `app.autodiscover_tasks()`) crashed with
   `django.core.exceptions.AppRegistryNotReady`. Root cause:
   `password_manager/__init__.py` does `from .celery import app as celery_app`,
   so `celery.py`'s module body runs as a side effect of *anything* importing
   the `password_manager` package — including Django's own `django.setup()`,
   which imports `password_manager.settings` as one of its first steps,
   *before* `apps.populate()` has finished. An eager import there runs
   mid-`django.setup()`, not after it. `app.autodiscover_tasks()` avoids this
   because (without `force=True`) it's deliberately lazy — it registers a
   promise rather than importing immediately.

   **Fix**: merge via `@app.on_after_finalize.connect`, Celery's own
   mechanism for deferred setup. Verified the ordering is actually safe by
   reading Celery 5.6.3's own source (`celery/apps/beat.py`,
   `celery/loaders/base.py`, `celery/fixups/django.py`): `beat`'s
   `init_loader()` calls `self.app.loader.init_worker()` — which fires the
   `import_modules` signal, triggering `django.setup()` via Celery's built-in
   Django fixup — *before* calling `self.app.finalize()` on the next line.
   `on_after_finalize` fires after `finalize()` completes, so by the time the
   merge callback runs, Django is fully set up. Confirmed empirically:
   scripted the exact same call order beat uses
   (`loader.init_worker()` then `app.finalize()`) starting from a cold
   import of `password_manager.celery` with `django.setup()` NOT
   pre-called — no crash, and `app.conf.beat_schedule` contained all 4
   `time_lock.*` entries afterward, each resolving in `app.tasks`.

2. No changes needed to `time_lock_tasks.py` itself — names, schema, and
   logic all check out.

## 5. Tests

New `security/tests/test_time_lock_tasks.py` (the task layer had zero
coverage before this):

- `check_capsule_unlocks`: unlocks a capsule past `unlock_at`, fans out
  `notify_beneficiary` for each not-yet-notified beneficiary; leaves an
  as-yet-not-due capsule alone.
- `check_expired_capsules`: marks a capsule unlocked >30 days ago as
  `expired`; leaves a recently-unlocked one alone.
- `check_dead_mans_switches` (inactivity trigger): reminder fires at the
  reminder threshold; will triggers once the deadline has passed; neither
  fires early.
- `check_dead_mans_switches` (date trigger): triggers once `target_date` has
  passed.
- `trigger_password_will`: marks the will triggered, unlocks the capsule,
  fans out `notify_beneficiary` to every beneficiary, is a no-op (not a
  double-send) if called again on an already-triggered will.
- `check_escrow_deadlines`: auto-releases an escrow past its
  `approval_deadline` when `can_release` is true; leaves a disputed one
  alone.
- A registry test mirroring PR #482's `test_celery_beat_registry.py` pattern
  (this branch doesn't depend on that PR, so a small self-contained version):
  asserts all 4 `time_lock.*` beat entries now resolve in the registry.

`send_mail` is mocked throughout — these tests must never attempt a real
SMTP connection.

Run with the `canny` venv and `DEBUG=True`.

## 5b. Pre-deploy backlog check

User asked to check the backlog before deploying. No production DB access
from this session (`DB_NAME` is unset here, so this environment only ever
touches the local dev SQLite) -- the query in §3 can't actually be run
against production from here. Instead, added
`python manage.py check_time_lock_backlog`
(`security/management/commands/check_time_lock_backlog.py`): a read-only
command mirroring `check_dead_mans_switches`'/`check_escrow_deadlines`'s own
trigger logic exactly, reporting record IDs and non-identifying
trigger/release metadata and overdue-by duration for each match (owner
usernames and capsule/escrow titles are deliberately left out of routine
CronJob stdout -- see round 1's PII fix, §7) and exiting 1 if anything is
found (0 otherwise) -- safe to gate a deploy script on, or just run by
hand. Covered by 8 tests
(`security/tests/test_check_time_lock_backlog_command.py`), and also run
manually against the local dev DB (empty, as expected -- confirms the
command executes cleanly, not that production has no backlog).

**Still outstanding**: run this against production before deploying this PR.

## 5c. Scheduling it: CronJob in k8s/cronjobs.yaml, not a one-off Job

User asked whether to check the command into `k8s/` alongside
`migrate-job.yaml`, explicitly "only if it is the best choice ... decide
intelligently after scanning infrastructure." Scanned `k8s/` and
`.github/workflows/ci.yml` before answering rather than just copying the
pattern that was suggested.

**Chose a CronJob in `cronjobs.yaml` instead.** That file's own header states
its purpose: "maintenance tasks that must run even when Celery beat is
unhealthy." A Time-Lock backlog is exactly that symptom — beat not
processing `check_dead_mans_switches`/`check_escrow_deadlines`, whether
because beat is down (ongoing risk after this PR ships) or because the
schedule was never wired up (today's specific bug). `migrate-job.yaml`'s
shape (standalone one-off Job) fits work needed on *every* deploy and is
wired into CI by explicit path (`ci.yml` line ~757); gating every future
unrelated deploy on a Time-Lock-specific check doesn't make sense, and
nothing would have run this new file automatically without also editing the
CI pipeline — out of scope for what was asked. Added as
`check-time-lock-backlog` (daily 06:00 UTC, clear of the two existing
CronJobs' 03:30/Sun-04:00 schedules), `backoffLimit: 0` (unlike the two
siblings' `backoffLimit: 2` — a backlog finding is a real signal, retrying
the same read-only query doesn't shrink it, just triples the log line). The
one-off pre-#483-deploy run is still available on demand:
`kubectl create job --from=cronjob/check-time-lock-backlog <name> -n password-manager`.

**Two things found while scanning, flagged to the user rather than fixed
(out of this task's scope)**:

- `ci.yml`'s production deploy step applies `kubectl apply -f k8s/production/`,
  a directory that does not exist anywhere in this repo. `migrate-job.yaml`
  is the only `k8s/*.yaml` file with confirmed CI wiring (explicit path
  reference); nothing here proves `cronjobs.yaml` is actually part of an
  automated deploy pipeline.
- `network-policy.yaml` is default-deny-all with explicit per-`component`
  allow rules (`backend`, `websocket`, `celery`, `cache`/redis,
  `database`/postgres, `frontend`) — but `component: maintenance`, the label
  both pre-existing CronJobs (`cleanup-old-logs`, `db-backup`) already use
  and what this new one uses too, has no database-egress allow rule
  anywhere in that file. Either NetworkPolicy enforcement isn't actually
  active in this cluster (the file's own comment: "Requires a CNI plugin
  that supports NetworkPolicy"), or those two existing CronJobs already
  can't reach Postgres. Pre-existing, not introduced here.

## 6. Test results

- `pytest security/tests/test_time_lock_tasks.py -v`: 17 passed, 4 subtests
  passed.
- `pytest security/tests/test_time_lock.py security/tests/test_time_lock_tasks.py -q`:
  39 passed, 4 subtests passed (confirms the new task-layer tests don't
  regress the existing API/model-layer coverage for the same feature).
- Full `pytest security/tests/`: 1147 passed, 7 skipped (pre-existing),
  0 failed.
- `pytest security/tests/test_check_time_lock_backlog_command.py -v`: 8
  passed (added in a follow-up commit, §5b).

## 7. Review-fix round 1 on PR #483 (CodeRabbit)

Three findings across `check_time_lock_backlog.py` and this plan doc.
Verified each critically against the actual pinned/installed environment and
the real production task before changing anything, per instruction. One
finding's *severity claim* turned out to be factually wrong for this
codebase; a second finding's own *suggested fix code* was syntactically
broken. Neither invalidated the underlying point in each case, so both were
still worth acting on, just not as literally suggested.

### 7.1 "Critical": `timezone.timedelta` doesn't exist in Django 5.1 (severity claim wrong, fixed anyway)

CodeRabbit's claim: `will.last_check_in + timezone.timedelta(days=...)`
(line ~54) calls an attribute Django 5.1 doesn't provide, so the inactivity
branch raises `AttributeError` before the command can report anything.

Checked directly against this repo's actual pinned/installed Django,
**not** taken on the bot's word:

```text
DEBUG=True canny/Scripts/python.exe -c "from django.utils import timezone; print(hasattr(timezone, 'timedelta')); print(timezone.timedelta)"
# -> True
# -> <class 'datetime.timedelta'>
```

`django/utils/timezone.py` in the installed 5.1.15 (pinned identically in
`requirements.txt`, `requirements-core.txt`, `requirements-lock.txt`,
`requirements-prod.txt`, `requirements-constraints.txt`) does
`from datetime import datetime, timedelta, timezone, tzinfo` at module
level — a real, working import, not a stub. `timezone.timedelta` **is**
`datetime.timedelta` in this exact pinned version, confirmed both by source
inspection and by this command's own tests already passing against it
before this round (`test_reports_overdue_inactivity_will` exercises this
exact line). The "raises AttributeError" claim does not hold for this
codebase as it actually runs. CodeRabbit's sandbox likely resolved a
different Django version than what's pinned here.

**Fixed anyway**: relying on an implicit module-namespace side effect
(`timezone.timedelta`) rather than importing `timedelta` from `datetime`
directly is fragile against a future Django refactor of `timezone.py`
dropping that import, and the change costs nothing — same object, verified
identical behavior. Added `from datetime import timedelta`, used `timedelta`
directly. Zero behavior change; purely a dependency-on-an-implementation-detail
removal.

### 7.2 Escrow query doesn't check `can_release` (real, but suggested fix code was broken)

CodeRabbit's claim: `approval_deadline__lte=now` alone doesn't mean an
escrow is releasable, so the command could over-report and block a deploy
unnecessarily.

**Confirmed real** by re-reading the actual production task,
`check_escrow_deadlines` (`security/tasks/time_lock_tasks.py`): it queries
this *exact same* broad filter, then gates the real `.release()` call on
`if escrow.can_release:`. An `EscrowAgreement` with `release_condition=
'all_approve'` and an elapsed `approval_deadline` but insufficient
approvals matches the command's old query yet would never actually be
auto-released by the task — a genuine over-report.

**CodeRabbit's own suggested diff was wrong**, though: it wrote
`if escrow.can_release()`. `can_release` is decorated `@property`
(`security/models/core.py`) — calling it as a method raises
`TypeError: 'bool' object is not callable`. Applying the suggested diff
verbatim would have replaced a (real but narrower) over-reporting issue with
a hard crash on every single escrow candidate. Fixed as `escrow.can_release`
(no parens), matching the property's actual definition and mirroring the
production task's own gate exactly.

**Regression caught while fixing this**: the existing test
`test_reports_overdue_escrow` created its escrow with `release_condition=
'date'` but never moved `capsule.unlock_at` into the past (the `make_capsule`
helper's default is `now + 1h`). `can_release` for the `'date'` condition
checks `now >= capsule.unlock_at`, which would have been `False` under the
new gated logic — the existing test would have started failing the moment
the fix landed, silently proving the fix "broken" rather than proving the
escrow it built was never actually releasable in the first place. Fixed the
test's capsule setup to also set `unlock_at` into the past. Also added a new
test, `test_does_not_report_escrow_with_unmet_approval_condition`, exercising
the exact scenario CodeRabbit's finding described (`all_approve`, deadline
elapsed, insufficient approvals) — this is the regression guard for the
actual bug, not just the crash CodeRabbit's own suggested code would have
introduced.

### 7.3 PII in routine CronJob output (real, fixed as suggested)

CodeRabbit's claim: the per-row output lines include `owner.username`,
`capsule.title`, and `escrow.title` — since this command runs daily as a
k8s CronJob (§5c), that PII lands in whatever log aggregation the cluster
uses by default, visible to a broader audience than someone deliberately
looking up a specific finding.

Confirmed by reading the command's own output lines — the claim is exactly
right, no ambiguity to verify here. Fixed as suggested: dropped
`owner={will.owner.username!r}` and `capsule={will.capsule.title!r}` from
the will lines, `title={escrow.title!r}` from the escrow lines. Rows are
still fully actionable by ID
(`PasswordWill.objects.get(id=...)` / `EscrowAgreement.objects.get(id=...)`)
for whoever needs to actually investigate a finding — the fix removes PII
from *routine* output, not the ability to look a row up deliberately.
Updated `test_reports_overdue_inactivity_will` and `test_reports_overdue_escrow`
to assert the username/titles are *absent* from output (previously one
asserted the username *was* present) and that the row ID is present instead.

### 7.4 Test results (targeted, per instruction)

`pytest security/tests/test_check_time_lock_backlog_command.py -v` — 9
passed (8 existing + 1 new: `test_does_not_report_escrow_with_unmet_approval_condition`).
Not re-run against the full suite this round: nothing outside this one
command and its own test file was touched, so the full-suite run from §6
still stands for everything else in this PR's footprint.

## 8. Review-fix round 2 on PR #483 (CodeRabbit + a failing CI check)

Three CodeRabbit findings plus one failing CI job (`Backend Tests`). Verified
each critically before acting; one of the four turned out to be unrelated
to this PR entirely.

### 8.1 Failing CI check: unrelated, pre-existing flaky test — NOT fixed here

`Backend Tests` failed with exactly one test:
`security/tests/test_adaptive_zk_v2.py::DeadProfileFieldTests::test_wpm_variance_is_written_and_grows_with_spread`
— `AssertionError: None != 0.0`.

Fetched the actual CI job log (`gh api .../actions/jobs/<id>/logs`, not just
the pass/fail badge) rather than guessing at the cause. Verified before
touching anything:
- `git diff main..fix/time-lock-beat-schedule-not-merged -- security/tests/test_adaptive_zk_v2.py security/services/adaptive_password_service.py`
  is empty — this PR's diff has zero overlap with the failing test or the
  feature it exercises (adaptive-password keystroke-dynamics ZK, unrelated
  to Time-Lock).
- Ran the exact failing test in isolation locally: **passed**. A
  deterministic bug in code this PR touches would fail the same way every
  time regardless of what else ran before it; this only failed inside the
  full 1962-test CI run, which points at test-order/shared-state dependence
  in that other feature, not a regression here.

Did not attempt a code fix: I have no context on that feature's
differential-privacy/variance computation, and guessing at a fix in
unfamiliar, security-sensitive code is precisely how a "surgical, no new
regressions" instruction gets violated, not honored. Pushing this round's
actual fixes (below) triggers a fresh CI run on a new commit, which is the
appropriate zero-code-risk way to see if it clears on retry, rather than a
separate manual rerun. If it fails the same way twice in a row, that
escalates it from "probably flaky" to "worth its own dedicated
investigation" — but that's a different, unrelated feature's bug, not
Time-Lock's.

### 8.2 Doc says "all" overdue escrows fire; code (already fixed in round 1) says only `can_release`-true ones do

Self-inconsistency, not a code bug: round 1 (§7.2) already fixed
`check_time_lock_backlog.py` to gate on `escrow.can_release`, and even
fixed *this same document's* illustrative code snippet (§3) to match — but
the *prose* immediately above that snippet, written before round 1,
still said "any `EscrowAgreement` with `approval_deadline` already passed
— would all fire," describing the pre-fix behavior. CodeRabbit caught the
doc contradicting its own adjacent code block. Fixed both the main
statement and its "If either is non-empty... will trigger all of them"
follow-up sentence to name the `can_release` gate explicitly.

### 8.3 `k8s/cronjobs.yaml` is never actually applied by CI (CONFIRMED, real, pre-existing gap widened by this PR)

Re-verified CodeRabbit's own research rather than trusting it blind:
grepped `.github/workflows/ci.yml` for `cronjobs.yaml`, `k8s/production`,
`envsubst` — confirmed the production deploy step applies
`kubectl apply -f k8s/production/` (a directory that does not exist in this
repo) and **only** `migrate-job.yaml` is applied by explicit path anywhere
in the workflow. `k8s/cronjobs.yaml` itself was never referenced. This is
the exact gap flagged (not fixed) in §5c/§7 of this doc when the
`check-time-lock-backlog` CronJob was first added — CodeRabbit independently
found and confirmed it, and the user asked for it to actually be fixed this
round.

Pre-existing: this gap predates the Time-Lock work entirely — `cleanup-old-logs`
and `db-backup` (added to `cronjobs.yaml` before this PR) were *also* never
applied by CI. Not scope creep to fix now: it's the same file this PR
already edits, and the fix serves all three CronJobs identically, not just
the new one.

Distinguished from `k8s/tor.yaml`'s existing pattern before choosing a fix:
Tor's Deployments are a genuine opt-in feature toggle, deliberately
operator-applied, with CI only updating their image tag *if* they already
exist (`--ignore-not-found`). The three CronJobs here aren't optional in
that sense — they're maintenance jobs that should simply always exist.
Auto-applying them (mirroring `migrate-job.yaml`'s established
`envsubst | kubectl apply` pattern, not Tor's operator-applied one) is the
correct fit, not just the available one.

**Fix**: added an "Apply scheduled maintenance CronJobs" step to
`.github/workflows/ci.yml`, right after the "Deploy to Kubernetes
(Production)" step's rollout wait (CronJobs don't depend on the
Deployments being rolled out first, and don't need `kubectl set image` /
`rollout status` the way Deployments do — a plain `apply` is sufficient and
idempotent). Verified: `yaml.safe_load` on the whole modified `ci.yml`
succeeds, and running the exact command the new step runs
(`GITHUB_SHA=<sha> envsubst < k8s/cronjobs.yaml | ...`) resolves all three
CronJobs' `${GITHUB_SHA}` image tags correctly, parsed back with `yaml.safe_load_all`.

### 8.4 `test_does_not_report_disputed_escrow` doesn't move `unlock_at` into the past — same masking pattern as round 1, missed on a sibling test

Same class of issue round 1 (§7.2) already fixed for
`test_reports_overdue_escrow`: the test's `make_capsule` call left
`unlock_at` at its default (`now + 1h`), so `can_release` would return
`False` for *two independent reasons* (`is_disputed=True`, and separately
the future `unlock_at`) — meaning a regression that dropped the query's
`is_disputed=False` filter would still pass this test, since the
future-`unlock_at` reason alone keeps `can_release` false. CodeRabbit named
only this one test; found the *identical*, unflagged pattern in the very
next test, `test_does_not_report_already_released_escrow` (same
future-`unlock_at` default, same `is_released=True` double-guard). Fixed
both for consistency rather than only the one literally named — leaving an
identical, adjacent gap unfixed would have been an inconsistent, half-done
response to the same underlying finding.

### 8.5 Test results (targeted, per instruction)

`pytest security/tests/test_check_time_lock_backlog_command.py -v` — 9
passed. No code was touched outside this one test file this round (the
`ci.yml` and doc changes are infra/prose, validated by YAML parsing and the
envsubst dry-run above, not pytest), so no broader Python test run was
needed.

## 9. Review-fix round 3 on PR #483 (CodeRabbit)

Two findings.

### 9.1 MD040: unlabeled fence in this doc's own §8.1 (the `hasattr(timezone, 'timedelta')` verification block)

Confirmed by grepping every `^```$` line in the file: this was the only
genuinely unlabeled *opening* fence remaining (the other two bare matches
are the correct closing fences of blocks already tagged `python`). Tagged
`text`, consistent with the other error/command-output blocks already
fixed this way in round 2 and in `celery-beat-genetic-task-names-plan.md`'s
own MD040 round.

### 9.2 "Deploy to Kubernetes (Production)" runs before the CronJob-apply step and would fail first if it ever actually ran (CONFIRMED, real — fixed by reordering, not by the heavy-lift fix suggested)

CodeRabbit's own remediation was explicitly labeled "🏗️ Heavy lift":
*"Create and populate k8s/production/, or replace the preceding apply path
with the actual production manifest set."* Verified the underlying claim
before deciding how to respond to it, not just the label:

- `kubectl apply -f k8s/production/` (line ~766) is the first command in
  "Deploy to Kubernetes (Production)"; that step opens with
  `set -euo pipefail`. `k8s/production/` does not exist anywhere in this
  repo (re-confirmed: `find k8s/production` — nothing). If this step ever
  actually executes, that first command fails and the step exits
  immediately.
- GitHub Actions skips every subsequent step in a job by default once one
  step fails (an `if:` that doesn't call `always()` doesn't override this).
  The CronJob-apply step added in round 2 sat *after* this step in the
  file, so a real failure here would have silently prevented it from ever
  running — exactly the sequencing risk CodeRabbit flagged.
- **But**: `deploy-production`'s own job condition is
  `if: github.ref == 'refs/heads/main'` — it never runs on `pull_request`
  events at all (confirmed independently: this PR's own checks list shows
  "Deploy to Production (pull_request) — Skipped" for this exact reason).
  And within the job, "Configure kubectl" sets `deploy_enabled=false` and
  clean-exits when `KUBE_CONFIG_PRODUCTION` isn't set as a repo secret,
  skipping every step gated on it. The PR's own merge panel shows *"This
  branch has not been deployed. No deployments."* — consistent with that
  secret never having been configured, meaning this entire step chain has
  never actually executed in this repo's history. The failure mode is real
  but currently latent, not something firing on any check today.

Did **not** attempt the heavy-lift fix: authoring an actual production
manifest set (Deployments/Services/ConfigMaps for backend, websocket,
celery-worker, celery-beat, frontend) with no spec beyond what the existing
`kubectl set image` calls imply would mean fabricating production
infrastructure this repo has no documented topology for — a far larger,
riskier, and more out-of-scope change than a CronJob-scheduling PR should
make, and exactly the kind of guess that "no new regressions" warns
against. That gap is real, pre-existing (predates the Time-Lock work
entirely), and still unfixed after this round — worth its own dedicated
effort by whoever has the actual production manifest specs.

**Fix that stayed in scope**: reordered the "Apply scheduled maintenance
CronJobs" step to run immediately after "Run database migrations
(one-shot Job)" and *before* "Deploy to Kubernetes (Production)" —
mirroring how `migrate-job.yaml`'s own step is already positioned ahead of
that same fragile step, for the same reason. CronJobs don't depend on the
Deployments being rolled out, so nothing is lost moving the step earlier,
and it's now resilient to that pre-existing, unrelated failure instead of
depending on it succeeding.

Verified: `yaml.safe_load` on the full modified `ci.yml` still succeeds;
re-ran the step ordering check
(`yaml.safe_load(...)['jobs']['deploy-production']['steps']`) to confirm
"Apply scheduled maintenance CronJobs" now sits between "Run database
migrations" and "Deploy to Kubernetes (Production)"; re-ran the exact
`envsubst < k8s/cronjobs.yaml | ...` dry-run to confirm all three CronJobs
still resolve their image tags correctly after the move.

### 9.3 Test results (targeted, per instruction)

CI-workflow and doc-only changes this round — no Python code touched, so no
pytest run was needed. Validated via `yaml.safe_load` (whole file parses)
and the envsubst dry-run (exact command the new step runs, output
re-parsed) instead.

## 10. Failing CI check: `Dependency Vulnerability Scan` (real, unrelated to Time-Lock, fixed with a one-line-per-file version bump)

Not a CodeRabbit finding — the "Multi-Scanner Security Scan / Dependency
Vulnerability Scan" GitHub check itself was red on the PR. Investigated the
same way as the round-2 flaky-test check: fetched the actual job log
(`gh api .../actions/jobs/<id>/logs`) rather than trusting the badge.

**Root cause, verified precisely rather than assumed**: the log contains
two errors in sequence, and only one of them is what actually fails the
job.
- `Error: Invalid value for '--policy-file': Unable to load the Safety
  Policy file ".safety-policy.yml"` — from the **"Run Safety check"** step
  (`safety check --file requirements.txt --exit-code --json > ... || true`).
  That trailing `|| true` swallows the failure; this step cannot fail the
  job and is not the cause. Cosmetic pre-existing noise, not touched.
- `##[error]pip-audit reported vulnerabilities or a non-transient error.`
  followed by a JSON dependency report — from the **"Run pip-audit"** step,
  which has no such swallow. This is what actually exits the job non-zero.
  The JSON shows every dependency's `vulns` empty except one:
  `sqlparse==0.5.4` carries four real CVEs (CVE-2026-71491, CVE-2026-59894,
  CVE-2026-59893, CVE-2026-54284 — two ReDoS, one quadratic-complexity DoS,
  one output-escaping code-injection in an opt-in formatter mode), all with
  `fix_versions: ["0.6.0"]`. `pip-audit-ignores.txt` doesn't list any of
  them — genuinely unsuppressed, not a broken suppression mechanism.

**Confirmed unrelated to Time-Lock/this PR**: no file in this branch's diff
touches `requirements*.txt` or anything sqlparse-adjacent; this dependency
scan runs on every `pull_request` push and had been passing on this exact
branch through rounds 1–3, so the CVEs were very likely just published
between then and now (the CVE IDs' `2026` year prefix is consistent with
"recently disclosed", and `pip-audit` queries the live OSV feed on every
run) — the same "not caused by this branch" shape as round 2's flaky test,
but this time a real, fixable finding rather than something to leave alone.

**Fix, verified before applying**:
- Confirmed `sqlparse` is pinned directly (not transitive) in all three
  files that carry it: `requirements.txt`, `requirements-core.txt`,
  `requirements-lock.txt` — all at `==0.5.4`, no compatibility comment
  explaining the pin.
- Confirmed `0.6.0` exists on PyPI (`pip index versions sqlparse`) and
  satisfies Django 5.1.15's own declared constraint
  (`importlib.metadata.requires('django')` → `sqlparse>=0.3.1`, no upper
  bound).
- Confirmed no code in this repo imports `sqlparse` directly (grepped) — it
  is Django's own internal dependency, so a version bump can't break
  application code that isn't there.
- Installed `sqlparse==0.6.0` for real in the local dev venv (not just a
  `--dry-run`) and verified: `python manage.py check` — 0 issues; the full
  `security/tests/test_time_lock_tasks.py` suite (17 tests, 4 subtests,
  exercises the ORM/query layer this PR's own tasks depend on) — all pass.
- Bumped the pin to `==0.6.0` in all three files.

Not fixed as part of this: whatever timing/notification gap let this land
as a red check on an otherwise-unrelated PR rather than surfacing via
Dependabot first — that's a repo-wide dependency-monitoring question, out
of scope here.

### 10.1 Test results (targeted, per instruction)

`python manage.py check` (0 issues) and
`pytest security/tests/test_time_lock_tasks.py -v` (17 passed, 4 subtests)
against the locally-installed `sqlparse==0.6.0`, before committing the
requirements-file bump. No broader suite run needed: the fix is a dependency
version bump with zero application-code changes, and no code in this repo
touches `sqlparse` directly.

## 11. Review-fix round 5 on PR #483 (CodeRabbit, 1 actionable finding)

CI green when this round started (25 successful, 1 neutral Trivy, 6
skipped, the one "in progress" Backend Tests check from the review
comment had finished by the time this round began). Single actionable
finding, no nitpicks this round.

### 11.1 Major: `k8s/cronjobs.yaml`'s three CronJobs hard-code a placeholder image, would ImagePullBackOff

CodeRabbit's claim: `ci.yml`'s `setup` job computes the real backend image
as `ghcr.io/<repo>/backend` (`needs.setup.outputs.backend_image`), but all
three CronJobs in `k8s/cronjobs.yaml` (added by this PR: `cleanup-old-logs`,
`db-backup`, `check-time-lock-backlog`) hard-code
`ghcr.io/yourusername/password-manager/backend` instead — a placeholder
that was never wired up to the real computed name. If the "Apply scheduled
maintenance CronJobs" step (§8, round 2) ever actually runs, every one of
these CronJobs would pull a nonexistent image and fail with
`ImagePullBackOff`.

Verified real: `grep -n "image:" k8s/cronjobs.yaml` confirmed all three
occurrences hard-code the placeholder, and the step's `env:` block
(`ci.yml`, "Apply scheduled maintenance CronJobs") only set `GITHUB_SHA`
for `envsubst` — no `BACKEND_IMAGE`/equivalent variable existed anywhere
in the workflow to resolve the placeholder even if it had been templated
correctly.

**Also discovered, NOT fixed (out of scope, flagged for the repo owner)**:
the identical `ghcr.io/yourusername/password-manager/<name>` placeholder
is hard-coded throughout the REST of `k8s/` too —
`k8s/deployment.yaml` (7 occurrences: 6 `backend`, 1 `frontend`),
`k8s/migrate-job.yaml` (1), `k8s/tor.yaml` (2) — and none of them are
resolved by any `envsubst` variable in `ci.yml` either (the migrate-job
apply step right above the CronJob one has the exact same gap: `env:`
only sets `GITHUB_SHA`, never `BACKEND_IMAGE`). This is a pre-existing,
repo-wide pattern that predates this PR entirely — `k8s/cronjobs.yaml` is
the only file in this list this PR actually authored, and CodeRabbit's own
review (scoped to this PR's diff) only flagged the file it added, not the
five pre-existing manifests sharing the same gap. Fixing those is a much
larger, riskier change (rewriting live Deployment/Job manifests this PR
never touched, for workloads whose actual rollout path hasn't been
audited here) — same class of decision as §9's `k8s/production/` gap:
real, but out of scope for a minimal fix, left for the repo owner.
`migrate-job.yaml` was subsequently fixed too, at the user's explicit
follow-up request — see §11.2. `deployment.yaml` and `tor.yaml` remain
unfixed and out of scope; nobody has asked for those yet.

**Fix, scoped to exactly the two files CodeRabbit named**:
- `.github/workflows/ci.yml`: added `BACKEND_IMAGE: ${{ needs.setup.outputs.backend_image }}`
  to the "Apply scheduled maintenance CronJobs" step's `env:` block,
  alongside the existing `GITHUB_SHA`. `deploy-production`'s `needs:
  [setup, build-images, security-scan]` already makes `setup`'s output
  available here — confirmed by the "Deploy to Kubernetes (Production)"
  step later in the same job already using
  `needs.setup.outputs.backend_image` directly.
- `k8s/cronjobs.yaml`: replaced all three
  `ghcr.io/yourusername/password-manager/backend:${GITHUB_SHA}` lines with
  `${BACKEND_IMAGE}:${GITHUB_SHA}` (CodeRabbit's finding named all three
  as affected, not just the one its inline comment anchored to — fixing
  only one would leave two CronJobs still broken). Updated the file's own
  header comment, which claimed the image handling matched
  `deployment.yaml`'s (now inaccurate, since `deployment.yaml` still
  hard-codes the placeholder per the out-of-scope note above).

Verified both files still parse: `ci.yml` as valid YAML via
`yaml.safe_load_all`, and `cronjobs.yaml`'s three documents parse cleanly
with the `${...}` placeholders substituted for dummy values (envsubst
syntax isn't valid bare YAML on its own, so this confirms structure
without needing a real cluster).

### 11.2 Follow-up (same round, explicit user request): fixed `migrate-job.yaml` too

The user read §11.1's "discovered but not fixed" note and explicitly
asked for `migrate-job.yaml` specifically (not `deployment.yaml`/
`tor.yaml`, which stay out of scope — nobody asked for those). Same bug,
same fix shape: the "Run database migrations (one-shot Job)" step in
`ci.yml` (lines 749-758, the step §11.1 already identified as sharing the
gap) only set `GITHUB_SHA` in its `env:` block; added `BACKEND_IMAGE:
${{ needs.setup.outputs.backend_image }}` alongside it — same
`deploy-production` job, same already-confirmed `needs: [setup, ...]`
availability. In `k8s/migrate-job.yaml`, replaced the single
`ghcr.io/yourusername/password-manager/backend:${GITHUB_SHA}` image line
with `${BACKEND_IMAGE}:${GITHUB_SHA}` — no header comment to update here
(unlike `cronjobs.yaml`, this file didn't claim to match another file's
convention).

### 11.3 Test results (targeted, per instruction)

No Python test surface exists for either change (grepped `security/tests/`
for `yourusername`/`BACKEND_IMAGE`/`cronjobs.yaml`/`migrate-job.yaml` —
zero references; this is pure CI-workflow/Kubernetes-manifest content with
no application code path). Verified via YAML parsing instead (see §11.1),
re-run after §11.2's `migrate-job.yaml` edit: both `ci.yml` and
`k8s/migrate-job.yaml` still parse cleanly (`yaml.safe_load_all`, with
`${BACKEND_IMAGE}`/`${GITHUB_SHA}` substituted for dummy values).

## 12. Review-fix round 6 on PR #483 (CodeRabbit, 2 actionable findings)

CI green when this round started (26 successful, 1 neutral Trivy, 6
skipped, 1 in-progress Docker build unrelated to either finding — no
failing check per `gh pr checks 483`). Both findings verified real against
current code and fixed.

### 12.1 Minor: plan doc's command description describes pre-fix (PII-including) output

CodeRabbit's claim: §5b's prose says `check_time_lock_backlog` reports
"owner/capsule/overdue-by for each match," but the actual command only
emits record IDs and non-identifying metadata.

Verified by reading the real command
(`security/management/commands/check_time_lock_backlog.py` lines 95-117):
confirmed it prints `will.id`/`trigger_type`/`overdue_by` and
`escrow.id`/`release_condition`/`overdue_by`/`party_count` — no
`owner.username`, no capsule/escrow title, with an explicit comment
(lines 95-101) explaining why they're left out. The doc text was simply
never updated after round 1 (§7) stripped that PII from the command's
actual stdout — a stale description, not a code bug. Fixed by adopting
CodeRabbit's suggested wording (accurate to the current command) and
cross-referencing §7 for why the PII was removed.

### 12.2 Major: `check-time-lock-backlog` Job mounts an unused Kubernetes API token

CodeRabbit's claim: the Job's pod spec has no `automountServiceAccountToken:
false`, so it gets the default ServiceAccount token mounted despite the
command never touching the Kubernetes API.

Verified by re-reading the full command (same file as §12.1): zero
Kubernetes-client imports, zero `KUBERNETES_SERVICE_HOST`/`kubeconfig`
references — purely Django ORM reads (`PasswordWill.objects.filter`,
`EscrowAgreement.objects.filter`) and `stdout` writes. The token would be
pure unused attack surface if this container were ever compromised via an
unrelated dependency vulnerability. Fixed by adding
`automountServiceAccountToken: false` to this Job's pod spec, alongside
the existing `serviceAccountName`/`securityContext` block.

**Also discovered, NOT fixed (out of scope, flagged for the repo owner)**:
the same gap exists in this file's other two, pre-existing CronJobs
(`cleanup-old-logs`, `db-backup` — both predate this PR; `git log
--follow -- k8s/cronjobs.yaml` confirms `check-time-lock-backlog` is the
only one this PR's own commits ever touched). Same shape as §11.1's
`BACKEND_IMAGE` gap in `deployment.yaml`/`tor.yaml`: CodeRabbit's review
only covers this PR's diff, so it never flagged the two Jobs it didn't
add. Left alone this round; extend on request, same as §11.2's
`migrate-job.yaml` follow-up.

### 12.3 Test results (targeted, per instruction)

No Python test surface for either change (doc prose + a pod-spec field,
no application code path). Verified via YAML parsing:
`k8s/cronjobs.yaml`'s three documents still parse cleanly with
`${BACKEND_IMAGE}`/`${GITHUB_SHA}` substituted, and the third document's
`spec.jobTemplate.spec.template.spec.automountServiceAccountToken` reads
back as `False`.

## 13. Review-fix round 7 on PR #483 (CodeRabbit, 1 actionable finding) + merge-conflict root-cause investigation

CI green when this round started (27 successful, 1 neutral Trivy, 6
skipped, no failing check per `gh pr checks 483`). One actionable
CodeRabbit finding, plus a user-requested investigation into why GitHub
reported "This branch cannot be rebased due to conflicts."

### 13.1 Minor: module docstring overstates which rows actually fire on the first tick

CodeRabbit's claim: `check_time_lock_backlog.py`'s module docstring says
"ANY PasswordWill or EscrowAgreement already past its deadline fires
immediately" — but the command (and the production tasks it mirrors) only
process eligible rows: active/untriggered wills, and unreleased/
undisputed escrows that additionally pass `can_release`.

Verified by re-reading the command's actual query logic (lines 49-77,
unchanged since round 1's `can_release` fix, §7): `PasswordWill.objects
.filter(is_active=True, is_triggered=False)` plus the inactivity/date
deadline check; `EscrowAgreement.objects.filter(is_released=False,
is_disputed=False, approval_deadline__lte=now)` further filtered by
`if escrow.can_release`. The code has always been correct on this point
— round 1 specifically fixed the query to stop over-reporting non-
releasable escrows. Only the top-of-file prose summary (written before
that fix, never updated after) still used the looser "ANY... already past
its deadline" phrasing. Fixed by adopting CodeRabbit's suggested wording,
which matches the actual eligibility gates precisely.

### 13.2 Investigated (not a CodeRabbit finding): "This branch cannot be rebased due to conflicts"

GitHub's PR page showed this branch as `mergeStateStatus: CLEAN` /
`mergeable: MERGEABLE` via `gh pr view 483 --json mergeable,mergeStateStatus`
— the actual merge (via "Merge pull request" or "Squash and merge") is
NOT blocked. Only GitHub's "Rebase and merge" option, which requires
replaying every commit in the PR linearly onto `main`, was affected.

**Root cause, found by reproducing the rebase in a disposable local
branch** (`git branch -f _rebase_probe HEAD`, rebase there, inspect,
`git rebase --abort`, delete the probe branch — never touched the real
branch or origin): `git log --oneline --reverse origin/main..HEAD` shows
this branch's own 20 commits contain the SAME logical work TWICE, under
two different sets of commit hashes back-to-back (e.g.
`fix(celery): merge the never-scheduled Time-Lock beat schedule` appears
as both `e8e99f7` and, nine commits later, `34bc672` with matching later
duplicates for every round-1/2/3 commit and the sqlparse bump). Traced to
merge commit `230e093` ("Merge branch '...' of https://github.com/... into
fix/time-lock-beat-schedule-not-merged") already present in this branch's
history, with parents `4dbcf45` and `5220fb9` — and the PR's own commit
timeline (pasted into this session by the user) independently confirms
`Rajarshi1-source force-pushed the branch from 4dbcf45 to 5220fb9` shortly
before that merge commit landed. Sequence: the remote branch was
force-pushed to a rebased history (`5220fb9`, rewriting every earlier
commit's hash); a `git pull origin fix/time-lock-beat-schedule-not-merged`
run earlier in this same working session (a plain fetch+merge, not
fetch+rebase) then joined that new remote tip with a stale pre-force-push
local copy still sitting in this environment's repo (still at `4dbcf45`),
producing merge commit `230e093` — which duplicates the entire commit
sequence rather than cleanly fast-forwarding, because the two sides had
diverged (different hashes) despite identical logical content. This merge
commit is not just local: `origin/fix/time-lock-beat-schedule-not-merged`
was subsequently pushed with it included (round 5/6 commits sit on top of
it), so it's now part of the PR's public history, which is what trips up
GitHub's linear-rebase check specifically.

**Not fixed**: cleaning this up properly means rewriting this branch's
history (e.g. resetting onto `origin/main` and replaying only the
non-duplicate commits, or an interactive rebase dropping the redundant
half) and force-pushing the result — a destructive operation on a shared,
already-reviewed remote branch (CodeRabbit has commented against specific
commit SHAs in this history). Per this session's own safety rules,
force-pushing a branch other sessions/reviewers may be relying on needs
explicit confirmation before acting, not just an instruction to "fix the
merge conflict" in general — especially since the actual merge is not
blocked today. Flagged for the user to decide: accept as-is (merge via
the default button, history noise disappears once merged), or explicitly
authorize a history rewrite + force-push if linear rebase-merge is
required by repo policy.

### 13.3 Test results (targeted, per instruction)

No Python test surface for either item this round — §13.1 is a prose-only
docstring edit with no behavior change (verified with `py_compile`, not a
test run), and §13.2 was an investigation that made no code change at
all. The disposable `_rebase_probe` branch used for that investigation
was deleted after `git rebase --abort`; the real branch and `origin` were
never touched.

## 14. Round 8 on PR #483: failing CI check fixed, CodeRabbit found nothing new, merge-conflict fixed (explicit authorization)

CodeRabbit's own full review this round posted zero inline comments
(confirmed via `gh api repos/.../pulls/483/comments` — empty result) and
its PR-level comment was just "Full review finished" with no "Actionable
comments posted" line at all, unlike every prior round. Nothing to fix
there. Two other items this round: a genuinely failing CI check, and the
merge-conflict fix from §13.2, now explicitly authorized by the user.

### 14.1 Failing check: `Multi-Scanner Security Scan / Dependency Vulnerability Scan`

Fetched the real job log (`gh api .../actions/jobs/<id>/logs`), same
method as every prior CI-check investigation in this doc — not the badge.
Root cause: `django==5.1.15` has one NEW, unsuppressed finding,
`PYSEC-2026-3717` / `CVE-2026-15830` — unbounded recursion / segfault in
`django.contrib.gis.geos.GEOSGeometry` when parsing a deeply nested
`GEOMETRYCOLLECTION` from WKT/WKB/hex-WKB. `fix_versions: ["5.2.17",
"6.0.8"]` — the same Django 5.2/6.0 minor-upgrade family already deferred
for six sibling CVEs in `pip-audit-ignores.txt`'s existing "Django
advisories disclosed 2026-08" block.

**Verified non-reachable, not assumed**, the same rigor as every entry
already in that file: zero `GEOSGeometry(`/`GeometryField`/`geos=True`
anywhere in the codebase (grep); `django.contrib.gis` stays commented out
of `INSTALLED_APPS`; the only `django.contrib.gis` import anywhere
(`django.contrib.gis.geoip2.GeoIP2`, used in
`honeypot_credentials/services/access_interceptor.py` and
`logging_manager/models.py`) only ever calls `.city(ip)` and reads the
returned dict's string keys — it never constructs a Geometry object, so
no WKT/WKB reaches GEOS. Structurally identical to the file's existing
`CVE-2026-53877` (GDALRaster) entry two bullets up — same subsystem
family, same "GeoIP2 is the only door in, and it doesn't lead here"
argument.

**Fix**: added `CVE-2026-15830 exp:2026-10-20` to `pip-audit-ignores.txt`
with a full threat-assessment comment, following this file's own required
format exactly (checked the workflow's validator script,
`.github/workflows/security-multi-scanner.yml` "Validate pip-audit ignore
expiries" step, to confirm the `CVE-\d{4}-\d+` regex and non-expired-date
requirements before adding the line — not just copying the visual
pattern). Verified locally two ways: (1) replayed the validator's own
parser against the file — 28 entries, zero malformed, zero expired,
`CVE-2026-15830` present; (2) ran `pip-audit` directly against an
isolated `Django==5.1.15`-only requirement with just
`--ignore-vuln CVE-2026-15830`, confirming that specific ID drops out of
the report (the other six pre-existing Django CVEs still showed, exactly
as expected, since only one flag was passed in that isolated check).

**Declined**: bumping Django itself to 5.2.17+. A Django MINOR version
bump is a categorically larger, riskier change than every prior CVE fix
in this whole engagement (sqlparse, torch, etc. are leaf/ML dependencies
with no framework-wide blast radius) — exactly the reasoning the file's
own existing Django block already established for its six other entries.
Not this PR's scope (Time-Lock beat scheduling), and doing it opportunistically
inside an unrelated PR risks exactly the kind of untested regression these
rounds have been careful to avoid throughout.

### 14.2 Merge-conflict fix (explicit authorization given this round)

§13.2 found the root cause but deliberately did not act on it without
explicit sign-off, since the fix requires rewriting and force-pushing a
shared, already-reviewed branch's history. The user's next message
explicitly authorized this ("fix the merge conflict problem... rebase and
merge button is not working"), confirmed again via `AskUserQuestion`
after the harness's own permission classifier blocked the first
`git checkout` of the fix (a scratch-branch checkout, not yet anything
destructive) pending explicit approval.

**Method, verified at every step before anything touched the real branch
or `origin`**:
1. Built a disposable branch (`_history_rebuild`) from `origin/main`.
2. Cherry-picked, in order, only the 12 non-duplicate commits identified
   in §13.2 (`34bc672` through `67a426d`, the SECOND/final occurrence of
   each duplicated commit plus the three genuinely-new round 5/6/7
   commits) — deliberately skipping the first/stale duplicate chain
   (`e8e99f7` through `4dbcf45`) and the self-merge commit (`230e093`)
   entirely. All 12 applied with **zero conflicts** — direct confirmation
   that the two duplicate chains really were content-identical, not just
   message-identical.
3. **Critical safety gate**: `git diff <old-branch-tip> <new-branch-tip>`
   — empty. `git rev-parse <old>^{tree}` and `<new>^{tree}` — identical
   hash (`c8afaec6...`) on both sides. This is not "looks the same"; it's
   the same tree object. Only proceeded past this point because the
   check passed.
4. Applied §14.1's `pip-audit-ignores.txt` fix as one new 13th commit on
   top of the verified-identical rebuilt history.
5. Re-verified: `git merge-base --is-ancestor origin/main HEAD` true, and
   `git rev-list --count origin/main..HEAD` == 13 — the branch is now a
   genuinely linear descendant of `main`, which structurally guarantees
   GitHub's "Rebase and merge" has nothing to replay against a different
   base and can no longer conflict.
6. Force-pushed with `--force-with-lease=<branch>:<known-remote-sha>`
   (not a blind `--force`) after re-fetching to confirm the remote tip
   hadn't moved since the last check — protects against clobbering a
   concurrent push from anyone else.
7. Reset the local branch (`git reset --hard origin/<branch>`, NOT
   `git pull` — a plain pull here is exactly the mistake that created
   this whole problem in the first place, per §13.2's own root-cause
   finding) and deleted the disposable branch.

**Result, confirmed via `gh pr view --json mergeable,mergeStateStatus,commits`**:
`commitCount: 13` (down from 22), `mergeable: MERGEABLE`. Also confirmed
locally with a direct `pip-audit` run against the suppression (§14.1) —
not relying on GitHub's UI alone for either fix.

### 14.3 Test results (targeted, per instruction)

No Python test surface changed by either fix (a text-manifest suppression
entry and a git-history operation, no application code touched). `ci.yml`
re-validated as parseable YAML after the rebuild. `pip-audit` run locally
against an isolated Django-only requirement (§14.1) is the direct
functional verification for the CI-check fix; the tree-hash equality
check (§14.2 step 3) is the direct functional verification for the
history rewrite — both stronger guarantees than a `pytest` run would give
for changes of this shape.

## 15. Round 9 on PR #483: NetworkPolicy gap (CodeRabbit Major) + a stuck CI job re-run

§14.1's fix confirmed working: `Dependency Vulnerability Scan` came back
green on the rebuilt history. This round: one real CodeRabbit finding, and
one genuinely-unrelated CI job that needed a re-run rather than a code fix.

### 15.1 Major: `check-time-lock-backlog`'s Pod has no NetworkPolicy path to Postgres

CodeRabbit's claim: `k8s/network-policy.yaml` is `default-deny-all`; no
policy grants `component: maintenance` egress to Postgres, and
`allow-postgres`'s ingress `from:` list doesn't include `maintenance`
either — so this PR's own `check-time-lock-backlog` CronJob cannot reach
the database at all if NetworkPolicy enforcement is active in the target
cluster.

**Not actually new** — this is the exact gap flagged (and deliberately
not fixed) back in round 4 §"Scheduling decision": *"network-policy.yaml
is default-deny-all with no database-egress rule for `component:
maintenance` at all... worth this user following up on separately."*
CodeRabbit is now surfacing the same gap formally against this round's
diff, since `check-time-lock-backlog`'s pod (added by this PR) carries
that same label. Re-verified directly rather than trusting the round-4
note alone: read `network-policy.yaml` in full — confirmed no
`NetworkPolicy` document selects `component: maintenance`, and
`allow-postgres`'s `ingress[].from` list has exactly three entries
(`backend`, `websocket`, `celery-worker`/`celery-beat`), no fourth for
maintenance.

Unlike round 4's assessment, decided this IS in scope this time: the
`check-time-lock-backlog` Job is this PR's own resource, its entire
purpose is querying Postgres (`PasswordWill`/`EscrowAgreement` via plain
Django ORM — pure read, no cache/Redis touch, confirmed by grep), and the
fix is a small, additive, well-scoped change (one new `NetworkPolicy`
document mirroring the existing `allow-celery` pattern exactly, plus one
list entry in `allow-postgres`) — not the "heavy lift" category that made
`k8s/production/` and the Django minor-version bump correctly
out-of-scope calls. It also incidentally fixes the same gap for the two
pre-existing CronJobs (`cleanup-old-logs`, `db-backup`) that share the
`component: maintenance` label, at no extra cost.

**Fix**: added `allow-maintenance` (egress to `component: database` on
5432 only — verified neither `cleanup_old_logs.py`, `db_backup.py`, nor
`check_time_lock_backlog.py` touches redis/cache, so no cache-egress rule
was added, matching CodeRabbit's own scoped suggestion exactly), and
added `component: maintenance` as a fourth `from:` entry in
`allow-postgres`'s ingress list. Verified the new policy's `podSelector`
labels (`app: password-manager`, `component: maintenance`) match all
three CronJobs' actual Pod-template labels in `k8s/cronjobs.yaml` (grepped
directly, not assumed).

### 15.2 Unrelated: `CI/CD Pipeline / Backend Tests` cancelled after 6 hours

Not a CodeRabbit finding or a code bug. Fetched the job's step timeline
(`gh api .../actions/jobs/<id>` steps array) rather than trusting the red
badge: "Install dependencies" (the ~3-4GB torch/tensorflow/mediapipe pip
install) started at 21:14:10 and was still running when GitHub's own
6-hour job ceiling force-cancelled it at 03:12:34 — every step after it
shows `skipped`, meaning the job never even reached the test-running
steps. On the exact same commit, the separate, leaner "Backend CI/CD /
Run Tests" workflow (a different workflow file) completed successfully in
27 minutes — independent confirmation the actual code and tests are fine;
this is a stuck/stalled dependency install, not a deterministic failure.
Same "verify before touching code" discipline as round 2's flaky-test
investigation: no code change would address a stuck `pip install`, so
none was made. Re-triggered the job directly instead
(`gh run rerun <run-id> --failed`) — a safe, reversible action, not a
code change — rather than guessing at a fix for infrastructure the diff
never touched.

### 15.3 Test results (targeted, per instruction)

No Python test surface for the NetworkPolicy change (pure K8s manifest,
no application code path) — verified via `yaml.safe_load_all` (9 documents
parse cleanly) and by confirming the new policy's `podSelector` matches
the real Pod labels already in `k8s/cronjobs.yaml`, the same verification
method used for every K8s-manifest fix in this doc (§11, §12).
