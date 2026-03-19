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

# This script helps register a Looker OAuth Client Application.
# It uses the Looker API 4.0.

# Usage: ./register-oauth.sh <looker_base_url> <admin_api_token> [client_guid]

BASE_URL=$1
ADMIN_TOKEN=$2
CLIENT_GUID=${3:-ca-looker-sdk-demo}

if [ -z "$BASE_URL" ] || [ -z "$ADMIN_TOKEN" ]; then
  echo "Usage: $0 <looker_base_url> <admin_api_token> [client_guid]"
  echo "Example: $0 https://your-instance.looker.com YOUR_ADMIN_TOKEN"
  exit 1
fi

# Remove trailing slash from base URL
BASE_URL=${BASE_URL%/}

echo "Registering OAuth client: $CLIENT_GUID on $BASE_URL"

curl -X POST "$BASE_URL/api/4.0/oauth_client_apps"      -H "Authorization: token $ADMIN_TOKEN"      -H "Content-Type: application/json"      -d "{
       \"client_guid\": \"$CLIENT_GUID\",
       \"redirect_uri\": \"http://localhost:3000/oauth/callback\",
       \"display_name\": \"CA in Looker SDK Demo\",
       \"enabled\": true
     }"

echo -e "\n\nIMPORTANT: You must also add http://localhost:3000 to the 'Embedded Domain Allowlist' in Looker Admin > Platform > Embed."
