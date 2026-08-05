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

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)" || {
  echo "::error::Could not resolve the repo root from ${BASH_SOURCE[0]}." >&2
  exit 1
}
cd "$REPO_ROOT" || exit 1

# v1 raw-password payload fields, and the deprecated server-side suggestion
# endpoint (HTTP 410) whose only caller shape required POSTing the password.
PATTERN='original_password|adapted_password|adaptive/suggest'

# frontend/src is the primary client for this feature (TypingPatternCapture.jsx,
# adaptiveFeatures.js, cryptoService.js) and is always present in a real
# checkout of this repo (no sparse-checkout is used in CI). If it's missing,
# fail loudly rather than silently reporting "OK" having scanned nothing — the
# previous "no client directories found, exit 0" behavior meant an adversarial
# rename/removal of every candidate directory would produce a green check
# without the scan ever running, defeating the guard's entire purpose.
if [ ! -d "frontend/src" ]; then
  echo "::error::frontend/src is missing — cannot verify the adaptive-password ZK contract. Refusing to report success having scanned nothing." >&2
  exit 1
fi

CLIENT_DIRS=(frontend/src)
for d in mobile desktop/src browser-extension/src; do
  [ -d "$d" ] && CLIENT_DIRS+=("$d")
done

# Fail closed on a real scan error. grep exits 0 for matches, 1 for "no
# matches" (the clean, expected case), and 2+ for an actual problem (bad
# pattern, unreadable file, etc.) — collapsing all of that into `|| true` would
# let a scan that silently didn't run at all report "OK" instead of failing the
# CI job. `$?` is read immediately after the assignment (not through `!`,
# which would collapse it to a plain 0/1 and destroy the real code).
hits="$(grep -rEn --binary-files=without-match "$PATTERN" "${CLIENT_DIRS[@]}" \
  --include='*.js' --include='*.jsx' --include='*.ts' --include='*.tsx' \
  --exclude-dir=node_modules \
  --exclude-dir=__tests__ \
  --exclude-dir=__mocks__ \
  --exclude-dir=e2e \
  --exclude='*.test.*' \
  --exclude='*.spec.*')"
grep_status=$?
if [ "$grep_status" -gt 1 ]; then
  echo "::error::grep failed while scanning for the ZK v1 contract (exit $grep_status)." >&2
  exit 1
fi

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
