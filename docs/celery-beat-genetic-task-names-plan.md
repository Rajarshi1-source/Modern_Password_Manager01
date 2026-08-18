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

```text
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

```text
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

## 9. Review-fix round 1 on PR #482 (CodeRabbit, commit afdc51a)

CodeRabbit's full review on commit `afdc51a` flagged 1 Major finding and 1
Nitpick. Verified both critically against the actual current code (not
taken on the bot's word) before changing anything, per instruction. Both
confirmed real; both fixed. A third item (docstring coverage 73.53% < 80%
threshold) was deliberately left alone — a repo-wide advisory metric, not a
specific defect, and chasing it across unrelated functions would work
against the "keep changes minimal" instruction for this pass.

### 9.1 Major: `check_genetic_evolution` double-writes the evolution log and counter (CONFIRMED)

CodeRabbit's claim: `EpigeneticEvolutionManager.check_and_evolve`
(`epigenetic_service.py`) already creates the `GeneticEvolutionLog` row and
increments `subscription.evolutions_triggered` on a successful evolution.
The task's own `check_genetic_evolution` (`breach_tasks.py`), added in round
1 of this same PR, did *both* of those again right after a successful call
— two `GeneticEvolutionLog` rows and a double-incremented counter per
trigger.

Verified by reading both functions in full at their current line numbers
rather than trusting the bot's line references (which were from the diff,
not necessarily current HEAD):
- `epigenetic_service.py` `check_and_evolve`, lines 355–381: increments
  `subscription.evolutions_triggered` then creates a
  `GeneticEvolutionLog.objects.create(...)`, using field names
  `old_biological_age`/`new_biological_age`.
- `breach_tasks.py` `check_genetic_evolution`, lines 338–358 (pre-fix):
  creates its *own* `GeneticEvolutionLog.objects.create(...)` (behind a
  24h cache-based dedup key that does nothing to stop this *first* write
  from duplicating the manager's) and its own
  `subscription.evolutions_triggered` increment, using field names
  `biological_age_before`/`biological_age_after` — a genuinely separate
  write, not an accidental re-run of the same one.

Root cause of how this got in: this task-level logging code pre-dates round
1 of this PR. Before round 1's fix, the task called
`check_and_evolve(user)` (wrong arity) and read the result as a dict (wrong
type) — a call that could only ever raise, caught by the task's own blanket
`except Exception`, so this logging code had never actually executed in
production. Round 1 fixed the call shape, which made the `if evolved:`
branch reachable for the first time — and exposed the dormant duplicate
write that had been sitting there unreachable the whole time.

**Fix** (`security/tasks/breach_tasks.py`): removed the task's own
`GeneticEvolutionLog.objects.create(...)`, its dedup-cache guard, and the
`subscription.evolutions_triggered` increment/save. The task now only reads
back `new_generation`/`biological_age` off the `dna_connection` instance the
manager already mutated (as round 1 already did) and returns them in its
result dict — no persistence besides what `check_and_evolve` itself does.
`previous_age` (only used by the removed block) and the local
`GeneticEvolutionLog` import (also only used there) were dropped along with
it. `cache` stays imported at module level — used by an unrelated function
elsewhere in the same file (`process_forced_rotation`'s rotation-event
dedup). Persistence living solely in the manager also matches the API view
(`genetic_password_views.py`), which already calls `check_and_evolve`
directly and relies on the manager's own side effects with no task-layer
duplicate in front of it.

**Test** (`security/tests/test_genetic_password.py`,
`test_check_genetic_evolution_task`): CodeRabbit's own suggestion was to
"model the manager persistence and verify exactly one log is created and
the usage counter increments once" — implemented literally. The
`fake_check_and_evolve` mock side effect now also creates the
`GeneticEvolutionLog` row and increments `subscription.evolutions_triggered`
itself (mirroring what the real manager does), and the test asserts
`GeneticEvolutionLog.objects.filter(user=self.user).count() == 1` and
`subscription.evolutions_triggered == 1` after `refresh_from_db()` — a
regression guard against the double-write recurring.

### 9.2 Nitpick: unused `message` binding (CONFIRMED)

`security/tests/test_genetic_password.py`,
`EpigeneticEvolutionManagerSyncTestCase.test_check_and_evolve_runs_without_async_error`:
`evolved, message = epigenetic_evolution_manager.check_and_evolve(...)` —
`message` bound, never read (Ruff RUF059). Confirmed real by direct read;
only match for the pattern in the file (grepped for the unpacking call
site). Fixed by renaming to `_message` (CodeRabbit's own first suggested
option) rather than asserting on the exact message string, which would make
the test brittle against message-wording changes that aren't bugs.

### 9.3 Declined: docstring coverage warning

73.53% vs. an 80% threshold, flagged as a pre-merge check warning (not a
failure — the PR's actual CI checks are green: "1 neutral, 6 skipped, 27
successful"). Not a specific, locatable defect the way the two findings
above are; satisfying it would mean writing docstrings across an
unspecified set of functions this PR didn't necessarily touch. Left alone
per this round's explicit "keep changes minimal, surgical" instruction —
revisit only if asked to address it directly.

### 9.4 Test results (targeted, per this round's testing guidance)

Ran only the tests touching the changed code, not the full suite, per
explicit instruction to prefer targeted runs over routine full-suite runs:

- `pytest security/tests/test_genetic_password.py::GeneticEvolutionTaskTestCase security/tests/test_genetic_password.py::EpigeneticEvolutionManagerSyncTestCase -v`
  — 8 passed.
- Broader confirmation once the fix was stable, scoped to this PR's actual
  footprint (not the full repo suite):
  `pytest security/tests/test_genetic_password.py security/tests/test_celery_beat_registry.py -q`
  — 67 passed, 8 subtests passed, 0 failed. This round added no new test
  functions (both changes strengthened an existing test's assertions/target
  variable, not new coverage), so the count reflects rounds 1+2's additions,
  not this round's.

## 10. Review-fix round 2 on PR #482 (CodeRabbit, MD040)

One finding: two fenced blocks in this doc itself (§3.2, §3.3 — the
`FieldError` and `SynchronousOnlyOperation` error-text blocks) opened with
a bare ` ``` ` instead of a language tag, tripping markdownlint's MD040
(`fenced-code-language`). Verified before fixing: grepped every bare
` ^```$ ` line in the file and classified each as an opening or closing
fence by reading its surrounding context — exactly 2 were unlabeled
*openings* (lines 89, 126 at the time of the finding); every other bare
match was the legitimate closing fence of a block whose opener already
carried `python`/`bash`. No other unflagged instances existed to fix for
consistency. Tagged both `text` (they're plain error-message output, not
executable Python). Doc-only, zero code/behavior impact — no test run
needed for this round.

## 11. Review-fix round 3 on PR #482 (CodeRabbit, Major — non-forced evolution could never succeed)

CodeRabbit's claim: after the async→sync fix (round 1) made this branch of
`check_and_evolve` reachable, `dna_connection.last_biological_age` is read
as `current_bio_age` (line ~339) and then read *again* as `last_bio_age`
(line ~349) — the same field, unchanged in between — so `age_change` is
always `0`, and `not force and age_change < EVOLUTION_THRESHOLD` rejects
every `force=False` call. That's the daily scheduled task's actual, default
call shape (`check_genetic_evolution.delay(...)` never passes `force=True`)
— meaning automatic evolution could never succeed for any user, ever.

Verified by reading the method fresh rather than trusting the line numbers
in the finding: confirmed both reads target the identical
`dna_connection.last_biological_age` attribute with no write in between,
and confirmed via `git diff main` that round 1's fix never touched this
logic at all (only the `async def`→`def` signature and its docstring) — the
bug is genuinely pre-existing, not something introduced by this PR; round 1
just made it reachable, the same "fix exposes a dormant pre-existing bug"
shape as the double-write bug in round 1 itself.

**The fix required actually understanding the data model, not just moving
lines around**: `DNAConnection` has exactly one biological-age field
(`last_biological_age`) — there is no second field anywhere to hold a
genuinely distinct "prior" value, so no amount of reordering the two reads
inside `check_and_evolve` could produce a real delta; both reads would
still resolve to the one stored value. CodeRabbit's own suggested
remediation ("capture the prior measurement before assigning or updating
the current one") describes a live-refresh flow this codebase doesn't have
yet — the API integration is still a stub (`# This would normally fetch
from the API`).

Found a fix that needs no new field or migration: `GeneticEvolutionLog`
(the audit-log model this same method already writes to on every
successful evolution) has its own `new_biological_age` column, which is
*exactly* "biological age as of the last successful evolution" — the
correct baseline to diff against, already populated, already scoped to
`user` the same way this method's own log-creation call already is.
Changed `last_bio_age` to come from
`GeneticEvolutionLog.objects.filter(user=user, success=True).order_by('-completed_at').first()`
(falling back to `current_bio_age` — i.e. `age_change == 0`, matching the
old code's own fallback semantics — when a user has no prior evolution to
compare against). Consolidated the pre-existing `from ..models import
GeneticEvolutionLog` import to before this new query instead of duplicating
it at its original (later) call site.

**Regression tests added** (CodeRabbit asked for one; added a
complementary second to prove the fix is precise, not just "always true
now"): `test_non_forced_evolution_succeeds_with_above_threshold_change`
seeds a prior `GeneticEvolutionLog` 5.0y below the connection's current
`last_biological_age` and confirms a `force=False` call now evolves;
`test_non_forced_evolution_still_blocked_below_threshold` seeds a prior log
only 0.2y below (under the 0.5y `EVOLUTION_THRESHOLD`) and confirms the
call still correctly declines.

### 11.1 Test results (targeted, per instruction)

- `pytest "security/tests/test_genetic_password.py::EpigeneticEvolutionManagerSyncTestCase" -v`
  — 4 passed (2 pre-existing + 2 new).
- Broader confirmation once stable, this PR's actual footprint (not the
  full repo suite):
  `pytest security/tests/test_genetic_password.py security/tests/test_celery_beat_registry.py -q`
  — 69 passed (up from round 2's 67, by the 2 new tests), 8 subtests
  passed, 0 failed.

## 12. Review-fix round 4 on PR #482 (CodeRabbit ×2 + a recurring failing CI check)

Three items: one CodeRabbit follow-up on round 3's own fix, one CodeRabbit
finding on code round 2 already touched but hadn't fully safety-reviewed,
and the same `sqlparse` CVE already fixed on PR #483.

### 12.1 Major: round 3's fix still couldn't start evolution for a brand-new user

CodeRabbit's claim: "When no successful GeneticEvolutionLog exists, this
code compares current_bio_age to itself and returns without writing a
baseline. Later non-forced checks still have no log, so automatic
evolution cannot start until a caller forces one manually."

Verified by re-tracing round 3's own fallback line
(`last_bio_age = last_log.new_biological_age if last_log else current_bio_age`):
for a user with ZERO prior `GeneticEvolutionLog` rows, `last_bio_age` ==
`current_bio_age` always, `age_change` is always `0`, the threshold gate
returns `False` — and because that early return happens before any write,
the NEXT check (days later, weeks later, forever) has exactly the same
"zero rows" state and reaches exactly the same dead end. Confirmed accurate:
round 3's fix solved "the comparison always yields zero even with real
history" but not "there's no automatic way to ever CREATE that history" —
a real gap in round 3's own fix, not something round 3 introduced (the
pre-round-3 code's fallback — `dna_connection.last_biological_age or
current_bio_age` — had the identical "always equals current" property, so
this was already true before any of this PR's work; round 3 just preserved
the old fallback's own semantics faithfully rather than questioning them).

**Fix**: restructured so the threshold gate only applies when a prior log
genuinely exists; a user's first-ever check (no prior log) now skips the
gate entirely and falls through to the method's own existing
evolve-and-log code path below, which creates the first
`GeneticEvolutionLog` baseline row on its own — no new write path needed,
no schema change. That first row honestly records
`old_biological_age == new_biological_age` (no measured change yet, this
*is* the baseline), so it doesn't fabricate a delta that didn't happen.

Added the regression test CodeRabbit asked for
(`test_non_forced_evolution_seeds_baseline_for_new_user`: confirms a
`force=False` call on a connection with zero evolution history now
evolves and writes that first log row). Caught and removed a second,
slightly-misleading assertion of my own before it landed — my first draft
also asserted a SECOND call now declines "because it compares against the
baseline," but a second immediate call actually declines earlier, on the
unrelated `CHECK_INTERVAL_DAYS` gate (30 days must pass since
`last_epigenetic_update`), not the threshold gate my test claimed to be
proving. `test_non_forced_evolution_still_blocked_below_threshold` (round
3) already covers "declines against a real baseline" correctly with its
own explicit prior-log setup, so the redundant, inaccurate assertion was
dropped rather than fixed in place.

### 12.2 Major: `health_check_nodes` mutates real node status from simulated data, no config gate

CodeRabbit's claim: importing `dark_protocol_tasks` (round 2) registers
`health_check_nodes` and activates its existing beat entry
(`dark-protocol-health-check`, every minute). The task selects every
`status='active'` `DarkProtocolNode` with no `is_enabled`-style gate,
decides reachability via `random.random() > 0.05`, and marks a node
`status='inactive'` — a real, persistent mutation — after 3 simulated
failures within a rolling 5-minute window.

**This is a genuine gap in round 2's own safety review**, not a new bug —
re-read: round 2 verified "zero outbound network I/O" and "every query
gated on `is_enabled` / an active session existing" for all five Dark
Protocol tasks and called that sufficient for "safe to turn on." That
network-I/O claim was correct, but the OVERALL safety conclusion missed a
different, real problem this specific task has: it doesn't need real
network access to still take a REAL node offline based on nothing but
chance — the query it runs (`DarkProtocolNode.objects.filter(status='active')`)
has no `is_enabled` gate at all (that's a session/config concept;
`DarkProtocolNode` rows aren't scoped to any single user's opt-in). Run
every minute forever, a genuinely healthy node WILL eventually roll 3
unlucky 5%-chance failures inside some 5-minute window — it's a matter of
when, not if.

**Fix**: removed the `dark-protocol-health-check` beat entry from
`celery.py` rather than attempting either of CodeRabbit's two suggested
remediations in full:
- "Prevent it from being registered" — not cleanly achievable: `@shared_task`
  registers a name the moment its defining MODULE is imported, and
  `security/tasks/__init__.py` imports `dark_protocol_tasks` as a whole for
  its other 4 (safe) tasks — un-importing just `health_check_nodes`'s name
  from that tuple would not stop its decorator from executing, since the
  module still loads regardless. The only way to prevent registration
  outright would be to stop importing the whole module, which would also
  un-register the other four tasks that verified safe.
- "Add a strict configuration gate that prevents status mutation" — the
  task's body is a `random.random()` simulation stub throughout, not a
  real check with one bad line; inventing a new settings flag and gating
  logic inside `dark_protocol_tasks.py` (a file with no other changes in
  this PR) is a larger, more speculative change than removing one
  schedule entry, and touching unfamiliar simulation logic to make it
  "safely fake" risks exactly the kind of guess this PR's own instruction
  warns against.

Un-scheduling is the part that's actually achievable and actually
eliminates the harm: a registered-but-unscheduled Celery task simply never
runs on its own, and nothing else in the codebase calls
`health_check_nodes.delay()` (confirmed by grep) — beat is the only thing
that would have invoked it periodically. The function itself is untouched
and stays fully registered/callable (`test_dark_protocol.py`'s own
`test_health_check_task` still calls and passes against it directly),
available for manual invocation or once it gets a real implementation.

Corrected the overstated safety-claim comment in `celery.py` (it used to
say all five Dark Protocol tasks were uniformly gated/safe) and added a
matching clarifying note to `security/tasks/__init__.py`'s import block,
per CodeRabbit's request to "update the related task registration
accordingly" there too — since importing a name only makes it
*registered*, not *scheduled*, and that distinction is exactly what this
finding turned on.

Added `test_health_check_nodes_entry_stays_removed` (same "must not
silently reappear" pattern as `analyze-password-strength-daily`'s removal
in round 2 of the 8-broken-entries work), and updated
`test_dark_protocol_entries_resolve` to check the remaining four entries
instead of five.

### 12.3 Recurring: `sqlparse==0.5.4` CVEs (same fix as PR #483)

Identical finding to PR #483 round 4 — same 4 CVEs
(CVE-2026-71491/59894/59893/54284), same `fix_versions: ["0.6.0"]`, same
root cause (this branch, a separate branch off `main`, hadn't had the bump
applied yet). No new verification needed beyond confirming the failing job
log actually names `sqlparse` here too (it does — fetched via
`gh api .../actions/jobs/<id>/logs`, identical dependency list and CVE
payload). Bumped the same three files
(`requirements.txt`/`requirements-core.txt`/`requirements-lock.txt`) to
`0.6.0`, reusing the PR #483 verification (Django's own constraint
satisfied, no direct imports in this codebase, already confirmed safe
against the local test suite there).

### 12.4 Test results (targeted, per instruction)

- `pytest "security/tests/test_genetic_password.py::EpigeneticEvolutionManagerSyncTestCase" security/tests/test_celery_beat_registry.py -v`
  — 13 passed, 7 subtests passed.
- Broader confirmation once stable, this PR's actual footprint (now
  including Dark Protocol, since this round touched its scheduling):
  `pytest security/tests/test_genetic_password.py security/tests/test_celery_beat_registry.py security/tests/test_dark_protocol.py -q`
  — 102 passed, 3 warnings (pre-existing `datetime.utcnow()` deprecation
  noise, unrelated), 7 subtests passed, 0 failed.

## 13. Review-fix round 5 on PR #482 (CodeRabbit full review, 2 actionable findings)

CI was fully green (27 successful, 1 neutral Trivy config-not-found, 6
skipped deploy/build jobs unrelated to this branch) when this round
started — there was no failing check to chase. `@coderabbitai full review`
surfaced two inline findings instead. The Multi-Scanner Security Report
comment on the same PR is informational only (posts to the Security tab,
not a required check); the 262 open code-scanning alerts it feeds are a
pre-existing, repo-wide baseline (same `Django==5.1.15` on `main` and this
branch, oldest alerts dated 2026-08-08, well before this branch existed) —
out of scope for a surgical celery-beat fix and left untouched.

### 13.1 Major: `check_and_evolve` gate-checks and writes run unlocked (CONFIRMED)

CodeRabbit's claim: concurrent calls for the same user (the daily beat
task and a manual "trigger now" hitting the same connection) can both pass
the `CHECK_INTERVAL_DAYS`/threshold gates before either writes
`last_epigenetic_update`, both decide to evolve, and then last-writer-wins
on `dna_connection.save()`/`subscription.save()` — duplicating a
generation transition in `GeneticEvolutionLog` while silently losing one
of the two `evolutions_triggered` increments.

Verified by reading the method (`epigenetic_service.py`, then lines
294-424): confirmed no `transaction.atomic()`/`select_for_update()`
anywhere in the file, and no DB-level uniqueness constraint on
`DNAConnection.evolution_generation` or `GeneticEvolutionLog` that would
catch a duplicate transition (`models/core.py`). `select_for_update()` +
`transaction.atomic()` is an established pattern elsewhere in this app
(`adaptive_password_service.py`'s `apply_adaptation_v2`/`rollback_to_v2`),
so locking here is consistent with how this codebase already handles the
same class of race, not a new pattern. Both real callers
(`breach_tasks.check_genetic_evolution`, the trigger-evolution API view's
`get_dna_connection`/`get_or_create_subscription`) always pass an
already-persisted row, so locking by `pk` inside the method is safe — no
caller ever passes an unsaved instance.

**Fix**: wrapped the gate checks and all three writes
(`dna_connection.save()`, `subscription.save()`,
`GeneticEvolutionLog.objects.create()`) in one `transaction.atomic()`
block, re-fetching both `dna_connection` and `subscription` with
`select_for_update()` at the top of the block before evaluating any gate.
This serializes concurrent callers for the same user: whichever call runs
second blocks until the first commits, then re-reads the just-written
state and re-evaluates the gates against it — so it correctly declines
(interval/threshold gate) instead of double-evolving. Early-return paths
(no subscription, interval not elapsed, no biological age, below
threshold) still return before any write; exiting the `with` block via
`return` there just commits an empty transaction, which is harmless.
No schema change, no new migration.

### 13.2 Major: Dark Protocol beat schedule can outlive its task registration (CONFIRMED, scoped down)

CodeRabbit's claim: `celery.py`'s `beat_schedule` statically lists four
`dark_protocol.*` entries; if the guarded import in
`security/tasks/__init__.py` ever raises `ImportError`,
`DARK_PROTOCOL_TASKS_AVAILABLE` silently becomes `False` (a
`logger.warning` only) while those four entries keep firing into
`NotRegistered` on every tick, forever, with no loud signal.

Verified this is real but pre-existing and not unique to Dark Protocol:
the identical `try/import ImportError → AVAILABLE=False` shape also guards
`adaptive_tasks` and `time_lock_tasks` immediately above in the same file,
and `DARK_PROTOCOL_TASKS_AVAILABLE`/its two siblings are used nowhere
outside this file's own `__all__` construction — `celery.py`'s
`beat_schedule` dict is built at Celery app definition time in a
completely different module and has no way to read this flag even in
principle. CodeRabbit's two suggested remediations don't fit cleanly:
gating the beat entries on the flag would require `celery.py` to import
`security.tasks` (a much larger, riskier change touching Celery app
bootstrap for all three guarded feature areas, not just Dark Protocol);
re-raising the `ImportError` would crash Celery worker/beat startup
entirely on any transient issue in this or an unrelated guarded import,
trading a silent degrade for a total outage — worse for the two other
call sites this round didn't touch.

**Fix, scoped to exactly what the finding names** (the four Dark Protocol
beat entries, not the other two guarded blocks): mirrored the fail-loud
stub pattern this file already uses one block above for the
predictive-expiration re-export (`breach_tasks` import, lines ~43-88) —
on `ImportError`, register `@shared_task`-decorated stubs under the same
`dark_protocol.rotate_network_paths` / `dark_protocol.generate_cover_traffic`
/ `dark_protocol.cleanup_expired_sessions` / `dark_protocol.analyze_traffic_patterns`
names that raise `RuntimeError` when Beat actually invokes them, and
upgraded the log call from `.warning` to `.exception` for a full
traceback. `health_check_nodes` and `register_node` are deliberately not
given stubs — neither has a beat entry (`health_check_nodes` was
unscheduled in round 4 §12.2; `register_node` is called directly by
application code, not Beat), so there is no scheduled tick that would
otherwise resolve to `NotRegistered` for either. This branch is inert
under normal operation: the import already succeeds today (confirmed by
`test_dark_protocol_tasks_importable_from_security_tasks_package`), so
this is a safety net for a failure mode that isn't currently occurring,
not a behavior change to the success path.

### 13.3 Test results (targeted, per instruction)

- `pytest security/tests/test_genetic_password.py -q -k "EpigeneticEvolutionManagerSyncTestCase or EvolutionTrigger"`
  — 5 passed (the 4 existing `check_and_evolve` behavior tests plus the
  async→sync coroutine-check test; all still pass under the new lock —
  none of them exercise concurrent calls, so this is a no-regression check
  on the gate logic itself, not a new concurrency test).
- `pytest security/tests/test_dark_protocol.py security/tests/test_celery_beat_registry.py -q`
  — 39 passed, 3 warnings (pre-existing `datetime.utcnow()` deprecation
  noise, unrelated), 7 subtests passed. Confirms the four Dark Protocol
  beat entries still resolve to real registered tasks on the success path
  (the `except ImportError` branch added in §13.2 doesn't execute in this
  environment) and that `health_check_nodes` stays unscheduled per round 4.

## 14. Review-fix round 6 on PR #482 (CodeRabbit full review, 2 Major + 3 nitpicks)

Round 5's own fix (§13.1, locking `check_and_evolve`) introduced one of
this round's two Major findings — a genuine "fix introduces a new bug"
case, not a dormant pre-existing one, and worth naming plainly rather than
folding into the same vague "CodeRabbit, PR #482" comment style used
elsewhere. Verified all 5 findings against current code (not the bot's
pasted snippets — the `breach_tasks.py` finding's own comment thread
quoted a version of that file that does not match what's actually on this
branch, most likely a stale render of an old diff hunk; read the real
file directly instead of trusting the pasted code).

### 14.1 Major: `check_and_evolve` callers read stale connection state (CONFIRMED, round-5 regression)

CodeRabbit's claim: `select_for_update().get(pk=...)` (added in round 5)
returns a new Python object; rebinding the local `dna_connection`
parameter to it never touches the object the *caller* is holding, so
`check_genetic_evolution` (`breach_tasks.py`) and the trigger-evolution
API view (`genetic_password_views.py`) both report pre-evolution
`evolution_generation`/`last_biological_age` immediately after a call that
returned `evolved=True` and genuinely updated the database.

Verified by reading the real, current `breach_tasks.py` (not the bot's
pasted code block, which showed duplicate/conflicting keys — e.g. two
different `'old_generation':` entries in the same dict literal — that
don't exist in this file on this branch; almost certainly a stale diff
render, not this repo's actual content) and `genetic_password_views.py`:
confirmed `check_genetic_evolution` reads `dna_connection.evolution_generation`
right after the call expecting the mutation, and the trigger-evolution view
passes `connection` into `get_evolution_status(connection)` immediately
after, same expectation. Both genuinely broken by round 5's locking fix:
Python's object-reference semantics mean reassigning a parameter name
inside a function is invisible to the caller's own variable.

**Fix, centralized rather than CodeRabbit's 3-file spread**: rather than
adding a `refresh_from_db()` call at each of the two call sites (plus
updating the test's `fake_check_and_evolve` mock as CodeRabbit's own
prompt suggested), fixed it once at the source: captured the caller's
original instance as `caller_dna_connection` before the lock re-fetch
rebinds the local name, then called `caller_dna_connection.refresh_from_db()`
right after the successful-evolution writes commit (still inside the same
`transaction.atomic()` block, so it reads the just-written state via the
same connection/transaction — standard read-your-own-writes). Zero
changes needed to `breach_tasks.py`, `genetic_password_views.py`, or the
existing mock-based task test (`fake_check_and_evolve` already mutates the
passed-in instance directly, which is exactly what the real method now
also does) — a future third caller gets this correctness automatically
rather than needing to remember its own `refresh_from_db()`. Added
`test_check_and_evolve_updates_callers_own_instance`, deliberately NOT
calling `refresh_from_db()` first (every other test in this class does,
which is exactly what would have hidden this bug).

### 14.2 Major: baseline query can select a `success=True` row with null fields (CONFIRMED, defensive fix)

CodeRabbit's claim: `new_biological_age`/`completed_at` are both nullable
on `GeneticEvolutionLog` (`models/core.py`); a `success=True` row with
either null would make `abs(current_bio_age - last_bio_age)` raise
`TypeError` if selected as the baseline, and PostgreSQL/SQLite order NULLs
differently on `order_by('-completed_at')`, so which row counts as
"latest" would be backend-dependent.

Verified both nullable (`null=True, blank=True` on both fields) and that
the model enforces nothing preventing this combination —
`GeneticEvolutionLogModelTestCase.test_log_evolution_event`
(`test_genetic_password.py:629`) already creates exactly such a row
(`success=True`, via the legacy `biological_age_before`/
`biological_age_after` fields, `new_biological_age` and `completed_at`
both left unset) as a standalone model unit test. Confirmed the ONLY real
(non-test) call site that creates a `GeneticEvolutionLog` row
(`epigenetic_service.py`'s own `check_and_evolve`) always sets both
fields, so this isn't reachable through any current production path —
but the model doesn't prevent a future caller (a migration backfill, an
admin action, a different task) from creating one that hits it, and the
one-line filter costs nothing against today's well-formed rows.

**Fix**: added `new_biological_age__isnull=False, completed_at__isnull=False`
to the baseline query's filter, matching CodeRabbit's own suggested fix
verbatim. Added `test_non_forced_evolution_ignores_incomplete_log_rows`
(seeds an incomplete `success=True` log, confirms `check_and_evolve` no
longer has anything to crash on and falls through to the same
first-baseline path as a brand-new user).

### 14.3 Nitpick, applied: strengthen the Dark Protocol registration test

`test_dark_protocol_tasks_importable_from_security_tasks_package` only
asserted `hasattr(tasks_pkg, name)`. Round 5 (§13.2) added fallback stub
functions under the same names (`rotate_network_paths`, etc.) for the
`ImportError` branch — `hasattr` alone can't tell a real registered task
from one of those stubs by name collision alone. Applied CodeRabbit's
suggested strengthening: assert `task.name == f'dark_protocol.{name}'` too
(verified all 5 real tasks in `dark_protocol_tasks.py` carry that exact
explicit `name=` already, so this doesn't change what passes today). Note
for later: because round 5's stubs were deliberately named to match the
real tasks' Celery names exactly (so Beat sees a registered handler either
way), this strengthened assertion still can't distinguish "real task" from
"stub" by name alone — it proves the object is a genuine registered Celery
task (not just any importable symbol), which is what CodeRabbit actually
asked for; distinguishing real-vs-stub would need `DARK_PROTOCOL_TASKS_AVAILABLE`
directly, which the test already asserts on the line above.

### 14.4 Nitpick, declined: Ruff S106 "hardcoded password" on a test fixture

`User.objects.create_user(..., password='testpassword123!')` in
`EpigeneticEvolutionManagerSyncTestCase.setUp` — CodeRabbit's own
assessment labels this "Trivial | Low value" and states it's a false
positive (standard Django test setup, not a real credential). Verified
the identical literal appears 6 times in this one file alone and the same
`create_user(..., password=...)` pattern appears throughout the rest of
`security/tests/` — this is the codebase's pervasive, pre-existing test
convention, not something new to this PR, and the "Lint & Code Quality" CI
check has passed on every one of the last 5 rounds despite it. No `S106`
reference exists in any repo lint config (searched for a `pyproject.toml`/
`ruff.toml`/`.ruff.toml`; none define it), so there's no evidence the rule
is even enabled. Declined: CodeRabbit's own suggested remediation is
editing shared Ruff config to suppress a rule for the whole test path —
broader blast radius than a minimal fix justifies for a bot-labeled
trivial/low-value finding with no reproduction of an actual lint failure.

### 14.5 Nitpick, declined: trim review-history commentary from code comments

Asked to strip "CodeRabbit, PR #482 round N" / "the pre-round-3-fix code"
references from the comment blocks this PR's fixes have added, keeping
only the current invariant. Also self-labeled "Trivial | Low value" by
CodeRabbit. Declined: this is the established, deliberate documentation
convention across every round of this same PR (visible in every file this
PR has touched — `epigenetic_service.py`, `breach_tasks.py`,
`tasks/__init__.py`, `celery.py`, the test files), not an accident specific
to the two spots flagged; selectively stripping it from just these two
locations would make this PR internally inconsistent with its own
established style for no functional gain. Matches how round 1's
docstring-coverage nitpick was declined for the same class of reason
(non-actionable style preference, not a bug).

### 14.6 Test results (targeted, per instruction)

- `pytest security/tests/test_genetic_password.py -q -k "EpigeneticEvolutionManagerSyncTestCase or GeneticEvolutionLogModelTestCase or CheckGeneticEvolutionTask or check_genetic_evolution"`
  — 10 passed (the two new regression tests plus all pre-existing
  evolution-manager/task/model tests, confirming no regression from either
  fix).
- `pytest security/tests/test_dark_protocol.py -q -k "importable_from_security_tasks_package"`
  — 1 passed. Confirms the strengthened assertion still passes against the
  real, currently-importing Dark Protocol tasks.

## 15. Review-fix round 7 on PR #482 (CodeRabbit full review, 1 actionable + 2 nitpicks)

CI fully green at the time of review (25 successful, 1 neutral Trivy,
6 skipped deploy/build, the one "in progress" Backend Tests check shown in
the review comment had finished by the time this round started — verified
via `gh pr checks 482`, no failing check found). CodeRabbit's own comment
distinguishes "Actionable comments posted: 1" from a separate "Nitpick
comments (2)" section — treated that as the bot's own priority signal.

### 15.1 Minor, applied: `__all__.extend(...)` not alphabetically sorted (Ruff RUF022)

The only actionable finding, and the only one this round with actual tool
output attached (`ruff` itself: `[warning] 258-265: __all__ is not sorted
(RUF022)`), unlike prior rounds' bot-inferred claims — verified by reading
the flagged block directly rather than just trusting the label. Confirmed
real: the `if DARK_PROTOCOL_TASKS_AVAILABLE: __all__.extend([...])` block
in `security/tasks/__init__.py` (added earlier in this same PR, not
pre-existing on `main`) lists its six names in declaration order, not
alphabetical. Fixed exactly as suggested — reordered the six string
literals alphabetically. Zero behavior change (`__all__` order has no
runtime effect beyond `from module import *`).

Deliberately did NOT also reorder the near-identical, equally-unsorted
`if TIME_LOCK_TASKS_AVAILABLE: __all__.extend([...])` block immediately
above it (lines 245-255) — Ruff's own output named only lines 258-265, and
opportunistically fixing adjacent, unflagged code beyond what a review
actually asked for is exactly the kind of scope creep "keep changes
minimal" rules out, even when the same class of issue is visible a few
lines away.

### 15.2 Nitpick, declined (repeat of §14.5): condense review-history comments

Same finding as round 6 §14.5, same self-label ("Trivial | Low value"),
now pointed at four locations in `epigenetic_service.py` instead of two
(the `caller_dna_connection` comment added in round 6 itself among them).
Declined for the same reason as before: this is this PR's own established,
deliberate documentation convention across every file it touches, not
specific to the flagged spots, and stripping it selectively would make the
file internally inconsistent with its own precedent for no functional
gain. Not re-litigating further per round; see §14.5 for the full
reasoning.

### 15.3 Nitpick, skipped as already-correct: DNA token refresh tracking

`breach_tasks.py`'s `refresh_dna_tokens` (lines 511-574) — the comment
itself is descriptive rather than prescriptive ("No production consumer
reads these result keys, so no migration is required. The task still only
surveys connections and does not decrypt or refresh tokens."), with no
proposed diff attached, unlike every other finding across all 7 rounds.
Verified by reading the current function in full: it already does exactly
what the comment describes as correct — survey-only via `get_dna_provider`,
no decrypt, no outbound request, no writes, returns `implemented: False`
— this was the deliberate design from the original round-1 fix (§3.4 of
this doc, and `celery-beat-registry-fix.md` memory), not something this
round changed. Nothing to fix; noted rather than silently ignored.

### 15.4 Test results (targeted, per instruction)

- `pytest security/tests/test_dark_protocol.py security/tests/test_celery_beat_registry.py -q`
  — 39 passed, 3 warnings (pre-existing `datetime.utcnow()` deprecation
  noise, unrelated), 7 subtests passed. Confirms the `__all__` reorder
  doesn't change which names are importable from `security.tasks` or
  disturb Dark Protocol task registration/beat-entry resolution.
