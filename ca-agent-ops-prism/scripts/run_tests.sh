#!/bin/bash
set -e

# Ensure we are in the project root
cd "$(dirname "$0")/.."

# --- Load Environment Variables ---
DOTENV_FILE=".env"
if [[ -f "$DOTENV_FILE" ]]; then
    echo "Loading environment from $DOTENV_FILE..."
    # Export variables from .env, ignoring comments and empty lines
    export $(grep -v '^#' "$DOTENV_FILE" | xargs)
fi

if [[ -z "$TEST_DATABASE_URL" ]]; then
    echo "Error: TEST_DATABASE_URL is not set."
    echo "Please run ./scripts/setup_postgres.sh first to generate your .env file."
    exit 1
fi
# ---------------------------

echo "Running tests against PostgreSQL..."
export PYTHONPATH=$PYTHONPATH:$(pwd)/src
export DATABASE_URL="$TEST_DATABASE_URL"

uv run pytest "$@"