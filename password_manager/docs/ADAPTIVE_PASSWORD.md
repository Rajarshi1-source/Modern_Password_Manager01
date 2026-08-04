# 🧬 Epigenetic Password Adaptation

## Overview

The Epigenetic Password Adaptation feature uses reinforcement learning and behavioral biometrics to suggest password modifications that are easier for you to remember and type, while maintaining strong security.

## Privacy Guarantees

| Guarantee | Description |
|-----------|-------------|
| **Zero-knowledge (v2)** | The raw password never leaves the device. The client sends only a keyed HMAC fingerprint + coarse features (length bucket, bucketized timings) and masked previews; the server rejects any plaintext field (HTTP 422). |
| **Client-side suggestions** | Suggestions are generated in the browser from a downloaded preference model — the server never scores a raw password. |
| **No raw keystrokes stored** | Only aggregated timing metrics |
| **Differential privacy** | All metrics have ε-DP protection (ε=0.5) |
| **Opt-in by default** | Feature must be explicitly enabled |
| **Transparent** | Full visibility into what data is collected |
| **GDPR compliant** | Export and delete your data anytime |

## The fingerprint key

Everything the client sends is keyed by a fingerprint derived on the device:

```text
fpKey       = Argon2id(masterPassword, salt = `${fingerprint_salt}:adaptive-fp`)
fingerprint = base64url(HMAC-SHA256(fpKey, "adaptive-pw|" + password))[:24]
```

`fingerprint_salt` is **non-secret**: inverting a stored fingerprint still needs
the master password, which the server never receives. It is minted per user by
`POST /adaptive/enable/` and returned by `GET /adaptive/config/`.

`fp_key_version` is the **key era**. Because `fpKey` derives from the master
password, changing that password changes every fingerprint. Rotating explicitly
via `POST /adaptive/rotate-fingerprint-key/` makes the break visible instead of
leaving the client writing fingerprints that silently never match:

- every v2 write must carry the current `fp_key_version` — a stale one is
  rejected with **HTTP 409**, not silently recorded;
- the stored era is stamped from the server's config, never from the request
  body, so a client cannot backdate a row into a dead era;
- prior-era `TypingSession` / `PasswordAdaptation` rows are retained for audit
  but drop out of history, stats and rollback. They remain in the GDPR export.

The aggregate `UserTypingProfile` (WPM, error-prone positions, substitution
preferences) is **not** era-scoped — it describes the user, not any particular
password, so it survives a rotation intact.

> Fingerprints are only as strong as the master password: an adversary who
> already holds it could brute-force `fingerprint(pw)` over a candidate
> dictionary, since HMAC is fast. Out of scope under the stated threat model
> (hostile server, master password never transmitted), but worth knowing.

## Getting Started

### 1. Enable Typing Pattern Capture

```javascript
// Frontend
import { adaptivePasswordService } from './Components/security/TypingPatternCapture';

// Enable with consent — returns the fingerprint salt + key era
const { fingerprint_salt, fp_key_version } = await adaptivePasswordService.enable({
  frequencyDays: 30,
  allowCentralized: true,
  allowFederated: false,
});

// Bind the salt to your unlocked CryptoService instance
const fingerprint = adaptivePasswordService.makeFingerprinter(
  cryptoService, fingerprint_salt,
);
```

### 2. Use Typing Pattern Input

```jsx
import { TypingPatternCapture } from './Components/security/TypingPatternCapture';

<TypingPatternCapture
  inputRef={passwordInputRef}
  enabled={userHasConsented}
  onPatternCaptured={handlePattern}
  // Zero-knowledge v2: inject a keyed-fingerprint fn; the raw password is used
  // only locally to derive the fingerprint and is never transmitted.
  fingerprint={fingerprint}
  // Required: the era the fingerprint fn was derived under (409 on mismatch).
  fpKeyVersion={fp_key_version}
/>
```

### 2b. After a master-password change

```javascript
const { fingerprint_salt, fp_key_version } =
  await adaptivePasswordService.rotateFingerprintKey();
// Rebuild the fingerprinter from the new salt and use the new era from here on.
```

### 3. Review Suggestions

After 10+ typing sessions, the system will suggest adaptations:

```jsx
<AdaptivePasswordSuggestion
  adaptation={suggestion}
  onAccept={handleAccept}
  onReject={handleReject}
/>
```

## API Reference

### Configuration Endpoints

| Endpoint | Method | Description |
|----------|--------------|-------------|
| `/adaptive/config/` | GET | Get configuration, incl. `fingerprint_salt` + `fp_key_version` |
| `/adaptive/enable/` | POST | Enable with consent; mints the `fingerprint_salt` |
| `/adaptive/disable/` | POST | Disable feature |
| `/adaptive/rotate-fingerprint-key/` | POST | Re-base the fingerprint key (`{"confirm": true}`) |

### Typing Session

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/adaptive/record-session/` | POST | Record typing session (v2: keyed fingerprint + coarse features + `fp_key_version`; raw password rejected) |

### Adaptation

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/adaptive/preference-model/` | GET | Download the learned preference model (client generates suggestions locally) |
| `/adaptive/suggest/` | POST | **Deprecated (HTTP 410)** — server-side suggestion removed; use the preference-model pull instead |
| `/adaptive/apply/` | POST | Apply adaptation (v2: original/adapted fingerprints + `fp_key_version` + substitution classes + masked previews; raw passwords rejected) |
| `/adaptive/rollback/` | POST | Rollback to previous |

### Profile & History

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/adaptive/profile/` | GET | Get typing profile |
| `/adaptive/history/` | GET | Get adaptation history |
| `/adaptive/stats/` | GET | Get evolution stats |

### Feedback

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/adaptive/feedback/` | POST | Submit feedback |
| `/adaptive/feedback/{id}/` | GET | Get feedback for adaptation |

### Data Management (GDPR)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/adaptive/data/` | DELETE | Delete all data |
| `/adaptive/export/` | GET | Export all data |

## Configuration

Settings in `settings.py`:

```python
ADAPTIVE_PASSWORD = {
    'ENABLED': True,
    'DEFAULT_OPT_IN': False,
    'SUGGESTION_FREQUENCY_DAYS': 30,
    'DIFFERENTIAL_PRIVACY_EPSILON': 0.5,
    'AUTO_APPLY_THRESHOLD': 0.9,
    'MAX_ROLLBACK_DEPTH': 10,
}
```

`ENABLED` is a deployment kill switch. When it is off, every learning endpoint
returns **HTTP 503** `{"code": "feature_disabled"}`. The GDPR endpoints —
`/adaptive/disable/`, `/adaptive/data/` (erasure) and `/adaptive/export/`
(portability) — stay reachable, because opting out and getting your data back
are rights rather than features.

## Error codes

| Status | When |
|--------|------|
| `400` | Malformed payload, wrong/missing `schema_version`, feature not enabled for the user |
| `409` | `fp_key_version` does not match the server's current era — re-fetch `/adaptive/config/` and re-derive |
| `410` | `/adaptive/suggest/` (server-side suggestion removed under ZK v2) |
| `422` | A raw-password field was present (zero-knowledge violation) |
| `503` | `ADAPTIVE_PASSWORD['ENABLED']` is off for this deployment |

## Security

- All password data is encrypted end-to-end
- Full rollback support for all changes
- Differential privacy on all aggregated metrics
- Suggestion confidence scores come from the exported preference model

> **Not yet implemented:** the reinforcement-learning policy. The weekly
> `update_rl_model_from_feedback` task computes rewards but does not yet persist
> a model, so `substitution_weights` is still close to the static leetspeak
> baseline. See `docs/epigenetic-adaptation-implementation-plan.md` §5 (Phase 3).
>
> **Not yet implemented:** the strength guard. Leetspeak substitutions are
> modelled by common cracking rule-sets, so an adaptation can currently reduce
> guess-resistance. Phase 2 of the same plan adds a client-side zxcvbn gate that
> rejects any non-improving candidate.
