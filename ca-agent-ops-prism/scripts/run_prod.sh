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

# gunicorn takes the bind address and the timeout on the command line, so both
# are settled here, in the shell, before Python starts. .env.example documents
# PORT and TIMEOUT, so read them from .env the way the other runners do. A
# value already exported still wins.
# shellcheck source=scripts/dotenv.sh
source scripts/dotenv.sh
load_dotenv ".env"

PORT=${PORT:-8080}
TIMEOUT=${TIMEOUT:-3600}

echo "Starting Prism App with Gunicorn (Production Build)..."
echo "Port: $PORT"

uv run gunicorn \
    --bind "0.0.0.0:$PORT" \
    --workers 1 \
    --threads 8 \
    --timeout "$TIMEOUT" \
    "prism.prod:app"
