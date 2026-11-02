#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:-okshouse-backend}"
REGION="${CLOUD_RUN_REGION:-asia-northeast3}"
SERVICE="${CLOUD_RUN_SERVICE:-okshouse-backend}"
SERVICE_ACCOUNT="okshouse-cloud-run@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud run deploy "$SERVICE" \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --source . \
  --port 8000 \
  --allow-unauthenticated \
  --min 0 \
  --max-instances 2 \
  --memory 512Mi \
  --cpu 1 \
  --concurrency 40 \
  --timeout 60 \
  --service-account "$SERVICE_ACCOUNT" \
  --set-env-vars 'ENVIRONMENT=production,DEBUG=false,HOST=0.0.0.0' \
  --set-secrets 'DATABASE_URL=DATABASE_URL:latest,SECRET_KEY=SECRET_KEY:latest,AES_KEY=AES_KEY:latest,AES_IV=AES_IV:latest,LOGIN_KEYS=LOGIN_KEYS:latest,ALLOWED_API_KEYS=ALLOWED_API_KEYS:latest,JWT_SECRET_KEY=JWT_SECRET_KEY:latest,JWT_ALGORITHM=JWT_ALGORITHM:latest,ACCESS_TOKEN_EXPIRE_SECONDS=ACCESS_TOKEN_EXPIRE_SECONDS:latest,REFRESH_TOKEN_EXPIRE_SECONDS=REFRESH_TOKEN_EXPIRE_SECONDS:latest,ALLOWED_ORIGINS=ALLOWED_ORIGINS:latest,FCM_SERVICE_ACCOUNT_JSON=FCM_SERVICE_ACCOUNT_JSON:latest'
