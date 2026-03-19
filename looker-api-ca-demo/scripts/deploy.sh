#!/bin/bash

# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


# scripts/deploy.sh
# Automates deploying to Cloud Run with environment variables from .env

# Ensure script is run from the project root
if [ ! -f "package.json" ]; then
  echo "Error: Please run this script from the project root (e.g., ./scripts/deploy.sh)."
  exit 1
fi

SERVICE_NAME="looker-ca-reference-demo"
REGION="us-central1"
ENV_FILE=".env"
TEMP_YAML="env_vars.yaml"

if [ ! -f "$ENV_FILE" ]; then
  echo "Error: $ENV_FILE not found."
  exit 1
fi

echo "Reading environment variables from $ENV_FILE..."

# Convert .env to YAML using embedded Python script for robustness
python3 -c "
import sys

def convert_env_to_yaml(env_file, yaml_file):
    try:
        env_vars = {}
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip()
        
        with open(yaml_file, 'w') as f:
            for key, value in env_vars.items():
                # manual yaml formatting to avoid dependency on pyyaml
                # safe for standard string values
                safe_value = value.replace('\"', '\\\"')
                f.write(f'{key}: \"{safe_value}\"\n')
                
    except Exception as e:
        print(f'Error converting .env to YAML: {e}')
        sys.exit(1)

convert_env_to_yaml('$ENV_FILE', '$TEMP_YAML')
"

if [ $? -ne 0 ]; then
    echo "Failed to process environment variables."
    exit 1
fi

if [ ! -f "$TEMP_YAML" ]; then
    echo "Failed to generate configuration file."
    exit 1
fi

echo "Deploying to Cloud Run with configuration from $ENV_FILE..."

gcloud run deploy "$SERVICE_NAME" \
  --source . \
  --region "$REGION" \
  --no-allow-unauthenticated \
  --ingress all \
  --env-vars-file "$TEMP_YAML"

# Clean up
rm "$TEMP_YAML"

echo "Deployment complete!"