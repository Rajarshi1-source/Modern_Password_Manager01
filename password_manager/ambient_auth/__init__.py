"""
Ambient Biometric Fusion — passive environmental-context authentication.

Extends the existing behavioral-biometrics stack by fusing *ambient* signals
(Wi-Fi BSSID sets, BLE devices, ambient audio fingerprint, ambient light,
motion, battery drain curve, connection class, pointer pressure, scroll
momentum) into a per-observation *trust score* and a *matched context*.

Privacy contract (Hybrid Policy):
  * Sensitive raw signals (BSSIDs, BT MACs, audio PCM) NEVER leave the
    device. Clients compute a 128-bit locality-sensitive hash (LSH) under
    a per-user local salt and ship only the digest.
  * Coarse features (light bucket, motion class, battery slope bucket,
    connection class, effective network type, pointer pressure bucket,
    scroll momentum bucket, geohash bucket) ship as structured JSON.
  * The server stores only opaque digests + bucketed features + derived
    scores, never raw signals.

Three client surfaces share a single wire protocol:
  * Web app (`frontend/src/services/behavioralCapture/*` + new ambient
    collectors + `ambientEmbedding.js`).
  * Browser extension (`browser-extension/src/ambient/*` — MV3 service
    worker, reuses the same embedding helper).
  * React Native mobile (`mobile/src/services/ambient/*` — WiFi BSSID
    scan, BLE scan, sensor fusion).

Decision integration:
  * `ambient_auth.services.ambient_fusion_service.ingest` returns a trust
    score in [0, 1] + novelty score + matched context id + structured
    `reasons[]` for UX transparency.
  * Adaptive MFA (`auth_module.assess_mfa_risk`) consumes the score to
    step down factor count when a trusted context is matched, and raise
    risk when a novel context is detected.
  * Session anomaly (`ml_security.batch_analyze_session`) ingests
    `ambient_score` / `ambient_novelty` as additional session_data keys.
"""

default_app_config = "ambient_auth.apps.AmbientAuthConfig"
