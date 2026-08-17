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
`EscrowAgreement` with `approval_deadline` already passed — would all fire
in a single batch on the very first beat tick after this deploys, rather
than each having fired individually at its own due date. For a feature whose
job is "reveal secrets to a beneficiary," a surprise batch is a materially
different experience than the intended one-at-a-time behavior.

I have no access to production data to check whether such a backlog exists.
**This must be checked before deploying**, not just before merging:

```python
from security.models import PasswordWill, EscrowAgreement
from django.utils import timezone
now = timezone.now()

overdue_wills = [
    w for w in PasswordWill.objects.filter(is_active=True, is_triggered=False)
    if (w.trigger_type == 'inactivity' and now >= w.last_check_in + timedelta(days=w.inactivity_days))
    or (w.trigger_type == 'date' and w.target_date and now >= w.target_date)
]
overdue_escrows = EscrowAgreement.objects.filter(
    is_released=False, is_disputed=False, approval_deadline__lte=now,
)
```

If either is non-empty, `check_dead_mans_switches` / `check_escrow_deadlines`
will trigger all of them on the first tick post-deploy. Flagging this
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
trigger logic exactly, reporting owner/capsule/overdue-by for each match and
exiting 1 if anything is found (0 otherwise) -- safe to gate a deploy script
on, or just run by hand. Covered by 8 tests
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
