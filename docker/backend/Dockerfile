# =============================================================================
# Backend Dockerfile - Django Password Manager API
# =============================================================================
# Multi-stage build with Post-Quantum Crypto (liboqs), pqcrypto, and FHE support
# Supports: Django REST API, Celery Workers, Daphne WebSockets, FHE Operations
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: Crypto Builder - Compile liboqs and Python crypto libraries
# -----------------------------------------------------------------------------
FROM python:3.11-slim AS crypto-builder

ENV DEBIAN_FRONTEND=noninteractive

# Install system build tools required for liboqs and crypto libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
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

# Install concrete-python (FHE library) - may fail on some platforms
RUN pip install --no-cache-dir concrete-python==2.5.0 || echo "concrete-python installation optional (Linux x86_64 only)"

# -----------------------------------------------------------------------------
# Stage 2: Dependencies Builder - Install Python dependencies
# -----------------------------------------------------------------------------
FROM python:3.11-slim AS deps-builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RESOLVER_BACKTRACK_LIMIT=200000

# Install build dependencies for Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
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

# Copy requirements and install Python dependencies
WORKDIR /app
COPY password_manager/requirements.txt .

# Install core dependencies.
#
# Notes:
# * We pin pip to a version known to handle large graphs without running
#   into the "resolution-too-deep" error that newer resolvers raise on the
#   unbounded version specifiers in this project's requirements.txt (this
#   is especially painful when the arm64 leg runs under QEMU emulation).
# * `--use-deprecated=legacy-resolver` bypasses the recursive backtracking
#   resolver entirely, matching the behaviour the project was authored
#   against and keeping ARM64 builds from timing out.
# * `--prefer-binary` forces pip to pick a wheel whenever one exists
#   (avoids multi-hour source builds under qemu for scipy, torch, etc.).
# * `--retries` cushions transient PyPI timeouts that appeared repeatedly
#   in the arm64 build logs.
RUN pip install --upgrade "pip==24.3.1" "setuptools>=70,<81" wheel && \
    pip install \
        --use-deprecated=legacy-resolver \
        --prefer-binary \
        --retries 5 \
        -r requirements.txt && \
    pip install \
        --use-deprecated=legacy-resolver \
        --prefer-binary \
        --retries 5 \
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
FROM python:3.11-slim AS production

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

# Install runtime dependencies including crypto runtime libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
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

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/api/health/ || exit 1

# Default entrypoint
ENTRYPOINT ["/entrypoint.sh"]

# Default command (can be overridden)
CMD ["daphne", \
    "-b", "0.0.0.0", \
    "-p", "8000", \
    "--websocket_timeout", "300", \
    "password_manager.asgi:application"]
