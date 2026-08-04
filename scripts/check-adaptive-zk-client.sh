#!/usr/bin/env bash
#
# Zero-knowledge guard for the adaptive-password client code.
#
# The v1 wire contract POSTed raw passwords to /adaptive/suggest/ and
# /adaptive/apply/. The backend now rejects those fields fail-closed (HTTP 422
# via RejectPlaintextMixin), but a client that still *sends* them puts the
# plaintext on the wire and into client-side logs before the rejection ever
# happens. mobile/src/services/AdaptivePasswordApi.js did exactly that until it
# was deleted; this guard stops the shape coming back.
#
# Scoped to client source only. Test files are excluded on purpose: the leak
# tests (adaptiveZkLeak.test.jsx, e2e/adaptive_password.spec.ts) must name these
# fields in order to assert they are absent.
#
# Usage: scripts/check-adaptive-zk-client.sh
# Exit 0 = clean, 1 = violation.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# v1 raw-password payload fields, and the deprecated server-side suggestion
# endpoint (HTTP 410) whose only caller shape required POSTing the password.
PATTERN='original_password|adapted_password|adaptive/suggest'

CLIENT_DIRS=()
for d in frontend/src mobile desktop/src browser-extension/src; do
  [ -d "$d" ] && CLIENT_DIRS+=("$d")
done

if [ ${#CLIENT_DIRS[@]} -eq 0 ]; then
  echo "No client directories found — nothing to check."
  exit 0
fi

hits="$(grep -rEn --binary-files=without-match "$PATTERN" "${CLIENT_DIRS[@]}" \
  --include='*.js' --include='*.jsx' --include='*.ts' --include='*.tsx' \
  --exclude-dir=node_modules \
  --exclude-dir=__tests__ \
  --exclude-dir=__mocks__ \
  --exclude-dir=e2e \
  --exclude='*.test.*' \
  --exclude='*.spec.*' || true)"

if [ -n "$hits" ]; then
  echo "::error::Adaptive-password zero-knowledge violation in client code."
  echo "These files reference the v1 raw-password contract:"
  echo "$hits"
  echo
  echo "The server never receives a raw password. Send a client-keyed"
  echo "fingerprint instead (cryptoService.passwordFingerprint) and pull"
  echo "GET /api/security/adaptive/preference-model/ for suggestions."
  echo "See docs/adaptive-password-zk-remediation-plan.md."
  exit 1
fi

echo "OK: no adaptive v1 raw-password contract in client code."
