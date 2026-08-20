#!/bin/bash
set -e

echo "Running database migrations via Alembic..."
python -m alembic upgrade head || echo "Alembic migration warning: Database connection unavailable or already up-to-date."

echo "Starting VisionGPT FastAPI backend application..."
exec "$@"
