#!/bin/bash
set -e

# Run database migrations
echo "Running database migrations..."
alembic upgrade head

# Start the application
echo "Starting TestR API on port ${PORT:-8080}..."
exec gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app \
    --bind 0.0.0.0:${PORT:-8080} \
    --timeout 120 \
    --log-level info
