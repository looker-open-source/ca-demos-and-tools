#!/bin/bash

# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Fail on any error.
set -e

# Display commands being run.
set -x

# --- Configuration ---
# Source the environment variables from the .env file.
if [ -f .env ]; then
  export $(cat .env | sed 's/#.*//g' | xargs)
fi

# --- Action ---
# Specify the action: 'create' or 'delete'
ACTION="create" # or "delete"

# --- Build and Deploy ---

# 1. Ensure uv is installed
if ! command -v uv &> /dev/null
then
    echo "uv could not be found. Please install it first."
    exit 1
fi

# 2. Build the wheel file
uv build --format=wheel --output-dir=deployment

# 3. Run the deployment script
python3 deployment/deploy.py \
  --project_id="${GOOGLE_CLOUD_PROJECT}" \
  --location="${GOOGLE_CLOUD_LOCATION}" \
  --bucket="${GOOGLE_CLOUD_STORAGE_BUCKET}" \
  --resource_id="${RESOURCE_ID}" \
  --${ACTION}