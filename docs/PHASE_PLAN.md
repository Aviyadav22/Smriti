# Smriti — Phased Build Plan

---

## Overview

Eight phases delivering a full production legal intelligence platform. Phases 1-5 complete. Phases 6-8 take Smriti from "search tool" to "AI-powered legal assistant" with autonomous agents, multilingual support, and production deployment.

**Guiding Principles:**
- Each phase ends with a deployable artifact
- Security is built in from Phase 1, not bolted on later
- Interfaces (Protocols) are defined first, implementations follow
- Test as you build — no "testing phase" at the end
- Keep scope tight — the "NOT building" list matters as much as the build list
- Data is the #1 priority — features on an empty DB are useless
- Agents are the differentiator — not just search, but autonomous legal workflows

**Vision:** India's AI-powered legal intelligence platform — the Harvey AI for Indian law.

**Three Pillars:**
1. **Search & Discovery** — Hybrid search, citation graphs, section-aware case viewer
2. **Intelligence & Agents** — AI agents that do legal work: research, case prep, strategy, drafting
3. **Accessibility** — Hindi/multilingual, audio digests, mobile-first

---

## Phase 1: Foundation + Ingestion (Week 1–2) — COMPLETE

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

## Phase 2: Search + Frontend (Week 3–4) — COMPLETE

### Goal
Full hybrid search pipeline. Next.js frontend with search UI, auth pages, and case viewer.

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
- [x] **Case detail** (`/case/[id]`) — Metadata panel, judgment text (section-tabbed), PDF viewer
- [x] **Auth pages** (`/login`, `/register`) — Form with validation, error handling
- [x] **Layout** — Header with search bar, nav, user menu, footer with attribution

#### 2.6 Bulk Ingestion (Scale Up)
- [ ] Ingest 5,000+ SC judgments (multiple years) — MOVED TO PHASE 4
- [ ] Verify search accuracy: run 10 test queries, check results manually — MOVED TO PHASE 4
- [ ] Fix any chunking/embedding/search issues discovered — MOVED TO PHASE 4

#### 2.7 Tests (Phase 2)
- [x] Unit tests: query understanding (mock Gemini), RRF merger, fulltext search
- [ ] Integration test: end-to-end search (query → results with correct metadata) — MOVED TO PHASE 4
- [x] Frontend: component tests for search bar, result card, filter sidebar
- [ ] Search accuracy test set: 15 queries with expected results — MOVED TO PHASE 4

### Exit Criteria
- [x] Search pipeline code complete and tested
- [x] Frontend deployed locally with all pages
- [x] Auth flow complete (register → login → search → logout)
- [x] Mobile-responsive search experience

---

## Phase 3: Intelligence + Graph Visualization (Week 5–6) — COMPLETE

### Goal
RAG chat with streaming, citation graph visualization, judgment section viewer.

### Deliverables

#### 3.1 RAG Chat
- [x] `api/routes/chat.py` — Streaming chat endpoint (SSE)
  - `POST /chat` — Start new chat session
  - `POST /chat/{session_id}/message` — Send message, receive streaming response
  - `GET /chat/sessions` — List user's chat sessions
  - `GET /chat/{session_id}/history` — Full chat history
  - `DELETE /chat/{session_id}` — Delete session
- [x] RAG pipeline: query → hybrid search → rerank → prompt with context + history → stream from Gemini
- [x] Citation grounding: every claim linked to source chunk
- [x] Chat history stored encrypted per-user (AES-256-GCM)
- [x] System prompt with legal research persona

#### 3.2 Citation Graph API
- [x] `api/routes/graph.py` — Graph query endpoints
  - `GET /graph/{case_id}/neighborhood` — 1-hop citation network
  - `GET /graph/{case_id}/chain` — Citation chain (recursive, max depth 3)
  - `GET /graph/{case_id}/authorities` — Most-cited cases in the network
  - `GET /graph/stats` — Graph statistics
- [x] Neo4j Cypher queries for forward/backward citations, overruled/affirmed/distinguished

#### 3.3 Frontend: Chat Interface
- [x] Chat page (`/chat`) — Sidebar with session list, main chat area
- [x] Streaming response display with typing indicator
- [x] Inline citations: clickable links to source cases
- [x] Sources panel: retrieved chunks with relevance scores

#### 3.4 Frontend: Citation Graph
- [x] Graph page (`/graph`) — Interactive citation network (react-force-graph-2d)
- [x] Edge types: color-coded (CITES=gray, OVERRULES=red, AFFIRMS=green, DISTINGUISHES=orange)
- [x] Click node → show case details panel
- [x] Zoom, pan, depth controls (1-3)

#### 3.5 Frontend: Enhanced Case Viewer
- [x] Section-tabbed view with mini citation graph
- [x] Cited Cases and Cited By tabs

#### 3.6 Tests (Phase 3)
- [x] Unit tests: RAG pipeline (17 tests), graph traversal (16 tests)
- [x] Frontend: chat page tests (6), graph page tests (5)
- [x] Encryption roundtrip tests (4)

### Exit Criteria
- [x] Chat produces grounded responses with citations
- [x] Citation graph renders correctly
- [x] All 190 backend tests pass
- [x] All 88 frontend tests pass
- [x] Frontend builds clean

---

## Phase 4: Judge Analytics — COMPLETE

### Goal
Ship Judge Analytics using the existing ~740 ingested cases. Build and validate the feature infrastructure first — bulk re-ingestion with improved metadata extraction happens separately later.

### Deliverables

#### 4.1 Data Validation (existing ~740 cases)
- [x] Verify existing cases have judge/author_judge fields populated
- [x] Audit metadata quality on 20 sample cases (judges, disposal_nature, acts_cited)
- [x] Identify metadata extraction gaps to fix before future re-ingestion
- [x] Verify search works against existing data: 5 test queries

#### 4.2 Judge Analytics API
- [x] `GET /judges` — List all judges with case counts
- [x] `GET /judges/{name}` — Judge profile:
  - Cases authored (count by year)
  - Disposal patterns (dismissed/allowed/remanded percentages)
  - Most frequent bench combinations
  - Most-cited judgments authored
  - Acts/sections most frequently dealt with
  - Landmark judgments authored
- [x] `GET /judges/{name}/cases` — Paginated case list with filters
- [x] `GET /judges/compare` — Compare 2-3 judges side by side
- [x] `GET /courts/{court}/stats` — Court-level statistics
- [x] Redis caching (judge stats: 1-hour TTL)

#### 4.3 Judge Analytics UI
- [x] Judge directory page (`/judges`) — searchable list with key stats
- [x] Judge profile page (`/judge/[name]`) — stats dashboard:
  - Disposal pattern pie chart
  - Cases per year bar chart
  - Bench combination co-judge list
  - Top cited judgments list
  - Acts/sections frequency bar chart
- [x] Judge comparison page (`/judges/compare`) — side-by-side stats
- [x] Link judges from case detail page (clickable judge names)
- [x] Court statistics page (`/courts`) — aggregate stats

#### 4.4 Tests (Phase 4)
- [x] Unit tests: judge analytics SQL queries (mock DB) — 28 backend tests
- [x] Frontend: judge profile page tests, comparison tests — 27 frontend tests
- [x] Data validation: spot-check judge stats against existing ~740 cases

### Exit Criteria
- [x] Judge Analytics working against existing ~740 cases
- [x] Judge profile, comparison, and court stats pages render correctly
- [x] All backend + frontend tests pass (197 backend, 115 frontend)
- [x] Metadata gaps documented for future re-ingestion improvements

---

## Phase 5: Document Upload + Audio Digests — COMPLETE

### Goal
Two killer features competitors charge for — upload briefs for precedent mapping, listen to judgment summaries on the go.

### Deliverables

#### 5.1 Document Upload Pipeline
- [x] Upload endpoint: `POST /documents/upload` (PDF, max 50MB)
- [x] File validation (type, size, virus scan optional)
- [x] Store to GCS/local storage
- [x] Background processing pipeline (Celery + Redis):
  1. Text extraction (pdfplumber + OCR fallback)
  2. Issue identification (Gemini Pro: extract legal issues)
  3. Per-issue precedent search (hybrid search, parallel)
  4. Counter-argument identification
  5. Research memo generation (structured, with citations)
- [x] Status tracking: pending → extracting → analyzing → searching → generating → complete → failed
- [x] Documents private per-user (row-level security)
- [x] `GET /documents` — List user's uploaded documents
- [x] `GET /documents/{id}` — Document detail + analysis results
- [x] `DELETE /documents/{id}` — Delete document + all analysis

#### 5.2 Document Upload UI
- [x] Upload page (`/upload`) — drag-and-drop PDF upload
- [x] Processing status with step-by-step progress
- [x] Analysis results page:
  - Extracted issues listed
  - Per-issue: supporting precedents, opposing precedents, key statutes
  - Downloadable research memo (PDF export)
- [x] Document history in user dashboard

#### 5.3 Audio Digests
- [x] Audio generation pipeline:
  1. Case summary generation (Gemini Pro: 2-3 min summary)
  2. TTS via Sarvam AI (Hindi + English) or Google Cloud TTS fallback
  3. Audio file storage (GCS/local, MP3)
  4. Cache generated audio (don't regenerate)
- [x] `GET /cases/{id}/audio` — Stream or download audio digest
- [x] `GET /cases/{id}/audio/status` — Check if audio exists
- [x] `POST /cases/{id}/audio/generate` — Trigger async generation
- [x] Audio player on case detail page:
  - Play/pause, progress bar, playback speed (0.5x-2x)
  - Download button, language selector (EN / HI)
- [ ] Batch audio generation for landmark cases — DEFERRED to Phase 8

#### 5.4 Tests (Phase 5)
- [x] Unit tests: document processing pipeline (mock Gemini) — 53 new backend tests
- [x] Unit tests: audio generation pipeline (mock TTS API) — 6 TTS + 2 audio task tests
- [x] Frontend: upload page tests, audio player tests — 12 new frontend tests
- [ ] Integration test: upload PDF → receive analysis results — DEFERRED to Phase 8

### Exit Criteria
- [x] Document upload produces accurate issue mapping for sample briefs
- [x] Audio digests play correctly in English and Hindi (Sarvam AI + Mock)
- [x] Processing status updates in real-time (polling)
- [x] Documents private per-user
- [x] All 250 backend tests pass
- [x] All 127 frontend tests pass
- [x] Frontend builds clean

---

## Phase 6: Agent Framework + Research & Case Prep Agents

### Goal
Build the agent infrastructure and ship the first two agents. Transition from "search tool" to "AI legal assistant."

### Deliverables

#### 6.1 Agent Infrastructure
- [ ] `core/agents/base.py` — Base agent Protocol:
  - `plan(input) -> list[Step]` — Break task into steps
  - `execute(step) -> StepResult` — Execute a single step
  - `adapt(results) -> list[Step]` — Revise plan based on results
  - `interact(checkpoint) -> UserInput` — Request human input
- [ ] `core/agents/orchestrator.py` — Orchestrator agent:
  - Intent classification (which agent to route to)
  - Multi-agent coordination (parallel sub-tasks)
  - Result aggregation and formatting
- [ ] `core/agents/state.py` — Agent state management:
  - PostgreSQL-backed state persistence
  - Step tracking (planned → running → completed → failed)
  - Intermediate results storage (encrypted)
  - Execution history and audit trail
- [ ] LangGraph integration:
  - Graph-based workflow definitions
  - Conditional routing (branch on step results)
  - Parallel node execution
  - Human-in-the-loop breakpoints
- [ ] Multi-model routing:
  - Gemini Pro for reasoning, analysis, synthesis
  - Gemini Flash for classification, extraction, summarization
  - Router logic based on task type + complexity
- [ ] Agent execution API:
  - `POST /agents/{agent_type}/run` — Start agent execution (SSE streaming)
  - `GET /agents/executions/{id}` — Execution status and results
  - `GET /agents/executions` — List user's executions
  - `POST /agents/executions/{id}/input` — Provide human input at checkpoint
  - `DELETE /agents/executions/{id}` — Cancel running execution

#### 6.2 Research Agent
- [ ] `core/agents/research.py`:
  - Decompose legal question into 3-7 sub-queries
  - Run parallel hybrid searches per sub-query
  - Cross-reference results (cases appearing in multiple sub-queries = high relevance)
  - Contradiction detection (flag conflicting holdings)
  - Produce structured research memo:
    - Executive summary
    - Key findings per sub-query
    - Supporting precedents (with relevance + confidence scores)
    - Opposing/distinguishing precedents
    - Statutory provisions cited
    - Recommended further research
  - Handle follow-up questions within session
  - Citation verification: every cited case exists in DB

#### 6.3 Case Prep Agent
- [ ] `core/agents/case_prep.py`:
  - Accept uploaded brief/petition (PDF or text)
  - Extract legal issues, parties, relief sought, key facts
  - Per issue: find supporting precedents, opposing precedents, key statutes
  - Identify likely counter-arguments and responses
  - Generate structured research memo:
    - Case overview
    - Issues identified
    - Per-issue analysis with precedent mapping
    - Counter-argument matrix
    - Recommended strategy points
  - Export as PDF/Word

#### 6.4 Agent UI
- [ ] Agent hub page (`/agents`) — agent selector with descriptions
- [ ] Agent workspace (`/agents/[type]`):
  - Input panel (text or file upload)
  - Step-by-step execution visualization
  - Real-time streaming of intermediate results
  - Human-in-the-loop input prompts
  - Final result with citations
- [ ] Agent history in user dashboard
- [ ] Share agent results (shareable link)

#### 6.5 Tests (Phase 6)
- [ ] Unit tests: orchestrator routing, research agent planning, case prep issue extraction
- [ ] Unit tests: agent state management (persistence, recovery)
- [ ] Frontend: agent hub tests, workspace tests
- [ ] Integration test: research agent end-to-end with mock LLM

### Exit Criteria
- [ ] Research Agent produces coherent memos for 10 test legal questions
- [ ] Case Prep Agent correctly identifies issues from 5 sample briefs
- [ ] Agent execution streams progress in real-time
- [ ] Human-in-the-loop checkpoints work
- [ ] Agent state persists and can be resumed

---

## Phase 7: Strategy Agent + Drafting Agent + Hindi

### Goal
Advanced agents for litigation strategy and document drafting. Hindi support to unlock India's mass market.

### Deliverables

#### 7.1 Strategy Agent
- [ ] `core/agents/strategy.py`:
  - Input: case facts + target judge/bench (optional) + desired relief
  - Pull Judge Analytics data (disposal patterns, tendencies)
  - Find cases with similar fact patterns, track outcomes
  - Predict likely arguments from opposing side
  - Identify weak points in user's position
  - Output:
    - Case strength assessment (strong/moderate/weak + reasoning)
    - Recommended legal arguments (ordered by predicted effectiveness)
    - Key precedents to cite (with relevance explanation)
    - Anticipated counter-arguments and rebuttals
    - Judge-specific considerations
    - Procedural strategy suggestions

#### 7.2 Drafting Agent
- [ ] `core/agents/drafting.py`:
  - Input: document type + case facts + relevant precedents
  - Document types:
    - Bail applications (Section 439 CrPC)
    - Writ petitions (Article 226/32)
    - Written statements
    - Legal notices
    - Appeals (civil/criminal)
    - Applications (interim relief, stay, adjournment)
  - Grounded in precedents and statutory provisions
  - Citation verification against DB
  - Template system (customizable per document type)
  - Export: Word (.docx) and PDF
  - Revision: accept feedback, regenerate sections

#### 7.3 Hindi Support
- [ ] `next-intl` for frontend i18n
- [ ] Hindi translations for all UI strings
- [ ] Language toggle in header (EN / HI)
- [ ] Hindi search: detect language → translate → search → translate back
- [ ] Hindi judgment summaries (Gemini translation)
- [ ] Hindi audio digests (Sarvam AI TTS)
- [ ] Hindi agent responses (when query is in Hindi)

#### 7.4 Document Review Agent (if time permits)
- [ ] Upload contract/agreement → clause-by-clause analysis
- [ ] Risk flagging (high/medium/low per clause)
- [ ] Missing clause detection
- [ ] Compliance check against relevant statutes

#### 7.5 Tests (Phase 7)
- [ ] Unit tests: strategy agent, drafting agent, Hindi translation pipeline
- [ ] Frontend: Hindi UI rendering, drafting workspace tests
- [ ] Integration test: strategy agent with real judge data
- [ ] Translation quality: 10 Hindi queries, verify search accuracy

### Exit Criteria
- [ ] Strategy Agent produces actionable strategy for 5 test cases
- [ ] Drafting Agent generates valid documents for all 6 types
- [ ] Hindi search returns relevant results for 10 test queries
- [ ] Hindi audio digests work
- [ ] Language toggle works across all pages

---

## Phase 8: Production Hardening + Launch

### Goal
Production-grade deployment on GCP. Everything needed for real lawyers.

### Deliverables

#### 8.1 GCP Production Deployment
- [ ] Cloud Run (backend): auto-scaling, min 1, max 10
- [ ] Cloud SQL PostgreSQL 16: SSL-only, backups, point-in-time recovery
- [ ] GCP Secret Manager for all secrets
- [ ] `providers/storage/gcs.py` — GCSStorage for PDFs + audio
- [ ] Cloud CDN for static assets
- [ ] Custom domain + SSL (smriti.law or similar)
- [ ] Cloud Armor WAF
- [ ] Vercel or Cloud Run for frontend

#### 8.2 Performance Optimization
- [ ] Redis caching: search (5min), metadata (1hr), judge stats (1hr), facets (15min), agent results (24hr)
- [ ] DB query optimization (EXPLAIN ANALYZE)
- [ ] Connection pooling
- [ ] Pinecone pre-filtering
- [ ] Frontend: code splitting, prefetching, image optimization
- [ ] Audio CDN caching (long TTL, immutable)

#### 8.3 DPDP Act Compliance
- [ ] Consent flow with purpose listing
- [ ] Consent versioning
- [ ] Right to erasure (`DELETE /auth/me`)
- [ ] Data retention policy (2yr default)
- [ ] Breach notification process (72hr)
- [ ] Privacy policy page
- [ ] Cookie consent banner

#### 8.4 Monitoring + Observability
- [ ] Structured JSON logging with PII redaction
- [ ] Cloud Logging + Sentry
- [ ] Health check with all dependencies
- [ ] Metrics dashboard:
  - Search: latency p50/p95/p99
  - API: error rate, request count
  - LLM: token usage, cost tracking
  - Agents: execution time, success rate
  - Users: DAU/WAU/MAU
- [ ] Alerts: >5% errors, p95 >3s, auth spike, agent failures

#### 8.5 Security Audit
- [ ] OWASP Top 10 review
- [ ] JWT review, SQL injection test, XSS test
- [ ] Rate limiting load test
- [ ] Secrets audit, CORS verification
- [ ] Agent prompt injection testing

#### 8.6 Landing Page + Onboarding
- [ ] Landing redesign: hero, features grid, agent showcase, pricing tiers, testimonials
- [ ] Onboarding guided tour
- [ ] About page with attribution (CC-BY-4.0)

#### 8.7 Load Testing + QA
- [ ] Search accuracy: 30 queries (citation >90%, topic >70%, filtered, complex)
- [ ] Agent quality: 20 test scenarios across all agents
- [ ] Load test: 50 concurrent users, <2s search, <5s agent first token
- [ ] Mobile responsiveness audit
- [ ] Cross-browser testing

### Exit Criteria
- [ ] Production stable on GCP
- [ ] Search and agent accuracy meet targets
- [ ] Security audit passed
- [ ] DPDP compliance active
- [ ] Monitoring operational
- [ ] <2s search, <5s agent response

---

## Post-Launch Roadmap

### Phase 9: High Court Expansion
- Indian Kanoon / eCourts data integration
- 100K+ HC judgments (top 5 HCs by volume)
- Regional court support
- State-specific statutes
- Judge Analytics for HC judges

### Phase 10: Compliance Agent + Enterprise
- Compliance Agent: regulatory monitoring, gap analysis
- Multi-tenant workspaces, SSO
- Admin panel, usage analytics
- API rate limits per pricing tier

### Phase 11: Mobile + API Platform
- React Native app (iOS + Android)
- Offline mode (cached cases, downloaded audio)
- Public API + webhooks
- SDK for embedding Smriti search

### Phase 12: Marketplace + Community
- Workflow marketplace (share agent workflows)
- Community document templates
- Lawyer profiles with expertise
- Legal education modules

---

## What We're NOT Building (Scope Control)

| Item | Reason | When |
|---|---|---|
| Multiple LLM vendors | Gemini family covers all needs | Post-launch if needed |
| Browser extension | Low priority, complex | Phase 11+ |
| Automated web scraping | Legal gray area, prefer structured sources | Phase 9 (official data sources) |
| Custom embedding model | Fine-tuning expensive, Gemini adequate | Post-launch R&D |
| Real-time court updates | Requires APIs not yet available | Phase 9 (eCourts) |
| Billing / payments | Free for launch | When monetizing |
| Video tutorials | Content, not engineering | Marketing team |
| Arbitration/ADR module | Niche | Phase 12+ |

---

## Risk Register

| Risk | Severity | Mitigation |
|---|---|---|
| Dataset too small (35K vs 16M competitors) | CRITICAL | Max out S3 Phase 4, plan HC expansion Phase 9 |
| No users / zero distribution | HIGH | Ship early, target law students, free tier |
| Agent hallucination in legal context | HIGH | Citation verification, human-in-the-loop, confidence scores |
| Pinecone cost at scale | MEDIUM | Upgrade to Starter ($70/mo), monitor usage |
| Gemini credit exhaustion | MEDIUM | Flash for ingestion, Pro for agents, monitor burn |
| LangGraph complexity | MEDIUM | Start simple (2-3 step agents), iterate |
| Hindi translation quality | MEDIUM | Gemini translation, verify with native speakers |
| Sarvam AI TTS availability | LOW | Google Cloud TTS as fallback |
| DPDP enforcement timeline | LOW | Compliance built in from Phase 1 |
| Neo4j free tier (200K nodes) | LOW | Sufficient for 35K, upgrade for HC |

---

## Dependencies Between Phases

```
Phase 1 (DONE) ───► Phase 2 (DONE) ───► Phase 3 (DONE)
  │                   │                    │
  │ Interfaces        │ Search pipeline    │ RAG chat
  │ Security          │ Frontend           │ Graph viz
  │ Ingestion         │ Auth flow          │ Encryption
  │                   │                    │
  └──► Phase 4 ───────┴──► Phase 5 ───────┴──► Phase 6
       │ Data!              │ Doc upload         │ Agent infra
       │ Judge Analytics    │ Audio              │ Research agent
       │                    │                    │ Case prep agent
       │                    │                    │
       └────────────────────┴──► Phase 7 ────────┘
                                  │ Strategy agent
                                  │ Drafting agent
                                  │ Hindi support
                                  │
                                  └──► Phase 8
                                       │ GCP deploy
                                       │ DPDP
                                       │ Monitoring
                                       │ Launch!
```

**Critical path**: Data (P4) → Agents (P6) → Production (P8)

Phases 5 and 7 can partially overlap with 4 and 6 respectively on non-dependent items.

---

## Success Metrics

| Metric | Launch Target | 6-Month Target |
|---|---|---|
| Cases ingested | 35,000 SC | 100,000+ (SC + HC) |
| Registered users | 100 | 5,000 |
| DAU | 10 | 500 |
| Search queries/day | 50 | 2,000 |
| Agent executions/day | 10 | 500 |
| Search latency (p95) | <2s | <1.5s |
| Agent first token (p95) | <5s | <3s |
| Audio digests generated | 1,000 | 10,000 |
| Hindi queries | 10% | 30% |
