# Plan — Close the gaps in 5 privacy/anti-forensics features

Verification performed on `main` @ `5e43b1d`. Every claim below was checked
against the code, not inferred from filenames or docs.

**Scope.** Onion-Routed Vault Sync (10), Plausible Deniability Vault (12),
Smart Contract Automation (15), Honeypot Passwords (18), Honeypot Emails.

---

## 0. Verdict table

| # | Feature | Status | Gap |
|---|---------|--------|-----|
| 10 | Onion-Routed Vault Sync | **Infrastructure only** | Tor rails built; **no client ever rides them** |
| 12 | Plausible Deniability Vault | **Partial** | Management plane complete; **unlock plane unwired** |
| 15 | Smart Contract Automation | **Complete** | — (no action) |
| 18 | Honeypot Passwords | **Complete** | — (no action) |
| — | Honeypot Emails (breach canary) | **Built, never runs** | 9 Celery tasks, all **absent from `beat_schedule`** (6 are schedulable) |

Three of the five need work. One (10) is the headline gap and directly
answers the question asked about PR #454.

---

## 1. Feature 10 — is the PR #454 Tor implementation utilised for vault sync?

**No.** The Tor work landed and is real, but nothing in any client routes a
sync through it. The rails exist; no train runs on them.

### 1.1 What PR #454 ("Dark Protocol") genuinely delivered — all verified present

- `docker/tor/{Dockerfile,entrypoint.sh,torrc.template}` — a Tor v3 onion
  service. `torrc.template` forwards `HiddenServicePort 80` to a **dedicated
  onion ingress listener**, deliberately *not* the clearnet backend port, so
  arrival-on-that-port is a network fact a remote client cannot forge.
- [`tor_service.py`](password_manager/security/services/tor_service.py) (~1100 lines):
  bootstrap progress, circuit state, onion address resolution, a loopback
  reachability self-check, `socks_proxies()`, and `request_is_onion_ingress()`.
- [`dark_protocol_service.py`](password_manager/security/services/dark_protocol_service.py):
  garlic routing, noise encryptor, cover-traffic generator, and
  `proxy_vault_operation()`.
- [`dark_protocol_views.py:461`](password_manager/security/api/dark_protocol_views.py:461)
  `DarkProtocolVaultProxyView` — **no clearnet fallback**; refuses with
  `clearnet_ingress_refused` rather than letting a client believe it was
  anonymous. That is the correct fail-closed posture.
- **`vault_sync` is already a routable operation**:
  [`dark_protocol_service.py:181`](password_manager/security/services/dark_protocol_service.py:181)
  → `'vault_sync': {'method': 'POST', 'route': 'vault-sync'}`, and the target
  `vault-sync` route genuinely exists at
  [`vault/urls.py:84`](password_manager/vault/urls.py:84).
- Cover traffic already models `vault_sync` as a decoy operation type
  ([`cover_traffic_generator.py:43,54,212,291`](password_manager/security/services/cover_traffic_generator.py:43)).

So the backend is, on its own, **ready**. The gap is entirely client-side.

### 1.2 The four confirmed breaks

1. **`proxyVaultOperation` is dead code.** Defined and exported at
   [`darkProtocolService.js:253`](frontend/src/services/darkProtocolService.js:253)
   and [`DarkProtocolService.js:318`](mobile/src/services/DarkProtocolService.js:318).
   A repo-wide search for callers returns **only the definition and the
   `export default` re-listing**. Nothing invokes it — not the web app, not
   mobile, not e2e.

2. **The real sync path is clearnet.** The only vault-sync callers are
   [`vaultService.js:189-191`](frontend/src/services/vaultService.js:189)
   (`syncVault()` → `this.api.post('/vault/sync/')`) and
   [`api.js:204`](frontend/src/services/api.js:204)
   (`sync: (data) => api.post('/vault/sync/', data)`). Both use the plain
   axios instance. Neither consults Tor capability, and neither has a
   Dark Protocol branch.

3. **No client-side Tor transport exists anywhere.** Greps for
   `socks`/`.onion` across `desktop/src/`, `browser-extension/`, and
   `mobile/src/` return nothing. The Tor daemon is *server-side only*. Today
   the sole way to actually reach the onion ingress is for the human to point
   Tor Browser at the `.onion` themselves.

4. **No "privacy vs speed" control.** The feature brief calls for a user
   choice; there is no such preference on the sync path.

### 1.3 An honest limitation to fix while we are here

`DarkProtocolVaultProxyView` is `permission_classes = [IsAuthenticated]`. Tor
hides the client's **IP**, but the JWT still names the **user**. So the brief's
"Server can't correlate sync with user identity" is *not* achieved by onion
routing alone — only "server doesn't know your IP" and (via existing cover
traffic) partial timing-analysis resistance are. Real unlinkability needs
blind/anonymous credentials. Phase 4 addresses this; Phases 1–3 must not claim
more than they deliver, and the UI copy must say *IP privacy*, not *identity
privacy*.

---

## 2. Feature 12 — Plausible Deniability Vault

### 2.1 What is genuinely complete

- Models ([`duress_models.py`](password_manager/security/models/duress_models.py)):
  `DuressCodeConfiguration`, `DuressCode`, `DecoyVault`, `DuressEvent`,
  plus trusted-authority and evidence-package support.
- [`decoy_vault_service.py`](password_manager/security/services/decoy_vault_service.py):
  genuinely convincing decoy generation — folders, password/card/identity/note
  entries, **Luhn-valid** fake card numbers, tracking-token injection, and a
  realism score.
- [`duress_code_service.py`](password_manager/security/services/duress_code_service.py):
  silent alarms (`_trigger_silent_alarms`), evidence packages, decoy refresh,
  and delegation to the stego/hidden vault (`_decoy_from_hidden_vault`).
- Timing-side-channel care: `_check_duress_codes` iterates **all** active codes
  before returning, so the count of codes does not leak.
- Full REST surface (`security/urls.py:353-374`) and web UI
  (`DuressCodeSetup`, `DuressCodeManager`, `DecoyVaultPreview`, `DuressEventLog`),
  routed in `App.jsx:2249-2263`.
- **Already wired for heartbeat auth**: `HeartbeatVerify.jsx` deliberately makes
  the success and duress paths indistinguishable in the UI — correct design.

### 2.2 The gap: the master-password unlock path has no duress branch

- [`security_service.py:62`](password_manager/security/services/security_service.py:62)
  `check_for_duress_code()` has a docstring saying *"This should be called
  during login AFTER the password is validated."* **Nothing calls it.** The
  only references are in `test_duress_code.py`, and the first of those merely
  asserts the method exists (`hasattr` + `callable`) — a tautological test that
  passes whether or not the feature is connected.
- Greps for `duress` across `auth_module/`, `user/`, and `api/` return **zero**
  hits. The login/unlock flow simply does not know duress exists.
- So the brief's core — *two master passwords, one opens the decoy* — is **not
  implemented for the master password**.

### 2.3 The ZK problem that must shape the fix

`verify_password_or_duress(user, input_password)` compares a **candidate master
password server-side** against `DuressCode.code_hash`. Under the project's own
ZK invariant (`docs/adaptive-password-zk-remediation-plan.md` §1: no value from
which the password can be feasibly recovered may reach the server; §2: the
server is assumable-hostile), sending the master password to the server is
exactly what the architecture forbids. **Wiring `check_for_duress_code` into
login as written would fix the feature by breaking the threat model.** It must
not be done that way.

### 2.4 The ZK-correct primitive already exists — it is just not on the unlock path

`HiddenVaultBlob v1` ([`hidden_vault/SPEC.md`](password_manager/hidden_vault/SPEC.md))
is precisely the right tool, and its stated goals match the feature brief:

- two vaults (real + decoy) encrypted under **two independent master passwords**
  in one opaque blob;
- **fixed size by tier**, so byte length leaks nothing;
- **slot symmetry** — the unused slot is filled with ciphertext under a fresh
  discarded key, so it is indistinguishable from a used one;
- **password → slot is opaque**: the decoder tries both slots client-side and
  returns whichever verifies.

It is implemented four times over and kept byte-compatible: `envelope.py`,
`frontend/src/services/hiddenVault/hiddenVaultEnvelope.js`,
`browser-extension/src/stego/hiddenVaultEnvelope.js`,
`mobile/src/services/stego/hiddenVaultEnvelope.js`.

**But** its only frontend consumer is `StegoVaultDashboard.jsx` (via the
`services/stego` facade). `VaultUnlockModal.jsx` — the actual unlock — never
touches it. The correct primitive exists and sits unused next to the door it
was built for.

---

## 3. Honeypot Emails — built, but never scheduled

`security/tasks/honeypot_tasks.py` defines **nine** `@shared_task`s with
explicit names. Six take no arguments and are schedulable:
`scan_all_honeypots`, `analyze_breach_patterns`, `process_pending_rotations`,
`cleanup_expired_honeypots`, `send_breach_digest`, `generate_honeypot_stats`.
Three take a required id and are fan-out targets invoked BY the six above, not
scheduled directly: `check_honeypot_activity`, `check_all_user_honeypots`,
`correlate_with_hibp`.

Backing them: `HoneypotConfiguration`, `HoneypotEmail`, `HoneypotActivity`,
`HoneypotBreachEvent`, `CredentialRotationLog`, plus working SimpleLogin and
AnonAddy alias providers with webhook signature verification.

**None of them are scheduled.** Verified three ways:

1. `grep honeypot password_manager/password_manager/celery.py` → no matches.
2. `honeypot_tasks.py` contains **no** `CELERY_BEAT_SCHEDULE` dict at all.
3. `security/tasks/__init__.py` exports only `TIME_LOCK_BEAT_SCHEDULE` (line 127).

**Found during implementation — the feature was broken twice over.** Beyond
being unscheduled, `honeypot_tasks.py` was never *imported* in production
either: the only importers in the repo were tests, by module path. Since
`@shared_task` registers a task only when its defining module is imported —
and `autodiscover_tasks()` imports the `security.tasks` *package*, not
submodules its `__init__` never names — none of the nine tasks were registered
at all. Fixing only the schedule would have been inert: beat would enqueue
names no worker could resolve. Both halves are required, and this is the exact
defect the Dark Protocol block at `security/tasks/__init__.py:138-144` already
documents for its own tasks.

**Also found: `test_celery_beat_registry.py` could not have caught any of
this.** Its `_beat_schedule()` helper read `app.conf.beat_schedule` without
calling `app.finalize()`, so entries contributed by `@app.on_after_finalize`
were invisible to every assertion in the file — including the four
`time_lock.*` entries PR #483 added. The suite that exists to catch orphaned
beat entries was blind to precisely the deferred-merge mechanism used to fix
them.

Consequence: "detects breaches instantly", "automatically rotates real
credentials", and the breach digest **never fire**. Alias activity is only ever
polled if something calls the task by hand.

This is the *same defect class* PR #483 just fixed for Time-Lock, and the
comment block at `celery.py:519-556` describes it exactly: a module defines a
schedule (or here, tasks with no schedule) that nothing merges into the app's
`beat_schedule`, so fully-implemented tasks never run. Sibling orphans still
outstanding, found while checking: `mesh_deaddrop/tasks/deaddrop_tasks.py:351`
and `personality_auth/tasks.py:80` each define a `CELERY_BEAT_SCHEDULE` that
nothing merges either — same bug, different modules.

---

## 4. Implementation plan

Ordering: §4.3 first (smallest, highest value, unblocks a live security
feature), then §4.2, then §4.1 phased.

### 4.1 Feature 10 — actually route sync over Tor

Architectural constraint to respect: **a page served over clearnet HTTPS cannot
open a `.onion` connection.** Only a process that can run or reach a SOCKS5
proxy can. So the phases are ordered by what is genuinely achievable per client.

#### Phase 1 — `onionSyncService` + preference (web, works when served from the `.onion`)

Modular-monolith placement: new frontend service beside its peers, no new
backend app — the backend already supports this operation.

1. New `frontend/src/services/onionSyncService.js`:
   - `getSyncPrivacyMode()` / `setSyncPrivacyMode(mode)` over the existing
     `preferencesService`, with modes `'off' | 'prefer_onion' | 'require_onion'`
     (default `'off'`, preserving today's behaviour).
   - `syncVault(syncData)` that:
     - `'off'` → delegate to `vaultService.syncVault` unchanged;
     - `'prefer_onion'` → call `darkProtocolService.getCapabilities()`; if
       `anonymity_active && current_connection_is_anonymous`, call
       `proxyVaultOperation('vault_sync', syncData)`; else fall back to clearnet
       **and return a flag saying it did**, so the UI can be honest;
     - `'require_onion'` → onion or **fail**; never silently downgrade. This
       mirrors the backend's existing no-fallback stance.
2. Change `vaultService.syncVault` call sites to go through `onionSyncService`.
   Keep `vaultService.syncVault` as the clearnet transport it already is —
   single responsibility, no behavioural change when mode is `'off'`.
3. Settings UI in `DarkProtocolSettings.jsx` (the component already exists):
   a three-way privacy-vs-speed control. Copy must say **"Hides your IP address
   from the server"**, not "server can't identify you" — see §1.3.
4. Surface the fallback truthfully: if `prefer_onion` degraded to clearnet, show
   it. Never let the user believe a sync was anonymous when it was not.

**ZK note:** the sync payload is already client-side encrypted; this phase adds
*metadata* privacy only and changes no crypto. No new plaintext crosses the wire.

#### Phase 2 — desktop Tor transport (the first phase that helps a normal user)

`desktop/` is Electron and can own a Tor process, which the browser cannot.

1. Bundle `tor` (or `arti`) as a sidecar; manage lifecycle in `desktop/src/main/`.
2. Expose a SOCKS5 proxy to the renderer; route the sync request — and only it,
   at first — through the `.onion` from `getCapabilities()`.
3. Reuse the Phase 1 service contract verbatim so the renderer code is identical
   across web and desktop; only the transport differs.
4. Health/bootstrap UI: reuse `DarkProtocolDashboard.jsx`, which already renders
   circuit and bootstrap state.

#### Phase 3 — mobile

Android via Orbot (`TorService` / `NetCipher`); iOS via an embedded Tor library.
Same service contract as Phases 1–2, wiring `mobile/src/services/DarkProtocolService.js`'s
already-present-but-unused `proxyVaultOperation`.

#### Phase 4 — close the identity-correlation gap (optional, larger)

To make "server can't correlate sync with user identity" true rather than
aspirational, replace the JWT on the vault-proxy path with an anonymous
credential (blind-signed token / OPRF), issued over clearnet and redeemed over
onion, so the redemption is unlinkable to issuance. Until then, Phase 1's UI
copy is the honest fix. Treat as its own design doc.

#### Tests (per phase)

- Unit: `require_onion` never falls back; `prefer_onion` sets the degraded flag;
  `off` is byte-identical to today's request.
- Backend contract: assert `vault_sync` stays in `VAULT_OPERATION_ROUTES` and
  that `vault-sync` reverses — a regression guard on the wiring that already exists.
- e2e: extend `e2e/dark_protocol.spec.js` with a sync-over-proxy case.
- Negative: proxy call from clearnet returns `clearnet_ingress_refused` (403)
  and the client surfaces it rather than retrying over clearnet.

### 4.2 Feature 12 — wire duress to unlock, the ZK-correct way

**Do not** call `check_for_duress_code` from login (see §2.3).

1. **Unlock via the envelope.** Extend `VaultUnlockModal.jsx` to decode through
   `services/stego` / `hiddenVaultEnvelope`: the entered password is tried
   against both slots **client-side**; whichever verifies is opened. The server
   learns nothing about which one, because it never sees the password. This is
   the primitive working as specified (`SPEC.md` goal 4).
2. **Silent alarm without leaking the password.** On a decoy-slot unlock, the
   client releases a **pre-registered opaque duress token** — a random value
   generated at duress-setup time and stored server-side hashed, entirely
   independent of any password. The server compares hashes and fires
   `_trigger_silent_alarms` + `DuressEvent` (both already implemented). Because
   the token is password-independent, this satisfies §1 of the ZK plan.
3. **Indistinguishability.** The duress request must be identical in shape,
   size, and timing to a normal unlock — same endpoint, same padded body, no
   extra round-trip. Follow the `HeartbeatVerify.jsx` precedent, which already
   refuses to branch the UI string on duress.
4. **Scope the legacy path.** Keep `verify_password_or_duress` **only** for the
   separate short duress *codes* (the existing `duress/test/` and heartbeat
   flows), and add an explicit docstring + a serializer guard stating it must
   never receive a master password. Mirrors the fail-closed serializer pattern
   in the ZK plan §1(b).
5. **Delete or fix the tautological test** at `test_duress_code.py:749` — replace
   `hasattr`/`callable` assertions with a real end-to-end unlock test.

#### Tests

- Client-side: real password → slot A; duress password → slot B; wrong → error.
- Contract: no request body on the unlock path contains the master password
  (extend the existing "no plaintext on the wire" contract test).
- Alarm: decoy unlock creates a `DuressEvent` and triggers alarms; normal unlock
  creates neither.
- Indistinguishability: assert request byte-length and endpoint are identical
  for both slots.

### 4.3 Honeypot Emails — schedule the tasks (do this first)

Follow the Time-Lock precedent exactly; it is already proven in this repo.

1. Add a `CELERY_BEAT_SCHEDULE` dict to `security/tasks/honeypot_tasks.py`, with
   entry task strings matching each `@shared_task(name=...)` **exactly** — the
   name mismatch was the original Genetic/DNA beat bug
   (`docs/celery-beat-genetic-task-names-plan.md`). Suggested cadence:
   `scan_all_honeypots` hourly; `process_pending_rotations` every 15 min;
   `analyze_breach_patterns` daily; `cleanup_expired_honeypots` daily;
   `send_breach_digest` weekly; `generate_honeypot_stats` daily.
2. Export it as `HONEYPOT_BEAT_SCHEDULE` from `security/tasks/__init__.py`,
   beside `TIME_LOCK_BEAT_SCHEDULE` (line 127).
3. Merge it in `celery.py` inside the **existing** `@app.on_after_finalize`
   handler — not an eager import. The `celery.py:528-545` comment documents why
   precisely: `security.tasks` pulls in `breach_tasks.py`, which does a
   module-level `from django.contrib.auth.models import User`, which raises
   `AppRegistryNotReady` during `django.setup()`. Extend
   `_merge_time_lock_beat_schedule` (renaming it, e.g. `_merge_feature_beat_schedules`)
   rather than adding a second handler.
4. **Pre-deploy backlog check — mandatory.** These tasks have externally-visible
   effects: `process_pending_rotations` rotates real credentials and
   `send_breach_digest` emails users. Exactly as with Time-Lock
   (`docs/time-lock-beat-schedule-plan.md` §3, and the safety note at
   `celery.py:546-556`), every pending rotation accumulated while the schedule
   was missing will fire in **one batch** on first tick. Add a
   `check_honeypot_backlog` management command mirroring
   `security/management/commands/check_time_lock_backlog.py`, and gate the
   deploy on it.
5. Add a `beat_schedule` registry test mirroring
   `security/tests/test_celery_beat_registry.py` — it already exists to catch
   exactly this class of bug; extend it to cover the honeypot entries so a
   future orphan fails CI.

### 4.4 Out of scope but log as follow-ups

`mesh_deaddrop/tasks/deaddrop_tasks.py:351` and `personality_auth/tasks.py:80`
define `CELERY_BEAT_SCHEDULE` dicts that nothing merges — same orphan bug,
unverified blast radius. Worth their own audit; extending
`test_celery_beat_registry.py` to assert *every* module-level
`CELERY_BEAT_SCHEDULE` is merged would catch all remaining instances at once.

---

## 5. Implementation status

Delivered on `feat/privacy-features-gap-remediation`:

**§4.3 Honeypot scheduling — done.** `CELERY_BEAT_SCHEDULE` added to
`honeypot_tasks.py` (6 zero-arg tasks; the 3 argument-taking ones deliberately
excluded), module imported and re-exported as `HONEYPOT_BEAT_SCHEDULE`, merged
via the existing `on_after_finalize` handler (renamed
`_merge_feature_beat_schedules`). `check_honeypot_backlog` command added,
mirroring the task filters and exiting 1 so a deploy can gate on it. The
`app.finalize()` fix to the registry test also brings PR #483's Time-Lock
entries under real coverage for the first time.

**§4.2 Duress unlock — done, backend + service layer.** New `DuressSignal`
model, `register_signal_token` / `consume_unlock_signal`, and two endpoints:
`duress/signal/register/` and `duress/signal/`. The report endpoint answers
204 for match, no-match, malformed, and error alike. Frontend
`duressSignalService.js` generates the token, registers it, and reports every
unlock with a fixed-length value. `verify_password_or_duress` and
`check_for_duress_code` now document that they must never receive a master
password, and the tautological test is replaced.

**§4.1 Phase 1 Onion sync — done.** `onionSyncService.js` with the three
privacy modes, gating on `vault_proxy.available` (not `anonymity.available`),
failing closed on `require_onion`, and flagging degradation on
`prefer_onion`. Wired into `VaultContext.syncVault`, which now exposes
`syncTransport` / `syncDegraded`. Privacy-vs-speed control added to
`DarkProtocolSettings.jsx` with IP-privacy-only copy. Backend contract test
guards the `vault_sync` route wiring.

**Not delivered — deliberately out of scope for this PR:** §4.1 Phases 2–4
(desktop Tor sidecar, mobile Orbot, anonymous credentials), and the §4.2
`VaultUnlockModal` envelope integration, which needs the two-slot blob to be
provisioned at vault setup — a migration path for existing vaults that
deserves its own PR rather than being bolted onto this one. §4.4 orphan audit
also remains open.

## 6. Acceptance criteria

- [ ] `require_onion` sync fails closed; `prefer_onion` reports honest degradation.
- [ ] `proxyVaultOperation` has real production callers, verified by grep in CI.
- [ ] Desktop routes vault sync over a real Tor circuit end-to-end.
- [ ] Sync privacy UI claims IP privacy only, until Phase 4 lands.
- [ ] Duress password opens the decoy vault from the main unlock modal.
- [ ] No master password ever reaches the server on the duress path (contract test).
- [ ] Duress and normal unlock are byte- and endpoint-indistinguishable.
- [ ] All six schedulable (zero-argument) honeypot tasks appear in
      `app.conf.beat_schedule` at runtime (registry test); the three
      argument-taking fan-out targets stay absent (also asserted by the
      registry test).
- [ ] Honeypot backlog command exists and is run before the scheduling deploy.

---

## 7. Review-fix round 1 on PR #486 (CodeRabbit)

Ten findings (7 actionable, 3 nitpick) plus one failing CI check
(`Dependency Vulnerability Scan`). Verified each critically against the
actual code before changing anything, per instruction — none were taken on
the bot's word alone. All ten held up; none were false positives. Two
(§7.5, §7.6) were more serious on inspection than their own text suggested.

### 7.1 CI failure: expired pip-audit suppressions (unrelated to this PR's code, fixed anyway since it blocks merge)

`PYSEC-2025-195/196/197` (torch advisories) expired 2026-08-20; today is
2026-08-22/23. Checked git blame before renewing: these three had never been
renewed since first added 2026-05-21 — a first renewal, not a repeat, so
within `pip-audit-ignores.txt`'s own policy (flag for a tracking issue only
after *two* renewals with no upstream fix).

Re-verified the reachability argument rather than re-asserting it: re-ran
the grep the neighbouring `CVE-2025-3000`/`PYSEC-2025-194` entries cite
(`jit\.script\|jit\.trace\|torch\.load\|jit\.load`, excluding tests) — still
zero `jit.script`/`jit.trace` call sites. The one `torch.load()` hit
(`ml_dark_web/ml_services.py:294`) loads from the hard-coded
`config.SIAMESE_MODEL_PATH`, never attacker input, already with
`weights_only=True` (PyTorch's own mitigation restricting the unpickler to
tensor data). Renewed to 2026-10-21 (60 days from the renewal date, matching
the precedent set when 194/3000 were renewed 2026-08-11 → 2026-10-10).

### 7.2 Doc: "Two of five need work" contradicted its own table (Minor, confirmed)

The verdict table already marked three rows (10, 12, Honeypot Emails)
incomplete; the prose said two. Also the honeypot task count said "seven"
while listing nine names. Both are pre-existing errors from the initial
verification pass, never corrected when implementation revealed the true
count. Fixed in §0 and §3 above — "Three", and the full nine-task
breakdown (6 schedulable / 3 argument-taking fan-out targets). Acceptance
criterion in §6 corrected to match: "all honeypot tasks" would have been
false for the delivered implementation, since 3 of 9 are deliberately never
scheduled.

### 7.3 `ipware` import inside a `try` the endpoint's own `except Exception` swallows (Trivial, confirmed)

`duress_signal_report` imported `get_client_ip` inside its try block; a
missing/renamed `ipware` package would raise `ImportError`, get caught by
the endpoint's own `except Exception`, and log as an indistinguishable
"Duress signal processing failed" — silently disarming the alarm with no
loud startup failure. Checked the codebase's own convention first:
`security_service.py` and `geofence_views.py` both import `ipware` at
module level; this was the only inline import. Moved to module level.

### 7.4 Missing negative-path test for token deactivation (Trivial, confirmed)

`test_registering_again_deactivates_the_previous_token` asserted the
`is_active` flag flipped, but nothing asserted the flag is actually
*honoured* — that a deactivated token no longer fires. Added
`test_a_deactivated_token_no_longer_fires`.

### 7.5 Duplicate index on `DuressSignal.token_hash` (Trivial, confirmed)

`db_index=True` on the field *and* `models.Index(fields=['token_hash'])` in
`Meta.indexes` — two identical single-column indexes, confirmed in the
generated migration (both `security_du_token_h_...` and a second implicit
one). Since migration `0031_duresssignal.py` was created in this same
unreleased PR and has never been deployed, edited it in place — a follow-up
"remove the duplicate" migration would have been pure churn for something
that never shipped. `makemigrations --check` confirms model and migration
are back in sync.

### 7.6 `duress_signal_report` inherits the shared `UserRateThrottle` (Major, confirmed — and larger than a one-line issue)

Verified `DEFAULT_THROTTLE_CLASSES` in `settings/base.py` includes
`UserRateThrottle` at 60/min in production, keyed by `scope='user'` and
therefore **shared across every endpoint using the default throttle** for
that user — not scoped to this view alone. `duress_signal_report` had no
override, so DRF's `check_throttles()` returns 429 *before this view runs at
all* once a user's combined API traffic crosses that shared budget — which
this endpoint's own docstring says fires on every unlock, and which the
sustained-coercion case explicitly anticipates ("a user under sustained
coercion may unlock repeatedly"). A throttled request breaks the documented
"always 204" contract outright, not just under attack but under ordinary
heavy app use.

Fixed with `@throttle_classes([])`: `IsAuthenticated` already bounds this to
sessions that exist, and each call does at most one small DB filter plus a
digest compare, so there is no new abuse surface from removing the shared
budget. `register` keeps its default throttle unchanged — it fires once per
duress setup, not per unlock, so the shared-budget problem doesn't apply
there. Added `test_report_endpoint_carries_no_throttle`, asserting on the
view's declared `throttle_classes` directly rather than firing 60+ real
requests in a test.

### 7.7 Match path leaked timing (Major, confirmed — the most serious finding)

Verified by reading the call chain: on a match, `consume_unlock_signal` did
`trigger_count` persistence inline, then either created a bare `DuressEvent`
or called `activate_duress_mode`, which can create an `EvidencePackage`,
look up/generate a `DecoyVault`, and — when silent alarms are enabled — call
`SilentAlarmService.send_alerts()`, confirmed to perform blocking `send_mail`
(SMTP) and `requests.post()` (outbound webhook). A non-match returned after
a single digest comparison. That is a real, measurable, network-observable
latency gap on the same endpoint — precisely the oracle this feature exists
to deny an attacker holding the user's session, and it directly contradicted
this PR's own docstring claim of uniform "latency class".

Fixed as CodeRabbit's own sketch suggested: moved everything past the match
determination (trigger_count write, severity fallback, `DuressEvent`
creation, `activate_duress_mode`) into a new Celery task,
`security.activate_duress_signal` (`security/tasks/duress_tasks.py`),
dispatched via `.delay()` and registered in `security/tasks/__init__.py`
following the exact "submodule must be explicitly imported to register"
pattern already established there for Dark Protocol and Honeypot (§3 above)
— `.delay()` on the calling side doesn't need local registration to enqueue,
but a worker that never imported the module would raise `NotRegistered`
when it tried to run the task. `consume_unlock_signal` now does identical
synchronous work on match and non-match: the constant-time digest loop, then
either nothing or one lightweight enqueue call.

Test-level consequence: this codebase's own test settings use `memory://`
for `CELERY_BROKER_URL` with tasks never executed under `.delay()` in tests
(documented in `settings/base.py`, "matching existing behaviour"), so the
four tests that used to assert on `consume_unlock_signal`'s sync side
effects were restructured — moved to a new `DuressSignalActivationTaskTests`
class that calls the task via `.apply()` (same pattern already used by
`ml_dark_web/tests/test_check_compromised_passwords.py` for a bound task).
Added two structural regression tests on the service method itself:
`test_matching_signal_fires_but_defers_the_work` (mocks `.delay`, asserts no
synchronous DB writes) and `test_matching_signal_never_calls_activate_duress_mode_inline`
(asserts `activate_duress_mode` is never called from the request thread) —
deterministic, not timing-based, so they can't be flaky in CI the way a
wall-clock assertion would be.

### 7.8 `process_pending_rotations` re-emails the same stale rotation every tick (Major, confirmed)

The task's own filter (`status='pending', initiated_at__lt=now-24h,
user_confirmed=False`) has no lower bound and no delivery-state tracking —
confirmed by reading the full task body. Scheduled at 15 minutes (this PR's
original choice), a single stale rotation would receive a reminder email
every 15 minutes, forever, until the user confirms — up to 96 emails/day.
The task itself is pre-existing code this PR didn't author, so adding
persisted delivery state (CodeRabbit's primary suggestion) would mean a new
model field and migration — out of scope for a review-fix round on a PR
whose job was wiring up scheduling, not redesigning the task. Took
CodeRabbit's own stated alternative instead: rescheduled to daily (86400s),
matching the 24h staleness window already baked into the query, so nothing
goes un-reminded but nothing is spammed either. Corrected an inaccurate
comment in the same block while there: it said the task "rotates real
credentials"; re-reading the task body confirms it only sends reminder
emails and never rotates anything itself.

### 7.9 `send_breach_digest` scheduled weekly against a 24h query window (Minor, confirmed)

The task's own docstring says "Send **daily** breach digest" and its query
is `detected_at__gte=now-24h`. This PR's original weekly schedule meant any
breach detected more than 24h before the weekly tick fell outside that
window permanently — not delayed, silently skipped forever, for the
majority of breaches in a 7-day cycle. Rescheduled to daily (86400s),
matching the task's own stated design.

### 7.10 Test results

Targeted re-run after all fixes above:
`security/tests/test_duress_signal.py` — 22 passed (up from 17: added
`test_a_deactivated_token_no_longer_fires`,
`test_matching_signal_never_calls_activate_duress_mode_inline`,
`test_report_endpoint_carries_no_throttle`, and the
`DuressSignalActivationTaskTests` class replacing the four tests that used
to assert on now-deferred side effects). `makemigrations --check` confirms
`DuressSignal` model/migration parity after the index fix. Per the
project's own testing guidance (targeted tests during iteration; full suite
once a feature is stable — the same discipline
`docs/time-lock-beat-schedule-plan.md` and
`docs/celery-beat-genetic-task-names-plan.md` document round-by-round), a
full backend/frontend suite run was deferred to the end of this round rather
than re-run after each individual finding.
