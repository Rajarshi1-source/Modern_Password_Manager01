# Ambient Biometric Fusion (`ambient_auth`)

Passive environmental context as an authentication factor. Extends the
existing behavioral biometrics pipeline with signals captured from the
device's sensors and connectivity stack and fuses them into:

- A **trust score** (how confidently do we recognize where the user is?)
- A **novelty score** (how unusual is this context vs the learned baseline?)
- A **matched context** (optional named cluster: "Home", "Office", …)
- A set of **reasons[]** the UX can explain to the user

The backend never sees raw BSSIDs, BT MAC addresses, or audio samples.
Sensitive signals are folded into a **128-bit locality-sensitive hash
(LSH) digest** on-device using a per-user, per-device salt.

## Data flow

```text
[web / extension / mobile]
  collect coarse features (light bucket, motion class, connection, …)
  + sensitive inputs (BSSIDs, BLE MACs, audio) → hash with local salt
  ↓ POST /api/ambient/ingest/
[ambient_auth backend]
  validate + privacy fence → build 64-d embedding →
  nearest-context search → update centroids → persist observation →
  return { trust, novelty, matched_context, reasons, mfa_recommendation }
```

## Cross-feature integration

| Consumer | Behavior |
|---|---|
| `auth_module.assess_mfa_risk` | Pulls `latest_signal(user)` and nudges the risk score: trusted context → step-down; novel context → step-up. Only takes effect when `ENFORCEMENT_STAGE` is `advisory` or `enforce`. |
| `ml_security.batch_analyze_session` | Attaches ambient trust/novelty to the response and adjusts `threat_analysis.risk_score` accordingly. |
| `security.GeofenceZone` | Optional cross-link via `AmbientContext.linked_geofence`. If the user is inside the linked zone, ambient trust is corroborated rather than replaced. |

## Surfaces

| Surface | Module | Transport |
|---|---|---|
| Web app | `frontend/src/services/behavioralCapture/` + `frontend/src/services/ambient/` | `axios` → `/api/ambient/ingest/` every ~30 s when the capture engine is active |
| Browser extension | `browser-extension/src/ambient/` | MV3 `chrome.alarms` tick (default 5 min) → `fetch` |
| Mobile | `mobile/src/services/AmbientService.js` + `AmbientSetupScreen` | User-driven "capture now" + optional background runner |

All three surfaces use byte-compatible copies of the same LSH algorithm
(see `ambientEmbedding.js`) so a given environment produces identical
digests across devices.

## Privacy contract

1. Raw BSSIDs / BT MACs / audio samples never leave the device. The
   backend **rejects** payloads that contain fields matching known
   sensitive patterns (`bssid`, `wifi_list`, `audio_pcm`, `mac_list`,
   …).
2. Only the 128-bit salted LSH digest and bucketed coarse features are
   persisted.
3. The per-user local salt is rotatable by the user ("Reset baseline"
   in the dashboard). Rotating the salt forces a fresh backend profile.
4. Observation rows are append-only and user-scoped. The user can wipe
   them at any time via `POST /api/ambient/baseline/reset/`.

## Settings

Defined in `password_manager/settings.py`:

```python
AMBIENT_AUTH = {
    "ENABLED": True,
    # "collect": capture + score only, never affect MFA
    # "advisory": scoring feeds risk assessments, no hard blocks
    # "enforce": novel contexts can trigger step-up or hard blocks
    "ENFORCEMENT_STAGE": "collect",
    "EMBEDDING_DIM": 64,
    "CONTEXT_MATCH_RADIUS": 0.35,
    "TRUST_HIGH": 0.85,
    "NOVELTY_HIGH": 0.75,
    "CENTROID_EMA_ALPHA": 0.15,
    "MAX_CONTEXTS_PER_PROFILE": 16,
}
```

## Staged rollout recipe

1. **Collect** (default): ship the feature behind
   `ENFORCEMENT_STAGE=collect`. The UX shows scores + reasons but
   `assess_mfa_risk` ignores ambient signals. Use to build the
   baseline.
2. **Advisory**: flip to `advisory` once most users have ≥10
   observations. Ambient signals now nudge risk scores (±0.2) but
   never hard-block.
3. **Enforce**: flip to `enforce` only after measuring the false-reject
   rate on advisory. Now novelty ≥ 0.9 surfaces a hard-block flag
   (`ambient_hard_block_eligible`) that MFA gateways can act on.

Each step is a single setting change; no migration required.

## Tests

- Backend: `password_manager/ambient_auth/tests/test_fusion.py`
  (fusion math + privacy fence fuzz) and
  `test_views.py` (API round-trips).
- Web: `frontend/src/services/ambient/__tests__/ambientEmbedding.test.js`
  (determinism + salt rotation + no sensitive echo).

Run all:

```bash
# backend
cd password_manager
python -m pytest ambient_auth/tests -q

# web
cd frontend
npx vitest run src/services/ambient
```

## User-facing help copy (drop-in)

> **What is Ambient Trust?**
> We gently learn the places you use your password manager from the
> most — your home network, your office Bluetooth neighborhood, the
> rhythm of your device. Nothing that could identify those places ever
> leaves your phone or laptop: we only upload a salted 128-bit
> fingerprint. When your surroundings look like a place you've
> approved, we reduce friction. When they look brand new, we add an
> extra verification step.
>
> You can always **reset your baseline** to erase everything we
> learned, **toggle individual signals** (microphone, Bluetooth, …),
> or promote the current place to a trusted context with one tap.
