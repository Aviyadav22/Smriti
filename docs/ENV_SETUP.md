# Smriti — Environment Setup & Configuration

---

## 1. Prerequisites

| Tool | Version | Purpose | Install |
|------|---------|---------|---------|
| Python | 3.12+ | Backend runtime | [python.org](https://www.python.org/downloads/) |
| Node.js | 20 LTS+ | Frontend runtime | [nodejs.org](https://nodejs.org/) |
| Docker | 24+ | Local services (PostgreSQL, Redis, Neo4j) | [docker.com](https://www.docker.com/) |
| Docker Compose | 2.20+ | Multi-container orchestration | Included with Docker Desktop |
| Git | 2.40+ | Version control | [git-scm.com](https://git-scm.com/) |
| AWS CLI | 2.x | Download S3 dataset (optional — HTTPS also works) | [aws.amazon.com/cli](https://aws.amazon.com/cli/) |
| pnpm | 9+ | Frontend package manager | `npm install -g pnpm` |

### Optional (for OCR)
| Tool | Version | Purpose |
|------|---------|---------|
| Tesseract | 5.x | OCR fallback for scanned PDFs |
| poppler-utils | 23+ | PDF rendering (pdf2image dependency) |

---

## 2. Environment Variables

### `.env.example` (backend)

```bash
# ============================================
# SMRITI BACKEND CONFIGURATION
# ============================================
# Copy to .env and fill in values
# NEVER commit .env to git

# ---------- App ----------
APP_NAME=smriti
APP_ENV=development                    # development | staging | production
APP_DEBUG=true                         # Enable debug logging
APP_HOST=0.0.0.0
APP_PORT=8000
APP_VERSION=0.1.0
CORS_ORIGINS=http://localhost:3000     # Comma-separated allowed origins

# ---------- Security ----------
JWT_SECRET_KEY=                        # openssl rand -hex 32
JWT_REFRESH_SECRET_KEY=                # openssl rand -hex 32 (different from above)
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7
BCRYPT_COST_FACTOR=12
ENCRYPTION_KEY=                        # openssl rand -hex 32 (AES-256 key for PII encryption)

# ---------- PostgreSQL ----------
DATABASE_URL=postgresql+asyncpg://smriti:smriti_dev@localhost:5432/smriti
DATABASE_SSL_MODE=disable              # disable for local, require for production
DATABASE_POOL_SIZE=10
DATABASE_MAX_OVERFLOW=20

# ---------- Redis ----------
REDIS_URL=redis://localhost:6379/0
# For Upstash (production):
# REDIS_URL=rediss://default:YOUR_PASSWORD@YOUR_ENDPOINT.upstash.io:6379

# ---------- Gemini (LLM + Embeddings) ----------
LLM_PROVIDER=gemini
GEMINI_API_KEY=                        # From https://aistudio.google.com/apikey
GEMINI_MODEL=gemini-2.5-pro           # Model for chat, analysis, extraction
GEMINI_EMBEDDING_MODEL=gemini-embedding-001
GEMINI_EMBEDDING_DIMENSION=1536
GEMINI_MAX_TOKENS=8192                 # Max output tokens
GEMINI_TEMPERATURE=0.1                 # Low temp for factual extraction
GEMINI_RATE_LIMIT_RPM=60              # Requests per minute

# ---------- Pinecone (Vector DB) ----------
VECTOR_PROVIDER=pinecone
PINECONE_API_KEY=                      # From https://app.pinecone.io/
PINECONE_INDEX_NAME=smriti-legal
PINECONE_ENVIRONMENT=us-east-1        # Free tier region
PINECONE_DIMENSION=1536                # Must match embedding dimension
PINECONE_METRIC=cosine
PINECONE_CLOUD=aws                     # aws | gcp | azure
PINECONE_TOP_K=20                      # Default number of results

# ---------- Neo4j (Graph DB) ----------
GRAPH_PROVIDER=neo4j
NEO4J_URI=bolt://localhost:7687        # Local Docker
# NEO4J_URI=neo4j+s://YOUR_ID.databases.neo4j.io  # AuraDB
NEO4J_USER=neo4j
NEO4J_PASSWORD=smriti_dev              # Change in production
NEO4J_DATABASE=neo4j

# ---------- Cohere (Reranker) ----------
RERANKER_PROVIDER=cohere
COHERE_API_KEY=                        # From https://dashboard.cohere.com/api-keys
COHERE_RERANK_MODEL=rerank-v4.0-pro
COHERE_RERANK_TOP_N=10                # Return top N after reranking

# ---------- Storage ----------
STORAGE_PROVIDER=local                 # local | gcs
LOCAL_STORAGE_PATH=./data/pdfs         # Local PDF storage directory
# GCS (production):
# GCS_BUCKET_NAME=smriti-pdfs
# GCS_PROJECT_ID=your-gcp-project-id
# GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json

# ---------- Ingestion ----------
INGESTION_BATCH_SIZE=10                # PDFs to process in parallel
INGESTION_CONCURRENCY=5                # Parallel workers
INGESTION_TRACKER_DB=./data/ingestion_tracker.db  # SQLite for progress tracking

# ---------- Rate Limiting ----------
RATE_LIMIT_DEFAULT=100/minute          # Per-user default
RATE_LIMIT_SEARCH=60/minute            # Search endpoint
RATE_LIMIT_CHAT=10/minute              # Chat/LLM endpoints
RATE_LIMIT_INGEST=5/minute             # Ingestion endpoint

# ---------- Logging ----------
LOG_LEVEL=INFO                         # DEBUG | INFO | WARNING | ERROR
LOG_FORMAT=json                        # json | text
LOG_PII_REDACTION=true                 # Redact emails, IPs in logs
```

### `.env.local` (frontend)

```bash
# ============================================
# SMRITI FRONTEND CONFIGURATION
# ============================================

NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
NEXT_PUBLIC_APP_NAME=Smriti
NEXT_PUBLIC_APP_DESCRIPTION=Indian Legal Research Platform
```

---

## 3. Local Development Setup

### Step 1: Clone and Configure

```bash
git clone <repo-url> smriti
cd smriti

# Backend env
cp backend/.env.example backend/.env
# Edit backend/.env — fill in API keys (see "Getting API Keys" below)

# Frontend env
cp frontend/.env.example frontend/.env.local
```

### Step 2: Start Infrastructure Services

```bash
# Start PostgreSQL, Redis, Neo4j
docker compose up -d

# Verify services are running
docker compose ps
# Expected: postgres (5432), redis (6379), neo4j (7474/7687)
```

### Step 3: Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate     # Linux/Mac
# .venv\Scripts\activate      # Windows

# Install dependencies
pip install -e ".[dev]"

# Run database migrations
alembic upgrade head

# Seed court master data
python scripts/seed_courts.py

# Start backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Verify: http://localhost:8000/docs (Swagger UI)
# Verify: http://localhost:8000/health
```

### Step 4: Frontend Setup

```bash
cd frontend

# Install dependencies
pnpm install

# Start dev server
pnpm dev

# Verify: http://localhost:3000
```

### Step 5: Ingest Sample Data

```bash
cd backend

# Download one year of SC judgments (no AWS credentials needed)
# Option A: AWS CLI
aws s3 cp s3://indian-supreme-court-judgments/data/tar/year=2024/english/english.tar ./data/raw/ --no-sign-request
aws s3 cp s3://indian-supreme-court-judgments/metadata/parquet/year=2024/metadata.parquet ./data/raw/ --no-sign-request

# Option B: HTTPS (no AWS CLI needed)
curl -O https://indian-supreme-court-judgments.s3.amazonaws.com/data/zip/year=2024/english.zip
curl -O https://indian-supreme-court-judgments.s3.amazonaws.com/metadata/parquet/year=2024/metadata.parquet

# Run ingestion
python scripts/ingest_s3.py --year 2024
```

---

## 4. Docker Compose (Local Dev)

```yaml
# docker-compose.yml
version: "3.9"

services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: smriti
      POSTGRES_USER: smriti
      POSTGRES_PASSWORD: smriti_dev
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U smriti"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5

  neo4j:
    image: neo4j:5-community
    environment:
      NEO4J_AUTH: neo4j/smriti_dev
      NEO4J_PLUGINS: '["apoc"]'
    ports:
      - "7474:7474"   # Browser UI
      - "7687:7687"   # Bolt protocol
    volumes:
      - neo4j_data:/data

volumes:
  postgres_data:
  redis_data:
  neo4j_data:
```

---

## 5. Getting API Keys

### Gemini API Key (Required)
1. Go to [Google AI Studio](https://aistudio.google.com/apikey)
2. Sign in with Google account
3. Click "Create API Key"
4. Copy key → set `GEMINI_API_KEY` in `.env`
5. For $300 credits: [Google Cloud Free Trial](https://cloud.google.com/free) → enable Vertex AI

### Pinecone API Key (Required)
1. Go to [Pinecone Console](https://app.pinecone.io/)
2. Sign up (free tier: 100K vectors)
3. Create index:
   - Name: `smriti-legal`
   - Dimensions: `1536`
   - Metric: `cosine`
   - Cloud: `AWS`
   - Region: `us-east-1`
4. Go to API Keys → copy key → set `PINECONE_API_KEY`

### Neo4j AuraDB (Optional — Docker works for dev)
1. Go to [Neo4j AuraDB](https://neo4j.com/cloud/aura-free/)
2. Create free instance (200K nodes, 400K relationships)
3. Save connection URI and password
4. Set `NEO4J_URI` and `NEO4J_PASSWORD`

### Cohere API Key (Required for reranking)
1. Go to [Cohere Dashboard](https://dashboard.cohere.com/)
2. Sign up (free tier: 1,000 API calls/month)
3. Go to API Keys → copy key → set `COHERE_API_KEY`

### Redis / Upstash (Optional — Docker works for dev)
1. For production: [Upstash Console](https://console.upstash.com/)
2. Create Redis database (free tier: 10K commands/day)
3. Copy Redis URL → set `REDIS_URL`

---

## 6. Makefile Commands

```makefile
# Makefile

.PHONY: dev test lint migrate ingest clean

# Start all services
dev:
	docker compose up -d
	cd backend && uvicorn app.main:app --reload --port 8000 &
	cd frontend && pnpm dev &

# Run backend tests
test:
	cd backend && pytest -v --cov=app

# Run linters
lint:
	cd backend && ruff check . && mypy app/

# Run database migrations
migrate:
	cd backend && alembic upgrade head

# Create new migration
migration:
	cd backend && alembic revision --autogenerate -m "$(msg)"

# Ingest SC judgments for one year
ingest:
	cd backend && python scripts/ingest_s3.py --year $(year)

# Ingest all available years
ingest-all:
	cd backend && python scripts/ingest_s3.py --all

# Clean local data
clean:
	docker compose down -v
	rm -rf backend/data/raw/*
	rm -rf backend/data/pdfs/*
	rm -f backend/data/ingestion_tracker.db

# Health check
health:
	curl -s http://localhost:8000/health | python -m json.tool
```

---

## 7. Production Configuration (GCP)

### Cloud Run Environment Variables

Set via `gcloud run deploy` or GCP Console:

```bash
# App
APP_ENV=production
APP_DEBUG=false
CORS_ORIGINS=https://smriti.app  # Your domain

# Secrets (from GCP Secret Manager)
JWT_SECRET_KEY=sm://smriti/jwt-secret
JWT_REFRESH_SECRET_KEY=sm://smriti/jwt-refresh-secret
ENCRYPTION_KEY=sm://smriti/encryption-key
GEMINI_API_KEY=sm://smriti/gemini-api-key
PINECONE_API_KEY=sm://smriti/pinecone-api-key
COHERE_API_KEY=sm://smriti/cohere-api-key

# Cloud SQL
DATABASE_URL=postgresql+asyncpg://smriti:PASSWORD@/smriti?host=/cloudsql/PROJECT:REGION:INSTANCE
DATABASE_SSL_MODE=require

# Redis (Upstash)
REDIS_URL=rediss://default:PASSWORD@ENDPOINT.upstash.io:6379

# Neo4j AuraDB
NEO4J_URI=neo4j+s://ID.databases.neo4j.io
NEO4J_PASSWORD=sm://smriti/neo4j-password

# GCS Storage
STORAGE_PROVIDER=gcs
GCS_BUCKET_NAME=smriti-pdfs
GCS_PROJECT_ID=your-project-id
```

### GCP Secret Manager Setup

```bash
# Create secrets
gcloud secrets create jwt-secret --data-file=- <<< "$(openssl rand -hex 32)"
gcloud secrets create jwt-refresh-secret --data-file=- <<< "$(openssl rand -hex 32)"
gcloud secrets create encryption-key --data-file=- <<< "$(openssl rand -hex 32)"
gcloud secrets create gemini-api-key --data-file=- <<< "YOUR_API_KEY"
gcloud secrets create pinecone-api-key --data-file=- <<< "YOUR_API_KEY"
gcloud secrets create cohere-api-key --data-file=- <<< "YOUR_API_KEY"
gcloud secrets create neo4j-password --data-file=- <<< "YOUR_PASSWORD"

# Grant Cloud Run access
gcloud secrets add-iam-policy-binding jwt-secret \
  --member="serviceAccount:YOUR_SA@PROJECT.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

---

## 8. Directory Structure for Data

```
backend/
├── data/
│   ├── raw/               # Downloaded S3 archives (tar/zip/parquet)
│   │   ├── year=2024/
│   │   │   ├── english.tar
│   │   │   └── metadata.parquet
│   │   └── year=2023/
│   ├── extracted/          # Extracted PDFs (temporary, delete after ingest)
│   │   └── year=2024/
│   │       ├── case_001.pdf
│   │       └── case_002.pdf
│   ├── pdfs/               # Stored PDFs (permanent, organized by shard)
│   │   ├── 00/
│   │   ├── 01/
│   │   └── ff/
│   └── ingestion_tracker.db  # SQLite progress tracking
```

All paths under `data/` are in `.gitignore`.

---

## 9. IDE Setup

### VS Code Extensions (Recommended)
- Python (ms-python.python)
- Pylance (ms-python.vscode-pylance)
- Ruff (charliermarsh.ruff)
- ESLint (dbaeumer.vscode-eslint)
- Tailwind CSS IntelliSense (bradlc.vscode-tailwindcss)
- Docker (ms-azuretools.vscode-docker)
- GitLens (eamodio.gitlens)

### VS Code Settings

```json
{
  "python.defaultInterpreterPath": "./backend/.venv/bin/python",
  "[python]": {
    "editor.defaultFormatter": "charliermarsh.ruff",
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": {
      "source.fixAll.ruff": "explicit",
      "source.organizeImports.ruff": "explicit"
    }
  },
  "[typescript]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode",
    "editor.formatOnSave": true
  }
}
```
