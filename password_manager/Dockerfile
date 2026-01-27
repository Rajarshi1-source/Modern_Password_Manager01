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
RUN pip install --no-cache-dir -r ml_dark_web/requirements_ml_darkweb.txt || true

# Install spaCy model (optional)
RUN python -m spacy download en_core_web_sm || true

# Copy project
COPY . /app/

# Create necessary directories
RUN mkdir -p /app/staticfiles /app/media /app/logs

# Collect static files (run during build for optimization)
# RUN python manage.py collectstatic --noinput || true

# Create non-root user
RUN adduser --disabled-password --gecos '' appuser && \
    chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Default command (can be overridden in docker-compose.yml)
CMD ["gunicorn", "password_manager.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "4"]

