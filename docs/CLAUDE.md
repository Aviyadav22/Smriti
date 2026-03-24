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
| LLM | Gemini 3.1 Pro Preview | 1M context, best reasoning, GCP native |
| Embeddings | Gemini gemini-embedding-2-preview | 1536-dim, task-type-aware (RETRIEVAL_DOCUMENT/RETRIEVAL_QUERY/SEMANTIC_SIMILARITY), 8K context |
| Reranker | Cohere rerank-v4.0-pro | Native reranker API, free tier |
| Agent Framework | LangGraph (StateGraph) | Graph-based agent orchestration, HITL checkpoints |
| Cache | Redis (Upstash) | Session, query caching, rate limiting |
| Storage | Google Cloud Storage | PDF documents |
| Background Jobs | Celery + Redis (broker on DB 1) | Async document processing, audio generation |
| TTS | Sarvam AI (22 Indian languages) / MockTTS (dev) | Audio digest generation |
| Deploy | Google Cloud Run | Serverless containers |

---

## Project Structure

```
smriti/
├── docs/                          # Project documentation
├── frontend/                      # Next.js 15 App Router
│   ├── app/                       # Pages: search, case/[id], chat, graph, agents/*, register, login, documents
│   ├── components/                # UI: header, footer, audio-player, file-upload, error-boundary, agent-checkpoint-prompt, ui/
│   └── lib/                       # API client, types, utils
├── backend/                       # FastAPI Python
│   ├── app/
│   │   ├── api/routes/            # 15 route modules, ~65 endpoints
│   │   │   ├── auth.py            # Register, login, refresh, logout, delete account
│   │   │   ├── search.py          # Hybrid search, suggest, facets
│   │   │   ├── cases.py           # Case detail, summary, PDF, citations, cited-by, similar
│   │   │   ├── chat.py            # SSE chat sessions, message history
│   │   │   ├── agents.py          # Agent run (SSE), executions, resume, drafting templates/export
│   │   │   ├── graph.py           # Neighborhood, chain, authorities, stats
│   │   │   ├── documents.py       # Upload, list, detail, delete, research memo
│   │   │   ├── audio.py           # Generate, status, stream audio digests
│   │   │   ├── ingest.py          # Upload, status, dashboard, review queue, approve/retry
│   │   │   ├── judges.py          # List, profile, cases, compare, court stats
│   │   │   ├── dpdp.py            # Data summary, erasure, consent withdraw/status
│   │   │   ├── health.py          # Dependency health checks
│   │   │   ├── data_quality.py    # Field population metrics (admin)
│   │   │   ├── admin_corrections.py # Metadata corrections with audit trail (admin)
│   │   │   └── admin_review.py    # Review queue, approve/reject cases (admin)
│   │   ├── core/
│   │   │   ├── interfaces/        # 11 Protocol contracts (LLM, embedder, vector, graph, reranker, storage, translator, TTS, doc parser, web search, external doc)
│   │   │   ├── providers/         # 15 implementations (Gemini, Pinecone, PgVector, Neo4j, PgGraph, Cohere, GCS, Local, Sarvam, MockTTS, Tavily, IndianKanoon, etc.)
│   │   │   ├── search/            # Hybrid search (RRF), fulltext (FTS), query understanding
│   │   │   ├── ingestion/         # PDF extraction, chunking, metadata, citation extraction, pipeline
│   │   │   ├── legal/             # Courts, citations, acts, prompts, precedent strength, treatment
│   │   │   ├── graph/             # Citation graph traversal (neighborhood, chain, authorities)
│   │   │   ├── analysis/          # Document analyzer, precedent mapper
│   │   │   ├── analytics/         # Judge analytics (profile, disposition, bench composition)
│   │   │   ├── chat/              # RAG pipeline (search → rerank → context → generate → verify)
│   │   │   ├── agents/            # 4 agent types: research, case_prep, strategy, drafting
│   │   │   │   └── nodes/         # Agent node functions (40 nodes total across 4 graphs)
│   │   │   ├── drafting/          # Document templates, DOCX/PDF export
│   │   │   └── middleware.py      # RequestID middleware, request logging
│   │   ├── tasks/                 # Celery: document analysis (6-step), audio generation
│   │   ├── security/              # Auth (JWT), RBAC, rate limiter, encryption, audit, consent, sanitizer
│   │   ├── models/                # 14 SQLAlchemy models (User, Case, Statute, ChatSession, CaseStatuteInterpretation, etc.)
│   │   └── db/                    # Database connections (PostgreSQL, Redis)
│   ├── scripts/                   # ingest_s3 (queue-based workers, circuit breaker), populate_neo4j, ingest_statutes, backfill_contextual_embeddings, build_citation_communities, benchmark
│   ├── migrations/                # 35 Alembic migrations (001-035)
│   └── tests/                     # ~2185 unit + integration + quality tests
├── docker-compose.yml             # Local dev services
└── .env.example                   # Environment template
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
- **State**: `useState`/`useReducer` for local state. No global state lib unless needed. (Note: TanStack Query is not currently used; frontend uses plain fetch via `lib/api.ts`.)
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
1. **Never call external services directly from routes**. Always go through an interface.
2. **Never store secrets in code or config files**. Use `.env` locally, GCP Secret Manager in production.
3. **Never construct SQL strings manually**. Use SQLAlchemy ORM or parameterized queries.
4. **Never log PII** (emails, names, passwords). Use structured logging with PII redaction.
5. **Never skip input validation**. Every route handler receives a Pydantic model, never raw `dict`.
6. **Never use `any` in TypeScript** or bare `Exception` in Python.
7. **Never add features outside current phase scope**. Check PHASE_PLAN.md.
8. **Never embed LLM prompts inline in code**. All prompts live in `PROMPT_LIBRARY.md` and `core/legal/prompts.py`.
9. **Never commit `.env` files**. Only `.env.example` with placeholder values.

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

# 6. Start Celery worker (for document processing & audio generation)
cd backend
celery -A app.worker:celery_app worker --loglevel=info
```

### Key URLs (Local Dev)
- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8000`
- API Docs (Swagger): `http://localhost:8000/docs`
- PostgreSQL: `localhost:5432`
- Redis: `localhost:6379`
- Neo4j Browser: `http://localhost:7474`
- Celery Flower (optional): `http://localhost:5555`

---

## Current Phase

**Phases 1-8 COMPLETE + Research Agent V2/V3 + 10x Audit Fix + Embedding Upgrade + Ingestion V3 (in progress)**

All core features built and tested: hybrid search (FTS + multi-vector + RRF + Cohere reranking), citation graph (Neo4j), RAG chat with SSE streaming and citation verification, 4 LangGraph agents (Research V3, Case Prep, Strategy, Drafting) with HITL checkpoints, judge analytics, audio digests (Sarvam AI), document upload + analysis, DPDP Act compliance, admin tools. ~2185 backend tests, ~311 frontend tests. 2,932 statute sections ingested from 8 acts. Database at migration 035 with 60+ columns. Hindi support partial (next-intl setup, language toggle, 100+ term glossary).

**Key completed milestones (March 2026):**
- **Research Agent V3**: 5-stage sequential-reactive pipeline (Understand → Route → Investigate → Challenge → Synthesize), 4 new nodes (statute_lookup, element_decomposition, adversarial_search, temporal_validation)
- **10x Audit Fix**: All CRITICAL + HIGH findings fixed across research agent quality
- **Gemini embedding-2-preview upgrade**: Task-type-aware embeddings (RETRIEVAL_DOCUMENT/RETRIEVAL_QUERY/SEMANTIC_SIMILARITY), 8K context
- **Multi-vector Pinecone**: 6 vector types (chunk, proposition, ratio, headnote, section, statute) with 1.5x RRF boost for proposition/ratio
- **Ingestion V3**: Proposition extraction, statute interpretation, fact pattern summaries, legal signal scoring
- **Frontend hardening**: JWT proactive refresh, session expiry event bus, stream disconnect detection, account lockout (10 attempts / 5 min)
- **Production readiness audit**: Security headers, fail-closed auth, ILIKE escaping, SSE session isolation, error sanitization, PII redaction, CSP

**Chunking**: Standard 2000-char / 200-char overlap; dense sections (ANALYSIS, RATIO, ORDER, DISSENT, CONCURRENCE) use 1800-char / 400-char overlap with legal signal scoring.

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
| `SECURITY_AUDIT.md` | OWASP Top 10 checklist, DPDP compliance, security headers. |
| `FRONTEND_ARCHITECTURE.md` | Frontend page inventory, component architecture, API patterns. |
| `STRATEGY.md` | Market analysis, competitive landscape, go-to-market. |
| `PHASE_9_SCALABILITY_AUDIT.md` | Production scalability findings, remediation priorities. |
