# `fhe_sharing` — Homomorphic Autofill & Password Sharing

The Django app that implements **Homomorphic Autofill** (use a password
without decrypting it on the sharer's device) and **Homomorphic Password
Sharing** (re-encrypt a vault item to a recipient's key without the
server ever seeing plaintext).

For the wire format, cryptographic primitives, and API schema see
[`SPEC.md`](SPEC.md). This README focuses on **operations**: threat
model, feature flags, kill switches, and the staged rollout playbook.

---

## 1. Threat Model

### 1.1 Defends against

| Adversary                                     | How we defend                                                                                             |
|-----------------------------------------------|-----------------------------------------------------------------------------------------------------------|
| **Passive server / breached database**        | Password ciphertext on the server is Umbral (`secp256k1` + ChaCha20-Poly1305) — owner private key never leaves the client; the `kfrag` alone cannot decrypt. |
| **Active server / malicious admin**           | The server can only produce `cfrag` (re-encryption fragment) from `kfrag` + `capsule`. Without the recipient's private key, `cfrag` cannot be turned into plaintext. |
| **Recipient curiosity ("use but not see")**   | Sealed injection paths never expose the plaintext string to untrusted JavaScript: web uses sandboxed `<iframe sandbox="allow-scripts">`; extension uses the isolated world + native value setters; Android uses `AutofillService` Datasets outside the app's JS context; iOS uses `ASCredentialProviderViewController`. |
| **Recipient page-script exfiltration**        | On web, the sealed iframe posts only `{ type: 'filled' }` back. On extension, the content script uses `Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(...)`, which cannot be hooked by the page's JS. |
| **Tampering with the re-encryption fragment** | Recipient verifies `cfrag` against `verifying_pk` before decrypting. Tampered `cfrag` raises `umbral-pre::VerificationError` client-side. |
| **Stale share replay**                        | `max_uses`, `expires_at`, `domain_constraints`, and per-use audit log are enforced server-side on every `POST /shares/<id>/use/`. |
| **Cross-origin autofill injection**           | Sealed injection targets only the `target_selector` on the same top-level origin the share was bound to. Browser extension background verifies `tab.url` origin against `domain_constraints` before streaming plaintext. |
| **Phishing look-alike domain**                | `domain_constraints` on the share are exact eTLD+1 matches; the extension and mobile autofill providers check before filling. |
| **Passive network attacker (TLS intact)**     | All PRE payloads traverse HTTPS; Umbral adds end-to-end secrecy on top — a successful TLS MITM still cannot read passwords. |

### 1.2 Does **not** defend against (explicitly out of scope)

| Adversary / Scenario                                   | Why we don't claim defense                                                                                     |
|--------------------------------------------------------|----------------------------------------------------------------------------------------------------------------|
| **Compromised recipient device**                       | If malware has code execution, it can observe the decrypted password during the ~1-frame autofill window. Sealed injection slows but does not stop a determined local attacker. |
| **OS-level screenshot / screen-record**                | Android `FLAG_SECURE` and iOS `UITextField.isSecureTextEntry` help, but a system-level attacker can record the screen. |
| **Coerced recipient**                                  | "Use but not see" is a UX promise against honest-but-curious recipients. A recipient who chooses to can always type the autofilled password back into an attacker's form. |
| **Compromised sharer device at share-creation time**   | If the sharer's device is already owned, the password was exposed before it entered PRE. PRE does not rewind the past. |
| **Server signing a malicious `kfrag`**                 | The server can replace a share's `kfrag` with its own. The recipient will be able to decrypt to a server-chosen password. Mitigation: the sharer's client sends the `kfrag` directly to the server in `POST /shares/`; the server never generates it. Future work: `kfrag` transparency log. |
| **Quantum adversary**                                  | `secp256k1` is not post-quantum. PQ-PRE (e.g. Kyber-based) is reserved for `umbral-v2`. |
| **True FHE of keystroke circuits / arbitrary functions** | We do CKKS only on numeric summaries (length, entropy, expiry). We do not run AES or hash circuits homomorphically on the password. |
| **Metadata leakage**                                   | The server knows *who shared what item with whom and when*. This is required for audit + revocation. Anonymous sharing is out of scope. |
| **Sidechannels in WASM / JNI / Swift FFI**             | We ship `@nucypher/umbral-pre` (WASM) as-is; we do not claim constant-time guarantees on all platforms. |

### 1.3 Trust assumptions

1. **Sharer client** is trusted at share-creation time. (If your device
   is compromised when you click "Share", you lose.)
2. **Recipient client** is trusted to *execute* sealed injection as
   designed. A malicious recipient client can always exfiltrate — the
   sealed-injection layer only defends against honest-but-curious
   recipients running the stock app/extension.
3. **Transport** is TLS 1.2+ with valid certs.
4. **Server** is honest-but-curious. An actively malicious server can
   replace `kfrag`; see §1.2 row 5.

---

## 2. Feature flags and kill switch

All PRE / homomorphic-autofill behavior is gated by `FHE_SHARING_SETTINGS`
in Django settings. Defaults live in
[`services/fhe_sharing_service.py`](services/fhe_sharing_service.py).

```python
FHE_SHARING_SETTINGS = {
    # -------- PRE / umbral-v1 rollout controls --------
    'PRE_ENABLED':   True,       # master kill switch for umbral-v1
    'ROLLOUT_STAGE': 'opt_in',   # 'off' | 'opt_in' | 'default_on'

    # -------- share lifecycle limits (apply to both suites) --------
    'DEFAULT_EXPIRY_HOURS':   72,
    'MAX_EXPIRY_DAYS':        90,
    'MAX_USES_DEFAULT':       None,
    'MAX_USES_LIMIT':         10000,
    'DOMAIN_BINDING_REQUIRED': True,

    # -------- audit / cleanup --------
    'AUDIT_RETENTION_DAYS':   365,
    'CLEANUP_INTERVAL_HOURS': 6,
}
```

### 2.1 `PRE_ENABLED` — the kill switch

| Value   | Effect on `POST /shares/` with `cipher_suite='umbral-v1'`          | Effect on `GET /status/`                              | Effect on existing `umbral-v1` shares |
|---------|--------------------------------------------------------------------|-------------------------------------------------------|---------------------------------------|
| `True`  | Accepted, PRE pipeline runs                                        | `features.pre_umbral_v1 = true`, suites list includes `umbral-v1` | Usable as normal                      |
| `False` | **Rejected with `403 { error: "FHE sharing disabled" }`** (see [`views.py:108`](views.py#L108)) | `features.pre_umbral_v1 = false`, suites list **only** `simulated-v1` | **Still usable (revoke only)** — existing shares are not destroyed, but no new `umbral-v1` shares can be minted |

**When to flip to `False`:**
1. A vulnerability is disclosed in `pyUmbral`, `@nucypher/umbral-pre`,
   or the UmbralBridge FFI.
2. A `cfrag` transparency / accountability gap is discovered.
3. A regression in the sealed-injection path is reported by any
   client (web, extension, Android, iOS).
4. Legal/compliance requires temporary suspension of cross-user
   re-encryption.

**Procedure (one-liner, zero deploys):**

```bash
# In Django settings or environment override
FHE_SHARING_SETTINGS={"PRE_ENABLED": false, "ROLLOUT_STAGE": "off"}
```

Clients poll `/api/fhe-sharing/status/` on every dashboard load;
`features.pre_umbral_v1 = false` will hide the PRE toggle in
`CreateHomomorphicShareModal` (see
[`frontend/src/Components/sharedfolders/CreateHomomorphicShareModal.jsx`](../../frontend/src/Components/sharedfolders/CreateHomomorphicShareModal.jsx))
and in the extension popup (see
[`browser-extension/src/fheShare/popupPanel.js`](../../browser-extension/src/fheShare/popupPanel.js)).

### 2.2 `ROLLOUT_STAGE` — semantic rollout

Clients may adjust UI based on this string. Currently enforced at the
UI layer only; the server enforces `PRE_ENABLED` as the hard gate.

| Stage        | UI behavior                                                           |
|--------------|-----------------------------------------------------------------------|
| `off`        | Hide "Use Umbral PRE" toggle entirely, even if `PRE_ENABLED=True`.    |
| `opt_in`     | Show the toggle, default off. Shipped default for v2.0.0.             |
| `default_on` | Show the toggle, default **on**. Tentative v2.2.0 target.             |

---

## 3. Staged rollout plan

> **Ownership:** The `fhe_sharing` app lead signs off on each stage
> transition. Each transition requires (a) error-rate dashboards in the
> target population to be green for ≥ 7 days and (b) no pending
> security tickets against the PRE path.

### Stage 0 — Internal dogfood  ( current )

- **Who:** Engineering + security team.
- **Flags:** `PRE_ENABLED=True`, `ROLLOUT_STAGE='off'` (toggle hidden).
- **Surfaces:** Web dashboard only; extension and mobile PRE UIs
  behind `ENABLE_FHE_SHARE_DEBUG=1` localStorage flag.
- **Exit criteria:**
  - 14 days without P0/P1 bug reports on umbral-v1 share
    creation / use / revoke.
  - `test_share_lifecycle_pre.py` + `test_pre_service.py` +
    `test_sharing_status.py` green in CI.
  - Playwright canary
    [`frontend/e2e/fhe_share_sealed_fill.spec.js`](../../frontend/e2e/fhe_share_sealed_fill.spec.js)
    passing on the internal preview deployment.

### Stage 1 — Beta: web + browser extension + Android

- **Who:** 5% of opted-in beta users, then 25%.
- **Flags:** `PRE_ENABLED=True`, `ROLLOUT_STAGE='opt_in'`.
- **Surfaces enabled:** Web dashboard, Chrome/Firefox extension,
  Android Autofill via `fhe-autofill` Expo module.
- **iOS:** still simulated-v1 only — the ASCredentialProvider
  extension ships in Stage 2 pending App Store review.
- **Exit criteria:**
  - < 0.5 % share-create error rate (Sentry) for the beta cohort.
  - < 1 % share-use failure rate excluding recipient-device errors.
  - Mobile instrumentation tests
    ([`PendingFillStoreTest.kt`](../../mobile/modules/fhe-autofill/android/src/androidTest/java/expo/modules/fheautofill/PendingFillStoreTest.kt),
    [`PendingFillStoreTests.swift`](../../mobile/modules/fhe-autofill/ios/Tests/PendingFillStoreTests.swift))
    green in their CI lanes.

### Stage 2 — GA: default-on + iOS

- **Who:** 100 % of users.
- **Flags:** `PRE_ENABLED=True`, `ROLLOUT_STAGE='default_on'`.
- **Surfaces enabled:** Web, Extension, Android, **iOS**
  `ASCredentialProviderViewController`.
- **UX change:** "Use Umbral PRE" toggle in
  `CreateHomomorphicShareModal` defaults to **on**.
- **Exit criteria:** 30 days at GA with error rates within SLA.

### Stage 3 — Deprecate `simulated-v1`

- **Announcement window:** 90 days in-app banner on `simulated-v1`
  shares: "This share uses the legacy HMAC autofill format and will
  stop working on YYYY-MM-DD. Re-share to upgrade."
- **Migration path:** `POST /api/fhe-sharing/shares/<id>/upgrade/`
  creates a fresh `umbral-v1` share with identical metadata and
  revokes the old one. (Endpoint lives in `views.py`.)
- **Terminal cutover:** After the 90-day window, remove
  `simulated-v1` from the `cipher_suite` choices in
  `CreateShareSerializer`, mark all remaining `simulated-v1` rows
  `revoked=True`, and delete the HMAC secret key from the
  `FHEKeyStore`.

---

## 4. Operational runbook

### 4.1 Rollback from Stage N → Stage N-1

1. **Flip the flags.** In whichever secret manager / K8s configmap
   backs the Django settings:
   ```json
   {"FHE_SHARING_SETTINGS": {"PRE_ENABLED": false, "ROLLOUT_STAGE": "off"}}
   ```
2. **Hot-reload Django** (rolling restart is fine; flags are read
   once per request from `getattr(settings, 'FHE_SHARING_SETTINGS', {})`).
3. **Confirm**: `curl /api/fhe-sharing/status/` returns
   `"pre_umbral_v1": false`.
4. **Notify**: post an in-app banner reading "Homomorphic autofill
   is temporarily paused — existing shares continue to work." Use
   `simulated-v1` path for new shares while the issue is
   investigated.
5. **Investigate** with the audit log
   (`HomomorphicShare.access_logs` + `ShareAccessLog.outcome`) and
   Sentry PRE tag.

### 4.2 Monitoring

- **Server metrics** (emit from `fhe_sharing_service.py`):
  - `fhe_sharing.share.create.{suite}.{status}`
  - `fhe_sharing.share.use.{suite}.{status}`
  - `fhe_sharing.pre.reencrypt.latency_ms`
- **Client metrics:**
  - `preClient.umbral_unavailable_error_total` (JS / Kotlin / Swift)
  - `sealedAutofill.fill_success_total` / `fill_failure_total`

### 4.3 Key-compromise response

If an owner's Umbral secret key is suspected compromised:

1. Owner rotates via the `rotateIdentity()` flow
   (`preKeyRegistration.js` on web, `FheAutofillSettingsScreen.js`
   on mobile, `popupPanel.js` on extension).
2. Server invalidates all outstanding `umbral-v1` shares whose
   `delegating_pk` matches the old key:
   ```sql
   UPDATE fhe_sharing_homomorphicshare
      SET revoked = true, revoked_at = now()
    WHERE cipher_suite = 'umbral-v1'
      AND delegating_pk = :old_pk_bytes;
   ```
3. Recipients see a banner reading "Share revoked by owner". They
   can request re-share; the owner's new key encrypts a fresh
   `capsule` and generates a fresh `kfrag`.

---

## 5. Quick reference

| What                                     | Where                                                                            |
|------------------------------------------|----------------------------------------------------------------------------------|
| Wire format / schema                     | [`SPEC.md`](SPEC.md)                                                             |
| PRE server-side service                  | [`services/pre_service.py`](services/pre_service.py)                             |
| FHE policy gates (CKKS)                  | [`services/policy_fhe_service.py`](services/policy_fhe_service.py)               |
| Share lifecycle                          | [`services/fhe_sharing_service.py`](services/fhe_sharing_service.py)             |
| HTTP views                               | [`views.py`](views.py)                                                           |
| Serializers (base64url handling)         | [`serializers.py`](serializers.py)                                               |
| Feature-flag gate                        | `pre_is_enabled()` in `fhe_sharing_service.py`                                   |
| Frontend PRE client                      | [`frontend/src/services/fhe/preClient.js`](../../frontend/src/services/fhe/preClient.js) |
| Extension PRE client                     | [`browser-extension/src/fheShare/preClient.js`](../../browser-extension/src/fheShare/preClient.js) |
| Android native module                    | [`mobile/modules/fhe-autofill/android`](../../mobile/modules/fhe-autofill/android) |
| iOS credential provider                  | [`mobile/modules/fhe-autofill/ios/CredentialProvider`](../../mobile/modules/fhe-autofill/ios/CredentialProvider) |
| Backend tests                            | [`tests/`](tests/)                                                               |
| Frontend parity tests                    | [`frontend/src/services/fhe/__tests__/`](../../frontend/src/services/fhe/__tests__/) |
