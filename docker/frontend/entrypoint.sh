#!/bin/sh
# =============================================================================
# Frontend Entrypoint Script
# =============================================================================
# This script handles runtime configuration injection for the frontend
# Allows changing environment variables without rebuilding the image
# =============================================================================

set -e

echo "==================================================================="
echo "Password Manager Frontend - Injecting Runtime Configuration"
echo "==================================================================="

# Define the target file (main JavaScript file after build)
# This will be injected into the HTML at runtime
CONFIG_FILE="/usr/share/nginx/html/config.js"

# Generate runtime configuration
cat > "$CONFIG_FILE" <<EOF
// Runtime Configuration (Generated at container startup)
window.__RUNTIME_CONFIG__ = {
  API_BASE_URL: '${VITE_API_BASE_URL:-http://localhost:8000}',
  WS_URL: '${VITE_WS_URL:-ws://localhost:8001}',
  BLOCKCHAIN_ENABLED: ${VITE_BLOCKCHAIN_ENABLED:-false},
  FHE_ENABLED: ${VITE_FHE_ENABLED:-true},
  APP_ENV: '${VITE_APP_ENV:-production}',
  VERSION: '${VITE_APP_VERSION:-1.0.0}'
};
EOF

echo "[INFO] Runtime configuration generated:"
cat "$CONFIG_FILE"

# Create health check endpoint
cat > /usr/share/nginx/html/health <<EOF
OK
EOF

echo "[INFO] Health check endpoint created"

echo "==================================================================="
echo "[INFO] Configuration injection complete! Starting nginx..."
echo "==================================================================="

# Start nginx
exec "$@"
