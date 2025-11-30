# =============================================================================
# Backend Dockerfile - Django Password Manager API
# =============================================================================
# Multi-stage build for optimized production image
# Supports: Django REST API, Celery Workers, Daphne WebSockets, FHE Operations
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: Builder - Install dependencies
# -----------------------------------------------------------------------------
FROM python:3.13-slim AS builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install build dependencies including FHE library requirements
# - cmake: Required for building FHE libraries (concrete-python, tenseal)
# - clang: LLVM compiler for FHE circuit compilation
# - libgmp-dev: GNU Multiple Precision library for large number operations
# - libmpfr-dev: Multiple precision floating-point library
# - libomp-dev: OpenMP for parallel FHE operations
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

# Install Python dependencies
WORKDIR /app
COPY password_manager/requirements.txt .

# Install core dependencies first, then FHE libraries with extended timeout
RUN pip install --upgrade pip setuptools wheel && \
    pip install -r requirements.txt && \
    pip install gunicorn daphne uvicorn[standard] psycopg2-binary redis django-redis

# -----------------------------------------------------------------------------
# Stage 2: Production - Final optimized image
# -----------------------------------------------------------------------------
FROM python:3.13-slim AS production

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    DJANGO_SETTINGS_MODULE=password_manager.settings \
    PATH="/opt/venv/bin:$PATH" \
    # Application settings
    APP_HOME=/app \
    APP_USER=appuser \
    APP_GROUP=appgroup

# Install runtime dependencies including FHE runtime libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    netcat-openbsd \
    libgmp10 \
    libmpfr6 \
    libomp5 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user for security
RUN groupadd --gid 1000 ${APP_GROUP} && \
    useradd --uid 1000 --gid ${APP_GROUP} --shell /bin/bash --create-home ${APP_USER}

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

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

