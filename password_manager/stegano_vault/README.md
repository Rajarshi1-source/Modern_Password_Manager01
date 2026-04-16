# `stegano_vault` — Steganographic Hidden Vault

A **plausible-deniability** vault layer built on top of two independent
cryptographic primitives:

1. **`HiddenVaultBlob v1`** (`password_manager/hidden_vault/`)
   A fixed-size two-slot authenticated-encryption container (Argon2id +
   AES-256-GCM) whose bytes reveal nothing about whether the hidden
   slot contains a real vault, a decoy vault, or random garbage.
2. **PNG LSB steganography** (`stegano_vault/services/png_lsb_service.py`)
   A keyed least-significant-bit embedding that hides the opaque
   `HiddenVaultBlob` inside the RGB channels of a user-supplied cover
   PNG. The cover image still *looks* like a normal photo.

The combination lets a user store a vault on public infrastructure
(Imgur / Flickr / Google Photos / a phone gallery) while retaining
cryptographic deniability about *whether a real vault exists at all*.

---

## 1. Architecture

```
                          +---------------------------+
                          |  User (browser / mobile)  |
                          +------------+--------------+
                                       |  decides which slot is "real"
                                       |  and which is "decoy"
                                       v
                 +---------------------+----------------------+
                 |  hiddenVaultEnvelope (frontend/extension/mobile) |
                 |  + argon2-browser / react-native-argon2         |
                 |  + WebCrypto / node AES-GCM                    |
                 +---------------------+----------------------+
                                       |  opaque blob (exactly tier_bytes)
                                       v
                          +---------------------------+
                          |  pngLsb (embed/extract)   |
                          +------------+--------------+
                                       |  stego PNG bytes
                                       v
                 +---------------------+----------------------+
                 |   POST /api/stego/store/ (opaque PNG only) |
                 |   GET  /api/stego/<id>/  (download PNG)    |
                 +--------------------------------------------+
```

The server **never** sees:

* the master password,
* the duress password,
* the real vault payload,
* the decoy vault payload,
* or the per-slot AES keys.

It only sees PNG bytes that are indistinguishable from a normal
photograph until someone runs statistical steganalysis *and* holds one
of the two passwords.

---

## 2. API surface (`/api/stego/`)

| Method | Path              | Purpose                                                 |
|--------|-------------------|---------------------------------------------------------|
| GET    | `/config/`        | Feature flag + tier info for clients.                   |
| POST   | `/embed/`         | Stateless: cover PNG + opaque blob → stego PNG.         |
| POST   | `/extract/`       | Stateless: stego PNG → opaque blob.                     |
| POST   | `/store/`         | Persist a stego PNG + label + tier.                     |
| GET    | `/`               | List this user's stego vaults.                          |
| GET    | `/<uuid>/`        | Download the raw stego PNG bytes.                       |
| DELETE | `/<uuid>/`        | Delete a stored stego vault.                            |
| GET    | `/events/`        | Audit log for embed/extract/store/download/delete.      |

All endpoints require `IsAuthenticated`. The feature flag
(`STEGO_VAULT.ENABLED`) gates every endpoint and returns `403` when
off.

---

## 3. Plausible deniability delegation (`DuressCode` integration)

Each `security.DuressCode` row exposes three extra fields:

```python
delegate_to_hidden_vault = BooleanField(default=False)
hidden_vault_slot        = PositiveSmallIntegerField(default=0)
stego_vault              = ForeignKey("stegano_vault.StegoVault", ...)
```

When `delegate_to_hidden_vault=True` and a duress code is triggered,
`DuressCodeService._decoy_from_hidden_vault`:

1. Reads the PNG bytes from the linked `StegoVault.image`.
2. Extracts the opaque blob with `png_lsb_service.extract_blob_from_png`.
3. Calls `hidden_vault.decode(blob, unlock_password)`.
4. On success, returns the decoded JSON as the "decoy" payload.

Crucially, **the server cannot distinguish the real slot from the
decoy slot** — both paths look identical in the DB. An adversary who
only has DB access cannot prove whether a second vault exists.

If decoding fails (wrong password, corrupted blob, feature flag off),
the service silently falls back to the legacy `DecoyVault` table so
the UX contract (“show *something* on duress”) is preserved.

---

## 4. Threat model (explicit)

### 4.1 What we defend against

| Threat                                                     | Defence                                                                                                     |
|------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------|
| Server-side DB dump reveals real + decoy vaults            | Blob is opaque to the server. Only AES-GCM ciphertext + random padding is stored.                           |
| Coerced disclosure of *the* password                       | User reveals decoy password → decoy slot decrypts → appears to be a valid vault. Real slot remains opaque. |
| Forensic comparison of user device vs. server              | Stego PNG is byte-for-byte the same on disk, in transit, and in the DB.                                     |
| Rogue server operator modifies stored blob                 | AES-GCM authenticates per-slot payloads; tampering yields `WrongPasswordError`, not a subtly wrong vault.   |
| Brute force of low-entropy decoy password                  | Argon2id with `time_cost=3, memory_cost=64 MiB` per slot.                                                   |
| Adversary with DB access trying to prove "real vault exists" | Fixed-size blob (32 KiB / 128 KiB / 1 MiB tiers) + random padding + random unused-slot key.                 |

### 4.2 What we explicitly do **not** defend against

1. **Compelled disclosure of *both* passwords** — plausible deniability
   assumes the adversary only knows *a* password, not every password.
   If a judge or a wrench-wielder obtains the real password too, the
   real slot is recoverable.
2. **Statistical steganalysis of the cover image** — PNG LSB is the
   simplest steganography and is detectable by e.g. chi-square or RS
   analysis if the adversary has the *original* cover. Mitigation:
   users should treat the cover as consumed (never publish the
   pre-embedding original) and prefer natural photos with high
   per-channel entropy.
3. **Lossy re-encoding by hosting providers** — Imgur, Facebook,
   WhatsApp all silently re-encode uploaded images (often to JPEG or
   stripped PNG). This destroys the LSB payload. The `image_mime`
   field is locked to `image/png` and JPEG input is rejected, but
   nothing prevents a hosting provider from re-encoding *after*
   upload. Mitigation: prefer cold storage (local disk, encrypted
   backup) or providers known to preserve PNG bytes (Telegram "send
   as file", direct S3, email attachment).
4. **Cover image hash comparison** — if the adversary has the exact
   original cover PNG they can diff it against the stego PNG and see
   LSB perturbation. The `cover_hash` field lets *users* detect this
   forensically; it is not a defence.
5. **Side-channel leakage of slot indices** — the duress-service log
   records `slot_index` in `StegoAccessEvent.details`. If the audit
   log itself is compromised, an adversary learns which slot was
   touched at which time. Mitigation: audit retention policy +
   encryption-at-rest of the `StegoAccessEvent.details` JSON.
6. **Mobile KDF downgrade** — if `react-native-argon2` is missing at
   runtime, `StegoVaultService` deliberately throws an explicit
   `Error("argon2 native module not available")` rather than silently
   degrading to a weaker KDF. Clients must install the native module.

### 4.3 Cryptographic invariants

These MUST hold across Python / web / extension / mobile
implementations (see `hidden_vault/tests/vectors.json`):

* Blob length is exactly `tier_bytes(tier)`.
* Header layout matches `hidden_vault/SPEC.md` byte-for-byte.
* `decode(blob, real_password).payload == real_payload`.
* `decode(blob, decoy_password).payload == decoy_payload`.
* `decode(blob, wrong_password)` raises `WrongPasswordError` —
  never returns the decoy slot.
* Both slot nonces are distinct and random.
* Unused slots hold `AES-GCM(random_key, random_payload)` with
  random framing so the two slots are byte-indistinguishable.

---

## 5. Configuration

`password_manager/settings.py`:

```python
STEGO_VAULT = {
    'ENABLED':        os.environ.get('STEGO_VAULT_ENABLED', 'True').lower() == 'true',
    'MAX_IMAGE_MB':   int(os.environ.get('STEGO_VAULT_MAX_IMAGE_MB', '8')),
    'TIERS_BYTES':    [32768, 131072, 1048576],
    'ROLLOUT_STAGE':  os.environ.get('STEGO_VAULT_STAGE', 'opt_in'),
}

HIDDEN_VAULT = {
    'ENABLED':         os.environ.get('HIDDEN_VAULT_ENABLED', 'True').lower() == 'true',
    'KDF_TIME_COST':   int(os.environ.get('HIDDEN_VAULT_KDF_T', '3')),
    'KDF_MEMORY_KIB':  int(os.environ.get('HIDDEN_VAULT_KDF_M', '65536')),
    'KDF_PARALLELISM': int(os.environ.get('HIDDEN_VAULT_KDF_P', '1')),
}
```

`ROLLOUT_STAGE` values:

* `off`        — feature flag off, all `/api/stego/*` returns 403.
* `opt_in`     — default. Feature is reachable only via
  `/security/stego` dashboard and the duress "upgrade" banner.
* `default_on` — the Stego Vault Dashboard is linked from the main
  navigation. Does **not** force anyone's vault into stego mode.

---

## 6. Staged rollout plan

### Stage 0 — Internal dog-food (current)

* `STEGO_VAULT_STAGE=opt_in`, `STEGO_VAULT_ENABLED=True`.
* Only surfaced via:
  * Explicit route `/security/stego`
  * "Upgrade your decoy vault" banner in `DuressCodeManager`.
* Requires the user to manually select a cover image and passwords.
* Metrics: `StegoAccessEvent` count, decode success rate, `embed_ms`.

### Stage 1 — Beta cohort (next)

* Entry conditions:
  * Stage 0 has > 50 successful `embed` + `extract` pairs.
  * Zero open Sentry issues tagged `stegano_vault`.
  * Mobile app shipped with `react-native-argon2` bundled.
* Changes:
  * Add "Create stego backup" CTA in `VaultBackup` screen.
  * Expose the browser-extension popup "Unlock from stego image"
    action by default (`stego-action-slot` visible).
* Rollback: set `STEGO_VAULT_ENABLED=False`; all clients gracefully
  degrade (403 on `/api/stego/*`, UI hides the dashboard).

### Stage 2 — Default-on (future)

* Entry conditions:
  * Stage 1 has run for 30 days without a decode-success-rate drop
    below 99% (modulo wrong-password attempts).
  * Audit log retention policy finalised.
  * Threat model reviewed by a second engineer.
* Changes:
  * `STEGO_VAULT_STAGE=default_on`.
  * Dashboard linked from primary security nav.
  * New accounts get a suggested "create stego backup" onboarding
    step (still opt-in per user; never forced).

### Stage 3 — Mobile + extension parity locked in

* Entry conditions:
  * Stage 2 mature.
  * Extension and mobile have parity tests running in CI against
    `hidden_vault/tests/vectors.json`.
* Changes:
  * Deprecate legacy server-stored `DecoyVault` JSON for users who
    have `delegate_to_hidden_vault=True`.
  * Remove the graceful-fallback branch once zero users hit it for
    two release cycles.

### Kill switch

At any stage, setting `STEGO_VAULT_ENABLED=False` disables:

* all `/api/stego/*` endpoints (403),
* the DuressCode hidden-vault delegation path (falls back silently
  to the legacy DecoyVault table).

Existing `StegoVault` rows are **not** deleted — a re-enable brings
them back online immediately.

---

## 7. Where to look in the code

| Concern                               | File                                                                          |
|---------------------------------------|-------------------------------------------------------------------------------|
| Envelope spec                         | `password_manager/hidden_vault/SPEC.md`                                       |
| Envelope reference impl (Python)      | `password_manager/hidden_vault/envelope.py`                                   |
| Cross-language test vectors           | `password_manager/hidden_vault/tests/vectors.json`                            |
| PNG LSB (Python)                      | `password_manager/stegano_vault/services/png_lsb_service.py`                  |
| Hidden-vault gluing + storage         | `password_manager/stegano_vault/services/hidden_vault_service.py`             |
| Django REST endpoints                 | `password_manager/stegano_vault/views.py`                                     |
| Duress delegation hook                | `password_manager/security/services/duress_code_service.py::_decoy_from_hidden_vault` |
| Envelope impl (web)                   | `frontend/src/services/hiddenVault/hiddenVaultEnvelope.js`                    |
| PNG LSB (web)                         | `frontend/src/services/stego/pngLsb.js`                                       |
| React dashboard                       | `frontend/src/Components/security/StegoVaultDashboard.jsx`                    |
| Extension popup action                | `browser-extension/src/stego/stegoAction.js`                                  |
| Mobile service                        | `mobile/src/services/StegoVaultService.js`                                    |
| Mobile screen                         | `mobile/src/screens/StegoVaultScreen.js`                                      |

---

## 8. Open work items

* Write a property-based test that fuzzes `encode/decode` across
  arbitrary passwords and payload lengths within `slot_payload_len(tier)`.
* Add a Sentry breadcrumb for `WrongPasswordError` frequency so that
  duress flows can be distinguished from real typos in aggregate.
* Add a `compare_with_original_cover(cover_hash)` endpoint so users
  can verify a hosting provider has not re-encoded their stego PNG.
