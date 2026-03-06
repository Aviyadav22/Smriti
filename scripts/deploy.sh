#!/bin/bash
# =============================================================================
# Smriti Deployment Script — Run in Google Cloud Shell
# Project: smriti-489416
# =============================================================================
set -e

PROJECT_ID="smriti-489416"
REGION="asia-south1"  # Mumbai — closest to Indian users
REPO_NAME="smriti"

echo "=== Step 1: Set project ==="
gcloud config set project $PROJECT_ID

echo "=== Step 2: Create Artifact Registry repo ==="
gcloud artifacts repositories create $REPO_NAME \
  --repository-format=docker \
  --location=$REGION \
  --description="Smriti container images" \
  2>/dev/null || echo "Repo already exists"

echo "=== Step 3: Configure Docker auth ==="
gcloud auth configure-docker ${REGION}-docker.pkg.dev --quiet

echo "=== Step 4: Build & push backend image ==="
cd backend
docker build -t ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/backend:latest .
docker push ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/backend:latest
cd ..

echo "=== Step 5: Build & push frontend image ==="
cd frontend
docker build \
  --build-arg NEXT_PUBLIC_API_URL=https://smriti-backend-HASH-${REGION}.a.run.app/api/v1 \
  -t ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/frontend:latest .
docker push ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/frontend:latest
cd ..

echo "=== Step 6: Deploy backend to Cloud Run ==="
gcloud run deploy smriti-backend \
  --image=${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/backend:latest \
  --region=$REGION \
  --platform=managed \
  --allow-unauthenticated \
  --memory=1Gi \
  --cpu=1 \
  --min-instances=0 \
  --max-instances=3 \
  --port=8000 \
  --set-env-vars="APP_ENV=production,APP_DEBUG=false,LOG_LEVEL=INFO" \
  --set-secrets="\
DATABASE_URL=DATABASE_URL:latest,\
REDIS_URL=REDIS_URL:latest,\
JWT_SECRET_KEY=JWT_SECRET_KEY:latest,\
JWT_REFRESH_SECRET_KEY=JWT_REFRESH_SECRET_KEY:latest,\
ENCRYPTION_KEY=ENCRYPTION_KEY:latest,\
GEMINI_API_KEY=GEMINI_API_KEY:latest,\
PINECONE_API_KEY=PINECONE_API_KEY:latest,\
PINECONE_HOST=PINECONE_HOST:latest,\
NEO4J_URI=NEO4J_URI:latest,\
NEO4J_USER=NEO4J_USER:latest,\
NEO4J_PASSWORD=NEO4J_PASSWORD:latest,\
COHERE_API_KEY=COHERE_API_KEY:latest,\
CORS_ORIGINS=CORS_ORIGINS:latest"

echo "=== Step 7: Get backend URL ==="
BACKEND_URL=$(gcloud run services describe smriti-backend --region=$REGION --format='value(status.url)')
echo "Backend URL: $BACKEND_URL"

echo "=== Step 8: Rebuild frontend with correct backend URL ==="
cd frontend
docker build \
  --build-arg NEXT_PUBLIC_API_URL=${BACKEND_URL}/api/v1 \
  -t ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/frontend:latest .
docker push ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/frontend:latest
cd ..

echo "=== Step 9: Deploy frontend to Cloud Run ==="
gcloud run deploy smriti-frontend \
  --image=${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/frontend:latest \
  --region=$REGION \
  --platform=managed \
  --allow-unauthenticated \
  --memory=512Mi \
  --cpu=1 \
  --min-instances=0 \
  --max-instances=3 \
  --port=3000

echo "=== Step 10: Update backend CORS with frontend URL ==="
FRONTEND_URL=$(gcloud run services describe smriti-frontend --region=$REGION --format='value(status.url)')
echo "Frontend URL: $FRONTEND_URL"

# Update CORS_ORIGINS secret to include frontend URL
echo -n "${FRONTEND_URL},http://localhost:3000" | \
  gcloud secrets versions add CORS_ORIGINS --data-file=-

# Redeploy backend to pick up new CORS
gcloud run services update smriti-backend --region=$REGION \
  --set-secrets="CORS_ORIGINS=CORS_ORIGINS:latest"

echo ""
echo "============================================="
echo "  DEPLOYMENT COMPLETE!"
echo "============================================="
echo "  Backend:  $BACKEND_URL"
echo "  Frontend: $FRONTEND_URL"
echo "  Health:   $BACKEND_URL/health"
echo "============================================="
