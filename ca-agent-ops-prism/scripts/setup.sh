#!/bin/bash
set -e

# Ensure we are in the project root
cd "$(dirname "$0")/.."

echo "Setting up Prism environment..."

UV_BIN="$HOME/.local/bin/uv"

if [[ ! -f "$UV_BIN" ]]; then
    echo "uv not found at $UV_BIN. Attempting to install..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi

echo "Syncing dependencies with uv..."
$UV_BIN sync

# Parse arguments
SETUP_DB=false
for arg in "$@"; do
    case $arg in
        --db)
            SETUP_DB=true
            shift
            ;;
    esac
done

if [ "$SETUP_DB" = true ]; then
    echo "Starting database setup..."
    ./scripts/setup_postgres.sh
fi

echo "Setup complete!"
if [ "$SETUP_DB" = false ]; then
    echo "To setup the database, run: ./scripts/setup_postgres.sh"
fi