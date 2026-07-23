#!/usr/bin/env bash
set -eo pipefail

echo "Running database migrations..."
alembic upgrade head || echo "WARNING: database migrations failed — the service will start but tables may be missing"

echo "Starting uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
