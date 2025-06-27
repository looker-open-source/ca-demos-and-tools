# Copyright 2025 Google LLC
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

#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "Usage: $0 <DEST_PROJECT_ID> <INPUT_DIR>"
  exit 1
fi

DEST_PROJECT="$1"
INPUT_DIR="$2"

# Loop over each .txt file in the input directory
shopt -s nullglob
for filepath in "${INPUT_DIR}"/*.txt; do
  filename=$(basename "${filepath}")
  # Strip the extension to get the secret name
  secret_name="${filename%.*}"
  echo "Importing secret: ${secret_name}"

  # Create the secret if it doesn’t exist
  if ! gcloud secrets describe "${secret_name}" --project="${DEST_PROJECT}" &>/dev/null; then
    echo "  Creating secret ${secret_name} in project ${DEST_PROJECT}"
    gcloud secrets create "${secret_name}" \
      --replication-policy="automatic" \
      --project="${DEST_PROJECT}"
  else
    echo "  Secret ${secret_name} already exists"
  fi

  # Add a new version with the file’s contents
  echo "  Adding new version from ${filepath}"
  gcloud secrets versions add "${secret_name}" \
    --data-file="${filepath}" \
    --project="${DEST_PROJECT}"
done

echo "All .txt secrets imported into project ${DEST_PROJECT}."
