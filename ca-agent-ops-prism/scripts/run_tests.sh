#!/bin/bash
set -e

# Ensure we are in the project root
cd "$(dirname "$0")/.."

UV_BIN="$HOME/.local/bin/uv"

if [[ ! -f "$UV_BIN" ]]; then
    echo "Error: uv not found at $UV_BIN. Please run ./scripts/setup.sh first."
    exit 1
fi

# --- OS Detection Logic ---
# Detect the operating system to determine the Postgres socket path
SYSTEM_NAME="$(uname -s)"

if [[ "$SYSTEM_NAME" == "Darwin" ]]; then
    # macOS: Standard Homebrew PostgreSQL socket location
    PG_HOST="/tmp"
    echo "Detected macOS. Setting Postgres host to $PG_HOST"
elif [[ "$SYSTEM_NAME" == "Linux" ]]; then
    # Linux: Check common socket locations
    if [[ -d "/var/run/postgresql" ]]; then
        PG_HOST="/var/run/postgresql"
    else
        # Fallback for some distros (like Arch) that use /run or /tmp
        PG_HOST="/tmp"
    fi
    echo "Detected Linux. Setting Postgres host to $PG_HOST"
else
    # Fallback for unknown systems
    PG_HOST="/tmp"
    echo "Unknown OS. Defaulting Postgres host to $PG_HOST"
fi
# ---------------------------

echo "Running tests against PostgreSQL..."
export PYTHONPATH=$PYTHONPATH:$(pwd)/src

# Tests strictly use the prism_test database
export TEST_DATABASE_URL="postgresql:///prism_test?host=$PG_HOST"
export DATABASE_URL="$TEST_DATABASE_URL"

$UV_BIN run pytest "$@"