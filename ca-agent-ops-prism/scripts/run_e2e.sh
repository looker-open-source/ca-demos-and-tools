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

#
# Runs the browser end-to-end suite.
#
# The E2E suite needs its own database, because the unit suite drops every
# table between tests and this suite keeps a server running. So: derive an E2E
# URL from TEST_DATABASE_URL, create the database if needed, and point
# DATABASE_URL at it so gunicorn and the trial workers it spawns agree.
#
# Usage:
#   ./scripts/run_e2e.sh                  # replay recorded agent responses
#   ./scripts/run_e2e.sh --record         # call the real APIs and record them
#   ./scripts/run_e2e.sh -k navigation    # any extra args go to pytest
set -e

cd "$(dirname "$0")/.."

# shellcheck source=scripts/dotenv.sh
source scripts/dotenv.sh

DOTENV_FILE=".env"
if [[ -f "$DOTENV_FILE" ]]; then
    echo "Loading environment from $DOTENV_FILE..."
    load_dotenv "$DOTENV_FILE"
fi

BACKEND="${PRISM_AGENT_BACKEND:-replay}"
PYTEST_ARGS=()
for arg in "$@"; do
    case "$arg" in
        --record) BACKEND="record" ;;
        --live)   BACKEND="live" ;;
        *)        PYTEST_ARGS+=("$arg") ;;
    esac
done

if [[ "$BACKEND" != "replay" ]]; then
    echo "WARNING: PRISM_AGENT_BACKEND=$BACKEND - this run will call the real"
    echo "         Gemini Data Analytics and Gen AI APIs and cost money."
fi

if [[ -z "$E2E_DATABASE_URL" ]]; then
    if [[ -z "$TEST_DATABASE_URL" ]]; then
        echo "Error: neither E2E_DATABASE_URL nor TEST_DATABASE_URL is set."
        echo "Run ./scripts/setup_postgres.sh first to generate your .env file."
        exit 1
    fi
    E2E_DATABASE_URL=$(uv run python - "$TEST_DATABASE_URL" <<'PY'
import sys
import sqlalchemy

url = sqlalchemy.engine.make_url(sys.argv[1])
name = (url.database or "prism").removesuffix("_test")
print(url.set(database=f"{name}_e2e").render_as_string(hide_password=False))
PY
)
fi

# Create the database if it isn't there yet. Alembic builds the schema, so
# this only has to create the empty database.
uv run python - "$E2E_DATABASE_URL" <<'PY'
import sys
import sqlalchemy

url = sqlalchemy.engine.make_url(sys.argv[1])
target = url.database
admin = sqlalchemy.create_engine(
    url.set(database="postgres"), isolation_level="AUTOCOMMIT"
)
with admin.connect() as connection:
    exists = connection.execute(
        sqlalchemy.text("SELECT 1 FROM pg_database WHERE datname = :name"),
        {"name": target},
    ).scalar()
    if not exists:
        print(f"  > Creating database {target!r}...")
        # CREATE DATABASE takes an identifier, which cannot be bound as a
        # parameter, and the name comes from TEST_DATABASE_URL. Let the
        # dialect quote it rather than wrapping it in quotes by hand.
        quoted = admin.dialect.identifier_preparer.quote(target)
        connection.execute(sqlalchemy.text(f"CREATE DATABASE {quoted}"))
    else:
        print(f"  > Database {target!r} already exists.")
admin.dispose()
PY

# The :+ keeps the separator off an unset PYTHONPATH. A leading empty entry
# would put the working directory on sys.path, where a stray prism.py or
# tests.py in the project root shadows the real package.
export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}$(pwd)/src"
# Same value for both, so tests/db_guard.py, gunicorn, and the trial
# subprocesses it spawns can't disagree.
export DATABASE_URL="$E2E_DATABASE_URL"
export TEST_DATABASE_URL="$E2E_DATABASE_URL"
export PRISM_AGENT_BACKEND="$BACKEND"
# PRISM_CASSETTE_DIR is left to tests/e2e/conftest.py. It points at
# tests/e2e/cassettes when recording and at a /tmp copy of them when replaying.

# Default to the whole directory, but step aside if a path was passed. pytest
# unions its positional arguments, so appending tests/e2e to an explicit file
# would run everything instead of the one spec asked for.
TARGETS=("tests/e2e")
for arg in "${PYTEST_ARGS[@]}"; do
    if [[ -e "${arg%%::*}" ]]; then
        TARGETS=()
        break
    fi
done

# playwright, pytest-playwright and pytest-timeout live in pyproject.toml's e2e
# dependency group. dev is uv's default group, so only this script pays for
# them; ./scripts/run_tests.sh installs none of it.
E2E_PACKAGES=(--group e2e)

# The playwright CLI only exists once the group is installed. This is a no-op
# after the matching build lands in ~/.cache/ms-playwright.
uv run "${E2E_PACKAGES[@]}" playwright install chromium

# --timeout is passed here rather than through pyproject.toml addopts, because
# pytest-timeout is not installed outside the e2e group and plain pytest would
# fail on an unrecognized argument. The tier needs one: both the worker pool
# and the browser can wait forever.
#
# `-m e2e` overrides the `-m 'not e2e and not live'` in pyproject.toml addopts.
uv run "${E2E_PACKAGES[@]}" \
    pytest -m e2e --timeout=300 "${TARGETS[@]}" "${PYTEST_ARGS[@]}"
