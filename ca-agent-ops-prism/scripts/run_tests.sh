#!/bin/bash
set -e

# Ensure we are in the project root
# Note: This method handles relative paths correctly on both OSs
cd "$(dirname "$0")/.."

# Check if venv is active
if [[ -z "$VIRTUAL_ENV" ]]; then
    # Try to activate standard location
    if [[ -f "$HOME/prism_venv/bin/activate" ]]; then
        source "$HOME/prism_venv/bin/activate"
    else
        echo "Error: Virtual environment is not active and not found at ~/prism_venv."
        echo "Please run: source ~/prism_venv/bin/activate"
        exit 1
    fi
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

# Inject the dynamic PG_HOST into the connection string
export TEST_DATABASE_URL="postgresql:///prism_test?host=${PG_HOST}"
export DATABASE_URL="$TEST_DATABASE_URL"

python3 -m pytest "$@"