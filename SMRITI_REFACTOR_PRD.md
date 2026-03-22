# SMRITI REFACTOR PRD — Overnight Autonomous Run

## CONTEXT
Smriti is an AI-powered Indian legal research platform (Harvey AI for Indian law). A lawyer enters a legal query and gets matching Supreme Court judgments with proper Indian legal citations, AI-synthesized research memos, citation graph analysis, and multi-agent legal research workflows.

Tech stack: FastAPI (Python 3.12) backend, Next.js 15 (App Router) + TypeScript + Tailwind CSS + shadcn/ui frontend, PostgreSQL 16 (metadata + FTS via tsvector), Pinecone vector DB (1536-dim, Gemini gemini-embedding-001), Neo4j AuraDB (citation graph), Gemini 2.5 Pro (reasoning LLM), Gemini 2.5 Flash (fast/cheap LLM for ingestion + classification), Cohere rerank-v4.0-pro (reranker), LangGraph (agent orchestration with HITL checkpoints), Celery + Redis (async task queue for document analysis + TTS), Redis/Upstash (caching + token revocation), Google Cloud Storage (prod PDF storage), Sarvam AI TTS (22 Indian languages), next-intl (EN/HI i18n), npm (frontend), pip (backend).

This codebase was written by Claude across multiple sessions. Many functions were written with intent but never wired up. Some represent earlier approaches that were superseded but never cleaned. Your job is to understand the LEGAL PURPOSE of each function, then either wire it into the app or mark it for human review with clear reasoning.

## RULES
- WORK ON EXACTLY ONE TASK PER ITERATION
- After completing a task, update this file: change `[ ]` to `[x]` for that task
- Commit after every task with message: `[SMRITI-REFACTOR] <task description>`
- NEVER delete a function unless you find its EXACT duplicate doing the same thing
- NEVER touch .env, API keys, or secrets
- If a function exists, assume it was written for a reason — your job is to find WHERE it plugs in
- When wiring up a function, think like an Indian litigation lawyer: "Would this help me find precedents faster? Would this help me prepare for bail arguments? Would this help me cite correctly in SCC/AIR format?"
- All external services MUST go through Protocol interfaces in `backend/app/core/interfaces/` — never call Gemini, Pinecone, Neo4j, or Cohere directly from routes
- All LLM prompts MUST live in `backend/app/core/legal/prompts.py` (PROMPT_LIBRARY) — never inline prompts
- Never use `any` in TypeScript or bare `Exception` in Python
- Never construct raw SQL strings — use SQLAlchemy ORM or parameterized text()
- Tests use pytest (backend, 2102 tests) and vitest (frontend, 311 tests) — NOT jest
- Update progress.txt after every iteration with what you did and what you learned about the codebase

## PHASE 1: DEEP AUDIT — Map Every Function to Its Legal Purpose

### Backend Audit
- [x] AUDIT-1: Read every Python file in `backend/app/core/`. For each function, write a one-line description of what it does and what legal workflow it serves (case search, citation extraction, judgment parsing, metadata extraction, embedding generation, reranking, agent orchestration, statute lookup, etc). Output to AUDIT_MAP.md
- [x] AUDIT-2: Read every file in `backend/app/core/providers/`. Map each provider to its Protocol interface in `backend/app/core/interfaces/`. Identify any provider with no interface or any interface with no concrete provider. Add to AUDIT_MAP.md
- [ ] AUDIT-3: Read every API route in `backend/app/api/routes/`. Map each route to: which core function it calls, which frontend component calls it (check `frontend/src/lib/api.ts`). Mark any route with no frontend caller as DISCONNECTED. Mark any core function with no route as UNEXPOSED. Add to AUDIT_MAP.md
- [x] AUDIT-4: Read every file in `backend/app/core/agents/` and `backend/app/core/agents/nodes/`. Map each LangGraph node function to: what stage it belongs to (Understand/Decompose/Investigate/Challenge/Synthesize), what state fields it reads/writes, what external services it calls. Identify any node function defined but not wired into any StateGraph. Add to AUDIT_MAP.md
- [x] AUDIT-5: Map the Pinecone integration — which functions write to Pinecone (`upsert`), which read from it (`search`), which handle metadata filtering (court, year, acts_cited, judgment_section). Identify any vector operations that are defined but never called. Cross-reference with `backend/app/core/providers/vector/pinecone_store.py`. Add to AUDIT_MAP.md
- [x] AUDIT-6: Map the Neo4j integration — which functions create nodes (MERGE), which create CITES edges, which query the graph (neighbors, shortest path, community detection). Identify any graph operations defined but never called. Cross-reference with `backend/app/core/providers/graph/neo4j_store.py`. Add to AUDIT_MAP.md

### Frontend Audit
- [ ] AUDIT-7: Read every page in `frontend/src/app/`. For each page, write what it renders and what user workflow it supports (search, chat, research, case prep, drafting, case detail, judge analytics, graph visualization, document upload). Add to AUDIT_MAP.md
- [ ] AUDIT-8: Read every component in `frontend/src/components/`. Map each to: which page(s) use it, what props it takes, what API calls it triggers. Identify any component that exists but is not imported by any page. Add to AUDIT_MAP.md
- [ ] AUDIT-9: Read `frontend/src/lib/api.ts`. Map each API function to: which backend route it calls, which frontend page/component calls it. Identify any API function with no frontend caller. Add to AUDIT_MAP.md

### Cross-Cutting Audit
- [ ] AUDIT-10: Create DISCONNECTED_FUNCTIONS.md listing every function (backend or frontend) that exists but is not reachable from any user action. For each one, write your best guess of where it should plug in based on its name, parameters, return type, and the legal workflow it seems to serve.

## PHASE 2: WIRE THE DOCUMENT INGESTION PIPELINE
The ingestion pipeline takes a PDF judgment → extracts text → extracts 16 metadata fields via Gemini → validates with regex → stores PDF (GCS/local) → inserts case into PostgreSQL → chunks (2000 chars, 200 overlap, section-tagged) → embeds (Gemini 1536-dim, batch 100) → upserts to Pinecone → builds citation graph in Neo4j → enriches statutes.

- [x] INGEST-1: Verify the upload endpoint (`POST /ingest/upload`) exists and the admin upload UI triggers it. If the upload API exists but no UI calls it, check if `frontend/src/app/upload/page.tsx` can be repurposed or if a separate admin upload page is needed.
- [x] INGEST-2: Verify PDF text extraction works — `backend/app/core/ingestion/pdf.py` has `extract_pdf_text()` (pdfplumber) and `extract_with_ocr()` (Gemini multimodal fallback). Verify these are called by `ingest_judgment()` in `pipeline.py`. Wire if disconnected.
- [x] INGEST-3: Verify LLM metadata extraction works — `backend/app/core/ingestion/metadata.py` has `extract_metadata_llm()` (Gemini structured output, 16 fields). Verify it's called after PDF extraction and before database insert. Wire if disconnected.
- [x] INGEST-4: Verify regex validation works — `metadata.py` has `validate_with_regex()` for sanity checks (judge count, citation format, year bounds). Verify it runs after LLM extraction. Wire if disconnected.
- [x] INGEST-5: Verify legal-aware chunking works — `backend/app/core/ingestion/chunker.py` has `chunk_judgment()` (2000-char chunks, 200-overlap, sentence-boundary, section-tagged). Verify it runs after metadata extraction. Wire if disconnected.
- [x] INGEST-6: Verify embedding generation works — `backend/app/core/providers/embeddings/gemini.py` has `embed_batch()` (1536-dim, batch 100). Verify `pipeline.py` calls it on chunks with contextual prefixes from `contextual_embeddings.py`. Wire if disconnected.
- [x] INGEST-7: Verify Pinecone upsert works — `backend/app/core/providers/vector/pinecone_store.py` has `upsert()` with metadata (case_id, citation, chunk_index, year, court, acts_cited, judgment_section). Verify `pipeline.py` calls it after embedding. Wire if disconnected.
- [x] INGEST-8: Verify Neo4j citation graph population works — `backend/app/core/providers/graph/neo4j_store.py` has `batch_create_nodes()` and `batch_create_citation_edges()`. Verify `pipeline.py` extracts citations via `extractor.py` and creates CITES edges. Wire if disconnected.
- [x] INGEST-9: Verify acts_cited normalization works — `extractor.py` has `normalize_acts_cited_list()` and `enrich_statute_cross_references()`. Verify pipeline calls these AFTER regex supplementation and BEFORE storage. Wire if disconnected.
- [x] INGEST-10: Verify the batch ingestion script works — `backend/scripts/ingest_s3.py` downloads from AWS S3 (`s3://indian-supreme-court-judgments/`), processes through `ingest_judgment()`, handles failures with circuit breaker (10 failures), has graceful shutdown. Test with 1 sample PDF.
- [x] INGEST-11: Verify statute ingestion works — `backend/scripts/ingest_statutes.py` ingests 59 acts (16,934 sections) with IPC→BNS/CrPC→BNSS/IEA→BSA replacement mappings. Verify statutes land in PostgreSQL with FTS indexes and in Pinecone with act_short_name metadata.

## PHASE 3: WIRE THE SEARCH AND RETRIEVAL PIPELINE
The search pipeline takes a user query → LLM query understanding → parallel vector search (Pinecone) + FTS (PostgreSQL tsvector) → RRF merge (k=60) → Cohere reranking (top 10) → results with citations.

- [ ] SEARCH-1: Verify the search page (`frontend/src/app/search/page.tsx`) calls `GET /search` via `api.search()`. Verify query, all 7 filter params (court, year_from, year_to, case_type, bench_type, judge, act), section filter, and pagination are passed through. Wire if disconnected.
- [ ] SEARCH-2: Verify `backend/app/core/search/hybrid.py` receives the query and runs LLM query understanding (Gemini) to extract legal concepts, then generates a Gemini embedding for vector search. Wire if any step is disconnected.
- [ ] SEARCH-3: Verify hybrid search works — vector search via Pinecone (`pinecone_store.search()`) + full-text search via PostgreSQL (`fulltext.py` using `websearch_to_tsquery`). Verify both run in parallel and results are merged via Reciprocal Rank Fusion (k=60). Wire if disconnected.
- [ ] SEARCH-4: Verify metadata filtering works — the `act` filter is normalized via `normalize_act_name()` before hitting Pinecone (`{"acts_cited": {"$in": [normalized_act]}}`). Verify court, year, case_type, bench_type, and judge filters are applied to both Pinecone and PostgreSQL queries. Wire if disconnected.
- [ ] SEARCH-5: Verify Cohere reranking works — `backend/app/core/providers/rerankers/cohere_reranker.py` has `rerank()` that re-ranks top results using `rerank-v4.0-pro`. Verify `hybrid.py` calls it after RRF merge and before returning results. Wire if disconnected.
- [ ] SEARCH-6: Verify search results display correctly — result cards show citation, court, year, judge, snippet with highlights, relevance score, precedent strength badge, bench strength indicator, section tabs. Wire any missing display element.
- [ ] SEARCH-7: Verify search suggestions work — `GET /search/suggest` provides autocomplete from case titles/citations. Verify frontend calls it. Wire if disconnected.
- [ ] SEARCH-8: Verify search facets work — `GET /search/facets` returns available filter values (courts, case types, etc.) cached for 1 hour. Verify frontend populates filter dropdowns from this. Wire if disconnected.
- [ ] SEARCH-9: Verify Hindi search works — if query is Hindi, `gemini_translator.py` translates to English for search, then translates result snippets back to Hindi. Wire if disconnected.
- [ ] SEARCH-10: Test the full search pipeline: enter "Section 302 IPC bail Supreme Court" → get relevant judgments with proper citations (SCC/AIR format). Fix any errors.

## PHASE 4: WIRE THE RAG CHAT PIPELINE
The chat pipeline provides multi-turn conversational legal research with source attribution.

- [ ] CHAT-1: Verify the chat page (`frontend/src/app/chat/page.tsx`) creates sessions via `POST /chat` and sends messages via `POST /chat/{session_id}/message`. Both should stream via SSE. Wire if disconnected.
- [ ] CHAT-2: Verify `backend/app/core/chat/rag.py` has `rag_respond()` that: searches context cases → reranks → sends to Gemini with legal-context prompt → streams response with source attribution. Wire if disconnected.
- [ ] CHAT-3: Verify chat session management works — `GET /chat/sessions` lists sessions, `GET /chat/{session_id}/history` returns messages (decrypted), `DELETE /chat/{session_id}` deletes cascade. Wire if disconnected.
- [ ] CHAT-4: Verify source cards display — each assistant message should show cited cases with case_id, title, citation, court, year, relevance score. Wire if disconnected.
- [ ] CHAT-5: Test: open chat → ask "What is the test for anticipatory bail under Section 438 CrPC?" → get answer with proper SCC/AIR citations and source cards. Fix any errors.

## PHASE 5: WIRE THE AGENT PIPELINES
Four LangGraph agents: Research (V3, 5-stage), Case Prep, Strategy, Drafting. All stream via SSE with HITL checkpoints.

### Research Agent V3 (5-Stage Pipeline)
- [ ] AGENT-1: Verify `frontend/src/app/agents/research/page.tsx` calls `POST /agents/research` via `api.runResearchAgent()` and handles all SSE event types (status, progress, checkpoint, memo, memo_stream, done, error). Wire if disconnected.
- [ ] AGENT-2: Verify `backend/app/core/agents/research.py` builds the StateGraph with all 5 stages:
  - Stage 1 (Understand): `rewrite_query_node` → `classify_query_node`
  - Stage 2 (Decompose): `statute_lookup_node` → `element_decomposition_node` → `route_by_complexity`
  - Stage 3 (Investigate): `plan_research_node` → checkpoint → `dispatch_workers` (7 workers: case_law, named_case, statute, graph, graph_community, ik_search, web_search) → `gather_results` → `batch_cot_reflection` → `evaluate_extract` → `gap_analysis` → checkpoint
  - Stage 4 (Challenge): `adversarial_search_node` → `temporal_validation_node`
  - Stage 5 (Synthesize): `speculative_synthesis_node` → `format_footnotes_node` → `verify_citations_v2_node` → `quality_check_node` → checkpoint
  Identify any node function defined in `nodes/research_nodes.py` but not wired into the graph. Wire or document why.
- [ ] AGENT-3: Verify all 7 worker nodes in `nodes/worker_nodes.py` are dispatched by `dispatch_workers_node`. Each worker should call its respective service:
  - `case_law_worker` → `hybrid_search()` (Pinecone + PG)
  - `named_case_worker` → direct PG lookup by citation/title
  - `statute_worker` → PG statute section lookup
  - `graph_worker` → Neo4j citation traversal
  - `graph_community_worker` → Neo4j community detection
  - `ik_search_worker` → Indian Kanoon API (`indiankanoon.py`)
  - `web_search_worker` → Tavily API (`tavily.py`)
  Wire if any worker is defined but not dispatched.
- [ ] AGENT-4: Verify HITL checkpoints work — `interrupt()` at plan, findings, and memo stages. Frontend `agent-checkpoint-prompt.tsx` renders the checkpoint dialog. `POST /agents/research/{execution_id}/resume` resumes from checkpoint. Wire if disconnected.
- [ ] AGENT-5: Verify research footnotes work — `format_footnotes_node` structures citations, `footnotes-panel.tsx` + `footnote-list-item.tsx` + `footnote-preview.tsx` display them. Wire if disconnected.
- [ ] AGENT-6: Verify research audit trail works — `research-audit-trail.tsx` displays methodology log (searches executed, refinement rounds, strategy pivots). Wire if the component exists but doesn't receive data.

### Case Prep Agent
- [ ] AGENT-7: Verify `frontend/src/app/agents/case-prep/page.tsx` calls `POST /agents/case-prep` with a document ID. Verify `backend/app/core/agents/case_prep.py` builds a graph with nodes from `nodes/case_prep_nodes.py`. Wire if disconnected.

### Strategy Agent
- [ ] AGENT-8: Verify `frontend/src/app/agents/strategy/page.tsx` calls `POST /agents/strategy` with case facts + desired relief + optional judge/bench. Verify `backend/app/core/agents/strategy.py` builds a graph with nodes from `nodes/strategy_nodes.py`. Wire if disconnected.

### Drafting Agent
- [ ] AGENT-9: Verify `frontend/src/app/agents/drafting/page.tsx` calls `POST /agents/drafting` with template + context. Verify `backend/app/core/agents/drafting.py` builds a graph with nodes from `nodes/drafting_nodes.py`. Verify export endpoints (`/export/pdf`, `/export/docx`) work via `backend/app/core/drafting/export.py`. Wire if disconnected.

### Agent History
- [ ] AGENT-10: Verify `frontend/src/app/agents/history/page.tsx` calls `GET /agents/{execution_id}` and `api.getAgentExecutions()` to list past runs. Verify status badges (running, waiting_input, completed, failed, cancelled) display correctly. Wire if disconnected.

## PHASE 6: WIRE THE CITATION GRAPH
- [ ] GRAPH-1: Verify `frontend/src/app/graph/page.tsx` calls `api.getGraphNeighborhood()`, `api.getGraphChain()`, and `api.getGraphAuthorities()`. Verify it renders an interactive D3/force graph. Wire if disconnected.
- [ ] GRAPH-2: Verify case detail page (`frontend/src/app/case/[id]/page.tsx`) shows "Cites" and "Cited By" tabs using `api.getCaseCitations()` and `api.getCaseCitedBy()`. Wire if disconnected.
- [ ] GRAPH-3: Verify `backend/app/core/graph/traversal.py` has working shortest-path and community detection algorithms. Verify the API route `GET /graph/path/{id1}/{id2}` calls it. Wire if disconnected.

## PHASE 7: WIRE SUPPORTING FEATURES

### Case Detail
- [ ] SUPPORT-1: Verify case detail page shows: full metadata (title, citation, court, year, judge, parties, bench type, disposal), acts cited (with display names from `get_act_display_name()`), cases cited, judgment sections (FACTS, ISSUES, ARGUMENTS, HOLDINGS, REASONING, ORDER), similar cases, PDF viewer, audio digest player. Wire any disconnected element.

### Judge Analytics
- [ ] SUPPORT-2: Verify `frontend/src/app/judges/page.tsx` lists judges with search + pagination via `api.getJudges()`. Verify `frontend/src/app/judge/[name]/page.tsx` shows profile (cases, disposal patterns, top judgments, acts frequency) via `api.getJudgeProfile()`. Wire if disconnected.
- [ ] SUPPORT-3: Verify judge comparison (`frontend/src/app/judges/compare/page.tsx`) calls `api.compareJudges()`. Wire if disconnected.

### Document Upload & Analysis
- [ ] SUPPORT-4: Verify `frontend/src/app/upload/page.tsx` calls `api.uploadDocument()` (50MB limit, PDF validation). Verify `frontend/src/app/documents/[id]/page.tsx` shows analysis results (issues extracted, counter-arguments, research memo). Verify Celery task `analyze_document()` processes uploads asynchronously. Wire if disconnected.

### Audio Digests (TTS)
- [ ] SUPPORT-5: Verify `audio-player.tsx` component calls `api.generateAudioDigest()` and `api.getAudioUrl()`. Verify Celery task `generate_audio()` uses Sarvam AI TTS. Verify it appears on case detail page. Wire if disconnected.

### Authentication & DPDP
- [ ] SUPPORT-6: Verify full auth flow: register (with DPDP consent) → login (with account lockout: 10 attempts / 5-min lock) → JWT access (60 min) + refresh (7 days) → proactive refresh (60s buffer) → session-expired event bus → logout (token revocation). Wire any disconnected step.
- [ ] SUPPORT-7: Verify DPDP compliance endpoints work: `GET /dpdp/audit-log`, `POST /dpdp/request-data`, `POST /dpdp/withdraw-consent`, `DELETE /auth/me` (cascade delete). Wire if disconnected.

### Semantic Cache
- [ ] SUPPORT-8: Verify `backend/app/core/search/semantic_cache.py` caches search results in Redis (5-min TTL) and is called by `hybrid.py` before running full search. Wire if disconnected.

### Admin Features
- [ ] SUPPORT-9: Verify admin review queue (`GET /review-queue`, `POST /review/{case_id}/approve|reject`) and admin corrections (`POST /corrections/{case_id}`) work. These are admin-only endpoints — verify RBAC middleware checks `user.role == "admin"`. Wire if disconnected.

### Error Handling & Logging
- [ ] SUPPORT-10: Verify `frontend/src/components/error-boundary.tsx` wraps the app. Verify all catch blocks in agent/chat/search pages surface errors to the UI (not silently swallowed). Check for any silent `catch (e) {}` blocks.

## PHASE 8: HARDEN

### Backend Hardening
- [ ] HARDEN-1: Add try/except with proper HTTP error codes to every FastAPI route that lacks it. A lawyer getting a generic 500 error loses trust instantly. Use `HTTPException` with meaningful detail messages.
- [ ] HARDEN-2: Verify Pydantic input validation on every endpoint — especially search (query cant be empty, year must be 1947-2026, court must be valid). Check all request models in route files.
- [ ] HARDEN-3: Add type hints to every Python function missing them. Never use bare `Exception` — always catch specific exceptions.
- [ ] HARDEN-4: Verify all external provider calls (Gemini, Pinecone, Neo4j, Cohere, Indian Kanoon, Tavily) use tenacity retry with exponential backoff (2-60s, 5 attempts). Add retry to any provider missing it.
- [ ] HARDEN-5: Verify circuit breaker pattern is applied to Neo4j (10 consecutive failures → 60s backoff). Check if other providers need circuit breakers.
- [ ] HARDEN-6: Verify no API keys or secrets are hardcoded anywhere. All must come from environment variables via `config.py`. Grep for any string that looks like `sk-`, `AIza`, hardcoded URLs with credentials.
- [ ] HARDEN-7: Verify CORS is configured correctly in `backend/app/main.py` for the frontend origin.
- [ ] HARDEN-8: Run ruff on all Python files. Fix all linting issues.

### Frontend Hardening
- [ ] HARDEN-9: Add loading/error/empty states to every frontend page/component that makes an API call. No raw spinners or blank screens.
- [ ] HARDEN-10: Verify every page that requires auth checks `isAuthenticated` and redirects to `/login`. List any unprotected page that should be protected.
- [ ] HARDEN-11: Run eslint on all TypeScript files. Fix all linting issues.
- [ ] HARDEN-12: Verify no `any` types in TypeScript. Grep for `: any` and fix with proper types from `types.ts`.

## PHASE 9: TEST VERIFICATION
- [ ] TEST-1: Run all backend tests: `cd backend && python -m pytest tests/unit/ -x -q`. All 2102+ tests must pass. Fix any failures.
- [ ] TEST-2: Run all frontend tests: `cd frontend && npx vitest run`. All 311+ tests must pass. Fix any failures.
- [ ] TEST-3: Identify any core function that lacks test coverage. Prioritize: ingestion pipeline steps, search pipeline steps, normalization functions, agent node functions.

## PHASE 10: FINAL VERIFICATION
- [ ] VERIFY-1: Start the FastAPI backend (`cd backend && uvicorn app.main:app`) — verify zero import errors, zero startup crashes, health endpoint returns all green.
- [ ] VERIFY-2: Build the Next.js frontend (`cd frontend && npm run build`) — verify zero build errors, zero type errors.
- [ ] VERIFY-3: Trace search end-to-end: Lawyer opens app → enters "anticipatory bail under Section 438 CrPC Supreme Court" → gets relevant judgments with proper Indian legal citations (SCC/AIR format) → can filter by court, year, bench type → sees precedent strength badges.
- [ ] VERIFY-4: Trace chat end-to-end: Lawyer opens chat → asks "What is the test for quashing under Section 482 CrPC?" → gets AI answer with cited cases and source cards → can ask follow-up questions in same session.
- [ ] VERIFY-5: Trace research agent end-to-end: Lawyer opens research workspace → enters "Whether Section 138 NI Act applies to post-dated cheques when account is closed before presentation" → agent runs 5-stage pipeline → presents research plan (HITL) → collects evidence → synthesizes memo with footnotes → shows audit trail.
- [ ] VERIFY-6: Review DISCONNECTED_FUNCTIONS.md — are there any functions left unwired? For each remaining one, add a comment in the code explaining why it was left and what it likely does.
- [ ] VERIFY-7: Final commit: `[SMRITI-REFACTOR] All tasks complete. See AUDIT_MAP.md and DISCONNECTED_FUNCTIONS.md for full summary.`
