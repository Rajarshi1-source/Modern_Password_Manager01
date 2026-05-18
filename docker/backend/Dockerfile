# =============================================================================
# Backend Dockerfile - Django Password Manager API
# =============================================================================
# Multi-stage build with Post-Quantum Crypto (liboqs), pqcrypto, and FHE support
# Supports: Django REST API, Celery Workers, Daphne WebSockets, FHE Operations
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: Crypto Builder - Compile liboqs and Python crypto libraries
# -----------------------------------------------------------------------------
FROM python:3.11-slim-bookworm AS crypto-builder

ENV DEBIAN_FRONTEND=noninteractive

# Install system build tools required for liboqs and crypto libraries.
# `apt-get -y upgrade` pulls patched curl + util-linux to address Trivy
# CVEs #1393, #1396, #1399-#1403; without it the image inherits whatever
# was frozen into the python:3.11-slim-bookworm base.
RUN apt-get update && apt-get -y upgrade && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    ninja-build \
    git \
    curl \
    pkg-config \
    openssl \
    libssl-dev \
    libgmp-dev \
    python3-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Build and install liboqs (Open Quantum Safe library)
WORKDIR /tmp
RUN git clone --depth 1 --branch 0.11.0 https://github.com/open-quantum-safe/liboqs.git && \
    mkdir -p liboqs/build
WORKDIR /tmp/liboqs/build
RUN cmake -GNinja .. \
    -DCMAKE_BUILD_TYPE=Release \
    -DBUILD_SHARED_LIBS=ON \
    -DOQS_USE_OPENSSL=ON \
    -DOQS_ENABLE_KEM_KYBER=ON \
    -DOQS_ENABLE_KEM_SABER=ON \
    -DOQS_ENABLE_KEM_NTRU=ON \
    -DOQS_ENABLE_SIG_DILITHIUM=ON \
    && ninja \
    && ninja install

# Set library path for liboqs
ENV LD_LIBRARY_PATH="/usr/local/lib"
ENV PKG_CONFIG_PATH="/usr/local/lib/pkgconfig"

# Install liboqs-python wrapper
# Install liboqs-python wrapper
WORKDIR /tmp
RUN git clone --depth 1 https://github.com/open-quantum-safe/liboqs-python.git
WORKDIR /tmp/liboqs-python
RUN pip install --no-cache-dir .
WORKDIR /tmp
RUN rm -rf liboqs-python

# Install pqcrypto (pure Python post-quantum crypto)
RUN pip install --no-cache-dir pqcrypto || echo "pqcrypto installation optional"

# Install concrete-python (FHE library) - may fail on some platforms.
# This is the single authoritative install point for concrete-python; do NOT
# duplicate it in the deps-builder stage to avoid pulling the same multi-GB
# package twice (which previously caused "No space left on device" on GHA
# runners).
RUN pip install --no-cache-dir concrete-python==2.5.0 || echo "concrete-python installation optional (Linux x86_64 only)"

# -----------------------------------------------------------------------------
# Stage 2: Dependencies Builder - Install Python dependencies
# -----------------------------------------------------------------------------
FROM python:3.11-slim-bookworm AS deps-builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RESOLVER_BACKTRACK_LIMIT=200000

# Install build dependencies for Python packages. `apt-get -y upgrade`
# patches curl / util-linux in the builder layer (Trivy #1393, #1396,
# #1399-#1403) so any tooling that links against them has the fixed
# versions.
RUN apt-get update && apt-get -y upgrade && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    cmake \
    clang \
    libpq-dev \
    libffi-dev \
    libssl-dev \
    libgmp-dev \
    libmpfr-dev \
    libomp-dev \
    gfortran \
    libopenblas-dev \
    liblapack-dev \
    libjpeg-dev \
    zlib1g-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create and activate virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements (split into layers) and install Python dependencies.
#
# Notes on the staged install:
# * Layer 1 (core) is the Django/web stack and is REQUIRED for the image to
#   boot. Failure here aborts the build.
# * Layer 2 (ml) is large (multi-GB) and OPTIONAL on space-constrained
#   runners. If installation fails (typically due to disk exhaustion on
#   GHA hosted runners) the build continues — the app has fallback paths.
# * Layer 3 (servers) is small and ensures gunicorn/daphne/uvicorn are
#   present even if the ml layer was skipped.
#
# General pip flags:
# * pip is pinned to a version known to handle large dependency graphs
#   without "resolution-too-deep" errors against unbounded specifiers.
# * `--prefer-binary` forces pip to pick a wheel whenever one exists
#   (avoids multi-hour source builds under qemu for scipy, torch, etc.).
# * `--retries` cushions transient PyPI timeouts.
WORKDIR /app
COPY password_manager/requirements-core.txt .
COPY password_manager/requirements-ml.txt .

RUN pip install --upgrade "pip==24.3.1" "setuptools>=70,<81" wheel && \
    pip install --prefer-binary --retries 5 -r requirements-core.txt

RUN pip install --prefer-binary --retries 5 -r requirements-ml.txt || \
    echo "ML deps skipped (insufficient disk space or unsupported platform)"

RUN pip install --prefer-binary --retries 5 \
    gunicorn daphne "uvicorn[standard]" redis django-redis

# Copy OQS Python package from crypto-builder using a version-agnostic glob via shell
RUN mkdir -p /tmp/oqs-staging
COPY --from=crypto-builder /usr/local/lib/python3.11/site-packages/oqs /tmp/oqs-staging/oqs
RUN PY_SITELIB=$(python -c "import sysconfig; print(sysconfig.get_path('purelib'))") && \
    cp -r /tmp/oqs-staging/oqs "$PY_SITELIB/oqs" && \
    rm -rf /tmp/oqs-staging

# -----------------------------------------------------------------------------
# Stage 3: Production - Final optimized image
# -----------------------------------------------------------------------------
FROM python:3.11-slim-bookworm AS production

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    DJANGO_SETTINGS_MODULE=password_manager.settings \
    PATH="/opt/venv/bin:$PATH" \
    LD_LIBRARY_PATH="/usr/local/lib" \
    # Application settings
    APP_HOME=/app \
    APP_USER=appuser \
    APP_GROUP=appgroup

# Install runtime dependencies including crypto runtime libraries.
# `curl` is intentionally NOT installed in the runtime stage — the
# HEALTHCHECK below uses python's stdlib urllib instead. Dropping curl
# closes Trivy CVEs #1399-#1403 (curl/libcurl) at the layer level
# rather than only patching them. `apt-get -y upgrade` patches the
# remaining transitive packages (util-linux: Trivy #1393, #1396).
RUN apt-get update && apt-get -y upgrade && apt-get install -y --no-install-recommends \
    libpq5 \
    netcat-openbsd \
    libgmp10 \
    libmpfr6 \
    libomp5 \
    libssl3 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user for security
RUN groupadd --gid 1000 ${APP_GROUP} && \
    useradd --uid 1000 --gid ${APP_GROUP} --shell /bin/bash --create-home ${APP_USER}

# Copy liboqs shared libraries and headers from crypto-builder
COPY --from=crypto-builder /usr/local/lib/liboqs.so* /usr/local/lib/
COPY --from=crypto-builder /usr/local/include/oqs /usr/local/include/oqs

# Copy virtual environment from deps-builder
COPY --from=deps-builder /opt/venv /opt/venv

# Update library cache after all native libs and venv are in place
RUN ldconfig

# Set working directory
WORKDIR ${APP_HOME}

# Copy application code
COPY --chown=${APP_USER}:${APP_GROUP} password_manager/ .

# Create necessary directories
RUN mkdir -p \
    ${APP_HOME}/staticfiles \
    ${APP_HOME}/media \
    ${APP_HOME}/logs \
    ${APP_HOME}/geoip \
    && chown -R ${APP_USER}:${APP_GROUP} ${APP_HOME}

# Copy entrypoint script
COPY --chown=${APP_USER}:${APP_GROUP} docker/backend/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Switch to non-root user
USER 1000:1000

# Expose ports
# 8000 - Gunicorn (REST API)
# 8001 - Daphne (WebSockets)
EXPOSE 8000 8001

# Health check — uses python stdlib urllib instead of curl so the
# runtime image doesn't need to ship curl (see Trivy CVEs #1399-#1403).
# urllib.request.urlopen raises on non-2xx responses, which gives the
# right non-zero exit code for the orchestrator to mark the container
# unhealthy.
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request, sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/api/health/', timeout=8).status == 200 else 1)" || exit 1

# Default entrypoint
ENTRYPOINT ["/entrypoint.sh"]

# Default command (can be overridden)
CMD ["daphne", \
    "-b", "0.0.0.0", \
    "-p", "8000", \
    "--websocket_timeout", "300", \
    "password_manager.asgi:application"]
