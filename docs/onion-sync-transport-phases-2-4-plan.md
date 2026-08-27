# Plan — Onion sync transport, Phases 2–4 (§4.1 carry-over)

Deferred from PR #486 (`docs/privacy-features-gap-remediation-plan.md` §4.1,
§5 "Not delivered"). Phase 1 shipped: `onionSyncService.js` with three privacy
modes, gated on the server's own `vault_proxy.available`, wired into
`VaultContext.syncVault`, with honest IP-privacy-only UI copy. What it cannot
do is give a normal browser user a real Tor circuit — a page served over
clearnet HTTPS cannot open a `.onion` connection. Phases 2–4 are the clients
that can.

**Scope: three PRs, in this order.** They are independent of the §4.2 work
(`docs/vault-unlock-envelope-integration-plan.md`).

| PR | Phase | Deliverable | Depends on |
|---|---|---|---|
| A | 2 | Desktop Tor sidecar — the first phase that helps a normal user | Phase 1 (merged) |
| B | 3 | Mobile: Android via Orbot, iOS deferred with a reason | Phase 1 (merged); independent of A |
| C | 4 | Anonymous credentials — close the identity-correlation gap | A or B, to have a real onion client to test against |

PR C is the only one that changes what the product may honestly *claim*.
A and B change only who can reach the existing claim.

---

## 0. What is already true — verified by reading the code

Do not re-litigate any of this; it is built, tested, and merged.

| Piece | Where | State |
|---|---|---|
| Tor v3 onion service + dedicated ingress listener | `docker-compose.yml` `--profile tor`, services `tor` and `backend-onion`; `k8s/tor.yaml` | Working |
| SOCKS5 exposed by the daemon | `TOR_SOCKS_HOST=tor`, `TOR_SOCKS_PORT=9050` | Working |
| Onion hostname published to the clearnet backend | `tor_shared:/var/lib/tor-shared:ro`, `TOR_ONION_HOSTNAME_FILE` | Working |
| Unforgeable onion-ingress detection | `security/services/tor_service.py:638` `request_is_onion_ingress` | Working |
| Capability the client gates on | `security/services/dark_protocol_service.py:283` `vault_proxy.available = anonymity_active AND onion_ingress` | Working |
| Fixed operation route table incl. `vault_sync` | `security/services/dark_protocol_service.py:169` `VAULT_OPERATION_ROUTES` | Working, regression-guarded by `test_onion_vault_sync_route.py` |
| Clearnet calls to the proxy refused | `clearnet_ingress_refused` → 403, `security/api/dark_protocol_views.py:452,479` | Working |
| Client transport contract | `frontend/src/services/onionSyncService.js` — `syncVault(syncData, {vaultService, mode}) → {data, transport, degraded}` | Working |

`request_is_onion_ingress` requires **four** independent conditions, none
client-supplied: `TOR.ENABLED`, the request served on `ONION_INGRESS_PORT`
(8443), the peer address in `ONION_INGRESS_TRUSTED_PEERS`, and the `Host`
header equal to the published onion address. It explicitly refuses to trust an
`X-Onion-Ingress` header. **This is the whole contract Phases 2 and 3 must
satisfy: reach the `.onion` through a real Tor SOCKS5 proxy so those four hold
naturally.** There is no shortcut, and any proposal that adds a header instead
of a circuit should be rejected on sight.

---

# PR A — Phase 2: desktop Tor sidecar

`desktop/` is Electron and can own a Tor process, which the browser cannot.
This is the first phase where an ordinary user gets a real circuit.

## A.1 Two hazards in `desktop/` to settle before writing any code

**A.1.1 There are two `main.js` files and only one of them runs.**

```text
desktop/package.json:  "main": "main.js"
desktop/main.js          556 lines  ← the real entry point
desktop/src/main/main.js 281 lines  ← not loaded by anything
```

The sidecar goes in `desktop/main.js`. Putting it in `src/main/main.js` would
produce code that reviews cleanly, tests nothing, and ships dead. Resolve the
duplication in this PR (delete or clearly mark the unused file) rather than
leaving the next contributor the same trap.

**A.1.2 The existing IPC channel names are already broken, and this PR adds
more of them.**

```text
desktop/src/shared/constants.js:116-119   SECURE_STORAGE_SET: 'secure-storage:set'   (colon)
desktop/main.js:317-347                   ipcMain.handle(IPC_CHANNELS.SECURE_STORAGE_*, …)
desktop/src/main/preload.js:8-11          ipcRenderer.invoke('secure-storage-set', …)  (hyphen)
```

The preload invokes hyphenated literals; the main process registers
colon-separated constants. No handler matches, so `window.electronAPI.secureStorage.*`
currently rejects with "No handler registered". Fix it in this PR — both sides
through `IPC_CHANNELS`, no string literals in `preload.js` — because Phase 2
adds four new channels and would otherwise duplicate the same bug at four times
the surface. Add a unit test that asserts every channel the preload invokes
exists in `IPC_CHANNELS`.

This is a pre-existing bug found while scoping, not a Phase 2 requirement.
Flagging it rather than silently expanding scope: it is two lines plus a test,
and shipping new IPC beside broken IPC is worse than fixing it.

## A.2 Bundling Tor

**Decision: bundle `tor` (the C daemon), not `arti`.** `arti` does not yet
expose a stable onion-client story across all three targets this app builds for
(`win`/`mac`/`linux` in `desktop/package.json` `build.*`), and the deployment
side is already a C-daemon deployment (`docker/tor/Dockerfile`), so operators
debug one implementation, not two. Revisit when `arti` ships onion-client
parity.

1. Vendor per-platform `tor` binaries under `desktop/vendor/tor/{win32,darwin,linux}/`.
2. `electron-builder` `extraResources`, **not** `files` — binaries must land
   outside the asar archive or they cannot be executed. Add to
   `desktop/package.json`:
   ```json
   "extraResources": [{ "from": "vendor/tor/${platform}", "to": "tor", "filter": ["**/*"] }]
   ```
   Use `${platform}`, not `${os}` — electron-builder 24.6.4 expands `${os}` to
   `mac`/`linux`/`win`, but `${platform}` expands to `process.platform`'s own
   values (`darwin`/`linux`/`win32`), which is what the vendor directory names
   above already are. Getting this macro wrong silently omits the Tor binary
   from the Windows and macOS packages — a packaging smoke test across all
   three targets is required in PR A precisely because this class of mistake
   builds cleanly and fails silently.
3. Resolve at runtime via `process.resourcesPath` in production and a repo-relative
   path in dev. `desktop/src/shared/utils.js` `PathUtils` already owns this kind
   of branch — extend it, do not add a second path helper.
4. **Verify the binary before executing it.** Pin a SHA-256 per platform in the
   repo and check it at spawn time. A bundled executable that is silently
   swapped is a far worse outcome than no Tor at all — refuse to start and
   report unavailable, never fall back to clearnet quietly.
5. macOS notarization and Windows signing both need the extra binary declared.
   Budget for a signing round-trip; this is the step that historically eats the
   schedule.

## A.3 Lifecycle: `desktop/src/main/torSidecar.js` (new)

Single owner of the process. Exports:

```text
start(): Promise<{ socksPort: number }>   // spawn, wait for bootstrap 100%
stop(): Promise<void>                     // SIGTERM, then SIGKILL after a grace period
getStatus(): { state, bootstrapPercent, socksPort, lastError }
```

Requirements:
- **Ephemeral SOCKS port.** Bind `SocksPort` to `auto`, not `127.0.0.1:0` —
  Tor's own manual treats port `0` as "disable this listener", not "pick one
  for me"; `auto` is the documented way to get an OS-assigned port. Read the
  actual port back from the control port, verify it bound to loopback only,
  and confirm `start()` by completing one real SOCKS5 connection through it —
  not just parsing "Bootstrapped 100%" — before reporting ready. Hardcoding
  9050 would collide with a system Tor or Tor Browser the user already runs,
  and the failure mode (silently using someone else's circuit) is worse than
  the collision.
- **Own `DataDirectory`** under `PathUtils.getUserDataPath()/tor`, owner-only.
  **"Mode 0700" is a POSIX-only instruction and this app ships a Windows
  target** (`desktop/package.json` `build.win`), where `fs.chmod` is
  effectively a no-op and the directory inherits whatever the parent's ACL
  grants — which on a shared machine can include other local users. Set mode
  0700 on macOS/Linux AND, on Windows, an explicit owner-only DACL with
  inheritance disabled (e.g. `icacls <dir> /inheritance:r /grant:r
  "%USERNAME%":(OI)(CI)F`, or the equivalent through a native binding).
  Apply the same to the control-port cookie file below — it is the actual
  credential. Test by attempting a read as a second local user and asserting
  it is denied, on every platform this ships to; a test that only checks the
  POSIX mode bits will pass on Windows while proving nothing.
- **Authenticated control port.** Tor allows any local process to drive an
  unauthenticated control port — no credential is required by default, which
  means another process on the machine could reconfigure or query this
  sidecar's Tor instance. Require `CookieAuthentication 1` and restrict the
  generated cookie file to the owning user (see the ACL note above — the
  cookie is the credential, so its permissions matter more than the
  directory's).

  **Test the AUTHORIZATION, not the TCP connect.** `CookieAuthentication 1`
  does not refuse the connection itself: Tor accepts the TCP connection and
  then rejects every control command until a valid `AUTHENTICATE` succeeds,
  closing the connection on a failed attempt. A test asserting "an
  unauthenticated control connection is rejected" at the socket level would
  therefore fail against a correctly-configured Tor while never exercising
  the check that actually matters. Instead: connect, issue a control command
  (e.g. `GETINFO version`) with no prior `AUTHENTICATE`, and assert Tor
  answers with an authentication error or closes the connection; then repeat
  with a deliberately WRONG cookie value and assert the same. Those two are
  the real assertions.
- **Bootstrap gating.** Parse `NOTICE: Bootstrapped NN%` from stdout, or use the
  control port. Do not report available before 100% AND the real-connection
  check above both pass.
- **A startup deadline, and reject (never hang) on child-process failure.**
  Nothing above bounds how long `start()` waits — if Tor never reaches 100%,
  or the process is alive but stuck, `start()`'s promise would simply never
  settle. Enforce a deadline (a fixed timeout, e.g. 60s, is enough — Tor
  bootstrap either completes quickly or something is genuinely wrong) and
  reject once it passes. Separately, `start()` must also reject immediately
  if the Tor child process itself errors or exits before bootstrap finishes
  — waiting on stdout from a process that already died is the same hang
  under a different cause. Run cleanup (killing whatever did spawn) in a
  `finally`-style path that cannot itself mask the original failure reason.
  Add a test for a stalled-bootstrap (deadline) case, not just the
  already-covered success path.
- **Kill on every exit path this process can actually observe.** `app.on('will-quit')` /
  `app.on('before-quit')` with `event.preventDefault()`, awaiting one guarded
  `stop()`, then quitting — this is the only path that can run async cleanup
  at all. It is not the only exit path: `process.on('exit')` cannot await
  anything (Node drops pending async work there), `app.exit()` skips
  `before-quit`/`will-quit` entirely, and `SIGKILL` runs no JS. State this
  limit rather than implying `process.on('exit')` closes it, and rely on an
  OS-level mechanism (a Windows Job Object, a Unix process group kill, or
  equivalent) as the actual backstop for those cases — an orphaned `tor`
  holding a `DataDirectory` lock makes the next launch fail in a way that
  looks like corruption, and JS-only cleanup cannot guarantee that never
  happens. A test here has to exercise a real parent-kill, not just call
  `stop()` and assert it resolves.
- **Never auto-start.** Spawn only when the user's sync privacy mode is
  `prefer_onion` or `require_onion`. A password manager that opens a Tor circuit
  by default is a surprising and, in some jurisdictions, unsafe default.
- **Bounded restart.** At most 3 restarts in 10 minutes, then stay down and
  report `lastError`. Do not loop.
- **A single, explicit lifecycle owner — this is not implied by the two
  bullets above, it must be built.** Something has to actually call
  `torSidecar.start()`/`stop()`; neither `onionSyncService.syncVault()` nor
  anything else does this today, because none of Phase 2 exists yet. Put
  this decision in the desktop main process, driven by the privacy-mode
  setting, not in `syncVault()` itself (which must stay identical to the
  Phase 1 contract per A.5): when the mode changes TO `prefer_onion` or
  `require_onion`, start the sidecar and let the FIRST subsequent
  `proxyVaultOperation` call await its readiness; when the mode changes TO
  `off`, stop a running sidecar rather than leaving it live for no reason
  (an idle Tor circuit is both a resource cost and a needless attack
  surface once the user has said they don't want one). Test the first sync
  from a fully-stopped state (sidecar starts, readiness is awaited, sync
  proceeds) and the `prefer_onion` → `off` transition (sidecar actually
  stops, not just "sync stops using it").

  **This requires a renderer-to-main mode handoff that nothing above
  defines, and it must be built, not assumed.** `getSyncPrivacyMode()` /
  `setSyncPrivacyMode()` (`onionSyncService.js`) are renderer-local —
  plain `localStorage` reads/writes, with no Electron main-process access
  of their own (the main process cannot reach the renderer's
  `localStorage` without an explicit bridge). But this bullet makes the
  main process the sole owner of `torSidecar.start()`/`stop()`, so it needs
  to learn the mode from somewhere. Two moments need a defined path:
  1. **A live change.** `setSyncPrivacyMode(mode)` gains one additive step:
     when running under Electron (`window.electronAPI?.isElectron`), after
     writing to `localStorage` it also calls
     `window.electronAPI.tor.start()` (mode is now `prefer_onion` or
     `require_onion`) or `window.electronAPI.tor.stop()` (mode is now
     `off`) — reusing the `TOR_START`/`TOR_STOP` channels already defined
     below, not a new one. A `prefer_onion → require_onion` change (already
     running, staying non-off) also calls `start()` again; both
     `start()`/`stop()` must therefore be idempotent so a redundant call
     from this is always safe. **Specifically: `start()` returns the SAME
     in-flight readiness promise while a bootstrap is under way, never a
     status snapshot.** Returning a snapshot here would contradict A.5's
     own requirement that the availability check be able to AWAIT an
     in-flight bootstrap: a second caller arriving mid-bootstrap would read
     "not ready" and `prefer_onion` would fall back to clearnet (or
     `require_onion` fail closed) while a perfectly good circuit was
     seconds from being ready. Once bootstrap has settled, `start()` is a
     genuine no-op returning the ready status; `stop()` while already
     stopped is likewise a no-op. Test two concurrent first syncs from a
     fully-stopped state: both must await the one shared promise and both
     proceed when it resolves — not one succeeding while the other reads a
     stale snapshot.
  2. **The persisted state at launch.** A user who quit the app with
     `require_onion` set and relaunches it must not silently revert to
     clearnet until they happen to touch the settings UI again. Whatever
     renderer code reads `getSyncPrivacyMode()` on startup (the settings
     screen mounting, or an app-level init effect — either is fine, but it
     must be unconditional, not only-if-the-user-opens-settings) calls the
     same `start()`/`stop()` step above once, immediately, using the
     freshly-read persisted value.
  Test: app launch with a persisted non-`off` mode actually starts the
  sidecar (not just "would start it if settings were opened"), and the
  `prefer_onion` → `off` transition through this same handoff actually
  stops it — the identical assertion the bullet above already asks for,
  now anchored to a concrete call path instead of an implied one.

## A.4 Transport: routing the request through the circuit

The renderer must not gain network privileges. Keep the fetch in the main
process.

New `desktop/src/main/onionTransport.js`:
- `socks-proxy-agent` as the `httpAgent`/`httpsAgent` for the bundled `axios`.
  **Add it to `desktop/package.json`'s dependencies in this PR** — it is not
  there today, only `axios` is.
- Target the `.onion` origin from `capabilities.anonymity.onion_address`.
  **This is resolved by `onionTransport.js` itself, independently of the
  renderer's `getCapabilities()` call described in A.5 — the two are
  separate fetches of the same clearnet endpoint, not one value handed
  across the IPC boundary.** The `TOR_PROXY` channel carries `operation`,
  sync-data-only `payload`, and `authToken` (below); it has no destination
  field, by design, so the main process cannot learn the onion address from
  anything the renderer sends it. Instead, on the first `TOR_PROXY` call in
  a session, `onionTransport.js` makes its own clearnet GET to the same
  capabilities endpoint `darkProtocolService.getCapabilities()` calls,
  authenticated with the same forwarded `authToken` it uses for the
  eventual `vault_sync` POST, and caches `anonymity.onion_address` in
  memory for the rest of the session. Validate the resolved value is a
  well-formed v3 `.onion` hostname before ever using it as a request
  target; refuse and report unavailable on anything else, and do not retry
  the resolution against a value that already failed validation. Add a
  test for the empty-cache first call (no address cached yet, the
  main-process fetch runs and succeeds) and one for a malformed resolved
  value being refused rather than dialed.
- **Only `vault_sync` at first**, as §4.1 Phase 2 step 2 says. Extending to the
  rest of `VAULT_OPERATION_ROUTES` is a follow-up.
- **Use `http://<addr>.onion/...`, not `https://`.** `backend-onion` in
  `docker-compose.yml` runs plain `daphne -b 0.0.0.0 -p 8443 ...` with no `-e
  ssl:...` — there is no TLS certificate on this listener, so an `https://`
  request would fail its TLS handshake before ever reaching the app. This is
  not a shortcut: Tor's own onion-service circuit already provides
  end-to-end encryption and the `.onion` address is itself
  self-authenticating (a hash of the service's public key), which is exactly
  why plaintext HTTP over a genuine onion circuit is the normal, expected
  pattern for hidden services — layering HTTPS on top would be redundant
  encryption for no additional guarantee unless an explicit TLS terminator
  is deliberately added and tested (not assumed). Apply the same `http://`
  scheme to the mobile client (B.3) once it exists — but see B.3's own note:
  on Android, `http://` alone is not sufficient, because the platform
  blocks cleartext traffic by default for any app targeting API 28+, and
  OkHttp (B.3's own transport) honors that platform policy.
- Do **not** set `Host` manually — requesting `http://<addr>.onion/...` sets it
  correctly, and that is condition 4 of `request_is_onion_ingress`. A
  hand-written `Host` is the single easiest way to get this subtly wrong.
- **Fail closed on the transport itself, not just on the request.** Set
  `proxy: false` on the Axios instance so it cannot pick up `http_proxy` /
  `https_proxy` env vars and bypass the SOCKS agent entirely; use a
  `socks5h://` (not `socks5://`) proxy URL so the `.onion` hostname resolves
  on the Tor side, never locally; and set `maxRedirects: 0` (or validate any
  redirect target stays on the exact `.onion` origin) so a malicious or
  misconfigured response cannot redirect this client to a clearnet endpoint
  it would then unknowingly call. Tests need to cover all three: an
  environment proxy present but ignored, hostname resolution happening
  proxy-side, and a redirect off-origin being rejected.
- Enforce a request timeout (circuits stall); surface the failure rather than
  retrying over clearnet.

Four new IPC channels in `IPC_CHANNELS` (colon-separated, matching the existing
convention, and used by both sides — see A.1.2):

```text
TOR_START:   'tor:start'
TOR_STOP:    'tor:stop'
TOR_STATUS:  'tor:status'
TOR_PROXY:   'tor:proxy-vault-operation'
```

`preload.js` exposes them as `window.electronAPI.tor.*`. **The `TOR_PROXY`
handler in the MAIN process is the trust boundary, not the preload bridge or
`onionSyncService`** — a compromised or buggy renderer can call
`window.electronAPI.tor.proxyVaultOperation` with any `operation` string it
likes. The `ipcMain.handle` implementation itself must check `operation`
against the single-entry allowlist (`vault_sync` — see above) and validate
the payload shape before it ever reaches `onionTransport.js`, and reject
anything else with no dispatch. Relying on the renderer-side service layer to
only ever send `'vault_sync'` is not a boundary; it is an assumption about a
process this feature explicitly does not trust with network privileges (see
"The renderer must not gain network privileges" above).

**"Validate the payload shape" means specifically: the `payload` for
`vault_sync` is sync data ONLY — the same shape `vaultService.syncVault`
already accepts — and the handler must reject the call outright if it
contains anything resembling a destination (`url`, `host`, `proxy`,
`origin`, or similar keys), not merely ignore those fields. The allowlist on
`operation` alone is not sufficient: `operation === 'vault_sync'` legitimately
passes it, but the actual network destination must still come ONLY from
`onionTransport.js`'s own resolution of `capabilities.anonymity.onion_address`
(above), never from any field inside the renderer-supplied `payload`. Without
this, a compromised renderer could ride the allowed `vault_sync` channel
itself and smuggle a destination override through the payload rather than
through `operation` — the allowlist would let the call through while the
actual boundary (what the main process is permitted to POST, and where) was
never checked. Add a test asserting a payload carrying a clearnet-looking
`url`/`host` field is rejected before any request is made, not merely
stripped.

**The schema itself, made concrete rather than left as "reject a denylist
of destination-looking names" — a renamed field would slip past a
denylist, so this must be an allowlist, and it must mirror the one real
contract that already defines "sync data" precisely:
`password_manager/vault/serializer.py`'s own `SyncSerializer` and
`VaultItemSerializer`.**

- Top level: exactly `last_sync` (string, optional), `items` (array,
  optional), `deleted_items` (array, optional), and `expected_sync_version`
  (integer, optional) — nothing else. `url`/`host`/`proxy`/`origin`, and any
  other key not in this list, are refused as unknown, not merely absent from
  a blocklist; this is what actually closes the gap above for a field name
  the denylist did not anticipate.
  **`expected_sync_version` is deliberately in this list even though
  `SyncSerializer` does not declare it and no client sends it today.** The
  sync view reads it straight off `request.data`, outside the serializer
  (`password_manager/vault/views/crud_views.py:373`), and uses it for
  optimistic concurrency — a mismatch against the locked `UserSalt.sync_version`
  returns 409 so the client can re-fetch and merge. Omitting it here would
  mean the IPC boundary silently rejects the first concurrency-aware client
  that starts sending it, and the failure would look like a transport bug
  rather than an allowlist that was never updated. It is a plain integer with
  no destination semantics, so admitting it costs nothing the rest of this
  schema is protecting.
- Each entry of `items[]`: exactly `item_id` (string), `item_type`
  (string), `encrypted_data` (string), `favorite` (boolean, optional),
  `folder_id` (string or null, optional), `tags` (array of strings,
  optional) — `VaultItemSerializer`'s own writable fields. `id`,
  `created_at`, and `updated_at` are server-assigned there
  (`read_only_fields`) and must not be accepted from the renderer either.
  Any other key on an item is refused.
- `deleted_items[]`: array of strings only.
- The payload must be a plain JSON object matching exactly the shape
  above — an array, a primitive, or an object with any extra top-level or
  nested key is refused before `onionTransport.js` is ever called.

Add a test asserting an unknown top-level key is refused even when it does
not resemble a destination (proving this is a real allowlist, not the same
denylist restated), alongside the existing clearnet-looking `url`/`host`
test.

**A separate, more basic gap: nothing above says how the request reaches
`/vault-proxy/`'s `IsAuthenticated` requirement at all.** `/vault-proxy/` is
`IsAuthenticated` today (§C.1), and the WEB client already satisfies this —
every `darkProtocolService` call, including the existing
`proxyVaultOperation`, sends `authHeader()`'s bearer token
(`frontend/src/services/darkProtocolService.js`). Desktop's onion-routed
request goes out from a completely different process (the Electron main
process, over its own OkHttp/Axios client), which has no JWT of its own —
without one, the onion-routed `vault_sync` gets a 401 before the proxy logic
ever runs, and Phase 2 does not work AT ALL regardless of how correctly
everything else here is built. Fix: `onionSyncService`'s desktop branch
passes the CURRENT session's bearer token (the same one `darkProtocolService`
already has, sourced identically) as an explicit, separately-named argument —
`proxyVaultOperation(operation, payload, authToken)`, never folded into
`payload` — and `onionTransport.js` attaches it as the request's
`Authorization` header, exactly mirroring what the web client already does
for every other dark-protocol call. Keeping it a separate parameter, not a
payload field, is what keeps this compatible with the payload-shape
validation immediately above: `authToken` is legitimate credential data the
main process is meant to use, not a destination the renderer controls, so it
must never be checked against — or confused with — the destination-field
rejection rule. Mobile's `proxyVaultOperation` (B.3) needs the identical
fix, sourced from wherever the RN app already holds its own bearer token
today.

## A.5 Renderer: reuse the Phase 1 contract verbatim

§4.1 Phase 2 step 3 requires the renderer code to be identical across web and
desktop. It already can be, because `onionSyncService.syncVault` takes its
collaborator by injection:

```text
frontend/src/services/onionSyncService.js:135
  syncVault(syncData, { vaultService, mode = null } = {})
```

Two small, additive changes, both in `frontend/src/services/`:

1. **A transport shim, for `proxyVaultOperation` only.** New
   `desktopOnionTransport.js` implements `proxyVaultOperation`, delegating to
   `window.electronAPI.tor.proxyVaultOperation` (which the main-process
   allowlist above gates to `vault_sync`).
2. **`getCapabilities` stays on the clearnet service, always — but
   `isOnionSyncAvailable()` must stop reading `vault_proxy.available` on any
   platform that owns a separate transport.** (This renderer-side fetch is
   separate from `onionTransport.js`'s own capability fetch in the main
   process, A.4 above — this one gates UI/availability decisions in the
   renderer; that one resolves the dial target the main process itself
   uses. Both hit the same clearnet endpoint independently; neither hands
   its result to the other.) This is the one place the original "swap the
   whole `darkProtocolService` import for a desktop shim" sketch breaks,
   and fixing HALF of it (routing only `getCapabilities` to clearnet)
   creates a second, worse bug that CodeRabbit caught in review:
   `isOnionSyncAvailable()` returns `Boolean(capabilities?.vault_proxy?.available)`,
   and the server computes `vault_proxy.available` as `anonymity_active AND
   request_is_onion_ingress` (`tor_service.py`) — true only when *this
   specific request* arrived over the onion listener. A `getCapabilities`
   call that always goes out over clearnet can therefore never make
   `request_is_onion_ingress` true, so `vault_proxy.available` is
   structurally always `false` on desktop, `isOnionSyncAvailable()` always
   returns `false`, and desktop would never attempt the onion path at all —
   Phase 2 would ship a sidecar that is never used.

   The reason `vault_proxy.available` is the right gate for Phase 1 (web) and
   the wrong one here: for a Tor-Browser user reaching the site AT its
   `.onion` address, the page itself — and therefore its own
   `getCapabilities()` call — already travels the onion route, so checking
   "did THIS request arrive over onion ingress" is checking the same
   transport the eventual `vault_sync` call will use. Desktop (and mobile,
   see B.3 point 1) has no such thing as "the page is served from `.onion`";
   the whole app is a separate process making its own transport decision per
   call, so `getCapabilities` and `proxyVaultOperation` are never guaranteed
   to travel the same route, and gating on the FORMER's per-request ingress
   status tells you nothing true about the LATTER.

   Fix: `isOnionSyncAvailable()` branches on whether a non-web transport is
   selected for this platform (see the `getVaultProxyTransport()` accessor
   below). When one is: check `capabilities?.anonymity?.available &&
   Boolean(capabilities?.anonymity?.onion_address)` **AND** that platform's
   own local transport readiness — for desktop, `torSidecar.getStatus()`
   reporting a bootstrapped, running circuit (A.3's `getStatus(): { state,
   bootstrapPercent, socksPort, lastError }`, not merely "spawned"); for
   mobile, the analogous Orbot-running check (B.3). These are two genuinely
   independent facts and both are required: `anonymity.available` describes
   the SERVER's Tor daemon (always up in a correctly configured deployment,
   and unaffected by anything happening on this device), while
   `torSidecar.getStatus()` describes THIS device's OWN local sidecar, which
   is stopped by default (A.3: "never auto-start") and takes real time to
   bootstrap once started. Gating on the server-side fact alone would report
   "available" while the local SOCKS5 listener is not yet listening — or has
   crashed — and `proxyVaultOperation` would then fail with a raw connection
   error instead of `isOnionSyncAvailable()` cleanly reporting unavailable
   beforehand. When neither this bootstrap check nor a non-web transport
   applies (plain web): keep the existing `vault_proxy.available` check
   unchanged — Phase 1's behaviour and tests are untouched. The REAL
   per-request verification for desktop/mobile then happens where it
   actually can: at the `proxyVaultOperation` call itself, which genuinely
   goes out over the onion SOCKS5 circuit (A.4); a `clearnet_ingress_refused`
   there would mean a genuine transport misconfiguration, not an expected
   steady-state outcome the client should route around silently.

   **This check must be able to AWAIT an in-flight bootstrap, not just read
   a snapshot of it.** A.3 promises "the first subsequent
   `proxyVaultOperation` call awaits [the sidecar's] readiness" — but
   `prefer_onion`/`require_onion` decide whether to call
   `proxyVaultOperation` at all based on THIS check, so a snapshot taken
   mid-bootstrap reads as "not ready," `prefer_onion` falls back to
   clearnet, and `require_onion` fails closed — during perfectly normal
   startup, before A.3's own await is ever reached. Concretely: the
   mode-change handler that starts the sidecar (A.3) must expose the
   in-flight `start()` promise it already holds, not just fire it and
   forget it, and this availability check awaits that promise — bounded by
   A.3's existing ~60s startup deadline — before evaluating
   `torSidecar.getStatus()`, rather than only ever inspecting whatever the
   status happens to be at the instant of the call. Concurrent callers
   (two syncs firing before the first bootstrap completes) must share the
   SAME in-flight promise rather than each calling `torSidecar.start()` —
   a second concurrent `start()` is not covered by A.3's idempotency
   guarantee for `stop()` and would either double-spawn the process or race
   the first call's own bootstrap tracking. Test: two concurrent
   first-syncs from a stopped state both await the same startup and both
   proceed once it completes, rather than one succeeding while the other
   reads a stale "not ready" snapshot.

   Change `onionSyncService`'s module-scope `darkProtocolService` import
   (line 46) to two things instead of one: keep the existing import for
   `getCapabilities` (always clearnet), and add a `getVaultProxyTransport()`
   accessor used both by the availability check above and inside the
   `syncVault` branch that calls `proxyVaultOperation` — returning the
   desktop shim when `window.electronAPI?.isElectron`, and the same web
   service otherwise (mobile gets its own equivalent condition when B.3 is
   built). Tests: the first-call case (no cached address yet, capability
   fetch must still succeed); `isOnionSyncAvailable()` returns `true` on
   desktop only when BOTH `anonymity.available` is true AND
   `torSidecar.getStatus()` reports ready, with `vault_proxy.available:
   false` throughout (proving that field is never consulted on this
   platform).

   **The bootstrapping case splits in two, and conflating them is what an
   earlier draft of this very list got wrong.** "Still bootstrapping" is not
   one state, and `isOnionSyncAvailable()` must not answer it the same way
   both times — an unqualified "returns `false` while bootstrapping" (which
   this list previously said) directly contradicts the await requirement
   above, and would reintroduce the fall-back-to-clearnet-during-startup bug
   that requirement exists to prevent:
   - **A bootstrap is IN FLIGHT** (a tracked `start()` promise exists):
     AWAIT it, bounded by A.3's ~60s deadline, then answer from the settled
     outcome — `true` if it reached ready, `false` if it failed. Do NOT
     return `false` merely because the percentage is currently short of 100.
     Test: a call made mid-bootstrap resolves `true` once the bootstrap
     completes, and two concurrent callers share the one promise.
   - **No bootstrap is in flight** (never started, deliberately stopped, or
     the last attempt already FAILED — `lastError` set, or the restart
     budget spent): return `false` immediately, without awaiting anything
     and without starting one as a side effect. Test each of those three
     shapes separately; a crashed sidecar must not hang a caller for 60s
     waiting on a promise that will never exist. The request-level integration assertion for
   the onion-routed-succeeds / clearnet-routed-403 pair is A.7's job, not
   this list's — see A.7 below for why `vault_proxy.available` must not be
   the success signal there either.

Everything else — the three modes, the fail-closed `require_onion` branch, the
`degraded` flag, `VaultContext`, `DarkProtocolSettings.jsx` — is untouched.
That is the point of the Phase 1 contract, and any design that forks
`onionSyncService` per platform has misread it.

## A.6 Bootstrap UI

Reuse `DarkProtocolDashboard.jsx`, which already renders circuit and bootstrap
state (§4.1 Phase 2 step 4). Feed it `tor:status`. Add no new component.

## A.7 Tests (PR A)

- **Unit, `torSidecar`:** bootstrap parser reaches 100% from a captured stdout
  fixture; `stop()` is idempotent; restart budget stops at 3; binary-hash
  mismatch refuses to spawn.
- **Unit, IPC:** every channel `preload.js` invokes exists in `IPC_CHANNELS`
  (the A.1.2 regression guard).
- **Unit, renderer selection:** with `window.electronAPI.isElectron` set,
  `onionSyncService` calls the desktop shim; without it, the web service. Assert
  the three modes behave identically in both — this is the "contract verbatim"
  claim, and it is only true if tested.
- **Integration (docker-compose `--profile tor`):** request-level assertions,
  not `vault_proxy.available` — per A.5's own fix, desktop's `getCapabilities`
  call is always clearnet, so `vault_proxy.available` is structurally always
  `false` for it and must never be treated as the success signal here.
  Instead: a `vault_sync` operation sent through the desktop's real onion
  SOCKS5 transport succeeds; the same operation sent over clearnet is refused
  with `clearnet_ingress_refused` (403) and the client surfaces it rather
  than retrying over clearnet; and `anonymity.onion_address` being present on
  the (clearnet) capabilities response is asserted separately, as the
  bootstrap signal it actually is, not conflated with the request-level
  outcome above.
- **e2e:** extend `e2e/dark_protocol.spec.js` with the sync-over-proxy case
  §4.1's own test list already asks for.

## A.8 Acceptance criteria (PR A)

- [ ] Desktop routes vault sync over a real Tor circuit end-to-end (the #486 §6
      criterion this PR exists to satisfy).
- [ ] `require_onion` fails closed on desktop when bootstrap has not completed.
- [ ] `prefer_onion` reports `degraded: true` and the UI shows it.
- [ ] `off` spawns no Tor process at all.
- [ ] No `tor` process survives a NORMAL app quit (`before-quit`/`will-quit`
      runs the guarded `stop()`), verified by observing the process is gone.
- [ ] For crash / `app.exit()` / SIGKILL — where A.3 already establishes that
      no JavaScript cleanup can run at all — a named OS-level
      parent-lifetime mechanism is in place per platform and verified by a
      real parent-kill test, not by calling `stop()`: a Windows Job Object
      with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`, and a process-group kill
      (or `prctl(PR_SET_PDEATHSIG)` on Linux / `kqueue` `NOTE_EXIT` watch on
      macOS) on the Unix targets. **Stated as two separate criteria on
      purpose:** the single unconditional "survives app quit, crash, or
      force-quit" line this replaces promised something JS cannot deliver
      and A.3's own exit-path bullet already says so — a criterion that
      contradicts its own design section is one nobody can honestly tick.
- [ ] Renderer code paths are identical to web except for the transport shim.
- [ ] Bundled binary hash is pinned and verified at spawn.
- [ ] The A.1.2 IPC channel-name bug is fixed and regression-tested.
- [ ] Signed/notarized builds produced for all three targets.

---

# PR B — Phase 3: mobile

## B.1 The constraint that shapes this PR

`mobile/` is **Expo managed** — `expo ~54.0.31`, `expo-router`, RN 0.85
(`mobile/package.json`). Orbot integration means `NetCipher` / `TorService`,
which is native Android code. That is possible on Expo, but only via a **config
plugin plus a custom dev client**; it can never work in Expo Go. Say this in the
PR description, because "add Orbot support" reads like a dependency install and
is not one.

Second constraint: `mobile/src/services/DarkProtocolService.js` has a
**different signature** from the web service —

```text
mobile/src/services/DarkProtocolService.js:318
  async proxyVaultOperation(token, operation, payload)   // token FIRST
frontend/src/services/darkProtocolService.js:253
  proxyVaultOperation(operation, payload = {}, sessionId = null)
```

and mobile has no `onionSyncService` equivalent at all. Reconciling these is
most of the work; the Tor part is smaller than it looks.

## B.2 Scope decision: Android only, iOS deferred with a reason

Ship Android. Defer iOS explicitly rather than half-building it:

- Android has Orbot, a maintained app with a documented `TorService` binding and
  a SOCKS5 endpoint on `127.0.0.1`. **`9050` is Orbot's DEFAULT SOCKS port,
  not a fixed one** — it is user-configurable, Orbot writes the configured
  value into the torrc it generates, and `0` is the documented way to
  DISABLE the SOCKS listener entirely. So B.3 must discover the port rather
  than hardcode it: read the configured value from Orbot's own status/
  binding surface, treat `0` (or an absent/unparseable value) as "onion sync
  unavailable" rather than falling back to 9050, and verify the resolved
  listener actually accepts a connection before reporting availability —
  the same "confirm one real SOCKS5 connection, don't just trust the
  number" discipline A.3 already applies to the desktop sidecar's own
  ephemeral port. Test a non-default configured port and the port-0
  disabled case explicitly; a test that only covers 9050 would pass on a
  default install and fail silently for every user who changed it.
- iOS has no Orbot equivalent; the options are embedding Tor.framework (App
  Store review risk, sizeable binary, ongoing maintenance) or shipping nothing.
  Neither is a line item — it is its own investigation.

State this in the UI, not just the plan: on iOS the sync privacy control must be
disabled with "Not available on iOS", never silently present and inert. The
whole discipline this feature was built under is that the UI never implies
protection the platform cannot deliver.

## B.3 Work items

1. **Port the Phase 1 service.** New `mobile/src/services/onionSyncService.js`,
   a direct port of the web one: same three modes, same fail-closed
   `require_onion`, same `degraded` flag. Storage via `AsyncStorage` (or
   `expo-secure-store`, consistent with the app's existing choice) instead of
   `localStorage`. **Port it, do not reinvent it** — the failure modes in the
   web version's comments were paid for in review. **Except** the
   availability check: mobile is a separate process with its own transport,
   never a page served from `.onion`, so it has the exact same shape as
   desktop — see A.5 point 2's fix (`isOnionSyncAvailable()` must check
   `anonymity.available` + `onion_address`, not `vault_proxy.available`, for
   any platform with its own shim). Porting the PRE-fix web gate here would
   silently carry desktop's original bug over to mobile: `vault_proxy.available`
   would be structurally always `false` and `prefer_onion`/`require_onion`
   would never engage.
2. **Normalise the signature.** Give mobile `DarkProtocolService` an
   `(operation, payload)` overload so the ported service is a straight copy.
   Keep the old three-argument form working, or update its callers in the same
   PR; do not leave two conventions live.
3. **Config plugin** `mobile/plugins/withOrbot.js`: queries package visibility
   for `org.torproject.android` (Android 11+ requires `<queries>`), plus the
   NetCipher dependency.
4. **Orbot detection and consent.** If Orbot is absent, `prefer_onion` degrades
   with an honest message and a Play Store link; `require_onion` fails closed.
   Never bundle or auto-install.
5. **SOCKS5 routing.** RN's `fetch` has no proxy option, and neither
   candidate from the original draft of this plan actually provides
   HTTP-over-SOCKS5 on its own — verified against each project's own docs
   before writing this: NetCipher's `StrongOkHttpClientBuilder` hardcodes
   `supportsSocksProxy()` to `false` (OkHttp3's own SOCKS support is not what
   NetCipher's convenience wrapper exposes), and `react-native-tcp-socket` is
   a raw TCP/TLS socket library with no HTTP client on top of it — using it
   alone would mean hand-rolling HTTP/1.1 framing.

   Use OkHttp's OWN native SOCKS support instead, bypassing NetCipher's
   builder entirely: a small custom native module constructs a plain
   `OkHttpClient` with `.proxy(new Proxy(Proxy.Type.SOCKS, new
   InetSocketAddress("127.0.0.1", orbotSocksPort)))` — standard
   `java.net.Proxy`, which OkHttp has always honored regardless of
   NetCipher's wrapper — and exposes one bridge method
   (`proxyVaultOperation`) that performs the POST through that client and
   returns the response to JS. This is a real, complete stack: standard
   OkHttp, standard `java.net.Proxy`, no unsupported convenience class in the
   path.

   **Apply the SAME redirect hardening A.4 requires for desktop's Axios
   client — OkHttp's default redirect behaviour is not safe here either.**
   Build the client with `.followRedirects(false).followSslRedirects(false)`,
   or if a redirect must be honored, validate the target stays on the exact
   `.onion` origin before following it — otherwise a malicious or
   misconfigured response could redirect this client to a clearnet endpoint
   it would then unknowingly call, exactly the risk A.4's `maxRedirects: 0`
   closes for desktop. This does not follow automatically from switching to
   OkHttp; it is a separate configuration step on the same `OkHttpClient`
   the SOCKS proxy is attached to. Add an Android test asserting a redirect
   to a clearnet target is rejected, not silently followed.

   **A separate, platform-level blocker: Android rejects cleartext HTTP by
   default for any app targeting API 28+, and OkHttp honors that policy —
   this `http://<addr>.onion` request would be blocked before it ever
   reaches Orbot, independent of anything above.** The fix is a
   domain-scoped exception, not a global one: a Network Security
   Configuration (`res/xml/network_security_config.xml`) with
   `cleartextTrafficPermitted="true"` scoped to the exact `.onion` hostname,
   referenced via `android:networkSecurityConfig` in the manifest. **Do
   not** set `cleartextTrafficPermitted="true"` at the base/global level —
   that would silently permit plaintext HTTP for every other request this
   app makes, a real regression the domain-scoped form avoids entirely.
   Test the onion request actually succeeds on an API 28+ target without
   global cleartext enabled — this is a platform policy, not something a
   unit test mocking OkHttp would catch.

   **This exact-hostname exception has a build-time/runtime mismatch that
   must be resolved before implementation, not glossed over.** Android's
   Network Security Configuration is packaged into the APK at build time
   and cannot be changed once installed, but point 6 below sources the
   onion address from `capabilities.anonymity.onion_address` at RUNTIME,
   with an explicit no-hardcoding rule — a `<domain>` entry cannot name a
   value the app does not learn until its first network call. Resolve this
   by treating the packaged hostname as a BUILD-time deployment constant,
   not a hardcoded secret: inject the exact `.onion` hostname for the
   backend this APK is built to talk to via a Gradle-generated resource
   value into `network_security_config.xml` at build time (the same kind
   of per-build-flavor parameterization the app likely already does for its
   clearnet backend URL), and at RUNTIME validate that
   `capabilities.anonymity.onion_address` matches that compiled-in value
   exactly before attempting the onion request. A mismatch — a different
   deployment's address, a rotated onion key, a misconfigured build — must
   be treated as `onion sync unavailable`, never as a reason to attempt the
   request anyway (Android would silently block it regardless) and never as
   a reason to widen the packaged exception. Test the mismatch path
   explicitly, alongside the existing release-like-APK success test on an
   API 28+ target.

   Whichever exact bridging shape is chosen, **the renderer contract
   does not change** — `onionSyncService.syncVault` still returns
   `{ data, transport, degraded }`. Add an Android integration test that
   proves `vault_sync` genuinely reaches the onion ingress through this
   stack (not just that the native module compiles) — the same
   request-level pair A.7 requires for desktop: the onion-routed operation
   succeeds, the clearnet-routed one is refused with
   `clearnet_ingress_refused` (403), and `anonymity.onion_address` is
   asserted separately from either outcome. Not `vault_proxy.available`:
   mobile's `getCapabilities` call is clearnet for the identical reason
   desktop's is (A.5), so that field is structurally always `false` here
   too and must never be read as a success signal.
6. **Onion address** — two DIFFERENT values, and collapsing them into one
   blanket "no hardcoding" rule (as an earlier draft of this point did)
   contradicts point 5's Network Security Configuration requirement above:
   - **The request target, at RUNTIME:** always from
     `capabilities.anonymity.onion_address`, same as desktop. **Never
     hardcoded** — this is the rule that matters for routing, and it is
     unchanged.
   - **The hostname baked into `network_security_config.xml`, at BUILD
     time:** necessarily a compile-time deployment constant, because
     Android's Network Security Configuration is packaged into the APK and
     cannot be changed after install (point 5). This is not a violation of
     the rule above — it is a per-build-flavor deployment parameter, the
     same kind of thing the clearnet backend URL already is — and point 5
     requires the runtime value to be validated against it before any onion
     request is attempted, with a mismatch treated as `onion sync
     unavailable`. A build that ships without this exception has no working
     onion sync at all on API 28+; a build that "avoids hardcoding" by
     widening cleartext globally is strictly worse than either.

## B.4 Tests (PR B)

- Unit (jest-expo): the three modes on the ported service, identical assertions
  to `frontend/src/services/onionSyncService.test.js`. Copy the test file too —
  divergence between the two suites is how the contract quietly forks.
- Orbot-absent: `require_onion` throws `OnionSyncUnavailableError`,
  `prefer_onion` returns `degraded: true`.
- iOS: the privacy control renders disabled.
- Manual matrix in the PR description: Orbot installed / not installed / running
  / stopped. There is no CI runner with Orbot; do not pretend otherwise.

## B.5 Acceptance criteria (PR B)

- [ ] Android with Orbot running routes vault sync over a real circuit.
- [ ] Android without Orbot: `prefer_onion` degrades honestly, `require_onion`
      fails closed.
- [ ] iOS shows the control as unavailable, with the reason.
- [ ] `proxyVaultOperation` has one signature across web and mobile.
- [ ] Mobile mode semantics are byte-identical to web (shared test assertions).
- [ ] PR description states the custom-dev-client requirement.

---

# PR C — Phase 4: anonymous credentials

## C.1 The gap, stated precisely

`/vault-proxy/` is `IsAuthenticated`. The JWT names the account on every
onion-routed request, so the server can correlate every "anonymous" sync with a
user identity. Phase 1 handled this the only honest way available — the UI says
"hides your IP address" and never "the server cannot identify you"
(`onionSyncService.js` module docstring, `DarkProtocolSettings.jsx` copy). This
PR is what makes the stronger claim true.

**This is the only PR of the three that may change privacy copy.** Until it
merges, the Phase 1 wording stands, including on desktop and mobile.

## C.2 Design — write the design doc first

§4.1 Phase 4 says "treat as its own design doc", and that is correct: the
choice of primitive determines the schema, the endpoints, and the threat model.
Land `docs/anonymous-credentials-design.md` and get it reviewed **before** any
implementation. It must settle:

1. **Primitive.** Blind RSA signatures (RFC 9474), VOPRF (RFC 9497 /
   Privacy Pass), or BBS+. Recommendation to argue against: **Privacy Pass
   VOPRF** — smallest server state, an existing spec, and libraries on both
   sides. BBS+ buys selective disclosure this use case does not need.
2. **Issuance.** Over clearnet, authenticated by the existing JWT. N tokens per
   issuance; N is a privacy parameter (too few and issuance timing correlates
   with redemption; too many and a stolen batch is worth more).
3. **Redemption.** Over onion only. A redeemed token authorises exactly one
   `vault_sync`, and authorises **nothing else** — it must not be usable to
   read or enumerate the vault.
4. **Double-spend prevention.** Redis set of spent nonces with a TTL matched to
   token expiry, and a durable fallback. This is the one component where a bug
   is a security bug, not a privacy one.
5. **Server-side unlinkability argument, bounded by a stated threat model.**
   The primitive gives CRYPTOGRAPHIC unlinkability — the server cannot derive
   which issuance a given redemption came from FROM THE TOKEN ITSELF, no
   matter how it is inspected. It does not, and cannot, erase everything the
   server observes as a byproduct of running the service: issuance batch
   size, redemption timing, and sync payload size are all still visible
   metadata, and a server willing to correlate traffic patterns across those
   (e.g. "this account requested a batch of 8 tokens 20 minutes before this
   redemption arrived") gets a probabilistic signal the cryptography does
   not touch. Write the argument as "unlinkable under the stated threat
   model, given the listed observable metadata" — never as an unqualified
   "cannot be linked." An acceptance criterion or a UI claim that drops the
   qualification contradicts this point and must be rejected in review.
6. **Key rotation and the anonymity-set collapse it causes.** A rotation
   partitions users by which key signed their tokens. Say how often, and how
   large the set stays.

## C.3 Implementation sketch (after the design lands)

- **Backend, new module** under `password_manager/security/` beside
  `dark_protocol_service.py` — the modular-monolith placement the Phase 1 work
  followed. Issuer key management, `POST /api/security/anon-credential/issue/`
  (clearnet, `IsAuthenticated`), and a `HasAnonymousCredential` DRF permission
  class.
- **`/vault-proxy/` permission change:** accept *either* `IsAuthenticated` **or**
  a valid anonymous credential. **The onion-ingress check
  (`request_is_onion_ingress` → `clearnet_ingress_refused`) already runs
  endpoint-wide and unconditionally today, and must not become conditional
  on which branch authorises the request** — this PR does not add that check
  "for the credential case," it is not new.

  **Correcting an ordering claim an earlier draft of this section got
  wrong, because PR C's design depends on getting it right:** that draft
  said the ingress check runs "before either permission class is even
  evaluated." It does not, and cannot where it currently lives. Verified
  against the installed DRF source rather than assumed:
  `APIView.dispatch()` calls `self.initial(...)`, which calls
  `check_permissions()` (`rest_framework/views.py:421`), and only then
  invokes the handler (`:512`). `DarkProtocolVaultProxyView.post()` calls
  `DarkProtocolService.proxy_vault_operation(...)`, so the ingress check
  inside that service method runs strictly **after** permission evaluation.
  That is harmless today — the endpoint is `IsAuthenticated`-only, so the
  two checks are independent and neither can mask the other — but the
  justification was false, and PR C is exactly where a false ordering
  assumption becomes a real bug.

  What remains true and is the actual requirement: the ingress check must
  stay on `proxy_vault_operation` itself, ahead of and independent of the
  vault dispatch, and must never be moved or duplicated inside
  `HasAnonymousCredential` alone — that would leave a JWT-authenticated
  request's onion-ingress enforcement resting on whichever permission class
  happens to short-circuit first, a real risk on ANY future refactor. Do
  not remove `IsAuthenticated` — clients that have not migrated must keep
  working, and a flag day here means a sync outage.

  **A request presenting BOTH a valid JWT and a valid anonymous credential
  must be rejected, and — unlike the ingress check — this one genuinely
  must run before permission evaluation.** `IsAuthenticated OR
  HasAnonymousCredential` grants access as soon as EITHER passes; it does
  not notice that the other also passed. Dispatch is `request.user`-scoped
  (C.3's "Ownership scoping" point below), so a request carrying an
  `Authorization` header alongside a credential passes on the JWT, reaches
  dispatch with `request.user` populated, and lets the server bind that
  redemption to a real identity — defeating C.5's own acceptance criterion
  ("vault sync over onion carries no JWT and no user identifier") for
  precisely the requests where it matters most.

  **Where to put it, concretely** (the previous draft said "same place as
  the ingress check," which per the correction above is too late):
  override `initial()` on `DarkProtocolVaultProxyView` and run the
  exactly-one-auth-mode check **before** calling `super().initial(...)` —
  that is the documented DRF hook that precedes `check_permissions()`.
  Running it at the top of `post()` would also prevent the vault dispatch
  and would close the security hole, but it leaves the guarantee resting on
  every future handler on this view remembering to call it; `initial()` is
  structural. This is an additional check alongside the OR, not a
  replacement: `IsAuthenticated` alone and a credential alone must both keep
  working exactly as today. Test all four shapes — JWT only, credential
  only, both, neither.
- **Ownership scoping is the hard part.** `VAULT_OPERATION_ROUTES` dispatches to
  the genuine vault views, whose scoping is `request.user`-based
  (`dark_protocol_service.py:150-158`). An anonymous credential deliberately has
  no `request.user`. Resolve this in the design doc, not in review: the credible
  option is that the credential carries a blinded, server-opaque vault handle
  established at issuance. **If this cannot be solved cleanly, Phase 4 does not
  ship** — a half-anonymous path that still needs `request.user` to scope the
  query has not removed the correlation it exists to remove.
- **Frontend:** token store, automatic refill, and redemption in
  `darkProtocolService.proxyVaultOperation`. `onionSyncService` should not need
  to change at all; if it does, the layering is wrong.

  **An anonymous redemption must strip `session_id`, not just the JWT.**
  Today's `proxyVaultOperation(operation, payload, sessionId)` sends
  `session_id` in the body alongside `authHeader()`'s bearer token
  (`frontend/src/services/darkProtocolService.js`), and the server hands it
  to `_record_operation_traffic`, which resolves it as
  `GarlicSession.objects.filter(session_id=session_id, user=user, ...)` —
  **a user-scoped row**. Sending it on a credential-backed request would
  re-link the redemption to an account identity through the accounting
  path, defeating the same C.5 criterion the mixed-credential rule above
  protects, just by a different route. Removing the `Authorization` header
  alone is therefore not sufficient.

  Define the anonymous redemption request explicitly as: the credential,
  the `operation`, and the sync-data-only `payload` — and NOTHING else. No
  `Authorization` header, no `session_id`, and no other account-scoped
  handle (existing or later added). Traffic accounting simply does not
  happen for these requests; `_record_operation_traffic` already returns
  early when `session_id` is falsy, so this needs no server change, and
  inventing an anonymous accounting handle would just recreate the
  correlation under a new name. **Add a wire-level test** asserting the
  redemption request's headers and body contain no bearer token, no
  `session_id`, and no user identifier — asserting on the actual serialized
  request, not on the function's arguments, since the point is what leaves
  the machine.

## C.4 Tests (PR C)

- Issuance/redemption round-trip; a redeemed token is rejected on reuse.
- A credential minted for user A cannot reach user B's vault.
- **A request presenting both a valid JWT and a valid anonymous credential,
  over onion, is refused before dispatch** — the mixed-credential case C.3's
  "exactly one authentication mode" rule exists to close. This is a
  different assertion from the clearnet-refusal bullet below: this one is
  about an otherwise-legitimate ONION request being rejected specifically
  because it carries two credentials, proving the vault is never reached
  with a redemption linkable to a JWT identity.
- Redemption over clearnet is refused (`clearnet_ingress_refused` still applies)
  — asserted for THREE separate authentication shapes, not just the credential
  one: a JWT-only (`IsAuthenticated`) request over clearnet, a
  credential-only request over clearnet, and a request presenting both. All
  three must be refused identically, proving the clearnet check in C.3 truly
  stays endpoint-wide rather than only firing on one branch.
- **Negative route-scope, covering every entry in `VAULT_OPERATION_ROUTES`,
  not just `vault_sync`.** C.2 point 3 requires a redeemed credential to
  "authorise exactly one `vault_sync`, and authorise nothing else — it must
  not be usable to read or enumerate the vault." That is a claim about every
  OTHER route in the table, so test every other route explicitly: a valid,
  unspent credential attempted against `vault_get`, `vault_list`,
  `vault_create`, `vault_update`, `vault_delete`, and `vault_search` must
  each be rejected before vault dispatch, not merely "not `vault_sync`."
  Asserting only that `vault_sync` succeeds would leave this requirement
  entirely unverified — a credential that happened to also authorise
  `vault_list` would pass every test in this list except this one.
- Expired credential refused; clock-skew tolerance asserted explicitly.
- Load test on the double-spend store: no false accepts under concurrency. This
  is the security-critical case.

## C.5 Acceptance criteria (PR C)

- [ ] `docs/anonymous-credentials-design.md` merged and reviewed first.
- [ ] Vault sync over onion carries no JWT and no user identifier — verified
      at the wire level, and explicitly including `session_id`, which
      resolves to a user-scoped `GarlicSession` row and would re-link the
      redemption through the accounting path even with the bearer token
      stripped (see C.3's frontend bullet). "No user identifier" means the
      serialized request, headers and body, not just the absence of an
      `Authorization` header.
- [ ] Under the documented threat model, the server cannot cryptographically
      link a redemption to an issuance beyond the listed observable metadata
      (issuance batch size, redemption timing, sync payload size) — argument
      written out and reviewed as an argument, not asserted, and matching
      C.2 point 5's qualification exactly.
- [ ] Double-spend is prevented under concurrent load.
- [ ] Ownership scoping without `request.user` is solved, not worked around.
- [ ] UI copy upgraded from "hides your IP address" to the stronger claim —
      **only in this PR**, and only for the paths that actually use a credential.
- [ ] The `IsAuthenticated` path still works for un-migrated clients.

---

## 9. Cross-cutting rules for all three PRs

1. **Never widen the honesty gap.** Every one of these clients must keep
   reporting `transport` and `degraded` truthfully. A silent clearnet fallback
   is the single failure this whole feature exists to prevent.
2. **Never add a trusted header.** `request_is_onion_ingress` refuses
   `X-Onion-Ingress` on purpose (`tor_service.py:657-660`). If a client cannot
   satisfy the four real conditions, the correct answer is "unavailable".
3. **Gate per platform, per A.5's fix — this rule is NOT one blanket
   condition.** Web (Phase 1) gates on `vault_proxy.available`: the page
   itself is served from `.onion` when this matters, so a `getCapabilities()`
   call from that page naturally shares the transport of the eventual
   `vault_sync` call, and `vault_proxy.available` — "this request arrived
   over onion" — is the strong, correct signal. Desktop and mobile (Phases
   2–3) are separate processes whose `getCapabilities()` call is necessarily
   clearnet (A.4), so `request_is_onion_ingress` for THAT call can never be
   true and `vault_proxy.available` would be structurally always `false` —
   gating desktop/mobile on it, as an earlier draft of this rule did, would
   mean `prefer_onion`/`require_onion` never engage at all. Those platforms
   bootstrap on `anonymity.available && onion_address` **and that
   platform's own local transport readiness** — desktop:
   `torSidecar.getStatus()` reporting a bootstrapped, running circuit;
   mobile: the analogous Orbot-running check; both per A.5 — instead of
   `vault_proxy.available` (the deployment-level "is Tor up and does it
   have a published address" signal is necessary but not sufficient on its
   own: it says nothing about whether THIS device's own local sidecar has
   finished bootstrapping) and let the real per-request check happen where
   it actually can: at the
   `proxyVaultOperation`/`vault_sync` call itself, which genuinely does
   travel the onion circuit and is still verified server-side by
   `request_is_onion_ingress` exactly as before — this does not weaken that
   boundary, it only changes which signal the CLIENT uses to decide whether
   to attempt the call. See A.5 for the full argument and B.3 point 1 for
   why mobile inherits the same fix.
4. **UI copy stays at IP-privacy-only until PR C.** Applies to desktop and
   mobile as much as to web.
5. **The Phase 1 contract is the contract.** `{ data, transport, degraded }`,
   three modes, fail-closed `require_onion`. A platform that needs to change it
   has found a real design problem worth discussing — not a reason to fork.

---

## 10. Related

- `docs/privacy-features-gap-remediation-plan.md` §1, §4.1, §5 — origin
- `frontend/src/services/onionSyncService.js` — the Phase 1 contract
- `password_manager/security/services/tor_service.py:638` — the ingress contract
- `docker-compose.yml` (`--profile tor`), `k8s/tor.yaml` — deployment
- `docs/vault-unlock-envelope-integration-plan.md` — the other #486 carry-over
