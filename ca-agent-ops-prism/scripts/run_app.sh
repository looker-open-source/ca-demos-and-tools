#!/bin/bash
set -e

# Ensure we are in the project root
cd "$(dirname "$0")/.."

UV_BIN="$HOME/.local/bin/uv"

if [[ ! -f "$UV_BIN" ]]; then
    # Fallback to 'uv' in PATH
    if command -v uv &> /dev/null; then
        UV_BIN="uv"
    else
        echo "Error: uv not found. Please run ./scripts/setup.sh first."
        exit 1
    fi
fi

echo "Starting Prism UI in debug mode..."
echo "This should not be used for production."
$UV_BIN run python src/prism/ui/app.py
