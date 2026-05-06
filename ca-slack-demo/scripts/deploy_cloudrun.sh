#!/usr/bin/env bash
# Deploy ca-demo to Cloud Run.
#
# Reads all values from .env — no hardcoded secrets.
# Run from the repo root:
#
#   bash scripts/deploy_cloudrun.sh
#
# To tear down:
#   gcloud run services delete ca-demo --region us-central1 --project YOUR_PROJECT --quiet

set -euo pipefail

# ── Load .env ────────────────────────────────────────────────────────────────
if [[ ! -f .env ]]; then
  echo "ERROR: .env not found. Copy .env.example and fill in your values."
  exit 1
fi
set -o allexport
source .env
set +o allexport

PROJECT="${GCP_PROJECT_ID:?GCP_PROJECT_ID not set in .env}"
REGION="${CLOUD_RUN_REGION:-us-central1}"
IMAGE="us-central1-docker.pkg.dev/${PROJECT}/ca-demo-repo/ca-bot:latest"
SA="ca-bot@${PROJECT}.iam.gserviceaccount.com"

echo "Project : $PROJECT"
echo "Region  : $REGION"
echo "Image   : $IMAGE"
echo ""

# ── Build ─────────────────────────────────────────────────────────────────────
echo "==> Building container..."
gcloud builds submit --tag "$IMAGE" --project "$PROJECT"

# ── Deploy ────────────────────────────────────────────────────────────────────
echo ""
echo "==> Deploying to Cloud Run..."
gcloud run deploy ca-demo \
  --image "$IMAGE" \
  --region "$REGION" \
  --project "$PROJECT" \
  --no-allow-unauthenticated \
  --min-instances 1 \
  --no-cpu-throttling \
  --service-account "$SA" \
  --set-env-vars "\
SLACK_BOT_TOKEN=${SLACK_BOT_TOKEN},\
SLACK_APP_TOKEN=${SLACK_APP_TOKEN},\
GCP_PROJECT_ID=${GCP_PROJECT_ID},\
GCP_LOCATION=${GCP_LOCATION},\
GOOGLE_GENAI_USE_VERTEXAI=${GOOGLE_GENAI_USE_VERTEXAI},\
GOOGLE_CLOUD_PROJECT=${GOOGLE_CLOUD_PROJECT},\
GOOGLE_CLOUD_LOCATION=${GOOGLE_CLOUD_LOCATION},\
ROUTER_MODEL=${ROUTER_MODEL},\
AGENT_MODEL=${AGENT_MODEL},\
GRPC_DNS_RESOLVER=native,\
CA_AGENT_THELOOK=${CA_AGENT_THELOOK:-},\
CA_AGENT_STACKOVERFLOW=${CA_AGENT_STACKOVERFLOW:-},\
CA_AGENT_NCAA=${CA_AGENT_NCAA:-},\
CA_AGENT_CENSUS=${CA_AGENT_CENSUS:-},\
CA_AGENT_GA4=${CA_AGENT_GA4:-},\
CA_AGENT_GA360=${CA_AGENT_GA360:-}"

echo ""
echo "==> Done. Verify with:"
echo "    gcloud run services logs tail ca-demo --region $REGION --project $PROJECT"
