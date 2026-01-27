#!/bin/bash
set -e

# Ensure we are in the project root
cd "$(dirname "$0")/.."

echo "Setting up Prism environment..."

VENV_PATH="$HOME/prism_venv"

if [[ ! -d "$VENV_PATH" ]]; then
    echo "Creating virtual environment at $VENV_PATH..."
    python3 -m venv "$VENV_PATH"
fi

echo "Activating virtual environment..."
source "$VENV_PATH/bin/activate"

echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
pip install -e .

if [[ "$1" == "--db" ]]; then
    echo "Database setup requested..."
    ./scripts/setup_postgres.sh
fi

echo "Setup complete!"
