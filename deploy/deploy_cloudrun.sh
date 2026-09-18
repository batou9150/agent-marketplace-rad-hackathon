#!/usr/bin/env bash
# ==============================================================================
# Vibe Guard A2UI — Cloud Run Packaging and Deployment Script
# Follows A2UI Cloud Run Deployer and SPEC-DEP-1..5 guidelines.
# ==============================================================================

set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:-${PROJECT_ID:-}}"
REGION="${GCP_REGION:-${REGION:-us-central1}}"
SERVICE_NAME="${SERVICE_NAME:-vibe-guard-a2ui}"
AR_REPO="${AR_REPO:-vibe-guard}"
IMAGE_TAG="${IMAGE_TAG:-latest}"

if [[ -z "${PROJECT_ID}" ]]; then
  echo "❌ Error: GCP_PROJECT_ID or PROJECT_ID environment variable must be set." >&2
  echo "Usage: GCP_PROJECT_ID=my-project-id ./deploy/deploy_cloudrun.sh" >&2
  exit 1
fi

echo "======================================================================"
echo "🛡️  VIBE GUARD A2UI — CLOUD RUN DEPLOYMENT"
echo "======================================================================"
echo "Project ID    : ${PROJECT_ID}"
echo "Region        : ${REGION}"
echo "Service Name  : ${SERVICE_NAME}"
echo "Artifact Repo : ${AR_REPO}"
echo "======================================================================"

IMAGE_URI="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}/${SERVICE_NAME}:${IMAGE_TAG}"

echo "Step 1: Ensuring Artifact Registry repository exists..."
gcloud artifacts repositories describe "${AR_REPO}" \
  --project="${PROJECT_ID}" \
  --location="${REGION}" >/dev/null 2>&1 || \
gcloud artifacts repositories create "${AR_REPO}" \
  --project="${PROJECT_ID}" \
  --location="${REGION}" \
  --repository-format=docker \
  --description="Vibe Guard Container Images"

echo "Step 2: Building container image via Cloud Build..."
gcloud builds submit . \
  --project="${PROJECT_ID}" \
  --config="deploy/cloudbuild.yaml" \
  --substitutions="_LOCATION=${REGION},_REPO=${AR_REPO},_IMAGE=${SERVICE_NAME},_TAG=${IMAGE_TAG}"

echo "Step 3: Deploying container to Cloud Run..."
# Security flags: default to private IAM/IAP and minimal SA (SPEC-OPS-3)
ALLOW_UNAUTH_FLAG="--no-allow-unauthenticated"
if [ "${ALLOW_UNAUTHENTICATED:-false}" = "true" ]; then
  ALLOW_UNAUTH_FLAG="--allow-unauthenticated"
fi

INGRESS_FLAG="--ingress=internal-and-cloud-load-balancing"
if [ -n "${INGRESS:-}" ]; then
  INGRESS_FLAG="--ingress=${INGRESS}"
fi

SA_FLAG="--service-account=vibe-guard-agent-sa@${PROJECT_ID}.iam.gserviceaccount.com"
if [ "${USE_DEFAULT_SA:-false}" = "true" ]; then
  SA_FLAG=""
fi

gcloud run deploy "${SERVICE_NAME}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --image="${IMAGE_URI}" \
  --platform=managed \
  ${ALLOW_UNAUTH_FLAG} \
  ${INGRESS_FLAG} \
  ${SA_FLAG} \
  --port=8080 \
  --cpu=2 \
  --memory=2Gi \
  --concurrency=8 \
  --timeout=300 \
  --execution-environment=gen2 \
  --set-env-vars="VIBE_GUARD_ENV=production,PYTHONUNBUFFERED=1,PYTHONDONTWRITEBYTECODE=1,TMPDIR=/tmp,CALLER_ID=vibe-guard-auditor@gcp.sfeir.com"

SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --format='value(status.url)')

A2A_URL="${SERVICE_URL}/a2a/vibe_guard_a2ui"
CARD_URL="${A2A_URL}/.well-known/agent-card.json"

echo "======================================================================"
echo "✅ DEPLOYMENT SUCCESSFUL!"
echo "======================================================================"
echo "Service URL      : ${SERVICE_URL}"
echo "A2A Endpoint     : ${A2A_URL}"
echo "Agent Card URL   : ${CARD_URL}"
echo "======================================================================"
echo "Verifying Agent Card availability..."
curl -s "${CARD_URL}" | grep -q "VibeGuardAgent" && echo "✓ Agent Card verified." || echo "⚠️ Warning: Agent card check returned unexpected content."
echo "======================================================================"
