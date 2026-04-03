# Quick Start Guide — Smriti

**Audience:** New developer with zero codebase context
**Goal:** Clone the repo and get everything running locally

---

## Prerequisites

Install these before starting:

| Tool | Version | Why |
|------|---------|-----|
| Docker + Docker Compose | Latest | Runs PostgreSQL, Redis, Neo4j locally |
| Python | 3.12+ | Backend runtime |
| Node.js | 22+ | Frontend runtime |
| npm | (comes with Node) | Frontend package manager (NOT yarn/pnpm) |
| Tesseract OCR | Latest | PDF OCR fallback (used by pytesseract) |
| Poppler | Latest | PDF-to-image conversion (used by pdf2image) |
| Git | Latest | Version control |

### Installing Tesseract & Poppler (Windows)
```bash
# Via chocolatey:
choco install tesseract poppler
# Or download manually from:
# Tesseract: https://github.com/UB-Mannheim/tesseract/wiki
# Poppler: https://github.com/oschwartz10612/poppler-windows/releases
```

---

## Step 1: Clone the Repository

```bash
git clone <repo-url>
cd Smriti
```

The top-level structure:
```
Smriti/
  backend/     # FastAPI Python API server
  frontend/    # Next.js TypeScript web app
  ingestion/   # Standalone ingestion scripts
  docs/        # Documentation
  nginx/       # Production reverse proxy
  data/        # Local data (PDFs, statutes)
```

## Step 2: Start Infrastructure (PostgreSQL, Redis, Neo4j)

```bash
make infra
# Or: docker compose up -d
```

This starts three containers:
- **PostgreSQL 16** on `localhost:5432` (user: `smriti`, password: `smriti_dev`)
- **Redis 7** on `localhost:6379` (password: `dev_password`)
- **Neo4j 5** on `localhost:7687` (bolt) / `localhost:7474` (web UI, user: `neo4j`, password: `smriti_dev`)

Verify they're running:
```bash
docker compose ps
```

## Step 3: Set Up Backend Environment

```bash
cd backend
cp .env.example .env
```

Edit `.env` and fill in these required values:

```ini
# Generate with: openssl rand -hex 32
JWT_SECRET_KEY=<32+ char random string>
JWT_REFRESH_SECRET_KEY=<32+ char random string>
ENCRYPTION_KEY=<64 char hex string>

# Get from Google AI Studio (https://aistudio.google.com/app/apikey)
GEMINI_API_KEY=<your-gemini-api-key>

# Get from Pinecone console (https://app.pinecone.io)
PINECONE_API_KEY=<your-pinecone-key>
PINECONE_HOST=<your-index-host-url>

# Get from Cohere dashboard (https://dashboard.cohere.com/api-keys)
COHERE_API_KEY=<your-cohere-key>

# These should match docker-compose.yml defaults:
DATABASE_URL=postgresql+asyncpg://smriti:smriti_dev@localhost:5432/smriti
REDIS_URL=redis://:dev_password@localhost:6379/0
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=smriti_dev
```

**Note:** Redis URL needs the password (`:dev_password@`). The default in `.env.example` may be missing it.

## Step 4: Install Python Dependencies

```bash
cd backend
pip install -e ".[dev]"
```

This installs FastAPI, SQLAlchemy, Gemini SDK, Pinecone, Cohere, LangGraph, and all other dependencies from `pyproject.toml`.

## Step 5: Run Database Migrations

```bash
cd backend
alembic upgrade head
# Or from repo root: make migrate
```

This creates all 38 migration tables (cases, users, documents, statutes, agents, audit logs, etc.).

## Step 6: Install Pre-commit Hooks

```bash
pre-commit install
```

This sets up automatic linting (ruff), type checking (mypy), and secret detection on every commit.

## Step 7: Start the Backend

```bash
cd backend
uvicorn app.main:app --reload --port 8000
# Or from repo root: make backend
```

The backend will:
1. Configure logging
2. Validate connectivity (PostgreSQL, Redis, Pinecone, Gemini)
3. Start serving on `http://localhost:8000`

**Verify:** Visit `http://localhost:8000/docs` for the Swagger UI (only in debug mode).

## Step 8: Set Up Frontend

In a **new terminal**:
```bash
cd frontend
npm install
npm run dev
```

Frontend starts on `http://localhost:3000`.

## Step 9: Create a Test Account

1. Open `http://localhost:3000/register`
2. Create an account (email + password)
3. Log in at `http://localhost:3000/login`

## Step 10: Verify Everything Works

```bash
# Health check
curl http://localhost:8000/health

# Or from repo root
make health
```

Expected response: `{"status": "ok"}`

---

## Running Tests

### Backend Tests (~2185 tests)
```bash
cd backend

# All tests with coverage
make test
# Or: pytest -v --cov=app

# Unit tests only (fast)
make test-unit
# Or: pytest tests/unit/ -v

# Integration tests (requires running infrastructure)
make test-integration

# Security tests
make test-security
```

### Frontend Tests (~311 tests)
```bash
cd frontend
npm test           # Watch mode
npm test -- --run  # Single run (CI mode)
```

**Important:** Frontend uses **vitest**, NOT jest.

---

## Common Issues & Fixes

### "Redis is not available"
Make sure Redis is running with password:
```bash
docker compose ps redis
# Check logs: docker compose logs redis
```
And your `REDIS_URL` includes the password: `redis://:dev_password@localhost:6379/0`

### "Pinecone dimension mismatch"
Your Pinecone index must be 1536 dimensions. Create a new index if needed:
- Model: `cosine` metric
- Dimensions: `1536`

### "Gemini API error"
- Verify your API key at https://aistudio.google.com/app/apikey
- Check rate limits (free tier: 60 RPM)
- Note: Some models (preview versions) may not be available on all tiers

### Neo4j "Authentication failed"
Default credentials in docker-compose: `neo4j` / `smriti_dev`. If Neo4j prompts for password change on first run, update your `.env`.

### "alembic.util.exc.CommandError: Target database is not up to date"
Run migrations first: `alembic upgrade head`

### Frontend build fails with "Module not found"
```bash
cd frontend
rm -rf node_modules .next
npm install
npm run dev
```

### Tests fail with "asyncpg connection refused"
Make sure PostgreSQL is running: `docker compose up -d postgres`

---

## Useful Makefile Commands

| Command | Purpose |
|---------|---------|
| `make infra` | Start Docker infrastructure |
| `make backend` | Start backend dev server |
| `make test` | Run all backend tests |
| `make test-unit` | Run unit tests only |
| `make lint` | Run ruff linter + mypy |
| `make format` | Auto-format Python code |
| `make migrate` | Apply database migrations |
| `make health` | Check backend health |
| `make clean` | **DESTRUCTIVE** — destroy all Docker volumes |

---

## Next Steps

After getting the app running:
1. Read `docs/onboarding/01_ARCHITECTURE_OVERVIEW.md` for the big picture
2. Try a search query at `http://localhost:3000/search`
3. Explore the Neo4j browser at `http://localhost:7474`
4. Read `docs/onboarding/09_VANSH_ONBOARDING_ROADMAP.md` for your learning path
