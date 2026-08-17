# Plan — Fix the 3 broken genetic/DNA Celery beat task names

Branch: `fix/celery-beat-genetic-task-names` (off `main` @ `518b973`)

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
