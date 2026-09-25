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

# app.py reads PRISM_HOST, PORT and PRISM_DEBUG straight from the environment,
# and python-dotenv hands it .env on import. Load the same file here, so the
# line below prints the address the server really comes up on.
# shellcheck source=scripts/dotenv.sh
source scripts/dotenv.sh
load_dotenv ".env"

# Debug is off by default and the bind address is loopback, so the old message
# named neither the mode nor the address it actually came up on. These are the
# defaults app.py applies to the same three variables.
echo "Starting Prism UI on ${PRISM_HOST:-127.0.0.1}:${PORT:-8080}, debug=${PRISM_DEBUG:-false}."
echo "Development server. Deployments run prism.prod:app under gunicorn."
uv run python src/prism/ui/app.py
