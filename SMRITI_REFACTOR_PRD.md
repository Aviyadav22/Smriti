# SMRITI REFACTOR PRD v2 — Based on Audit Findings

## CONTEXT
Smriti audit is complete. The codebase is ~95% wired. This PRD targets the remaining gaps, legacy cleanup, hardening, and quality improvements. Every task below is a REAL gap found during the audit.

## RULES
- ONE TASK per iteration. Check it off when done.
- Commit after every task: [SMRITI-REFACTOR] <description>
- Update progress.txt after every iteration.
- NEVER touch .env, API keys, secrets.
- Think like an Indian litigation lawyer for every decision.

## PHASE 1: WIRE THE 10 REAL GAPS

- [x] GAP-1: Wire `build_lookup()` in amendment_service.py — this builds the bidirectional old↔new section mapping dict. It should be called by `expand_statute_references()` in search/query.py and/or `enrich_statute_cross_references()` in statute_enrichment.py so that statute expansion uses the DB-backed amendment maps instead of hardcoded ones. Wire it, verify the statute expansion still works for IPC↔BNS, CrPC↔BNSS, IEA↔BSA lookups.
- [x] GAP-2: Wire `classify_treatment_llm()` in treatment.py — this is the LLM-based citation treatment classifier (more accurate than regex). It should be used as an upgrade path in `check_treatment_from_graph()` in rag.py or in `detect_treatment_in_text()` when regex confidence is low. Add a fallback pattern: try regex first, if confidence < threshold, call LLM classifier. Wire it with a config flag so it can be toggled.
- [x] GAP-3: Wire `section-filter.tsx` frontend component — the audit says the search page uses inline section tabs instead. Either integrate section-filter.tsx into the search page as a proper reusable filter component replacing the inline tabs, OR if the inline tabs are genuinely better, mark section-filter.tsx as deprecated with a clear comment explaining why.
- [x] GAP-4: Wire the 27 "disconnected" admin routes — verify each admin/infra/DPDP route has proper auth middleware (admin-only access). Specifically check: ingest admin endpoints (7), DPDP compliance (4), admin review queue (4), admin corrections (2), data quality (1). If any admin route lacks auth protection, add it.
- [x] GAP-5: Legacy V1/V2 research nodes — the 6 superseded functions (decompose_query_node, detect_contradictions_node, gather_results_node, parallel_search_node, synthesize_memo_node, verify_citations_node) are kept for rollback. Add clear deprecation docstrings to each: what V3 function replaced it, when it was superseded, and under what conditions it would be restored.
- [x] GAP-6: Search suggest/autocomplete route — listed as disconnected. Determine if the backend endpoint works and wire it to the frontend search input as typeahead suggestions. If the frontend search component already has autocomplete UI but no API call, wire it. If there is no frontend autocomplete UI, build a simple one.
- [x] GAP-7: Document memo route — listed as disconnected. This likely serves the research memo export for uploaded documents. Trace where the document analysis → memo generation flow should call this route, and wire it so a user can generate a research memo from an uploaded document.
- [x] GAP-8: Agent execution detail/cancel/revise/export routes (4 disconnected) — these are agent management endpoints. Wire them to the /agents/history frontend page so a user can view execution details, cancel a running agent, request revision, and export results from the history view.
- [x] GAP-9: Case summary route — listed as disconnected. Wire it so the case detail page (/case/[id]) can show an AI-generated summary. If the frontend case detail page has a summary section that is empty or placeholder, wire it to this endpoint.
- [x] GAP-10: Verify the full search suggest flow — after GAP-6, test: user types "Section 302" in search → autocomplete shows suggestions → user selects one → search executes with proper filters.

## PHASE 2: HARDEN EVERY USER-FACING ROUTE

- [x] HARDEN-1: Audit all 29 connected user-facing routes for try/except error handling. For each route missing proper error handling, add try/except that returns meaningful HTTP error codes (400 for bad input, 401 for auth, 404 for not found, 500 for server error) with a user-friendly message. Log the full traceback server-side.
- [x] HARDEN-2: Audit all 29 routes for Pydantic input validation. Ensure every POST/PUT endpoint has a Pydantic request model. Check that search query cant be empty, year filters are reasonable (1947-current), court names are from a valid enum, pagination params have sane defaults and limits.
- [x] HARDEN-3: Audit all frontend API calls (43 functions in api.ts) for loading/error/empty state handling. Every API call should show a loading spinner during fetch, a meaningful error message on failure (not just console.log), and an empty state message when results are empty (e.g. "No cases found matching your query").
- [x] HARDEN-4: Verify CORS configuration in middleware — ensure the allowed origins list matches the actual frontend deployment URLs. Check that no wildcard (*) is used in production config.
- [x] HARDEN-5: Scan entire codebase for hardcoded API keys, secrets, or credentials. If any are found outside .env files, move them to environment variables.
- [x] HARDEN-6: Verify rate limiting on expensive endpoints — search, chat message, agent run, document upload, and TTS generation should all have rate limits to prevent abuse. If rate limiting middleware exists but isnt applied to these routes, apply it.
- [x] HARDEN-7: Verify the Indian Kanoon circuit breaker and rate limiter (2 req/sec) are functioning correctly. Test that when IK API is down, the fallback path works gracefully.

## PHASE 3: CODE QUALITY

- [x] QUALITY-1: Add type hints to every Python function in backend/app/core/ that lacks them. Focus on function signatures (params and return types). Use proper typing imports (Optional, List, Dict, Union, etc).
- [x] QUALITY-2: Add docstrings to every public function that lacks one. Each docstring should explain: what the function does, what legal workflow it serves, and any important constraints (e.g. "chunks must be < 2000 chars" or "expects canonical court name format").
- [x] QUALITY-3: Run ruff or flake8 on the entire backend. Fix all linting errors. Do NOT change any logic, only fix formatting, unused imports, and style issues.
- [x] QUALITY-4: Run eslint/tsc on the entire frontend. Fix all type errors and linting issues. Do NOT change any logic.
- [x] QUALITY-5: Review requirements.txt / pyproject.toml — remove any dependency that is imported nowhere in the codebase. Add any dependency that is imported but not listed.
- [x] QUALITY-6: Review package.json — remove unused frontend dependencies, ensure all imported packages are listed.
- [x] QUALITY-7: Consolidate duplicate statute normalization — statute expansion exists in search/query.py, extractor.py, and agents/nodes/common.py. Create a single shared utility if one doesnt exist, and redirect all three callers to it. If this was already done, verify consistency.

## PHASE 4: TESTS

- [ ] TEST-1: Write unit tests for the 2 newly-wired functions (build_lookup, classify_treatment_llm) to verify they work correctly in their new wiring.
- [ ] TEST-2: Write an integration test for the search pipeline: query "Section 302 IPC bail" → verify response contains case results with proper citation format.
- [ ] TEST-3: Write an integration test for the ingestion pipeline: mock PDF → parse → chunk → embed → verify vectors stored with correct metadata.
- [ ] TEST-4: Write unit tests for statute expansion: verify IPC↔BNS, CrPC↔BNSS, IEA↔BSA bidirectional mapping works.
- [ ] TEST-5: Write unit tests for citation extraction: test against known Indian citation formats (SCC, AIR, INSC Neutral, MANU, LiveLaw).
- [ ] TEST-6: Run the full test suite. Fix any failures. Do not mark this done until ALL tests pass.

## PHASE 5: FINAL VERIFICATION

- [ ] FINAL-1: Start the FastAPI backend — verify zero import errors, zero startup crashes, all routes register.
- [ ] FINAL-2: Build the Next.js frontend — verify zero build errors, all pages render.
- [ ] FINAL-3: Trace end-to-end: search "anticipatory bail under Section 438 CrPC Bombay High Court" → verify results show with proper Indian legal citations, court filter works, year filter works.
- [ ] FINAL-4: Trace agent flow: start a research agent with query "Whether anticipatory bail can be granted under Section 438 CrPC for offences under Section 302 IPC" → verify the 5-stage V3 pipeline executes without errors.
- [ ] FINAL-5: Update AUDIT_MAP.md with final status of all gaps — what was wired, what was deprecated, what needs human review.
- [ ] FINAL-6: Final commit: [SMRITI-REFACTOR] v2 refactor complete — all gaps wired, codebase hardened, tests passing.