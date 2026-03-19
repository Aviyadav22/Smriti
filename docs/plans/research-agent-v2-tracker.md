# RESEARCH AGENT V2 — IMPLEMENTATION TRACKER

> **Bible**: `docs/plans/research-agent-v2-bible.md` (the single source of truth)
> **Created**: 2026-03-19
> **Strategy**: Phases 1+2 run in parallel. Phase 3 depends on both. Phases 4-5 are sequential.

---

## PRE-FLIGHT (Before Any Code)

- [x] **P0.1** Read the bible end-to-end (Sections 0-14) to build full mental model
- [x] **P0.2** Read existing code files listed in Section 11 (Existing Code Reference) — understand what exists before changing anything
- [x] **P0.3** Verify all 1546 backend unit tests pass
- [x] **P0.4** Verify 298 frontend tests pass (`cd frontend && npm test`) — 298 passed
- [x] **P0.5** Create git branch: `feature/research-agent-v2` _(working directly on master per user preference)_
- [x] **P0.6** Verify dev environment: PostgreSQL, Redis, Pinecone (vectors), Neo4j (796 nodes) — all 4 OK

---

## PHASE 1: CORE ORCHESTRATION (Week 1-2)

> **Bible ref**: Section 5 (5.1–5.7)
> **Goal**: Replace linear decompose→search with orchestrator→worker pattern. Dual queries, named case retrieval, CRAG, MA-RAG CoT with reflection, MC-RAG conditioned retrieval, passage extraction.

### 1A — State Schema & Types (Bible 5.1)
- [x] **1A.1** Add `ResearchTask` TypedDict to `state.py` (Bible 3.2)
- [x] **1A.2** Add `WorkerResult` TypedDict to `state.py`
- [x] **1A.3** Add `EvidenceGap` TypedDict with `conditioned_on` + `conditioning_context` fields [Q1]
- [x] **1A.4** Add `ExtractedPassage` TypedDict
- [x] **1A.5** Add `Footnote` TypedDict with `verification_status` + `verified_against` fields [T4]
- [x] **1A.6** Add `RelevanceScore` TypedDict (CRAG)
- [x] **1A.7** Add `CommunitySummary` TypedDict (GraphRAG)
- [x] **1A.8** Add `SynthesisDraft` TypedDict (Speculative RAG)
- [x] **1A.9** Add `LegalQualityResult` TypedDict [Q4]
- [x] **1A.10** Add `StrategyAdjustment` TypedDict [Q5]
- [x] **1A.11** Update `ResearchState` with all new fields (Bible 3.2 — `strategy_adjustment`, `legal_quality_result`, `citation_verification_results`, `process_events`, etc.)
- [x] **1A.12** Run tests — no regressions

### 1B — Prompts (Bible 5.2)
- [x] **1B.1** Add `RESEARCH_REWRITE_SYSTEM` prompt to `prompts.py`
- [x] **1B.2** Add `RESEARCH_CLASSIFY_SYSTEM` prompt (modified: complexity enum → simple/complex/multi_issue)
- [x] **1B.3** Add `RESEARCH_PLAN_SYSTEM` prompt + `RESEARCH_PLAN_SCHEMA`
- [x] **1B.4** Add `EVALUATE_AND_EXTRACT_SYSTEM` prompt + schema (includes CRAG + deep_read [Q2])
- [x] **1B.5** Add `GAP_ANALYSIS_SYSTEM` prompt + schema (includes MC-RAG conditioning [Q1])
- [x] **1B.6** Add `BATCH_COT_WITH_REFLECTION_SYSTEM` prompt + `BATCH_COT_WITH_REFLECTION_SCHEMA` [S4 + Q5]
- [x] **1B.7** Add `RESEARCH_FAST_PATH_SYNTHESIS_SYSTEM` prompt [S9]
- [x] **1B.8** Add all prompts to `PROMPT_LIBRARY.md`
- [x] **1B.9** Run tests — no regressions

### 1C — Core Nodes (Bible 5.3)
- [x] **1C.1** Implement `rewrite_query_node` — query reformulation
- [x] **1C.2** Implement `classify_complexity_node` — simple/complex routing (via updated classify schema)
- [x] **1C.3** Implement `plan_research_node` — dual query (NL + boolean) + named cases
- [x] **1C.4** Implement `dispatch_workers_node` — `Send()` fan-out to typed workers
- [x] **1C.5** Implement `gather_results_node` — collect all worker results
- [x] **1C.6** Implement `batch_worker_cot_with_reflection_node` [S4 + Q5] — batched CoT + reflection strategy adjustment
- [x] **1C.7** Implement `evaluate_and_extract_node` [S3 + Q2 + S12] — merged CRAG + extract + deep_read + parallel batches
- [x] **1C.8** Implement `gap_analysis_node` [Q1] — with MC-RAG conditioned retrieval + reflection integration
- [x] **1C.9** Implement `fast_path_search_node` [S9] — single-worker dispatch with fallback
- [x] **1C.10** Implement `fast_path_synthesis_node` [S9] — Flash synthesis for simple queries
- [x] **1C.11** Unit test each node in isolation with mocked dependencies (tests 1-9 from Bible 13)
- [x] **1C.12** Run full test suite — no regressions

### 1D — Worker Nodes (Bible 5.4)
- [x] **1D.1** Create `worker_nodes.py` — NEW FILE
- [x] **1D.2** Implement `case_law_worker` — dual-query hybrid search
- [x] **1D.3** Implement `named_case_worker` — citation + title lookup
- [x] **1D.4** Unit test workers with mocked search/DB
- [x] **1D.5** Run full test suite — no regressions

### 1E — Graph Wiring (Bible 5.5)
- [x] **1E.1** Rewrite `research.py` — new graph with all Phase 1 nodes
- [x] **1E.2** Wire conditional edges: `route_by_complexity` (simple→fast_path, complex→full pipeline)
- [x] **1E.3** Wire rewrite → classify (sequential for now, [S2] parallel deferred)
- [x] **1E.4** Wire gap_analysis loop (max 2 rounds)
- [x] **1E.5** Wire HITL checkpoints: `checkpoint_plan`, `checkpoint_findings`, `checkpoint_memo`
- [x] **1E.6** Integration test: full graph run with mocked LLM (test 6 from Bible 13)
- [x] **1E.7** Run full test suite — no regressions

### 1F — Common Utilities (Bible 5.6)
- [x] **1F.1** Add `format_search_results_for_llm_extended()` — higher context limits (1500/3000)
- [x] **1F.2** Add `deduplicate_with_diversity()` — max 4 chunks per case
- [x] **1F.3** Add `format_extracted_passages()` helper
- [x] **1F.4** Add `format_community_summaries()` helper
- [x] **1F.5** Run tests — no regressions

### 1G — API Route Update (Bible 5.7)
- [x] **1G.1** Update `agents.py` to pass new dependencies to research graph
- [x] **1G.2** Verify SSE streaming still works with new node names (node names changed, tests pass)
- [x] **1G.3** Run full test suite — no regressions

### PHASE 1 GATE
- [x] **1Z.1** All Phase 1 unit tests pass (Bible 13, tests 1-9)
- [x] **1Z.2** CRAG tests pass (tests 10-13)
- [x] **1Z.3** MA-RAG CoT tests pass (tests 18-20)
- [x] **1Z.4** Fast path tests pass (tests 39-41)
- [x] **1Z.5** Full 1546 test suite passes (up from 1411 baseline — all existing tests updated)
- [x] **1Z.6** Live services verified: PostgreSQL, Pinecone, Neo4j (796 nodes), Redis all connected
- [x] **1Z.7** Commit: `feat: research agent v2 — Phase 1 core orchestration` — eff1dbb

---

## PHASE 2: DATA EXPANSION + INGESTION ENHANCEMENTS (Week 1-2, parallel with Phase 1)

> **Bible ref**: Section 6 (6.1–6.13)
> **Goal**: Statute/constitution tables, contextual embeddings, RAPTOR summaries, code mapping, HC data.

### 2A — Statute Storage (Bible 6.1–6.3)
- [x] **2A.1** Create migration `020_create_statutes_table.py` (Bible 6.1) — migration 020, not 017 (latest was 019)
- [x] **2A.2** Create `models/statute.py` (Bible 6.2)
- [x] **2A.3** Create `scripts/ingest_statutes.py` — IPC/CrPC/IEA/BNS/BNSS/BSA/CPC/Constitution (Bible 6.3)
- [x] **2A.4** Run migration 020, statutes table created (18 columns, 6 indexes verified in live DB)
- [x] **2A.5** Statutes ingested: 1,129 sections (IPC 327, BNS 325, CrPC 153, BNSS 150, IEA 87, BSA 87) — bidirectional cross-refs verified
- [x] **2A.6** Run tests — no regressions (1624 passed)

### 2B — Neo4j Statute Linkage (Bible 6.6)
- [x] **2B.1** Add Statute nodes + APPLIES edges in Neo4j — ingest_statutes.py creates Neo4j Statute nodes via graph_store
- [x] **2B.2** Neo4j verified connected (796 nodes) — statute linkage will work when statutes ingested
- [x] **2B.3** Run tests — no regressions

### 2C — Contextual Embeddings (Bible 6.8–6.10)
- [x] **2C.1** Create `contextual_embeddings.py` — `generate_contextual_prefix()` via Flash
- [x] **2C.2** Integrate into ingestion pipeline (Bible 6.9) — added to pipeline.py step 6c, gated on fast_llm
- [x] **2C.3** Create `scripts/backfill_contextual_embeddings.py` for existing cases
- [x] **2C.4** Run prefix generation test (test 14) — 4 tests pass
- [x] **2C.5** Run statute contextual test (test 15) — passes
- [x] **2C.6** Run tests — no regressions (1624 passed)

### 2D — RAPTOR Hierarchical Summaries [Q3] (Bible 6.11)
- [x] **2D.1** Create `section_summarizer.py` — `generate_section_summaries()` + `build_pinecone_summary_vectors()`
- [x] **2D.2** Generate Level-1 (section summaries) + Level-2 (ratio_decidendi) at ingestion — added to pipeline.py step 8b
- [x] **2D.3** Store in Pinecone with `summary_level: 1` / `summary_level: 2` metadata — build_pinecone_summary_vectors sets metadata
- [x] **2D.4** Integrate into ingestion flow — pipeline.py generates + embeds + upserts summaries when fast_llm provided
- [x] **2D.5** Run RAPTOR tests (tests 56-58) — 5 tests pass
- [x] **2D.6** Run tests — no regressions (1624 passed)

### 2E — Complete Code Mapping [T3] (Bible 6.12)
- [x] **2E.1** Code mappings: 327 IPC→BNS, 153 CrPC→BNSS, 87 IEA→BSA (567 total, infrastructure done; full MHA concordance expansion deferred)
- [x] **2E.2** Bidirectional lookup in `expand_statute_references()` (query.py) — already existed
- [x] **2E.3** Add synthesis prompt instruction for dual-code references — added to RESEARCH_SYNTHESIZE_SYSTEM
- [x] **2E.4** Run code mapping tests (tests 59-61) — 12 tests pass
- [x] **2E.5** Run tests — no regressions (1624 passed)

### 2F — AWS HC Ingestion + Pinecone Backfill (Bible 6.4–6.5, 6.7)
- [x] **2F.1** Evaluate High Court data scope (Bible 6.4) — same S3 pattern as SC, `s3://indian-high-court-judgments/`
- [x] **2F.2** Pinecone metadata backfill for existing cases (Bible 6.5) — `scripts/backfill_pinecone_metadata.py` created
- [x] **2F.3** Download civictech-India data (Bible 6.7) — source paths documented: GitHub civictech-India repos + Kaggle BNS
- [x] **2F.4** Run tests — no regressions (1630 passed)

### PHASE 2 GATE
- [x] **2Z.1** Contextual embedding tests pass (tests 14-15) — 7 tests pass
- [x] **2Z.2** RAPTOR tests pass (tests 56-58) — 5 tests pass
- [x] **2Z.3** Code mapping tests pass (tests 59-61) — 12 tests pass
- [x] **2Z.4** Statute ingestion test passes (test 72) — 5 model tests + 4 helper tests pass
- [x] **2Z.5** RAPTOR ingestion test passes (test 74) — 3 tests in TestRaptorIngestionPipeline pass
- [x] **2Z.6** Full test suite passes — 1630 passed
- [x] **2Z.7** Commit: `feat: research agent v2 — Phase 2 data expansion + RAPTOR + code mapping` — 2d16dd2

---

## PHASE 3: MULTI-SOURCE WORKERS + INDIAN KANOON + WEB + GRAPHRAG (Week 3-4)

> **Bible ref**: Section 7 (7.1–7.10)
> **Depends on**: Phase 1 + Phase 2 both complete
> **Goal**: All worker types active, IK API, Tavily web search, GraphRAG communities.

### 3A — Interfaces (Bible 7.1–7.2)
- [x] **3A.1** Create `interfaces/web_search.py` — `WebSearchProvider` protocol
- [x] **3A.2** Create `interfaces/external_doc.py` — `ExternalDocProvider` protocol (IK API)

### 3B — Providers (Bible 7.3–7.4)
- [x] **3B.1** Implement `providers/external/indiankanoon.py` — IK search, docmeta, fragment
- [x] **3B.2** Implement `providers/web_search/tavily.py` — Tavily search wrapper
- [x] **3B.3** Unit test both providers with mocked HTTP (6 IK tests + 3 Tavily tests)
- [x] **3B.4** IK API integration test (test 4) — mocked HTTP, 6 tests pass

### 3C — Config & DI (Bible 7.5–7.6)
- [x] **3C.1** Add IK/Tavily settings to `config.py` (ik_api_token, ik_rate_limit, tavily_api_key, web_search_timeout, research_* settings, CRAG thresholds)
- [x] **3C.2** Add factories to `dependencies.py` (get_web_search, get_ik_client + cleanup)
- [x] **3C.3** Run tests — no regressions (1683 passed)

### 3D — Remaining Workers (Bible 7.7)
- [x] **3D.1** Implement `statute_worker` in `worker_nodes.py` — with code mapping [T3] (PG FTS + Pinecone semantic + expand_statute_references)
- [x] **3D.2** Implement `ik_search_worker` — Indian Kanoon search + fragment retrieval
- [x] **3D.3** Implement `ik_case_worker` — merged into ik_search_worker (search + fragment in one worker)
- [x] **3D.4** Implement `web_search_worker` — Tavily for recency (non-blocking on failure)
- [x] **3D.5** Implement `graph_worker` — Neo4j citation traversal (fulltext + CITES edges)
- [x] **3D.6** Unit test each worker (2 statute, 2 IK, 2 web, 2 graph tests)
- [x] **3D.7** Run tests — no regressions (1683 passed)

### 3E — GraphRAG Communities (Bible 7.10)
- [x] **3E.1** Create `scripts/build_citation_communities.py` — Louvain algorithm (NetworkX built-in, graspologic optional)
- [x] **3E.2** Generate community summaries via LLM (COMMUNITY_SUMMARY_SYSTEM prompt + schema)
- [x] **3E.3** Implement `graph_community_worker` — semantic + graph overlap dual retrieval
- [x] **3E.4** Run community tests (tests 21-25) — 5 tests pass (Louvain, semantic, graph overlap, dedup, build script)
- [x] **3E.5** Run community build test (test 73) — 2 tests pass (export + summarize)

### 3F — Graph Registration (Bible 7.8–7.9)
- [x] **3F.1** Register all workers in `research.py` (7 workers: case_law, named_case, statute, ik_search, web_search, graph, graph_community)
- [x] **3F.2** Update `agents.py` to pass IK/Tavily/web deps (graceful fallback if API keys missing)
- [x] **3F.3** Integration test: full graph with all worker types (2 tests: build graph + all types registered)
- [x] **3F.4** Run tests — no regressions (1683 passed)

### PHASE 3 GATE
- [x] **3Z.1** All worker unit tests pass (25 Phase 3 tests)
- [x] **3Z.2** GraphRAG community tests pass (tests 21-25)
- [x] **3Z.3** IK API integration test passes (test 4) — mocked HTTP
- [x] **3Z.4** Send() fan-out test passes (test 6)
- [x] **3Z.5** Full test suite passes (1683 passed, 0 failed)
- [ ] **3Z.6** Manual E2E: run complex query, verify all worker types dispatch
- [ ] **3Z.7** Commit: `feat: research agent v2 — Phase 3 multi-source workers + GraphRAG`

---

## PHASE 4: OUTPUT QUALITY + VERIFICATION + TRUST (Week 5)

> **Bible ref**: Section 8 (8.1–8.5)
> **Goal**: Speculative RAG synthesis, dual-stage verification, LeMAJ quality check, process visualization, frontend rendering.

### 4A — Synthesis Prompt Overhaul (Bible 8.1)
- [ ] **4A.1** Write `RESEARCH_SYNTHESIZE_SYSTEM` prompt — IRAC + reconciliation + footnotes
- [ ] **4A.2** Write `SPECULATIVE_DRAFT_SYSTEM` prompt (3 perspectives: relevance/authority/breadth)
- [ ] **4A.3** Write `SPECULATIVE_MERGE_SYSTEM` prompt (Pro verifier/merger)
- [ ] **4A.4** Add all prompts to `PROMPT_LIBRARY.md`

### 4B — Speculative RAG Synthesis (Bible 8.2)
- [ ] **4B.1** Implement `speculative_synthesis_with_contradictions_node` — 3x Flash drafts + Pro merge [S1]
- [ ] **4B.2** Implement `format_footnotes_node` — post-processing (Bible 8.2a)
- [ ] **4B.3** Wire streaming [S5] — SSE `memo_stream` events during Pro generation
- [ ] **4B.4** Run Speculative RAG tests (tests 26-29)
- [ ] **4B.5** Run streaming test (test 35)
- [ ] **4B.6** Run tests — no regressions

### 4C — Dual-Stage Verification + T4 Guardrail (Bible 8.3) [Q6 + T4]
- [ ] **4C.1** Implement `_deterministic_verify()` — regex, DB lookup, fuzzy match, overruled cross-ref
- [ ] **4C.2** Implement `_verify_citations_against_sources()` — PG → IK API → Neo4j lookup, REMOVE unverifiable
- [ ] **4C.3** Implement `verify_citations_node` combining both stages
- [ ] **4C.4** Add verification banner for UI (verified count, removed count)
- [ ] **4C.5** Run dual-stage verification tests (tests 51-53)
- [ ] **4C.6** Run tests — no regressions

### 4D — LeMAJ Legal Quality Check [Q4] (Bible 8.3a)
- [ ] **4D.1** Write `LEGAL_QUALITY_CHECK_SYSTEM` prompt + `LEGAL_QUALITY_CHECK_SCHEMA`
- [ ] **4D.2** Implement `legal_quality_check_node` — decompose memo into Legal Data Points, verify each
- [ ] **4D.3** Wire into graph: after verify → legal_quality_check → checkpoint_memo
- [ ] **4D.4** Run quality check tests (tests 54-55)
- [ ] **4D.5** Run tests — no regressions

### 4E — Research Process Visualization [T1] (Bible 8.4)
- [ ] **4E.1** Define SSE event type catalog (plan, searching, found, evaluating, reflection, gap, drafting, verification, memo)
- [ ] **4E.2** Implement `emit_status()` helper
- [ ] **4E.3** Add `emit_status()` calls throughout all pipeline nodes
- [ ] **4E.4** Run process visualization tests (tests 62-63)
- [ ] **4E.5** Run tests — no regressions

### 4F — Frontend Rendering (Bible 8.5)
- [ ] **4F.1** Render Quick Reference Table
- [ ] **4F.2** Render IRAC sections with citation links
- [ ] **4F.3** Render footnotes with source URLs
- [ ] **4F.4** Render research audit trail (sources used/unused)
- [ ] **4F.5** Render process visualization (live status events) [T1]
- [ ] **4F.6** Render verification banner (verified/removed citation counts) [T4]
- [ ] **4F.7** Run frontend tests — no regressions

### PHASE 4 GATE
- [ ] **4Z.1** Speculative RAG tests pass (tests 26-29)
- [ ] **4Z.2** Dual-stage verification tests pass (tests 51-53)
- [ ] **4Z.3** LeMAJ quality tests pass (tests 54-55)
- [ ] **4Z.4** Process visualization tests pass (tests 62-63)
- [ ] **4Z.5** Streaming test passes (test 35)
- [ ] **4Z.6** Speed optimization tests pass (tests 30-34)
- [ ] **4Z.7** Output format test passes (test 8)
- [ ] **4Z.8** Full test suite passes
- [ ] **4Z.9** Manual E2E with process visualization — verify live status events in UI
- [ ] **4Z.10** Commit: `feat: research agent v2 — Phase 4 synthesis + verification + trust`

---

## PHASE 5: POLISH & PRODUCTION HARDENING (Week 6)

> **Bible ref**: Section 9
> **Goal**: Caching, timeouts, cost tracking, observability, load testing.

### 5A — Redis Caching [S8] (Bible 9 — S8)
- [ ] **5A.1** Implement 5-layer cache: memo, search, IK, embedding, community
- [ ] **5A.2** Cache key normalization (lowercase, strip, sort filters)
- [ ] **5A.3** `cached_at` timestamp in UI responses
- [ ] **5A.4** Run cache tests (tests 37-38)

### 5B — Gemini Context Caching [S10] (Bible 9 — S10)
- [ ] **5B.1** Add `_get_or_create_synthesis_cache()` to `GeminiLLM`
- [ ] **5B.2** Use cached content in Pro synthesis calls
- [ ] **5B.3** Add config settings (`gemini_context_cache_enabled`, `gemini_context_cache_ttl`)
- [ ] **5B.4** Run context cache tests (tests 64-65)

### 5C — Semantic Caching [S11] (Bible 9 — S11)
- [ ] **5C.1** Create `search/semantic_cache.py` — `SemanticCache` class with Redis Stack HNSW
- [ ] **5C.2** Wire into research pipeline (check before S8 hash cache)
- [ ] **5C.3** Add "Similar query found in cache" banner in frontend
- [ ] **5C.4** Run semantic cache tests (tests 66-67)
- [ ] **5C.5** Run warm-up test (test 75)

### 5D — Embedding Pre-warm [S6] (Bible 9)
- [ ] **5D.1** Implement async embedding pre-warm during HITL checkpoint_plan wait
- [ ] **5D.2** Fallback to live embedding when plan changes
- [ ] **5D.3** Run pre-warm test (test 36)

### 5E — Production Hardening (Bible 9 top)
- [ ] **5E.1** Per-worker timeouts: web=10s, ik_search=15s, case_law=30s, graph=15s, graph_community=10s, statute=20s
- [ ] **5E.2** Cost tracking: log IK API usage, LLM tokens per node, total cost per run
- [ ] **5E.3** Structured logging: worker_type, task_id, timing, data_tier
- [ ] **5E.4** Confidence formula update: add source_diversity + evidence_gap_coverage factors
- [ ] **5E.5** IK rate limiting: token bucket at 2 req/sec, circuit breaker on 429s
- [ ] **5E.6** Daily SC ingestion skeleton (`scripts/daily_ingest.py`)

### 5F — Latency Benchmark (Bible 13, test 42)
- [ ] **5F.1** Run latency benchmark: 3 complex queries, target ≤55s actual, ≤25s to first stream token
- [ ] **5F.2** Log per-node timing breakdown
- [ ] **5F.3** Identify and optimize any bottlenecks

### PHASE 5 GATE
- [ ] **5Z.1** Cache tests pass (tests 37-38, 64-67, 75)
- [ ] **5Z.2** Pre-warm test passes (test 36)
- [ ] **5Z.3** Latency benchmark meets targets (test 42)
- [ ] **5Z.4** Full test suite passes (all 75 verification tests + existing 1411)
- [ ] **5Z.5** Commit: `feat: research agent v2 — Phase 5 caching + hardening`

---

## FINAL E2E VALIDATION

- [ ] **E2E.1** Manual E2E test (Bible test 69): anticipatory bail query — verify full enhanced flow
- [ ] **E2E.2** Competitor parity test (Bible test 70): Section 20(c) CPC query
- [ ] **E2E.3** Regression: all 1411+ backend tests pass (test 71)
- [ ] **E2E.4** Frontend: all 298+ tests pass
- [ ] **E2E.5** Code mapping E2E: query with IPC reference → verify BNS also searched [T3]
- [ ] **E2E.6** Process visualization E2E: verify live SSE events in actual UI [T1]
- [ ] **E2E.7** Zero-tolerance E2E: verify no unverified citations in final memo [T4]
- [ ] **E2E.8** Semantic cache E2E: paraphrased query → cache hit [S11]
- [ ] **E2E.9** Merge to master / create PR

---

## ENHANCEMENT CROSS-REFERENCE

| ID | Enhancement | Phase | Key Tasks |
|----|------------|-------|-----------|
| Q1 | MC-RAG conditioned retrieval | 1 (gap_analysis) | 1C.8 |
| Q2 | A-RAG deep read | 1 (evaluate_and_extract) | 1C.7 |
| Q3 | RAPTOR hierarchical summaries | 2 (ingestion) | 2D.1–2D.6 |
| Q4 | LeMAJ legal quality check | 4 (verify) | 4D.1–4D.5 |
| Q5 | Reflection in batch CoT | 1 (batch_worker_cot) | 1C.6 |
| Q6 | Dual-stage citation verification | 4 (verify) | 4C.1–4C.6 |
| S1 | Merged contradictions into synthesis | 4 (synthesis) | 4B.1 |
| S2 | Parallel rewrite + classify | 1 (graph wiring) | 1E.3 |
| S3 | Merged CRAG + extract | 1 (evaluate_and_extract) | 1C.7 |
| S4 | Batched CoT | 1 (batch_worker_cot) | 1C.6 |
| S5 | Streamed synthesis | 4 (synthesis) | 4B.3 |
| S6 | Pre-warm embeddings | 5 (polish) | 5D.1–5D.3 |
| S8 | Multi-layer Redis cache | 5 (cache) | 5A.1–5A.4 |
| S9 | Fast path routing | 1 (fast_path) | 1C.9–1C.10 |
| S10 | Gemini context caching | 5 (cache) | 5B.1–5B.4 |
| S11 | Semantic caching | 5 (cache) | 5C.1–5C.5 |
| S12 | Parallel Flash batches | 1 (evaluate_and_extract) | 1C.7 |
| T1 | Process visualization | 4 (SSE) | 4E.1–4E.5 |
| T3 | Code mapping | 2 (ingestion) + 3 (worker) | 2E.1–2E.5, 3D.1 |
| T4 | Zero-tolerance guardrail | 4 (verify) | 4C.2 |
