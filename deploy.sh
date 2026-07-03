#!/usr/bin/env bash
# Deploy olx-cars-mcp to Google Cloud Run (free tier, scale-to-zero).
# Prereqs (one-time): `gcloud auth login` and a project with billing enabled.
# Usage:  CARS_DATABASE_URL='postgresql://…?sslmode=require' ./deploy.sh
set -euo pipefail
: "${CARS_DATABASE_URL:?set CARS_DATABASE_URL to the read-only Postgres DSN}"
REGION="${REGION:-us-central1}"

gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com

gcloud run deploy olx-cars-mcp \
  --source . \
  --region "$REGION" \
  --allow-unauthenticated \
  --port 8000 \
  --set-env-vars ALLOW_SQL=0 \
  --set-env-vars "CARS_DATABASE_URL=${CARS_DATABASE_URL}"

echo
echo "Done. Your public MCP URL is the service URL above with /mcp appended, e.g.:"
echo "  https://olx-cars-mcp-XXXXXX-uc.a.run.app/mcp"
echo "Add it in Claude Code:  claude mcp add --transport http olx-cars <URL>"
