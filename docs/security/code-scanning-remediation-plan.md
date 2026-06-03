# Code Scanning Remediation Plan

Branch: `fix/code-scanning-alerts` (from `main` @ 599fc09, after PR #288 merge)
Status: **PLAN ONLY — no code changed yet.** Every item below was verified
against the actual code in this branch before being written.

Guiding constraints (from the request):
- Verify each bug before changing anything.
- Keep code changes **minimal**.

---

## 0. TL;DR — the single highest-leverage finding

`.github/workflows/ci.yml` runs the Trivy **image** scans that feed GitHub
Code Scanning (`category: trivy-backend` / `trivy-frontend`, lines 437–465) **without**
`trivy-config: trivy.yaml`. The repo already maintains a careful `.trivyignore`
(with expiry dates + per-CVE threat assessments), and `trivy.yaml` points at it
via `ignorefile: ".trivyignore"`. But because the **image** scan never loads
that config, **every already-justified suppression is bypassed on the exact
scan that produces these alerts.** `security-multi-scanner.yml:245` *does* pass
`trivy-config: trivy.yaml` — so the gap is only in `ci.yml`.

**Wiring `.trivyignore` into the two `ci.yml` Trivy steps is a 2-line change
that clears the bulk of the container-OS-CVE and secret alerts** (ncurses,
curl, libssh2, sqlite, libgcrypt, libldap, autobahn key, …) that are already
documented and accepted. This is the keystone fix; do it first.

A second class is **stale** alerts: dependency pins / Dockerfile strips that
already fix the issue have landed, but the alert was raised against an older
commit and only clears on the next clean scan.

---

## 1. Triage summary

| Group | Alerts | Nature | Action | Code risk |
|------|--------|--------|--------|-----------|
| A. CodeQL "Information exposure through an exception" | ~50 (Py) | **Real** | Genericize client-facing message at each flagged sink; keep server log | Low |
| B. CodeQL URL redirection (oidc_views) | 1 (#1058) | **Real** (reflected param) | URL-encode reflected error params in redirect | Low |
| C. CodeQL Prototype-polluting function (shared/config/index.js) | 1 (#1053) | **Real** | Reject `__proto__`/`constructor`/`prototype` keys in `set()` | Low |
| D. CodeQL Workflow missing permissions (ci.yml) | 1 (#1390) | **Real** | Add top-level `permissions: contents: read` | Low |
| E. Trivy container OS CVEs (perl, ncurses, glibc, curl, libpam, gnupg, sqlite, openssl, binutils, llvm, http-tiny, Archive::Tar, IO-Compress…) | ~30 | Mix: **no upstream fix** + **suppression bypassed** + **stale** | Wire `.trivyignore` into ci.yml + add new no-fix entries w/ threat assessment | Low (config) |
| F. Trivy secret "Asymmetric Private Key" (autobahn cryptosign) | 2 (#1559/#1560) | **Stale** (Dockerfile already strips it) + suppression bypassed | Keystone fix + confirm next scan is clean | None |
| G. Grype Python deps (ujson, twisted, scrapy, nltk, ecdsa) | ~8 | Mostly **stale** (pins already fixed) + ecdsa **no-fix** | Confirm rescan clears; add `.grype.yaml` ignore for ecdsa Minerva | Low |
| H. npm uuid (mobile) | 2 (#1378/#1848) | **Real** | `overrides: uuid ^11` in mobile/package.json + relock | Low–Med |
| I. Trivy K8s UID/GID ≤ 10000 (grafana/prometheus/alertmanager) | 4 (Low) | Vendor-fixed UIDs | Add Trivy KSV ignore (consistent w/ existing KSV0125) | None |

---

## 2. Group A — CodeQL: Information exposure through an exception (~50)

### Verified pattern
`password_manager/auth_module/mfa_views.py:170-175` (representative):
```python
except Exception as e:
    logger.error(f"Face registration error: {e}")     # server log — fine
    return Response({
        'success': False,
        'message': f'Registration error: {str(e)}'      # <-- leaks detail to client
    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
```
CodeQL flags the `Response(...)`/`JsonResponse(...)` sink that embeds `str(e)`
(or `f"...{e}"`). The `logger.*` call is **not** the problem and must stay.

### Scope
`str(e)` appears 259× across the tree, but **only the ~50 that flow into an HTTP
response are flagged.** Do **not** blanket-replace — touch only the exact
CodeQL alert locations. Flagged files (alert IDs in parentheses):
- `auth_module/mfa_views.py` — #1119-1137 + #499/495/399/344/340/310/254/247/206/172/165/158 (the largest cluster)
- `auth_module/oidc_views.py:364` (#1168)
- `auth_module/mfa_views.py` cluster above
- `*/api/genetic_password_views.py:583/694/757` (#1096/1099/1101)
- `*/api/natural_entropy_views.py:175/236` (#1138/1139)
- `*/api/deaddrop_views.py:291` (#1084)
- `*/api/darkWebEndpoints.py:69` (#1079)
- `*/views/crypto_views.py:113` (#1081)
- `*/views/api_views.py:68` (#1060)
- `password_manager/api_utils.py:6` (#1059) — the shared `error_response()` helper
- `shared/decorators.py:297` (#1085)
- `ml_dark_web/views.py:334/521` (#1299/#1303)
- `decentralized_identity/views.py:162/232` (#1207/#1208)
- `zk_proofs/serializers.py:42` (#1178)
- `password_reputation/serializers.py:31` (#1177)

### Minimal fix (per sink)
Replace the exception-bearing client message with a static, generic string;
leave the `logger` line untouched. Example:
```python
except Exception as e:
    logger.error(f"Face registration error: {e}")
    return Response({
        'success': False,
        'message': 'Registration failed. Please try again.'   # generic
    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
```
For `api_utils.error_response()` (#1059): the helper is flagged because callers
pass `str(e)` as `message`/`details`. Fix at the **call sites** that pass
exception text (don't change the helper signature). If the helper is reached by
many flagged callers, an optional minimal hardening is to drop `details` from
the serialized body when `DEBUG` is false — but the lower-risk path is editing
the specific flagged callers.

### Verification after change
- `python -m pytest` for the affected apps (auth_module especially) to confirm
  no test asserts on the old `str(e)` substring in responses.
- Re-run CodeQL (the `codeql.yml` workflow) — alerts should drop to 0 for this query.

---

## 3. Group B — CodeQL: URL redirection from remote source (#1058)

### Verified
`auth_module/oidc_views.py` `oidc_callback()` redirect sinks (currently ~246/249/256):
```python
frontend_url = os.environ.get('FRONTEND_URL', 'http://localhost:3000')
if error:
    error_description = request.GET.get('error_description', 'Authentication failed')
    return redirect(f"{frontend_url}/auth/callback?error={error}&message={error_description}")
```
Host is fixed (env), but `error` / `error_description` are **request-controlled**
and interpolated raw into the redirect URL (reflected-parameter / CRLF risk).

### Minimal fix
Percent-encode the reflected values (CodeQL recognizes this as sanitization):
```python
from urllib.parse import urlencode
qs = urlencode({'error': error, 'message': error_description})
return redirect(f"{frontend_url}/auth/callback?{qs}")
```
Apply to all three reflected redirects. No behavior change for legitimate flows.

---

## 4. Group C — CodeQL: Prototype-polluting function (#1053)

### Verified
`shared/config/index.js:~292-301` — a dotted-path `set()` walks `keys` and assigns
`current[keys[keys.length - 1]] = value;` with only a `hasOwnProperty` guard. A
key of `__proto__` / `constructor` / `prototype` pollutes `Object.prototype`.

### Minimal fix
Reject dangerous keys before walking/assigning:
```js
const FORBIDDEN = new Set(['__proto__', 'prototype', 'constructor']);
// inside set(), after computing keys:
if (keys.some(k => FORBIDDEN.has(k))) return; // or throw
```

---

## 5. Group D — CodeQL: Workflow does not contain permissions (#1390)

### Verified
`.github/workflows/ci.yml` has per-job `permissions:` on most jobs (lines
64/309/421/479/549/729) but **no top-level block**, so the `setup` job (line ~44)
runs with the default broad token → CodeQL flags it.

### Minimal fix
Add a least-privilege top-level block after `on:` (jobs needing more already
override it):
```yaml
permissions:
  contents: read
```

---

## 6. Group E — Trivy container OS CVEs (~30)

### Verified facts
- Final image base = `python:3.11-slim-bookworm`; build tools (llvm/clang/binutils/
  gcc) live only in `deps-builder`/`crypto-builder` and are **not** in the runtime
  stage (only `/opt/venv` + liboqs `.so` are copied). So llvm/binutils/clang CVEs
  (#1825-1829, #1838) are **build-layer only**.
- The two **CRITICAL** perl CVEs (CVE-2026-42496, CVE-2026-8376) and several
  others show **"Fixed Version:" blank** → **no Debian patch exists yet**, so
  `apt-get -y upgrade` cannot fix them. The realistic action is suppression with
  a documented threat assessment + expiry (the repo's established pattern) and
  monitoring the Debian tracker — not a code fix.
- `.trivyignore` already covers ncurses/_nc_wrap_entry (CVE-2025-69720), libssh2,
  libcurl, sqlite, libgcrypt, libldap, zlib — **but the ci.yml image scan bypasses
  it** (see §0), so they re-surface.

### Fix (two parts)
1. **Keystone:** add `trivy-config: trivy.yaml` to both ci.yml Trivy steps:
   ```yaml
   - name: Run Trivy vulnerability scanner (Backend)
     uses: aquasecurity/trivy-action@…
     with:
       image-ref: ${{ needs.setup.outputs.backend_image }}:latest
       format: 'sarif'
       output: 'trivy-backend.sarif'
       severity: 'CRITICAL,HIGH'
       trivy-config: trivy.yaml      # <-- add (loads .trivyignore)
   ```
   (same for the Frontend step). This clears all already-listed CVEs from Code
   Scanning.
2. **New no-fix entries in `.trivyignore`** — only after verifying each on
   https://security-tracker.debian.org shows no fixed bookworm version. Add with
   the existing format (`<CVE> exp:<YYYY-MM-DD> # threat assessment`):
   - `CVE-2026-42496` (Archive::Tar symlink traversal) — perl-base. We do not call
     `Archive::Tar`; perl is base-image only, not invoked by the app.
   - `CVE-2026-8376` (perl regex heap overflow, **32-bit only**) — image is amd64
     (64-bit) → not exploitable on our arch.
   - perl-IO-Compress (#1860), Archive::Tar hardlink/memory (#1854/#1855) — same
     perl-not-invoked rationale.
   - libpam read-hashed-password (#1830-1833), gnupg (#1807/#1808), sqlite FTS5
     (#1835), glibc scanf/ungetwc (#1418/1419/1430/1431), util-linux (#1393/1396/
     1402-1404/1411/1414/1464), curl (#1402-1404) — verify each, attach rationale.
   - openssl PowerPC (#1837/#1844) and llvm/ARM (#1825-1829) — **wrong-arch**,
     trivially not applicable to the amd64 runtime.
   - http-tiny insecure-TLS-default (#1845) — perl module, not invoked.

> Note: many of these are already partially covered; the goal is that after the
> keystone fix + new entries, the `trivy-backend` Code Scanning category is clean
> or only shows entries with live expiry dates.

---

## 7. Group F — Trivy secret: autobahn cryptosign key (#1559/#1560)

### Verified
`docker/backend/Dockerfile:319-351` **already** removes `autobahn/wamp` and any
`autobahn/*cryptosign*.py*` and **fails the build** if they survive. `.trivyignore`
also has an `autobahn-wamp-example-key` custom-secret entry. `cryptosign.py` is
**not** in the repo (it's vendored inside the image only). → The alerts are
**stale** (raised before the strip landed) and additionally suppressed-but-bypassed.

### Fix
No code change. The §6 keystone fix applies the secret ignore on the image scan;
a fresh build+scan should report 0. If #1559 (the `.pyc`) persists, extend the
Dockerfile `-delete` glob to cover `*/autobahn/**/__pycache__/*cryptosign*` (the
current glob already matches `*cryptosign*.py*`, which includes `.pyc`).

---

## 8. Group G — Grype Python dependency alerts (~8)

### Verified — most are STALE (pins already fixed)
`requirements-core.txt` / `requirements.txt` already pin the fixed versions with
GHSA references in comments, and the lock reflects them:
- `nltk>=3.9.4` (GHSA-jm6w-m3j8-898g) → **#805 stale**.
- `ujson>=5.12.1` (GHSA-c38f-wx89-p2xg / CVE-2026-44660) → **#1752 likely stale**
  — *verify 5.12.1 is the fixed version (not 5.13+) before closing.*
- `scrapy` — core pin `>=2.14.2`, ml pin `>=2.15.0`; GHSA-h7wm-ph43-c39p was fixed
  in 2.11.2 → **#977/#978 stale**. *Fix the lock inconsistency:* main
  `requirements-lock.txt` pins `Scrapy==2.14.2` while the constraint floor is
  `scrapy>=2.15.0` — bump the main lock to `2.15.0` to match.
- `Twisted==26.4.0` (constraint floor 26.4.0; GHSA-grgv-6hw6-v9g4) → **#1725 stale**
  *if* fixed ≤26.4.0 — verify.

### ecdsa (#867/#868) — NO upstream fix
`ecdsa==0.19.2`, GHSA-wj6h-64fc-37mp = the **Minerva timing side-channel**, which
the maintainers **will not fix** in pure-Python ecdsa. It's transitive (not a
direct pin). Action: add a **`.grype.yaml`** (Grype auto-loads it from CWD; none
exists today) with a justified ignore:
```yaml
ignore:
  - vulnerability: GHSA-wj6h-64fc-37mp   # ecdsa Minerva timing attack — no upstream fix
    # We do not perform ECDSA signing/verification with attacker-controlled
    # timing exposure; ecdsa is a transitive dep. Re-evaluate <date>.
```

---

## 9. Group H — npm uuid (mobile) (#1378/#1848)

### Verified
`mobile/package-lock.json` carries `uuid@10-and-below` (deprecated), GHSA flags an
out-of-bounds write. uuid is (almost certainly) transitive.

### Minimal fix
Add an override in `mobile/package.json` and relock:
```json
"overrides": { "uuid": "^11.0.0" }
```
then `cd mobile && npm install` (regenerate lock). Verify the RN build/tests still
pass (uuid 11 is ESM-first; confirm consumers don't rely on removed default export).
Medium risk → isolate in its own commit.

---

## 10. Group I — Trivy K8s UID/GID ≤ 10000 (Low) (#1688/1690/1691/1693)

### Verified
`k8s/monitoring/grafana-deployment.yaml` uses `runAsUser: 472` (grafana's vendor
UID); prometheus/alertmanager similar. KSV020/KSV021 want UID/GID > 10000.
Changing grafana's UID risks volume-permission breakage.

### Minimal fix (lowest risk)
Add the KSV checks to `.trivyignore` with justification (mirrors the existing
`KSV0125` entry) rather than re-UID vendor images:
```
KSV020   # vendored monitoring images (grafana 472, …) require their fixed UID
KSV021   # same — GID fixed by upstream image; volumes chowned to it
```
(Alternatively, if a security policy mandates high UIDs, set `runAsUser/runAsGroup`
> 10000 *and* an `initContainer` to chown the data dir — higher effort/risk.)

---

## 11. Suggested PR slicing (so a red scan never blocks a green fix)

1. **PR-1 (keystone, config-only, zero code risk):** ci.yml `trivy-config` wiring
   (§6.1) + new `.trivyignore` entries (§6.2) + `.grype.yaml` (§8) + KSV ignores
   (§10). Clears the majority of E/F/G/I immediately.
2. **PR-2 (CodeQL Python, app code):** Group A (info-exposure) + B (open redirect).
   Run backend test suite. Largest diff but mechanical.
3. **PR-3 (small code):** Group C (prototype pollution) + D (workflow permissions).
4. **PR-4 (deps):** §8 lock bump (scrapy) + Group H (mobile uuid) — isolated relock.

## 12. Verification strategy (per the "verify before change" instruction)
- **Before:** each item above was confirmed against source (file:line) and the
  scanner configs; root cause for the container alerts identified (ignore bypass).
- **During:** for every new `.trivyignore` CVE, confirm "no fixed version" on the
  Debian tracker and grep the codebase for the named vulnerable API (the repo's
  own renewal checklist, `.trivyignore` lines 103-120).
- **After:** re-run `codeql.yml`, the `trivy-backend` scan, and Grype; confirm
  alert counts drop and no *new* alerts appear. Run `pytest` for touched apps and
  the mobile build for the uuid bump.

## 13. Risk / rollback
- Config + ignore changes (PR-1) are reversible and cannot affect runtime.
- App-code changes (PR-2/3) are message-string and key-guard edits — no logic
  flow change; covered by existing tests.
- The mobile uuid bump (PR-4) is the only one with real regression surface; keep
  it isolated and gate on the mobile build.
