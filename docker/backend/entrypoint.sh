#!/bin/bash
# =============================================================================
# Backend Entrypoint Script
# =============================================================================
# This script handles initialization tasks before starting the Django application
# - Database connection waiting
# - Migrations
# - Static file collection
# - Cache warming
# =============================================================================

set -e  # Exit on error

echo "==================================================================="
echo "Password Manager Backend - Starting Initialization"
echo "==================================================================="

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored messages
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# =============================================================================
# STEP 1: Wait for PostgreSQL
# =============================================================================
print_info "Waiting for PostgreSQL to be ready..."

if [ -n "$DATABASE_HOST" ]; then
    host="$DATABASE_HOST"
    port="${DATABASE_PORT:-5432}"
    
    print_info "Checking connection to $host:$port"
    
    # Wait for PostgreSQL to be ready
    max_attempts=30
    attempt=0
    
    while ! nc -z "$host" "$port" 2>/dev/null; do
        attempt=$((attempt + 1))
        if [ $attempt -ge $max_attempts ]; then
            print_error "PostgreSQL is not available after $max_attempts attempts"
            exit 1
        fi
        print_warn "PostgreSQL is unavailable - attempt $attempt/$max_attempts - sleeping"
        sleep 2
    done
    
    print_info "PostgreSQL is ready!"
else
    print_warn "DATABASE_HOST not set, skipping database wait"
fi

# =============================================================================
# STEP 2: Wait for Redis
# =============================================================================
print_info "Waiting for Redis to be ready..."

if [ -n "$REDIS_HOST" ]; then
    host="$REDIS_HOST"
    port="${REDIS_PORT:-6379}"
    
    print_info "Checking connection to $host:$port"
    
    max_attempts=30
    attempt=0
    
    while ! nc -z "$host" "$port" 2>/dev/null; do
        attempt=$((attempt + 1))
        if [ $attempt -ge $max_attempts ]; then
            print_error "Redis is not available after $max_attempts attempts"
            exit 1
        fi
        print_warn "Redis is unavailable - attempt $attempt/$max_attempts - sleeping"
        sleep 2
    done
    
    print_info "Redis is ready!"
else
    print_warn "REDIS_HOST not set, skipping Redis wait"
fi

# =============================================================================
# STEP 3: Run Database Migrations
# =============================================================================
if [ "${RUN_MIGRATIONS:-false}" = "true" ]; then
    print_info "Running database migrations..."
    python manage.py migrate --noinput
    print_info "Migrations completed!"
else
    print_warn "Skipping migrations (RUN_MIGRATIONS not set)"
fi

# =============================================================================
# STEP 4: Collect Static Files
# =============================================================================
if [ "${COLLECT_STATIC:-false}" = "true" ]; then
    print_info "Collecting static files..."
    python manage.py collectstatic --noinput --clear
    print_info "Static files collected!"
else
    print_warn "Skipping static file collection (COLLECT_STATIC not set)"
fi

# =============================================================================
# STEP 5: Create Superuser (if needed)
# =============================================================================
if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ] && [ -n "$DJANGO_SUPERUSER_EMAIL" ]; then
    print_info "Creating superuser if it doesn't exist..."
    python manage.py shell <<EOF
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='$DJANGO_SUPERUSER_USERNAME').exists():
    User.objects.create_superuser('$DJANGO_SUPERUSER_USERNAME', '$DJANGO_SUPERUSER_EMAIL', '$DJANGO_SUPERUSER_PASSWORD')
    print('Superuser created successfully')
else:
    print('Superuser already exists')
EOF
    print_info "Superuser check completed!"
fi

# =============================================================================
# STEP 6: Create Required Directories
# =============================================================================
print_info "Creating required directories..."
mkdir -p /app/logs /app/media /app/staticfiles
print_info "Directories created!"

# =============================================================================
# STEP 7: Run System Checks
# =============================================================================
print_info "Running Django system checks..."
python manage.py check --deploy 2>&1 | grep -v "WARNING" || true
print_info "System checks completed!"

# =============================================================================
# STEP 8: Execute Command
# =============================================================================
echo "==================================================================="
print_info "Initialization complete! Starting application..."
echo "==================================================================="

# Execute the main command (e.g., gunicorn, daphne, celery)
exec "$@"
