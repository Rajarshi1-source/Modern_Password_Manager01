"""Heartbeat / HRV authentication.

The user captures ~30 s of PPG (photoplethysmography) with their
phone camera. The browser extracts HRV features locally — only the
feature vector (RMSSD, SDNN, pNN50, mean HR, LF/HF, etc.) leaves the
device. The server-side matcher uses Mahalanobis distance vs a rolling
per-user baseline.

A secondary detector watches for stress/coercion signatures (low RMSSD
+ elevated HR vs baseline). When it fires during ``verify``, the bridge
in :mod:`heartbeat_auth.services.duress_bridge` hands the user the
existing decoy vault from
:mod:`security.services.duress_code_service.DuressCodeService` instead
of the real one, without any UI difference — the anti-coercion
property.
"""

default_app_config = 'heartbeat_auth.apps.HeartbeatAuthConfig'
