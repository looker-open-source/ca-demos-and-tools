#!/bin/bash
set -e

# Ensure we are in the project root
cd "$(dirname "$0")/.."

echo "Starting Prism UI in debug mode..."
echo "This should not be used for production."
uv run python src/prism/ui/app.py
