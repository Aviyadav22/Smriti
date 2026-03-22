# Research Agent — Perfect 10/10 Upgrade Plan

> **Purpose**: Complete reference for upgrading the research agent from 5.8/10 to 10/10 across all evaluation dimensions.
> **Optimized for**: Claude Opus in ralph loop — contains full context to execute any step cold.
> **Date**: 2026-03-21 | **Project**: Smriti (d:\Startup\Smriti)
> **Tracker**: `docs/plans/2026-03-21-research-agent-perfect-10-tracker.md`
> **V2 Bible**: `docs/plans/research-agent-v2-bible.md` (prior implementation reference)

---

## Context

The Smriti research agent was evaluated by 10 Opus subagents role-playing as different legal professionals (criminal defense, constitutional law, corporate, family law, appellate/SLP practitioners, search quality expert, synthesis expert, HITL/UX expert, safety expert, performance engineer). **Grand average: 5.8/10.** This plan covers ~71 implementation items across 5 categories to bring every score to 10/10.

**Root causes of low scores:**
1. **Data coverage**: Only 8 acts ingested, 796 cases — too thin for real legal research
2. **Statute recognition**: `_STATUTE_RE` in common.py matches only 8 acts despite extractor.py knowing 62
3. **Performance**: ~164s for complex queries; 3 sequential loops that should be parallel
4. **Domain gaps**: No decomposition templates for tax, labor, IP, environmental, family law
5. **UX/HITL**: Raw data dumps at checkpoints, no structured review, no export
6. **Safety**: No semantic holding verification, no distinguish-vs-contradict, quality check uses Flash instead of Pro

---

## CRITICAL: Cross-Cutting Concerns

**Every step MUST consider these E2E effects:**

1. **Test Suite Integrity**: After every step, run `cd backend && python -m pytest tests/ -x -q`. Current baseline: 1845 passing. Never drop below.
2. **Frontend Tests**: After any frontend change, run `cd frontend && npm test`. Current baseline: 298 passing.
3. **State Schema Compatibility**: Any change to `ResearchState` must be backward-compatible (use `NotRequired[]` for new fields). Existing checkpoints must still work.
4. **Graph Wiring**: Any new node or edge change in `research.py` must be tested with both simple (fast path) and complex queries.
5. **Prompt Length Budget**: Each LLM call has a context window. Adding to prompts (e.g., precedent hierarchy rules, risk assessment) must not push total input past Gemini's 1M token limit. Monitor prompt sizes.
6. **Migration Safety**: All DB migrations must be reversible. Test with `alembic downgrade` after `upgrade`.
7. **Performance Regression**: After performance-related changes (B1-B10), measure actual latency. Target: complex query < 90s.
8. **Import Chain**: Changes to extractor.py, constants.py, or treatment.py may break imports in ingestion pipeline, search, and agents. Test all three paths.

---

## CATEGORY A: STATUTE, DATA & DOMAIN COVERAGE (10 Workstreams)

### A1. Unify Statute Regex — Delegate to Extractor
**Files:** `backend/app/core/agents/nodes/common.py`, `backend/app/core/legal/extractor.py`
**Problem:** `_STATUTE_RE` in common.py hardcodes 8 acts. extractor.py already has 62+ acts in `_SHORT_ACT_NAMES`.
**Implementation:**
1. In `common.py`, replace `_STATUTE_RE` with a call to `extractor.extract_acts_cited(text)`
2. Delete the duplicated `_STATUTE_RE` and `_ARTICLE_RE` from common.py
3. In `_extract_statute_refs()`, parse extractor output into the existing `(act, section)` tuple format
4. Add a `normalize_act_name(raw: str) -> str` function in extractor.py that maps all aliases (e.g., "Indian Penal Code", "IPC", "45 of 1860") to canonical short names
5. Update `_expand_refs()` to use `constants.py` maps bidirectionally (BNS→IPC and IPC→BNS)
**E2E Impact:** statute_lookup_node will now detect 62+ acts instead of 8. Workers downstream receive richer statute_context. Synthesis quality improves. Verify: run a query mentioning "NDPS Act Section 37" — should now be recognized.

### A2. Fix Article Regex for Sub-Clauses
**Files:** `backend/app/core/legal/extractor.py`
**Problem:** `_ARTICLE_RE` misses sub-clauses like `Article 19(1)(a)`, `Article 21 read with Article 14`
**Implementation:**
1. Update `_ARTICLE_PATTERN` to: `r'(?:Art(?:icle)?\.?\s*)(\d+[A-Z]?)(?:\s*\((\d+)\))?(?:\s*\(([a-z])\))?(?:\s*(?:read\s+with|r/w)\s*(?:Art(?:icle)?\.?\s*)(\d+[A-Z]?))?'`
2. Return linked articles as a tuple: `(primary_article, sub_clause, linked_article)`
3. Add test cases for: `19(1)(a)`, `21 read with 14`, `368A`, `Article 226(1)`
**E2E Impact:** Constitutional queries will now correctly decompose "Article 19(1)(a) read with Article 21" into separate elements. Affects element_decomposition_node output.

### A3. Expand _SHORT_ACT_NAMES to 85+ Acts
**Files:** `backend/app/core/legal/extractor.py`
**Problem:** Only 62 acts recognized. India has ~891 central acts; at minimum need ~85 commonly litigated ones.
**Acts to add by domain:**
- **Criminal (4):** UAPA, NIA Act, PMLA, Juvenile Justice Act
- **Commercial (15):** Companies Act 2013, SEBI Act, Competition Act, SARFAESI Act, IBC, Negotiable Instruments Act, Sale of Goods Act, Indian Contract Act, Partnership Act, LLP Act, Arbitration and Conciliation Act, FEMA, Banking Regulation Act, Insurance Act, MSMED Act
- **Family (6):** Hindu Marriage Act, Hindu Succession Act, Muslim Personal Law Application Act, Special Marriage Act, Guardians and Wards Act, Domestic Violence Act
- **Labor (8):** Industrial Disputes Act, Factories Act, ESI Act, EPF Act, Payment of Wages Act, Minimum Wages Act, Trade Unions Act, Workmen's Compensation Act + Code on Wages 2019, Code on Social Security 2020
- **Tax (6):** Income Tax Act, GST Act (CGST/SGST/IGST), Customs Act, Central Excise Act, Stamp Act, Benami Transactions Act
- **Constitutional/Admin (4):** RTI Act, Lokpal Act, Contempt of Courts Act, Administrative Tribunals Act
- **Property (4):** Transfer of Property Act, Registration Act, Indian Easements Act, RERA Act
- **Environmental (4):** Environment Protection Act, Wildlife Protection Act, Forest Conservation Act, Water/Air Pollution Acts
- **Technology (3):** DPDP Act, Aadhaar Act (IT Act already present)

For each: add canonical name, short alias, year, and act number to `_SHORT_ACT_NAMES` dict.
**E2E Impact:** A1's extractor delegation immediately picks up all new acts. No other code changes needed — A1 is the bridge. But verify: ingestion pipeline's `extract_acts_cited` used during case ingestion also benefits.

### A4. Batch Statute DB Lookups (Fix N+1)
**Files:** `backend/app/core/agents/nodes/common.py`
**Problem:** `_fetch_statute_from_db()` runs one query per (act, section) pair — N+1 pattern.
**Implementation:**
1. Create `_fetch_statutes_batch(refs: list[tuple[str, str]], db) -> dict[tuple[str,str], Statute]`
2. Single query: `SELECT * FROM statutes WHERE (act_short_name, section_number) IN (VALUES ...)` using SQLAlchemy `tuple_()` + `in_()`
3. Return dict keyed by (act, section) for O(1) lookup
4. Replace all individual calls in `statute_lookup_node`
5. Migration: `CREATE INDEX ix_statutes_act_section ON statutes(act_short_name, section_number)`
**E2E Impact:** Reduces statute_lookup_node latency from O(n) queries to O(1). Combined with A1 detecting more acts, this prevents the N+1 from getting worse with more acts.

### A5. 85-Act Ingestion Pipeline (10 Batches)
**Files:** `backend/scripts/ingest_statutes.py` (new), existing ingestion pipeline
**Problem:** Only 8 acts in statute DB. Need 85+ for comprehensive coverage.
**Implementation:**
1. Source from India Code (https://indiacode.nic.in/) — publicly available
2. Script: download, parse sections (heading/body/explanation/proviso/illustration), store in `statutes` table, embed in Pinecone namespace `statutes`
3. 10 batches by domain (Criminal, Criminal+, Commercial-1, Commercial-2, Family, Labor, Tax, Constitutional, Property+Environmental, Technology)
4. Migration: add `amendment_history` JSONB, `effective_from` DATE, `effective_until` DATE to `statutes`
**E2E Impact:** This is a DATA step, not code. It enriches the DB that A1/A4 query. After ingestion, statute_lookup_node returns actual text. Temporal validation becomes meaningful. Verify: query "What is Section 302 IPC?" should return full section text.

### A6. Expand Classify Schema — All Legal Domains
**Files:** `backend/app/core/legal/prompts.py`
**Problem:** `RESEARCH_CLASSIFY_SCHEMA` has 10 topics. Missing IP, banking, arbitration, consumer, cyber, admin, etc.
**Implementation:**
1. Expand `topics` to 20+: add intellectual_property, banking_finance, insurance, arbitration, consumer, cyber, administrative, military, maritime, education, media_telecom
2. Expand `procedural_context`: add review, curative, contempt, execution, original_jurisdiction
3. Expand `client_position`: add intervenor, amicus_curiae, third_party
4. Add `jurisdiction_level`: supreme_court, high_court, tribunal, district_court
5. Add `urgency`: interim_relief, stay_application, regular
**E2E Impact:** classify_node output feeds plan_research and element_decomposition. More granular classification → better-targeted research tasks → more relevant worker results. Verify: query about "SEBI insider trading" should classify as banking_finance, not "other".

### A7. Domain-Specific Element Decomposition Templates
**Files:** `backend/app/core/legal/prompts.py`
**Problem:** `ELEMENT_DECOMPOSITION_SYSTEM` only has templates for criminal, civil, constitutional.
**Add 7 new templates:**
1. **Tax Law**: Taxable event, applicable provision+rate, exemption/deduction, assessment validity, limitation, penalty threshold
2. **Labor/Industrial**: Employer-employee relationship, applicable code/act, standing orders, domestic inquiry compliance, retrenchment conditions, relief
3. **Intellectual Property**: Registrability/novelty, prior art, infringement test, defenses, remedies
4. **Family Law**: Personal law applicable, ground for relief, jurisdiction, maintenance factors, custody test, property division
5. **Environmental**: Polluter pays/precautionary, EIA compliance, NGT jurisdiction, sustainable development, public trust doctrine
6. **Company/Corporate**: Veil piercing, fiduciary duties, oppression/mismanagement, related party transactions, shareholder rights, winding up
7. **Arbitration**: Agreement validity, arbitrability, S.34 challenge grounds, S.11 appointment, interim measures, enforcement
**E2E Impact:** element_decomposition_node uses these templates. Currently falls back to generic decomposition for non-criminal/civil/constitutional. After this, plan_research creates more targeted tasks, workers search with element-specific queries. MUST be done after A6 (classification feeds template selection).

### A8. Bench Hierarchy Upgrade — Coram Size
**Files:** `backend/app/core/legal/precedent_strength.py`, `backend/app/models/case.py`
**Problem:** 4-tier system ignores coram size (5-judge > 3-judge even if both "full bench").
**Implementation:**
1. Migration: add `coram_size: int | None` to Case model
2. Replace `BENCH_HIERARCHY` dict with `_bench_rank(bench_type, coram_size) -> float`
3. Update `classify_precedent_strength()` and `compute_effective_strength()`
4. Add reportability weight (SCC/AIR × 1.2, MANU-only × 0.8)
5. Separate PER_INCURIAM from OVERRULED in treatment.py (new 8th type)
6. Extract coram size during ingestion from judge count
**E2E Impact:** Affects CRAG evaluate_and_extract (relevance scoring), synthesis (which precedent to follow when conflicts), and confidence scoring. Workers rank results differently. MUST update precedent_strength tests.

### A9. Amendment Tracking — Dynamic Maps
**Files:** `backend/app/models/statute.py`, `backend/app/core/legal/constants.py`, new migration
**Problem:** IPC→BNS maps hardcoded in constants.py (567 entries). No dynamic tracking.
**Implementation:**
1. Create `amendment_maps` table (old_act, old_section, new_act, new_section, effective_date, notes)
2. Data migration: seed from constants.py maps
3. `AmendmentMapService` with Redis cache (24h TTL)
4. Update `_expand_refs()` to use service
5. Keep constants.py as fallback
**E2E Impact:** temporal_validation_node becomes dynamic. New act mappings can be added without code deploy. Import chain: common.py → amendment_service → db + Redis. Test: verify existing IPC→BNS lookups still work after migration.

### A10. Order, Rule, Regulation, Schedule Patterns
**Files:** `backend/app/core/legal/extractor.py`
**Problem:** Missing Regulation, Schedule, Clause, Form patterns.
**Implementation:** Add `_REGULATION_PATTERN`, `_SCHEDULE_PATTERN`, `_CLAUSE_PATTERN`, `_FORM_PATTERN`. Add `reference_type` field to extraction output.
**E2E Impact:** More reference types detected → richer statute_context → better synthesis. Affects A1's delegation. Test: "Regulation 4 of SEBI (Listing Obligations)" should be recognized.

---

## CATEGORY B: PERFORMANCE & SEARCH QUALITY (17 Items)

### B1. Switch Adversarial Search to Flash
**Files:** `backend/app/core/agents/research.py` (~line 410)
**Fix:** Change adversarial_search node to pass `flash_llm` instead of `llm`. **Saves ~24s.**
**E2E Impact:** Adversarial search generates simpler queries — Flash is sufficient. No quality loss. Verify: adversarial results should be equally relevant.

### B2. Switch Quality Check to Pro
**Files:** `backend/app/core/agents/research.py` (~line 440)
**Fix:** Change quality_check node to pass `llm` (Pro). This is the final safety gate.
**E2E Impact:** Quality check catches more issues. Combined with B3 retry, this is the safety net. MUST be paired with B3.

### B3. Quality Check Retry Loop
**Files:** `backend/app/core/agents/research.py`, `backend/app/core/agents/nodes/research_nodes.py`
**Implementation:**
1. Add `quality_attempts: int = 0` to ResearchState
2. Conditional edge: score >= 0.7 → verify, score < 0.7 AND attempts < 2 → back to synthesis with feedback, attempts >= 2 → proceed with warning
3. Append quality feedback to state for synthesis to address
**E2E Impact:** CHANGES GRAPH TOPOLOGY. The edge from quality_check now has 3 targets instead of 1. Must test: (a) happy path still works, (b) retry path correctly re-runs synthesis, (c) max-attempts path proceeds with warning flag visible in frontend.

### B4. Fix Rewrite + Classify Parallelism
**Files:** `backend/app/core/agents/research.py` (~line 558)
**Fix:** Both START → rewrite_query AND START → classify, with a join before statute_lookup.
**E2E Impact:** CHANGES GRAPH TOPOLOGY. Both nodes read `original_query` from state (no dependency). Must join before statute_lookup which needs both outputs. **Saves ~2-3s.** Test: verify both nodes populate their respective state fields.

### B5. Parallelize Adversarial Workers
**Files:** `backend/app/core/agents/nodes/research_nodes.py` — `_run_adversarial_search()`
**Fix:** `asyncio.gather()` for 3 counter-argument searches. **Saves ~20s.**
**E2E Impact:** Same results, faster. Verify: all 3 adversarial results still populate state correctly.

### B6. Parallelize Deep-Read Re-evaluations
**Files:** `backend/app/core/agents/nodes/research_nodes.py` — `evaluate_and_extract_node()`
**Fix:** Batch ambiguous results into parallel `asyncio.gather()`. Cap at 5 concurrent.
**E2E Impact:** CRAG deep-read is the bottleneck in Challenge phase. Parallelizing saves ~10-15s. Watch for Gemini rate limits.

### B7. Reduce Speculative Draft Token Size
**Files:** `backend/app/core/agents/nodes/research_nodes.py`
**Fix:** 6000 → 3000 tokens per draft. Add abort if 0 results.
**E2E Impact:** 3 drafts × 3000 = 9000 tokens vs 18000. Merge quality may change — test carefully. C6 (no-results abort) depends on this.

### B8. Add `pre_understood` to Hybrid Search
**Files:** `backend/app/core/search/hybrid.py`
**Fix:** Add `pre_understood: bool = False` param. Skip `understand_query()` when True. Update all agent worker calls.
**E2E Impact:** **Saves ~14s** (2s × 7 workers). Verify: search results are identical with pre_understood=True when query is already rewritten.

### B9. Batch Citation Verification
**Files:** `backend/app/core/agents/nodes/research_nodes.py` — `verify_citations_v2_node()`
**Fix:** Single `SELECT id FROM cases WHERE id IN (...)` query.
**E2E Impact:** Verification phase drops from O(n) queries to 1. **Saves ~2-5s depending on citation count.**

### B10. Add Moderate Complexity Tier
**Files:** `backend/app/core/agents/research.py`
**Implementation:** classify_node adds `moderate` complexity. Moderate path: 2 workers, no adversarial, Flash synthesis.
**E2E Impact:** CHANGES GRAPH TOPOLOGY. Adds a third conditional branch from classify. Must test all 3 paths: simple, moderate, complex. **Saves ~60s for moderate queries.**

### B11. Multi-Hop Graph Traversal
**Files:** `backend/app/core/agents/nodes/worker_nodes.py` — `graph_worker()`
**Fix:** 2-hop bidirectional Cypher. Add `cited_by_count` ranking. Add APPLIES relationship.
**E2E Impact:** graph_worker returns more authoritative and connected cases. Synthesis has richer material. Watch for: larger result sets → more context for CRAG → slower evaluate. May need to cap at 20 results.

### B12. Fuzzy Case Name Search (pg_trgm)
**Files:** `backend/app/core/agents/nodes/worker_nodes.py`, new migration
**Fix:** `CREATE EXTENSION pg_trgm`, GIN index on title, `similarity()` function.
**E2E Impact:** named_case_worker can now find cases despite typos. Migration required. Test: "Keshavananda Bharti" (misspelled) should still find Kesavananda Bharati.

### B13. Wire Precomputed Embeddings
**Files:** `backend/app/core/agents/nodes/worker_nodes.py`
**Fix:** Batch-embed all sub-queries after plan_research. Store in state. Pass to workers.
**E2E Impact:** **Saves ~3.5s** (7 × 0.5s). Requires state schema change (add `query_embeddings`). Workers must accept optional pre-embedded vector.

### B14. Tighten Citation Matching
**Files:** `backend/app/core/search/hybrid.py`
**Fix:** Word boundary regex: `citation ~ ('\m' || $pattern || '\M')`
**E2E Impact:** Fewer false-positive citation matches → cleaner search results → better CRAG scoring.

### B15. Neo4j Fulltext Index Expansion
**Files:** `backend/app/core/providers/graph/neo4j_store.py`
**Fix:** Recreate fulltext index with keywords, acts_cited, ratio_decidendi fields.
**E2E Impact:** graph_worker text search becomes more powerful. Test: search for "Section 302 murder" should match cases with that in ratio.

### B16. Semantic Holding Verification
**Files:** `backend/app/core/agents/nodes/common.py`
**Fix:** Embed claim + actual ratio, cosine similarity, flag if < 0.75. Use Flash.
**E2E Impact:** verify_citations becomes more thorough. Flagged misrepresentations appear in frontend (depends on D4 color-coded pills). **New embedding calls add ~2s — offset by B8/B13 savings.**

### B17. Distinguish vs Contradict Detection
**Files:** `backend/app/core/agents/nodes/research_nodes.py`
**Fix:** After CRAG contradiction detection, add distinguish check. Categorize: contradicts / distinguishable / limited.
**E2E Impact:** Synthesis gets richer contradiction analysis. Counter-argument section (C9) becomes more nuanced. Adds ~3s per contradiction (Flash call).

---

## CATEGORY C: SYNTHESIS & SAFETY (10 Items)

### C1. Indian Precedent Hierarchy in Merge Prompt
**Files:** `backend/app/core/legal/prompts.py` — `SPECULATIVE_MERGE_SYSTEM`
**Fix:** Add 7-rule Indian precedent hierarchy to merge prompt.
**E2E Impact:** Synthesis correctly prioritizes larger/later benches. Depends on A8 (bench hierarchy data). Without A8, prompt rules exist but data is incomplete.

### C2. Dissent Handling
**Files:** `backend/app/core/legal/prompts.py`, `backend/app/core/agents/nodes/research_nodes.py`
**Fix:** Add `dissenting_views` section. Flag dissents later adopted by larger bench.
**E2E Impact:** Requires dissent data in case model or extraction. For MVP, instruct LLM to note dissents it encounters in source text.

### C3. Risk Assessment Matrix
**Files:** `backend/app/core/legal/prompts.py`
**Fix:** Add Risk Assessment section to merge prompt (strength/risks/counter-args/mitigation).
**E2E Impact:** Longer memo output. Frontend must render this section. Pairs with C9 (counter-arguments).

### C4. Temporal Warning Integration
**Files:** `backend/app/core/agents/nodes/research_nodes.py`
**Fix:** Pass `temporal_warnings` to synthesis. Add visual ⚠️ markers.
**E2E Impact:** Depends on A9 (amendment maps) for dynamic lookups. Without A9, uses static constants.py.

### C5. Confidence Breakdown — 3 Dimensions
**Files:** `backend/app/core/agents/confidence.py`, `backend/app/core/agents/state.py`, frontend
**Fix:** Surface `calculate_confidence_detailed()`. Add evidence_quality, legal_accuracy, consistency breakdown.
**E2E Impact:** State schema change. SSE `done` event payload changes. Frontend D5 depends on this.

### C6. "No Results" Abort Path
**Files:** `backend/app/core/agents/nodes/research_nodes.py`
**Fix:** Check total_results after workers. 0 → skip synthesis. <3 → add caveat.
**E2E Impact:** CHANGES GRAPH TOPOLOGY (new conditional edge after worker fan-in). Must test: query with no matching cases should return helpful "no results" memo, not hallucinated synthesis.

### C7. Footnote Paragraph References
**Files:** `backend/app/core/agents/state.py`, synthesis prompts
**Fix:** Add `paragraph: str | None` to Footnote TypedDict. Instruct LLM to include paragraph numbers.
**E2E Impact:** State schema change (backward-compatible with NotRequired). Frontend D12 citation popover uses this.

### C8. Section-Level Confidence
**Files:** Synthesis prompts, frontend
**Fix:** LLM rates each section: well_supported / moderate_support / limited_support / speculative.
**E2E Impact:** Memo structure changes (metadata per section). Frontend renders colored borders. Must define JSON structure for section metadata.

### C9. Counter-Argument Section
**Fix:** Dedicated "Counter-Arguments & Responses" section in merge prompt. Depends on adversarial_search results.
**E2E Impact:** Longer memo. Pairs with B17 distinguish-vs-contradict. If adversarial is disabled (user toggle), this section is skipped.

### C10. Output Sanitization
**Files:** `backend/app/core/agents/nodes/common.py`
**Fix:** Strip injection attempts, truncate to 2000 chars, validate case_id/citation format.
**E2E Impact:** Defensive measure. No functional change for clean data. Test: inject system-prompt-like text in case data, verify it's stripped.

---

## CATEGORY D: UX, HITL & FRONTEND (30 Items)

### D1-D3: HITL Checkpoint UX
- **D1**: Structured plan review component (PlanHeader, TaskList, StatuteContext, ElementBreakdown, AdversarialToggle)
- **D2**: Structured findings review (top 10 case cards, contradictions, gaps). Backend: include cases in checkpoint payload.
- **D3**: Context-aware suggestion chips per checkpoint type (plan/findings/final)

### D4-D7: Memo Viewer Core
- **D4**: Color-coded footnote pills (green=verified, yellow=partial, red=flagged, gray=unchecked). Depends on B16.
- **D5**: Contextualized confidence display (3-bar breakdown + descriptive label). Depends on C5.
- **D6**: DOCX/PDF export (python-docx + weasyprint/reportlab, cover page, footnotes, bibliography)
- **D7**: Section-level revision (per-section "Revise" button, inline feedback, streaming re-synthesis)

### D8-D10: Progress & Control
- **D8**: Progress bar with 5 stages (Understand 10%, Decompose 10%, Investigate 50%, Challenge 20%, Synthesize 10%). Backend SSE progress events.
- **D9**: Error categorization (rate_limit, llm_error, no_results, timeout, auth_error). Categorized SSE error events.
- **D10**: Auto-approve HITL toggle. Add `auto_approve: bool` to state. Skip `interrupt()` when True.

### D11-D15: Memo Viewer Enhancements
- **D11**: Table of contents (auto-generated from headings, sticky sidebar)
- **D12**: Citation popover (on-demand case details from API). Depends on C7.
- **D13**: Related research suggestions
- **D14**: Print-optimized CSS (@media print)
- **D15**: Copy individual sections button

### D16-D20: Streaming & Real-Time
- **D16**: Typing indicator during SSE waits
- **D17**: Stage transition animations
- **D18**: Partial results side panel (show worker results as they complete)
- **D19**: Cancel research (POST cancel endpoint, cancellation flag at node boundaries)
- **D20**: Resume research (reconnect from last checkpoint)

### D21-D25: Error Handling
- **D21**: Offline detection (navigator.onLine)
- **D22**: Session timeout handling (30 min idle)
- **D23**: Input validation (2000 char max, language detection)
- **D24**: Rate limit UI (cooldown timer)
- **D25**: Accessibility (ARIA labels, keyboard nav, screen reader)

### D26-D30: Domain Workflows
- **D26**: Criminal defense mode (bail checklist, mandatory minimums)
- **D27**: Constitutional petition mode (Article breakdown, fundamental rights)
- **D28**: Corporate advisory mode (compliance checklist, regulatory body grouping)
- **D29**: Tax dispute mode (assessment year, limitation, circular references)
- **D30**: Family law mode (personal law applicability, welfare-of-child, maintenance)

---

## CATEGORY E: GRAPH & KNOWLEDGE ENRICHMENT (4 Items)

### E1. Doctrine Nodes in Neo4j
Create `Doctrine` node type. Initial 10+ doctrines. `(Case)-[:APPLIES_DOCTRINE]->(Doctrine)` relationships.

### E2. Community Detection
Louvain community detection on citation graph. Label communities by topic. Store community_id on Case nodes.

### E3. Citation Treatment Extraction at Ingestion
Classify each citation context (AFFIRMED/FOLLOWED/DISTINGUISHED/etc.) using Flash LLM during ingestion.

### E4. Scale to 35K Cases
Run full ingestion on all 35K SC judgments from S3 dataset. Rebuild indexes after.

---

## Implementation Sequence

### Sprint 1 — Quick Wins (Performance + Critical Fixes)
| # | Task | ID | Key Dependencies |
|---|------|----|-----------------|
| 1 | Switch adversarial to Flash | B1 | None |
| 2 | Fix rewrite+classify parallelism | B4 | None |
| 3 | Parallelize adversarial workers | B5 | None |
| 4 | Add pre_understood to hybrid search | B8 | None |
| 5 | Unify statute regex (delegate to extractor) | A1 | None |
| 6 | Batch citation verification | B9 | None |
**Expected: ~50s latency reduction, 8→62 acts recognized**

### Sprint 2 — Data Foundation
| # | Task | ID | Key Dependencies |
|---|------|----|-----------------|
| 7 | Expand _SHORT_ACT_NAMES to 85+ | A3 | A1 |
| 8 | Batch statute DB lookups | A4 | A1 |
| 9 | 85-act statute ingestion (Batches 1-3) | A5 | A3, A4 |
| 10 | Fix article regex | A2 | None |
| 11 | Order/Rule/Regulation patterns | A10 | None |
| 12 | pg_trgm fuzzy search | B12 | Migration |

### Sprint 3 — Search & Graph Quality
| # | Task | ID | Key Dependencies |
|---|------|----|-----------------|
| 13 | Multi-hop graph traversal | B11 | None |
| 14 | Wire precomputed embeddings | B13 | State schema |
| 15 | Tighten citation matching | B14 | None |
| 16 | Neo4j fulltext expansion | B15 | None |
| 17 | Semantic holding verification | B16 | None |
| 18 | Distinguish vs contradict | B17 | B16 |
| 19 | Doctrine nodes | E1 | None |
| 20 | Citation treatment extraction | E3 | E1 |

### Sprint 4 — Synthesis & Safety
| # | Task | ID | Key Dependencies |
|---|------|----|-----------------|
| 21 | Indian precedent hierarchy in merge | C1 | A8 (partial) |
| 22 | Dissent handling | C2 | None |
| 23 | Risk assessment matrix | C3 | None |
| 24 | Temporal warning integration | C4 | A9 (partial) |
| 25 | Confidence breakdown | C5 | None |
| 26 | No-results abort path | C6 | B7 |
| 27 | Switch quality check to Pro | B2 | None |
| 28 | Quality retry loop | B3 | B2 |
| 29 | Moderate complexity tier | B10 | None |
| 30 | Expand classify schema | A6 | None |
| 31 | Domain decomposition templates | A7 | A6 |
| 32 | Bench hierarchy upgrade | A8 | Migration |

### Sprint 5 — UX & HITL
| # | Task | ID | Key Dependencies |
|---|------|----|-----------------|
| 33 | Structured plan review | D1 | Backend state |
| 34 | Structured findings review | D2 | Backend payload |
| 35 | Context-aware chips | D3 | D1, D2 |
| 36 | Color-coded footnotes | D4 | B16 |
| 37 | Contextualized confidence | D5 | C5 |
| 38 | Progress bar | D8 | Backend SSE |
| 39 | Error categorization | D9 | None |
| 40 | Auto-approve option | D10 | State schema |

### Sprint 6 — Polish & Scale
| # | Task | ID | Key Dependencies |
|---|------|----|-----------------|
| 41 | DOCX/PDF export | D6 | None |
| 42 | Section-level revision | D7 | None |
| 43 | Memo viewer enhancements | D11-D15 | C7 (D12) |
| 44 | Streaming & real-time UX | D16-D20 | D8 |
| 45 | Error handling & edge cases | D21-D25 | None |
| 46 | Domain workflows | D26-D30 | A6, A7 |
| 47 | Community detection | E2 | E4 |
| 48 | Scale to 35K cases | E4 | None |
| 49 | Complete ingestion batches 4-10 | A5+ | A5 |
| 50 | Dynamic amendment maps | A9 | Migration |

---

## Verification Plan

### After Every Step
- `cd backend && python -m pytest tests/ -x -q` — must pass (baseline: 1845)
- `cd frontend && npm test` — must pass (baseline: 298)
- If step changes graph topology: test simple + complex queries E2E
- If step changes state schema: verify backward compatibility

### After Each Sprint
- Measure complex query latency (target: Sprint 1 → <120s, Sprint 6 → <90s)
- Count recognized acts (target: Sprint 1 → 62, Sprint 2 → 85+)
- Run 2-3 real legal queries E2E and verify output quality

### Final Verification
- Re-run 10 Opus evaluator agents — target all scores >= 9/10
- Performance: complex query < 90s
- Coverage: 85+ acts, 35K cases
- All 1845+ backend tests + 298+ frontend tests passing
