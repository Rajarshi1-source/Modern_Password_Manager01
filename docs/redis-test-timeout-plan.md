# Implementation Plan — Eliminate Redis Connection Timeouts in Backend Tests

**Status:** Plan (verified). Code fix not yet applied — awaiting go-ahead.
**Scope:** `password_manager/` (Django backend). Test runner: `manage.py test` (Django), *not* pytest.
**Author note:** Every claim below was reproduced empirically in the `canny` venv on Windows; measured numbers are inline.

---

## TL;DR

Backend tests run minutes-slow because **Celery is not neutralised for tests**: the broker stays
`redis://localhost:6379/0`, so every `task.delay()` a test triggers blocks **~4.2s** on a broker
connect before `OperationalError` (Redis is absent in dev/CI). A `post_save` signal on `User` fires a
task on nearly every test, multiplying the cost. The Django **cache and channel layers are already
test-safe** — they are not the problem.

**Fix (minimal, two files):**
1. In `settings/base.py`'s `if TESTING:` block, point Celery at an in-memory broker (`memory://`).
2. In `ml_dark_web/signals.py`, short-circuit `_is_celery_available()` under `TESTING`.

**Verified effect:** a task dispatch drops from **~4.2s → ~0.12s**; no behavior change (tasks already
never executed in tests).

---

## Symptom

Observed during PR D: the full `vault` test module took **3409s (~57 min)** for 69 tests, while a
non-Redis subset (17 tests) ran in **6.5s**. The slowdown was attributed to "Redis connection retries
(~1s each), ~20s per affected test."

## Verified root cause

### What is already correct (do NOT touch)
`settings/base.py` has a `TESTING` block (`TESTING = 'test' in sys.argv or 'pytest' in sys.modules`,
line ~2286) that already forces:
- `CACHES['default']` and `CACHES['rate_limiting']` → `LocMemCache` (no Redis).
- `CHANNEL_LAYERS` → `InMemoryChannelLayer`.

So the Django cache is **not** the cause, and the suggested `IGNORE_EXCEPTIONS` / `SOCKET_TIMEOUT`
cache tweaks are unnecessary.

### Bug 1 — Celery is not neutralised for tests (dominant cost)
The `TESTING` block omits Celery. Measured in test mode (`TESTING=True`):

| Setting | Value |
|---|---|
| `CELERY_BROKER_URL` | `redis://localhost:6379/0` |
| `CELERY_TASK_ALWAYS_EAGER` | unset → `False` |
| `app.conf.task_always_eager` | `False` |

On this box a failed loopback connect **hangs for the full timeout** rather than fast-refusing, and
`localhost` costs ~2× because it tries IPv6 `::1` *and* IPv4 `127.0.0.1`:

```
redis ping socket_connect_timeout=1, 127.0.0.1  -> TimeoutError after 1.00s
redis ping socket_connect_timeout=1, localhost  -> TimeoutError after 2.09s
debug_task.delay() against down broker           -> OperationalError after 4.21s
```

So every `task.delay()` / `.apply_async()` a test triggers blocks **~4.2s**. "~20s per affected test"
≈ a handful of dispatches × ~4.2s.

### Bug 2 — Inverted DEBUG gate in `ml_dark_web/signals.py`
A `post_save` receiver on `User` (fires in essentially every test that creates a user) calls
`_is_celery_available()`:

```python
if not settings.DEBUG:
    return True          # DEBUG=False (Django test default) -> returns True WITHOUT checking
...
r = redis.Redis(host='localhost', port=6379, socket_connect_timeout=1); r.ping()  # DEBUG=True path
```

Measured:
```
_is_celery_available() DEBUG=False -> True in 0.000s   (=> .delay() fires -> ~4.2s broker hang)
_is_celery_available() DEBUG=True  -> False in 2.21s   (redis ping; result cached 60s)
```

So under the Django default (`DEBUG=False`) the signal queues `monitor_user_credentials.delay(...)`
and eats the broker hang; under `@override_settings(DEBUG=True)` tests (e.g. the PR D mirror) it pays
the ~2.2s redis ping instead.

---

## Decision: `memory://` broker (do NOT execute) vs. eager (execute inline)

Both eliminate the hang. The question is whether tasks should *run* during tests.

**Verified facts:**
- A single `.delay()`: redis broker **4.2s** → `memory://` **0.12s** (`executed_already=False`, i.e.
  enqueued but not run) → eager **0.07s** (runs inline, returns result).
- **No test relies on global eager:** zero `ALWAYS_EAGER` overrides exist anywhere in the repo. The
  only synchronous-task test (`ml_dark_web/tests/test_check_compromised_passwords.py:498`) uses
  `.apply()`, which runs inline **regardless** of broker/eager (verified 0.077s under `memory://`).
  `biometric_liveness/tests.py:47` **mocks** `monitor_user_credentials.delay`.
- Eager would execute heavy task bodies inline on every dispatch — `monitor_user_credentials` /
  `create_breach_alert` load ML breach classifiers and chain further `.delay()` calls
  (`ml_dark_web/tasks.py`).

**Conclusion → prefer `memory://`.** It removes the hang while preserving the current "tasks don't
run in tests" behavior exactly (lowest regression risk), and avoids dragging ML/blockchain task
bodies into every test. Eager offers no benefit here (nothing depends on it) and adds risk
(latent task-body errors surfacing, slower tests, especially with `EAGER_PROPAGATES`). Test classes
that specifically need a task to run can opt in locally with
`@override_settings(CELERY_TASK_ALWAYS_EAGER=True)` or call `.apply()`.

---

## The fix

### Change 1 — `password_manager/settings/base.py` (inside `if TESTING:`, ~line 2300)
```python
    # Celery: never touch the Redis broker during tests. Without this, every
    # task .delay()/.apply_async() blocks ~4.2s on a broker connect before
    # OperationalError (Redis is absent in dev/CI). 'memory://' enqueues
    # in-process and returns instantly; with no worker the task body does not
    # run — matching existing behaviour (tasks never executed in tests), but fast.
    # Tests that must run a task use .apply() or @override_settings(
    # CELERY_TASK_ALWAYS_EAGER=True) locally.
    CELERY_BROKER_URL = 'memory://'
    CELERY_RESULT_BACKEND = 'cache+memory://'
    CELERY_TASK_ALWAYS_EAGER = False
    CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = False
```

### Change 2 — `password_manager/ml_dark_web/signals.py` (`_is_celery_available`, first lines)
```python
def _is_celery_available():
    """Check if Celery/Redis is available before queueing tasks (cached 60s)."""
    if getattr(settings, 'TESTING', False):
        return False          # never probe Redis or queue monitoring during tests
    if not settings.DEBUG:
        return True
    ...
```
This kills both the ~2.2s redis ping (DEBUG=True path) and the redundant queueing in tests, and is a
**test-branch-only** change (no production behavior change).

### Change 3 (optional / defensive — apply ONLY if profiling still shows slowness)
Direct redis clients that bypass the cache can still hang if a test exercises them:
- `security/services/ocean_cache.py:71` — `redis.from_url(redis_url)` with **no** `socket_connect_timeout`.
- `fhe_service/services/fhe_cache.py:122` — `socket_connect_timeout=5`.

Add a short `socket_connect_timeout` (≈1s) and/or a `TESTING` guard **only** if their app tests are
still slow after Changes 1–2. Keep minimal.

---

## Verification (gate, in `canny`)

1. **Micro-benchmark (already proven):** `.delay()` 4.2s → 0.12s (`memory://`); `.apply()` still 0.077s.
2. **Targeted real-test timing:** `..\canny\Scripts\python.exe manage.py test ml_dark_web -v2`, then
   `manage.py test vault`. Expect per-test cost to drop from ~4–20s to sub-second (excluding DB setup).
3. **Full-suite wall-clock:** re-run the `vault` module that took 3409s; expect the ~seconds range the
   non-Redis subset showed.
4. **Regression sweep:** run `ml_dark_web`, `vault`, `biometric_liveness` and a broad sweep. Watch for
   any test that implicitly relied on `.delay()` raising/being caught (now it succeeds via `memory://`).

## Risks & mitigations
- **Low risk.** `memory://` preserves "tasks don't run in tests" while removing the hang; pure
  test-config change, trivially revertable.
- Change 2 only alters the `TESTING` branch of a signal → **zero production behavior change**.
- The regression sweep is the gate for any test that depended on the old enqueue-failure path.

## Sequencing
- **Single small PR** ("fix(tests): neutralise Celery/Redis in test settings"), Changes 1 + 2, on a
  fresh branch off `main`. Change 3 only if step 2/3 profiling demands it.
- Fully verifiable in `canny`; no frontend impact.

---

## Appendix — assessment of the original suggestions

| Suggestion | Verdict |
|---|---|
| Add `IGNORE_EXCEPTIONS`/`SOCKET_TIMEOUT` to **test cache** | Not needed — tests already use `LocMemCache`; prod cache already sets `SOCKET_TIMEOUT: 5`. |
| Separate test settings file w/ `LocMemCache` | Already effectively present via the `if TESTING:` block. |
| `conftest.py` cache fixture / `pytest.ini` `DJANGO_SETTINGS_MODULE` | Wrong layer — the suite runs via `manage.py test`, which does **not** load `conftest.py`. Fix must live in settings. |
| `pytest-mock` / mock `get_redis_connection` | Not needed — the only `get_redis_connection` use (`vault/tasks.py:196`) is in a task body that doesn't run in tests. |
| `fakeredis` | Overkill — `memory://` removes all task-path redis sockets. |
| **Celery eager + memory broker** | Correct lever, but in **settings** not `conftest.py`; and `memory://` (no eager) is preferred here (see Decision section). |
| `redis-cli ping` / start redis | Environmental, not a code fix — the goal is for tests to not require Redis. |
