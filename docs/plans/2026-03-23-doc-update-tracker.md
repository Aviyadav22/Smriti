# Documentation Update Tracker

**Date:** 2026-03-23
**Purpose:** Update ALL outdated docs to match actual codebase state
**Ground truth:** `~/.claude/projects/d--Startup-Smriti/memory/doc-update-ground-truth.md`

---

## Phase 1: CRITICAL (Core reference docs — most stale)

### 1.1 CLAUDE.md
- [x] Fix Next.js version reference (16 → verify actual from package.json)
- [x] Update embedding model: `gemini-embedding-001` → `gemini-embedding-2-preview`
- [x] Update test counts: backend ~2185+, frontend ~311
- [x] Update current phase description (add V2, V3, 10x audit, embedding upgrade, ingestion V3)
- [x] Update project structure tree (35 migrations not 18, 4 new V3 nodes)
- [x] Update ingest script description (queue-based workers, circuit breaker)
- [x] Update chunking params (1800/400 not 2000/200)
- [x] Add task_type embedding info
- [x] Add multi-vector Pinecone architecture summary
- [x] Verify and update all file path references

### 1.2 ARCHITECTURE.md
- [x] Update system overview diagram: `gemini-embedding-2-preview`
- [x] Update ingestion flow: multi-vector types (chunk/proposition/ratio/headnote/section/statute)
- [x] Update search flow: multi-vector querying + type-based 1.5x boost
- [x] Update agent execution architecture: V3 5-stage sequential pipeline
- [x] Update 4 new V3 nodes in agent diagram
- [x] Update endpoint count if changed
- [x] Update test count references

### 1.3 LLD.md
- [x] Add migrations 015-035 to schema
- [x] Add V3 fields: source_dataset, legal_propositions, statute_sections_interpreted, fact_pattern_summary
- [x] Add `case_statute_interpretations` table
- [x] Add `statutes` table schema
- [x] Update Pinecone vector schema with `vector_type` field
- [x] Update migration count (35 not 14)
- [x] Update Cases table column count (now 60+)

### 1.4 HLD.md
- [x] Update Pinecone design: multi-vector types
- [x] Update search module: multi-vector querying + RRF boosts
- [x] Update ingestion module: proposition extraction, statute interpretation, fact pattern
- [x] Update agent module: V3 sequential-reactive pipeline (not V2 parallel dispatch)
- [x] Update embedding model references throughout
- [x] Update API route inventory if endpoints changed

### 1.5 PROMPT_LIBRARY.md
- [x] Add V3 node prompts: statute_lookup, element_decomposition, adversarial_search, temporal_validation
- [x] Update metadata extraction schema: add 10+ new V2/V3 fields
- [x] Update query understanding: add vector_type filter
- [x] Add section_filter for section-scoped search
- [x] Update case_type constraint (27 mappings not 9)
- [x] Document Perfect-10 prompt upgrades (parallel rewrite+classify, improved synthesis, anti-hallucination)

---

## Phase 2: HIGH (Important reference docs)

### 2.1 DECISIONS.md
- [x] Fix ADR-003: Next.js version
- [x] Fix ADR-005: Pinecone multi-vector architecture note
- [x] Fix ADR-007: embedding model → `gemini-embedding-2-preview`
- [x] Fix ADR-012: chunk sizes (1800/400 not 2000/200, 1200 for ANALYSIS/RATIO)
- [x] Add ADR-020: Multi-vector Pinecone architecture
- [x] Add ADR-021: Research Agent V3 sequential-reactive pipeline
- [x] Add ADR-022: Gemini embedding-2-preview upgrade rationale
- [x] Add ADR-023: Statute ingestion from IndiaCode

### 2.2 PHASE_PLAN.md
- [x] Mark Phase 8 exit criteria as complete (checkboxes)
- [x] Add Research Agent V2 as completed phase
- [x] Add Research Agent V3 as completed phase
- [x] Add 10x Audit Fix as completed phase
- [x] Add Ingestion V2 as completed phase
- [x] Add Embedding Upgrade as completed phase
- [x] Add Ingestion V3 as current phase (in progress)
- [x] Update success metrics test counts
- [x] Update dependencies diagram
- [x] Reconcile Phase 7 Hindi items (partial)

### 2.3 DATA_SOURCES.md
- [x] Update ingestion status (796 → actual count, 2932 statute sections)
- [x] Update enriched schema (add migrations 015-035 fields)
- [x] Update pipeline architecture diagram (multi-vector, V3)
- [x] Update embedding model in diagram
- [x] Update IndianKanoon integration status (now active, not future)
- [x] Update statutes section (2932 sections from 8 acts ingested)

### 2.4 FRONTEND_ARCHITECTURE.md
- [x] Fix Next.js version
- [x] Update test count (311)
- [x] Add research UI premium overhaul changes
- [x] Add footnotes panel component documentation
- [x] Add stream disconnect detection
- [x] Add session expiry event bus
- [x] Add JWT proactive refresh pattern
- [x] Add account lockout UI warnings

---

## Phase 3: MEDIUM (Supporting docs)

### 3.1 ENV_SETUP.md
- [x] Update `GEMINI_EMBEDDING_MODEL` → `gemini-embedding-2-preview`
- [x] Update `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` → 60
- [x] Update migration count (35 not 14)
- [x] Add any new V3 env vars
- [x] Add `INDIAN_KANOON_API_KEY` documentation
- [x] Add `TAVILY_API_KEY` documentation

### 3.2 TESTING_STRATEGY.md
- [x] Update test counts: ~2185 backend, ~311 frontend
- [x] Add new test files for V3 features
- [x] Add `test_embedding_task_types.py` to inventory
- [x] Update test file inventory (120+ backend test files now)
- [x] Add multi-vector search quality tests

### 3.3 SECURITY_AUDIT.md
- [x] Update JWT expiry section (60 min access, proactive refresh)
- [x] Add account lockout (10 attempts / 5 min)
- [x] Add stream disconnect detection
- [x] Add session expired event bus
- [x] Note 10x audit fix completion
- [x] Note silent failure audit completion

### 3.4 PHASE_9_SCALABILITY_AUDIT.md
- [x] Add status checkboxes for each finding
- [x] Mark resolved findings from 10x audit
- [x] Note frontend token refresh race condition fixed
- [x] Note AsyncPostgresSaver status

### 3.5 PRD.md
- [x] Add Research Agent V3 features to core features
- [x] Add multi-vector retrieval to feature list
- [x] Add statute lookup capability
- [x] Update test count if mentioned
- [x] Update current phase status

---

## Phase 4: LOW (Stable/strategic docs)

### 4.1 LEGAL_DOMAIN.md
- [x] Add BNS/BNSS/BSA transition section (IPC→BNS, CrPC→BNSS, IEA→BSA)
- [x] Add section mapping complexity note

### 4.2 STRATEGY.md
- [x] Light refresh of competitive data if needed
- [x] Note actual ingestion status vs 35K target

### 4.3 CURSOR_FOR_LAW.md
- [x] No changes needed (strategic vision doc)

### 4.4 GCP_DEPLOYMENT_CREDENTIALS.md
- [x] ⚠️ FLAG: Contains plaintext production secrets — recommend moving to .env.prod or removing
- [x] Update Pinecone host if changed after embedding upgrade
- [x] Add Sentry DSN when configured

---

## Phase 5: Memory file update

### 5.1 MEMORY.md (auto-memory)
- [x] Update to reflect all completed work
- [x] Fix any stale references
- [x] Keep under 200 lines

---

## Completion Criteria
- All checkboxes marked [x]
- Every doc references `gemini-embedding-2-preview` (not `gemini-embedding-001`)
- Every doc shows correct chunk sizes (1800/400)
- Every doc shows correct test counts (~2185 BE, ~311 FE)
- Every doc shows 35 migrations
- Multi-vector architecture documented in ARCHITECTURE, LLD, HLD
- V3 agent pipeline documented in ARCHITECTURE, HLD, PROMPT_LIBRARY
- No doc references "Next.js 16" incorrectly
