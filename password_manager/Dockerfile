FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    gcc \
    python3-dev \
    musl-dev \
    libpq-dev \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Install ML dependencies (optional, comment out if not using ML features)
COPY ml_dark_web/requirements_ml_darkweb.txt /app/ml_dark_web/
RUN pip install --no-cache-dir -r ml_dark_web/requirements_ml_darkweb.txt \
    || echo "WARNING: ML dependencies not installed, ML features disabled"

# Install spaCy model (optional)
RUN python -m spacy download en_core_web_sm --no-deps || true

# Copy project
COPY . /app/

# Create necessary directories
RUN mkdir -p /app/staticfiles /app/media /app/logs

# Collect static files (run during build for optimization)
# RUN python manage.py collectstatic --noinput || true

# Create non-root user
RUN addgroup --gid 1000 appgroup && \
    adduser --uid 1000 --gid 1000 --disabled-password --gecos '' appuser && \
    chown -R 1000:1000 /app
USER 1000:1000

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/api/health/ || exit 1

# Set Docker environment flags
ENV DOCKER_CONTAINER=true
ENV RUN_MAIN=true

# Default command (can be overridden in docker-compose.yml)
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "password_manager.asgi:application"]

