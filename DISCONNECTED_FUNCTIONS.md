# DISCONNECTED FUNCTIONS — Smriti Codebase

> Functions that exist but are not directly reachable from any user action.
> For each, a best guess of where it should plug in is provided.

---

## Backend — Legacy/Superseded Research Node Functions

These are V1/V2 versions of research agent nodes that were superseded by V3 but kept for potential rollback. They are NOT bugs — they are intentional dead code from evolutionary development.

### `decompose_query_node()` — research_nodes.py
- **What it does**: Breaks research query into sub-queries for parallel search
- **Superseded by**: `element_decomposition_node()` in common.py (V3 Stage 2) which uses statute text context
- **Recommendation**: Keep for rollback. If V3 element decomposition proves too slow, this simpler version can be swapped back.

### `detect_contradictions_node()` — research_nodes.py
- **What it does**: Standalone contradiction detection between search results
- **Superseded by**: Contradiction handling integrated into `speculative_synthesis_with_contradictions_node()` (V2+)
- **Recommendation**: Keep. The integrated version is better but this standalone version could be useful for a dedicated "contradiction check" agent step.

### `gather_results_node()` — research_nodes.py
- **What it does**: Simple gather of parallel search results
- **Superseded by**: `gather_worker_results_node()` which handles the Send()/worker pattern
- **Recommendation**: Can be removed. The worker-based gather is strictly superior.

### `parallel_search_node()` — research_nodes.py
- **What it does**: Runs multiple searches in parallel
- **Superseded by**: Worker dispatch pattern (7 typed workers via Send())
- **Recommendation**: Can be removed. Worker dispatch is more flexible.

### `synthesize_memo_node()` — research_nodes.py
- **What it does**: Single-draft memo synthesis
- **Superseded by**: `speculative_synthesis_with_contradictions_node()` which generates 3 drafts with different strategies
- **Recommendation**: Keep for fast-path or simple queries that don't need 3-draft speculation.

### `verify_citations_node()` — research_nodes.py
- **What it does**: V1 citation verification (PG-only)
- **Superseded by**: `verify_citations_v2_node()` which verifies against PG + Indian Kanoon + Neo4j
- **Recommendation**: Can be removed. V2 is strictly superior.

---

## Backend — Orphaned Utility Functions

### `build_lookup()` — amendment_service.py
- **What it does**: Builds bidirectional old↔new section lookup dicts from amendment entries
- **Why disconnected**: The amendment_service.py provides `get_amendment_maps()` for retrieving data and `seed_amendment_maps()` for seeding, but `build_lookup()` is never called
- **Where it should plug in**: Could be used in `statute_lookup_node()` or `expand_statute_references()` to do section-level old→new mapping (currently these work at act level, not section level)
- **Recommendation**: NEEDS_HUMAN_REVIEW — wire when section-level statute comparison is needed

### `classify_treatment_llm()` — treatment.py
- **What it does**: LLM-based citation treatment classification (overruled, distinguished, etc.)
- **Why disconnected**: Marked `[E3]` — planned enhancement. The regex-based `detect_treatment_in_text()` is used instead
- **Where it should plug in**: Could replace regex detection during ingestion (`pipeline.py:_build_citation_graph()`) for higher accuracy treatment classification
- **Recommendation**: NEEDS_HUMAN_REVIEW — wire when accuracy of treatment detection becomes critical

---

## Backend — Disconnected API Endpoints (Intentionally Admin-Only)

These endpoints exist but have no frontend UI. They are intentionally admin-only and accessed via direct API calls, scripts, or admin tools.

- `POST /ingest/upload` — Admin bulk ingestion (use `scripts/ingest_s3.py` instead)
- `GET /ingest/status/{id}` — Ingestion status tracking
- `GET /ingest/dashboard/completeness` — Data completeness dashboard
- `GET /ingest/review-queue` — Cases pending review
- `PATCH /ingest/cases/{id}/metadata` — Manual metadata correction
- `POST /ingest/cases/{id}/approve` / `retry` — Approval workflow
- `GET/POST /admin/review/*` — Admin review queue
- `POST /admin/corrections/{id}/*` — Admin metadata corrections
- `GET /admin/data-quality` — Data quality metrics
- `GET/POST /dpdp/*` — DPDP compliance endpoints
- `DELETE /auth/me` — Account deletion (DPDP)
- `GET /search/suggest` — Autocomplete (no frontend UI yet)

---

## Frontend — Unused Component

### `SectionFilter` — section-filter.tsx
- **What it does**: Dropdown to filter search results by judgment section (FACTS, ISSUES, ARGUMENTS, etc.)
- **Why disconnected**: The search page implements its own inline section filter with badge-style tabs
- **Recommendation**: NEEDS_HUMAN_REVIEW — remove component and its test, or integrate into search page as an alternative filter style
