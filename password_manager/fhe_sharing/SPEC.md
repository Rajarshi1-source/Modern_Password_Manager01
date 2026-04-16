# `fhe_sharing` — Homomorphic Autofill Specification v2 (PRE + FHE Hybrid)

Status: v2 draft. Supersedes the simulated-HMAC design documented inline in
[autofill_circuit_service.py](services/autofill_circuit_service.py).

## 1. Goals

1. **Use without see.** A share recipient can autofill a password into a
   form input element but cannot recover the plaintext password under
   any analysis performed *in their own application / page context*.
2. **Server is a proxy, not an oracle.** The server stores only
   ciphertexts and a re-encryption delegation key. It cannot recover
   the password.
3. **Cross-platform parity.** Identical byte-level payloads travel
   between the backend, web frontend, browser extension, Android
   autofill service, and iOS credential provider.
4. **Backward compat.** Existing `cipher_suite='simulated-v1'` shares
   keep working for revocation/list until drained; no forced migration
   of historical rows.

## 2. Cryptographic suite

### 2.1 Proxy Re-Encryption (PRE) — the password ciphertext

- **Primitive**: Umbral (BBS98-style threshold PRE) over `secp256k1`.
- **Reference implementations**:
  - Backend: [`pyUmbral`](https://github.com/nucypher/pyUmbral) `>=0.3`.
  - Web / Extension: `@nucypher/umbral-pre` (WASM, same algorithm).
  - Mobile (RN): `@nucypher/umbral-pre` via rn-friendly WASM loader.
  - Android native: `umbral-pre-rust` via Rust FFI (future).
  - iOS native: `umbral-pre-rust` via Swift FFI (future).
- **Threshold**: `m=1, n=1` in v1. Real team-share `m-of-n` reserved
  for a future minor bump (`umbral-v2`).
- **Envelope**: Umbral's default KEM encrypts a random symmetric key
  and uses ChaCha20-Poly1305 over the UTF-8 password plaintext.

### 2.2 Auxiliary homomorphic policy layer — optional gates

Non-secret computations over ciphertexts using TenSEAL CKKS from
[fhe_service/services/seal_service.py](../fhe_service/services/seal_service.py):

| Gate                  | Input ciphertext                           | Output            |
|-----------------------|--------------------------------------------|-------------------|
| `strength_threshold`  | CKKS ciphertext of `len(password)`         | Encrypted boolean |
| `breach_distance`     | CKKS ciphertext of Hamming-like scalar     | Encrypted scalar  |
| `expiry_countdown`    | CKKS ciphertext of remaining days          | Encrypted scalar  |

These gates **never reveal the plaintext password** — they accept
ciphertext inputs derived during vault-item creation and operate on
derived numeric summaries, not the password text. The server holds
only the CKKS evaluation context and a service-wide decryption key
for the boolean output. The encryption happens client-side at share
creation.

## 3. Data model

### 3.1 Key registry extensions — `FHEKeyStore`

Add to [fhe_service/models.py::FHEKeyStore](../fhe_service/models.py):

```
umbral_public_key         : BinaryField (33 B compressed secp256k1 pk)
umbral_verifying_key      : BinaryField (33 B compressed secp256k1 pk)
umbral_signer_public_key  : BinaryField (33 B compressed secp256k1 pk)
pre_schema_version        : PositiveSmallIntegerField  (1 for Umbral v1)
```

Secret keys (`sk_O`, `sk_R`, `sk_signer`) stay client-side,
encrypted under the user's master key via `secureVaultCrypto`.

### 3.2 `HomomorphicShare` extensions

New fields (migration `0002_pre_fields`):

```
cipher_suite   : CharField(max_length=24, default='simulated-v1')
capsule        : BinaryField (Umbral capsule)
ciphertext     : BinaryField (Umbral ChaCha20-Poly1305 payload)
kfrag          : BinaryField (Umbral key fragment)
delegating_pk  : BinaryField (owner's pk)
verifying_pk   : BinaryField (owner's verifying pk)
receiving_pk   : BinaryField (recipient's pk)
```

Invariants per row:
- `cipher_suite='simulated-v1'`: legacy row; `capsule`/`ciphertext`/`kfrag` are `NULL`.
- `cipher_suite='umbral-v1'`: all six new fields are non-null.

## 4. End-to-end flow

```
OWNER  (sk_O, pk_O)                       RECIPIENT (sk_R, pk_R)
  |                                                 ^
  | 1. GET /keys/<recipient_username>/              |
  | <-------- pk_R ----------------------           |
  |                                                 |
  | 2. local:                                       |
  |    (capsule, ciphertext) = umbral.encrypt(pk_O, pw)
  |    kfrag                 = umbral.generate_kfrags(
  |                                sk_O, pk_R, signer_sk, m=1, n=1)[0]
  |                                                 |
  | 3. POST /shares/                                |
  |    { capsule, ciphertext, kfrag,                |
  |      delegating_pk, verifying_pk, receiving_pk, |
  |      cipher_suite='umbral-v1', ... }            |
  |                                                 |
  | ------------->  SERVER  <----------------       |
  |                                                 |
  |                                      4. POST /shares/<id>/use/ { domain }
  |                                         server validates + runs:
  |                                         cfrag = umbral.reencrypt(
  |                                             share.capsule, share.kfrag)
  |                                                 |
  |                                      5. response
  |                                         { capsule, cfrag, ciphertext,
  |                                           delegating_pk, verifying_pk }
  |                                                 v
  |                                      6. local (sealed context):
  |                                         pw = umbral.decrypt_reencrypted(
  |                                             sk_R, pk_O, capsule,
  |                                             [cfrag], ciphertext)
  |                                         inject(pw) -> DOM / IME / AS
  |                                         zeroize(pw)
```

## 5. Sealed injection contract

Every sealed surface must satisfy:

1. **No page JS access.** The plaintext never enters an execution
   context controllable by an adversary's page scripts.
2. **No persistence.** Plaintext is never written to any storage
   (`chrome.storage.*`, `localStorage`, `AsyncStorage`, keychain,
   keystore, clipboard).
3. **Short lifetime.** Between PRE decrypt and DOM / IME write, the
   plaintext must live no longer than 20 ms in RAM.
4. **Audit trail.** Each sealed fill emits a `ShareAccessLog`
   `action='autofill_used'` entry *before* the plaintext is decrypted,
   so the audit log is never missing a successful use.

Platform-specific realisation:

| Surface          | Sealed realisation                                                   |
|------------------|----------------------------------------------------------------------|
| Browser extn     | `world: 'ISOLATED'` content script + native value setter bypass      |
| Web fallback     | `<iframe sandbox="allow-scripts" srcdoc>` + clipboard w/ auto-clear  |
| Android          | `AutofillService.onFillRequest` returns `Dataset` via framework IPC  |
| iOS              | `ASCredentialProviderViewController.completeRequest`                 |

## 6. Revocation semantics

- **Active share revocation** (`is_active=False`): server refuses
  `/use/` — no new `cfrag` is produced.
- **kfrag deletion** (hard revoke): `share.kfrag = None` and
  `is_active=False`; server physically cannot re-encrypt any more.
- **Non-retroactive caveat**: a `cfrag` already delivered to a
  recipient device is usable to decrypt `ciphertext` forever,
  assuming the recipient also has their `sk_R`. The owner must set a
  short `expires_at` to minimise this window. Clients MUST NOT cache
  `cfrag` beyond a single autofill injection.

## 7. Versioning

```
cipher_suite = 'umbral-v1'     # Umbral 0.3, m=1 n=1, ChaCha20-Poly1305
cipher_suite = 'umbral-v2'     # reserved: threshold m>1 team shares
cipher_suite = 'simulated-v1'  # legacy HMAC scaffold (deprecated)
```

`pre_schema_version` on `FHEKeyStore` increments only when the key
encoding format itself changes. Adding new fields (e.g. a future
X25519 signing key) bumps it.

## 8. Wire format

All binary fields are raw bytes, base64url-encoded over the JSON API.

```
POST /api/fhe-sharing/shares/
{
  "vault_item_id": "...",
  "recipient_username": "...",
  "domain_constraints": ["github.com"],
  "expires_at": "2026-05-01T00:00:00Z",
  "max_uses": 100,
  "cipher_suite": "umbral-v1",
  "capsule": "<b64url>",
  "ciphertext": "<b64url>",
  "kfrag": "<b64url>",
  "delegating_pk": "<b64url>",
  "verifying_pk": "<b64url>",
  "receiving_pk": "<b64url>"
}
```

```
POST /api/fhe-sharing/shares/<uuid>/use/
{ "domain": "github.com", "form_field_selector": "input[type=password]" }
```

Response (bumped `schema_version`: 2):

```
{
  "success": true,
  "schema_version": 2,
  "cipher_suite": "umbral-v1",
  "capsule":        "<b64url>",
  "cfrag":          "<b64url>",
  "ciphertext":     "<b64url>",
  "delegating_pk":  "<b64url>",
  "verifying_pk":   "<b64url>",
  "target_selector": "input[type=password]",
  "sealed_envelope": {
    "version": 2,
    "nonce": "<hex>",
    "instructions": {
      "method": "sealed_inject",
      "clear_after_ms": 0,
      "prevent_copy": true,
      "prevent_inspect": true
    }
  },
  "use_count": 1,
  "remaining_uses": 99
}
```

## 9. Failure modes

| Failure                                 | API result                          |
|-----------------------------------------|--------------------------------------|
| feature flag off                        | 403 `{error: "FHE sharing disabled"}` |
| `cipher_suite` unknown                  | 400 `{error: "Unsupported cipher_suite"}` |
| recipient has no registered umbral pk   | 404 on `GET /keys/<user>/`           |
| share not owned by caller               | 403                                   |
| share revoked / expired / usage maxed   | existing 400                          |
| domain constraint violated              | existing 400                          |
| PRE reencrypt internal error            | 500 `{error: "re-encryption failed"}` |
| client: wrong sk_R                      | Umbral decrypt raises locally        |
| client: tampered `cfrag`                | Umbral verification raises locally   |

## 10. Non-goals / out of scope

- Compromised recipient device.
- OS-level screenshotting during autofill.
- Cached `cfrag` replay within its TTL.
- Quantum adversaries (secp256k1 is not PQ-safe).
- Arbitrary computation on passwords (true FHE of keystroke circuits).
