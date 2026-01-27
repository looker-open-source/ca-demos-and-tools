#!/bin/bash
set -e

# Ensure we are in the project root
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

echo "Running tests against PostgreSQL..."
export PYTHONPATH=$PYTHONPATH:$(pwd)/src

# Tests strictly use the prism_test database
export TEST_DATABASE_URL="postgresql:///prism_test?host=/var/run/postgresql"
export DATABASE_URL="$TEST_DATABASE_URL"

python3 -m pytest "$@"
