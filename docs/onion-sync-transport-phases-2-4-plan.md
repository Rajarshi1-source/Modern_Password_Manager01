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
- **Own `DataDirectory`** under `PathUtils.getUserDataPath()/tor`, mode 0700.
- **Authenticated control port.** Tor allows any local process to drive an
  unauthenticated control port — no credential is required by default, which
  means another process on the machine could reconfigure or query this
  sidecar's Tor instance. Require `CookieAuthentication 1`, restrict the
  generated cookie file to the owning user, and add a test asserting an
  unauthenticated control connection is rejected.
- **Bootstrap gating.** Parse `NOTICE: Bootstrapped NN%` from stdout, or use the
  control port. Do not report available before 100% AND the real-connection
  check above both pass.
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

## A.4 Transport: routing the request through the circuit

The renderer must not gain network privileges. Keep the fetch in the main
process.

New `desktop/src/main/onionTransport.js`:
- `socks-proxy-agent` as the `httpAgent`/`httpsAgent` for the bundled `axios`.
  **Add it to `desktop/package.json`'s dependencies in this PR** — it is not
  there today, only `axios` is.
- Target the `.onion` origin from `capabilities.anonymity.onion_address`,
  fetched over clearnet on the first call and cached for the session (see
  A.5 below for exactly which service that clearnet call goes through).
- **Only `vault_sync` at first**, as §4.1 Phase 2 step 2 says. Extending to the
  rest of `VAULT_OPERATION_ROUTES` is a follow-up.
- Do **not** set `Host` manually — requesting `https://<addr>.onion/...` sets it
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
2. **`getCapabilities` stays on the clearnet service, always.** This is the
   one place the original "swap the whole `darkProtocolService` import for a
   desktop shim" sketch breaks: `isOnionSyncAvailable()` calls
   `getCapabilities()` to learn `vault_proxy.available` and the `.onion`
   address in the first place (A.4 above: "fetched over clearnet on the first
   call and cached for the session"). If `getCapabilities` were ALSO routed
   through the not-yet-connected onion transport, the very first call would
   need the onion address to reach the endpoint that hands out the onion
   address — a circular dependency with no first move. So only
   `proxyVaultOperation` is selected per-platform; `getCapabilities` keeps
   calling the web `darkProtocolService` unconditionally, on both web and
   desktop. Change `onionSyncService`'s module-scope
   `darkProtocolService` import (line 46) to two things instead of one
   accessor: keep the existing import for `getCapabilities`, and add a
   `getVaultProxyTransport()` accessor used only inside the `syncVault` branch
   that calls `proxyVaultOperation`, returning the desktop shim when
   `window.electronAPI?.isElectron` and the same web service otherwise. Add a
   test for the first-call case specifically: no cached address yet, and the
   capability fetch must still succeed.

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
- **Integration (docker-compose `--profile tor`):** desktop-shaped SOCKS5
  request to the `.onion` returns `vault_proxy.available === true`; the same
  request over clearnet returns `clearnet_ingress_refused` (403) and the client
  surfaces it rather than retrying over clearnet.
- **e2e:** extend `e2e/dark_protocol.spec.js` with the sync-over-proxy case
  §4.1's own test list already asks for.

## A.8 Acceptance criteria (PR A)

- [ ] Desktop routes vault sync over a real Tor circuit end-to-end (the #486 §6
      criterion this PR exists to satisfy).
- [ ] `require_onion` fails closed on desktop when bootstrap has not completed.
- [ ] `prefer_onion` reports `degraded: true` and the UI shows it.
- [ ] `off` spawns no Tor process at all.
- [ ] No `tor` process survives app quit, crash, or force-quit.
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
  a stable SOCKS5 endpoint on `127.0.0.1:9050`.
- iOS has no Orbot equivalent; the options are embedding Tor.framework (App
  Store review risk, sizeable binary, ongoing maintenance) or shipping nothing.
  Neither is a line item — it is its own investigation.

State this in the UI, not just the plan: on iOS the sync privacy control must be
disabled with "Not available on iOS", never silently present and inert. The
whole discipline this feature was built under is that the UI never implies
protection the platform cannot deliver.

## B.3 Work items

1. **Port the Phase 1 service.** New `mobile/src/services/onionSyncService.js`,
   a direct port of the web one: same three modes, same
   `vault_proxy.available` gate, same fail-closed `require_onion`, same
   `degraded` flag. Storage via `AsyncStorage` (or `expo-secure-store`,
   consistent with the app's existing choice) instead of `localStorage`.
   **Port it, do not reinvent it** — the failure modes in the web version's
   comments were paid for in review.
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
5. **SOCKS5 routing.** RN's `fetch` has no proxy option. Route through
   NetCipher's `StrongOkHttpClientBuilder` behind a small native module, or
   `react-native-tcp-socket`. Whichever is chosen, **the renderer contract does
   not change** — `onionSyncService.syncVault` still returns
   `{ data, transport, degraded }`.
6. **Onion address** from `capabilities.anonymity.onion_address`, same as
   desktop. No hardcoding.

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
5. **Server-side unlinkability argument.** Written out explicitly: what the
   server can still correlate (issuance batch size, redemption timing, sync
   payload size) and what it genuinely cannot.
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
  a valid anonymous credential, and require onion ingress in the credential case.
  Do not remove `IsAuthenticated` — clients that have not migrated must keep
  working, and a flag day here means a sync outage.
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

## C.4 Tests (PR C)

- Issuance/redemption round-trip; a redeemed token is rejected on reuse.
- A credential minted for user A cannot reach user B's vault.
- Redemption over clearnet is refused (`clearnet_ingress_refused` still applies).
- Expired credential refused; clock-skew tolerance asserted explicitly.
- Load test on the double-spend store: no false accepts under concurrency. This
  is the security-critical case.

## C.5 Acceptance criteria (PR C)

- [ ] `docs/anonymous-credentials-design.md` merged and reviewed first.
- [ ] Vault sync over onion carries no JWT and no user identifier.
- [ ] The server cannot link a redemption to an issuance (argument written out,
      and reviewed as an argument, not asserted).
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
3. **Gate on `vault_proxy.available`, never on `anonymity.available`.** The
   first is "this request arrived over onion"; the second is only "the daemon is
   up". Phase 1 chose the strong one deliberately.
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
