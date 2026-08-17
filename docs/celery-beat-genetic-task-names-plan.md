# Plan — Fix the 3 broken genetic/DNA Celery beat task names

Branch: `fix/celery-beat-genetic-task-names` (off `main` @ `518b973`)

**Update — round 2**: the user asked for the other 8 pre-existing broken
entries (§4 below) to be fixed too, not just quarantined. See §7 for what
changed and why. `KNOWN_UNREGISTERED` in the guard test is now empty.

## 1. The reported problem

`password_manager/password_manager/celery.py` schedules three tasks under names
that are not in the live Celery registry:

| beat entry | scheduled name | real registry name |
| --- | --- | --- |
| `check-genetic-evolution-daily` | `security.tasks.daily_genetic_evolution_check` | `security.tasks.breach_tasks.daily_genetic_evolution_check` |
| `cleanup-genetic-trials` | `security.tasks.cleanup_expired_genetic_trials` | `security.tasks.breach_tasks.cleanup_expired_genetic_trials` |
| `refresh-dna-tokens-weekly` | `security.tasks.refresh_dna_tokens` | `security.tasks.breach_tasks.refresh_dna_tokens` |

The three functions live in `security/tasks/breach_tasks.py` under a bare
`@shared_task`, so Celery derives the name from the **defining** module — which
carries the `breach_tasks` segment. Beat still publishes the message (the
scheduler falls back to `send_task` for names it cannot resolve locally); the
**worker** is what rejects it as `NotRegistered`. Either way the three jobs have
never run.

Verified against the live registry with the `canny` venv:

```bash
DEBUG=True canny/Scripts/python.exe -c "import django,os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','password_manager.settings'); django.setup(); from password_manager.celery import app; app.autodiscover_tasks(force=True); import security.tasks; print('\n'.join(sorted(app.tasks)))"
```

## 2. Fix (a) vs fix (b)

**Chosen: (a) — correct the three beat entries to the real dotted names.**

The brief said to prefer (b) (pin `name='security.tasks.<func>'` on the
decorators) *if anything else already refers to the short names*. Grepped the
whole repo for all three identifiers across `.py/.md/.yml/.yaml/.json/.js/.jsx/.sh/.cfg/.toml`:
the only references to the **short dotted names** are the three broken
`celery.py` entries themselves. `security/tasks/__init__.py` and
`security/tests/test_genetic_password.py` reference the **Python symbols**, which
are unaffected by either fix. So (b)'s precondition is not met.

Further reasons for (a):

- **Direct in-file precedent.** The adaptive-password block immediately below
  these entries already resolved this exact question the same way in PR #475,
  and documents it at length: names verified against the live registry rather
  than taken from plan text, `security.tasks.adaptive_tasks.*`.
- **(b) is a rollout hazard.** Renaming a registered task means a worker running
  old code does not recognise the new name. (a) changes only what beat
  publishes.
- **(b) re-creates the original confusion** — a name that disagrees with its
  defining module is precisely what made this bug invisible.

Not doing: normalising the four siblings in the same file that *do* carry an
explicit `name='security.tasks.<func>'` (`update_threat_intelligence`,
`evaluate_password_expiration_risk`, `daily_predictive_scan`,
`send_expiration_notifications`). They work today and have live beat entries;
renaming them would be unrelated risk.

## 3. Safety audit — "this is not a no-op cleanup"

Fixing the names turns three dead jobs on. Each was checked against the current
schema before enabling. **Two of the three crash as written**, and the fan-out
target of the third is broken in two further ways.

### 3.1 `cleanup_expired_genetic_trials` — safe, enable as-is

Touches only `GeneticSubscription`. Every field it uses (`tier`, `status`,
`trial_expires_at`, `epigenetic_evolution_enabled`) exists. Idempotent: the
queryset filters `status='active'`, and the task sets `status='expired'`, so a
re-run selects nothing. `trial_expires_at__lt=now` excludes NULLs, and the
model's `save()` override only backfills `trial_expires_at` when it is unset, so
saving an already-dated row does not extend the trial. Already covered by
`test_cleanup_expired_trials_task`. **No code change needed.**

### 3.2 `daily_genetic_evolution_check` — `FieldError`, would crash on first run

```python
user__geneticsubscription__epigenetic_evolution_enabled=True
```

`GeneticSubscription.user` is a `OneToOneField(related_name='genetic_subscription')`,
so the reverse query name is `genetic_subscription`, not the default
`geneticsubscription`. Confirmed empirically:

```
FieldError: Unsupported lookup 'geneticsubscription' for ForeignKey or join on the field not permitted.
```

Fix: use `user__genetic_subscription__…`.

Additionally, narrow the queryset with `last_biological_age__isnull=False`.
`check_and_evolve` returns `"No biological age data available"` immediately when
that field is NULL, so those connections can never evolve; filtering them out
makes the daily fan-out queue **zero** tasks in the current (unconfigured) state
instead of one guaranteed no-op task per eligible user. Same outcomes, less work.

### 3.3 `check_genetic_evolution` (the fan-out target) — two more bugs

`daily_genetic_evolution_check`'s entire job is `check_genetic_evolution.delay(...)`,
so enabling the parent means enabling this. It calls:

```python
result = epigenetic_evolution_manager.check_and_evolve(user)
if result.get('evolved'):
```

against a method whose real signature is:

```python
async def check_and_evolve(user, dna_connection, force=False) -> Tuple[bool, Optional[str]]
```

Three mismatches: missing the required `dna_connection` argument, an unawaited
coroutine, and a tuple treated as a dict.

**And the method cannot work from a Celery task even when called correctly.**
`check_and_evolve` is `async def` but performs sync ORM throughout
(`user.genetic_subscription`, `dna_connection.save()`,
`GeneticEvolutionLog.objects.create`, `subscription.save()`). Django rejects
that:

```
SynchronousOnlyOperation: You cannot call this from an async context - use a thread or sync_to_async.
```

Crucially, **`check_and_evolve` contains zero `await` expressions** — it is
gratuitously async. Both of its call sites are sync contexts:

- `security/tasks/breach_tasks.py:310` (this task)
- `security/api/genetic_password_views.py:975` — already calls it *correctly*,
  `async_to_sync(...)` with tuple unpacking, and therefore already hits
  `SynchronousOnlyOperation`. The view catches it into a generic 500, so the
  manual "trigger evolution" endpoint has been silently failing.

**Fix: make `check_and_evolve` a plain `def`** and update both call sites. This
repairs the API endpoint as well as the task.

### 3.4 `refresh_dna_tokens` — `AttributeError`, would crash on first connection

```python
if connection.encrypted_refresh_token:
```

The field is `refresh_token_encrypted` (confirmed: `DNAConnection` token fields
are `access_token_encrypted`, `refresh_token_encrypted`, `token_expires_at`).
`AttributeError` is not caught — the `except` clause is `ValueError` only — so
the task dies on the first active connection.

**The brief's concern about outbound calls does not apply.** The body is a
placeholder: it resolves a provider class and logs. There is no network call, no
token decryption, and no write. Nothing to configure-gate.

That creates a different problem: with the attribute fixed, the task would log
`"Provider OAuth refresh complete: N refreshed, 0 failed"` having refreshed
nothing — false success telemetry, which is worse than a dead job. So the fix
also makes the reporting honest: count `needs_refresh`, return
`{'refreshed': 0, …, 'implemented': False}`, and log at WARNING that the refresh
call is unimplemented.

### 3.5 Is the DNA / Humanity.health integration configured?

No. `HUMANITY_HEALTH_API_KEY` / `_CLIENT_ID` / `_CLIENT_SECRET` appear only in
`password_manager/.env.genetic.example`, all blank; there are no settings
entries. Consistent with §3.2 — with no provider, `last_biological_age` is never
populated, so the narrowed fan-out selects nothing and the daily job is inert
until someone configures a provider or enters a biological age manually.

## 4. Out of scope — 8 further broken beat entries

Auditing **all 42** beat entries against the registry found 11 broken, not 3.
The other 8 are pre-existing, unrelated, and each belongs to a different feature
area:

| beat entry | unregistered name | why |
| --- | --- | --- |
| `analyze-password-strength-daily` | `ml_security.tasks.analyze_all_passwords` | `ml_security` has no `tasks.py` |
| `update-threat-intel` | `ml_security.tasks.update_threat_intelligence` | real name is `security.tasks.update_threat_intelligence` |
| `cleanup-expired-sessions` | `shared.tasks.cleanup_expired_sessions` | `shared` has no `tasks.py` |
| `dark-protocol-rotate-paths` | `dark_protocol.rotate_network_paths` | functions live in `security/tasks/dark_protocol_tasks.py`, which `security/tasks/__init__.py` never imports; `dark_protocol` is not in `INSTALLED_APPS` |
| `dark-protocol-health-check` | `dark_protocol.health_check_nodes` | ″ |
| `dark-protocol-cover-traffic` | `dark_protocol.generate_cover_traffic` | ″ |
| `dark-protocol-cleanup` | `dark_protocol.cleanup_expired_sessions` | ″ |
| `dark-protocol-traffic-analysis` | `dark_protocol.analyze_traffic_patterns` | ″ |

Fixing these means enabling five Dark Protocol jobs and reviving two apps'
missing task modules — separate features with their own history (Dark Protocol:
PRs #454/#464). Left for follow-up PRs, but **locked in by the guard test below**
so they cannot be forgotten or quietly grow.

## 5. Changes

1. **`password_manager/password_manager/celery.py`** — three `'task':` values to
   the real registry names, plus a comment recording the (a)-vs-(b) reasoning.
2. **`password_manager/security/services/epigenetic_service.py`** —
   `check_and_evolve`: `async def` → `def`.
3. **`password_manager/security/api/genetic_password_views.py`** — drop the
   `async_to_sync` wrapper at the `check_and_evolve` call (keep the import;
   three other call sites still use it).
4. **`password_manager/security/tasks/breach_tasks.py`** —
   - `check_genetic_evolution`: call `check_and_evolve(user, dna_connection)`,
     unpack `(evolved, message)`, drop the now-duplicated
     `evolution_generation` / `last_biological_age` write (the manager already
     saves them), source log values from the mutated instance.
   - `daily_genetic_evolution_check`: `genetic_subscription` reverse name;
     `last_biological_age__isnull=False`.
   - `refresh_dna_tokens`: `refresh_token_encrypted`; honest counters and log.

## 6. Tests

- **New `security/tests/test_celery_beat_registry.py`** — the regression guard
  that would have caught all of this: assert every `beat_schedule` entry
  resolves to a registered task. The 8 pre-existing breakages sit in an explicit
  `KNOWN_UNREGISTERED` quarantine dict; a second test asserts each quarantined
  entry is *still* unregistered, so the list cannot rot and fixing one forces
  its removal.

  The registry snapshot is taken in a **fresh subprocess**, not read off the
  already-running test process's `app.tasks`. `@shared_task` registers a
  function into a registry shared by every `Celery()` instance in the process
  the moment its module is imported — and `test_dark_protocol.py`'s tests
  `import security.tasks.dark_protocol_tasks` inside their bodies (to exercise
  those tasks directly, since `dark_protocol` isn't in `INSTALLED_APPS`).
  Running the full suite, that import happens well after this module is
  collected, so five Dark Protocol tasks looked "registered" in-process even
  though no autodiscovery path imports that module in production. Caught by
  actually running the two suites together
  (`pytest test_dark_protocol.py test_celery_beat_registry.py`) before trusting
  the guard test; fixed by shelling out to a clean interpreter that runs only
  `autodiscover_tasks()` + `import security.tasks` — the same sequence a real
  worker runs, immune to whatever else shares the pytest process.
- **Update `test_check_genetic_evolution_task`** — it currently patches the
  manager with a bare `MagicMock`, which accepts any signature and returns a
  dict, so it passes *against the broken call*. Switch to `autospec=True` so
  arity/async drift fails the test, with a side effect that mimics the real
  manager's row mutation.
- **New**: `daily_genetic_evolution_check` runs without `FieldError` and selects
  only eligible connections with biological-age data.
- **New**: `refresh_dna_tokens` runs without `AttributeError` against a
  connection holding a refresh token, and reports `refreshed: 0` /
  `implemented: False`.
- **New**: `check_and_evolve` is not a coroutine function and completes real ORM
  work when called from a sync context.

Run with the `canny` venv and `DEBUG=True`.

## 7. Round 2 — the other 8 broken entries

The user asked for §4's 8 quarantined entries to be fixed rather than left
for follow-up PRs. Investigated each individually; they turned out to split
into three different bug shapes, one dead entry, and one unrelated
out-of-scope discovery.

### 7.1 `update-threat-intel` — wrong app prefix

Scheduled `ml_security.tasks.update_threat_intelligence`. The task is real,
just registered elsewhere: `security.tasks.update_threat_intelligence`
(`breach_tasks.py`, explicit `name=`). Fixed the beat entry's task string.

Not new capability: `daily_predictive_scan` already calls
`update_threat_intelligence()` directly (a plain function call, not
`.delay()`) as its first step, and that scan has a working beat entry
(`predictive-daily-scan`) today. Fixing this entry means the threat-feed
refresh now runs twice a day instead of once — redundant, not harmful:
`update_threat_intelligence` only upserts `ThreatIntelFeed` sync status and
aggregates `IndustryThreatLevel`; re-running it early has no unbounded side
effect.

### 7.2 Dark Protocol × 5 — correct names, missing import

This is where §4's original diagnosis was wrong. Re-reading
`security/tasks/dark_protocol_tasks.py` shows every `@shared_task` there
already carries an explicit `name='dark_protocol.<func>'` that matches
`celery.py`'s beat entries **exactly**. The bug was never the name — it's that
`security/tasks/__init__.py` never imported this module, so those decorators
never executed and nothing ever registered the name beat was asking for.

Fix: added an import block for `dark_protocol_tasks` in
`security/tasks/__init__.py`, mirroring the existing try/except pattern
already used for `time_lock_tasks` and `adaptive_tasks`. No changes to
`celery.py` needed for these five at all.

Verified safe to enable before wiring the import:
- Confirmed the reverse-relation names used in the tasks' ORM filters
  (`user__dark_protocol_sessions`, `user__dark_protocol_config`) actually
  match the models' `related_name`s — the same class of bug that broke
  `daily_genetic_evolution_check` in round 1 does NOT recur here.
- Grepped the whole call chain (`dark_protocol_tasks.py`,
  `dark_protocol_service.py`, `cover_traffic_generator.py`,
  `noise_encryptor.py`) for `httpx`/`requests`/`socket`/etc: zero matches.
  `health_check_nodes` is explicitly a `random.random()` simulation ("in
  production, this would ping the node"); `rotate_network_paths`'s node
  selection (`_select_path_nodes`) is a pure DB filter over
  `DarkProtocolNode`, no dialing. None of the five make outbound network
  calls.
- Every task's query is gated on `is_enabled` / `cover_traffic_enabled` /
  `learn_from_real_traffic` / an active session existing, so each is a cheap
  empty-queryset no-op until Dark Protocol is actually in use by a real user.
  `DARK_PROTOCOL['ENABLED']` defaults `True` in settings, but that only
  affects whether the feature is *reachable*, not whether any
  `DarkProtocolConfig` rows exist yet.
- `health_check_nodes` and `cleanup_expired_sessions` (the Dark Protocol one,
  distinct from §7.3) already had passing direct task tests
  (`test_dark_protocol.py::DarkProtocolTaskTests`). Added matching smoke
  tests for the other three (`rotate_network_paths`,
  `generate_cover_traffic`, `analyze_traffic_patterns`), plus a test that
  imports `security.tasks` and asserts `DARK_PROTOCOL_TASKS_AVAILABLE` is
  `True` — the actual regression this whole fix is about.

### 7.3 `cleanup-expired-sessions` — task genuinely didn't exist, implemented it

`shared.tasks.cleanup_expired_sessions` named a task in an app
(`shared`) that had no `tasks.py` at all — nothing to rename this into.
Unlike the Dark Protocol case, this isn't a Django "sessions" feature that's
niche or optional: `django.contrib.sessions` is installed with the DB-backed
engine (`SESSION_ENGINE = django.contrib.sessions.backends.db`, confirmed),
so `django_session` accumulates a row per login with nothing pruning it.
Django ships exactly this cleanup as the `clearsessions` management command
(`Session.objects.filter(expire_date__lt=now).delete()`); added
`shared/tasks.py` with a Celery-task equivalent of that same query. No
`celery.py` change needed — the name it already scheduled is now real.

Also added `shared/tests/` (a `tests/` package; `shared` had none). Note for
future work in this app: `pytest.ini` has no `python_files` override, so
pytest's default `test_*.py` / `*_test.py` glob applies — the `tests.py`
(bare, no underscore) files already present in several peer apps
(`ml_security/tests.py`, `logging_manager/tests.py`, etc.) are NOT matched by
that glob and are not part of the suite `pytest security/tests/` or a
rootdir-wide `pytest` run collects; they only run if invoked by explicit
path. Followed the pattern that's actually proven to be collected
(`security/tests/test_*.py`) rather than the inconsistent one.

### 7.4 `analyze-password-strength-daily` — removed, not fixed

No task by this name, or any equivalent, exists anywhere in the codebase.
The only thing that scores password strength
(`PasswordStrengthPredictor` in `ml_security/ml_models/password_strength.py`)
is wired into the adversarial-AI red-team feature (`adversarial_ai/`), not
any per-user vault sweep — confirmed via `grep -rl PasswordStrengthPredictor`.

Writing a new task under this name would require the server to decrypt every
user's stored passwords to score them. That conflicts with the zero-knowledge
design this same file already commits to for daily password-risk analysis:
`daily_predictive_scan`'s own docstring states "the server never decrypts
the vault — it only refreshes risk on stored structural metadata," and its
`predictive-daily-scan` beat entry already runs that zero-knowledge-compatible
daily analysis in production today.

Asked the user rather than deciding unilaterally, since the two reasonable
paths (remove the dead entry vs. build new architecture-conflicting
functionality) diverge too far to pick silently. Chose: **removed the
entry**. `daily_predictive_scan` / `evaluate_password_expiration_risk`
already supersede whatever this was meant to do. Guarded by
`test_dead_password_strength_entry_was_removed_not_fixed` so it can't
silently reappear.

### 7.5 Discovered, NOT fixed: Time-Lock beat schedule is never merged

While reading `security/tasks/__init__.py` for the dark-protocol import
pattern, noticed it also imports
`time_lock_tasks.CELERY_BEAT_SCHEDULE as TIME_LOCK_BEAT_SCHEDULE` — but that
name is never referenced again anywhere (grepped `celery.py` and this whole
package). `time_lock_tasks.py` defines a real `CELERY_BEAT_SCHEDULE` dict
(line 507) for `check_capsule_unlocks`, `check_dead_mans_switches`,
`check_expired_capsules`, `check_escrow_deadlines`, etc. — the Password
Will / Dead Man's Switch feature — and it is never merged into `celery.py`'s
actual `app.conf.beat_schedule`. Those tasks are fully implemented and would
work if invoked, but nothing ever schedules them; the beat process simply
never asks for them.

This is arguably more severe than anything in this PR — a dead man's switch
that doesn't fire is a different failure mode than a genetic-evolution check
that doesn't run — but it's a different feature with its own safety
questions (inheritance/beneficiary notification correctness, what happens on
a late trigger, whether time-based triggers need catch-up-on-restart
semantics). Asked the user whether to expand this PR to cover it; they chose
to flag it only. **Deliberately left untouched.** Follow-up PR needed.

## 8. Round-2 test results

`pytest shared/tests/ security/tests/test_dark_protocol.py
security/tests/test_celery_beat_registry.py`: 40 passed (8 subtests).

Full `pytest security/tests/ shared/tests/`: 1148 passed, 7 skipped
(pre-existing), 0 failed — up from round 1's 1138 by the 10 new tests added
this round (3 explicit registry-resolution tests, 5 dark-protocol task
tests, 2 shared-session-cleanup tests).
