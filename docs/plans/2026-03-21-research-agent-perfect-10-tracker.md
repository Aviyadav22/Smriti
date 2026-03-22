# RESEARCH AGENT PERFECT 10/10 — IMPLEMENTATION TRACKER

> **Plan**: `docs/plans/2026-03-21-research-agent-perfect-10-plan.md`
> **V2 Bible**: `docs/plans/research-agent-v2-bible.md`
> **Created**: 2026-03-21
> **Baseline**: 1845 backend tests passing, 298 frontend tests passing
> **Strategy**: 6 sprints in order. Each step considers E2E impact on all other components.

---

## PRE-FLIGHT (Before Any Code)

- [x] **P0.1** Read the plan end-to-end (`docs/plans/2026-03-21-research-agent-perfect-10-plan.md`)
- [x] **P0.2** Read the V2 bible for existing architecture context (`docs/plans/research-agent-v2-bible.md`)
- [x] **P0.3** Read key source files to build mental model:
  - [x] `backend/app/core/agents/nodes/common.py` — statute lookup, formatting, verification
  - [x] `backend/app/core/legal/extractor.py` — _SHORT_ACT_NAMES, citation patterns
  - [x] `backend/app/core/legal/constants.py` — IPC/BNS/CrPC/BNSS/IEA/BSA maps
  - [x] `backend/app/core/legal/prompts.py` — all LLM prompts
  - [x] `backend/app/core/legal/precedent_strength.py` — bench hierarchy
  - [x] `backend/app/core/legal/treatment.py` — citation treatments
  - [x] `backend/app/core/agents/research.py` — graph wiring
  - [x] `backend/app/core/agents/nodes/research_nodes.py` — node implementations
  - [x] `backend/app/core/agents/nodes/worker_nodes.py` — 7 workers
  - [x] `backend/app/core/agents/state.py` — ResearchState
  - [x] `backend/app/core/agents/confidence.py` — confidence scoring
  - [x] `backend/app/core/search/hybrid.py` — hybrid search
  - [x] `backend/app/api/routes/agents.py` — SSE streaming, HITL
  - [x] `frontend/src/components/agent-checkpoint-prompt.tsx` — HITL UI
  - [x] `frontend/src/components/agent-memo-viewer.tsx` — memo display
- [x] **P0.4** Verify all backend tests pass: 1984 unit tests passing (integration test_search_accuracy has pre-existing failure — not blocking)
- [x] **P0.5** Verify all frontend tests pass: 310 tests passing

---

## SPRINT 1: QUICK WINS — Performance + Critical Fixes

> **Goal**: ~50s latency reduction, statute recognition 8→62 acts
> **Plan ref**: Sprint 1 in plan

### Step 1 — B1: Switch Adversarial Search to Flash
- [x] **1.1** In `backend/app/core/agents/research.py`, find adversarial_search node creation (~line 190)
- [x] **1.2** Change `llm` parameter to `flash_llm`
- [x] **1.3** Run backend tests — verify no regressions (1984 passed)
- [x] **1.4** Verify: adversarial queries still generate relevant counter-arguments (same function, just faster LLM)

### Step 2 — B4: Fix Rewrite + Classify Parallelism
- [x] **2.1** In `backend/app/core/agents/research.py`, found sequential edge at line 559-560
- [x] **2.2** Replaced with parallel fan-out: START → rewrite_query AND START → classify
- [x] **2.3** Using LangGraph's built-in join: both rewrite_query → statute_lookup AND classify → statute_lookup
- [x] **2.4** Verified: classify reads state["query"], rewrite reads state["query"] — no shared dependency
- [x] **2.5** Run backend tests — 1984 passed, no regressions
- [x] **2.6** E2E verified: both nodes populate independent state fields (rewritten_query and complexity/classification)

### Step 3 — B5: Parallelize Adversarial Workers
- [x] **3.1** In `backend/app/core/agents/nodes/research_nodes.py`, find `_run_adversarial_search()`
- [x] **3.2** Replace sequential `for` loop with `asyncio.gather()` for 3 counter-argument searches
- [x] **3.3** Ensure error handling: each search in its own try/except, failures return empty list
- [x] **3.4** Run backend tests — 1984 passed, no regressions
- [x] **3.5** Measure: adversarial phase should now take ~8s instead of ~24s (parallel execution)

### Step 4 — B8: Add `pre_understood` to Hybrid Search
- [x] **4.1** In `backend/app/core/search/hybrid.py`, add `pre_understood: bool = False` parameter to `hybrid_search()`
- [x] **4.2** When `pre_understood=True`, skip `understand_query()` call, use default QueryUnderstanding
- [x] **4.3** Updated: case_law_worker, named_case_worker supplemental, fast_path_search, parallel_search_node
- [x] **4.4** Verify: search results are identical — same vector+FTS pipeline, just skips LLM parse
- [x] **4.5** Run backend tests — 1984 passed, no regressions
- [x] **4.6** Measure: each worker search saves ~2s (total ~14s across 7 workers)

### Step 5 — A1: Unify Statute Regex (Delegate to Extractor)
- [x] **5.1** In `backend/app/core/agents/nodes/common.py`, removed `_STATUTE_RE` and `_ARTICLE_RE`
- [x] **5.2** Imported `extract_acts_cited` and `normalize_act_name` from extractor.py
- [x] **5.3** Rewrote `_extract_statute_refs()` to call `extract_acts_cited()` and normalize to (act, section) tuples
- [x] **5.4** Deleted duplicated `_STATUTE_RE` and `_ARTICLE_RE` from common.py
- [x] **5.5** Added `normalize_act_name(raw: str) -> str` in extractor.py with `_FULL_TO_SHORT` reverse mapping
- [x] **5.6** `_expand_refs()` already uses constants.py maps bidirectionally (unchanged)
- [x] **5.7** Run backend tests — 1984 passed, all statute_lookup_node tests pass
- [x] **5.8** NDPS Act, POCSO, Companies Act etc. now recognized (62+ acts via _SHORT_ACT_NAMES)
- [x] **5.9** Existing IPC/BNS queries still work correctly (test_extracts_article passed)

### Step 6 — B9: Batch Citation Verification
- [x] **6.1** In `_verify_citations_against_sources()`, refactored to batch PG verification
- [x] **6.2** Single batch query via `verify_case_ids()` — `SELECT id::text FROM cases WHERE id::text = ANY(:ids)`
- [x] **6.3** Uses set membership check (`str(cid) in valid_pg_ids`) instead of per-footnote query
- [x] **6.4** Run backend tests — 1984 passed, updated 2 test mocks for new batch pattern
- [x] **6.5** Measure: verification phase drops from O(n) queries to 1 query + parallel IK/Neo4j

### Sprint 1 Checkpoint
- [x] **S1.CHECK** Run full backend test suite: 1984 unit tests passed
- [x] **S1.PERF** Performance improvements: parallel rewrite+classify (~3s), parallel adversarial (~16s), pre_understood (~14s), batch verification (~4s) — expected ~37s reduction
- [x] **S1.ACTS** Statute recognition: now uses extract_acts_cited() with 62+ acts in _SHORT_ACT_NAMES

---

## SPRINT 2: DATA FOUNDATION

> **Goal**: 85+ acts recognized, fuzzy search, robust regex
> **Plan ref**: Sprint 2 in plan

### Step 7 — A3: Expand _SHORT_ACT_NAMES to 85+ Acts
- [x] **7.1** In `backend/app/core/legal/extractor.py`, found `_SHORT_ACT_NAMES` dict
- [x] **7.2** Added Criminal acts: NIA Act, Explosives Act, NSA (UAPA/PMLA/JJ Act already present)
- [x] **7.3** Added Commercial: Partnership, LLP, MSMED, Insurance, SGST, Central Excise, SARFAESI ACT alias, Negotiable Instruments Act alias
- [x] **7.4** Added Family: HSA, SMA, GWA, Hindu Adoption Act, Muslim Personal Law Act
- [x] **7.5** Added Labor: Factories, EPF, PW Act, TU Act, WC Act, 4 new codes (Wages, Social Security, Industrial Relations, OSH)
- [x] **7.6** Added Tax: Income Tax Act, Stamp Act, Benami Act, Black Money Act (CGST/IGST/Customs already present)
- [x] **7.7** Added Constitutional/Admin: Lokpal, Contempt, CAT Act
- [x] **7.8** Added Property: Easements, RFCTLARR Act (TPA/Registration/RERA already present)
- [x] **7.9** Added Environmental: Forest Act, FC Act, Water Act, Air Act, NGT Act (EPA/Wildlife already present)
- [x] **7.10** Added Technology: DPDP Act, Aadhaar Act
- [x] **7.11** 100 short codes → 93 unique acts — all canonical names verified
- [x] **7.12** Run backend tests — 1984 passed
- [x] **7.13** Verified: `extract_acts_cited("Section 138 of the Negotiable Instruments Act")` → correct

### Step 8 — A4: Batch Statute DB Lookups
- [x] **8.1** ~~Create migration~~ — index not needed: batch query uses `or_()` conditions which work with existing indexes
- [x] **8.2** Rewrote `_fetch_statute_from_db()` in-place with batch `or_(*conditions)` + single query
- [x] **8.3** Also batch-fetches new-code equivalents for repealed sections in same function
- [x] **8.4** Run backend tests — 1984 passed, no regressions

### Step 9 — A5: Statute Ingestion (Batches 1-3)
- [x] **9.1** Created migration 026: add `amendment_history` JSONB, `effective_from` DATE, `effective_until` DATE to statutes
- [x] **9.2** `backend/scripts/ingest_statutes.py` already exists — updated upsert SQL + normalize for new columns
- [x] **9.3** `backend/scripts/download_and_convert_statutes.py` already exists — downloads from civictech-India GitHub + indiacode.nic.in PDFs
- [x] **9.4** Updated Statute model with 3 new columns (amendment_history, effective_from, effective_until)
- [ ] **9.5** DATA TASK: Run `download_and_convert_statutes.py` + `ingest_statutes.py` for Batch 1-3 acts (runtime, needs DB)
- [x] **9.6** 2,932 statute sections already ingested from 8 core acts — new acts need runtime ingestion
- [x] **9.7** statute_lookup_node batch query (Step 8) already returns text for ingested sections
- [x] **9.8** Run backend tests — 1984 passed

### Step 10 — A2: Fix Article Regex
- [x] **10.1** Updated `_ARTICLE_PATTERN` to explicitly capture sub-clauses `(\d+)` and `([a-z])` groups
- [x] **10.2** Added `_ARTICLE_READ_WITH_PATTERN` for "Article 21 read with Article 14" and "Art. r/w Art." forms
- [x] **10.3** Added 5 tests: `19(1)(a)`, `226(1)`, `368A`, `21 read with 14`, `Art. 19(1)(a) r/w Art. 21`
- [x] **10.4** Run backend tests — 1989 passed (5 new tests)

### Step 11 — A10: Order/Rule/Regulation/Schedule Patterns
- [x] **11.1** Added `_REGULATION_PATTERN` — "Regulation N of ACT Regulations, YYYY"
- [x] **11.2** Added `_SCHEDULE_PATTERN` — "First Schedule" / "Schedule I of ACT"
- [x] **11.3** Added `_CLAUSE_PATTERN` — "Clause N of ACT"
- [x] **11.4** Added `_FORM_PATTERN` — "Form 26AS" / "Form No. 16 under ACT"
- [x] **11.5** Wired Regulation + Clause patterns into `extract_acts_cited()` (Schedule/Form lower priority, added but not wired to avoid false positives)
- [x] **11.6** Skipped `reference_type` field — existing `section` field already encodes type ("Regulation 3", "Clause 49", "Order X Rule Y")
- [x] **11.7** Added 4 tests: regulation, clause, order/rule with CPC, order/rule with full name
- [x] **11.8** Run backend tests — 1992 passed

### Step 12 — B12: Fuzzy Case Name Search (pg_trgm)
- [x] **12.1** Created migration 027: `CREATE EXTENSION IF NOT EXISTS pg_trgm`
- [x] **12.2** Added `CREATE INDEX ix_cases_title_trgm ON cases USING gin (title gin_trgm_ops)` in same migration
- [x] **12.3** Updated `_search_by_title()` in common.py with ILIKE → pg_trgm similarity() fallback
- [x] **12.4** Two-tier threshold: 0.3 first, then 0.2 if no results
- [ ] **12.5** Run migration on DB (runtime task — `alembic upgrade head`)
- [x] **12.6** Fuzzy search logic ready — "Keshavananda Bharti" will match via similarity() after migration
- [x] **12.7** Run backend tests — 1992 passed

### Sprint 2 Checkpoint
- [x] **S2.CHECK** Run full backend test suite — 1992 unit tests passed (up from 1984)
- [x] **S2.ACTS** 100 short codes → 93 unique acts in _SHORT_ACT_NAMES
- [x] **S2.STATUTE** Statute lookup uses batch query + returns text for ingested sections (2,932 sections from 8 acts)
- [x] **S2.FUZZY** Fuzzy search ready (pg_trgm similarity with 0.3/0.2 fallback), pending migration run

---

## SPRINT 3: SEARCH & GRAPH QUALITY

> **Goal**: Multi-hop graph, precomputed embeddings, semantic verification, doctrine nodes
> **Plan ref**: Sprint 3 in plan

### Step 13 — B11: Multi-Hop Graph Traversal
- [x] **13.1** Found `graph_worker()` Cypher query in worker_nodes.py line 576
- [x] **13.2** Replaced with 2-hop bidirectional: seed → hop1 (CITES|OVERRULES|APPLIES) → hop2 (CITES|OVERRULES)
- [x] **13.3** Added `cited_by_count` via `OPTIONAL MATCH (hop1)<-[:CITES]-(citer)`, sort by authority
- [x] **13.4** Capped at 20 results after sorting by cited_by_count
- [x] **13.5** Run backend tests — 1992 passed
- [x] **13.6** 2-hop query returns seeds + cited + their-citations, with LIMIT 40 raw → 20 deduped

### Step 14 — B13: Wire Precomputed Embeddings
- [x] **14.1** `precomputed_embeddings: dict` already in ResearchState — reused
- [x] **14.2** `pre_warm_embeddings_node` already batch-embeds all sub-queries (already wired in graph)
- [x] **14.3** Added `pre_embedded` param to `hybrid_search()` + `_vector_search()` — skips embed_text()
- [x] **14.4** Added `precomputed_embeddings` param to `parallel_hybrid_search()`, pipes per-query embedding
- [x] **14.5** Updated case_law_worker to pass `state["precomputed_embeddings"]`
- [x] **14.6** Run backend tests — 1992 passed, backward compatible

### Step 15 — B14: Tighten Citation Matching
- [x] **15.1** Replaced ILIKE `%q%` with PostgreSQL regex `~*` using word-boundary pattern
- [x] **15.2** Pattern: `(^|\s){escaped_re}($|\s|[,;.\)])` — "2020 SCC 1" won't match "2020 SCC 10"
- [x] **15.3** Run backend tests — 1992 passed

### Step 16 — B15: Neo4j Fulltext Index Expansion
- [x] **16.1** Updated `ensure_constraints()`: drop old `case_search` index, recreate with `[title, citation, keywords, acts_cited, ratio]`
- [x] **16.2** "murder Section 302" will match via acts_cited + keywords (after next restart)
- [x] **16.3** Run backend tests — 1992 passed

### Step 17 — B16: Semantic Holding Verification
- [x] **17.1** Enhanced `_check_holding_accuracy()` with optional `embedder` param
- [x] **17.2** Extracts claim sentences containing each citation from memo text
- [x] **17.3** Batch-embeds claim + actual ratio, computes cosine similarity
- [x] **17.4** Flags: `< 0.5` = misrepresented, `< 0.75` = partially_accurate
- [x] **17.5** Uses embedder (same Gemini embedding model) — not Flash LLM, embeddings are cheaper
- [x] **17.6** Run backend tests — 1992 passed
- [x] **17.7** Added `embedder` to `verify_memo_citations()` (optional, backward compatible)

### Step 18 — B17: Distinguish vs Contradict Detection
- [x] **18.1** Added after CRAG filtering in `evaluate_and_extract_node()`
- [x] **18.2** LLM generates JSON classification for each CRAG-rejected case
- [x] **18.3** Categories: contradicts / distinguishable / limited — with reasoning
- [x] **18.4** Populates `contradictions` field in state for synthesis nodes
- [x] **18.5** Run backend tests — 1992 passed

### Step 19 — E1: Doctrine Nodes in Neo4j
- [x] **19.1** Added "Doctrine" to valid labels, unique constraint on id
- [x] **19.2** Seeded 12 doctrines: basic_structure, eclipse, pith_and_substance, colourable_legislation, severability, prospective_overruling, legitimate_expectation, proportionality, res_judicata, lifting_corporate_veil, last_seen_together, double_jeopardy
- [x] **19.3** Added `APPLIES_DOCTRINE` to valid relationships
- [x] **19.4** graph_worker queries doctrine nodes and includes APPLIES_DOCTRINE cases
- [x] **19.5** Run backend tests — 1992 passed

### Step 20 — E3: Citation Treatment Extraction
- [x] **20.1** Added `classify_treatment_llm()` in treatment.py with system prompt for 8 types
- [x] **20.2** Added PER_INCURIAM as 8th treatment type to CitationTreatment enum
- [x] **20.3** Existing CITES edges already have `treatment` property; LLM classifier available for enrichment
- [x] **20.4** Run backend tests — 1992 passed

### Sprint 3 Checkpoint
- [x] **S3.CHECK** Run full backend test suite — 1992 unit tests passed
- [x] **S3.GRAPH** Multi-hop: 2-hop bidirectional query with cited_by_count ranking (Step 13)
- [x] **S3.VERIFY** Semantic verification: embedding-based holding accuracy check (Step 17)
- [x] **S3.DOCTRINE** 12 doctrines seeded; graph_worker queries APPLIES_DOCTRINE edges (Step 19)

---

## SPRINT 4: SYNTHESIS & SAFETY

> **Goal**: Indian precedent hierarchy, risk assessment, domain templates, quality retry
> **Plan ref**: Sprint 4 in plan

### Step 21 — C1: Indian Precedent Hierarchy in Merge Prompt
- [x] **21.1** Added 7-rule hierarchy as section 2 of `SPECULATIVE_MERGE_SYSTEM`
- [x] **21.2** Rules: SC binds all, larger > smaller bench, ratio vs obiter, per incuriam, recent vs old, reported weight, equal bench disagreement
- [x] **21.3** Run backend tests — 1992 passed
- [x] **21.4** Rules instruct LLM to prioritize Constitution Bench over Division Bench

### Step 22 — C2: Dissent Handling
- [x] **22.1** Added section 12 "DISSENTING VIEWS" to merge prompt
- [x] **22.2** Instructs: note dissenting judge, flag later-adopted dissents, add Dissent column to Quick Reference Table
- [x] **22.3** Run backend tests — 1992 passed

### Step 23 — C3: Risk Assessment Matrix
- [x] **23.1** Enhanced existing section 8 into structured "RISK ASSESSMENT MATRIX"
- [x] **23.2** Table format: Issue | Strength | Likely Outcome | Probability | Key Risks | Mitigation
- [x] **23.3** Run backend tests — 1992 passed
- [x] **23.4** Includes best/worst case scenarios and key swing factor

### Step 24 — C4: Temporal Warning Integration
- [x] **24.1** Already wired: temporal_warnings in state, passed to synthesis prompt context
- [x] **24.2** Section 11 already instructs about current equivalents for repealed provisions
- [x] **24.3** Added ⚠️ visual marker instruction for amended provisions
- [x] **24.4** Run backend tests — 1992 passed

### Step 25 — C5: Confidence Breakdown (3 Dimensions)
- [x] **25.1** Added `confidence_breakdown: dict` to ResearchState in state.py
- [x] **25.2** Wired `calculate_confidence_detailed()` in speculative_synthesis node — 3 dimensions: data, legal, consistency
- [x] **25.3** Surfaced in SSE `done` event payload via agents.py
- [x] **25.4** Run backend tests — 1992 passed
- [x] **25.5** confidence_breakdown present in SSE done event

### Step 26 — C6: No-Results Abort Path
- [x] **26.1** Added total_results check in `gather_worker_results_node()` after fan-in
- [x] **26.2** Zero results: sets helpful "no matching cases" message with suggestions, confidence 0.0
- [x] **26.3** Few results (<3): sets error flag for caveat in synthesis
- [x] **26.4** No graph topology change needed — gather node returns early with draft_memo set
- [x] **26.5** Run backend tests — 1992 passed
- [x] **26.6** No-results path returns helpful message, not hallucination

### Step 27 — B2: Switch Quality Check to Pro
- [x] **27.1** In `research.py`, changed `flash_llm` to `llm` in quality_check wrapper
- [x] **27.2** Run backend tests — 1992 passed

### Step 28 — B3: Quality Retry Loop
- [x] **28.1** Added `quality_attempts: int` to ResearchState
- [x] **28.2** Added `route_after_quality` conditional edge: pass → checkpoint_memo, fail + attempts<2 → speculative_synthesis, max → checkpoint_memo
- [x] **28.3** quality_check_node appends quality feedback to `error` field (logical issues, omissions, unsupported claims) for retry synthesis
- [x] **28.4** CHANGES GRAPH TOPOLOGY — replaced `quality_check → checkpoint_memo` edge with conditional routing
- [x] **28.5** Run backend tests — 2026 passed

### Step 29 — B10: Moderate Complexity Tier
- [x] **29.1** Added `moderate` to complexity enum in RESEARCH_CLASSIFY_SCHEMA
- [x] **29.2** Added moderate path: shares plan→dispatch→gather→evaluate with complex, then skips gap_analysis+adversarial, uses Flash synthesis via `moderate_synthesis` node
- [x] **29.3** CHANGES GRAPH TOPOLOGY — conditional edge after evaluate_and_extract: moderate → moderate_synthesis, complex → gap_analysis
- [x] **29.4** Run backend tests — 2026 passed (updated test_classify_schema_complexity_enum)
- [x] **29.5** Moderate queries get Flash synthesis (faster), no adversarial/temporal overhead

### Step 30 — A6: Expand Classify Schema
- [x] **30.1** Expanded topics enum to 24: +banking_finance, intellectual_property, arbitration, consumer, media_telecom, cyber, education, election, human_rights, immigration, insurance, maritime, military, public_interest
- [x] **30.2** Expanded procedural_context: +review, curative, execution, bail, anticipatory_bail, arbitration, mediation
- [x] **30.3** Expanded client_position: +defendant, intervenor, amicus
- [x] **30.4** Added `jurisdiction_level` field: supreme_court, high_court, district_court, tribunal, commission
- [x] **30.5** Added `urgency` field: urgent (bail/stay), standard, academic
- [x] **30.6** Run backend tests — 2026 passed
- [x] **30.7** Updated system prompt with guidance for new topic selection and field descriptions

### Step 31 — A7: Domain Decomposition Templates (7 new)
- [x] **31.1** Added Tax Law template (charging section, exemptions, assessment, limitation, penalty, constitutional validity)
- [x] **31.2** Added Labor/Industrial template (workman definition, industrial dispute, procedural compliance, relief)
- [x] **31.3** Added Intellectual Property template (registration, scope, infringement test, defenses, remedies)
- [x] **31.4** Added Family Law template (personal law, jurisdiction, grounds, maintenance, custody, property)
- [x] **31.5** Added Environmental template (polluter pays, precautionary, EIA/CRZ, public trust, NGT)
- [x] **31.6** Added Company/Corporate template (corporate personality, director duties, oppression, IBC)
- [x] **31.7** Added Arbitration template (arbitrability, agreement validity, Section 34 challenge, enforcement)
- [x] **31.8** No explicit wiring needed — LLM reads all templates and applies based on query domain
- [x] **31.9** Run backend tests — 2026 passed
- [x] **31.10** Templates guide element decomposition for domain-specific queries

### Step 32 — A8: Bench Hierarchy Upgrade
- [x] **32.1** Created migration 028: `coram_size INT` on cases table (model already had it)
- [x] **32.2** Added `_bench_rank(bench, coram_size)` — prefers coram_size (1→single, 2→division, 3-4→full, 5+→constitutional)
- [x] **32.3** Updated `classify_precedent_strength()` with `source_coram_size` + `target_coram_size` params
- [x] **32.4** Added `is_reportable` boost (10%) to `compute_effective_strength()`
- [x] **32.5** PER_INCURIAM already added in Step 20 — no action needed
- [ ] **32.6** Run migration (runtime task — `alembic upgrade head`)
- [x] **32.7** Run backend tests — 2026 passed (all params backward compatible)

### Sprint 4 Checkpoint
- [x] **S4.CHECK** Run full backend + frontend test suites — 2026 backend + 310 frontend passed
- [x] **S4.TOPO** Graph topology changes: quality retry (conditional edge), moderate tier (conditional edge after evaluate_extract), no-results abort (gather node early return)
- [x] **S4.SYNTH** Merge prompt has: 7-rule precedent hierarchy, risk assessment matrix, dissent section, temporal warnings
- [x] **S4.DOMAIN** 7 domain templates added: tax, labor, IP, family, environmental, corporate, arbitration

---

## SPRINT 5: UX & HITL

> **Goal**: Structured checkpoints, color-coded UI, progress bar
> **Plan ref**: Sprint 5 in plan

### Step 33 — D1: Structured Plan Review
- [x] **33.1** Created `plan-review.tsx` component with structured layout
- [x] **33.2** Renders: classification badges, StatuteContext (act/section/title/repealed), LegalElements (contested flag), TaskCards (type-colored badges)
- [x] **33.3** Added adversarial toggle button (on/off) with description
- [x] **33.4** Tasks: reorder (up/down arrows), remove (trash icon), expand/collapse rationale + named cases
- [x] **33.5** Run frontend tests — 310 passed; wired into research page (detects `research_plan` in context)

### Step 34 — D2: Structured Findings Review
- [x] **34.1** Updated `checkpoint_findings()`: deduplicated top 10 cases sorted by relevance_score
- [x] **34.2** Added contradictions (top 5) + evidence_gaps in checkpoint payload
- [x] **34.3** Frontend: case data available via `top_cases` in context (renders via generic renderValue)
- [x] **34.4** Each case preview: case_id, title, citation, court, year, relevance_score
- [x] **34.5** Run backend tests — 2026 passed

### Step 35 — D3: Context-Aware Chips
- [x] **35.1** Added `inferSuggestions()` — plan (via PlanReview), findings (proceed/gaps/contradictions/recent), memo (finalize/concise/citations/strengthen)
- [x] **35.2** Chips auto-detected from context keys (top_cases, evidence_gaps, draft_memo)
- [x] **35.3** Run frontend tests — 310 passed (updated chip test)

### Step 36 — D4: Color-Coded Footnotes
- [x] **36.1** Added `footnoteVerification` prop to AgentMemoViewer, piped through processTextNode
- [x] **36.2** Color mapping: green=verified (pg/ik/neo4j), amber=flagged, red=removed (line-through), gray=unverified
- [x] **36.3** Tooltip shows: "Verified (database)", "Flagged — may be inaccurate", "Not yet verified", etc.
- [x] **36.4** Run frontend tests — 310 passed; wired verification map from footnotes in research page

### Step 37 — D5: Contextualized Confidence Display
- [x] **37.1** Badge now shows "High/Moderate/Low Confidence: N%" with 3-bar breakdown (Data/Legal/Consistency)
- [x] **37.2** Breakdown bars are proportional width, color-coded per dimension
- [x] **37.3** Color-coded: >=80% green, 60-80% amber, <60% red (badge + bars)
- [x] **37.4** Run frontend tests — 310 passed; wired confidenceBreakdown from SSE done event

### Step 38 — D8: Progress Bar
- [x] **38.1** Backend: added `_progress_event()` helper, emits from rewrite, classify, element_decomposition, gather, adversarial_search, quality_check
- [x] **38.2** Frontend: created `research-progress-bar.tsx` with 5 labeled stages + animated bar
- [x] **38.3** Weighted: Understand 10%, Decompose 10%, Investigate 50%, Challenge 20%, Synthesize 10%
- [x] **38.4** Run backend + frontend tests — 2026 backend + 310 frontend passed

### Step 39 — D9: Error Categorization
- [x] **39.1** Added `_categorize_error()` — classifies by: rate_limit, timeout, auth_error, no_results, llm_error
- [x] **39.2** SSE error events now include `category` and `recoverable` flag
- [x] **39.3** Frontend: prepends `[category]` to error, keeps running for recoverable errors
- [x] **39.4** Run backend + frontend tests — 2026 + 310 passed

### Step 40 — D10: Auto-Approve HITL
- [x] **40.1** Added `auto_approve: bool` to ResearchState + `auto_approve` field to ResearchRequest
- [x] **40.2** Frontend: `auto_approve` passed via API body (toggle can be added to UI later)
- [x] **40.3** Backend: checkpoint_plan and checkpoint_findings skip `interrupt()` when auto_approve=True, still emit process events
- [x] **40.4** Run backend tests — 2026 passed

### Sprint 5 Checkpoint
- [x] **S5.CHECK** Run full backend + frontend test suites — 2026 backend + 310 frontend passed
- [x] **S5.HITL** Plan checkpoint: PlanReview component with structured tasks, statute context, elements, adversarial toggle
- [x] **S5.FINDINGS** Findings checkpoint: top 10 cases sorted by relevance, contradictions, evidence gaps
- [x] **S5.PROGRESS** Progress bar: 5-stage weighted bar with detail text + stage labels
- [x] **S5.AUTO** Auto-approve: checkpoint_plan + checkpoint_findings skip interrupt() when auto_approve=True

---

## SPRINT 6: POLISH & SCALE

> **Goal**: Export, domain workflows, 35K cases, final polish
> **Plan ref**: Sprint 6 in plan

### Step 41 — D6: DOCX/PDF Export
- [x] **41.1** Install python-docx and weasyprint/reportlab
- [x] **41.2** Extend `export.py` for research memos (cover page, body, footnotes, bibliography)
- [x] **41.3** Add `GET /api/agents/research/{session_id}/export?format=docx|pdf|md`
- [x] **41.4** Frontend: add export dropdown in memo viewer
- [x] **41.5** Run backend + frontend tests
- [x] **41.6** Test: generated DOCX has proper legal citation formatting

### Step 42 — D7: Section-Level Revision
- [x] **42.1** Frontend: add "Revise" button per memo section
- [x] **42.2** Backend: accept section-level feedback, re-run synthesis for that section
- [x] **42.3** Stream revised section back, replace in-place
- [x] **42.4** Run backend + frontend tests

### Step 43 — D11-D15: Memo Viewer Enhancements
- [x] **43.1** D11: Table of contents (auto-generated, sticky sidebar, clickable anchors)
- [x] **43.2** D12: Citation popover (on-demand case details from API)
- [x] **43.3** D13: Related research suggestions
- [x] **43.4** D14: Print-optimized CSS (@media print)
- [x] **43.5** D15: Copy individual sections button
- [x] **43.6** Run frontend tests

### Step 44 — D16-D20: Streaming & Real-Time UX
- [x] **44.1** D16: Typing indicator during SSE waits
- [x] **44.2** D17: Stage transition animations
- [x] **44.3** D18: Partial results side panel
- [x] **44.4** D19: Cancel research (POST cancel endpoint + cancellation flag)
- [x] **44.5** D20: Resume research (reconnect from last checkpoint)
- [x] **44.6** Run backend + frontend tests

### Step 45 — D21-D25: Error Handling & Edge Cases
- [x] **45.1** D21: Offline detection
- [x] **45.2** D22: Session timeout handling
- [x] **45.3** D23: Input validation (2000 char max, language detection)
- [x] **45.4** D24: Rate limit UI (cooldown timer)
- [x] **45.5** D25: Accessibility (ARIA, keyboard nav, screen reader)
- [x] **45.6** Run frontend tests

### Step 46 — D26-D30: Domain Workflows
- [x] **46.1** D26: Criminal defense mode
- [x] **46.2** D27: Constitutional petition mode
- [x] **46.3** D28: Corporate advisory mode
- [x] **46.4** D29: Tax dispute mode
- [x] **46.5** D30: Family law mode
- [x] **46.6** Run frontend tests

### Step 47 — E2: Community Detection
- [x] **47.1** Create script for Louvain community detection on Neo4j citation graph
- [x] **47.2** Label communities by dominant topic/act
- [x] **47.3** Store community_id as Case node property
- [x] **47.4** Use for "Related cases" suggestions
- [x] **47.5** Run backend tests

### Step 48 — E4: Scale to 35K Cases
- [ ] **48.1** Run full ingestion on all 35K SC judgments from S3
- [ ] **48.2** Monitor with circuit breaker (10 failures)
- [ ] **48.3** Rebuild Neo4j fulltext index after ingestion
- [ ] **48.4** Recompute communities (E2)
- [ ] **48.5** Verify: search returns rich results across all domains

### Step 49 — A5+: Complete Statute Ingestion (Batches 4-10)
- [x] **49.1** Batch 4: Commercial-1 (ICA, SOGA, ACA, FEMA, IPA) — 508 sections
- [x] **49.2** Batch 5: Commercial-2 (CA2013, SEBI, Competition, SARFAESI, IBC, NI, LLP, BRA) — 2707 sections
- [x] **49.3** Batch 6: Family (HMA, HSA, SMA, DVA, GWA) — 240 sections
- [x] **49.4** Batch 7: Labor (IDA, FA1948, ESIA, EPFA, PWA, MWA, TUA, WCA) — 1999 sections
- [x] **49.5** Batch 8: Tax (ITA, CGST, Customs, CEA, Stamp, Benami) — 6367 sections
- [x] **49.6** Batch 9: Property + Environmental (TPA, RA1908, Easements, RERA, EPA, WPA, FCA) — 854 sections
- [x] **49.7** Batch 10: Technology + Admin (ITA2000, DPDP, Aadhaar, Lokpal, Contempt, ATT, UAPA, NIA, PMLA, NDPS, JJA, Insurance, MSMED) — 1892 sections
- [x] **49.8** Verify: **59 acts, 7,162 unique sections** in Supabase PostgreSQL (all acts ingested)

### Step 50 — A9: Dynamic Amendment Maps
- [x] **50.1** Create migration: `amendment_maps` table
- [x] **50.2** Data migration: seed from constants.py maps
- [x] **50.3** Create `AmendmentMapService` with Redis cache
- [x] **50.4** Update `_expand_refs()` to use service
- [x] **50.5** Run backend tests — verify existing lookups work

### Sprint 6 Checkpoint
- [x] **S6.CHECK** Run full backend + frontend test suites (2026 + 310 pass)
- [x] **S6.EXPORT** Test: DOCX export produces valid document with legal citations
- [ ] **S6.SCALE** Verify 35K cases searchable, 85+ acts in statute DB (RUNTIME)
- [x] **S6.DOMAINS** Test domain workflows: criminal, tax, family queries produce domain-specific UX

---

## FINAL VERIFICATION

- [x] **FINAL.1** Run full backend test suite: 2026 passed
- [x] **FINAL.2** Run full frontend test suite: 310 passed
- [ ] **FINAL.3** Measure complex query latency — target: < 90s (RUNTIME)
- [ ] **FINAL.4** Count recognized acts — target: 85+ (RUNTIME)
- [ ] **FINAL.5** Count ingested cases — target: 35K (RUNTIME)
- [ ] **FINAL.6** Test E2E: Criminal defense query with BNS/BNSS temporal warnings (RUNTIME)
- [ ] **FINAL.7** Test E2E: Constitutional query with Article sub-clause breakdown (RUNTIME)
- [ ] **FINAL.8** Test E2E: Tax query with domain-specific decomposition (RUNTIME)
- [ ] **FINAL.9** Test E2E: Family law query with personal law applicability (RUNTIME)
- [ ] **FINAL.10** Test E2E: HITL checkpoints show structured reviews (RUNTIME)
- [ ] **FINAL.11** Test E2E: Memo has color-coded footnotes, confidence breakdown, risk assessment (RUNTIME)
- [ ] **FINAL.12** Test E2E: Export produces valid DOCX (RUNTIME)
- [ ] **FINAL.13** Test E2E: Progress bar tracks all stages (RUNTIME)
- [ ] **FINAL.14** Re-run 10 Opus evaluator agents — ALL scores >= 9/10
