# Smriti — Implementation Progress

**Last Updated**: 2026-03-05
**Branch**: `master`
**Latest Commit**: Phase 2 backend search pipeline

---

## Status: Phase 2 Backend COMPLETE — Frontend Starting

### Phase 1 — All Done (Audited & Committed)

| # | Module | Files | Status |
|---|--------|-------|--------|
| 1 | **Project Scaffold** | `pyproject.toml`, `docker-compose.yml`, `Dockerfile`, `.gitignore`, `.env.example`, `Makefile`, `alembic.ini`, `migrations/env.py` | DONE |
| 2 | **Interface Layer** (7 Protocols) | `core/interfaces/{llm,embedder,vector_store,graph_store,reranker,document_parser,storage}.py`, `__init__.py` | DONE |
| 3 | **Legal Domain** | `core/legal/{courts,constants,extractor,prompts}.py`, `__init__.py` | DONE |
| 4 | **Security Module** | `security/{auth,rbac,sanitizer,rate_limiter,audit,consent,encryption,exceptions}.py`, `__init__.py` | DONE |
| 5 | **Database Layer** | `models/{case,user,document,chat,audit,consent,base}.py`, `db/{postgres,redis_client}.py`, `migrations/versions/001_initial.py` | DONE |
| 6 | **Provider Implementations** | `providers/{llm/gemini,embeddings/gemini,vector/pinecone_store,graph/neo4j_store,rerankers/cohere_reranker,storage/local_storage,document_parsers/pdf_parser}.py`, `core/dependencies.py` | DONE |
| 7 | **API Endpoints** | `api/routes/{health,auth,cases,ingest}.py`, `main.py` | DONE |
| 8 | **Ingestion Pipeline** | `core/ingestion/{pdf,metadata,chunker,pipeline}.py`, `__init__.py` | DONE |
| 9 | **S3 Bulk Script** | `scripts/ingest_s3.py` | DONE |
| 10 | **Tests** | `tests/unit/{test_courts,test_extractor,test_chunker,test_auth,test_sanitizer,test_encryption,test_metadata}.py`, `tests/security/test_security.py`, `tests/conftest.py` | DONE |
| 11 | **Pre-commit hooks** | `.pre-commit-config.yaml` (ruff, mypy, detect-secrets) | DONE |
| 12 | **FTS Trigger** | `migrations/versions/001_initial.py` lines 322-347 (weighted tsvector, GIN index) | DONE |

### Phase 2 Backend — All Done (25 Tests Pass)

| # | Module | Files | Status |
|---|--------|-------|--------|
| 1 | **Search Pipeline** | `core/search/{query,fulltext,hybrid}.py`, `__init__.py` | DONE |
| 2 | **Search API** | `api/routes/search.py` (GET /search, /search/suggest, /search/facets) | DONE |
| 3 | **Cases API Enhanced** | `api/routes/cases.py` (5 endpoints: detail+sections, pdf, citations, cited-by, similar) | DONE |
| 4 | **Config Updates** | `core/config.py` (9 search settings), `main.py` (search router) | DONE |
| 5 | **Unit Tests** | `tests/unit/{test_rrf,test_query_understanding,test_fulltext}.py` (25 tests) | DONE |

### Phase 2 Backend — What Was Built

**Search Pipeline** (`core/search/`):
- `query.py` — LLM query understanding via Gemini structured JSON output. Parses raw queries into intent, entities, filters, expanded_query. Graceful fallback on LLM failure.
- `fulltext.py` — PostgreSQL FTS using `ts_rank_cd` with dynamic filter construction, `ts_headline` snippets.
- `hybrid.py` — Orchestrator: parallel vector + FTS → RRF merge (k=60) → Cohere rerank → enrich from PostgreSQL. Redis caching with SHA-256 cache keys.

**Search API** (`api/routes/search.py`):
- `GET /api/v1/search` — Full hybrid search with query params: q, court, year_from, year_to, case_type, bench_type, judge, act, page, page_size
- `GET /api/v1/search/suggest` — Auto-complete suggestions (ILIKE on case titles, Redis-cached 15min)
- `GET /api/v1/search/facets` — Distinct filter values (courts, case_types, years, bench_types), Redis-cached 15min

**Enhanced Cases API** (`api/routes/cases.py`):
- `GET /cases/{id}` — Full case with judgment sections (joined from document_chunks)
- `GET /cases/{id}/pdf` — Serve PDF from FileStorage
- `GET /cases/{id}/citations` — Cases cited by this case (Neo4j outgoing CITES)
- `GET /cases/{id}/cited-by` — Cases citing this case (Neo4j incoming CITES)
- `GET /cases/{id}/similar` — Semantically similar cases (embed ratio_decidendi → Pinecone)

### Deferred to Later

- **Phase 2 Frontend** — Next.js 15 frontend (search UI, case viewer, auth pages)
- **Bulk Ingestion Scale-Up** — Ingest 5,000+ judgments
- **Integration tests** — End-to-end search with running infrastructure
- **Structured logging** — Switch to structlog (ADR-015)

---

### Architecture Quick Reference

```
backend/
├── app/
│   ├── main.py                          # FastAPI app, CORS, exception handlers, lifespan
│   ├── api/routes/                      # REST endpoints (health, auth, cases, ingest, search)
│   ├── core/
│   │   ├── config.py                    # Pydantic Settings (all config including search)
│   │   ├── dependencies.py              # DI factories (get_llm, get_embedder, etc.)
│   │   ├── interfaces/                  # 7 Protocol classes (structural subtyping)
│   │   ├── legal/                       # Courts, citations, constants, LLM prompts
│   │   ├── search/                      # Query understanding, FTS, hybrid RRF, caching
│   │   ├── ingestion/                   # PDF→text→metadata→chunks→embed→store pipeline
│   │   └── providers/                   # Gemini, Pinecone, Neo4j, Cohere, LocalStorage
│   ├── db/                              # Async PostgreSQL + Redis connections
│   ├── models/                          # SQLAlchemy 2.0 ORM
│   └── security/                        # JWT, RBAC, encryption, sanitizer, rate limiter
├── migrations/versions/001_initial.py   # All tables, indexes, triggers
├── scripts/ingest_s3.py                 # CLI bulk ingestion from AWS Open Data
└── tests/                               # Unit + security tests (11 test files, ~105 tests)
```

### Key Technical Decisions

- **Protocols (not ABCs)** for all interfaces (ADR-001)
- **JWT HS256** — 15-min access, 7-day refresh with rotation (ADR-005)
- **RRF k=60** for hybrid search fusion (ADR-009)
- **Parallel retrieval** — asyncio.gather() for vector + FTS (ADR-009)
- **Cohere rerank-v4.0-pro** on top-20 RRF results → return top-10
- **Redis caching** — 5-min search results, 15-min facets/suggestions
- **Legal-aware chunking**: 2000 chars, 200 overlap, section-tagged
- **Gemini 3.1 Pro** via google-genai SDK for query understanding + metadata
- **gemini-embedding-001** (1536 dimensions, Matryoshka, cosine)

### Config/Env Reference

All settings in `app/core/config.py`. Key env vars:
- `JWT_SECRET_KEY`, `JWT_REFRESH_SECRET_KEY` — token signing
- `ENCRYPTION_KEY` — 64-char hex for AES-256
- `GEMINI_API_KEY`, `PINECONE_API_KEY`, `COHERE_API_KEY`
- `DATABASE_URL` — `postgresql+asyncpg://...`
- `REDIS_URL` — `redis://...`
- `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`
- Search config: `SEARCH_CACHE_TTL`, `SEARCH_RRF_K`, `SEARCH_VECTOR_TOP_K`, etc.

### How to Continue

1. **Set up environment**: `cd backend && python -m venv .venv && .venv\Scripts\activate && pip install -e ".[dev]"`
2. **Start infra**: `docker-compose up -d` (PostgreSQL, Redis, Neo4j)
3. **Run migrations**: `cd backend && alembic upgrade head`
4. **Run tests**: `cd backend && pytest tests/ -v`
5. **Start dev server**: `uvicorn app.main:app --reload --port 8000`
6. **Check API docs**: `http://localhost:8000/docs`
7. **Phase 2 Frontend** (per PHASE_PLAN.md §2.4-2.5): Next.js 15, search UI, case viewer

### Commit History

```
[PENDING] Add Phase 2 backend: search pipeline, search API, enhanced cases API
922a5d6 Fix all Phase 1 audit issues for pristine condition
b5ecf1a Add PROGRESS.md for cross-session handoff and context tracking
409b09d Add comprehensive unit and security tests for Phase 1 modules
b36541c Add ingestion pipeline orchestrator, S3 bulk script, and module exports
93f7e0d Add legal domain, security, and ingestion modules from worktree agents
ef03ec4 Merge branch 'worktree-agent-a692836a' (providers)
fb1fa10 Merge branch 'worktree-agent-ae05ac06' (database)
0bd9595 Add API endpoints: health, auth, cases, ingest + main app
851074e Merge branch 'worktree-agent-a7e10139' (security exceptions)
f69412f Merge branch 'worktree-agent-a35cc5d5' (legal constants/courts)
404e660 Add Interface Layer - 7 Protocol classes
acc5317 Phase 1: Project scaffold - directory structure, configs, Docker, Makefile
```
