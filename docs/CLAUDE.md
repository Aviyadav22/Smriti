# CLAUDE.md — Smriti Master Briefing

> Read this file first on every session. It tells you what the product is, how it's built, and what rules to follow.

---

## What is Smriti?

Smriti is a purpose-built Indian legal research platform — think Harvey AI but specifically for Indian law. It helps lawyers find relevant case law precedents through hybrid semantic + keyword search, understand citation networks between judgments, and get AI-powered analysis of legal issues — all grounded in actual Indian court judgments.

**One-line pitch**: AI-powered legal research for Indian lawyers — find the right precedent in seconds, not hours.

---

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Frontend | Next.js 15 (App Router) + TypeScript + Tailwind CSS + shadcn/ui | SSR, type-safe, fast DX |
| Backend | FastAPI (Python 3.12) | AI/ML ecosystem, async, Pydantic validation |
| Primary DB | PostgreSQL 16 | Metadata, FTS (tsvector + ts_rank_cd), users, audit |
| Vector DB | Pinecone | Managed, metadata filtering, hybrid search |
| Graph DB | Neo4j AuraDB | Citation graph, precedent tracking |
| LLM | Gemini 2.5 Pro | 1M context, best reasoning, GCP native |
| Embeddings | Gemini gemini-embedding-001 | 1536-dim (Matryoshka), free tier on GCP |
| Reranker | Cohere rerank-v4.0-pro | Native reranker API, free tier |
| Cache | Redis (Upstash) | Session, query caching, rate limiting |
| Storage | Google Cloud Storage | PDF documents |
| Deploy | Google Cloud Run | Serverless containers |

---

## Project Structure

```
smriti/
├── docs/                          # You are here — project documentation
├── frontend/                      # Next.js 15 App Router
│   ├── app/                       # Pages (search, case, chat, graph, upload)
│   ├── components/                # UI components (search, case, chat, graph, ui)
│   └── lib/                       # API client, types, utils
├── backend/                       # FastAPI Python
│   ├── app/
│   │   ├── api/routes/            # Endpoint handlers
│   │   ├── core/
│   │   │   ├── interfaces/        # Protocol contracts (plug-and-play)
│   │   │   ├── providers/         # Concrete implementations (Gemini, Pinecone, etc.)
│   │   │   ├── search/            # Hybrid search, RRF, query understanding
│   │   │   ├── ingestion/         # PDF processing, chunking, embedding
│   │   │   ├── legal/             # Indian legal patterns, courts, citations
│   │   │   └── graph/             # Citation graph operations
│   │   ├── security/              # Auth, RBAC, encryption, audit, consent
│   │   ├── models/                # SQLAlchemy ORM models
│   │   └── db/                    # Database connections
│   ├── scripts/                   # Bulk ingestion, seeding
│   ├── migrations/                # Alembic DB migrations
│   └── tests/                     # Pytest test suite
├── docker-compose.yml             # Local dev services
├── .env.example                   # Environment template
└── Makefile                       # Common commands
```

---

## Coding Conventions

### Python (Backend)
- **Style**: PEP 8, enforced by `ruff` linter + `ruff format`
- **Type hints**: Required on all function signatures. Use `typing` module.
- **Async**: All I/O-bound functions must be `async`. Use `asyncio` and `httpx`.
- **Naming**: `snake_case` for functions/variables, `PascalCase` for classes, `UPPER_SNAKE` for constants
- **Imports**: stdlib → third-party → local, separated by blank lines. Use absolute imports.
- **Models**: Pydantic `BaseModel` for request/response schemas. SQLAlchemy 2.0 style for ORM.
- **Error handling**: Raise `HTTPException` with specific status codes. Never catch bare `Exception`.
- **Validation**: Pydantic models validate ALL external input. Never trust raw user data.
- **Secrets**: Always via `os.environ` or `pydantic_settings.BaseSettings`. Never hardcode.
- **SQL**: Always use SQLAlchemy ORM or parameterized queries. Never construct raw SQL strings.
- **Files**: One class per file for large classes. Group related small functions in themed modules.

### TypeScript (Frontend)
- **Style**: ESLint + Prettier, strict TypeScript (`strict: true`)
- **Components**: Functional components only. Server Components by default, `"use client"` only when needed.
- **Naming**: `PascalCase` for components, `camelCase` for functions/variables, `kebab-case` for files
- **State**: TanStack Query for server state, `useState`/`useReducer` for local state. No global state lib unless needed.
- **API calls**: Centralized in `lib/api.ts`. Never call `fetch` directly from components.
- **Types**: Define in `lib/types.ts`. Share types between components. No `any`.

### General Rules
- **No comments on obvious code**. Comment only when the "why" isn't clear from the code itself.
- **No dead code**. Delete unused imports, variables, functions immediately.
- **No premature abstraction**. Three similar lines > one over-engineered abstraction.
- **No feature flags or backwards compatibility** for MVP.
- **Every external service behind an interface** (`core/interfaces/`). Swap implementations, not business logic.

---

## Architecture Pattern: Interfaces + Providers

This is the most important pattern in the codebase. Every external dependency has:

1. **Interface** (`core/interfaces/llm.py`): Python `Protocol` defining the contract
2. **Provider** (`core/providers/llm/gemini.py`): Concrete implementation
3. **Factory** (`config.py`): Selects provider based on env vars
4. **Injection** (`Depends(get_llm)`): FastAPI injects the right provider

To add a new LLM provider:
1. Create `core/providers/llm/openai.py` implementing `LLMProvider`
2. Add `case "openai"` to factory in `config.py`
3. Set `LLM_PROVIDER=openai` in `.env`
4. Done. Zero changes to routes, search, or ingestion code.

---

## What NOT to Do (Anti-Patterns)

1. **Never copy code from the old AnythingLLM codebase**. Reference it for domain patterns (citation regex, court names) but rewrite everything fresh in Python.
2. **Never call external services directly from routes**. Always go through an interface.
3. **Never store secrets in code or config files**. Use `.env` locally, GCP Secret Manager in production.
4. **Never construct SQL strings manually**. Use SQLAlchemy ORM or parameterized queries.
5. **Never log PII** (emails, names, passwords). Use structured logging with PII redaction.
6. **Never skip input validation**. Every route handler receives a Pydantic model, never raw `dict`.
7. **Never use `any` in TypeScript** or bare `Exception` in Python.
8. **Never add features outside current phase scope**. Check PHASE_PLAN.md.
9. **Never embed LLM prompts inline in code**. All prompts live in `PROMPT_LIBRARY.md` and `core/legal/prompts.py`.
10. **Never commit `.env` files**. Only `.env.example` with placeholder values.

---

## How to Run the Project

### Prerequisites
- Python 3.12+
- Node.js 20+
- Docker & Docker Compose
- AWS CLI (for S3 data download, no credentials needed)

### Local Development
```bash
# 1. Clone and setup
git clone <repo>
cd smriti
cp .env.example .env          # Fill in API keys

# 2. Start infrastructure
docker compose up -d           # PostgreSQL + Redis + Neo4j

# 3. Backend
cd backend
python -m venv venv
source venv/bin/activate       # or venv\Scripts\activate on Windows
pip install -r requirements.txt
alembic upgrade head           # Run migrations
uvicorn app.main:app --reload --port 8000

# 4. Frontend
cd frontend
npm install
npm run dev                    # http://localhost:3000

# 5. Ingest sample data
cd backend
python scripts/ingest_s3.py --year 2024 --limit 100
```

### Key URLs (Local Dev)
- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8000`
- API Docs (Swagger): `http://localhost:8000/docs`
- PostgreSQL: `localhost:5432`
- Redis: `localhost:6379`
- Neo4j Browser: `http://localhost:7474`

---

## Current Phase

**Phase 2: Search + Frontend (in progress)**

Phase 1 (Foundation + Ingestion) is complete — all backend code, security, DB, interfaces, providers, ingestion pipeline, and tests are built. Phase 2 search pipeline and frontend are built; currently ingesting SC judgments and validating search quality. See `PHASE_PLAN.md` for full status.

---

## Key Documents

| Document | Purpose |
|----------|---------|
| `CLAUDE.md` | This file. Read first every session. |
| `PRD.md` | What we're building and why. User stories, acceptance criteria. |
| `ARCHITECTURE.md` | System diagrams, data flow, RAG pipeline. |
| `HLD.md` | Module breakdown, service boundaries, API design. |
| `LLD.md` | DB schemas, API specs, component tree, state management. |
| `PHASE_PLAN.md` | What to build in each phase. What to ignore. |
| `LEGAL_DOMAIN.md` | Indian court system, citation formats, terminology. Your domain cheat sheet. |
| `DATA_SOURCES.md` | Where data comes from (S3 datasets, IndianKanoon), ingestion pipeline. |
| `PROMPT_LIBRARY.md` | All LLM prompts: research, extraction, analysis, chat. |
| `DECISIONS.md` | Architecture Decision Records: why we chose each technology. |
| `ENV_SETUP.md` | All env vars, API keys, local dev setup. |
| `TESTING_STRATEGY.md` | What to test, how to evaluate AI output, legal accuracy benchmarks. |
