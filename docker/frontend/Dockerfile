# =============================================================================
# Frontend Dockerfile - React Password Manager UI
# =============================================================================
# Multi-stage build for optimized production image
# Supports: React 18, Vite, TensorFlow.js, Quantum Crypto (Kyber), FHE (TFHE-rs WASM)
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: Dependencies - Install npm packages
# -----------------------------------------------------------------------------
# Pinned to $BUILDPLATFORM so npm/Node always runs natively on the runner.
# This avoids QEMU "Illegal instruction" (exit 132) crashes when emulating
# Node 22 on linux/arm64 from an amd64 runner. The frontend build output is
# static assets, so it is architecture-independent — only the final nginx
# stage needs to be multi-arch.
FROM --platform=$BUILDPLATFORM node:22-alpine AS deps

# Set working directory
WORKDIR /app

# Copy package files
COPY frontend/package*.json ./

# Install ALL dependencies including dev dependencies for build stage
# (wasm plugins are in devDependencies)
RUN npm ci && \
    npm cache clean --force

# -----------------------------------------------------------------------------
# Stage 2: Builder - Build the application
# -----------------------------------------------------------------------------
FROM --platform=$BUILDPLATFORM node:22-alpine AS builder

# Set working directory
WORKDIR /app

# Copy dependencies from deps stage
COPY --from=deps /app/node_modules ./node_modules

# Copy source code
COPY frontend/ .

# Set build-time environment variables
ARG VITE_API_BASE_URL
ARG VITE_WS_URL
ARG VITE_BLOCKCHAIN_ENABLED=false
ARG VITE_CONTRACT_ADDRESS
ARG VITE_FHE_ENABLED=true

# Other public settings the code reads. .dockerignore keeps frontend/.env* out
# of the context, so pass these with --build-arg. Vite compiles them into the
# public bundle, so never pass a secret here. No ENV: an ARG that is not passed
# stays unset, and these exist only in this stage, not in the final image.
ARG VITE_API_URL
ARG VITE_API_TIMEOUT
ARG VITE_FIREBASE_API_KEY
ARG VITE_FIREBASE_APP_ID
ARG VITE_FIREBASE_AUTH_DOMAIN
ARG VITE_FIREBASE_DATABASE_URL
ARG VITE_FIREBASE_MESSAGING_SENDER_ID
ARG VITE_FIREBASE_PROJECT_ID
ARG VITE_FIREBASE_STORAGE_BUCKET
ARG VITE_SENTRY_DSN
ARG VITE_SENTRY_RELEASE
ARG VITE_SENTRY_TRACES_SAMPLE_RATE

ENV VITE_API_BASE_URL=${VITE_API_BASE_URL} \
    VITE_WS_URL=${VITE_WS_URL} \
    VITE_BLOCKCHAIN_ENABLED=${VITE_BLOCKCHAIN_ENABLED} \
    VITE_CONTRACT_ADDRESS=${VITE_CONTRACT_ADDRESS} \
    VITE_FHE_ENABLED=${VITE_FHE_ENABLED} \
    # Increase Node.js memory for WASM compilation
    NODE_OPTIONS="--max-old-space-size=4096"

# Build the application with WASM support
RUN npm run build

# -----------------------------------------------------------------------------
# Stage 3: Production - Nginx serving static files
# -----------------------------------------------------------------------------
FROM nginx:1.31.7-alpine AS production

# Refresh indexes and upgrade OS packages (libssl3, libxml2, etc.) then curl for health checks
RUN apk update && apk upgrade --no-cache && apk add --no-cache curl

# Create non-root user
RUN addgroup -g 1000 -S nginx-app && \
    adduser -u 1000 -S nginx-app -G nginx-app

# Remove default nginx config
RUN rm -rf /etc/nginx/conf.d/default.conf /usr/share/nginx/html/*

# Copy custom nginx configuration (+ shared security-headers snippet it includes)
COPY docker/frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY docker/frontend/security-headers.conf /etc/nginx/security-headers.conf

# Copy built files from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Set correct permissions
RUN chown -R nginx-app:nginx-app /usr/share/nginx/html && \
    chown -R nginx-app:nginx-app /var/cache/nginx && \
    chown -R nginx-app:nginx-app /var/log/nginx && \
    touch /var/run/nginx.pid && \
    chown -R nginx-app:nginx-app /var/run/nginx.pid

# Copy entrypoint script for runtime config
COPY docker/frontend/entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Expose port (nginx listens on 8080 because the non-root nginx-app user
# cannot bind to privileged ports < 1024).
EXPOSE 8080

# Switch to non-root user
USER nginx-app

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Use custom entrypoint
ENTRYPOINT ["/docker-entrypoint.sh"]

# Start nginx
CMD ["nginx", "-g", "daemon off;"]

