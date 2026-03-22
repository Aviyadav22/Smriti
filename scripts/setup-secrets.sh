#!/bin/bash
# =============================================================================
# Smriti — Secret Manager Setup
# Run this FIRST in Cloud Shell before deploy.sh
# =============================================================================
set -e

PROJECT_ID="smriti-489416"
gcloud config set project $PROJECT_ID

echo "Creating secrets in Secret Manager..."
echo ""

# Helper: create or update a secret with a value
set_secret() {
  local name=$1
  local value=$2

  gcloud secrets create "$name" --replication-policy="automatic" 2>/dev/null || true
  echo -n "$value" | gcloud secrets versions add "$name" --data-file=-
  echo "  ✓ $name"
}

# Helper: prompt for a secret
prompt_secret() {
  local name=$1
  local prompt=$2

  echo -n "$prompt: "
  read -r value
  set_secret "$name" "$value"
}

echo "=== PostgreSQL (Hostinger KVM2 VPS) ==="
set_secret "DATABASE_URL" "postgresql+asyncpg://smriti:***REMOVED***@76.13.185.172:5432/smriti"

echo ""
echo "=== Redis (Upstash) ==="
prompt_secret "REDIS_URL" "Redis URL (rediss://...)"

echo ""
echo "=== Security Keys ==="
prompt_secret "JWT_SECRET_KEY" "JWT Secret Key (64-char hex)"
prompt_secret "JWT_REFRESH_SECRET_KEY" "JWT Refresh Secret Key (64-char hex)"
prompt_secret "ENCRYPTION_KEY" "Encryption Key (64-char hex)"

echo ""
echo "=== Gemini API ==="
prompt_secret "GEMINI_API_KEY" "Primary Gemini API Key"
prompt_secret "GEMINI_API_KEYS" "Comma-separated Gemini API Keys (for round-robin)"

echo ""
echo "=== Pinecone ==="
prompt_secret "PINECONE_API_KEY" "Pinecone API Key"
prompt_secret "PINECONE_HOST" "Pinecone Host URL"

echo ""
echo "=== Neo4j ==="
prompt_secret "NEO4J_URI" "Neo4j URI (neo4j+s://...)"
prompt_secret "NEO4J_USER" "Neo4j User"
prompt_secret "NEO4J_PASSWORD" "Neo4j Password"
prompt_secret "NEO4J_DATABASE" "Neo4j Database Name"

echo ""
echo "=== Cohere ==="
prompt_secret "COHERE_API_KEY" "Cohere API Key"

echo ""
echo "=== Indian Kanoon ==="
prompt_secret "IK_API_TOKEN" "Indian Kanoon API Token"

echo ""
echo "=== Tavily ==="
prompt_secret "TAVILY_API_KEY" "Tavily API Key"

echo ""
echo "=== Sentry (optional, press Enter to skip) ==="
prompt_secret "SENTRY_DSN" "Sentry DSN"

echo ""
echo "=== CORS (will be updated after deployment) ==="
set_secret "CORS_ORIGINS" "http://localhost:3000"

echo ""
echo "=== Grant Cloud Run access to secrets ==="
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor" \
  --quiet

echo ""
echo "============================================="
echo "  ALL SECRETS CONFIGURED!"
echo "  Now run: bash scripts/deploy.sh"
echo "============================================="
