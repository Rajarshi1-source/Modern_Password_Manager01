# Plan — Close the gaps in 5 privacy/anti-forensics features

Verification performed on `main` @ `5e43b1d`. Every claim below was checked
against the code, not inferred from filenames or docs. This scoping applies to
§§0-6, the gap analysis and delivery plan; §7 onward (the review-fix rounds)
are each verified against the PR branch at their own commit, named in that
round's own text.

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

Consequence: the original feature brief's own claims — "detects breaches
instantly", "automatically rotates real credentials" — **never happened**, and
neither did the breach digest. Alias activity was only ever polled if
something called the task by hand. Both of those are the BRIEF's language,
not the code's: the implemented `process_pending_rotations` only ever sends a
reminder EMAIL for a stale rotation, and never rotates any credential itself
— see §7.8 of the round-1 review-fix log below, where a scheduling mismatch
this PR itself introduced surfaced that same distinction the hard way.

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
   - `getSyncPrivacyMode()` / `setSyncPrivacyMode(mode)` reading/writing
     `localStorage` directly (a device-local transport preference, not
     account state — the delivered implementation does not route this
     through `preferencesService`, unlike the original draft of this plan),
     with modes `'off' | 'prefer_onion' | 'require_onion'` (default `'off'`,
     preserving today's behaviour).
   - `syncVault(syncData)` that:
     - `'off'` → delegate to `vaultService.syncVault` unchanged;
     - `'prefer_onion'` → call `darkProtocolService.getCapabilities()`; if
       `vault_proxy.available` (the backend's own
       `anonymity_active AND request-arrived-over-onion-ingress` computation
       — gate on this single server-derived field, not on
       `anonymity_active`/`current_connection_is_anonymous` recombined
       client-side, which is what the delivered implementation actually
       does and is the stronger contract: the client cannot get this wrong
       by checking the two halves differently than the server does), call
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
   `scan_all_honeypots` every 30 minutes; `process_pending_rotations` daily;
   `analyze_breach_patterns` daily; `cleanup_expired_honeypots` daily;
   `send_breach_digest` daily; `generate_honeypot_stats` daily. (Originally
   proposed as 15 min / weekly for these last two, and hourly for the
   first; all three were tried during implementation and found wrong — see
   §7.8/§7.9 of the round-1 review-fix log for the middle two, and §12.5 of
   the round-6 log for `scan_all_honeypots` (its own docstring says "every
   15-30 minutes", which hourly violated) — corrected here so this plan
   doesn't keep pointing a future reader at values already proven to spam,
   to silently drop breaches, or to run outside the task's own contract.)
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
   effects: `process_pending_rotations` sends a reminder EMAIL for each stale
   rotation (it does not itself rotate any credential — corrected here after
   the original draft of this line got that wrong) and `send_breach_digest`
   emails users. Exactly as with Time-Lock
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
`duressSignalService.js` generates the token, registers it, and reports
supported embedded-vault unlocks through `StegoVaultDashboard.jsx` with a
fixed-length value -- not yet wired into the main `VaultUnlockModal` flow,
see "Not delivered" below. `verify_password_or_duress` and
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

- [x] `require_onion` sync fails closed; `prefer_onion` reports honest degradation
      (`onionSyncService.test.js`: `test_fails_closed_rather_than_downgrading`,
      `test_falls_back_to_clearnet_but_flags_the_downgrade`).
- [x] `proxyVaultOperation` has a real production caller
      (`onionSyncService.syncVault` → `darkProtocolService.proxyVaultOperation`,
      wired into `VaultContext.syncVault`). Reworded from the original draft,
      which claimed this was "verified by grep in CI" — no such CI step was
      ever added; this was confirmed by direct inspection instead, which is
      what actually backs the checkmark.
- [ ] Desktop routes vault sync over a real Tor circuit end-to-end. (Phase 2,
      explicitly out of scope for this PR — see §5.)
- [x] Sync privacy UI claims IP privacy only, until Phase 4 lands
      (`DarkProtocolSettings.jsx`: "hides your IP address", never "the server
      can't identify you", including in the mode-dependent copy added in
      round-2 review fixes).
- [ ] Duress password opens the decoy vault from the main unlock modal.
- [ ] No master password ever reaches the server on the duress path (contract test).
- [ ] Duress and normal unlock are byte- and endpoint-indistinguishable.
- [x] All six schedulable (zero-argument) honeypot tasks appear in
      `app.conf.beat_schedule` at runtime (registry test); the three
      argument-taking fan-out targets stay absent (also asserted by the
      registry test) --
      `test_celery_beat_registry.py::CeleryBeatScheduleRegistryTests::test_honeypot_entries_resolve`
      and `::test_argument_taking_honeypot_tasks_stay_unscheduled`.
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

---

## 8. Review-fix round 2 on PR #486 (CodeRabbit, second pass)

Eleven findings (10 actionable, 1 nitpick), verified critically before
changing anything. All eleven held up; none were false positives. Two are
worth highlighting because they identify a real class of bug this whole PR
exists to fix — and round 2 found an instance of it *inside this PR's own
round-1 fix*.

### 8.1 `activate_duress_signal_task.delay()` was still match-dependent (Major, confirmed — the most serious finding of round 2)

Round 1 moved the *activation* work off the request thread, but
`consume_unlock_signal` still ran the digest-comparison loop synchronously
and called `.delay()` **only on a match**. CodeRabbit ran an actual web
query to confirm the underlying Celery fact rather than asserting it:
`Task.delay()`/`apply_async()` synchronously publish the task message to the
broker before returning — real network I/O, not free. So whether that
publish happened at all was itself a smaller but real, still match-dependent
timing signal, which is exactly the property round 1's own docstring set out
to eliminate ("ANY observable difference... would hand a coercer a way to
test"). By that self-imposed bar, this was a genuine regression-in-miniature
of the same bug round 1 fixed.

Fixed by moving the match determination itself into the task, not just the
activation that follows it: `consume_unlock_signal` now enqueues
`activate_duress_signal_task` **unconditionally**, passing the raw signal;
the digest loop and everything downstream of a match now run entirely
inside the task, which is invisible to the HTTP response either way. The
request thread's own work is now identical no matter what the signal turns
out to be — one `.delay()` call, full stop.

Consequence for tests: `consume_unlock_signal` can no longer report whether
a signal matched (nothing on the request thread determines that anymore),
so its return value changed from `bool` to `None`, and the four service-level
tests that asserted match/no-match behavior moved to
`DuressSignalActivationTaskTests` (which now takes `user_id, signal` and does
its own lookup, rather than `signal_id`). Added
`test_consume_unlock_signal_always_enqueues_identically`, asserting `.delay()`
receives the exact same argument shape for a matching and a non-matching
token — the direct regression test for this finding.

### 8.2 `reportUnlockForSlot` had zero production callers (Major, confirmed — the second instance of the pattern)

CodeRabbit's own investigation (ripgrep across `frontend/src`, an AST-based
call-site verifier script, tracing `StegoVaultDashboard.jsx`'s decode flow)
found that `reportUnlockForSlot` — the client function that reports a duress
unlock to the server — was called from nowhere in production. Verified
independently with the same grep: confirmed zero hits outside the service
and its own test file. `StegoVaultDashboard.jsx`'s `onExtract` calls
`extractVault` (the actual `HiddenVaultBlob` decode — per §2.4 above, the
*only* place in the frontend this decode happens today) and got `slotIndex`
back, but never told the server anything about it.

This means the entire server-side duress-signalling feature — fully built,
fully tested across two rounds of review fixes — was unreachable from any
real user action. It is the identical defect class this whole PR exists to
close (built the backend, never wired the caller — see the Honeypot Emails
and Onion Sync findings in §1–§3 above), reproduced by this PR's own author
inside the very code meant to fix instances of it elsewhere.

Fixed by calling `reportUnlockForSlot(getAccessToken(), slotIndex, json)`
after every successful extract in `onExtract`, using the same
`useAuth().getAccessToken()` pattern already established in
`DuressCodeSetup.jsx`. Not the same thing as wiring the master-password
`VaultUnlockModal` (still correctly out of scope — see §5's "Not delivered"
list): `StegoVaultDashboard` is a separate, already-shipped feature page, and
this closes the one gap in it that this PR's own new service left open.

### 8.3 `register_signal_token` had no protection against concurrent registration (Major, confirmed)

`DuressSignal.objects.filter(is_active=True).update(is_active=False)`
followed by `.create()`, both inside one `transaction.atomic()` block, is
not atomic against a *second* concurrent caller: under READ COMMITTED, two
transactions racing on the same user's first-ever registration can each see
zero existing active rows (neither has committed its `INSERT` yet when the
other's `UPDATE` runs), so both insert a new active signal and the user ends
up with two.

Fixed with `select_for_update()` on the user's `DuressCodeConfiguration` row
— a pre-existing `OneToOneField`-unique-per-user row, so no new migration or
constraint was needed; the second concurrent call simply blocks until the
first commits. CodeRabbit's own suggested fix (a conditional
`UniqueConstraint` plus catching the resulting `IntegrityError`) would also
have worked but needs a schema migration and after-the-fact race handling;
locking a row that already exists precisely because it's per-user, then
deciding whether it's still worth doing given "keep changes minimal",
resolves the same race without either. Added
`RegisterSignalTokenConcurrencyTests` (a `TransactionTestCase` with real
threads via `ThreadPoolExecutor`), mirroring the exact pattern already
established in `test_adaptive_policy_bandit.py::ArmCeilingConcurrencyTests`
— including the SQLite skip, since `select_for_update()` needs real MVCC row
locking that SQLite doesn't provide (it serializes writers at the file
level instead), so this genuinely validates only against CI's Postgres.

### 8.4 Doc drift, five instances (Minor, all confirmed)

- §3's "Consequence" paragraph read as a factual claim that
  `process_pending_rotations` rotates credentials; it was meant as a quote of
  the *original feature brief's* language, but read ambiguously either way.
  Reworded to attribute it explicitly to the brief and state the actual
  behavior (reminder emails only).
- §4.3 step 4 (pre-deploy backlog check) had the same "rotates real
  credentials" error, this time as a direct technical claim with no
  brief-quoting excuse. Corrected.
- §4.3's "Suggested cadence" list still proposed 15 min /
  weekly for `process_pending_rotations`/`send_breach_digest` — the exact
  values §7.8/§7.9 had already found wrong during implementation. A future
  reader following the plan section literally would reintroduce the bug
  those sections fixed. Corrected to daily/daily with a pointer to why.
- §4.1 Phase 1's spec said the gate was
  `anonymity_active && current_connection_is_anonymous`; the delivered
  implementation (§5) correctly gates on the backend's own single
  `vault_proxy.available` field instead — a stronger contract, since the
  client can't get it wrong by recombining the two halves differently than
  the server does. Updated the plan to describe what was actually built.
- §6's acceptance checklist had four items already delivered per §5 but
  left unchecked. Checked off three (`require_onion`/`prefer_onion`
  behavior, `proxyVaultOperation` having a real caller, IP-only UI copy),
  correcting the second one's wording along the way — it claimed a
  grep-based CI verification step that was never actually built; the
  checkmark is backed by direct inspection instead, which is what actually
  supports it. Left the desktop-Tor-circuit item unchecked, correctly, since
  that's Phase 2 and still out of scope.

### 8.5 Sync-privacy UI copy claimed onion routing unconditionally (Minor, confirmed)

The description under the sync-privacy dropdown was static regardless of
`syncPrivacyMode` — including when the mode is `'off'` (the default!), where
sync never touches Tor at all, and `'prefer_onion'`, which can silently fall
back to clearnet. Claiming "routes through Tor" in either case is exactly
the false privacy promise this feature exists to avoid. Made the copy
mode-dependent (three variants), preserving the "IP privacy only, never
identity" framing in every one — see §6's now-checked acceptance criterion.

### 8.6 `syncTransport` initialized to `'clearnet'` before any sync ran (Minor, confirmed)

`'clearnet'` reads as "the last sync used the normal connection," which is
false before any sync has happened at all — no sync means no transport, not
an implicit clearnet one. Changed the initial value to `'none'`, already a
valid value in this field's own contract (used for the `require_onion`
refused-before-sending case).

### 8.7 Two `# nosec B106` suppressions should be `# noqa: S106` (Trivial, confirmed but low-stakes)

CodeRabbit's own scanner runs Ruff; this project's actual CI gate is
Bandit (`.github/workflows/ci.yml`), which excludes `tests/` entirely
(`-x tests,venv`) and ignores its own exit code (`|| true`) — so neither
suppression form is ever CI-checked either way. Fixed anyway since the
change is free and this repo has no Ruff config of its own, meaning
CodeRabbit's scanner is the only thing that will ever read these comments.
Fixed exactly the one occurrence CodeRabbit flagged
(`test_check_honeypot_backlog_command.py:33`) plus the equivalent new
occurrences introduced in this same round's own test edits — deliberately
not a repo-wide sweep of the many pre-existing `# nosec B106` occurrences
elsewhere, which is out of scope for "keep changes minimal."

### 8.8 Nitpick: `test_no_password_field_is_accepted_anywhere_in_this_flow` posted an unrelated token (Trivial, confirmed)

The test posted `make_token()` (fresh, unrelated) as `signal` alongside the
extra `password` field, so it never actually exercised the path where a
match occurs — it "proved" the password field changes nothing while the
signal itself could never have matched regardless. Fixed to post the
actually-registered token, mock `.delay`, and assert both that it fires
exactly once and that `password` never reaches the task's arguments —
adapted for the §8.1 redesign (matching moved into the task, so the
strongest assertion available at this layer is "the extra field never
leaks into what gets enqueued," not "no alarm fires," which round 1's
version had checked).

### 8.9 Test results

`security/tests/test_duress_signal.py` — 24 passed, 1 skipped (the new
concurrency test, correctly skipped under SQLite; runs against CI's
Postgres). `security/tests/test_check_honeypot_backlog_command.py` —
unaffected by the suppression-comment change, re-run to confirm. Frontend:
`duressSignalService.test.js` (14) and `onionSyncService.test.js` (16)
unaffected by the wiring/copy changes, both re-run to confirm — 30 passed.
ESLint clean on all four touched frontend files (one real error caught and
fixed: an unescaped apostrophe introduced by this round's own new JSX copy,
`react/no-unescaped-entities`).

---

## 9. Review-fix round 3 on PR #486 (CodeRabbit, third pass)

Eight findings (7 actionable, 1 nitpick), verified critically before
changing anything. Seven held up and were fixed; one (`get_user_model()`)
was checked against this project's actual settings and found not to apply —
skipped, with the reasoning recorded rather than silently ignored.

### 9.1 Decoy vaults created via `StegoVaultDashboard` never had a duress token to release (Major, confirmed — a third instance of "built the caller, forgot the other half")

`onEmbed` passed the user's raw `decoyVaultJson` straight to `embedVault`
with no `__duress_signal` field ever added. Round 2 wired `onExtract` to
*read* `payloadJson.__duress_signal` and report it — but nothing had ever
*written* that field into a decoy payload created through this dashboard, so
every decoy vault made here would decode successfully on its decoy password
and still release indistinguishable noise, never the real alarm token. Two
built halves of the same feature, wired to each other, with the third half
(provisioning) missing — found by CodeRabbit tracing the actual data flow
from `onEmbed` through to what `onExtract` reads.

Fixed by generating and registering a token inside `onEmbed`, exactly when a
decoy vault and decoy password are both being set up, and injecting it into
the decoy payload only:
`decoyPayload = { ...decoyVault, __duress_signal: duressToken }`. The real
vault payload is never touched, so there is no alarm-shaped field for anyone
inspecting the real slot to find. Also fixed, since CodeRabbit's own
recommendation called it out explicitly: `extractResult` — the raw JSON
`JSON.stringify`'d onto the screen after a successful extract — would have
displayed the literal token value on a decoy unlock, which is exactly the
kind of thing a coercer watching the screen would notice. Stripped before
render, reported (from the untouched payload) before that.

### 9.2 `@throttle_classes([])` removed every limit, not just the one that broke the 204 contract (Major, confirmed)

Round 1 correctly removed the shared `UserRateThrottle` from
`duress_signal_report` because it could return a 429 before the view even
ran. What that left behind: no limit at all. Since round 2 made
`consume_unlock_signal` enqueue a Celery task on literally every accepted
call, an authenticated session hammering this endpoint could generate
unbounded broker publishes and worker task executions — and, on whichever
call happens to carry a real matching signal, unbounded full activations:
repeated evidence packages, repeated decoy-vault generation, repeated real
SMTP/webhook alerts to trusted authorities.

Fixed with a silent, per-user cap (`_within_report_budget`) called from
inside the view body rather than registered as a DRF throttle class — a
`BaseThrottle` subclass wired via `@throttle_classes([...])` would still
trigger DRF's own automatic 429 the moment `allow_request()` returns False,
which is the exact behavior round 1 removed this mechanism to avoid. Uses
the *dedicated* `'rate_limiting'` cache alias and the atomic
add-then-increment pattern already established in
`ai_assistant/services/claude_service.py::_check_rate_limit` — not a new
pattern invented for this fix. 60/min, **dedicated to this one endpoint**,
not shared with the rest of the API the way the removed `UserRateThrottle`
was; that distinction is what makes this safe to add back without
reintroducing the original problem (a legitimate high-frequency unlock
session getting starved by unrelated API traffic). The gate depends only on
request rate, never on the signal itself, so it cannot become a second
match/no-match oracle in place of the one round 1 closed.

### 9.3 `max_retries=2` was dead configuration (Major, confirmed via CodeRabbit's own Celery doc lookup)

CodeRabbit ran an actual query against Celery's docs to confirm:
`max_retries` alone does nothing without `self.retry()` or `autoretry_for`
somewhere in the task body. Neither existed. `bind=True` was equally dead —
`self` was never referenced anywhere in the task. The three parameters
together implied a retry guarantee the task never actually had; an uncaught
exception always failed the task outright, exactly as it does now with them
removed.

Deliberately did NOT add real retry logic instead, which was CodeRabbit's
own alternative suggestion — and its own severity tag agreed this is a
"heavy lift", not a quick fix: `activate_duress_signal_task` creates a
`DuressEvent`, may create an `EvidencePackage` and a decoy vault, and may
call `SilentAlarmService.send_alerts()` (real outbound SMTP/webhook, not a
side effect that's safe to run twice). A naive retry on transient failure
risks re-running all of that and double-sending a genuine alert to trusted
authorities during an actual emergency — a worse outcome than the failure
being retried. Idempotent activation is real, separately-scoped follow-up
work; removing the misleading configuration is the correct minimal fix
*for this PR*.

### 9.4 `trigger_count` incremented via Python read-modify-write (Minor, confirmed via CodeRabbit's own Django doc lookup)

`matched.trigger_count += 1` then `.save(update_fields=[...])` is a lost-
update race: two tasks processing matching reports for the same signal
close together can each read the same starting count and each write back
the same incremented value, silently losing one increment. Fixed with
`DuressSignal.objects.filter(pk=matched.pk).update(trigger_count=F('trigger_count') + 1, ...)`,
which performs the increment atomically in the database. `matched` (the
in-memory instance) is not read again afterward in this task, so no
`refresh_from_db()` was needed to keep it in sync — confirmed by reading the
rest of the function body before deciding that, not assumed.

### 9.5 `get_user_model()` — checked, found not to apply (Major claim, verified invalid for this codebase)

CodeRabbit's own investigation was explicitly conditional: "if custom users
are supported, update...". Checked directly: `grep -rn "^AUTH_USER_MODEL"
password_manager/password_manager/settings/*.py` returns nothing — this
project never overrides Django's default user model, and every other model
in `duress_models.py` (including `DuressSignal.user` itself) already
hardcodes `django.contrib.auth.models.User` the same way the task does.
CodeRabbit's own text said "a task-only change is insufficient" — i.e., it
did not even recommend doing just this. Not fixed: there is no real
inconsistency to resolve, and changing only this one file would make it the
one place in the codebase inconsistent with the (unanimous, if debatable)
convention everywhere else.

### 9.6 Two trivial Ruff-suppression cleanups (confirmed, same reasoning as round 2 §8.7)

Four `_out` renames in `test_check_honeypot_backlog_command.py` (Ruff
RUF059, unused unpacked variable — verified each of the 4 flagged lines
genuinely never reads `out` afterward, unlike 5 sibling lines in the same
file that do and were correctly left alone) and five more
`# nosec B106` → `# noqa: S106` conversions in `test_duress_signal.py`
(sites this round's own new tests had reintroduced, plus ones round 2
missed within the same file). Same CI-irrelevance caveat as round 2: this
project's actual gate is Bandit, which excludes `tests/` and ignores its
own exit code either way.

### 9.7 Nitpick: stale docstring cross-reference (confirmed, trivial)

`DuressSignal`'s "why a plain SHA-256" rationale still named
`consume_unlock_signal` as where the constant-work comparison runs — true
before round 2, false after (§8.1 moved the comparison into
`activate_duress_signal_task`). Corrected the reference.

### 9.8 Test results

`security/tests/test_duress_signal.py` — added
`DuressSignalReportRateLimitTests` (4 new tests covering the §9.2 rate cap:
within-budget, over-budget, per-user isolation, and the silent-204
end-to-end check) on top of the existing 24 passed / 1 skipped from round 2.
`security/tests/test_check_honeypot_backlog_command.py` — unaffected by the
`_out` rename, re-run to confirm. `python -m py_compile` clean on all five
touched backend files before running tests. ESLint clean on both touched
frontend files.

---

## 10. Review-fix round 4 on PR #486 (CodeRabbit, fourth pass)

Seven findings (6 actionable, 1 filed as a nitpick — §10.1, which turned out
Major on inspection rather than staying minor), verified critically before
changing anything. All seven held up and were fixed. No CI check was failing
this round — the check fixed in round 1 (`Dependency Vulnerability Scan`)
was green throughout, but this round's nitpick found the round-1 renewal had
itself been incomplete, so it is logged here as a correction, not a new
failure.

### 10.1 Nitpick, upgraded on inspection: the round-1 torch renewal never checked whether pip-audit still raised the IDs at all (Trivial claim, Major in practice)

CodeRabbit's claim: `PYSEC-2025-195/196/197`'s vulnerable version ranges end
below this project's actual torch minimum (`>=2.12.0` in `requirements.txt`,
locked to exactly `2.12.0` in `requirements-lock.txt`), so the suppressions
are simply stale. Verified directly against the tool itself rather than
trusted: `pip-audit -r <torch==2.12.0>` reports exactly one torch finding —
`PYSEC-2025-194`/`CVE-2025-3000`, already suppressed separately — and 195,
196, 197 do not appear at all.

This is a real gap in round 1's own renewal, not just a stale-suppression
tidy-up: round 1 re-verified the *reachability argument* (no
`jit.script`/`jit.trace` call sites, the one `torch.load()` hit uses
`weights_only=True` on a hard-coded path) but never checked whether
pip-audit would raise these three IDs against the pin *at all* — it should
have, and the omission would have repeated at every future renewal round
had it gone uncaught. Removed the three entries, following the exact
"REMOVED, not renewed" pattern this file already uses for other IDs that
turned out not to apply (see the pyjwt/joblib/Twisted entries near the top).

Noted but NOT acted on: the same `pip-audit -r` query suggests
`PYSEC-2025-210`/`PYSEC-2026-139` (the block's remaining two torch entries)
might be similarly stale — they were not in the query's output either. Not
flagged by CodeRabbit this round, and their `exp:2026-08-25` dates were not
expired at time of writing, so removing them now would be scope beyond what
was actually raised. Worth checking at their own next renewal.

### 10.2 Doc drift: plan described a storage mechanism that isn't what shipped (Minor, confirmed)

§4.1 step 1 said `getSyncPrivacyMode()`/`setSyncPrivacyMode()` go "over the
existing `preferencesService`". Verified against `onionSyncService.js`:
both read/write `localStorage` directly; `preferencesService` is never
imported. Updated the plan to describe the delivered device-local
preference contract instead of the originally-drafted one.

### 10.3 `StegoVaultDashboard.onEmbed` registered the duress token before confirming the embed would succeed (Major, confirmed)

`registerSignalToken` deactivates the user's previous active signal as part
of installing the new one — and `embedVault` is a pure client-side PNG
encode with no guarantee of success (cover-image capacity, corrupt bytes,
etc.). Registering first meant a failed embed would deactivate whatever
decoy vault the user already had *working*, leaving the new token
registered server-side with no PNG anywhere that actually embeds it — a
silent, invisible breakage of existing duress protection triggered by an
unrelated encode failure. Fixed by generating the token before the embed
(it needs to be embedded in the payload) but registering it only after
`embedVault` resolves successfully, immediately before the file is
exported — exactly the ordering CodeRabbit's own diff proposed.

### 10.4 `syncDegraded`/`syncTransport` were tracked but never rendered anywhere (Minor, confirmed — a fourth instance of the recurring pattern)

Verified via grep: zero references to either field outside
`VaultContext.jsx` itself. The state was added in §5's Phase 1 delivery
specifically "so the UI can be honest" about a `prefer_onion` fallback to
clearnet, but with no consumer, the UI was exactly as silent about the
downgrade as it would have been with no tracking at all — the false-
privacy-promise gap moved from "reports success" to "reports nothing",
which is not actually progress.

Deliberately did NOT build new UI infrastructure for this: `syncStatus`
itself (a field that predates this entire PR) has never been rendered
anywhere in the app either, so a dedicated sync-status banner/badge would be
new surface area disproportionate to a Minor finding. Instead reused the
existing `error` field from `useVault()`, already rendered in several places
in `App.jsx` — on a degraded sync, `setError()` now carries a non-alarming,
clearly-not-a-failure message ("Vault synced, but not through the private
onion route you requested...") instead of being unconditionally cleared to
`null`. Minimal: one conditional replacing one unconditional call, no new
component, no new state.

### 10.5 `_within_report_budget` did not fail open on cache backend errors (Major, confirmed via CodeRabbit's own django-redis doc lookup)

Verified this project sets no `IGNORE_EXCEPTIONS` anywhere (`grep -rn
"IGNORE_EXCEPTIONS" password_manager/password_manager/settings/*.py` →
nothing), and CodeRabbit's own doc lookup confirms django-redis re-raises
connection errors by default without it. `_within_report_budget` is called
from inside `duress_signal_report`'s own `if` condition, **before** the
view's `try/except` begins (confirmed by reading the exact call site) — so
an uncaught cache backend exception (Redis unreachable, connection pool
exhausted, etc.) would propagate straight past the view, breaking the
"always 204" guarantee this endpoint exists to provide, exactly the class
of regression §9.2 introduced this mechanism to prevent in the first place.

Fixed by wrapping the cache operations in a broad `except Exception` that
fails OPEN (returns `True`, i.e. "within budget, proceed") — kept distinct
from the existing `except ValueError` handling for the documented "key
expired between add() and incr()" case, which is normal cache behaviour,
not a backend failure. A rate limiter must not be the reason this endpoint
stops answering 204.

### 10.6 `check_honeypot_backlog` loaded and printed an unbounded backlog (Major, confirmed)

The command's own query has no historical lower bound — read literally, a
large enough backlog (a badly out-of-sync production system, not the
one-time pre-deploy check this tool was designed for, but not impossible)
would load every matching row into memory via `list(...)` and print every
one to stdout, which lands in cluster log aggregation per the file's own
existing privacy comment. Fixed with a bounded sample: the summary count is
now a cheap `.count()` on the full queryset (the TRUE total, never
truncated), while the per-row detail section is capped at
`MAX_ROTATION_SAMPLES = 100` (the longest-pending rows, via
`.order_by('initiated_at')`) with an explicit "... and N more" notice when
the total exceeds the sample — so the report is always numerically accurate
even when it can't enumerate every row. Added
`test_large_backlog_reports_true_total_and_truncates_the_sample`, creating
`MAX_ROTATION_SAMPLES + 7` rows via `bulk_create` and asserting the summary
shows the true total while exactly `MAX_ROTATION_SAMPLES` detail rows print.

### 10.7 `DuressSignalAPITests` had the identical cache-isolation gap `DuressSignalReportRateLimitTests` was fixed for in round 3 (Minor, confirmed)

Same root cause as §9's own fix, in a sibling class round 3 didn't touch:
Django's `TestCase` reuses auto-incremented user PKs across test methods
(transaction rollback resets the sequence), and the `'rate_limiting'` cache
is process-wide, not covered by that rollback. If
`DuressSignalReportRateLimitTests` (which deliberately exhausts a user's
budget) runs before `DuressSignalAPITests` and both happen to reuse the
same numeric PK, a leaked counter would make
`test_no_password_field_is_accepted_anywhere_in_this_flow`'s
`mock_delay.assert_called_once()` fail for a reason unrelated to what it
actually tests. Today's alphabetical test ordering happens to avoid it, but
that's incidental, not a guarantee — `--reverse`, parallel runners, or a
class rename would all break it. Added the identical `caches['rate_limiting'].clear()`
call to this class's `setUp`, matching round 3's fix exactly.

### 10.8 Test results

`security/tests/test_duress_signal.py` and
`security/tests/test_check_honeypot_backlog_command.py` (the latter with
one new test for §10.6) re-run to confirm; full frontend suite (711 tests)
re-run to confirm the `StegoVaultDashboard`/`VaultContext` changes.
`python -m py_compile` clean on all four touched backend files. ESLint
clean on both touched frontend files. `pip-audit-ignores.txt` re-validated
locally against the exact CI parser logic after the §10.1 removal.

## 11. Review-fix round 5 on PR #486 (CodeRabbit, fifth pass)

Six findings (5 actionable, 1 nitpick), verified critically before changing
anything. All six held up in some form; two of the "Major" security findings
were real but narrower than the headline claim once checked against this
project's actual Celery defaults and test isolation, so the fix was scoped to
what the verification actually supported rather than the broadest version of
the suggested change. No CI check was failing this round.

### 11.1 `_within_report_budget` could be exhausted by an attacker to silently suppress a genuine duress report (Major, confirmed)

CodeRabbit's claim: since the per-user report budget counts every
well-formed report regardless of content (it has to -- see the function's own
docstring on why it cannot look at the signal), an attacker who already holds
the user's session (this endpoint's own stated threat model) can post 60
throwaway 44-char values to exhaust the window, then the coerced user's real
duress unlock in that same window gets silently dropped: nothing queued,
nothing retried, still 204.

Confirmed by reading `duress_signal_report` and `_within_report_budget`
directly (`security/api/duress_code_views.py`): the over-budget branch
returns `False` unconditionally, and the caller skips the enqueue entirely on
`False` with no fallback. This is exactly the failure mode the feature exists
to prevent, reachable by the adversary the docstring already assumes.

Implemented CodeRabbit's own first suggested option (a small reserved
allowance the over-budget path may still consume) rather than the second
(coalescing multiple reports into one delayed enqueue): coalescing would mean
the LATEST report in a window wins, which does not help if the attacker's
flood continues *after* the real signal, and required a new delivery
mechanism (nothing today flushes a coalesced value except the next request)
that was a larger, less bounded change for the same guarantee. Added a
second, independently-keyed counter (`duress_signal_report_reserve_{user_id}`,
same atomic `cache.add()` claim pattern as the primary counter) that always
allows exactly one more report through every
`_REPORT_RESERVE_WINDOW_SECONDS` (5s), regardless of how exhausted the
primary 60/min budget is. This does not make suppression impossible -- no
undifferentiated rate limit can, since the endpoint cannot tell real signal
from noise without first doing the timing-sensitive work the whole design
exists to avoid on the request thread. **Correction, round 8 (§14.3): this
paragraph originally claimed the reserve "bounds the worst case... to at
most ~5s" — wrong for a continuously-flooding attacker, who can keep
winning the single reserve slot in every window indefinitely. See §14.3 for
what this mechanism actually guarantees.** At the cost of a small, fixed
amount of extra worker load (at most 12 additional enqueues/min/user).
Updated `test_exceeding_budget_returns_false` and
`test_over_budget_report_still_returns_204_and_skips_the_enqueue` (both
previously asserted the request immediately after the primary budget was
exhausted; that request now consumes the reserve slot instead) and added
`test_reserve_survives_budget_exhaustion`.

### 11.2 `activate_duress_signal_task.delay()` has no explicit broker connection/publish bound (Major, confirmed but narrower than framed)

CodeRabbit's claim, as framed: no `broker_transport_options` or connection
timeout is configured anywhere in this project, so a broker outage could
block the unlock response "indefinitely."

Verified the "no explicit config" half directly: grepped
`password_manager/settings/base.py` and `password_manager/celery.py` for
`broker_transport_options`/`broker_connection_timeout`/`BROKER_TRANSPORT_OPTIONS`
-- neither appears anywhere in this project. But "indefinitely" overstates
Celery 5.6.3's actual behaviour: `broker_connection_timeout` defaults to
4 seconds (not unset/unbounded), and this project's own `TESTING` settings
block already documents the real number empirically --
`password_manager/settings/base.py` around `CELERY_BROKER_URL = 'memory://'`
notes "every task .delay()/.apply_async() blocks ~4.2s on a broker connect
before OperationalError" when Redis is absent, which is exactly the
connection-timeout default at work, not an infinite hang. Layered on top,
Celery's default publish-retry policy adds up to 3 more attempts, so the
real worst case today is roughly 4s × up to 4 attempts ≈ mid-teens of
seconds, not unbounded -- still far too slow for an endpoint whose entire
design is to answer 204 promptly no matter what (see
`duress_signal_report`'s own docstring), but not the crash/hang CodeRabbit's
phrasing implied, and the response was never at risk of erroring: the view
already wraps this call in its own `try/except` and answers 204 regardless
of what the publish does.

Fixed by switching this one call from `.delay()` to `.apply_async(kwargs=...,
retry=True, retry_policy={'max_retries': 1, 'interval_start': 0,
'interval_step': 0.1, 'interval_max': 0.1})` -- scoped to this call site via
the per-call `retry_policy` argument rather than a project-wide
`broker_transport_options` change in `celery.py`, which would also alter
publish-retry behaviour for every other task in this large codebase (blockchain
anchoring, ML pipelines, breach scans, etc.) for a latency concern specific to
one endpoint. This does not touch `broker_connection_timeout` itself (that is
an app-level, not a per-call, setting, and 4s is already Celery's own bound,
not something this project left unset by oversight) -- it only caps the
publish-retry layer on top of it, cutting the worst case roughly in half.
Updated the three tests that mocked `.delay()` on this task
(`test_consume_unlock_signal_does_identical_work_on_match_and_non_match`,
`test_no_password_field_is_accepted_anywhere_in_this_flow`, and §11.1's
budget-exhaustion test) to mock `.apply_async()` instead and read the task
kwargs from `call_args.kwargs['kwargs']`.

### 11.3 Nitpick: no test for `_within_report_budget`'s fail-open branch (Trivial, confirmed)

The round-4 fix (§10.5) added a broad `except Exception` so a cache backend
failure fails open, but no test exercised that branch -- every existing test
in `DuressSignalReportRateLimitTests` hits a working LocMemCache. Added
`test_cache_failure_fails_open`, patching the `caches` dict with a mock whose
`add()` raises `ConnectionError`, asserting `_within_report_budget` still
returns `True`, exactly as CodeRabbit's suggested patch.

### 11.4 Doc drift: two statements described round-1 behaviour that round-2 changed (Minor, confirmed)

`docs/privacy-features-gap-remediation-plan.md` §5 said
`duressSignalService.js` "reports every unlock," and
`security/tasks/__init__.py`'s comment on `activate_duress_signal_task` said
it "is only ever enqueued... when a signal matches." Both were accurate
descriptions of the feature's FIRST version and stale after round 2 changed
both halves: `reportUnlockForSlot` is wired only into
`StegoVaultDashboard.jsx`'s `onExtract` (confirmed by grep -- `VaultUnlockModal`
never calls it, exactly as §5's own "Not delivered" list already said in a
different sentence), and `consume_unlock_signal` enqueues unconditionally on
every report, match or not, with matching now decided entirely inside the
task (see §8's round-2 write-up). Corrected both to describe the delivered
behaviour instead of the pre-round-2 one.

### 11.5 Acceptance criterion left unchecked despite being covered (Minor, confirmed)

§6's honeypot-registry bullet described exactly what
`test_celery_beat_registry.py::CeleryBeatScheduleRegistryTests::test_honeypot_entries_resolve`
and `::test_argument_taking_honeypot_tasks_stay_unscheduled` already assert
(all six zero-argument tasks present, all three argument-taking fan-out
targets absent) but was left as `[ ]`. Ran both tests to confirm before
checking the box; named them in the acceptance line so the claim is
traceable the way the other checked items in §6 already are.

### 11.6 pip-audit-ignores.txt torch inventory count was stale after this round's own removal (Minor, confirmed)

The block's own summary comment said "Seven IDs total (was twelve; five
removed above)" -- correct as of round 4, but round 4 itself removed three
more (`PYSEC-2025-195/196/197`, §10.1), leaving four active
(`CVE-2025-3000`, `PYSEC-2025-194`, `PYSEC-2025-210`, `PYSEC-2026-139`) and
eight removed total. The summary line was never updated after that edit.
Corrected to "Four IDs total (was twelve; eight removed above)."

Re-ran `pip-audit -r <torch==2.12.0>` directly (not assumed) while verifying
this: confirms exactly one torch finding, `PYSEC-2025-194`/`CVE-2025-3000`,
already suppressed. Also re-confirms round 4's own open note in §10.1:
`PYSEC-2025-210`/`PYSEC-2026-139` don't appear in the tool's output either,
which is consistent with them being similarly stale -- but they were not
flagged by CodeRabbit this round, and touching them now would be scope
neither CodeRabbit nor the user asked for. Left exactly as round 4 deferred
it, for their own renewal (`exp:2026-08-25`, two days out).

### 11.7 Test results

`security/tests/test_duress_signal.py` re-run in full (matches CI's actual
`DEBUG=True` test invocation --
[backend-ci.yml](../.github/workflows/backend-ci.yml) sets this explicitly
for the pytest job; a local run without it 301-redirects every request via
`SECURE_SSL_REDIRECT`, an unrelated pre-existing environment quirk, not a
regression from this round): 30 passed, 1 skipped (the same pre-existing
SQLite/Postgres concurrency skip noted in §8.9, still unrelated). That is
§9.8's 28 passed / 1 skipped (24 from round 2's §8.9 + the 4 rate-limit tests
round 3 added) plus this round's 2 new tests --
`test_reserve_survives_budget_exhaustion` (§11.1) and
`test_cache_failure_fails_open` (§11.3) -- round 4 added none to this file.
`test_celery_beat_registry.py -k honeypot` re-run to confirm §11.5's
checkbox: 2 passed, 6 subtests passed. `python -m py_compile` clean on all
four touched backend files.

## 12. Review-fix round 6 on PR #486 (CodeRabbit, sixth pass)

Six findings (all actionable, no nitpicks this round), verified critically
before changing anything. All six held up. No CI check was failing this
round -- all 34 checks were green at the time of review; this round is a
response to CodeRabbit's own comments, not a CI failure.

### 12.1 `caches['rate_limiting']` looked up before the try block it's meant to be covered by (Minor, confirmed)

`_within_report_budget` assigned `rate_cache = caches['rate_limiting']` one
line above `try:`. `caches[...]` raises `InvalidCacheBackendError` if the
alias isn't declared in the active settings profile's `CACHES` dict -- and
unlike a live connection failure (already handled, §10.5), that lookup ran
outside the function's own fail-open boundary. Today's settings always
declare `'rate_limiting'` (confirmed by grep), so this was latent, not live
-- but the whole point of a fail-open rate limiter is that it holds under
every settings profile, not just the one currently deployed. Moved the
lookup inside the `try:`, exactly as CodeRabbit's own patch proposed; no
other line moved.

### 12.2 `onionSyncService.syncVault`'s explicit `mode` override was never validated (Minor, confirmed, not reachable in production today)

`effectiveMode = mode || getSyncPrivacyMode()` takes any truthy `mode`
literally. `VaultContext.jsx` -- the only production caller -- never passes
`mode` (confirmed by grep), so this path is not reachable today. But `mode`
is a documented parameter of a shared service module ("override the stored
preference"), already exercised directly by five cases in
`onionSyncService.test.js`, so a future caller passing a misspelled mode
string would silently fall through: not `OFF` (skips the cheap path), not a
capability match if onion happens to be up, and if onion is down, not
`REQUIRE_ONION` either -- so it lands on the degraded-clearnet return with
`degraded: true`, having never actually been the mode it claimed to be. That
is exactly the "quiet downgrade" this module's own JSDoc calls a false
privacy promise, just reachable through the API surface rather than the
UI. Fixed with CodeRabbit's own proposed patch: `mode ?? getSyncPrivacyMode()`
(switched from `||` to `??` so an explicit empty string is treated as an
invalid override, not "not provided") plus a `VALID_MODES.has(effectiveMode)`
guard that throws. Added
`rejects an explicit but invalid mode instead of silently downgrading` to
`onionSyncService.test.js`.

### 12.3 `honeypot-scan-all` scheduled outside its own task's documented cadence (Major, confirmed)

`scan_all_honeypots`'s docstring says "Should be scheduled to run every
15-30 minutes via Celery Beat" -- this is the actual breach-canary detection
loop, so that window IS the feature's detection latency, not an arbitrary
number. The schedule this PR shipped was hourly (3600s), double the
documented ceiling. Traced the discrepancy to this plan doc's own §4.3,
which suggested "hourly" for this one entry with no reasoning recorded,
unlike its neighbours `process_pending_rotations`/`send_breach_digest`,
whose cadences ARE reasoned through against their own tasks (§7.8/§7.9) --
an oversight in the plan itself, carried straight through to
implementation. Corrected to 1800s (30 minutes): the slower end of the
task's documented range, chosen over 15 minutes because `celery.py`'s own
SAFETY NOTE on this task already flags it for tripping the alias provider's
(SimpleLogin/AnonAddy) rate limits on a backlog tick -- 30 minutes satisfies
the docstring's floor while adding only 2x/day more provider calls than
hourly, not 4x. Added
`test_honeypot_scan_all_matches_its_own_docstring_cadence` to
`test_celery_beat_registry.py`, asserting the schedule falls in `[900,
1800]` seconds, per CodeRabbit's own request for a registry assertion (not
just the config change) so a future edit can't silently drift back outside
the documented range the way this one did. Updated §4.3's suggested cadence
in this plan to match.

### 12.4 Vault-sync route contract test only checked the trailing path segment (Minor, confirmed)

`test_the_named_route_actually_reverses` asserted `url.endswith('/sync/')`.
Any endpoint mounted at a different prefix but also literally ending
`/sync/` would still pass -- which defeats the point of a contract test
whose own module docstring says it exists so "a rename of the `vault-sync`
URL name... would break onion sync in a way no existing test would catch."
Traced the actual mount chain rather than assuming CodeRabbit's suggested
path was right: `password_manager/urls.py` (`path('api/', ...)`) ->
`api/urls.py` (`path('vault/', include('vault.urls'))`) -> `vault/urls.py`
(`path('sync/', ..., name='vault-sync')`) resolves to exactly
`/api/vault/sync/`, confirming the suggested fix. Tightened the assertion to
the full suffix.

### 12.5 Two documentation-scoping findings (Minor, both confirmed)

The doc's opening line ("Verification performed on `main` @ `5e43b1d`")
technically only covers §§0-6 (the original gap analysis); §7 onward
describes review-fix rounds each verified against their own later PR-branch
commit, named in that round's own text. Scoped the opening statement
explicitly rather than leaving it to read as covering the whole file.
Separately, §11.7's final test count (30 passed, 1 skipped) was correct but
required a reader to sum deltas scattered across three earlier rounds'
write-ups (24 from §8.9, +4 from §9.8, +0 from round 4, +2 from §11.1/§11.3)
to reconcile against the PR description's original "17 duress-signal" figure
-- not wrong, just not shown. Expanded §11.7 to state the arithmetic
explicitly.

### 12.6 Test results

`security/tests/test_duress_signal.py`,
`security/tests/test_celery_beat_registry.py`, and
`security/tests/test_onion_vault_sync_route.py` re-run together (same
`DEBUG=True` invocation as round 5, `canny` venv): 46 passed, 1 skipped
(same pre-existing skip), 20 subtests passed. `onionSyncService.test.js`
re-run in full: 17 passed (16 pre-existing + 1 new). `python -m py_compile`
clean on all four touched backend files. ESLint clean on both touched
frontend files.

## 13. Review-fix round 7 on PR #486 (CodeRabbit, seventh pass)

Two findings, both confirmed valid, both minor and copy/comment-scoped. All
34 CI checks were green going into this round.

### 13.1 Sync privacy mode descriptions didn't state the onion-ingress precondition (Minor, confirmed)

`DarkProtocolSettings.jsx`'s PREFER_ONION/REQUIRE_ONION copy said sync
"tries"/"only uses" the Tor onion service, without saying this client can
only reach the vault proxy when the page itself is being served from the
onion address. Verified against `onionSyncService.js`'s own doc comment:
`isOnionSyncAvailable` gates on `vault_proxy.available`, computed
server-side as "request arrived over the onion ingress" — on the ordinary
clearnet web origin nearly every user is on, that is always false, so
PREFER_ONION silently always falls back and REQUIRE_ONION always fails,
regardless of the toggle. Not a functional bug (the fallback/fail-closed
behavior is correct and already covered by
`onionSyncService.test.js`) but exactly the class of overclaim §6's own
acceptance criteria already guard against for this UI ("hides your IP
address", never "the server can't identify you") — a user flipping this
toggle from the normal web app would reasonably read "tries the Tor onion
service" as doing something, not as a no-op. Added one clause to each
description naming the actual precondition (accessing the app through its
onion address, e.g. Tor Browser). No test file exists for this component
(confirmed by search); ESLint clean, no new `react/no-unescaped-entities`
issues (matched the file's existing `&apos;` pattern for the two new
contractions).

### 13.2 `pip-audit-ignores.txt`'s round-5 torch-count fix was itself imprecise (Minor, confirmed — a correction to this doc's own round-5 fix)

§11.6 fixed "seven IDs total" to "Four IDs total (was twelve; eight removed
above, not renewed)" — the *count* (8) was right, but "above" wasn't:
verified by re-reading the file top to bottom, only 5 removed IDs
(`PYSEC-2025-189/190/191`, `192/193`) are documented before this summary
line; the other 3 (`PYSEC-2025-195/196/197`) are documented after it,
below, since that removal was itself round-4's fix and predates this
comment by position but not by file order. Changed "eight removed above"
to "eight removed in this manifest" — true regardless of position, and
avoids re-introducing a positional claim a future edit could just as easily
get backwards again. Comment-only change; the suppression parser
(`.github/workflows/security-multi-scanner.yml`, `_ID_RX`) only reads
`<ID> exp:<date>` lines, confirmed unaffected.

## 14. Review-fix round 8 on PR #486 (CodeRabbit, eighth pass)

Four findings, all confirmed valid. All 34 CI checks were green going into
this round. One finding (§14.3) is a correction to this document's and this
codebase's own overclaimed security guarantee from round 5 — the most
consequential kind of finding to get right, so it gets the fullest
treatment below.

### 14.1 §8.4's heading undercounted its own list (Minor, confirmed)

"Doc drift, four instances" headed a list of five bullets. Simple
miscount at authoring time — the five corrections listed were all already
correct and unchanged; only the number in the heading was wrong. Corrected
to "five instances".

### 14.2 §10's finding count didn't match its own subsections (Minor, confirmed)

"Six findings (5 actionable, 1 nitpick)" headed seven subsections
(§10.1-§10.7). Recounted directly from the section's own structure rather
than re-deriving from the original CodeRabbit comment: seven findings,
still one originally filed as a nitpick (§10.1), but that one's own heading
already says it turned out "Major in practice" on inspection — the
actionable/nitpick split in the summary line hadn't been updated to match
that upgrade. Corrected to "Seven findings (6 actionable, 1 filed as a
nitpick — §10.1, which turned out Major on inspection rather than staying
minor)".

### 14.3 The reserve counter's "~5s" bound (§11.1, round 5) does not hold against a continuously flooding attacker (Major, confirmed — a correction to our own prior work)

This is CodeRabbit catching an overclaim in a security-relevant comment we
wrote, not catching a new bug in the mechanism itself — the mechanism
behaves exactly as coded; the claim about what it *guarantees* was wrong.

**The claim, as written in round 5:** the reserve slot "bounds the
worst-case suppression window from 60s down to 5s" for a genuine duress
report an attacker is trying to suppress by flooding the endpoint.

**Why it's wrong:** the reserve slot is claimed by `cache.add()` -- first
well-formed request in each `_REPORT_RESERVE_WINDOW_SECONDS` (5s) window
wins, exactly like the primary counter, and for the identical reason
(neither counter may look at the signal's content to decide, or the
request thread becomes a timing oracle for whether it matched -- the
entire design principle §7's timing fix exists to protect). An attacker
who sends noise once every 5 seconds forever, without pausing, wins the
single reserve slot in every window, every time, for as long as they keep
sending -- there is no mechanism that lets a request "queue" for the *next*
window if it loses the current one. The real report, arriving at literally
any point during a sustained flood, loses every window it arrives in
exactly like the noise around it did. Suppression is bounded by how long
the flood lasts, which is entirely the attacker's choice -- not by 5
seconds, not by anything this endpoint controls.

**What the reserve actually buys:** it is a real, correct fix for the
narrower and arguably more common case round 5 also described --
`_within_report_budget`'s docstring calls this "a small per-user cap", and
the threat scenario originally motivating the reserve was a one-time burst
(attacker sends 60 requests to exhaust the window, then the real report
follows some time later in the same window). Against *that* shape of
attack, the reserve is a full fix: burst-then-stop suppression drops from
"rest of the 60s window" to "at most 5s". It only stops being a full fix
once the attacker's own request budget is large enough, and their patience
long enough, to keep flooding continuously -- a strictly harder attack to
sustain than a one-time burst, but not one this mechanism, or any
undifferentiated content-blind rate limit, can rule out.

**Why no code change accompanies this entry:** CodeRabbit's own finding
offered two options -- document the limitation, or redesign so reserve
delivery is protected from attacker-controlled traffic -- and, unlike
every code-level finding fixed in rounds 1-7, supplied no committable
diff for the second option. Evaluated it anyway before choosing the first:
every redesign considered (a larger reserve pool, per-source cooldowns, a
debounce-and-flush-on-quiet design) reduces to the same structural limit,
because the request thread has no signal available to weight one caller's
request over another's -- an attacker holding the user's session is,
architecturally, indistinguishable from the user themselves at this layer,
which is the same property that makes the endpoint's indistinguishability
guarantee (§7's original purpose) work in the first place. Closing this
gap for real needs a channel this endpoint doesn't have today -- delivery
redundant to network-layer flooding (a second transport, client-side
retry-with-backoff across reconnects, or an out-of-band signal) -- which is
new feature work, not a bug fix, and well outside "minimal, surgical,
no new regressions" for a review-fix round. Documented the limitation
honestly instead, in both places the false claim lived: this plan (§11.1,
corrected in place with a pointer here) and the code comment above
`_REPORT_RESERVE_WINDOW_SECONDS` in `duress_code_views.py`, which said the
same thing and is read independently of this doc. Also corrected
`test_reserve_survives_budget_exhaustion`'s docstring, which claimed the
same bound the test doesn't actually establish — the test itself needed no
change, since what it asserts (one more request gets through right after
budget exhaustion) is true and unaffected by this correction; only the
prose describing what that proves was wrong.

**Recorded as a candidate for future work, not implemented:** an
out-of-band or client-redundant duress delivery path would be the correct
fix if this attack scenario (sustained-session-hijack-plus-continuous-flood,
concurrent with the coerced unlock) is judged worth defending against
specifically -- flagged here rather than filed as a silent TODO so a future
reader has the reasoning, not just the gap.

### 14.4 TOCTOU race between the signal match and its trigger-count update (Major, confirmed)

`activate_duress_signal_task` reads `active_signals` (filtered
`is_active=True`) and picks `matched`, then later runs
`DuressSignal.objects.filter(pk=matched.pk).update(trigger_count=F(...)+1,
...)` using only the primary key -- no `is_active` re-check. Between those
two steps, nothing serialises against `register_signal_token`'s
deactivate-then-create (§8's fix; it holds a lock on the user's
`DuressCodeConfiguration` row, not on `DuressSignal`, so this task doesn't
wait on it). If a concurrent re-registration deactivates this exact row in
that window, the update still succeeds unconditionally on `pk` alone, and
the task proceeds to activate `matched.duress_code` -- read from the
now-stale in-memory object, not re-fetched -- for a signal the DB has
already retired. Confirmed by reading both call sites directly, not
assumed from the finding's description.

Fixed with CodeRabbit's own proposed diff: added `is_active=True` to the
update's filter and an early return when `updated` is falsy, mirroring
exactly how `if matched is None: return` already handles the equivalent
case one step earlier. Added
`test_concurrent_deactivation_between_match_and_trigger_update_does_not_fire`
to `DuressSignalActivationTaskTests`, simulating the race deterministically
(no threads needed): `DuressSignal.objects.filter` is patched so that the
specific `pk=matched.pk` call -- and only that call, not the earlier
`user=user, is_active=True` lookup -- triggers a real, synchronous
`filter(pk=signal.pk).update(is_active=False)` first, standing in for the
concurrent `register_signal_token` call landing in exactly that window.
Asserts the signal's `trigger_count`/`last_triggered_at` stay untouched and
no `DuressEvent` is created, i.e. the stale match is treated exactly like
no match at all.

### 14.5 Test results

`DuressSignalActivationTaskTests` (the class containing the new race test)
re-run in isolation first per the project's targeted-testing preference (10
passed) before the fuller run below. `security/tests/test_duress_signal.py`
in full (`canny` venv, `DEBUG=True`, matching CI): 31 passed, 1 skipped
(same pre-existing skip) -- 30 from round 5's §11.7 (unchanged by rounds 6
and 7, which touched other files, not this one) plus this round's one new
test; see §14.4. Round 6's 46-passed figure (§12.6) was three files
combined (this one plus `test_celery_beat_registry.py` and
`test_onion_vault_sync_route.py`), not this file alone -- noted here since
an earlier draft of this section conflated the two counts before being
caught in the same review pass that produced this section. `python -m
py_compile` clean on the one touched Python source file (`duress_tasks.py`)
and the one touched test file. No frontend files
touched this round.

## 15. Review-fix round 9 on PR #486 (CodeRabbit, ninth pass)

Three findings. Two fixed; one verified critically and found not to hold up
as an actionable bug once traced through what it would actually take to fix
-- recorded here with full reasoning rather than silently skipped, per this
round's own instructions to "skip the rest with a brief reason" rather than
fix speculatively. All CI checks that had completed were green going into
this round (`Backend CI/CD / Run Tests` and two other backend jobs were
still in progress at review time, per the PR's own check list, not failing).

### 15.1 A second race window after round 8's fix, between the trigger update and activation (Major claim, checked and NOT applied)

CodeRabbit's claim: round 8's `is_active=True` filter (§14.4) only protects
the conditional trigger-count *update*. A concurrent `register_signal_token`
call can still deactivate the same signal in the gap between that update
succeeding and `activate_duress_mode` actually running, using the
now-superseded `matched.duress_code`. Suggested fix: serialize registration
and activation with the same per-user lock or transaction, and extend the
regression test to cover this post-update interleaving.

**The race window is real. Traced what "fixing" it would actually require,
and concluded it should not be fixed the suggested way:**

- The remaining window (between the confirmed-active update at
  `duress_tasks.py` and the `activate_duress_mode` call a few lines later)
  has no I/O boundary in it -- no DB query, no `await`. It is narrower by
  a full DB round-trip than the window round 8 closed, and only reachable
  by genuine OS-level concurrency (a separate Celery worker process running
  a `register_signal_token` request at the exact same instant), not by
  anything schedulable from a single request.
- More importantly: `matched.duress_code` is not corrupted or wrong data if
  this race is hit. A new registration creates a brand-new `DuressSignal`
  row; it never modifies the FK on the OLD row this task already loaded via
  `select_related`. The "staleness" CodeRabbit's finding describes is only
  the OLD signal's `is_active` flag flipping to `False` moments after a
  match that already, genuinely, correctly occurred against it while it was
  still active. Firing the alarm for a match that was real when it happened
  is not a data-integrity bug.
- Whether firing is even undesirable is the real question, and the answer
  is no: `activate_duress_signal_task`'s own docstring already establishes
  the opposite design intent two paragraphs above this exact code --
  "a duress signal is single-fire per registration in spirit, but we do NOT
  deactivate it here: a user under sustained coercion may unlock
  repeatedly, and silently disarming the alarm after the first use is the
  opposite of what this feature is for." Suppressing an alarm for a
  just-confirmed genuine match because an unrelated registration raced past
  it a moment later is the same failure mode in a different guise -- a
  coercer who could somehow trigger both events in that same instant would
  gain a tool to silence the alarm, exactly backwards from what this
  feature must guarantee.
- The suggested remedy has a real cost the finding doesn't account for:
  `activate_duress_mode` is not cheap -- it creates an evidence package, may
  generate a decoy vault, and (when silent alarms are enabled) calls
  `SilentAlarmService.send_alerts()`, real blocking SMTP and webhook I/O
  (see §7's original timing-fix writeup for the same characterization).
  Serializing it against `register_signal_token` with a shared lock would
  mean a user's own legitimate attempt to register a NEW duress token --
  ordinary account maintenance, not an attack -- blocks for however long
  that I/O takes, any time it happens to land while an activation for their
  OLD token is in flight. That is a availability regression traded for
  closing a window that, per the point above, was not a real bug to begin
  with.

**Not applied.** No lock/transaction added, no new test -- a test asserting
"no activation occurs" would be asserting behavior this analysis concludes
is wrong to want. If this reasoning is ever revisited, the trigger to
re-open it is a concrete report of the race actually mattering in
practice, not a theoretical interleaving alone.

### 15.2 `safeJson`'s output was assumed to always be a plain object (Minor, confirmed)

`StegoVaultDashboard.jsx`'s `safeJson` is a bare `JSON.parse`, and its only
existing guard (`!decoyVault` after parsing) rejects `null`/falsy results --
not arrays, strings, or numbers, all of which parse successfully and are
truthy. Two call sites then used object-spread assuming an object shape:
`onEmbed`'s `{ ...decoyVault, __duress_signal: duressToken }` (embedding)
and `onExtract`'s `{ ...json }` (the on-screen display copy, stripped of
the signal field before rendering). Spreading a non-object silently
corrupts it -- an array becomes `{0: ..., 1: ..., __duress_signal: ...}`,
losing its array-ness entirely; a string becomes an object of its
characters; a number or boolean spreads to `{}`. Confirmed by reading
`safeJson` and both call sites directly: neither validates the parsed
value's shape before this point, only that it's syntactically valid JSON.

The embed-side instance is the more consequential of the two: it would
silently create a decoy vault whose payload does not match what the user
actually typed, without any error, for anyone whose vault JSON happens to
be array-shaped (e.g. `[{"user":"a"},{"user":"b"}]`, a plausible way to
represent a credential list) rather than a single object. The extract-side
instance only affects the on-screen JSON dump after a decoy unlock, not the
duress-reporting path itself (`reportUnlockForSlot` is called with the
original untouched `json`, before the display copy is made).

Added `isPlainObject` (object, non-null, non-array) next to `safeJson` and
gated both call sites on it: `onEmbed` now shows a validation error
("Decoy vault JSON must be an object, not an array or a bare value.")
instead of silently embedding a corrupted payload; `onExtract` skips the
clone-and-strip only when the extracted value isn't a plain object (the
REAL vault can legitimately be array-shaped too, and never carries
`__duress_signal` regardless -- see `onEmbed`'s own comment on why only the
decoy payload gets the field). No test file exists for this component
(confirmed by search, same as §13.1's finding on the sibling
`DarkProtocolSettings.jsx`); verified with `--max-warnings=0` ESLint
instead, clean.

### 15.3 A wall-clock-dependent test could flake on a slow CI runner (Minor, confirmed)

`test_over_budget_report_still_returns_204_and_skips_the_enqueue` sends 61
real authenticated POSTs through the full view -- not a direct
`_within_report_budget` call like its sibling tests in the same class --
before asserting the 62nd is silently dropped. The reserve slot the test
depends on has a hard 5-second TTL (`_REPORT_RESERVE_WINDOW_SECONDS`); if
the loop plus final request takes longer than that on a loaded runner, the
reserve key expires mid-test and the final request claims a fresh slot
instead of being the one that's rejected, failing
`mock_apply_async.assert_not_called()` for a reason unrelated to the budget
logic under test. Confirmed this test is the only one of its siblings with
this exposure: the others (`test_exceeding_budget_returns_false`,
`test_reserve_survives_budget_exhaustion`, etc.) call
`_within_report_budget` directly -- a plain LocMemCache read/write with no
HTTP request/response cycle, no view dispatch, no real `apply_async`
publish -- so 60-61 iterations complete in microseconds regardless of
runner load; only the one test that goes through real POSTs is exposed.

Fixed with CodeRabbit's own proposed patch: widened
`_REPORT_RESERVE_WINDOW_SECONDS` to match the primary window
(`_REPORT_RATE_WINDOW_SECONDS`, 60s) for the duration of this test via
`mock.patch` on the module attribute, so the outcome depends on request
*count* rather than how long the loop happened to take. No other test in
the file needed the same change.

### 15.4 Test results

`security/tests/test_duress_signal.py -k RateLimit`
(`DuressSignalReportRateLimitTests`, the class containing §15.3's fix; `canny`
venv, `DEBUG=True`): 6 passed, confirming the widened-window fix without a
full-file re-run -- §15.2's frontend change and §15.1's no-op both needed no
Python test run at all (no test file exists for the former; the latter
changed no code). Kept to this one targeted class deliberately: this file's
own real-POST-based tests are measurably the slowest in it (this run alone
took ~19 minutes for 6 tests, almost entirely the one test §15.3 touches,
which now makes 62 real authenticated requests instead of erroring out
early), so a full-file re-run for a single-test, non-logic change would cost
several times that for no additional signal -- exactly the "don't run the
enormous suite after every tiny change" guidance this project has followed
since round 1. `python -m py_compile` clean on the one touched Python file
(`test_duress_signal.py`). `eslint --max-warnings=0` clean on
`StegoVaultDashboard.jsx`.

## 16. Review-fix round 10 on PR #486 (CodeRabbit, tenth pass)

Two findings, both confirmed valid. All 34 CI checks were green going into
this round.

### 16.1 Raw exception messages logged on both duress-signal paths that handle the secret token (Minor, confirmed)

`duress_signal_register` and `duress_signal_report` both interpolate the
caught exception directly into the log line (`f"...: {e}"`). Both handlers
hold the raw 44-char signal/token value -- the actual secret this whole
feature exists to keep server-side-hashed-only (`register`) or
indistinguishable (`report`) -- as a local in the same scope as the `try`
block. Nothing guarantees no exception anywhere in the call stack below
(broker publish, Celery/kombu serialization, the ORM) ever embeds an
argument's value in its own `str()`; this codebase already treats that
possibility as real enough to act on elsewhere -- `DuressSignal.__str__`
omits the hash for exactly this reason ("that output reaches logs and
error reports"), and `_within_report_budget`'s own two `except Exception:`
blocks (added rounds 4/8) already log a fixed message plus `user_id` only,
never the caught exception. These two handlers were the only two in the
file's ~13 `except Exception as e:` sites actually holding the secret
token itself in scope, which is why the fix is scoped to just them rather
than the other ~11 (config/duress-code/authority/event handlers in this
same file, which don't touch this specific secret).

Fixed by logging `type(e).__name__` instead of the exception body, at both
sites. Verified no test asserts on either log message's content (searched
both duress test files; none do), so no test needed updating. No test
added either -- this changes only what appears in a log line on an
already-swallowed exception path; the existing "swallowed error still
returns the documented response" behavior (500+`internal_error` for
`register`, 204 for `report`) is unchanged and already covered.

### 16.2 The vault-sync route contract test only checked its own registry's metadata (Minor, confirmed)

`test_vault_sync_posts_to_the_vault_sync_route` asserted
`VAULT_OPERATION_ROUTES['vault_sync']['method'] == 'POST'` -- a string in a
Python dict this same module defines, checked against itself. It never
touched the actual Django URL pattern or view. If
`vault/urls.py`'s `path('sync/', CrudVaultItemViewSet.as_view({'post':
'sync'}), name='vault-sync')` ever changed which method maps to `sync`
without someone remembering to update the unrelated `VAULT_OPERATION_ROUTES`
dict to match, this test would keep passing while onion-routed sync
actually got a 405 from the real endpoint -- the exact "wiring silently
rots" failure mode this whole test file's own docstring says it exists to
catch, just not yet covering this specific gap.

Extended the same test (per CodeRabbit's own framing -- one cohesive
"posts to the route" contract, not a second test) to resolve the real URL
via `resolve(reverse(...))` and inspect the DRF ViewSet's own action
mapping: `ViewSetMixin.as_view()` attaches the exact `{method: action}`
dict it was built from as `view.actions` on the returned callable --
confirmed directly against the installed `rest_framework.viewsets` source
(`canny/Lib/site-packages/rest_framework/viewsets.py:139`,
`view.actions = actions`) rather than assumed from memory of the DRF API.
Asserts `resolved.func.actions.get('post') == 'sync'`. Chose this over a
full request/response integration test (firing a real authenticated POST)
because it checks the same fact -- which method maps to which action --
without needing to build out auth/payload fixtures for a view this test
file was never exercising end-to-end in the first place; the existing
tests in this file are all structural/resolution checks, and this stays
consistent with that style.

### 16.3 Test results

`security/tests/test_onion_vault_sync_route.py` in full (`canny` venv,
`DEBUG=True`): 5 passed, confirming the extended §16.2 test. Targeted
classes in `security/tests/test_duress_signal.py` covering both §16.1
handlers (`DuressSignalAPITests`, which exercises `duress_signal_register`
and `duress_signal_report`, plus `DuressSignalReportRateLimitTests`, which
covers the report path's rate-limit branch, including §15.3's real-POST
test): 14 passed. Notably faster this round (4m43s) than §15.4's ~19-minute
figure for a similarly-shaped run -- the earlier number reflected
contention at that specific point in the session, not a fixed cost of this
file; don't treat either figure as a hard estimate for next time. `python
-m py_compile` clean on both touched Python files. Searched both
duress test files for any assertion on the two changed log messages'
content; none exist, confirmed no test needed updating for §16.1.

## 17. Review-fix round 11 on PR #486 (CodeRabbit, eleventh pass)

One finding, confirmed and found to run deeper than the specific lines
flagged -- the correction it required, once actually carried out against
CI's real input rather than the stand-in every prior round used, applied to
the whole torch suppression block, not just the three IDs the flagged note
was about. All 34 CI checks were green going into this round.

### 17.1 Every torch renewal since round 1 verified against the wrong pip-audit input (Minor claim, Major once traced through)

CodeRabbit's claim, narrowly: the round-5 removal note for
`PYSEC-2025-195/196/197` says it verified with `pip-audit -r
<torch==2.12.0>` -- a placeholder-style single-package check, not
`requirements.txt`, the file CI's own "Run pip-audit" step
(`security-multi-scanner.yml`) actually scans (`cd password_manager &&
pip-audit -r requirements.txt --desc --format json`). `requirements.txt`
declares `torch>=2.12.0` -- an open floor, no ceiling -- not
`requirements-lock.txt`'s exact `torch==2.12.0+cpu` pin every round from 1
through 10 checked against instead. Update the note to describe the real
CI input, keeping the conclusion only if a CI-equivalent audit confirms it.

**Traced what "CI-equivalent" actually means and ran it, using the `canny`
venv the user pointed at:**

- `pip install --dry-run "torch>=2.12.0"` (the same resolution step
  `pip-audit -r <file>` performs internally for an unpinned requirement)
  resolves to **torch 2.13.0**, not 2.12.0. Confirmed this isn't an
  artifact of only checking torch in isolation: re-ran it alongside
  `transformers>=4.35.1` (the one real torch-consuming package actually
  declared in `requirements.txt` -- confirmed by grep that nothing else in
  the file names torch), and the resolution is unchanged. Confirmed the
  wheel exists for CI's actual platform, not just this machine's: CI's job
  pins `python-version: '3.11'` on (implicitly) a Linux runner; torch
  2.13.0's published files on PyPI include
  `torch-2.13.0-cp311-cp311-manylinux_2_28_x86_64.whl`, so the resolution
  isn't a Windows/Python-3.13-only artifact of this dev machine.
- `pip-audit -r <torch==2.13.0>` (the resolved version) reports **zero
  vulnerabilities** for torch -- not just the three IDs the flagged note
  named, all of them, including the two still-active entries
  (`CVE-2025-3000`/`PYSEC-2025-194`) every prior round's reachability
  argument was built to justify keeping.
- Attempted the literal full-file audit CI runs (`pip-audit -r
  requirements.txt`, all 146 declared packages) to remove any doubt
  entirely, rather than stop at the isolated check above. It did not
  complete: `pip install --dry-run` on the full file fails building
  `scipy` from source on this Windows machine (no Fortran compiler
  available for `meson`'s build backend) -- a Windows/local-toolchain gap
  unrelated to torch, and exactly the kind of platform difference from
  CI's Linux runner that motivated checking the isolated resolution
  against CI's actual Python version and OS family above rather than
  taking a Windows result on faith.

**Two of the four remaining torch entries were about to make this moot in
the worst possible way.** `PYSEC-2025-210`/`PYSEC-2026-139` carried
`exp:2026-08-25` -- tomorrow, relative to today (2026-08-24). This
manifest's own validation step (`Validate pip-audit ignore expiries`,
`security-multi-scanner.yml`) hard-fails the build (`sys.exit(3)`) on any
expired entry. Left alone, correcting only the flagged note's wording would
have fixed a documentation accuracy issue while leaving a real CI failure
one day out, on entries the SAME corrected verification already showed
don't apply. Removed both, following this file's own established "REMOVED,
not renewed" pattern, rather than renewing them a fourth time on the
lock-file-pin basis just shown to be the wrong check.

**`CVE-2025-3000`/`PYSEC-2025-194` were deliberately left alone.**
Same verification shows they don't apply to torch 2.13.0 either, but
CodeRabbit's finding didn't name them, and their `exp:2026-10-10` isn't
imminent -- removing them now would be the same scope-creep round 4 (§10.1)
and round 8 (§14.3) both already declined for adjacent-but-unflagged
findings in this exact file. Added a note in their own comment block
instead, so their next renewal starts from the corrected input rather than
re-verifying against the lock file's pin out of habit and reaching the same
stale conclusion a fourth time.

Updated: the block's own summary count (`Four IDs total` →
`Two IDs total`, ten removed rather than eight), the 195/196/197 note
(added a pointer to the corrected-methodology block above it rather than
rewriting its own already-accurate per-ID reasoning), and the
CVE-2025-3000/PYSEC-2025-194 block (added the "already-patched, not
removed this round" paragraph without touching its exp date or the two
active `ID exp:date` lines themselves).

### 17.2 Validation

No Python test references `pip-audit-ignores.txt` (confirmed by search) --
the only thing that reads it is `security-multi-scanner.yml`'s own inline
validation step and, at audit time, `pip-audit` itself. Ran the exact same
parser CI uses (transcribed from the workflow file, not re-approximated)
against the updated manifest locally: 23 active entries (was 25), zero
malformed, **zero expired** -- confirming §17.1's removal lands before
tomorrow's would-be failure, not after it. No `pytest` run for this round:
nothing else changed.
