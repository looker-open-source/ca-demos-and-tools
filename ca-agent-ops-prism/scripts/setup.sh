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
pip install -r requirements.txt
pip install -e .

echo "Initializing database..."
python scripts/init_db.py

echo "Setup complete!"
