#!/bin/bash
set -e

# Ensure we are in the project root
cd "$(dirname "$0")/.."

# Default values for production
PORT=${PORT:-8080}
TIMEOUT=${TIMEOUT:-3600}

echo "Starting Prism App with Gunicorn (Production Build)..."
echo "Port: $PORT"

uv run gunicorn \
    --bind 0.0.0.0:$PORT \
    --workers 1 \
    --threads 8 \
    --timeout $TIMEOUT \
    "prism.prod:app"
