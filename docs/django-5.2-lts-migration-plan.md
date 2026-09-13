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
