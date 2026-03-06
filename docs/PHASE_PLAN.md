# Smriti — Phased Build Plan

---

## Overview

Four phases, each delivering a usable increment. Each phase builds on the previous. Target: 8 weeks to production MVP.

**Guiding Principles:**
- Each phase ends with a deployable artifact
- Security is built in from Phase 1, not bolted on later
- Interfaces (Protocols) are defined first, implementations follow
- Test as you build — no "testing phase" at the end
- Keep scope tight — the "NOT building" list matters as much as the build list

---

## Phase 1: Foundation + Ingestion (Week 1–2)

### Goal
Backend scaffold with security, database, ingestion pipeline. Ingest first 1,000 SC judgments. No frontend yet — test via API.

### Deliverables

#### 1.1 Project Scaffold
- [x] FastAPI project with app router structure
- [x] `pyproject.toml` with all dependencies (pinned versions)
- [x] `Dockerfile` for backend (multi-stage, slim Python 3.12)
- [x] `docker-compose.yml` for local dev: PostgreSQL 16, Redis 7, Neo4j 5
- [x] `.env.example` with all config variables documented
- [x] `.gitignore` (secrets, venvs, __pycache__, .env, data/)
- [x] `Makefile` with common commands (dev, test, lint, migrate, ingest)
- [x] ruff + mypy configuration
- [x] Pre-commit hooks (ruff, mypy, secrets detection)

#### 1.2 Interface Layer (Protocols)
- [x] `core/interfaces/llm.py` — LLMProvider Protocol
- [x] `core/interfaces/embedder.py` — EmbeddingProvider Protocol
- [x] `core/interfaces/vector_store.py` — VectorStore Protocol
- [x] `core/interfaces/graph_store.py` — GraphStore Protocol
- [x] `core/interfaces/reranker.py` — Reranker Protocol
- [x] `core/interfaces/document_parser.py` — DocumentParser Protocol
- [x] `core/interfaces/storage.py` — FileStorage Protocol

#### 1.3 Security Module
- [x] `security/auth.py` — JWT access (15-min) + refresh tokens (7-day, rotated)
- [x] `security/auth.py` — bcrypt password hashing (cost factor 12)
- [x] `security/rbac.py` — Role-based access: admin, researcher, viewer
- [x] `security/sanitizer.py` — Input sanitization (HTML entities, SQL chars, LLM prompt injection markers)
- [x] `security/rate_limiter.py` — Redis-backed per-user + per-IP rate limiting
- [x] `security/audit.py` — Audit log middleware (every API call: user, IP, endpoint, timestamp, response_code)
- [x] `security/consent.py` — DPDP Act consent recording (timestamped, versioned)
- [x] `security/encryption.py` — AES-256-GCM field-level encryption for PII

#### 1.4 Database Layer
- [x] SQLAlchemy 2.0 async models: cases, users, documents, audit_logs, consent_records, chat_sessions, chat_messages
- [x] Alembic migration: `001_initial.py` — all tables, indexes, triggers
- [x] PostgreSQL FTS setup: weighted tsvector trigger on cases table
- [x] `db/postgres.py` — async connection pool (SSL-only in production)
- [x] `db/redis_client.py` — Upstash-compatible Redis client

#### 1.5 Provider Implementations (Phase 1)
- [x] `providers/llm/gemini.py` — GeminiLLM: generate, generate_structured, stream
- [x] `providers/embeddings/gemini.py` — GeminiEmbedder: embed_text, embed_batch
- [x] `providers/vector/pinecone.py` — PineconeStore: upsert, search, delete
- [x] `providers/graph/neo4j.py` — Neo4jGraph: create_node, create_edge, query
- [x] `providers/storage/local.py` — LocalStorage: store, retrieve, delete (dev)
- [x] Dependency injection setup in `config.py` using FastAPI Depends()

#### 1.6 Ingestion Pipeline
- [x] `core/ingestion/pdf.py` — PDF text extraction (pdfplumber + Tesseract OCR fallback)
- [x] `core/ingestion/metadata.py` — LLM-based metadata extraction (Gemini structured JSON output)
- [x] `core/ingestion/metadata.py` — Regex validation of LLM output (catch hallucinations)
- [x] `core/ingestion/chunker.py` — Legal-aware chunking:
  - Section detection (FACTS, ARGUMENTS, ANALYSIS, RATIO DECIDENDI, ORDER)
  - 2000-char chunks with 200-char overlap
  - Each chunk tagged: section_type, page_number, case_id, chunk_index
- [x] `core/ingestion/pipeline.py` — Orchestrator: PDF → text → metadata → chunks → embeddings → store
- [x] `core/legal/extractor.py` — Indian citation regex (5 formats), acts/sections parser
- [x] `core/legal/courts.py` — Court name normalization (SC + 25 HCs + tribunals)
- [x] `core/legal/constants.py` — Case types, bench types, disposal natures

#### 1.7 S3 Bulk Ingestion Script
- [x] `scripts/ingest_s3.py` — Download tar/zip + parquet from S3 (no-sign-required)
- [x] Parquet metadata reading + merge with LLM extraction
- [x] Progress tracking in local SQLite (resume support)
- [x] Rate limiting for Gemini API calls
- [x] Error logging for failed documents
- [x] Configurable concurrency (default: 5 parallel)
- [x] Ingest 1 year of SC judgments (~1000 docs) as initial dataset

#### 1.8 API Endpoints (Phase 1)
- [x] `POST /auth/register` — User registration with consent
- [x] `POST /auth/login` — JWT token pair
- [x] `POST /auth/refresh` — Token refresh with rotation
- [x] `POST /ingest/upload` — Single PDF upload (authenticated, admin only)
- [x] `GET /cases/{id}` — Case metadata + text
- [x] `GET /health` — Health check with dependency status

#### 1.9 Tests (Phase 1)
- [x] Unit tests: PDF extraction (sample PDFs), chunker (known sections), metadata regex
- [x] Unit tests: Auth (JWT creation/validation, password hashing)
- [ ] Integration test: Full ingest pipeline (PDF → all stores)
- [x] Test fixtures: 5 sample SC judgment PDFs with known metadata

### Exit Criteria
- [ ] 1,000+ SC judgments ingested (PostgreSQL + Pinecone + Neo4j)
- [x] All security middleware active (rate limiter, audit log, sanitizer)
- [x] API endpoints working with JWT auth
- [x] `docker compose up` starts everything locally
- [x] All tests pass, ruff + mypy clean

---

## Phase 2: Search + Frontend (Week 3–4)

### Goal
Full hybrid search pipeline. Next.js frontend with search UI, auth pages, and case viewer. Deploy to Vercel (frontend) + Cloud Run (backend).

### Deliverables

#### 2.1 Search Pipeline
- [x] `core/search/query.py` — LLM query understanding (Gemini → structured JSON: intent, entities, filters, expanded_query)
- [x] `core/search/fulltext.py` — PostgreSQL ts_rank_cd search with legal term boosting
- [x] `core/search/hybrid.py` — Search orchestrator:
  - Parallel execution: Pinecone vector + PostgreSQL FTS + metadata exact match
  - Reciprocal Rank Fusion (RRF, k=60) to merge
  - Result deduplication by case_id
- [x] `providers/rerankers/cohere.py` — CohereReranker: rerank top 20 → return top 10
- [x] Search result enrichment: attach full metadata, section labels, relevance snippets
- [x] Query caching in Redis (TTL: 5 minutes for identical queries)

#### 2.2 Search API
- [x] `GET /search` — Main search endpoint
  - Query params: `q`, `court`, `year_from`, `year_to`, `case_type`, `bench_type`, `judge`, `act`, `sort_by`, `page`, `page_size`
  - Response: results[], total_count, facets{}, query_understanding{}
  - Rate limited: 100 req/min per user
- [x] `GET /search/suggest` — Auto-complete suggestions (Redis-cached)
- [x] `GET /search/facets` — Available filter values (cached)

#### 2.3 Cases API
- [x] `GET /cases/{id}` — Full case detail with sections
- [x] `GET /cases/{id}/pdf` — Serve PDF from storage
- [x] `GET /cases/{id}/citations` — Cases cited by this case
- [x] `GET /cases/{id}/cited-by` — Cases that cite this case
- [x] `GET /cases/{id}/similar` — Semantically similar cases (vector search)

#### 2.4 Next.js Frontend Setup
- [x] Next.js 15 (App Router) + TypeScript strict
- [x] Tailwind CSS + shadcn/ui component library
- [x] `lib/api.ts` — Typed API client (fetch wrapper with JWT handling)
- [x] `lib/types.ts` — Shared TypeScript types matching backend schemas
- [x] Auth context: JWT storage (httpOnly cookie preferred), auto-refresh
- [x] CSP headers, CORS config in `next.config.ts`

#### 2.5 Frontend Pages
- [x] **Landing page** (`/`) — Search bar, tagline, recent notable cases
- [x] **Search results** (`/search`) — Result cards, filter sidebar, pagination, sort
  - Filter sidebar: court, year range, case type, bench type, judge, act
  - Result card: title, citation, court, date, snippet, relevance score
  - Responsive: mobile-first
- [x] **Case detail** (`/case/[id]`) — Metadata panel, judgment text (section-tabbed), PDF viewer
- [x] **Auth pages** (`/login`, `/register`) — Form with validation, error handling
- [x] **Layout** — Header with search bar, nav, user menu, footer with attribution (CC-BY-4.0)

#### 2.6 Bulk Ingestion (Scale Up)
- [ ] Ingest 5,000+ SC judgments (multiple years)
- [ ] Verify search accuracy: run 10 test queries, check results manually
- [ ] Fix any chunking/embedding/search issues discovered

#### 2.7 Tests (Phase 2)
- [ ] Unit tests: query understanding (mock Gemini), RRF merger, fulltext search
- [ ] Integration test: end-to-end search (query → results with correct metadata)
- [ ] Frontend: component tests for search bar, result card, filter sidebar
- [ ] Search accuracy test set: 15 queries with expected results

### Exit Criteria
- [ ] Search works for citation lookup, topic search, and filtered queries
- [ ] Frontend deployed to Vercel, backend on Cloud Run
- [ ] >80% recall@5 for citation queries on test set
- [ ] Auth flow complete (register → login → search → logout)
- [ ] Mobile-responsive search experience

---

## Phase 3: Intelligence + Graph Visualization (Week 5–6)

### Goal
RAG chat with streaming, citation graph visualization, judgment section viewer. The platform becomes a research assistant, not just a search engine.

### Deliverables

#### 3.1 RAG Chat
- [ ] `api/routes/chat.py` — Streaming chat endpoint (SSE)
  - `POST /chat` — Start new chat session
  - `POST /chat/{session_id}/message` — Send message, receive streaming response
  - `GET /chat/sessions` — List user's chat sessions
  - `GET /chat/{session_id}/history` — Full chat history
  - `DELETE /chat/{session_id}` — Delete session
- [ ] RAG pipeline:
  1. User query → LLM query understanding
  2. Hybrid search (top 10 chunks)
  3. Rerank (top 5)
  4. Construct prompt with retrieved context + chat history
  5. Stream response from Gemini with inline citations
- [ ] Citation grounding: every claim in response linked to source chunk
- [ ] Chat history stored encrypted per-user in PostgreSQL
- [ ] System prompt with legal research persona (from PROMPT_LIBRARY.md)

#### 3.2 Citation Graph API
- [ ] `api/routes/graph.py` — Graph query endpoints
  - `GET /graph/{case_id}/neighborhood` — 1-hop citation network
  - `GET /graph/{case_id}/chain` — Citation chain (recursive, max depth 3)
  - `GET /graph/{case_id}/authorities` — Most-cited cases in the network
  - `GET /graph/stats` — Graph statistics (total nodes, edges, most cited)
- [ ] Neo4j Cypher queries for:
  - Forward citations (cases this case cites)
  - Backward citations (cases that cite this case)
  - Overruled/affirmed/distinguished relationships
  - Authority score (PageRank-like: cases with most citations)
  - Common citations between two cases

#### 3.3 Frontend: Chat Interface
- [ ] Chat page (`/chat`) — Sidebar with session list, main chat area
- [ ] Streaming response display with typing indicator
- [ ] Inline citations: clickable links to source cases/sections
- [ ] "Sources" panel: retrieved chunks with relevance scores
- [ ] New session / continue session
- [ ] Chat input: multi-line, submit on Enter, Shift+Enter for newline

#### 3.4 Frontend: Citation Graph
- [ ] Graph page (`/graph`) — Interactive citation network visualization
- [ ] d3.js or vis.js force-directed graph
- [ ] Node types: Judgment (circle), Statute (diamond), Court (square)
- [ ] Edge types: color-coded (CITES=gray, OVERRULES=red, AFFIRMS=green, DISTINGUISHES=orange)
- [ ] Click node → show case details panel
- [ ] Zoom, pan, drag nodes
- [ ] Filter by: year range, court, relationship type

#### 3.5 Frontend: Enhanced Case Viewer
- [ ] Section-tabbed view: Facts | Arguments | Analysis | Ratio Decidendi | Order
- [ ] Highlighted key passages (ratio decidendi in yellow)
- [ ] "Cited Cases" sidebar: list with quick-view popover
- [ ] "Cited By" tab: cases that reference this judgment
- [ ] PDF download button
- [ ] Share/bookmark functionality

#### 3.6 Tests (Phase 3)
- [ ] Unit tests: RAG pipeline (mock LLM, verify prompt construction)
- [ ] Unit tests: Neo4j graph queries (test with sample graph)
- [ ] Integration test: chat flow (send message → receive streamed response with citations)
- [ ] Frontend: chat component tests, graph rendering tests

### Exit Criteria
- [ ] Chat produces grounded responses with citations for legal queries
- [ ] Citation graph renders for any ingested case
- [ ] Section viewer correctly identifies judgment sections
- [ ] Chat history persists across sessions
- [ ] 10,000+ SC judgments ingested

---

## Phase 4: Production Hardening + Launch (Week 7–8)

### Goal
Production-grade deployment on GCP, performance optimization, DPDP compliance, monitoring. Ready for real users.

### Deliverables

#### 4.1 GCP Production Deployment
- [ ] Cloud Run (backend): auto-scaling, min 1 instance, max 10
- [ ] Cloud SQL PostgreSQL 16: SSL-only, automated backups, point-in-time recovery
- [ ] GCP Secret Manager: all API keys, DB passwords, JWT secrets
- [ ] `providers/storage/gcs.py` — GCSStorage for PDF storage
- [ ] Cloud CDN for static assets (frontend)
- [ ] Custom domain + SSL certificate
- [ ] Cloud Armor: WAF rules for common attacks

#### 4.2 Performance Optimization
- [ ] Redis caching layer:
  - Search results: 5-min TTL for identical queries
  - Case metadata: 1-hour TTL
  - Facet counts: 15-min TTL
  - User session data: 24-hour TTL
- [ ] Database query optimization: EXPLAIN ANALYZE on slow queries
- [ ] Connection pooling: PgBouncer or SQLAlchemy pool tuning
- [ ] Pinecone query optimization: metadata pre-filtering
- [ ] Frontend: Image optimization, code splitting, prefetching

#### 4.3 DPDP Act Compliance
- [ ] Consent flow: explicit consent at registration with purpose listing
- [ ] Consent versioning: track which version user consented to
- [ ] Right to erasure: `DELETE /auth/me` — deletes all user data (chat, uploads, consent records, audit entries marked as deleted)
- [ ] Data retention policy: configurable (default: 2 years inactive)
- [ ] Breach notification process documented (72-hour requirement)
- [ ] Privacy policy page on frontend
- [ ] Cookie consent banner (if using cookies)

#### 4.4 Monitoring + Observability
- [ ] Structured logging (JSON) with PII redaction
- [ ] Cloud Logging integration
- [ ] Health check endpoint with dependency status (DB, Redis, Pinecone, Neo4j, Gemini)
- [ ] Error tracking: Sentry or GCP Error Reporting
- [ ] Uptime monitoring: Cloud Monitoring alerts
- [ ] Key metrics dashboard: search latency (p50/p95/p99), API error rate, LLM token usage, active users
- [ ] Alert rules: >5% error rate, p95 latency >3s, failed auth spike

#### 4.5 Document Upload (User Documents)
- [ ] Upload flow: file validation → virus scan (optional) → store → extract → chunk → embed → index
- [ ] Supported formats: PDF only (MVP)
- [ ] Size limit: 50MB per file
- [ ] Documents private to uploading user (row-level security)
- [ ] Upload status tracking: pending → processing → completed → failed
- [ ] Upload page (`/upload`) in frontend

#### 4.6 Landing + Onboarding
- [ ] Landing page redesign: hero, features grid, how-it-works, CTA
- [ ] Onboarding tour: first-time search walkthrough
- [ ] About page with dataset attribution (CC-BY-4.0, Dattam Labs)
- [ ] Credits/licensing page

#### 4.7 Final Quality Assurance
- [ ] Search accuracy evaluation: 30 test queries across categories
  - Citation lookup (10 queries): >90% recall@5
  - Topic search (10 queries): >70% recall@5
  - Filtered search (5 queries): correct filter application
  - Complex queries (5 queries): multi-facet, natural language
- [ ] Security audit checklist:
  - [ ] OWASP Top 10 review
  - [ ] JWT implementation review
  - [ ] SQL injection test (parameterized queries verified)
  - [ ] XSS test (CSP headers, output escaping)
  - [ ] Rate limiting verified under load
  - [ ] Secrets not in code or logs
  - [ ] CORS restricted to known origins
- [ ] Load testing: 50 concurrent users, <2s search response
- [ ] Mobile responsiveness audit

#### 4.8 Scale Ingestion
- [ ] Ingest remaining SC judgments (target: 20,000+)
- [ ] Citation graph integrity check: verify edges match extracted citations
- [ ] Metadata quality audit: sample 100 cases, verify LLM extraction accuracy

### Exit Criteria
- [ ] Production deployment stable on GCP
- [ ] Search accuracy meets targets on 30-query test set
- [ ] Security audit passed (no critical/high findings)
- [ ] DPDP compliance features active
- [ ] Monitoring + alerting operational
- [ ] 20,000+ SC judgments searchable
- [ ] <2s average search response time

---

## What Claude Should Build (Per Phase)

| Phase | Claude Builds | Claude Does NOT Build |
|-------|--------------|---------------------|
| 1 | All backend code, security, ingestion pipeline, tests | Frontend, CI/CD, production infra |
| 2 | Search pipeline, frontend pages, deploy configs | Mobile app, email notifications |
| 3 | Chat, graph API, graph viz, section viewer | Agent flows, document comparison |
| 4 | GCS provider, monitoring, DPDP flow, upload | Analytics dashboard, billing, admin panel |

## What We're NOT Building (Scope Control)

These items are explicitly deferred:

| Item | Reason | When |
|------|--------|------|
| Multiple LLM providers | Gemini covers all needs for MVP | Post-launch if needed |
| Browser extension | Low priority, complex | Phase 5+ |
| Multi-tenant workspaces | Single-tenant for MVP | When enterprise customers arrive |
| Mobile app | Web is sufficient for lawyers | Phase 5+ |
| TTS / STT | Not core workflow | Never (probably) |
| Agent flows | Complex, not MVP | Phase 5+ |
| Automated scraping | S3 dataset is sufficient | Phase 5 (bi-monthly S3 sync) |
| High Court judgments | Start with SC only | Phase 5 (16.7M docs, different scale) |
| Analytics dashboard | Not user-facing priority | Phase 5+ |
| Billing / payments | Free for MVP | When monetizing |
| Admin panel | API-only admin for MVP | Phase 5+ |
| Document comparison | Advanced feature | Phase 5+ |
| Email notifications | Not needed for MVP | Phase 5+ |
| i18n / Hindi UI | English-first for lawyers | Phase 5+ |

---

## Risk Register

| Risk | Impact | Mitigation |
|------|--------|------------|
| Gemini API quota exhaustion during bulk ingestion | Ingestion stalls | Rate limiting, batch processing, Flash fallback for non-critical extraction |
| Poor OCR quality on scanned PDFs | Bad text → bad embeddings → bad search | Detect OCR quality score, flag low-quality docs for review |
| Pinecone free tier limits (100K vectors) | Can't ingest all SC judgments | Upgrade to Starter ($70/mo) or switch to pgvector |
| Neo4j AuraDB free tier limits (200K nodes) | Citation graph truncated | Prioritize SC judgments, defer HC graph |
| LLM hallucination in metadata extraction | Wrong case_type, acts_cited | Regex validation layer, Parquet metadata as ground truth |
| Search latency >3s for complex queries | Poor UX | Cache, pre-compute facets, optimize Pinecone filters |
| GCP credits expire before launch | Cost spike | Monitor burn rate weekly, optimize for free tiers |
| DPDP Act enforcement timeline unclear | Compliance uncertainty | Build consent + erasure from day 1, adapt as regulations clarify |

---

## Dependencies Between Phases

```
Phase 1 ──────────────────────► Phase 2
  │ Interfaces + Providers         │ Search uses interfaces
  │ Security module                │ Frontend uses auth
  │ Ingestion pipeline             │ Search needs data
  │ PostgreSQL + Pinecone          │ FTS + vector search
  │                                │
  └──────────────────────────────► Phase 3
                                   │ Chat uses search pipeline
                                   │ Graph uses Neo4j provider
                                   │ Section viewer uses chunker
                                   │
                                   └──────────► Phase 4
                                                │ Production deployment
                                                │ GCS replaces LocalStorage
                                                │ Monitoring wraps everything
```

**Critical path**: Interfaces → Providers → Ingestion → Search → Chat

If any phase runs behind, the next phase can still start on non-dependent items (e.g., frontend layout while search is being tuned).
