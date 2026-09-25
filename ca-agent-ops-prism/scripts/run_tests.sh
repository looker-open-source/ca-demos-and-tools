#!/bin/bash
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

set -e

cd "$(dirname "$0")/.."

# shellcheck source=scripts/dotenv.sh
source scripts/dotenv.sh

DOTENV_FILE=".env"
if [[ -f "$DOTENV_FILE" ]]; then
    echo "Loading environment from $DOTENV_FILE..."
    load_dotenv "$DOTENV_FILE"
fi

if [[ -z "$TEST_DATABASE_URL" ]]; then
    echo "Error: TEST_DATABASE_URL is not set."
    echo "Please run ./scripts/setup_postgres.sh first to generate your .env file."
    exit 1
fi

echo "Running tests against PostgreSQL..."
# The :+ keeps the separator off an unset PYTHONPATH. A leading empty entry
# would put the working directory on sys.path, where a stray prism.py or
# tests.py in the project root shadows the real package.
export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}$(pwd)/src"
export DATABASE_URL="$TEST_DATABASE_URL"

uv run pytest "$@"
