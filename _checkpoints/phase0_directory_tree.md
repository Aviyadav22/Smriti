# Phase 0: Directory Scan & Project Structure
**Generated:** 2026-04-03

## Top-Level Directory Structure

```
Smriti/
├── .claude/              # Claude Code settings
├── .github/workflows/    # CI/CD (ci.yml)
├── .worktrees/           # Git worktrees for isolated dev
├── backend/              # FastAPI Python backend (main service)
├── data/                 # Local data storage (PDFs, parquet, statutes)
├── docs/                 # Project documentation (plans, architecture, decisions)
├── frontend/             # Next.js TypeScript frontend
├── ingestion/            # Standalone ingestion pipeline scripts
├── nginx/                # Nginx reverse proxy config
├── scripts/              # Top-level utility scripts
├── smriti-storybook/     # Interactive onboarding storybook (Vite + React)
├── docker-compose.yml    # Local development docker setup
├── docker-compose.prod.yml # Production docker setup
├── Makefile              # Build/run shortcuts
├── .env.prod.example     # Production env template
├── .pre-commit-config.yaml # Pre-commit hooks (ruff, etc.)
└── .mcp.json             # MCP server configuration
```

## Identified Services

1. **Backend (FastAPI)** — `./backend/` — Core API server: auth, search, RAG chat, agents, ingestion, graph, analytics
2. **Frontend (Next.js)** — `./frontend/` — Web UI: search, case viewer, agent interfaces, chat, document management
3. **Ingestion Pipeline** — `./ingestion/` + `./backend/scripts/` — PDF processing, metadata extraction, embedding, vector/graph storage
4. **Storybook** — `./smriti-storybook/` — Interactive project explainer/onboarding tool (Vite + React + Three.js)
5. **Nginx** — `./nginx/` — Reverse proxy for production deployment
6. **CI/CD** — `.github/workflows/ci.yml` — GitHub Actions pipeline

## Tech Stack

- **Language (Backend):** Python 3.12
- **Language (Frontend):** TypeScript
- **Backend Framework:** FastAPI
- **Frontend Framework:** Next.js 16.x (App Router)
- **CSS:** Tailwind CSS + shadcn/ui
- **Primary Database:** PostgreSQL 16 (metadata, FTS via tsvector, pg_trgm)
- **Vector Database:** Pinecone (1536-dim, Gemini embeddings)
- **Graph Database:** Neo4j AuraDB (citation graph)
- **LLM (Reasoning):** Gemini 3.1 Pro Preview
- **LLM (Fast):** Gemini 3 Flash Preview
- **Embedding Model:** gemini-embedding-2-preview (1536 dim)
- **Reranker:** Cohere rerank-v4.0-pro
- **TTS:** Sarvam AI / Google Cloud TTS
- **Agent Framework:** LangGraph
- **Cache:** Redis (Upstash in prod)
- **Object Storage:** Google Cloud Storage (prod), local (dev)
- **Deploy:** Google Cloud Run + Docker
- **ORM/Migrations:** SQLAlchemy + Alembic (38 migrations)
- **Testing:** pytest (backend ~2185 tests), vitest (frontend ~311 tests)
- **Linting:** ruff (Python), ESLint (TypeScript)
- **i18n:** next-intl (Hindi support)
- **Markdown:** react-markdown + remark-gfm

## Config Files Found

| File | Type | Purpose |
|------|------|---------|
| `.env.prod.example` | env | Production environment template |
| `.github/workflows/ci.yml` | CI | GitHub Actions pipeline |
| `.mcp.json` | config | MCP server configuration |
| `.pre-commit-config.yaml` | config | Pre-commit hooks (ruff) |
| `docker-compose.yml` | docker | Local dev services |
| `docker-compose.prod.yml` | docker | Production services |
| `Makefile` | build | Build/run shortcuts |
| `backend/.env.example` | env | Backend env template |
| `backend/.env.prod.example` | env | Backend prod env template |
| `backend/alembic.ini` | config | Alembic migration config |
| `backend/pyproject.toml` | config | Python project config (ruff, pytest) |
| `backend/requirements.txt` | deps | Python dependencies |
| `frontend/package.json` | deps | Node.js dependencies |
| `frontend/next.config.ts` | config | Next.js configuration |
| `frontend/tsconfig.json` | config | TypeScript configuration |
| `frontend/tailwind.config.ts` | config | Tailwind CSS configuration |
| `frontend/vitest.config.ts` | config | Vitest test configuration |
| `frontend/postcss.config.mjs` | config | PostCSS configuration |
| `ingestion/env_template` | env | Ingestion environment template |

## Backend Source Files (Non-Test)

### API Routes (16 files)
- `admin_corrections.py` — Admin metadata correction interface
- `admin_review.py` — Admin review queue
- `agents.py` — Agent endpoints (research, case-prep, drafting, strategy)
- `audio.py` — TTS audio generation
- `auth.py` — Authentication (register, login, refresh, profile)
- `cases.py` — Case CRUD, search, timeline
- `chat.py` — RAG chat endpoints
- `counsel.py` — Counsel/lawyer analytics
- `data_quality.py` — Data quality metrics
- `documents.py` — Document upload/management
- `dpdp.py` — DPDP compliance (data protection)
- `graph.py` — Citation graph endpoints
- `health.py` — Health check
- `ingest.py` — Ingestion trigger endpoints
- `judges.py` — Judge analytics/profiles
- `preferences.py` — User preferences
- `search.py` — Hybrid search endpoint
- `sharing.py` — Shared memo links

### Core Modules
- **Agents (12 files):** LangGraph agents — research, case_prep, drafting, strategy, follow_up + node implementations
- **Analysis (2 files):** Document analysis, precedent mapping
- **Analytics (3 files):** Counsel analytics, judge analytics, judge prediction
- **Chat (1 file):** RAG chat implementation
- **Drafting (6 files):** Court profiles, document parser, export, hindi glossary, PDF compliance, templates
- **Graph (1 file):** Citation graph traversal
- **Ingestion (8 files):** PDF extraction, chunking, metadata, pipeline, contextual embeddings, anonymizer, rate limiter, section summarizer
- **Interfaces (11 files):** Protocol classes — embedder, llm, vector_store, graph_store, reranker, storage, translator, tts, web_search, document_parser, external_doc
- **Legal (8 files):** Constants, extractor (citations/statutes), prompts, courts, amendment service, limitation, precedent strength, treatment, statute enrichment, court fees
- **Providers (14 files):** Concrete implementations — Gemini LLM, Gemini embeddings, Pinecone, Neo4j, PGVector, Cohere reranker, GCS/local storage, Sarvam TTS, Gemini translator, Tavily web search, PDF parser, IndianKanoon
- **Search (4 files):** Fulltext search, hybrid search, query understanding, semantic cache
- **Security (7 files):** Auth (JWT), RBAC, rate limiter, sanitizer, encryption, audit, consent, exceptions
- **Models (14 files):** SQLAlchemy models — case, user, document, chat, statute, agent_session, agent_execution, audit, consent, etc.
- **DB (2 files):** PostgreSQL connection, Redis client
- **Tasks (2 files):** Background tasks — audio generation, document processing
- **Migrations (38 files):** Alembic migrations 001-038

### Scripts (30+ files)
Ingestion scripts, backfill scripts, audit scripts, batch processing, quality evaluation, etc.

## Frontend Source Files

### Pages (App Router — 22 routes)
- `/` — Home/landing page
- `/login`, `/register` — Authentication
- `/search` — Hybrid search
- `/case/[id]` — Case detail view
- `/chat` — RAG chat interface
- `/agents` — Agent hub
- `/agents/research` — Research agent
- `/agents/case-prep` — Case preparation agent
- `/agents/drafting` — Legal drafting agent
- `/agents/strategy` — Strategy agent
- `/agents/history` — Agent session history
- `/graph` — Citation graph visualization
- `/judges`, `/judge/[name]` — Judge profiles/analytics
- `/judges/compare` — Judge comparison
- `/counsel`, `/counsel/[name]` — Counsel profiles
- `/courts` — Court information
- `/documents`, `/documents/[id]` — Document management
- `/upload` — Document upload
- `/shared/[token]` — Shared memo viewer
- `/about`, `/privacy`, `/terms` — Static pages

### Components (45+ files)
UI components: agent interfaces, audio player, case timeline, confidence meter, search components, graph utils, etc.

### Libraries (5 files)
- `api.ts` — API client (fetch wrapper)
- `auth-context.tsx` — Authentication context provider
- `graph-utils.ts` — Citation graph utilities
- `types.ts` — TypeScript type definitions
- `utils.ts` — Utility functions

## Storybook (Interactive Onboarding)
Separate Vite + React app with 11 chapters explaining Smriti's architecture through interactive 3D visualizations (Three.js), quizzes, and animations.

## File Count by Extension (Source Files Only, Excluding node_modules/.git/venv/worktrees)

| Extension | Count | Purpose |
|-----------|-------|---------|
| .py | ~380 | Python backend + scripts + tests |
| .tsx | ~245 | React TypeScript components |
| .ts | ~42 | TypeScript utilities/config |
| .json | ~146 | Config, package manifests, data |
| .md | ~144 | Documentation |
| .css | ~3 | Stylesheets |
| .yml/.yaml | ~10 | CI/CD, Docker, config |
| .sql | ~2 | SQL scripts |
| .sh | ~7 | Shell scripts |
| .toml | ~3 | Python project config |

## Data Directory
- `data/statutes/` — JSON statute files for ingestion
- `data/cases/` — Downloaded case PDFs
- `data/parquet/` — Parquet metadata from S3 dataset
