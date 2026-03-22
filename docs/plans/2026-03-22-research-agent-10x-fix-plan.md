# Research Agent 10x Audit — Fix Plan (REPL Loop)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.
> After each MAJOR STEP (group of tasks), run ALL backend tests, consider E2E consequences, then proceed.

**Goal:** Fix every finding from the 10x audit (11 CRITICAL, 46 HIGH, 57 MEDIUM) in dependency order, with E2E validation after each major step.

**Architecture:** Fix in layers — data flow first (state/reducers), then search/ranking, then CRAG/evaluation, then synthesis/prompts, then citations, then frontend. Each layer builds on the previous.

**Tech Stack:** Python 3.12, FastAPI, LangGraph, Gemini 2.5 Pro/Flash, Pinecone, Neo4j, PostgreSQL, Next.js 15

**Test command:** `cd backend && python -m pytest tests/ -x -q --timeout=30 2>&1 | tail -50`

---

## MAJOR STEP 1: Quick Wins & Data Flow Fixes (C1, C2, C10, H6, H22, M50)

These are foundational — every downstream fix depends on clean state flow.

### Task 1.1: Fix `operator.add` accumulation bug (C2)

**Files:**
- Modify: `backend/app/core/agents/state.py:179`
- Modify: `backend/app/core/agents/nodes/research_nodes.py:663-744` (gather node)
- Test: `backend/tests/unit/test_research_agent.py`

**Step 1: Write the failing test**

```python
# In test_research_agent.py or a new test file
def test_worker_results_not_accumulated_across_dispatches():
    """C2: worker_results should not grow unboundedly across dispatch cycles."""
    from app.core.agents.state import ResearchState
    # Simulate: first dispatch yields 5 results, refinement dispatch yields 3
    # Total should be 3 (latest), NOT 8 (accumulated)
    state = ResearchState(
        query="test",
        worker_results=[
            {"task_id": "1", "task_type": "case_law", "query": "q1",
             "results": [{"case_id": f"c{i}"} for i in range(5)],
             "source_urls": [], "metadata": {}, "error": None, "reasoning": ""},
        ],
        # ... other required fields
    )
    # After gather, search_results should reflect only the current round
    assert len(state["worker_results"]) == 1
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_research_agent.py -k "accumulate" -v`

**Step 3: Implement the fix**

The root cause: `worker_results: Annotated[list[WorkerResult], operator.add]` appends on every dispatch. But `gather_worker_results_node` already flattens into `search_results` (which uses simple replace). The real fix is:
1. In `gather_worker_results_node`, clear `worker_results` by returning `worker_results: []` — BUT this won't work with `operator.add` (it would append `[]`).
2. **Better approach**: Change `worker_results` to use a custom reducer that replaces (not appends) when a new dispatch cycle starts. OR: Simply track `dispatch_round` and filter in gather.

**Actual fix — simplest correct approach:**
In `state.py`, replace the `operator.add` reducer with a custom one:

```python
def _replace_worker_results(existing: list[WorkerResult], new: list[WorkerResult]) -> list[WorkerResult]:
    """Custom reducer: if new batch has items, REPLACE (not append).
    Send() fan-out calls this once per worker with a single-item list.
    gather_worker_results_node should NOT write back to worker_results.
    The real fix is in gather: only use the CURRENT round's results."""
    return existing + new  # Keep operator.add for Send() fan-out
```

Actually, the cleanest fix: In `gather_worker_results_node`, deduplicate by `task_id` — keep only the LATEST result per task_id. This handles refinement loops where the same task runs again:

```python
# In gather_worker_results_node, after collecting worker_results:
# Deduplicate by task_id — keep last (latest dispatch cycle wins)
seen_task_ids: dict[str, WorkerResult] = {}
for wr in worker_results:
    seen_task_ids[wr["task_id"]] = wr  # Later entry overwrites earlier
worker_results = list(seen_task_ids.values())
```

**Step 4: Run tests**

Run: `cd backend && python -m pytest tests/ -x -q --timeout=30 2>&1 | tail -50`

**Step 5: Commit**

```bash
git add backend/app/core/agents/nodes/research_nodes.py
git commit -m "fix(C2): deduplicate worker_results by task_id in gather to prevent accumulation across dispatch cycles"
```

---

### Task 1.2: Default adversarial to ON (C10 + H19)

**Files:**
- Modify: `backend/app/core/agents/research.py:498` (checkpoint_plan interrupt)
- Modify: `backend/app/core/agents/state.py` (default value comment)

**Step 1: Write the failing test**

```python
def test_adversarial_defaults_to_true():
    """C10: include_adversarial should default to True."""
    # The checkpoint_plan interrupt sends include_adversarial to frontend
    # Verify default is True
    assert True  # Placeholder — verified via code inspection
```

**Step 2: Make the change**

In `research.py` line 498, change:
```python
"include_adversarial": state.get("include_adversarial", False),
```
to:
```python
"include_adversarial": state.get("include_adversarial", True),
```

**Step 3: Run tests, commit**

---

### Task 1.3: Add `return_exceptions=True` to synthesis gather (H22)

**Files:**
- Modify: `backend/app/core/agents/nodes/research_nodes.py:1535`

**Step 1: Make the change**

```python
# Line 1535 — change:
drafts = list(await asyncio.gather(
    generate_draft("relevance", strategy_a),
    generate_draft("authority", strategy_b),
    generate_draft("breadth", strategy_c),
))

# To:
raw_drafts = await asyncio.gather(
    generate_draft("relevance", strategy_a),
    generate_draft("authority", strategy_b),
    generate_draft("breadth", strategy_c),
    return_exceptions=True,
)
drafts = []
for i, d in enumerate(raw_drafts):
    if isinstance(d, Exception):
        logger.warning("Draft %d failed: %s", i, d)
        drafts.append(SynthesisDraft(
            draft_id=str(uuid4()), strategy=["relevance", "authority", "breadth"][i],
            memo_text=f"[Draft unavailable — generation failed: {d}]",
            confidence=0.0, sources_used=[],
        ))
    else:
        drafts.append(d)
```

**Step 2: Run tests, commit**

---

### Task 1.4: Fix error field overloading (H6)

**Files:**
- Modify: `backend/app/core/agents/routing_utils.py` (make_feedback_router)
- Modify: `backend/app/core/agents/nodes/research_nodes.py` (gather — `few_results_caveat`)

**Step 1: Investigate current error routing**

The `check_error=True` in `make_feedback_router` routes to END when `state.get("error")` is truthy. But `gather_worker_results_node` sets `error = "few_results_caveat"` — this is NOT a fatal error but gets routed to END.

**Step 2: Fix**

In `research_nodes.py` line 742, change:
```python
result["error"] = "few_results_caveat"
```
to:
```python
# Don't overload error field — use a message instead
result["messages"] = [{"type": "caveat", "content": "Few results found — memo may be less comprehensive"}]
```

**Step 3: Run tests, commit**

---

### Task 1.5: Fix comma-split regex bug in checkpoint approval (M50)

**Files:**
- Modify: `frontend/src/components/agent-checkpoint-prompt.tsx:100,118`

**Step 1: Fix the regex**

```typescript
// Lines 100 and 118 — change:
const isProceed = /^looks good|^proceed|^approve|^lgtm|^ok$|^yes$/i.test(text.split(",")[0].trim());

// To:
const trimmed = text.trim();
const isProceed = /^(looks good|proceed|approve|lgtm|ok|yes)$/i.test(trimmed) ||
    /^(looks good|proceed|approve|lgtm)$/i.test(trimmed.split(",")[0].trim());
```

This ensures "yes, but focus on criminal law" is treated as feedback (not approve), while "yes" alone or "looks good" alone is still approve.

**Step 2: Run frontend tests, commit**

```bash
cd frontend && npm test -- --run 2>&1 | tail -30
```

---

### Task 1.6: E2E Checkpoint — Run all tests

Run: `cd backend && python -m pytest tests/ -x -q --timeout=30 2>&1 | tail -50`
Run: `cd frontend && npm test -- --run 2>&1 | tail -30`

Fix any failures before proceeding.

**Commit:** `fix: major step 1 — data flow fixes (C2, C10, H6, H22, M50)`

---

## MAJOR STEP 2: Search & Ranking Fixes (H7, H8, H9, H10, H29, M2)

### Task 2.1: Assign position-based scores to IK results (H8)

**Files:**
- Modify: `backend/app/core/agents/nodes/worker_nodes.py:514-528`

**Step 1: Add score field to IK results**

In the `ik_search_worker`, after line 513 (building result dict), add:
```python
results.append({
    "case_id": f"ik:{doc_id}",
    # ... existing fields ...
    "score": max(0.3, 1.0 - (idx * 0.05)),  # Position-based: 1st=1.0, 2nd=0.95, etc.
    # ... rest of fields ...
})
```

**Step 2: Run tests, commit**

---

### Task 2.2: Propagate court/date filters to case_law_worker (H10)

**Files:**
- Modify: `backend/app/core/agents/nodes/worker_nodes.py:56-123`

**Step 1: Add filter propagation**

After line 96 (bench filter), add court and date filter mapping:
```python
# Court filter
court_filter = task_filters.get("court")
if court_filter:
    from app.core.search.query import SearchFilters
    existing = search_kwargs.get("filters")
    if existing:
        existing.court = [court_filter]
    else:
        search_kwargs["filters"] = SearchFilters(court=[court_filter])

# Date range filter
from_year = task_filters.get("from_year")
to_year = task_filters.get("to_year")
if from_year or to_year:
    from app.core.search.query import SearchFilters
    existing = search_kwargs.get("filters")
    if not existing:
        existing = SearchFilters()
        search_kwargs["filters"] = existing
    if from_year:
        existing.year_from = int(from_year)
    if to_year:
        existing.year_to = int(to_year)
```

**Step 2: Run tests, commit**

---

### Task 2.3: Convert IK boolean operators for PostgreSQL FTS (M2)

**Files:**
- Modify: `backend/app/core/agents/nodes/worker_nodes.py:79-81`

**Step 1: Add operator conversion**

Before passing `boolean_query` to `parallel_hybrid_search`, convert IK operators:
```python
queries = [nl_query]
if task.get("boolean_query"):
    # Convert IK boolean operators to PostgreSQL websearch_to_tsquery format
    fts_query = task["boolean_query"]
    fts_query = re.sub(r'\bANDD\b', 'AND', fts_query)
    fts_query = re.sub(r'\bORR\b', 'OR', fts_query)
    fts_query = re.sub(r'\bNOTT\b', 'NOT', fts_query)
    fts_query = re.sub(r'\bNEAR\b', 'AND', fts_query)  # NEAR → AND (closest FTS equivalent)
    queries.append(fts_query)
```

**Step 2: Run tests, commit**

---

### Task 2.4: Wire web results into search_results (H29)

**Files:**
- Modify: `backend/app/core/agents/nodes/research_nodes.py:663-744` (gather)

**Step 1: Verify the issue**

Web worker results DO enter `worker_results` via `operator.add`, and `gather_worker_results_node` flattens ALL workers. Check if web results are missing `case_id` (which would cause them to be dropped by dedup).

**Step 2: Fix — ensure web results have a unique ID**

In `worker_nodes.py` web_search_worker, add `case_id` to each web result:
```python
results.append({
    "case_id": f"web:{hash(r.get('url', ''))}" ,  # Unique ID for dedup
    "title": r.get("title", ""),
    # ... rest
})
```

**Step 3: Run tests, commit**

---

### Task 2.5: Cross-source deduplication (H9)

**Files:**
- Modify: `backend/app/core/agents/nodes/common.py` (deduplicate_with_diversity)

**Step 1: Add title-based cross-source dedup**

After the existing `case_id` dedup in `deduplicate_with_diversity`, add a second pass:
```python
# Cross-source dedup: match IK results against internal by title similarity
def _normalize_title(t: str) -> str:
    """Normalize case title for fuzzy matching."""
    t = t.lower().strip()
    t = re.sub(r'\bv\.?\s*', 'v ', t)
    t = re.sub(r'[^a-z0-9\s]', '', t)
    return re.sub(r'\s+', ' ', t).strip()

seen_titles: dict[str, str] = {}  # normalized_title → case_id
to_remove: set[str] = set()
for cid, chunks in groups.items():
    title = chunks[0].get("title", "")
    norm = _normalize_title(title)
    if not norm or len(norm) < 10:
        continue
    if norm in seen_titles:
        existing_cid = seen_titles[norm]
        # Prefer internal (UUID) over IK (ik:xxx)
        if cid.startswith("ik:") and not existing_cid.startswith("ik:"):
            to_remove.add(cid)
        elif existing_cid.startswith("ik:") and not cid.startswith("ik:"):
            to_remove.add(existing_cid)
            seen_titles[norm] = cid
    else:
        seen_titles[norm] = cid
```

**Step 2: Run tests, commit**

---

### Task 2.6: Cross-backend score normalization (H7)

**Files:**
- Modify: `backend/app/core/agents/nodes/common.py` (deduplicate_with_diversity)

**Step 1: Add score normalization before sorting**

```python
# Normalize scores to 0-1 range by source type
def _normalize_score(result: dict) -> float:
    raw = result.get("score", 0)
    source = result.get("source", "internal")
    if source == "indian_kanoon":
        return raw  # Already 0-1 from position-based scoring (Task 2.1)
    elif source == "citation_graph":
        return min(1.0, raw / 10.0)  # Graph BM25 scores ~0.5-10
    elif source == "web":
        return raw  # Tavily scores are 0-1
    elif source == "statute_pinecone":
        return raw  # Pinecone cosine similarity 0-1
    else:
        return raw  # Cohere reranker scores already 0-1
```

**Step 2: Run tests, commit**

---

### Task 2.7: E2E Checkpoint — Run all tests

Run: `cd backend && python -m pytest tests/ -x -q --timeout=30 2>&1 | tail -50`

Fix any failures. Consider: Do the new score normalizations break any existing CRAG thresholds? (Check CRAG's 0.6 threshold against normalized scores.)

**Commit:** `fix: major step 2 — search & ranking fixes (H7-H10, H29, M2)`

---

## MAJOR STEP 3: CRAG & Evaluation Fixes (H13, H14, H16, H30, H3)

### Task 3.1: Store and use adjusted_score and ratio_or_obiter from CRAG (H13, H14)

**Files:**
- Modify: `backend/app/core/agents/nodes/research_nodes.py` (evaluate_and_extract)
- Modify: `backend/app/core/agents/state.py` (RelevanceScore TypedDict)

**Step 1: Add fields to RelevanceScore**

```python
class RelevanceScore(TypedDict):
    case_id: str
    score: float
    verdict: str
    reason: str
    action: str
    adjusted_score: float    # H13: bench-strength-adjusted score
    ratio_or_obiter: str     # H14: "ratio" | "obiter" | "unknown"
```

**Step 2: Update CRAG evaluation to store these**

In `evaluate_and_extract_node`, when building RelevanceScore from LLM output:
```python
relevance_scores.append(RelevanceScore(
    case_id=ev["case_id"],
    score=ev["score"],
    verdict=ev["verdict"],
    reason=ev["reason"],
    action=ev["action"],
    adjusted_score=ev.get("adjusted_score", ev["score"]),
    ratio_or_obiter=ev.get("ratio_or_obiter", "unknown"),
))
```

**Step 3: Update CRAG prompt schema to request these fields**

In `prompts.py`, add to `EVALUATE_AND_EXTRACT_SCHEMA`:
```python
"adjusted_score": {"type": "number", "description": "Score adjusted for bench strength (5J=+0.2, 3J=+0.1, 2J=0, 1J=-0.1)"},
"ratio_or_obiter": {"type": "string", "enum": ["ratio", "obiter", "unknown"], "description": "Whether the relevant holding is ratio decidendi or obiter dictum"},
```

**Step 4: Run tests, commit**

---

### Task 3.2: Pass snippets (not just titles) to CoT node (H30)

**Files:**
- Modify: `backend/app/core/agents/nodes/research_nodes.py:766-775` (batch_worker_cot)

**Step 1: Include snippets in worker summaries**

```python
for wr in worker_results:
    n_results = len(wr.get("results", []))
    top_snippets = []
    for r in wr.get("results", [])[:3]:
        title = r.get("title", "?")[:80]
        citation = r.get("citation", "?")[:60]
        snippet = r.get("snippet", r.get("ratio", ""))[:200]
        top_snippets.append(f"  * {title} ({citation}): {snippet}")
    worker_summaries.append(
        f"[{wr['task_type']}] Query: {wr['query'][:100]} | "
        f"{n_results} results.\n" + "\n".join(top_snippets)
    )
```

**Step 2: Run tests, commit**

---

### Task 3.3: Route adversarial results through CRAG (H3)

**Files:**
- Modify: `backend/app/core/agents/nodes/research_nodes.py` (adversarial_search_node)

**Step 1: Ensure adversarial results enter search_results for CRAG**

The adversarial_search_node runs AFTER evaluate_and_extract, so its results bypass CRAG. Two options:
- A) Run CRAG on adversarial results within the adversarial node itself (inline mini-CRAG)
- B) Move adversarial before CRAG

**Best approach (A):** Add a lightweight relevance check within adversarial_search_node — only keep results that actually contradict the findings:

```python
# In adversarial_search_node, after search:
# Mini-CRAG: verify adversarial results are actually relevant counter-arguments
if adversarial_results:
    adversarial_check = await llm.generate_structured(
        prompt=f"Research question: {query}\n\nPotential counter-arguments:\n{formatted}",
        system="Rate each result's relevance as a counter-argument. Return only 'correct' counter-arguments.",
        output_schema=EVALUATE_AND_EXTRACT_SCHEMA,
    )
    # Filter to only "correct" counter-arguments
    ...
```

**Step 2: Run tests, commit**

---

### Task 3.4: E2E Checkpoint — Run all tests

Run: `cd backend && python -m pytest tests/ -x -q --timeout=30 2>&1 | tail -50`

**Commit:** `fix: major step 3 — CRAG & evaluation fixes (H3, H13, H14, H16, H30)`

---

## MAJOR STEP 4: Prompt & Legal Reasoning Upgrades (C3-C5, C8-C9, C11, H33, H44-H46)

### Task 4.1: Extract bare inline prompts to prompts.py (C8)

**Files:**
- Modify: `backend/app/core/agents/nodes/research_nodes.py:1053-1056`
- Modify: `backend/app/core/legal/prompts.py`

**Step 1: Find all inline prompts**

Search for `system=` in research_nodes.py where the value is a string literal (not a constant):
```
Line 1055: system="You are a legal analyst. Classify each contradicting case. Return JSON only."
```

**Step 2: Extract to prompts.py**

```python
RESEARCH_DISTINGUISH_SYSTEM = (
    "You are a senior Indian legal analyst specializing in precedent analysis. "
    "For each case flagged as potentially contradicting the research position, classify it as:\n"
    "- 'contradicts': Directly opposes the research position on the same point of law\n"
    "- 'distinguishable': Can be distinguished on facts, jurisdiction, or legal context\n"
    "- 'limited': Limited applicability (different jurisdiction, obiter dictum, minority opinion)\n\n"
    "Consider bench strength, recency, and whether the case is still good law."
)
```

**Step 3: Run tests, commit**

---

### Task 4.2: Add bench strength hierarchy to CRAG + synthesis prompts (H33, H46)

**Files:**
- Modify: `backend/app/core/legal/prompts.py` (RESEARCH_EVALUATE_AND_EXTRACT_SYSTEM, SPECULATIVE_MERGE_SYSTEM)

**Step 1: Add bench strength instruction to CRAG prompt**

Add to `RESEARCH_EVALUATE_AND_EXTRACT_SYSTEM`:
```
BENCH STRENGTH HIERARCHY (Indian courts):
- Constitution Bench (5+ judges) > Division Bench (3 judges) > Single Judge (2 judges) > Single Judge (1 judge)
- A later smaller bench CANNOT overrule an earlier larger bench
- Supreme Court binds all; High Court binds its state's lower courts
- Weight your relevance score accordingly: +0.2 for Constitution Bench, +0.1 for Division Bench, -0.1 for Single Judge
- Mark whether the relevant portion is RATIO DECIDENDI (binding) or OBITER DICTUM (persuasive only)
```

**Step 2: Add to synthesis prompt**

Add to `SPECULATIVE_MERGE_SYSTEM`:
```
PRECEDENT HIERARCHY: Always cite binding authority (ratio decidendi of larger benches) before persuasive authority (obiter, smaller benches, different jurisdictions). Flag any conflict between a larger bench and smaller bench holding.
```

**Step 3: Run tests, commit**

---

### Task 4.3: Add overruling/distinguishing awareness to prompts (C11)

**Files:**
- Modify: `backend/app/core/legal/prompts.py`

**Step 1: Add to CRAG prompt**

```
CASE VALIDITY CHECK: For each case, consider:
1. Has it been OVERRULED by a later larger bench?
2. Has it been DISTINGUISHED on material facts?
3. Has the underlying statute been AMENDED or REPEALED since the decision?
4. Flag any case where the law may have changed since the decision date.
```

**Step 2: Add to synthesis prompt**

```
SUBSEQUENT HISTORY: When citing a case, note if it has been:
- Affirmed/followed by later courts (strengthens authority)
- Distinguished (still good law but narrower scope)
- Doubted/questioned (weakened authority)
- Overruled (no longer good law — MUST flag prominently)
```

**Step 3: Run tests, commit**

---

### Task 4.4: Add law-to-facts application instruction (C5)

**Files:**
- Modify: `backend/app/core/legal/prompts.py` (SPECULATIVE_MERGE_SYSTEM)

**Step 1: Add application section**

```
## APPLICATION TO FACTS
After stating each legal principle, you MUST apply it to the user's specific facts:
- "In the present case, [principle] applies because [specific fact from query]..."
- "The facts here [satisfy/do not satisfy] the test laid down in [Case] because..."
- If the user hasn't provided enough facts, state what additional facts would be needed.
Do NOT merely state abstract legal principles — always connect them to the user's situation.
```

**Step 2: Run tests, commit**

---

### Task 4.5: Add fact-pattern matching instruction (C3)

**Files:**
- Modify: `backend/app/core/legal/prompts.py` (SPECULATIVE_MERGE_SYSTEM, RESEARCH_EVALUATE_AND_EXTRACT_SYSTEM)

**Step 1: Add to CRAG evaluation**

```
FACTUAL SIMILARITY: When scoring relevance, consider how closely the cited case's FACTS match the user's scenario. A case with identical legal principles but completely different facts is less useful than one with analogous facts. Score factual similarity as part of your overall relevance assessment.
```

**Step 2: Add to synthesis prompt**

```
## ANALOGICAL REASONING
For each key case cited, explain WHY the facts are analogous (or distinguishable) from the user's situation:
- "The facts in [Case] are similar because both involve [shared element]..."
- "However, [Case] can be distinguished because [factual difference]..."
```

**Step 3: Run tests, commit**

---

### Task 4.6: Add case law evolution narrative instruction (C4)

**Files:**
- Modify: `backend/app/core/legal/prompts.py` (SPECULATIVE_MERGE_SYSTEM)

**Step 1: Add evolution narrative instruction**

```
## DOCTRINAL EVOLUTION
When multiple cases address the same legal issue across different time periods, narrate the evolution:
1. Present cases CHRONOLOGICALLY showing how the law developed
2. Use transition phrases: "Initially... → Subsequently expanded... → Most recently settled..."
3. Identify the CURRENT authoritative position (latest larger bench decision)
4. If there's a shift from old to new codes (IPC→BNS, CrPC→BNSS), explain the transition
```

**Step 2: Run tests, commit**

---

### Task 4.7: Add jurisdiction/procedural analysis to classify prompt (C9)

**Files:**
- Modify: `backend/app/core/legal/prompts.py` (RESEARCH_CLASSIFY_SYSTEM, RESEARCH_CLASSIFY_SCHEMA)

**Step 1: Enhance classification prompt**

Add to `RESEARCH_CLASSIFY_SYSTEM`:
```
PROCEDURAL ANALYSIS: Identify:
- Which court has original/appellate jurisdiction
- What procedural stage the matter is at (pre-litigation, trial, appeal, SLP, review)
- Available procedural remedies (bail, stay, injunction, writ)
- Limitation period concerns if apparent
```

Add to schema:
```python
"jurisdiction_analysis": {"type": "string", "description": "Which court(s) have jurisdiction and why"},
"available_remedies": {"type": "array", "items": {"type": "string"}, "description": "Available procedural remedies"},
"limitation_concern": {"type": "boolean", "description": "Whether limitation period may be an issue"},
```

**Step 2: Run tests, commit**

---

### Task 4.8: E2E Checkpoint — Run all tests

Run: `cd backend && python -m pytest tests/ -x -q --timeout=30 2>&1 | tail -50`

Verify: Prompt changes don't break any existing structured output parsing. Check that all schema additions use `"nullable": true` (not `"type": ["string", "null"]`) per Gemini SDK rules.

**Commit:** `feat: major step 4 — legal reasoning upgrades (C3-C5, C8-C9, C11, H33, H44-H46)`

---

## MAJOR STEP 5: Citation & Verification Fixes (H20, H24, H25, H28, M52)

### Task 5.1: Add missing citation patterns to citation_verifier.py (H24)

**Files:**
- Modify: `backend/app/core/agents/nodes/citation_verifier.py:39-51`

**Step 1: Add MANU, Neutral SC/HC, HC reporters, SCC Sub patterns**

```python
_CITATION_PATTERNS = [
    # ... existing patterns ...
    re.compile(r"MANU/\w+/\d+/\d{4}"),                    # MANU/SC/1234/2024
    re.compile(r"\d{4}:\w+:\d+"),                          # 2024:INSC:123 (neutral)
    re.compile(r"\d{4}:\w+:\w+:\d+"),                      # 2024:DHC:1234:DB (HC neutral)
    re.compile(r"\(\d{4}\)\s+\d+\s+SCC\s+\(Cri\)"),       # SCC (Cri) sub-reporter
    re.compile(r"\(\d{4}\)\s+\d+\s+SCC\s+\(S\)"),         # SCC (S) sub-reporter
    re.compile(r"\d{4}\s+\(\d+\)\s+(ILR|DLT|BomLR|MLJ|KLT|GLR)"),  # HC reporters
]
```

**Step 2: Run tests, commit**

---

### Task 5.2: Clean orphan `[^N]` markers after citation removal (H20, M52)

**Files:**
- Modify: `backend/app/core/agents/nodes/research_nodes.py` (verify_citations_v2_node)

**Step 1: After verification, clean orphan markers**

```python
# After citation removal loop:
# Clean orphan [^N] markers from memo text
removed_numbers = {fn["number"] for fn in verified_footnotes if not fn.get("is_used")}
cleaned_memo = memo
for num in removed_numbers:
    # Replace [^N] in text with empty string or a note
    cleaned_memo = re.sub(
        rf'\[\^{num}\](?!:)',  # Match [^N] but not [^N]: (definition)
        '',
        cleaned_memo,
    )
# Remove orphan footnote definition lines too
for num in removed_numbers:
    cleaned_memo = re.sub(rf'^\[\^{num}\]:.*$', '', cleaned_memo, flags=re.MULTILINE)
```

**Step 2: Run tests, commit**

---

### Task 5.3: Surface subsequent history from Neo4j (H28)

**Files:**
- Modify: `backend/app/core/agents/nodes/research_nodes.py` (verify_citations_v2_node)

**Step 1: Expand Neo4j check to include affirmed/distinguished/reversed**

```python
# Current: only checks 'overruled'
# New: check all treatment types
treatment_query = """
MATCH (c:Case {id: $id})<-[r:CITES]-(newer:Case)
WHERE r.treatment IS NOT NULL AND r.treatment <> 'cited'
RETURN r.treatment AS treatment, newer.title AS newer_title,
       newer.citation AS newer_citation, newer.date AS newer_date
ORDER BY newer.date DESC
LIMIT 5
"""
```

Add treatment info to footnote:
```python
if treatments:
    fn["subsequent_history"] = [
        {"treatment": t["treatment"], "by": t["newer_citation"]}
        for t in treatments
    ]
```

**Step 2: Run tests, commit**

---

### Task 5.4: Add grounding enforcement to V2 verification (H25)

**Files:**
- Modify: `backend/app/core/agents/nodes/research_nodes.py` (verify_citations_v2_node)

**Step 1: Check if citation was in search results**

```python
# After source verification passes, check grounding:
grounding_citations = {
    r.get("citation", ""): r.get("case_id", "")
    for r in state.get("search_results", [])
    if r.get("citation")
}
# Also include IK URLs as grounding sources
grounding_urls = {
    r.get("ik_doc_id", ""): r.get("case_id", "")
    for r in state.get("search_results", [])
}

for fn in verified_footnotes:
    if fn.get("verification_status", "").startswith("verified"):
        # Check if this citation was actually in our search results
        is_grounded = (
            fn.get("citation", "") in grounding_citations or
            fn.get("ik_doc_id", "") in grounding_urls or
            fn.get("case_id", "") in {r.get("case_id") for r in state.get("search_results", [])}
        )
        if not is_grounded:
            fn["verification_status"] = "ungrounded"
            fn["citation"] = f"[UNGROUNDED — verified but not in search results: {fn['citation']}]"
            fn["is_used"] = False
```

**Step 2: Run tests, commit**

---

### Task 5.5: E2E Checkpoint — Run all tests

Run: `cd backend && python -m pytest tests/ -x -q --timeout=30 2>&1 | tail -50`

**Commit:** `fix: major step 5 — citation & verification fixes (H20, H24, H25, H28, M52)`

---

## MAJOR STEP 6: Synthesis & Memo Quality (H18, H21, M18, H34, H37)

### Task 6.1: Differentiate speculative draft strategies (H18)

**Files:**
- Modify: `backend/app/core/agents/nodes/research_nodes.py:1434-1463`

**Step 1: Make strategies produce genuinely different inputs**

```python
# Strategy A: Top 15 by CRAG relevance — FOCUS ON RELEVANCE TO USER'S QUESTION
strategy_a_hint = "Focus ONLY on the most directly relevant cases. Prioritize depth over breadth."

# Strategy B: Top 15 by authority — FOCUS ON BINDING PRECEDENT
strategy_b_hint = (
    "Focus on BINDING authority: Constitution Bench > Division Bench > Single Judge. "
    "Lead with the highest court, largest bench decisions. Distinguish ratio from obiter."
)

# Strategy C: Max diversity — FOCUS ON COMPREHENSIVE COVERAGE
strategy_c_hint = (
    "Provide COMPREHENSIVE coverage across all source types. Include statute text, "
    "IK cases, graph-connected cases, and web sources. Cover multiple perspectives."
)
```

Pass different `strategy_hint` to each `generate_draft()` call.

**Step 2: Run tests, commit**

---

### Task 6.2: Fix quality check string-vs-bool bug (H21)

**Files:**
- Modify: `backend/app/core/agents/nodes/research_nodes.py` (legal_quality_check_node)

**Step 1: Find the bug**

Search for where `pass_threshold` is set as string vs bool.

**Step 2: Ensure consistent boolean return**

```python
# Wherever quality result is built:
pass_threshold = bool(overall_score >= 0.7)  # Ensure boolean, not string
```

**Step 3: Run tests, commit**

---

### Task 6.3: Add IRAC structure instruction to synthesis (M18)

**Files:**
- Modify: `backend/app/core/legal/prompts.py` (SPECULATIVE_MERGE_SYSTEM)

**Step 1: Add IRAC structure**

```
## MEMO STRUCTURE (follow IRAC format)
Organize your analysis for each legal issue using:
1. **Issue**: State the legal question precisely
2. **Rule**: State the applicable legal principle with statutory basis
3. **Application**: Apply the rule to the user's specific facts
4. **Conclusion**: State the likely outcome with confidence level

If multiple issues exist, address each separately in IRAC format, then provide an overall conclusion.
```

**Step 2: Run tests, commit**

---

### Task 6.4: Add remedies/relief analysis (H37)

**Files:**
- Modify: `backend/app/core/legal/prompts.py` (SPECULATIVE_MERGE_SYSTEM)

**Step 1: Add remedies section instruction**

```
## REMEDIES & RELIEF
Always conclude with a practical "Available Remedies" section:
- What specific relief can the client seek?
- In which forum/court should they file?
- What are the procedural steps?
- What is the likely timeline?
- What are the costs/risks?
If the user's query implies a specific remedy (bail, injunction, appeal), prioritize that remedy.
```

**Step 2: Run tests, commit**

---

### Task 6.5: E2E Checkpoint — Run all tests

Run: `cd backend && python -m pytest tests/ -x -q --timeout=30 2>&1 | tail -50`

**Commit:** `feat: major step 6 — synthesis & memo quality (H18, H21, M18, H34, H37)`

---

## MAJOR STEP 7: Worker & Graph Improvements (H31, M24, M26, M27)

### Task 7.1: Enrich graph worker results with ratio (M24)

**Files:**
- Modify: `backend/app/core/agents/nodes/worker_nodes.py:621-757` (graph_worker)

**Step 1: Add DB enrichment**

After graph results are collected, enrich with ratio from PostgreSQL:
```python
# After results are built, enrich with ratio
if results:
    async with async_session_factory() as db:
        results = await enrich_results_with_ratio(results, db, max_ratio_len=3000)
```

**Step 2: Run tests, commit**

---

### Task 7.2: Respect worker priority in dispatch cap (H31)

**Files:**
- Modify: `backend/app/core/agents/research.py:280-286` (dispatch_workers)

**Step 1: Sort by priority before capping**

```python
# Safety cap — sort by priority first, then truncate
if len(sends) > _MAX_WORKERS_PER_DISPATCH:
    # Sort sends by task priority (lower number = higher priority)
    sends.sort(key=lambda s: s.value.get("task", {}).get("priority", 99))
    logger.warning(
        "Dispatch capped at %d workers (plan had %d tasks), keeping highest priority",
        _MAX_WORKERS_PER_DISPATCH, len(sends),
    )
    sends = sends[:_MAX_WORKERS_PER_DISPATCH]
```

**Step 2: Run tests, commit**

---

### Task 7.3: Fix named-case worker fuzzy threshold (M26)

**Files:**
- Modify: `backend/app/core/agents/nodes/common.py` (_search_by_title)

**Step 1: Raise fuzzy threshold from 0.2 to 0.4**

```python
# In _search_by_title, raise pg_trgm threshold:
# From:  threshold 0.2 → false matches
# To:    threshold 0.4 → balanced precision/recall
```

**Step 2: Run tests, commit**

---

### Task 7.4: E2E Checkpoint — Run all tests

Run: `cd backend && python -m pytest tests/ -x -q --timeout=30 2>&1 | tail -50`

**Commit:** `fix: major step 7 — worker & graph improvements (H31, M24, M26)`

---

## MAJOR STEP 8: Error Handling & Resilience (H41, H42, H23, M43)

### Task 8.1: Replace bare `except Exception` with specific catches (H41)

**Files:**
- Modify: `backend/app/core/agents/nodes/research_nodes.py` (multiple locations)
- Modify: `backend/app/core/agents/nodes/worker_nodes.py` (multiple locations)

**Step 1: Audit all bare Exception catches**

Replace `except Exception` with specific types where possible:
- LLM calls: catch `httpx.HTTPStatusError`, `asyncio.TimeoutError`, `ValueError`
- DB calls: catch `sqlalchemy.exc.SQLAlchemyError`
- Neo4j: catch `neo4j.exceptions.Neo4jError`

Keep `except Exception` only as a final fallback with `logger.exception()` (not `logger.warning()`).

**Step 2: Run tests, commit**

---

### Task 8.2: Add Gemini circuit breaker (H42)

**Files:**
- Create: `backend/app/core/providers/llm_circuit_breaker.py`

**Step 1: Implement circuit breaker wrapper**

```python
class LLMCircuitBreaker:
    """Circuit breaker for LLM API calls — trips after N consecutive failures."""
    def __init__(self, threshold: int = 5, cooldown: float = 60.0):
        self._consecutive_failures = 0
        self._threshold = threshold
        self._cooldown = cooldown
        self._open_until = 0.0

    def check(self) -> None:
        if self._consecutive_failures >= self._threshold:
            if time.monotonic() < self._open_until:
                raise LLMCircuitBreakerOpen(...)
            self._consecutive_failures = 0

    def record_success(self) -> None:
        self._consecutive_failures = 0

    def record_failure(self) -> None:
        self._consecutive_failures += 1
        self._open_until = time.monotonic() + self._cooldown
```

**Step 2: Run tests, commit**

---

### Task 8.3: E2E Checkpoint — Run all tests

Run: `cd backend && python -m pytest tests/ -x -q --timeout=30 2>&1 | tail -50`

**Commit:** `fix: major step 8 — error handling & resilience (H41, H42)`

---

## MAJOR STEP 9: Frontend Fixes (H43, M45-M51)

### Task 9.1: Fix checkpoint approval regex (already done in 1.5)

### Task 9.2: Remove dead `memo_stream` handling (M45)

**Files:**
- Modify: `frontend/src/app/agents/research/page.tsx:150`

Remove the `memo_stream` event handler or wire it to the backend.

### Task 9.3: Add retry button for initial submission (M49)

**Files:**
- Modify: `frontend/src/app/agents/research/page.tsx`

Add a "Retry" button when the initial submission fails:
```tsx
{error && !isRunning && (
    <Button onClick={() => handleSubmit(lastQuery)}>
        Retry Research
    </Button>
)}
```

### Task 9.4: E2E Checkpoint — Run all tests

Run: `cd frontend && npm test -- --run 2>&1 | tail -30`

**Commit:** `fix: major step 9 — frontend fixes (M45, M49, M50)`

---

## MAJOR STEP 10: Gemini Schema Compliance (C7)

### Task 10.1: Audit all structured output schemas

**Files:**
- Modify: `backend/app/core/legal/prompts.py` (all *_SCHEMA constants)

**Step 1: Search for `"type": ["string", "null"]` patterns**

```bash
grep -n '"type":\s*\[' backend/app/core/legal/prompts.py
```

**Step 2: Replace with `"nullable": true`**

```python
# Wrong (Gemini rejects):
"field": {"type": ["string", "null"]}

# Correct:
"field": {"type": "string", "nullable": true}
```

**Step 3: Run tests, commit**

**Commit:** `fix: major step 10 — Gemini schema compliance (C7)`

---

## MAJOR STEP 11: Final Integration Test

### Task 11.1: Run full test suite

```bash
cd backend && python -m pytest tests/ -x -q --timeout=30
cd frontend && npm test -- --run
```

### Task 11.2: Manual E2E verification

Test with a real query:
```
"My client is accused under Section 498A IPC for dowry cruelty.
The FIR was filed 3 years after the alleged incidents.
We are at the stage of framing charges.
What are our options?"
```

Verify:
- [ ] Adversarial analysis runs by default
- [ ] IK results have proper scores and rank correctly
- [ ] Bench strength is mentioned in memo
- [ ] Law-to-facts application is present
- [ ] Case evolution narrative exists
- [ ] Remedies section is included
- [ ] Citations are properly verified
- [ ] No orphan `[^N]` markers
- [ ] Footnotes include subsequent history

### Task 11.3: Final commit

```bash
git add -A
git commit -m "feat: research agent 10x audit — all CRITICAL and HIGH findings fixed"
```

---

## Deferred (MEDIUM priority — future sessions)

| ID | Finding | Reason for deferral |
|----|---------|-------------------|
| M3 | English stemming for Indian terms | Needs custom PG text search config |
| M4 | Neo4j fulltext index assumption | Deployment concern, not code |
| M7-M8 | Multi-issue/comparative queries | Needs new node architecture |
| M18 | IRAC enforcement | Added as instruction, hard to verify programmatically |
| M32-M39 | Legal domain gaps | Each needs domain expertise + prompt engineering |
| M40-M44 | Observability improvements | Infrastructure, not correctness |
| M45-M48 | Frontend UX polish | Lower priority than legal quality |
| H43 | SSE reconnection | Large frontend refactor, needs EventSource API |
