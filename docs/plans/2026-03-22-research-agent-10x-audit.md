# Research Agent 10x Audit — Unified Findings

> **10 Opus subagents scrutinized every code path, prompt, decision loop, and legal reasoning gap.**
> Date: 2026-03-22 | Scope: Full research agent pipeline (backend + frontend)

---

## Audit Dimensions

| # | Dimension | Agent | Findings |
|---|-----------|-------|----------|
| 1 | Graph Architecture | Opus | 2 CRITICAL, 2 HIGH, 6 MEDIUM |
| 2 | LLM Prompts | Opus | 3 CRITICAL, 5 HIGH, 8 MEDIUM |
| 3 | CRAG Evaluation | Opus | 5 HIGH, 7 MEDIUM |
| 4 | Synthesis & Memo | Opus | 8 HIGH |
| 5 | Worker Nodes | Opus | 3 HIGH, 11 MEDIUM |
| 6 | Legal Reasoning | Opus | 5 CRITICAL, 10 HIGH, 8 MEDIUM |
| 7 | State Data Flow | Opus | 1 CRITICAL, 3 HIGH, 5 MEDIUM |
| 8 | Error Handling | Opus | 5 HIGH, 5 MEDIUM |
| 9 | Search & Query Quality | Opus | 4 HIGH, 8 MEDIUM, 7 LOW |
| 10 | Frontend & UX / SSE | Opus | 1 HIGH, 7 MEDIUM, 7 LOW |
| — | Citation & Verification | Opus | 5 HIGH, 6 MEDIUM, 3 LOW |

---

## CRITICAL Findings (11 total)

### C1. Missing `json` import in research.py ✅ FIXED
**File:** `research.py` | **Agent:** #1 Graph Architecture
`checkpoint_plan` uses `json.loads()` but `json` was never imported. Fixed during audit.

### C2. `worker_results` uses `operator.add` reducer — append-only accumulation
**File:** `state.py` | **Agent:** #7 State Data Flow
On refinement loops or re-dispatches, `worker_results` grows unboundedly because `operator.add` appends rather than replaces. This causes duplicate results, inflated token counts, and eventually Gemini refusal loops.
**Fix:** Use a custom reducer that replaces on re-dispatch, or clear `worker_results` before each dispatch cycle.

### C3. No fact-pattern matching in legal analysis
**Agent:** #6 Legal Reasoning
The system never maps the user's specific facts to the legal elements of cited cases. A lawyer's core skill is analogical reasoning: "the facts in Case X are similar to your situation because..." The agent treats all matching cases as equally applicable regardless of factual similarity.
**Fix:** Add a fact-pattern similarity step after CRAG that scores cases by factual resemblance to the user's scenario.

### C4. No case law evolution narrative
**Agent:** #6 Legal Reasoning
The memo presents cases as isolated citations without showing how the law evolved. A competent lawyer shows the doctrinal trajectory: "Initially the court held X (Case A, 1990), then expanded to Y (Case B, 2005), and most recently..."
**Fix:** Add an evolution/timeline synthesis step that orders key cases chronologically and narrates doctrinal development.

### C5. No law-to-facts application
**Agent:** #6 Legal Reasoning
The memo states legal principles but never explicitly applies them to the user's facts. "Section 498A requires cruelty" is useless without "In your case, the alleged conduct of [X] would/would not constitute cruelty because..."
**Fix:** Add an application section in the synthesis prompt that maps each legal element to the user's stated facts.

### C6. LLM can hallucinate case names — no hard enforcement
**Agent:** #2 LLM Prompts
The plan prompt says "Name 2-3 specific landmark Indian cases" from LLM memory. Citation recall is notoriously unreliable. The named_case_worker has fallbacks (citation → title → fuzzy), but completely fabricated cases fail silently.
**Fix:** Log and surface warnings when LLM-suggested cases are not found. Consider removing named-case suggestion from the plan prompt entirely.

### C7. Gemini SDK schema violations in prompts
**Agent:** #2 LLM Prompts
Some structured output schemas use `"type": ["string", "null"]` instead of Gemini's required `"nullable": true`. This can cause silent failures or Gemini returning malformed JSON.
**Fix:** Audit all JSON schemas for Gemini compatibility.

### C8. Bare inline prompt in graph (not in PROMPT_LIBRARY)
**Agent:** #2 LLM Prompts
At least one prompt string is hardcoded inline in a node function instead of being defined in `core/legal/prompts.py`. Violates the project rule that all prompts must be in PROMPT_LIBRARY.
**Fix:** Extract to `prompts.py` with a named constant.

### C9. No forum/jurisdiction analysis
**Agent:** #6 Legal Reasoning
The agent doesn't analyze which court has jurisdiction, whether the matter is at trial/appeal/SLP stage, or what procedural options are available. These are fundamental to any legal advice.
**Fix:** Add jurisdiction and procedural analysis to the classification node.

### C10. Adversarial analysis defaults to OFF
**Agent:** #6 Legal Reasoning
Counter-arguments are gated behind an `include_adversarial` toggle that defaults to `False`. A competent lawyer always considers opposing arguments. This should default to ON.
**Fix:** Change default to `True` in the HITL checkpoint.

### C11. No overruling/distinguishing/amendment awareness in prompts
**Agent:** #2 LLM Prompts
Prompts don't instruct the LLM to check whether cited cases have been overruled, distinguished, or whether the underlying statute has been amended. This is a fundamental legal research requirement.
**Fix:** Add instructions in CRAG and synthesis prompts to flag overruled/distinguished cases.

---

## HIGH Findings (46 total)

### Architecture & Data Flow

| ID | Finding | File/Location | Agent |
|----|---------|---------------|-------|
| H1 | `checkpoint_memo` ignores `auto_approve` — always pauses | `research.py` | #1 |
| H2 | Moderate path skips temporal validation entirely | `research.py` graph wiring | #1 |
| H3 | Adversarial results bypass CRAG evaluation | `research_nodes.py` | #7 |
| H4 | Double-evaluation on refinement (worker_results accumulate, re-evaluated) | State flow | #7 |
| H5 | Dead fields in state never read downstream | `state.py` | #7 |
| H6 | Error field overloading causes premature END routing | `research.py` router | #8 |

### Search & Ranking

| ID | Finding | File/Location | Agent |
|----|---------|---------------|-------|
| H7 | No cross-backend score normalization — IK scores vs Pinecone vs FTS incomparable | `common.py` dedup | #9 |
| H8 | IK results have NO score field → ranked last (score=0) | `worker_nodes.py:514-528` | #9 |
| H9 | No cross-source deduplication (IK `ik:123` vs internal UUID) — same case appears twice | `common.py` dedup | #9 |
| H10 | `case_law_worker` ignores court and date filters from plan | `worker_nodes.py:56-123` | #9 |
| H11 | Historical/temporal queries silently ignore date context | Workers | #9 |
| H12 | Named cases from LLM are hallucination-prone (no validation) | `plan_research_node` | #9 |

### CRAG & Evaluation

| ID | Finding | File/Location | Agent |
|----|---------|---------------|-------|
| H13 | `adjusted_score` computed but never stored or used downstream | `research_nodes.py` CRAG | #3 |
| H14 | `ratio_or_obiter` computed but never stored | `research_nodes.py` CRAG | #3 |
| H15 | Deep-read `case_id` matching uses raw string (ik: prefix issues) | `research_nodes.py` | #3 |
| H16 | IK results systematically disadvantaged in CRAG (no ratio, no snippet quality) | CRAG scoring | #3 |
| H17 | CRAG threshold is hardcoded (0.6) — no per-query-type tuning | `research_nodes.py` | #3 |

### Synthesis & Memo

| ID | Finding | File/Location | Agent |
|----|---------|---------------|-------|
| H18 | 3 speculative draft strategies produce near-identical inputs | `research_nodes.py` | #4 |
| H19 | Counter-arguments gated behind toggle (defaults OFF) | Synthesis | #4 |
| H20 | Dead footnote references after citation removal (`[^N]` stays in text) | `research_nodes.py` | #4 |
| H21 | Quality check has string-vs-bool bug (returns "pass"/"fail" vs True/False) | `research_nodes.py` | #4 |
| H22 | `synthesis gather` lacks `return_exceptions=True` — one failure kills all | `research_nodes.py` | #8 |
| H23 | No early termination when all external services are down | Error handling | #8 |

### Citation & Verification

| ID | Finding | File/Location | Agent |
|----|---------|---------------|-------|
| H24 | `citation_verifier.py` missing 5 citation patterns (MANU, Neutral SC/HC, HC reporters, SCC Sub) | `citation_verifier.py:39-51` | #10b |
| H25 | No hard grounding enforcement in V2 verification — hallucinated-but-real citations pass | `research_nodes.py:2129-2210` | #10b |
| H26 | Cannot detect wrong citation numbers for correct case names | Verification | #10b |
| H27 | No enforcement that every case mention has a footnote | Footnote generation | #10b |
| H28 | Subsequent history not surfaced (affirmed/distinguished/reversed — only "overruled" checked) | Neo4j check | #10b |

### Workers

| ID | Finding | File/Location | Agent |
|----|---------|---------------|-------|
| H29 | Web search results silently dropped (never reach search_results) | `worker_nodes.py` web worker | #5 |
| H30 | CoT (Chain of Thought) node sees only titles, not snippets | `research_nodes.py` CoT | #5 |
| H31 | Worker priority field ignored — all tasks run regardless of priority | Fan-out | #5 |
| H32 | No cross-source dedup at worker level | Workers | #5 |

### Legal Reasoning

| ID | Finding | File/Location | Agent |
|----|---------|---------------|-------|
| H33 | No bench strength hierarchy in ranking (5-judge > 3-judge > 2-judge) | CRAG/Synthesis | #6 |
| H34 | No ratio decidendi vs obiter dicta distinction in synthesis | Memo generation | #6 |
| H35 | No amendment/repeal awareness for statutes | Temporal | #6 |
| H36 | No dissenting opinion analysis | Synthesis | #6 |
| H37 | No remedies/relief analysis (what can the client actually get?) | Synthesis | #6 |
| H38 | No limitation period awareness | Classification/Synthesis | #6 |
| H39 | No evidentiary burden analysis (who proves what) | Synthesis | #6 |
| H40 | No PIL/writ jurisdiction guidance | Classification | #6 |

### Error Handling

| ID | Finding | File/Location | Agent |
|----|---------|---------------|-------|
| H41 | Bare `except Exception` in multiple nodes — swallows actionable errors | Various nodes | #8 |
| H42 | No circuit breaker for Gemini API (only IK has one) | LLM calls | #8 |

### Frontend

| ID | Finding | File/Location | Agent |
|----|---------|---------------|-------|
| H43 | No SSE reconnection/resume logic — connection drop = lost progress | `api.ts:_streamSSE()` | #10 |

### Prompts

| ID | Finding | File/Location | Agent |
|----|---------|---------------|-------|
| H44 | Synthesis prompt doesn't distinguish binding vs persuasive authority | `prompts.py` | #2 |
| H45 | No prompt instructs LLM to check if cited statute section is still in force | `prompts.py` | #2 |
| H46 | CRAG prompt doesn't weight bench strength or ratio/obiter | `prompts.py` | #2 |

---

## MEDIUM Findings (57 total)

### Search & Query

| ID | Finding | Agent |
|----|---------|-------|
| M1 | No deterministic legal shorthand expansion in rewrite (LLM-only) | #9 |
| M2 | Boolean query uses IK syntax (ANDD/ORR) for PostgreSQL FTS (which doesn't understand it) | #9 |
| M3 | Statute FTS uses English stemming for Indian legal terms (poor stem matches) | #9 |
| M4 | Graph worker assumes `case_search` fulltext index exists (fails silently if missing) | #9 |
| M5 | Statute worker ignores all plan filters | #9 |
| M6 | IK results have no score field → all ranked last after dedup | #9 |
| M7 | Multi-issue queries not well-decomposed (single task for 4 legal issues) | #9 |
| M8 | Comparative law queries produce no useful results (IN-only data) | #9 |

### CRAG

| ID | Finding | Agent |
|----|---------|-------|
| M9 | Deep-read uses raw text matching — IK HTML tags in snippets not fully stripped | #3 |
| M10 | CRAG batch size hardcoded at 5 — large result sets evaluated in arbitrary batches | #3 |
| M11 | Ambiguous threshold (0.4-0.6) range too narrow — many results cluster here | #3 |
| M12 | No per-court-type relevance weighting (SC=HC=tribunal) | #3 |
| M13 | CRAG doesn't penalize old cases when newer law exists | #3 |
| M14 | No handling of conflicting SC vs HC holdings | #3 |
| M15 | CRAG evaluation prompt doesn't see the user's original query (only rewritten) | #3 |

### Synthesis

| ID | Finding | Agent |
|----|---------|-------|
| M16 | Speculative drafts all see same evidence — no perspective-specific filtering | #4 |
| M17 | Merge prompt doesn't resolve contradictions between drafts — just concatenates | #4 |
| M18 | No structured legal analysis format (IRAC/CREAC) enforced | #4 |
| M19 | Confidence score is LLM-generated (subjective, not calibrated) | #4 |
| M20 | Gap analysis findings not fed back into synthesis | #4 |

### Workers

| ID | Finding | Agent |
|----|---------|-------|
| M21 | No cross-worker deduplication before CRAG | #5 |
| M22 | Web worker has no Indian-legal-specific search refinement | #5 |
| M23 | Statute worker returns raw text — no section-aware extraction | #5 |
| M24 | Graph worker results lack snippets/ratio — undervalued by CRAG | #5 |
| M25 | LLM-direct worker has no grounding check — pure hallucination risk | #5 |
| M26 | Named-case worker fuzzy threshold too low (0.2) — false matches | #5 |
| M27 | No worker-level timeout — single slow worker blocks all | #5 |
| M28 | Worker result format inconsistent across worker types | #5 |
| M29 | IK search doesn't use `max_cites` filter for authority ranking | #5 |
| M30 | No parallel citation enrichment for IK results | #5 |
| M31 | Worker cap doesn't respect priority (cuts high-priority tasks too) | #5 |

### Legal Reasoning

| ID | Finding | Agent |
|----|---------|-------|
| M32 | No constitutional validity analysis | #6 |
| M33 | No procedural stage awareness (bail vs trial vs appeal) | #6 |
| M34 | No costs/fees guidance | #6 |
| M35 | No alternative dispute resolution analysis | #6 |
| M36 | No international treaty/convention awareness | #6 |
| M37 | No legal ethics/conflict-of-interest flagging | #6 |
| M38 | No specific tribunal procedure awareness (NCLT, ITAT, etc.) | #6 |
| M39 | No sentencing guidelines analysis for criminal matters | #6 |

### Error Handling

| ID | Finding | Agent |
|----|---------|-------|
| M40 | No structured logging — errors logged as unstructured strings | #8 |
| M41 | No health check for external services before starting research | #8 |
| M42 | Retry exhaustion doesn't surface the specific service that failed | #8 |
| M43 | No partial-result delivery when some workers fail | #8 |
| M44 | Checkpoint timeout not enforced (waits indefinitely for user) | #8 |

### Frontend & UX

| ID | Finding | Agent |
|----|---------|-------|
| M45 | `memo_stream` event consumed by frontend but never emitted by backend (dead code) | #10 |
| M46 | No timeout warning for checkpoint responses (JWT may expire) | #10 |
| M47 | No ability to go back to a previous checkpoint decision | #10 |
| M48 | Progress bar depends on `progress` events that may not be emitted | #10 |
| M49 | No retry button for initial research submission failures | #10 |
| M50 | `"yes, but..."` misclassified as approve (comma-split regex bug) | #10 |
| M51 | Plan review "request changes" chips send plain strings, not structured JSON | #10 |

### Citation & Verification

| ID | Finding | Agent |
|----|---------|-------|
| M52 | Removed citations leave orphan `[^N]` markers in memo text | #10b |
| M53 | Parallel citations not consolidated (same case = two footnotes) | #10b |
| M54 | `pdf_available` assumes all internal cases have PDFs | #10b |
| M55 | `_matches_indian_citation_pattern` differs from `_CITATION_PATTERNS` (pattern drift) | #10b |
| M56 | No supra/ibid support in footnote resolution | #10b |
| M57 | Overruled check limited to explicit Neo4j relationships only | #10b |

---

## Recommended Fix Priority (Top 20)

These are ordered by impact on legal research quality:

| Priority | ID(s) | Fix | Effort |
|----------|-------|-----|--------|
| 1 | C2 | Fix `operator.add` accumulation — use custom reducer or clear before dispatch | S |
| 2 | H7,H8 | Cross-backend score normalization + assign IK results a position-based score | M |
| 3 | H9 | Cross-source deduplication (title/citation fuzzy matching across IK vs internal) | M |
| 4 | H10 | Propagate court/date filters from plan to `case_law_worker` → `SearchFilters` | S |
| 5 | M2 | Generate backend-specific boolean queries (IK syntax vs FTS syntax) | S |
| 6 | C10,H19 | Default adversarial to ON | XS |
| 7 | H22 | Add `return_exceptions=True` to synthesis `asyncio.gather` | XS |
| 8 | H6 | Fix error field overloading — use dedicated `has_error` bool, not string check | S |
| 9 | H20,M52 | Clean orphan `[^N]` markers after citation removal | S |
| 10 | H24 | Add missing citation patterns to `citation_verifier.py` | S |
| 11 | H29 | Wire web results into `search_results` (currently silently dropped) | S |
| 12 | H30 | Pass snippets (not just titles) to CoT node | S |
| 13 | H13,H14 | Store and use `adjusted_score` and `ratio_or_obiter` from CRAG | M |
| 14 | C3 | Add fact-pattern similarity scoring after CRAG | L |
| 15 | C4 | Add case law evolution narrative in synthesis | M |
| 16 | C5 | Add law-to-facts application section in synthesis prompt | M |
| 17 | H33 | Implement bench strength hierarchy in ranking (5J > 3J > 2J > 1J) | M |
| 18 | H28 | Surface subsequent history (affirmed/distinguished/reversed) from Neo4j | M |
| 19 | H43 | Add SSE reconnection with `Last-Event-ID` support | L |
| 20 | M50 | Fix comma-split regex bug in checkpoint approval detection | XS |

**Effort key:** XS = <30min, S = 1-2hr, M = 3-6hr, L = 1-2 days

---

## Architecture-Level Gaps Summary

### What makes a great AI lawyer (and what we're missing)

```
GREAT AI LAWYER                          CURRENT STATE
─────────────────────────────────────    ─────────────────────────────────
1. Reads the law FIRST                   ✅ statute_lookup_node (V3)
2. Identifies legal elements             ✅ element_decomposition (V3)
3. Matches facts to elements             ❌ No fact-pattern matching (C3)
4. Finds on-point cases                  ⚠️  Search works but ranking broken (H7-H10)
5. Traces doctrinal evolution            ❌ Cases listed, not narrated (C4)
6. Applies law to YOUR facts             ❌ Generic principles only (C5)
7. Considers opposing arguments          ⚠️  Exists but defaults OFF (C10)
8. Checks if law is still good           ⚠️  Only "overruled" checked (H28)
9. Assesses bench strength               ❌ All courts weighted equally (H33)
10. Provides specific remedies           ❌ No remedies analysis (H37)
11. Warns about limitations              ❌ No limitation period check (H38)
12. Identifies evidentiary needs         ❌ No burden analysis (H39)
13. Cites accurately                     ⚠️  Verification exists but has gaps (H24-H28)
14. Structures analysis (IRAC)           ❌ Free-form memo only (M18)
```

---

## Quick Wins (can fix today)

1. **C10**: `include_adversarial` default → `True` (1 line change)
2. **H22**: Add `return_exceptions=True` to gather (1 line)
3. **M50**: Fix comma-split regex in checkpoint approval (5 lines)
4. **H8**: Assign `score = 1.0 - (idx * 0.05)` to IK results based on position (3 lines)
5. **H10**: Map plan filters to `SearchFilters` in case_law_worker (10 lines)
6. **M2**: Convert ANDD/ORR/NOTT → AND/OR/NOT before PostgreSQL FTS (5 lines)
7. **H29**: Include web results in `search_results` output (5 lines)
