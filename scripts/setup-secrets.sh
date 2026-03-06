#!/bin/bash
# =============================================================================
# Smriti — Secret Manager Setup
# Run this FIRST in Cloud Shell before deploy.sh
# =============================================================================
set -e

PROJECT_ID="smriti-489416"
gcloud config set project $PROJECT_ID

echo "Creating secrets in Secret Manager..."
echo "You'll be prompted for each value."
echo ""

# Helper function
create_secret() {
  local name=$1
  local prompt=$2

  echo -n "$prompt: "
  read -r value

  # Create secret if it doesn't exist
  gcloud secrets create "$name" --replication-policy="automatic" 2>/dev/null || true

  # Add the value
  echo -n "$value" | gcloud secrets versions add "$name" --data-file=-
  echo "  ✓ $name set"
}

echo "=== Database (use Neon free tier: https://neon.tech) ==="
create_secret "DATABASE_URL" "PostgreSQL URL (postgresql+asyncpg://user:pass@host/db)"

echo ""
echo "=== Redis (use Upstash free tier: https://upstash.com) ==="
create_secret "REDIS_URL" "Redis URL (rediss://default:pass@host:port)"

echo ""
echo "=== Security Keys (generate with: openssl rand -hex 32) ==="
create_secret "JWT_SECRET_KEY" "JWT Secret Key (64-char hex)"
create_secret "JWT_REFRESH_SECRET_KEY" "JWT Refresh Secret Key (64-char hex)"
create_secret "ENCRYPTION_KEY" "Encryption Key (64-char hex)"

echo ""
echo "=== Gemini API ==="
create_secret "GEMINI_API_KEY" "Gemini API Key"

echo ""
echo "=== Pinecone ==="
create_secret "PINECONE_API_KEY" "Pinecone API Key"
create_secret "PINECONE_HOST" "Pinecone Host URL (https://smriti-legal-xxx.svc.xxx.pinecone.io)"

echo ""
echo "=== Neo4j ==="
create_secret "NEO4J_URI" "Neo4j URI (neo4j+s://xxx.databases.neo4j.io)"
create_secret "NEO4J_USER" "Neo4j User"
create_secret "NEO4J_PASSWORD" "Neo4j Password"

echo ""
echo "=== Cohere ==="
create_secret "COHERE_API_KEY" "Cohere API Key"

echo ""
echo "=== CORS (will be updated after deployment) ==="
echo -n "http://localhost:3000" | gcloud secrets create "CORS_ORIGINS" \
  --replication-policy="automatic" --data-file=- 2>/dev/null || \
  echo -n "http://localhost:3000" | gcloud secrets versions add "CORS_ORIGINS" --data-file=-

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
