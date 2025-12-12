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
RUN git clone --depth 1 --branch main https://github.com/open-quantum-safe/liboqs.git \
    && cd liboqs \
    && mkdir build && cd build \
    && cmake -GNinja .. \
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
ENV LD_LIBRARY_PATH="/usr/local/lib:${LD_LIBRARY_PATH}"
ENV PKG_CONFIG_PATH="/usr/local/lib/pkgconfig:${PKG_CONFIG_PATH}"

# Install liboqs-python wrapper
RUN git clone --depth 1 https://github.com/open-quantum-safe/liboqs-python.git \
    && cd liboqs-python \
    && pip install --no-cache-dir . \
    && cd .. && rm -rf liboqs-python

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
    PIP_DISABLE_PIP_VERSION_CHECK=1

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
    libomp-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create and activate virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements and install Python dependencies
WORKDIR /app
COPY password_manager/requirements.txt .

# Install core dependencies first
RUN pip install --upgrade pip setuptools wheel && \
    pip install -r requirements.txt && \
    pip install gunicorn daphne uvicorn[standard] psycopg2-binary redis django-redis

# Copy crypto packages from crypto-builder
COPY --from=crypto-builder /usr/local/lib/python3.11/site-packages /opt/venv/lib/python3.11/site-packages/

# -----------------------------------------------------------------------------
# Stage 3: Production - Final optimized image
# -----------------------------------------------------------------------------
FROM python:3.11-slim AS production

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    DJANGO_SETTINGS_MODULE=password_manager.settings \
    PATH="/opt/venv/bin:$PATH" \
    LD_LIBRARY_PATH="/usr/local/lib:${LD_LIBRARY_PATH}" \
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

# Copy liboqs libraries from crypto-builder
COPY --from=crypto-builder /usr/local/lib/liboqs* /usr/local/lib/
COPY --from=crypto-builder /usr/local/include/oqs /usr/local/include/oqs

# Update library cache
RUN ldconfig

# Copy virtual environment from deps-builder
COPY --from=deps-builder /opt/venv /opt/venv

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
USER ${APP_USER}

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
CMD ["gunicorn", "password_manager.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "4", \
     "--threads", "2", \
     "--timeout", "120", \
     "--keep-alive", "5", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "--capture-output", \
     "--enable-stdio-inheritance"]
