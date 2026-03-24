# Smriti -- Implementation Progress

**Last Updated**: 2026-03-12
**Branch**: `master`
**Status**: Phases 1-8 COMPLETE -- Phase 9 (Scalability) starting

---

## Current Metrics

| Metric | Count |
|--------|-------|
| Backend unit tests | 1,443 |
| Backend integration tests | 31 |
| Frontend tests | 298 |
| Cases loaded | 796 |
| PostgreSQL tables | 15 |
| Cases table columns | 52 |
| Alembic migrations | 14 (001-014) |
| API routes | 9 route modules |
| Frontend pages | 20+ routes |
| LangGraph agents | 4 (Research, Case Prep, Strategy, Drafting) |

---

## Phase 1: Foundation + Ingestion -- COMPLETE

**Delivered:**
- FastAPI project scaffold with Docker, Makefile, pre-commit hooks (ruff, mypy, detect-secrets)
- 7 Protocol interfaces: LLM, Embedder, VectorStore, GraphStore, Reranker, DocumentParser, Storage
- Provider implementations: Gemini LLM, Gemini Embedder, Pinecone, Neo4j, Cohere, LocalStorage
- Security module: JWT auth (15-min access, 7-day refresh rotation), RBAC (admin/researcher/viewer), AES-256-GCM encryption, input sanitizer, rate limiter, audit logger, DPDP consent recording
- Database layer: SQLAlchemy 2.0 async models, Alembic migrations, PostgreSQL FTS (weighted tsvector, GIN index)
- Ingestion pipeline: PDF extraction (pdfplumber + OCR fallback), LLM metadata extraction (Gemini structured output), regex validation, legal-aware chunking (2000-char, 200-overlap, section-tagged)
- Legal domain: Indian citation regex (5 formats), acts/sections parser, court normalization (SC + 25 HCs + tribunals)
- S3 bulk ingestion script with resume support, rate limiting, configurable concurrency
- API endpoints: auth (register, login, refresh), ingest (upload), cases (detail), health check

---

## Phase 2: Search + Frontend -- COMPLETE

**Delivered:**
- Search pipeline: LLM query understanding (Gemini structured JSON), PostgreSQL FTS (ts_rank_cd), hybrid orchestrator with parallel vector + FTS retrieval
- RRF fusion (k=60) with Cohere reranking (top-20 to top-10), Redis caching (5-min TTL)
- Search API: `GET /search`, `/search/suggest`, `/search/facets` with full filtering
- Enhanced Cases API: case detail with sections, PDF serving, citations, cited-by, similar cases
- Next.js 15 frontend: App Router, TypeScript strict, Tailwind CSS, shadcn/ui
- Frontend pages: landing, search results with filter sidebar, case detail with section tabs, auth (login, register), layout with nav
- Typed API client (`lib/api.ts`) with JWT handling, CSP headers, CORS config

---

## Phase 3: Intelligence + Graph Visualization -- COMPLETE

**Delivered:**
- RAG chat: streaming SSE endpoint, citation grounding (every claim linked to source chunks), encrypted chat history (AES-256-GCM), legal research persona prompt
- Chat API: create session, send message (streaming), list sessions, get history, delete session
- Citation graph API: 1-hop neighborhood, citation chain (max depth 3), authority ranking, graph stats
- Neo4j Cypher queries for forward/backward citations with relationship types (CITES, OVERRULES, AFFIRMS, DISTINGUISHES)
- Chat UI: session sidebar, streaming response display, inline clickable citations, sources panel with relevance scores
- Graph UI: interactive force-directed visualization (react-force-graph-2d), color-coded edges, node click detail panel, zoom/pan/depth controls
- Enhanced case viewer: section-tabbed view, mini citation graph, Cited Cases and Cited By tabs

---

## Phase 4: Judge Analytics -- COMPLETE

**Delivered:**
- Judge analytics API: judge listing with case counts, judge profiles (cases authored by year, disposal patterns, bench combinations, most-cited judgments, acts/sections frequency), judge comparison (2-3 judges), court-level statistics
- Redis caching for judge stats (1-hour TTL)
- Judge directory page, judge profile page (disposal pie chart, cases-per-year bar chart, bench combinations, top cited judgments), judge comparison page, court statistics page
- Clickable judge names from case detail pages
- Data validation against existing ~740 cases

---

## Phase 5: Document Upload + Audio Digests -- COMPLETE

**Delivered:**
- Document upload pipeline: PDF upload (max 50MB), background processing via Celery (text extraction, issue identification, per-issue precedent search, counter-argument detection, research memo generation)
- Status tracking: pending, extracting, analyzing, searching, generating, complete, failed
- Document privacy (row-level security per user)
- Upload UI: drag-and-drop, step-by-step processing status, analysis results with per-issue precedents
- Audio digest pipeline: case summary generation (Gemini Pro), TTS via Sarvam AI (22 Indian languages) with Google Cloud TTS fallback, MP3 storage, caching
- Audio API: stream/download digest, check status, trigger async generation
- Audio player: play/pause, progress bar, playback speed (0.5x-2x), download, language selector (EN/HI)

---

## Phase 6: Agent Framework + Research and Case Prep Agents -- COMPLETE

**Delivered:**
- LangGraph StateGraph integration: graph-based workflows, conditional routing, parallel node execution, human-in-the-loop via interrupt() + Command(resume=...), MemorySaver checkpointing (AsyncPostgresSaver for prod)
- Agent state schemas (TypedDict with Annotated reducers)
- AgentExecution model (PostgreSQL): status tracking, JSONB input/result, thread_id for checkpointing
- Multi-model routing: Gemini Pro for reasoning, Gemini Flash for classification
- Agent API (5 endpoints): run (SSE streaming), status, list executions, resume at checkpoint, cancel
- 13 agent-specific LLM prompts with structured output schemas
- **Research Agent** (10 nodes): classify, decompose, checkpoint_plan, parallel_search, gather, contradictions, checkpoint_findings, synthesize, verify, checkpoint_memo -- 3 HITL checkpoints, decompose into 3-7 sub-queries, contradiction detection, confidence scoring
- **Case Prep Agent** (9 nodes): load_analysis, prioritize, checkpoint_issues, deep_search, argument_order, checkpoint_strategy, strategy_memo, verify, checkpoint_memo -- builds on DocumentAnalysis, issue prioritization, 2-hop Neo4j traversal, counter-argument matrix
- Agent UI: hub page with cards, research workspace, case prep workspace, execution history page
- 4 shared components: AgentStepTimeline, AgentCheckpointPrompt, AgentMemoViewer, AgentHubCard

---

## Phase 6.5: Quality Excellence (Sprint) -- COMPLETE

**Delivered:**
- Weighted RRF + search strategy routing (exact citation, topical, filtered)
- RAG context grounding fix (LLM now sees case text chunks)
- Enriched agent context with ratio_decidendi and bench_type
- Prompt hardening: anti-sycophancy, bench-aware, legal disclaimers
- Precedent strength classification (binding / persuasive / distinguished / overruled)
- Confidence scoring overhaul (grounded in evidence quality)
- Citation equivalence model + migration (AIR, SCC, SCR cross-format matching)
- Case sections model + migration (Facts, Issues, Arguments, Holdings, Reasoning, Order)
- Section-aware search backend
- Frontend components: PrecedentBadge, BenchStrength, EquivalentCitations, SectionFilter, LegalDisclaimer, ConfidenceMeter

---

## Phase 7: Strategy Agent + Drafting Agent + Hindi -- COMPLETE

**Delivered:**
- **Strategy Agent**: case strength assessment (strong/moderate/weak), recommended legal arguments ordered by predicted effectiveness, key precedents with relevance explanations, anticipated counter-arguments and rebuttals, judge-specific considerations, procedural strategy suggestions
- **Drafting Agent**: generates 6 document types (bail applications, writ petitions, written statements, legal notices, appeals, interim applications), grounded in precedents and statutory provisions, citation verification against DB, template system
- **Hindi support (partial)**: next-intl setup, language toggle (EN/HI) in header, Hindi legal terminology glossary (100+ terms in Devanagari)
- Hindi translations for UI strings: in progress
- Strategy and drafting agent UI pages

---

## Phase 7.5: Codebase Audit v2 (Sprint) -- COMPLETE

**Delivered:**
- IRAC enforcement in agent prompts (Issue-Rule-Application-Conclusion structure)
- Legal disclaimers on all AI-generated output (agents, chat, documents)
- Semantic citation verification (holding accuracy checks against stored ratio_decidendi)
- Treatment-strength fusion for precedent classification
- Expanded statute mappings: IPC-to-BNS, CrPC-to-BNSS, IEA-to-BSA (bidirectional)
- Hindi legal terminology glossary integrated into constants module
- Hindi prompt suffix for agent system prompts (apply_language_suffix)
- Hardened prompt injection detection patterns
- Input sanitization and retry logic improvements

---

## Phase 8: Production Hardening + Ingestion Overhaul -- COMPLETE

**Delivered:**
- DPDP Act compliance: consent flow, right to erasure, data retention policies
- Enterprise readiness improvements (migration 013)
- Ingestion pipeline overhaul:
  - PDF extraction: NFKC normalization, zero-width char removal, header/footer dedup, per-page OCR fallback, smart page joining
  - Metadata: 16-rule system prompt, few-shot examples, head+tail truncation (30K+20K), 4 new fields (case_number, is_reportable, headnotes, outcome_summary), judge name parsing, case_type normalization (27 mappings)
  - Chunker: heading-position detection, sentence-boundary breaks, DISSENT/CONCURRENCE sections, cross-type proximity dedup
  - Extractor: neutral citations (YYYY:INSC:NNNN), SCC sub-reporters, MANU/JT/HC reporters, 42 short act names, plural section parsing, Order/Rule patterns
  - Pipeline: stale vector cleanup, regex acts/citations supplementation, enriched Pinecone metadata, enriched Neo4j nodes, batch size 100
  - Ingestion script: queue-based workers, circuit breaker (10 failures), graceful shutdown, download retries, ETA logging
- Migrations 009-014: ingestion improvements, weighted FTS, legal completeness, search excellence, enterprise readiness, trigger/constraint fixes
- Data quality dashboard and benchmark script
- Admin routes

---

## Database State

| Item | Detail |
|------|--------|
| **Cases loaded** | 796 Supreme Court judgments |
| **Tables** | 15 (cases, users, documents, chat_sessions, chat_messages, audit_logs, consent_records, document_chunks, citation_equivalents, case_sections, agent_executions, and others) |
| **Cases table columns** | 52 (including case_number, is_reportable, headnotes, outcome_summary, ingestion_status) |
| **Migrations** | 14 (001_initial through 014_fix_triggers_and_constraints) |
| **PostgreSQL** | Supabase (PostgreSQL 16), FTS via weighted tsvector with GIN index |
| **Pinecone** | 1536-dim vectors (gemini-embedding-2-preview) |
| **Neo4j** | Citation graph with CITES, OVERRULES, AFFIRMS, DISTINGUISHES edges |

---

## Phase 9: Scalability (Starting)

Based on the [Phase 9 Scalability Audit](docs/PHASE_9_SCALABILITY_AUDIT.md), key items:

**Critical (blocks production launch):**
- Rotate exposed secrets, move to Cloud Run Secret Manager
- Replace in-memory agent checkpointers with AsyncPostgresSaver for horizontal scaling
- Upgrade Supabase from free tier (3 connections) to Starter for proper connection pooling
- Fix Dockerfile worker count for Cloud Run scaling
- Consolidate Redis clients, add connection limits and timeouts
- Upgrade Upstash Redis from free tier (10k commands/day)

**High priority:**
- Distributed rate limiting (remove threading.Lock, use asyncio.Lock)
- Connection pooling configuration
- 50K case bulk ingestion (pipeline is production-ready, data source has 35K SC judgments)

**Medium priority:**
- Monitoring and observability (structured logging, metrics dashboard)
- Load testing (target: 50 concurrent users, <2s search, <5s agent first token)
- Frontend performance (code splitting, prefetching)

---

## Key Technical Decisions

- **Protocols (not ABCs)** for all interfaces (ADR-001)
- **JWT HS256** -- 15-min access, 7-day refresh with rotation (ADR-005)
- **RRF k=60** for hybrid search fusion (ADR-009)
- **Parallel retrieval** -- asyncio.gather() for vector + FTS (ADR-009)
- **Cohere rerank-v4.0-pro** on top-20 RRF results, return top-10
- **LangGraph StateGraph** for agent orchestration with interrupt() for HITL
- **Gemini 2.5 Pro** for reasoning, **Gemini 2.5 Flash** for classification/ingestion
- **Tenacity retry** on all external providers (exponential backoff, 2-60s, 5 attempts)
- **Legal-aware chunking**: 2000 chars, 200 overlap, section-tagged, paragraph-tracked

---

## Config/Env Reference

All settings in `app/core/config.py`. Key env vars:
- `JWT_SECRET_KEY`, `JWT_REFRESH_SECRET_KEY` -- token signing
- `ENCRYPTION_KEY` -- 64-char hex for AES-256
- `GEMINI_API_KEY`, `PINECONE_API_KEY`, `COHERE_API_KEY`
- `DATABASE_URL` -- `postgresql+asyncpg://...`
- `REDIS_URL` -- `redis://...`
- `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`
- `SARVAM_API_KEY` -- TTS audio generation
- Search config: `SEARCH_CACHE_TTL`, `SEARCH_RRF_K`, `SEARCH_VECTOR_TOP_K`, etc.

---

## How to Continue

1. **Set up environment**: `cd backend && python -m venv .venv && .venv\Scripts\activate && pip install -r requirements.txt`
2. **Start infra**: `docker compose up -d` (PostgreSQL, Redis, Neo4j)
3. **Run migrations**: `cd backend && alembic upgrade head`
4. **Run backend tests**: `cd backend && pytest tests/ -v`
5. **Run frontend tests**: `cd frontend && npm test`
6. **Start dev server**: `uvicorn app.main:app --reload --port 8000`
7. **Start Celery worker**: `celery -A app.worker:celery_app worker --loglevel=info`
8. **Start frontend**: `cd frontend && npm run dev`
9. **Check API docs**: `http://localhost:8000/docs`
10. **Begin Phase 9**: See [PHASE_9_SCALABILITY_AUDIT.md](docs/PHASE_9_SCALABILITY_AUDIT.md)
