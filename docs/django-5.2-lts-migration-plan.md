# Django 5.2 LTS migration plan

**Branch:** `chore/django-5.2-lts-migration-plan` (off `main` @ `7545e73f`)
**Author:** drafted 2026-09-14
**Current state:** Django **5.1.15** — end of life since **December 2025**, receiving no
security patches.
**Target:** Django **5.2.17 LTS** — extended support through **April 2028**.

---

## 0. Read this first: what the investigation actually found

This plan was written **after** reading the code, the installed packages and the CI
logs — not from the upgrade guides. Four claims that commonly circulate about this
upgrade were checked against primary sources and are **false for this codebase**.
They are recorded here because each one, if believed, would have added days of
pointless refactoring.

| Claim | Verdict | Evidence |
|---|---|---|
| "Django 5.2's latest patch is 5.2.15 / 5.2.16" | **False** — it is **5.2.17** | `djangoproject.com/download/` |
| "Django 6.x removes `unique_together`" | **False** — not removed in 6.0 or 6.1 | 6.0 + 6.1 release notes; neither mentions it |
| "Django 6.x removes `DEFAULT_FILE_STORAGE` / `STATICFILES_STORAGE`" | **False** for 6.0 | 6.0 release notes; also *this repo sets neither* |
| "`index_together` must be converted" | **N/A** — zero occurrences repo-wide | `grep -rn index_together --include=*.py` → 0 hits |

The `unique_together` correction alone removes a **23-model-file refactor** from the
scope. Those files stay exactly as they are.

### The real blocker is not Django

Dependabot has had this exact bump open since 2026-08-09 as
[PR #473](https://github.com/Rajarshi1-source/Modern_Password_Manager01/pull/473)
(`django 5.1.15 → 5.2.16`). It **fails CI**. The failing step is `Run migrations`,
and the tests never execute. The traceback is:

```
File ".../password_manager/password_manager/urls.py", line 19, in <module>
    from health_check.views import MainView as HealthCheckMainView
ImportError: cannot import name 'MainView' from 'health_check.views'
```

That has **nothing to do with Django 5.2**. It is `django-health-check` removing its
own public API:

- `requirements.txt:229` pins `django-health-check>=3.18.0` — **unbounded**
- the `canny` venv has **3.20.0**, whose `views.py` defines `class MainView`
- PyPI latest is **4.5.1**, whose `views.py` defines `class HealthCheckView` and
  **no `MainView`** — verified by reading the 4.5.1 source, not inferred
- `ci.yml:168` installs with `pip install --no-cache-dir -r requirements.txt`

So any fresh dependency resolution — a Django bump, a `pillow` bump, a cache miss —
pulls 4.5.1 and breaks `urls.py` on import. **`main` is one cache eviction away from
the same failure today.** `requirements.txt` carries **73** such unbounded `>=`
specifiers.

This is why the plan below starts at Phase 0 and does not touch Django until
Phase 2. Bumping Django first would simply inherit PR #473's red CI and invite the
conclusion that "Django 5.2 broke the build", which is not true.

---

## 1. Version decision: 5.2 LTS, not 6.1

| | Django 5.2.17 LTS | Django 6.1.1 |
|---|---|---|
| Support ends | **April 2028** | December 2027 |
| Python required | 3.10–3.14 | 3.12+ |
| PostgreSQL required | 14+ | **15+** |
| Steps from 5.1.15 | **one minor** | three (5.2 → 6.0 → 6.1) |
| `drf-yasg` support | **Yes** (1.21.15 declares 5.2) | **No** — no 6.0/6.1 classifier |

**Decision: 5.2.17 LTS.**

The deciding factor is `drf-yasg`, which serves this project's entire Swagger/ReDoc
surface from `password_manager/urls.py`. Its newest release (1.21.15) declares
Django 4.0–5.2 and stops there. Moving to 6.x would mean either dropping the API
documentation or running an unsupported combination — in a password manager, on the
public API surface. Nothing in 6.x is worth that.

Secondary reasons: 5.2 LTS is supported **four months longer** than 6.1 despite being
the older line; the upgrade is a single minor step with no intermediate hops; and
**Django 6.2 LTS lands April 2027** (supported to April 2030), which is the natural
next move once the ecosystem — drf-yasg included — has caught up.

This is not a permanent answer. It is the right answer until April 2027.

---

## 2. Migration surface in this codebase: near zero

Every backwards-incompatible change in the real 5.2 release notes was grepped for.
Results:

| 5.2 breaking change | Occurrences | Action |
|---|---|---|
| PostgreSQL 13 dropped (needs 14+) | CI + compose already on **pg15** | none |
| MySQL default charset → `utf8mb4` | MySQL not used (`postgresql`/`sqlite3` only) | none |
| Aggregates raise `TypeError` on bad arity | no misuse found | none |
| `UniqueConstraint.violation_error_code/message` now always applied | no usages set them | none |
| `EmailMultiAlternatives.alternatives` assignment | zero `.alternatives` usages | none |
| `gettext` 0.19+ required | CI runner + local both newer | none |
| `HttpRequest.accepted_types` ordering | not referenced | none |
| *(5.2 deprecation)* `staticfiles.finders.find(all=)` | zero usages | none |
| *(5.2 deprecation)* `RemoteUserMiddleware` | zero usages | none |
| *(5.2 deprecation)* `ArrayAgg/JSONBAgg/StringAgg(ordering=)` | zero usages | none |
| *(5.2 deprecation)* `auth.login()` with `user=None` | only `login(request, user)` | none |

Forward-looking (6.x) items, checked now so the next hop is cheap:

- `DEFAULT_AUTO_FIELD` — already explicitly `BigAutoField` (`settings/base.py:671`),
  so 6.0's default change is a no-op here.
- Custom `as_sql()` returning list params — **zero** `def as_sql` in the repo.
- Positional `Model.save()` args — **zero** `.save(True/False)` calls.
- `send_mail(connection=..., fail_silently=...)` together — no call site passes both.

**Baseline check, run in the `canny` venv against the current 5.1.15 install:**

```
System check identified no issues (0 silenced).
```

with **zero `RemovedInDjango*` warnings** under `-Wd`. The only deprecation warning
emitted comes from an unrelated third-party library. Per Django's own upgrade guide,
a clean deprecation baseline is the precondition for a minor upgrade — this codebase
already has it.

**Resolution probe (non-destructive, `pip install --dry-run` into `canny`, Python 3.13.3):**

```
Requirement already satisfied: sqlparse>=0.3.1 ... (0.6.0)
Requirement already satisfied: tzdata ... (2025.2)
Would install Django-5.2.17
```

Django 5.2.17 drops in with **no transitive churn at all**.

---

## 3. Phase 0 — stop the floating-dependency bleeding (prerequisite)

**Goal:** make dependency resolution reproducible, so that the Django bump is the only
variable in Phase 2. **This phase contains no Django change and is independently
mergeable.** It also fixes a latent break on `main`.

1. **Fix the `django-health-check` break.** Two options; take (a) unless the 4.x
   feature set is wanted:
   - (a) **Bound the pin**: `django-health-check>=3.18.0,<4` in `requirements.txt`
     and `requirements-core.txt`. Keeps `urls.py:19` valid, zero code change.
   - (b) **Adopt 4.x**: bump to `==4.5.1` and change `urls.py:19` to import
     `HealthCheckView` (4.5.1's replacement name) instead of `MainView`, updating the
     two `path()` registrations that use it. Larger blast radius on the health
     endpoints, and it is not what this migration is about.
2. **Bound every unbounded Django-ecosystem specifier** in `requirements.txt` /
   `requirements-core.txt`. There are 73 `>=` lines; the ones that can break an
   import at startup are the Django-adjacent ones — `channels`, `channels-redis`,
   `daphne`, `django-redis`, `django-prometheus`, `django-ratelimit`,
   `django-defender`, `django-health-check`, `django-silk`, `mozilla-django-oidc`,
   `whitenoise`, `gunicorn`. Give each an upper bound at the next major.
   The ML/scientific pins (`torch`, `tensorflow`, `transformers`, …) are out of scope
   here — they do not run at Django import time.
3. **Verify:** `pip install --dry-run -r requirements.txt` resolves, and
   `DEBUG=True python manage.py check` still reports no issues.

**Exit criterion:** a fresh resolve of `requirements.txt` cannot pull a major version
that removes an API `urls.py` imports.

---

## 4. Phase 1 — pre-flight on the current version

Run **before** changing Django, so any failure is attributable to today's code:

1. `DEBUG=True python manage.py check` → expect *no issues*
   (`DEBUG=True` is mandatory locally; without it every request 301-redirects).
2. `DEBUG=True python -Wd manage.py check` → expect no `RemovedInDjango*` lines.
3. `DEBUG=True python manage.py makemigrations --check --dry-run` → expect
   "No changes detected". **If this reports changes, stop** — an unrelated model drift
   is present and would be misread as migration fallout in Phase 3.
4. Record the current `pip freeze` as the rollback reference.

---

## 5. Phase 2 — the Django bump

**All six files pin `Django==5.1.15` and must move together.** A partial bump produces
a resolver conflict, which is its own class of confusing red CI:

| File | Consumed by |
|---|---|
| `password_manager/requirements.txt` | `ci.yml` Backend Tests; CI vulnerability scanners |
| `password_manager/requirements-core.txt` | `docker/backend/Dockerfile:220` (the image that ships; also installs `requirements-ml.txt`, which pins no Django) |
| `password_manager/requirements-prod.txt` | `password_manager/Dockerfile.prod` |
| `password_manager/requirements-constraints.txt` | `Dockerfile.prod` as `-c` — **can veto an upgrade** |
| `password_manager/requirements-lock.txt` | what Grype/Trivy actually scan |
| `password_manager/ml_dark_web/requirements-lock.txt` | dark-web scraper image |

Set `Django==5.2.17` in all six. Note `ml_dark_web/requirements-lock.txt` also pins
`djangorestframework==3.16.1` while the main tree is on `3.17.2` — align it to 3.17.2
in the same commit so the two trees stop diverging.

**Third-party co-bumps required for 5.2** (verified against PyPI classifiers):

| Package | Current | Target | Why |
|---|---|---|---|
| `django-cors-headers` | 4.0.0 | **4.9.0** | 4.0.0 predates 5.2 entirely |
| `django-celery-beat` | 2.8.0 | **2.9.0** | 2.9.0 is the release that declares 5.2 |
| `django-timezone-field` | 7.1 | **7.2.2** | 5.2 support |
| `drf-yasg` | 1.21.10 | **1.21.15** | newest with 5.2; also the 6.x ceiling |
| `django-storages` | 1.13.2 | **1.14.6** | 1.13.2 is from 2022 |
| `channels` | 4.2.2 | 4.3.2 *(optional)* | 5.2 declared; only if async tests stay green |

**Watch list — stale classifiers, must be proven by running, not by metadata.**
These declare no Django ≥5.x support but are widely used on newer Django; PyPI
classifiers are frequently just not updated. Do **not** pre-emptively replace them,
and do **not** trust them either — Phase 3 is what decides.

Phase 0 established *which of them the project actually loads*, which reorders the
risk substantially:

| Package | Classifier ceiling | Actually wired in? | Real risk |
|---|---|---|---|
| `django-push-notifications` | ≤ 4.0 | **Yes — `from push_notifications.models import APNSDevice, GCMDevice` at module scope in `auth_module/models.py:4`** | **Highest.** A model-scope import gates *app loading*: if it breaks, `manage.py check` fails outright. |
| `django-ipware` | none | **Yes — `from ipware import get_client_ip` in 4 `security/` modules** | Real, but call-site local. |
| `django-defender` | ≤ 4.1 | **No** — absent from `INSTALLED_APPS`, `MIDDLEWARE` and every import | Install-time only. |
| `django-ratelimit` | none | **No** — zero imports repo-wide | Install-time only. |

`whitenoise` and `django-silk` are likewise installed but **entirely unwired** (no
imports, no settings entries). They were bounded in Phase 0 for consistency, but they
cannot break startup.

---

## 6. Phase 3 — verification, targeted first

Per the standing testing preference: **targeted suites while iterating, the full suite
once, at the end.** The full backend suite takes 13–25 minutes; running it after every
edit is wasted time.

**Step 1 — import and config integrity** (catches the whole `urls.py`/app-registry
class of failure in seconds):

```bash
DEBUG=True python manage.py check
DEBUG=True python manage.py makemigrations --check --dry-run
```

**Step 2 — targeted app suites**, in dependency order. Run only these while fixing:

```bash
DEBUG=True pytest vault/ -q
DEBUG=True pytest auth_module/ -q
DEBUG=True pytest security/ -q
DEBUG=True pytest api/ hidden_vault/ -q
```

These cover the crypto/vault core, the auth surface that uses `login()` and
`send_mail()`, and — per the corrected table in §5 — the two watch-list packages the
project genuinely loads: `django-push-notifications` (via `auth_module/models.py`) and
`django-ipware` (via `security/`).

**Step 3 — the packages metadata could not vouch for.** Exercise them deliberately
rather than assuming a green suite touched them:

- **`django-push-notifications`** — `manage.py check` already proves it, because
  `auth_module/models.py:4` imports `APNSDevice`/`GCMDevice` at module scope; a break
  here fails app loading, not a test.
- **`django-ipware`** — hit an endpoint routed through
  `security/services/security_service.py` or `account_protection.py` and confirm
  `get_client_ip` still returns a resolved address.
- **`django-health-check`** — request `/health/`, which exercises the `MainView`
  import in `urls.py:19`.
- `django-defender` and `django-ratelimit` need **no runtime exercise** — they are not
  imported anywhere. An install-time resolve is the whole test.

**Step 4 — full backend suite, once, when the targeted runs are clean:**

```bash
DEBUG=True pytest -q
```

**Step 5 — frontend:** no change expected. The React app talks to the backend over
HTTP and has no Django coupling. Run `npx vitest run` once as a regression control,
not because the migration touches it.

---

## 7. Phase 4 — container verification (Docker Desktop)

The local venv proves the code; the images prove what ships. Two images install from
*different* requirements files, so both must be built:

```bash
docker build -f docker/backend/Dockerfile -t pm-backend:django52 .    # uses requirements-core.txt
docker compose up -d postgres redis
docker compose run --rm backend python manage.py check
docker compose run --rm backend python manage.py migrate --noinput
```

`docker-compose.yml` already provisions **postgres:15-alpine**, which satisfies 5.2's
PostgreSQL 14+ floor — no database upgrade is needed for this migration.

**`password_manager/Dockerfile.prod` is deliberately out of scope.** No CI job builds
it; its builder stage is `python:3.11-slim-bookworm` and its runtime is
`gcr.io/distroless/python3-debian12:nonroot` (also 3.11), making it the documented
exception to the project's 3.12 floor.
Bump the `Django==` line in `requirements-prod.txt`/`requirements-constraints.txt` for
consistency, but do not attempt to validate that image here — that is its own change.

---

## 8. Phase 5 — documentation and CI

1. `SECURITY.md` and the deployment guides state a supported-version matrix — update
   the Django row to 5.2 LTS with the April 2028 date.
2. CI Python stays at **3.12** and local stays at **3.13.3**; both are inside 5.2's
   3.10–3.14 window. No workflow change is required. Do not raise the CI Python
   floor as part of this migration — that is an unrelated change with its own blast
   radius.
3. Close Dependabot PR #473 with a pointer to this branch, noting its red CI was the
   `django-health-check` floating pin (Phase 0), not Django.

---

## 9. Explicitly not doing

| Item | Why not |
|---|---|
| Django 6.0 / 6.1 | `drf-yasg` has no 6.x support; 6.1 support ends *earlier* than 5.2 LTS. Revisit at 6.2 LTS (April 2027). |
| Converting 23 files off `unique_together` | Not deprecated, not removed, in 5.2 **or** 6.1. Verified against both release notes. |
| `STORAGES` dict migration | The repo sets neither `DEFAULT_FILE_STORAGE` nor `STATICFILES_STORAGE`. Nothing to migrate. |
| Frontend React 18 → 19, Vite/TS bumps | **Not required by this migration.** The frontend is already current (Vite 7.3, Vitest 4.0, TS 6.0, ESLint 9) and has zero Django coupling. The open frontend CVEs (`axios`, `react-router`, `fflate`, `js-yaml`, `dompurify`) are real but belong to a separate security-bump PR — bundling them here would make a Django regression indistinguishable from a React one. |
| Raising the CI Python floor | 3.12 already satisfies 5.2. Unrelated change. |
| `Dockerfile.prod` validation | Built by no CI job; documented 3.11/3.12 exception. |

---

## 10. Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| A floating `>=` dep resolves to a breaking major mid-migration | **High** — already happened (PR #473) | Phase 0 bounds them before Django moves |
| `django-push-notifications` genuinely broken on 5.2 | Low–Medium | It is imported at model scope, so `manage.py check` catches it immediately (Phase 3 Step 1), before any test runs |
| `django-ipware` genuinely broken on 5.2 | Low | Phase 3 Step 3 exercises `get_client_ip` at a real call site |
| `django-defender` / `django-ratelimit` broken | **Negligible** | Verified unimported and unwired — they cannot affect runtime |
| Migration state drift surfaces during `migrate` | Low | Phase 1 Step 3 proves `makemigrations --check` is clean *before* the bump |
| Shipped image differs from tested venv | Medium | Phase 4 builds `docker/backend/Dockerfile` from `requirements-core.txt` |
| A partial six-file bump causes resolver conflicts | Medium | Phase 2 changes all six in one commit |

## 11. Rollback

Every phase is a separate commit on `chore/django-5.2-lts-migration-plan`:

1. Phase 0 (dependency bounds) — independently valuable; keep even if Django is reverted.
2. Phase 2 (Django + co-bumps) — `git revert` restores 5.1.15 across all six files.

Since Phase 0 is mergeable on its own, a failure in Phase 3 does not strand the
repository: the floating-pin fix lands regardless, and `main` is left strictly safer
than it is today.

---

## 12. Sequencing summary

| Phase | Content | Gate to proceed |
|---|---|---|
| 0 | Bound floating deps; fix `django-health-check` — **DONE, see §13** | fresh resolve + `manage.py check` clean |
| 1 | Pre-flight on 5.1.15 | no issues, no `RemovedInDjango*`, no migration drift |
| 2 | `Django==5.2.17` in six files + co-bumps | `pip install` resolves in `canny` |
| 3 | Targeted suites → watch-list → full suite | all green |
| 4 | Docker build + migrate | container `check`/`migrate` clean |
| 5 | Docs, CI notes, close PR #473 | — |

---

## 13. Phase 0 — execution record (2026-09-14, complete)

**Scope taken:** option (a) — bound the pins. `urls.py` is untouched, so the health
endpoints keep their current behaviour.

**Change:** 24 lines, 12 packages × 2 files (`requirements.txt`,
`requirements-core.txt`). Nothing else in either file was modified.

| Package | Before | After | Locked | Resolves to |
|---|---|---|---|---|
| `django-health-check` | `>=3.18.0` | `>=3.18.0,<4` | 3.20.0 | **3.24.0** |
| `django-prometheus` | `>=2.3.1` | `>=2.3.1,<3` | — | 2.5.0 |
| `django-redis` | `>=5.4.0` | `>=5.4.0,<7` | 6.0.0 | 6.0.0 |
| `mozilla-django-oidc` | `>=4.0.0` | `>=4.0.0,<5` | 4.0.1 | 4.0.1 |
| `gunicorn` | `>=21.2.0` | `>=21.2.0,<24` | 23.0.0 | 23.0.0 |
| `channels` | `>=4.0.0` | `>=4.0.0,<5` | 4.2.2 | 4.3.2 |
| `channels-redis` | `>=4.3.0` | `>=4.3.0,<5` | — | 4.3.0 |
| `daphne` | `>=4.0.0` | `>=4.0.0,<5` | 4.2.1 | 4.2.3 |
| `django-silk` | `>=5.0.4` | `>=5.0.4,<6` | 5.4.3 | 5.6.0 |
| `whitenoise` | `>=6.6.0` | `>=6.6.0,<7` | 6.11.0 | 6.12.0 |
| `django-ratelimit` | `>=4.1.0` | `>=4.1.0,<5` | 4.1.0 | 4.1.0 |
| `django-defender` | `>=0.9.7` | `>=0.9.7,<1.0` | 0.9.8 | 0.9.8 |

**The `<4` boundary on `django-health-check` is exact, not approximate.** Reading
`health_check/views.py` at four upstream tags:

| Version | `MainView` | `HealthCheckView` |
|---|---|---|
| 3.20.0 | yes | no |
| 3.22.0 | yes | yes |
| 3.24.0 | **yes** | yes |
| 4.0.0 | **no** | yes |

The 3.x line carried `MainView` the whole way and added the new name alongside it;
**4.0.0 is precisely where it was removed**. `<4` is therefore the correct cut — it is
neither a version too tight nor too loose, and 3.24.0 satisfies `urls.py:19`.

### Verification performed

| Check | Result |
|---|---|
| All requirement lines parse (`packaging.Requirement`) | **146 / 120 lines OK, 0 invalid** |
| Duplicate or conflicting specifiers for the 12 packages | **none**; 0 duplicate package lines in either file |
| Targeted resolve of the 12 bounds (local, Python 3.13.3) | all 12 resolve as tabled above |
| **Targeted resolve on CI's platform** (`python:3.12-slim-bookworm`, Linux, Docker 29.7.2) | identical: `django-health-check 3.24.0`, `Django 5.2.17`, `django-redis 6.0.0`, `gunicorn 23.0.0`, `mozilla-django-oidc 4.0.1`, `channels 4.3.2`, `daphne 4.2.3` |
| `DEBUG=True manage.py check` | **System check identified no issues (0 silenced)** |
| `DEBUG=True manage.py makemigrations --check --dry-run` | **No changes detected** (Phase 1 Step 3 baseline, banked early) |

The cross-platform check matters because pip resolution is Python-version sensitive:
the bounds were authored against 3.13.3 locally but must hold on CI's 3.12. They do,
identically.

### Deviation from the plan as written

**The full `pip install --dry-run -r requirements.txt` could not be run on this
machine**, and this is an environment limit, not a finding. It fails during metadata
generation for **`scipy`**, which has no matching wheel for this interpreter and falls
back to a meson source build without the required toolchain:

```
error: metadata-generation-failed
note: This is an issue with the package mentioned above, not pip.   # scipy
```

No line changed in Phase 0 touches `scipy` or any scientific package. The substituted
evidence above — per-line parse, conflict scan, and a platform-accurate resolve of
every changed specifier on CI's own Python — covers the actual risk. A genuine
full-file install on Linux happens in **Phase 4**, where
`docker/backend/Dockerfile` installs `requirements-core.txt` for real.

### Scope decision: `requirements-prod.txt` deliberately left alone

`requirements-prod.txt` also carries unbounded `gunicorn>=21.2.0` and
`whitenoise>=6.6.0`. Sweeping them in was considered and **rejected on evidence**:
neither is wired into the project (`grep -rni whitenoise --include=*.py` → **zero
hits**; `gunicorn` is a process runner named in `CMD`, never imported), and
`Dockerfile.prod` is built by no CI job. The two packages that *can* break Django
startup — `django-health-check` (in `INSTALLED_APPS`, and `MainView` imported by
`urls.py`) and `django_prometheus` (in `INSTALLED_APPS` **and** `MIDDLEWARE` twice) —
are both bounded, in both files CI and the shipping image actually read.

### Correction to this document, made during Phase 0

§5's watch list originally asserted that `django-defender`, `django-ipware` and
`django-ratelimit` "all sit in the request path". Grepping each symbol showed that is
**false for two of them**: `django-defender` and `django-ratelimit` have zero imports
and zero settings entries. The table in §5 and Step 3 in §6 were rewritten against
what the code actually loads, which promotes `django-push-notifications` to the top
risk (model-scope import → gates app loading) and demotes the other two to
install-time-only.

### Gate status

Phase 0 exit criterion — *"a fresh resolve of `requirements.txt` cannot pull a major
version that removes an API `urls.py` imports"* — **met**, and verified on CI's
platform. Phase 1's pre-flight is also already green. **Cleared to start Phase 2.**

---

## 14. Phase 2 — execution record (2026-09-14)

**All six `Django==5.1.15` pins moved to `Django==5.2.17` in one commit**, plus the
co-bumps and the `ml_dark_web` DRF alignment. Total diff: **31 lines across 6 files**,
every one a version bump — no code, no settings, no migrations.

| Package | From | To | Files touched |
|---|---|---|---|
| `Django` | 5.1.15 | **5.2.17** | **6** (all) |
| `django-celery-beat` | 2.8.0 | 2.9.0 | 5 |
| `django-cors-headers` | 4.0.0 | 4.9.0 | 4 |
| `django-storages` | 1.13.2 | 1.14.6 | 4 |
| `django-timezone-field` | 7.1 | 7.2.2 | 4 |
| `drf-yasg` | 1.21.10 | 1.21.15 | 4 |
| `channels` | 4.2.2 | 4.3.2 | 3 (the `==`-pinned files; the other two carry `>=4.0.0,<5`) |
| `djangorestframework` | 3.16.1 | 3.17.2 | 1 (`ml_dark_web/requirements-lock.txt` only — aligning it to the main tree) |

`grep -rn "5\.1\.15"` across every requirements file now returns **nothing**.

### The lock file needed no transitive edits

`Django==5.2.17` declares only `asgiref>=3.8.1`, `sqlparse>=0.3.1` and `tzdata`
(win32). The lock already carries `asgiref==3.9.1`, `sqlparse==0.6.0`,
`tzdata==2025.2`. Every co-bump's runtime deps were likewise checked against the lock
and all were present and satisfied: `packaging 25.0`, `pytz 2025.2`,
`uritemplate 4.1.1`, `inflection 0.5.1`, `PyYAML 6.0.2`, `python-crontab 3.3.0`,
`cron-descriptor 1.4.5`, `celery 5.6.3`.

`requirements-constraints.txt` — the `-c` file that can veto `Dockerfile.prod`'s
install — was re-checked against both `requirements-prod.txt` and
`requirements-core.txt`: **zero conflicting pins** in either direction.

### Corrected rationale: only 3 of the 6 co-bumps are load-bearing

Phase 0's "check the wiring before believing the risk" lesson was applied again here,
and it reclassifies most of this table:

| Co-bump | Wired into Django? | Why it was bumped |
|---|---|---|
| `django-cors-headers` | **Yes** — `INSTALLED_APPS:188` **and** `MIDDLEWARE:259` | **Required.** 4.0.0 predates 5.2 entirely. |
| `drf-yasg` | **Yes** — `INSTALLED_APPS:194`, schema view in `urls.py:31` | **Required.** 1.21.15 is the newest declaring 5.2. |
| `channels` | **Yes** — `INSTALLED_APPS:197`, `ASGI_APPLICATION`, `CHANNEL_LAYERS`, consumers across 5+ apps | Real: 4.2.2 declares 5.1 but not 5.2; 4.3.2 declares 5.2. |
| `django-celery-beat` | **No** — beat schedules are plain `CELERY_BEAT_SCHEDULE` dicts in `celery.py`; the DB scheduler is unused | Hygiene only. |
| `django-timezone-field` | **No** — zero imports | Hygiene only (it is `django-celery-beat`'s dependency). |
| `django-storages` | **No** — zero imports, zero settings references | Hygiene only. **Its latest release still declares no 5.2 classifier, and that is irrelevant precisely because nothing imports it.** |

Worth recording for the *next* hop: `django-celery-beat==2.9.0` requires
`Django<6.1` and `django-timezone-field==7.2.2` requires `Django<6.2`. Both are
independent corroboration of §1's decision — even setting `drf-yasg` aside, the
current dependency set cannot reach 6.1 today.

---

## 15. Phases 3–5 — verification record (2026-09-14)

### Phase 3 Step 1 — import and config integrity (on Django 5.2.17)

| Check | Result |
|---|---|
| `DEBUG=True manage.py check` | **System check identified no issues (0 silenced)** |
| `DEBUG=True manage.py makemigrations --check --dry-run` | **No changes detected** |
| `-Wd` scan for `RemovedInDjango*` / Django deprecations | **zero** |

`manage.py check` passing is a stronger result than it looks: it loads all 60+
INSTALLED_APPS, which means it also clears the §5 watch list's highest risk —
`auth_module/models.py:4` imports `APNSDevice`/`GCMDevice` at module scope, so a
`django-push-notifications` incompatibility would fail here before any test ran.

No migration drift means **no new migrations were generated by the upgrade** — the
model layer is byte-for-byte unaffected.

### Phase 3 Step 3 — watch-list packages exercised directly

Run inside a configured Django 5.2.17 process rather than inferred from a green suite:

| Package | Exercise | Result |
|---|---|---|
| `django-ipware` | `get_client_ip(RequestFactory().get('/', REMOTE_ADDR=...))` | returns `203.0.113.7` |
| `django-health-check` | `from health_check.views import MainView` | imports (3.20.0 locally, 3.24.0 on a fresh resolve) |
| `django-push-notifications` | `from push_notifications.models import APNSDevice, GCMDevice` | imports |
| `drf-yasg` | version + `urls.py` schema view construction | 1.21.15 |
| `django-cors-headers` | `from corsheaders.middleware import CorsMiddleware` | imports |
| `channels` | `get_channel_layer()` | 4.3.2, `InMemoryChannelLayer` |

### Phase 3 Steps 2 & 4 — test suites

| Suite | Result |
|---|---|
| `auth_module/ hidden_vault/ password_manager/` | **227 passed, 19 subtests passed, 1 failed** (5m01s) |
| `security/` (38 test files) | **1234 passed, 7 skipped, 63 subtests passed, 0 failed** (10m34s) |
| Frontend `vitest run` (regression control) | **79 files, 920 tests, all passed** |

**The single failure is pre-existing and environmental, and that was proven rather
than assumed.** `auth_module/tests/test_security.py::TestSQLInjectionPrevention::
test_sql_injection_in_email_field` executes:

```sql
SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'
```

`information_schema` is a PostgreSQL/MySQL construct; the local run uses SQLite
(`_USE_POSTGRES = bool(os.environ.get('DB_NAME'))`, `settings/base.py:360`), which has
no such table. The test carries no backend guard. To rule out a regression the venv was
**downgraded to Django 5.1.15 and the same test re-run: it failed identically**, then
the venv was restored to 5.2.17. CI runs PostgreSQL 15, where this test passes — it is
green on `main` today for exactly that reason.

The 977 warnings in the `security/` run are `datetime.datetime.utcnow()` deprecations —
a *Python* deprecation in first-party code, pre-existing and unrelated to Django.

### Phase 4 — container and database verification

Docker Desktop 29.7.2, Linux containers.

**Install** — `requirements-core.txt` is what `docker/backend/Dockerfile:220` installs
into the image that actually ships. Installed for real (not a dry run) on
`python:3.12-slim-bookworm`, CI's platform:

```
pip exit=0
Django                       5.2.17
djangorestframework          3.17.2
channels                     4.3.2
daphne                       4.2.3
django-cors-headers          4.9.0
drf-yasg                     1.21.15
django-health-check          3.24.0      <- Phase 0's bound holding; not 4.x
django-celery-beat           2.9.0
django-timezone-field        7.2.2
django-storages              1.14.6
asgiref                      3.9.1       <- matches requirements-lock.txt exactly
django-prometheus            2.5.0
```

**Migrations** — `pgvector/pgvector:pg15` (the same image CI uses), running the exact
command `ci.yml:221` runs, `python manage.py migrate --noinput`:

| Metric | Result |
|---|---|
| Errors / tracebacks | **0** |
| Migrations recorded in `django_migrations` | **199** |
| Tables created in `public` | **324** |

This is the step that fails on Dependabot PR #473, and it has **no
`continue-on-error`** in `ci.yml` — it is a hard gate. It now completes cleanly.

### Phase 5 — documentation

- `README.md`'s two technology tables claimed **Django 4.2.27** — stale even before this
  migration, since the project was on 5.1.15. Both now read 5.2.17; DRF and Channels
  corrected alongside.
- `settings/base.py` carried **8** `docs.djangoproject.com/en/5.1.15/` comment links from
  the original `startproject` template; all now point at `/en/5.2/`. `manage.py check`
  was re-run after the edit and still reports no issues.
- `SECURITY.md` states no Django version number (only "Django Backend | ✅ Supported"),
  so it needed no change.
- Other plan documents mention `5.1.15` and are **deliberately untouched**: they are
  historical review records describing what was true when written, not forward-looking
  version statements. Rewriting them would falsify the record.
- CI Python stays at **3.12** and local at **3.13.3**; both sit inside 5.2's 3.10–3.14
  window, so no workflow change was required — and raising the CI floor remains an
  unrelated change with its own blast radius.

### Commits

| Commit | Content |
|---|---|
| `62bcd927` | the plan |
| `21add40a` | **Phase 0** — bound 12 floating Django-adjacent pins |
| `0f42a892` | Phase 0 record + watch-list correction |
| `a69d1233` | **Phase 2** — Django 5.2.17 across six files + co-bumps |
| `ed52949d` | **Phase 5** — version matrix and settings doc links |

Phase 0 remains separable: `21add40a` stands on its own and leaves `main` strictly
safer regardless of what happens to the Django bump.

---

## 16. PostgreSQL 15 → 17, and making PostgreSQL actually production-ready

### 16.1 The verdict on the version question: not necessary, but justified

**Upgrading 15 → 17 is NOT strictly required.** Django 5.2 supports PostgreSQL 14+,
and this codebase's version-sensitive surface is close to nil:

| Surface | Finding |
|---|---|
| PostGIS / `django.contrib.gis` | **Not used.** `'django.contrib.gis'` is commented out in `INSTALLED_APPS:182`. The only GIS import is `django.contrib.gis.geoip2.GeoIP2`, MaxMind's **file-based MMDB reader**, which needs no spatial database. |
| `django.contrib.postgres` | **Zero usages** repo-wide — no `ArrayField`, no `SearchVector`, no trigram. |
| Raw SQL | **9** `cursor.execute(` calls outside migrations, and **zero** touching `pg_catalog`, `pg_stat`, `information_schema` or `current_setting`. |
| pgvector | Used by `ml_dark_web`, but its migration guards on `connection.vendor` and swallows failures by design. |
| JSONB | 260 `models.JSONField` — stable across 15/16/17. |
| GIN | One index, `vault/migrations/0014`, `CREATE INDEX CONCURRENTLY ... USING gin (tags)`. |

**But the dates argue for doing it now.** Authoritative EOLs from
postgresql.org/support/versioning:

| | EOL |
|---|---|
| PostgreSQL 15 | **2027-11-11** |
| PostgreSQL 17 | 2029-11-08 |
| Django 5.2 LTS | 2028-04 |

**PostgreSQL 15 expires *before* the Django version this PR commits to.** A database
upgrade is therefore already scheduled inside Django 5.2's supported life. Doing it
now — with a verified harness — beats doing it under time pressure in 2027.

### 16.2 Empirical result: PG15 and PG17 produce an identical schema

Both run against `pgvector/pgvector` images, using the exact command `ci.yml:221` runs
(`python manage.py migrate --noinput`):

| | PostgreSQL 15.19 | PostgreSQL 17.11 |
|---|---|---|
| Errors / tracebacks | 0 | **0** |
| Migrations recorded | 199 | **199** |
| Tables in `public` | 324 | **324** |
| `idx_eitem_tags_gin` (CONCURRENTLY) | created | **created** |
| `vector` extension | present | **present (0.8.6)** |

### 16.3 The much bigger finding: compose and Kubernetes were never using PostgreSQL at all

Scanning the database configuration for the version question surfaced something
considerably more serious. Three surfaces spelled the database environment
differently, and settings read only one of them:

| Surface | Provides | `settings/base.py` read | Result |
|---|---|---|---|
| CI workflows | `DB_NAME`, `DB_USER`, … | `DB_NAME` | **PostgreSQL** |
| `docker-compose.yml` | `DATABASE_URL` only | never parsed | **SQLite** |
| `k8s` `app-config` | `DATABASE_NAME`, `DATABASE_HOST`, … | never read | **SQLite** |

`_USE_POSTGRES = bool(os.environ.get('DB_NAME'))` — and `DB_NAME` is never an
environment variable in either the compose containers or the k8s pods. In compose it
appears only as `POSTGRES_DB:` (which configures the *Postgres* container) and
interpolated into the `DATABASE_URL` *string*; k8s sets `DATABASE_NAME`.

**Proven rather than inferred.** With compose's exact environment:

```
DATABASE_URL set : True
DB_NAME set      : None
ENGINE Django uses: django.db.backends.sqlite3
NAME              : .../password_manager/db.sqlite3
```

So every Django service in `docker-compose.yml` — and the Kubernetes Deployment **and
its migrate-Job** — ran on SQLite while a healthy, health-checked PostgreSQL sat beside
them unused. In Kubernetes that SQLite file lives on the pod's ephemeral filesystem, so
the vault would not survive a pod restart. **Only CI was ever exercising PostgreSQL**,
which is precisely why this never showed up as a test failure.

**Fix:** `settings/base.py` resolves all three spellings, `DB_*` **first** so CI is
bit-for-bit unchanged, with `DATABASE_URL` percent-decoded. A non-`postgres://`
`DATABASE_URL` is ignored rather than misparsed — this repo's own `.env` carries a
`sqlite://` one, so local development still correctly selects SQLite.

Verified across six scenarios:

| Scenario | Engine | Notes |
|---|---|---|
| no DB env (local dev) | `sqlite3` | unchanged |
| `DB_*` (CI) | `postgresql` | unchanged |
| `DATABASE_URL` (compose) | `postgresql` | **was `sqlite3`** |
| `DATABASE_*` (k8s) | `postgresql` | **was `sqlite3`** |
| `DB_*` + `DATABASE_URL` | `postgresql`, `DB_*` wins | precedence |
| `DB_SSLMODE=require` | `sslmode=require` | both spellings honoured |

End-to-end, a compose-style `DATABASE_URL` now reaches a real server:
`PostgreSQL 17.11`, `django_migrations = 199`.

### 16.4 TLS to the database was impossible to configure

There was no way to set `sslmode` at all. libpq's default is `prefer`, which **silently
falls back to an unencrypted connection** when the server offers no TLS — for a password
manager that is vault ciphertext, auth hashes and session data on the wire in the clear,
with nothing logged.

The default deliberately **stays** `prefer`: `backend-ci.yml` runs `manage.py check
--deploy` and `migrate` with `DEBUG=False` against a TLS-less Postgres service, so
keying this off `DEBUG` would have broken CI on day one. The setting is now
*configurable* via `DB_SSLMODE`/`DATABASE_SSLMODE`, with
`DB_SSLROOTCERT`/`DATABASE_SSLROOTCERT` for `verify-full`.

> **Corrected in review round 1 (§17.1).** This section originally said
> "`k8s/configmap.yaml` now sets `DB_SSLMODE=require`". It did, and that was wrong:
> the PostgreSQL Deployment in the same manifest set runs the stock image with no
> TLS, so `require` would have failed every pod. The configmap now ships `prefer`
> with the enablement procedure written beside it. **Making `sslmode` settable is
> the durable change here; the value itself cannot be raised until the server can
> actually serve TLS.**

### 16.5 `scripts/init-db.sql` did not exist

`docker-compose.yml` has always mounted `./scripts/init-db.sql` into
`/docker-entrypoint-initdb.d/`, but the file was absent — a bind mount of a missing host
path makes Docker create a **directory** there. Added, creating the `vector` extension
only. It deliberately does **not** create `btree_gin` or `pg_trgm`: the GIN index in
`vault/migrations/0014` is over `tags`, a `models.JSONField` → `jsonb`, and GIN on jsonb
uses the built-in `jsonb_ops`. (An earlier draft of that file claimed otherwise; the
claim was checked against the migration and removed.)

### 16.6 Which images moved, and which deliberately did not

| Location | Before | After | Why |
|---|---|---|---|
| `.github/workflows/ci.yml` | `pgvector/pgvector:pg15` | **pg17** | ephemeral, no data |
| `.github/workflows/backend-ci.yml` | `pgvector/pgvector:pg15` | **pg17** | ephemeral, no data |
| `.github/workflows/stackhawk.yml` | `postgres:15-alpine` | **`pgvector/pgvector:pg17`** | ephemeral; also aligns the image family with the other jobs |
| `docker-compose.yml` | `postgres:15-alpine` | **`pgvector/pgvector:pg17`** | now that compose actually connects, it needs the `vector` extension the migration asks for; volume caveat documented inline |
| `k8s/deployment.yaml` | `postgres:15-alpine` | **unchanged — 15** | see below |

**Kubernetes was deliberately left on 15.** That pod is stateful (`postgres-pvc`), and a
major-version bump is a *data migration*, not an image-tag edit: PostgreSQL refuses to
start on a data directory initialised by another major version, so flipping the tag alone
yields `CrashLoopBackOff` on the production vault database. It also pins
`runAsUser/runAsGroup/fsGroup: 10070` for the **alpine** postgres uid, while the pgvector
images are Debian-based with a different uid — both would have to change together. The
manifest now carries the full upgrade procedure (dump → scale app to 0 → `pg_upgrade` or
restore into a fresh 17 PVC → flip tag → scale up) as a comment instead of a silent,
breaking change. PostgreSQL 15 is supported to 2027-11-11, so there is no urgency.

### 16.7 Regression test: the complete backend suite on PostgreSQL 17

The full suite (not a subset) was run against each backend:

| Backend | Result |
|---|---|
| SQLite (local default) | 2062 passed, 13 skipped, 82 subtests, **1 failed** |
| **PostgreSQL 17.11** | **2066 passed, 9 skipped, 82 subtests, 1 failed** (14m45s) |

Moving to PostgreSQL **gained** coverage rather than losing it: 4 previously-skipped
tests now execute (13 → 9 skipped), and `test_sql_injection_in_email_field` — the
SQLite-only failure documented in §15, which queries `information_schema` — **passes**,
exactly as predicted.

One test fails on PostgreSQL:
`security/tests/test_legacy_security_service.py::SecurityServiceTestCase::test_analyze_successful_login_normal_case`,
with `AssertionError: 100 not less than 80`. It asserts a legacy threat-scoring
heuristic stays under the suspicious threshold for a first login; on PostgreSQL the
summed risk factors reach the 100 cap.

**It is not caused by either upgrade, and that was established by running the
baselines rather than by argument.** The same single test, in isolation:

| Django | PostgreSQL | Result |
|---|---|---|
| **5.1.15** (pre-PR baseline) | **15.19** | `AssertionError: 100 not less than 80` |
| 5.2.17 | 15.19 | `AssertionError: 100 not less than 80` |
| 5.2.17 | **17.11** | `AssertionError: 100 not less than 80` |

Identical on all three. So **PostgreSQL 17 adds no regression over 15**, and Django
5.2.17 adds none either. The failure is a pre-existing PostgreSQL-vs-SQLite behavioural
difference in that legacy heuristic — it is out of scope for this PR, and worth its own
issue. (It does not surface in CI: `backend-ci.yml`'s test step carries
`continue-on-error: true`.)

The scoring path holds no Redis or cache dependency (`security/services/security_service.py`
has no `django.core.cache` or redis import), so the difference is in how the summed
factor queries evaluate on PostgreSQL, not in missing local infrastructure.

### 16.8 Answering the two questions the version decision hinges on

- **Database performance bottlenecks?** None were found or claimed, and nothing in this
  work measured any. The upgrade is therefore **not** justified on performance grounds;
  it is justified purely on the EOL ordering in §16.1.
- **Reliance on specialised PostgreSQL features?** Only `pgvector` (guarded, optional,
  verified working on 17 at 0.8.6) and one GIN-on-jsonb index (verified created on 17).
  No PostGIS, no `django.contrib.postgres`, no logical replication in this repository.

---

## 17. Review round 1 (PR #512, 2026-09-14) — CodeRabbit + Codex

**No CI check was failing** — 27 successful, 1 neutral (Trivy: no matching configs),
6 skipped (deploy jobs gated on push). Four findings, **all four real, and three of
them are consequences of my own previous round.** That is the pattern to notice: the
§16.3 fix (making Kubernetes genuinely reach PostgreSQL) turned three previously
*dormant* misconfigurations into live rollout failures. A change that makes a code path
execute for the first time inherits every latent defect on that path.

### 17.1 `DB_SSLMODE=require` against a PostgreSQL that has no TLS (P1, both reviewers)

Flagged independently by Codex and CodeRabbit, and correct. `k8s/deployment.yaml` runs
the stock `postgres` image: no `-c ssl=on`, no certificate or key mounted, no TLS proxy.
PostgreSQL ships `ssl = off`, so a client demanding `require` is refused with *"server
does not support SSL, but SSL was required"*.

On its own that was latent. Combined with §16.3 — which made these pods actually connect
to PostgreSQL instead of silently using SQLite — it becomes a **guaranteed rollout
failure**: the migrate Job, the collectstatic init container and every backend pod.

Fixed by shipping `prefer` and writing the two-step enablement procedure into the
configmap (mount a cert/key Secret and start the server with `ssl=on` — noting the key
must be `0600`, so a cert-manager Secret needs `defaultMode: 0600` — *then* raise the
value). §16.4 has been corrected, because it asserted the opposite.

**The durable half of that change still stands: `sslmode` was previously impossible to
set at all.** Adding the capability is the fix; setting a value the server cannot honour
is not.

### 17.2 NetworkPolicy denies the migration Job its database (P1, Codex)

`migrate-job.yaml` labels its pod `component: migrate`. Under `default-deny-all`, no
policy granted that label egress, and `allow-postgres` did not list it as an ingress
source — blocked in **both** directions.

Invisible until now for the same reason as §17.1: the Job received `DATABASE_NAME`, which
settings did not read, so it ran on SQLite and never opened a socket to 5432. Now it does.

Added `allow-migrate` (egress to `component: database` on 5432, modelled exactly on the
existing `allow-maintenance`) and added `migrate` to `allow-postgres`'s ingress sources.
Both halves are required — an egress rule is useless if the database refuses the ingress.
DNS was already covered namespace-wide by `allow-dns`.

### 17.3 A database password containing `#`, `/` or `?` crashed settings at import (P2, Codex)

Real, and **worse than reported**. `urlparse` is lazy: it splits eagerly but only
validates `.port` when read. An unencoded `#`, `/` or `?` in the password splits the
authority wrongly, so `.port` raises `ValueError` — and `getattr(parts, 'port', default)`
does **not** absorb it, because `getattr`'s default only covers `AttributeError`.
Verified directly:

```
pw='plain'  -> hostname='postgres' port=5432
pw='p#ss'   -> ValueError: Port could not be cast to integer value as 'p'
pw='p/ss'   -> ValueError: ...
pw='p?ss'   -> ValueError: ...
pw='p@ss'   -> hostname='postgres' port=5432        # '@' is fine, last one wins
getattr(u, 'port', 'DEFAULT')  ->  RAISED ValueError
```

`docker-compose.yml` interpolates `${DB_PASSWORD}` straight into `DATABASE_URL`, so this
is reachable with nothing more exotic than a generated password.

**A bare `try/except` returning the default would have been the wrong fix.** `#`
truncates the URL at a fragment, so the surviving `.hostname` is a piece of the
credentials rather than the database host — swallowing the error means quietly connecting
somewhere unintended, or quietly dropping back to SQLite. Both are worse than a crash for
a password manager. `_parse_db_url` therefore raises `ImproperlyConfigured` naming the
offending characters, their encodings, and the `DB_*` alternative that needs no encoding.

### 17.4 README dependency table still listed the pre-bump versions (minor, CodeRabbit)

Correct: `django-cors-headers 4.0.0`, `django-storages 1.13.2`, `django-timezone-field
7.1`, `drf-yasg 1.21.10`, `django-celery-beat 2.8.0`. §15 updated the Django and DRF rows
and stopped there — the same partial-sweep shape this document has recorded before.

All five corrected, then **cross-checked programmatically against
`requirements.txt`** rather than by eye: all seven Django-ecosystem rows now match their
pins exactly.

### Verification

| Check | Result |
|---|---|
| `manage.py check` | no issues |
| k8s YAML parses (`configmap`, `network-policy`, `deployment`) | OK — 1 / 10 / 18 docs |
| `allow-migrate` present; `allow-postgres` ingress | `backend, websocket, maintenance, migrate` |
| `DB_SSLMODE` shipped value | `prefer` |
| Malformed `DATABASE_URL` | clear `ImproperlyConfigured`, not "cast to integer" |
| Percent-encoded / normal / CI / local-dev resolution | unchanged — postgresql, postgresql, postgresql, sqlite3 |
| README rows vs `requirements.txt` | 7/7 match |
| Targeted suites (`password_manager/`, `hidden_vault/`) | **79 passed, 19 subtests** |

Targeted suites only, per the standing preference — the full 2066-test run was done in
§16.7 and nothing here touches application logic.

---

## 18. The `test_analyze_successful_login_normal_case` failure, diagnosed and fixed

§16.7 recorded this test failing identically on Django 5.1.15+PG15, 5.2.17+PG15 and
5.2.17+PG17 — enough to prove neither upgrade caused it, and it was left as
"out of scope, deserves its own issue". Running that issue down produced a better
answer than expected: **the test failure was environmental, but chasing it exposed a
real security defect underneath.**

### 18.1 The failure itself: a local `.env` value colliding with a hardcoded test IP

Instrumenting the scoring rather than reasoning about it gave the exact factors:

```
threat_score = 100
location     = ', '
factors      = {'new_device': True, 'new_location': ', ',
                'unusual_user_agent': 'Other on Other', 'blacklisted_ip': True}
```

`30 (new_device) + 30 (new_location) + 15 (unusual_user_agent) + 50 (blacklisted_ip)
= 125`, capped to 100. The deciding factor is **`blacklisted_ip`**, and the reason is
not subtle once seen:

```
.env:  BLACKLISTED_IPS=192.168.1.100,10.0.0.5
test:  create_mock_request(ip='192.168.1.100')
```

The test hardcodes the *exact* address this repository's own `.env` blacklists, so
`_is_ip_blacklisted` fired **correctly**. CI sets no `BLACKLISTED_IPS`, so the blacklist
is empty there, the score is 75, and the suite passes — which is why this was green in
CI and red locally, the least useful way for a test to be wrong.

Fixed by neutralising the ambient setting for that test class:
`@override_settings(BLACKLISTED_IPS=set(), BLACKLISTED_IP_NETS=[])`. `_is_ip_blacklisted`
reads `getattr(settings, 'BLACKLISTED_IP_NETS', [])` at call time, so the override takes
effect. **A unit test asserting a risk threshold must not depend on whatever the
developer happens to have in their environment.**

### 18.2 The real bug underneath: PostgreSQL-only SQL silently abandoning the risk calculation

The question this left open was why the test ever passed on SQLite, where the same
blacklist applies. The answer is a genuine defect:

```python
).extra(select={'hour': 'EXTRACT(hour FROM timestamp)'}).values_list('hour', flat=True)
```

`EXTRACT(hour FROM ...)` is PostgreSQL/MySQL syntax. **SQLite has no `EXTRACT`**, so the
query raises — and `_calculate_risk_score` wraps its entire body in

```python
except Exception as e:
    logger.error(f"Error calculating risk score: {e}")
```

so the exception is swallowed and the method **returns the partial score accumulated so
far**. Everything below that line was skipped on any non-PostgreSQL backend:

| Factor after the EXTRACT call | Weight | Status on SQLite |
|---|---|---|
| unusual time | +20 | never evaluated |
| impossible travel | +50 | never evaluated |
| unusual user agent | +15 | never evaluated |
| **blacklisted IP** | **+50** | **never evaluated** |
| velocity / multiple IPs | +30 | never evaluated |

That is why the test passed on SQLite: scoring aborted at 60 before it could reach the
blacklist check. The "passing" test was passing *because the security feature was
silently broken*.

Replaced with Django's portable `ExtractHour`, which compiles per-backend:

```python
).annotate(hour=ExtractHour('timestamp')).values_list('hour', flat=True)
```

`grep -rn "\.extra(" --include=*.py` now returns only the explanatory comment, and there
are no `RawSQL(`/`.raw(` calls anywhere — so this was the only instance of the pattern,
not one of several.

### 18.3 Why this was safe to change

The concern with fixing 18.2 is that SQLite scores now *rise* (the calculation completes
instead of truncating). Checked before editing:

- The only upper-bound assertion on a computed score in the touched file is the
  `assertLess(..., 80)` at issue; the others are lower bounds (`> 0`, `> 30`) that a
  higher score cannot break.
- Every other `threat_score` assertion in the repository belongs to unrelated models
  (`ml_security` uses a 0.0–1.0 scale; `test_predictive_expiration*` asserts on an
  industry record), not to `SecurityService._calculate_risk_score`.
- In CI, with no `BLACKLISTED_IPS`, a first login now scores 75 on **both** backends —
  under the 80 suspicious threshold, so `is_suspicious` is unchanged.

| Check | Result |
|---|---|
| `test_legacy_security_service.py` on **PostgreSQL 17.11** | **10 passed** (was 1 failed) |
| `test_legacy_security_service.py` on **SQLite** | **10 passed** |
| `manage.py check` | no issues |
| `.extra(` / `RawSQL(` / `.raw(` sweep | no other occurrences |

### 18.4 Noted, not fixed

`location` came back as the string `', '` — a failed GeoIP lookup (`GeoLite2-City.mmdb`
absent) still produces a truthy `"city, country"` join from two empty strings, which then
satisfies `if user and login_attempt.location` and contributes `new_location` **+30**. So
an unresolvable IP is scored as a *new location* rather than as no location at all.

Left alone deliberately: it is pre-existing, orthogonal to both the Django and PostgreSQL
upgrades, and changing it shifts scoring for every login path in the application — which
wants its own change and its own regression run, not a ride-along in a dependency PR.
