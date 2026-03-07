#!/bin/bash
# One-shot deploy script for Cloud Shell
# Usage: bash cloud_deploy.sh
set -e

PROJECT_ID="smriti-489416"
REGION="asia-south1"
REPO="smriti-repo"
REGISTRY="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}"

echo "=== Step 1: Grant Cloud Build permissions ==="
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
  --role="roles/artifactregistry.writer" --quiet 2>/dev/null || echo "Permission may already exist or needs console IAM setup"

echo "=== Step 2: Clone/update repo ==="
if [ -d ~/smriti ]; then
  cd ~/smriti && git pull
else
  git clone https://github.com/Aviyadav22/Smriti.git ~/smriti && cd ~/smriti
fi
cd ~/smriti

echo "=== Step 3: Build backend ==="
gcloud builds submit --tag ${REGISTRY}/smriti-backend:latest ./backend --region=${REGION}

echo "=== Step 4: Remove APP_ENV env var conflict ==="
gcloud run services update smriti-backend --region $REGION --remove-env-vars APP_ENV --quiet 2>/dev/null || true

echo "=== Step 5: Deploy backend ==="
gcloud run deploy smriti-backend \
  --image ${REGISTRY}/smriti-backend:latest \
  --region $REGION \
  --memory 2Gi \
  --cpu 2 \
  --set-secrets="DATABASE_URL=DATABASE_URL:latest,REDIS_URL=REDIS_URL:latest,GEMINI_API_KEY=GEMINI_API_KEY:latest,PINECONE_API_KEY=PINECONE_API_KEY:latest,PINECONE_HOST=PINECONE_HOST:latest,NEO4J_URI=NEO4J_URI:latest,NEO4J_USER=NEO4J_USER:latest,NEO4J_PASSWORD=NEO4J_PASSWORD:latest,JWT_SECRET_KEY=JWT_SECRET_KEY:latest,JWT_REFRESH_SECRET_KEY=JWT_REFRESH_SECRET_KEY:latest,ENCRYPTION_KEY=ENCRYPTION_KEY:latest,COHERE_API_KEY=COHERE_API_KEY:latest,CORS_ORIGINS=CORS_ORIGINS:latest,APP_ENV=APP_ENV:latest" \
  --quiet

echo "=== Step 6: Import data into Supabase ==="
if [ -f ~/cases_export.sql ]; then
  echo "Found cases_export.sql, importing into Supabase..."
  sudo apt-get install -y postgresql-client -qq 2>/dev/null || true

  # Read DATABASE_URL from Secret Manager (do not echo)
  echo "Importing cases into production database..."
  psql "$(gcloud secrets versions access latest --secret=DATABASE_URL)" < ~/cases_export.sql
  echo "Data import complete!"
else
  echo "WARNING: ~/cases_export.sql not found."
  echo "Upload it via Cloud Shell (3-dot menu → Upload) then run:"
  echo "  psql \"\$(gcloud secrets versions access latest --secret=DATABASE_URL)\" < ~/cases_export.sql"
fi

echo ""
echo "=== DONE ==="
BACKEND_URL=$(gcloud run services describe smriti-backend --region $REGION --format='value(status.url)')
echo "Backend: $BACKEND_URL"
echo "Health:  $BACKEND_URL/health"
