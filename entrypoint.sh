#!/bin/bash
set -e

# Only run migrations for the API server, not the Celery worker.
# The API command starts with 'uvicorn', the worker with 'celery'.
if [ "$1" = "uvicorn" ]; then
    echo "Running database migrations..."
    alembic upgrade head
    echo "Migrations complete."
fi

echo "Starting: $@"
exec "$@"
