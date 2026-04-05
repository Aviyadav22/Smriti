# Argument Builder V2 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enrich argument builder with richer case metadata and 3 research agent features (CRAG eval, footnotes, quality check) to produce higher-quality litigation-ready memos.

**Architecture:** 6 tasks split into metadata enrichment (A1-A3, zero new LLM calls) and feature ports (B1-B3, 3 new nodes). The argument builder graph grows from 14 to 17 nodes with a quality retry loop.

**Tech Stack:** FastAPI, SQLAlchemy, LangGraph, Gemini Pro/Flash, Python asyncio

**Design doc:** `docs/plans/2026-04-05-argument-builder-v2-design.md`

---

## Task A1: Enrich precedent_map with 6 new metadata fields

**Files:**
- Modify: `backend/app/core/agents/nodes/strategy_nodes.py` (search_precedents_node, ~line 193)
- Modify: `backend/app/core/agents/nodes/common.py` (enrich_results_with_ratio, ~line 565)
- Test: `backend/tests/unit/test_strategy_nodes.py`

**Step 1: Extend `enrich_results_with_ratio` SQL query**

In `backend/app/core/agents/nodes/common.py`, find `enrich_results_with_ratio` (line ~587). The current query is:

```sql
SELECT id::text, LEFT(ratio_decidendi, :max_len) AS ratio, bench_type, coram_size FROM cases WHERE id::text IN (...)
```

Add 4 new fields:

```sql
SELECT id::text, LEFT(ratio_decidendi, :max_len) AS ratio, bench_type, coram_size,
       opinion_type, split_ratio, disposal_nature, year
FROM cases WHERE id::text IN (...)
```

Update the enrichment loop (line ~607-616) to also set these new fields on each result:

```python
if cid in ratio_map:
    if not r.get("ratio"):
        r["ratio"] = ratio_map[cid]["ratio"]
    if not r.get("bench_type"):
        r["bench_type"] = ratio_map[cid]["bench_type"]
    if not r.get("coram_size") and ratio_map[cid].get("coram_size"):
        r["coram_size"] = ratio_map[cid]["coram_size"]
    # NEW: enrich with opinion/outcome metadata
    if not r.get("opinion_type") and ratio_map[cid].get("opinion_type"):
        r["opinion_type"] = ratio_map[cid]["opinion_type"]
    if not r.get("split_ratio") and ratio_map[cid].get("split_ratio"):
        r["split_ratio"] = ratio_map[cid]["split_ratio"]
    if not r.get("disposal_nature") and ratio_map[cid].get("disposal_nature"):
        r["disposal_nature"] = ratio_map[cid]["disposal_nature"]
    if not r.get("year") and ratio_map[cid].get("year"):
        r["year"] = ratio_map[cid]["year"]
```

**Step 2: Pass new fields into `precedent_map` construction**

In `strategy_nodes.py`, find `search_precedents_node` (line ~264-297). The `precedent_map.append()` dict currently has: case_id, title, citation, court, bench_type, strength, is_overruled, ratio, relevance_to_argument.

Add the new fields:

```python
precedent_map.append({
    "case_id": cid,
    "title": r.get("title"),
    "citation": r.get("citation"),
    "court": court,
    "year": r.get("year"),
    "bench_type": bench,
    "coram_size": r.get("coram_size"),
    "opinion_type": r.get("opinion_type", ""),
    "split_ratio": r.get("split_ratio", ""),
    "disposal_nature": r.get("disposal_nature", ""),
    "strength": strength,
    "is_overruled": is_overruled,
    "ratio": r.get("ratio", ""),
    "relevance_to_argument": r.get("source_query", ""),
})
```

**Step 3: Run tests**

Run: `cd backend && python -m pytest tests/unit/ -x -q -k "strategy or enrich" 2>&1 | tail -10`

**Step 4: Commit**

```bash
git commit -m "feat(strategy): enrich precedent_map with opinion_type, split_ratio, disposal_nature, year"
```

---

## Task A2: Enrich precedent strength with opinion_type and split_ratio

**Files:**
- Modify: `backend/app/core/legal/precedent_strength.py` (~line 68)
- Test: `backend/tests/unit/test_precedent_strength.py`

**Step 1: Add parameters to `classify_precedent_strength`**

```python
def classify_precedent_strength(
    source_court: str,
    source_bench: str | None,
    target_court: str | None = None,
    target_bench: str | None = None,
    overruled: bool = False,
    source_coram_size: int | None = None,
    target_coram_size: int | None = None,
    opinion_type: str | None = None,    # NEW
    split_ratio: str | None = None,     # NEW
) -> PrecedentStrength:
```

After the existing logic determines BINDING/PERSUASIVE, add a refinement step. This doesn't change the enum value (still BINDING/PERSUASIVE/etc.) but we can store the opinion metadata for the LLM to use. The key change: for the LLM prompt, we want to convey that a 3-2 split BINDING is weaker than a unanimous BINDING. Add a `strength_note` to the precedent_map entry.

Actually — keep `classify_precedent_strength` unchanged (it returns an enum, adding granularity would break existing code). Instead, in `search_precedents_node`, add a `strength_note` field to each precedent:

```python
# After classify_precedent_strength call
strength_note = ""
if r.get("opinion_type") == "plurality":
    strength_note = "plurality opinion (no majority — weakest form of binding)"
elif r.get("split_ratio") and ":" in r.get("split_ratio", ""):
    parts = r["split_ratio"].split(":")
    if len(parts) == 2 and parts[0].strip().isdigit() and parts[1].strip().isdigit():
        majority = int(parts[0].strip())
        minority = int(parts[1].strip())
        if minority > 0:
            strength_note = f"split decision ({r['split_ratio']}) — dissent present"
        else:
            strength_note = "unanimous"
elif r.get("opinion_type") == "unanimous":
    strength_note = "unanimous"

precedent_map.append({
    ...
    "strength_note": strength_note,
})
```

**Step 2: Run tests**

Run: `cd backend && python -m pytest tests/unit/ -x -q -k "strategy or precedent" 2>&1 | tail -10`

**Step 3: Commit**

```bash
git commit -m "feat(strategy): add strength_note (unanimous/split/plurality) to precedent_map"
```

---

## Task A3: Add arguments_raised to adversarial/counter-argument context

**Files:**
- Modify: `backend/app/core/agents/nodes/strategy_nodes.py` (counter_arguments_node ~line 581, adversarial_search ~line 446)

**Step 1: Fetch `arguments_raised` for adversarial results**

In `adversarial_search_strategy_node`, after the parallel search completes and `all_results` is built, fetch `arguments_raised` for the found cases:

```python
# After all_results is assembled
if all_results:
    adv_case_ids = [r.get("case_id") for r in all_results if r.get("case_id") and not r["case_id"].startswith(("ik:", "statute:"))]
    if adv_case_ids:
        try:
            async with async_session_factory() as db:
                placeholders = ", ".join(f":id{i}" for i in range(len(adv_case_ids)))
                args_result = await db.execute(
                    text(f"SELECT id::text, arguments_raised FROM cases WHERE id::text IN ({placeholders}) AND arguments_raised IS NOT NULL"),
                    {f"id{i}": cid for i, cid in enumerate(adv_case_ids)},
                )
                args_map = {str(row["id"]): row["arguments_raised"] for row in args_result.mappings().all()}
                for r in all_results:
                    cid = r.get("case_id", "")
                    if cid in args_map:
                        r["arguments_raised"] = args_map[cid]
        except Exception as e:
            logger.warning("Failed to fetch arguments_raised for adversarial results: %s", e)
```

**Step 2: Include arguments_raised in counter_arguments_node context**

In `counter_arguments_node`, when building `all_precedents` from adversarial results, include `arguments_raised`:

```python
for ar in adversarial_results:
    entry = {
        "title": ar.get("title", ""),
        "citation": ar.get("citation", ""),
        "ratio": ar.get("chunk_text", "") or ar.get("snippet", ""),
        "strength": ar.get("strength", "UNKNOWN"),
        "adversarial": True,
    }
    if ar.get("arguments_raised"):
        entry["arguments_raised_in_case"] = ar["arguments_raised"]
    all_precedents.append(entry)
```

**Step 3: Run tests, commit**

```bash
git commit -m "feat(strategy): add arguments_raised to adversarial and counter-argument context"
```

---

## Task B1: CRAG Relevance Evaluation Node

**Files:**
- Modify: `backend/app/core/agents/nodes/strategy_nodes.py` (add new node)
- Modify: `backend/app/core/agents/state.py` (add new fields to StrategyState)
- Modify: `backend/app/core/agents/strategy.py` (wire into graph)
- Modify: `backend/app/core/legal/prompts.py` (add strategy-specific CRAG prompt)
- Test: `backend/tests/unit/test_strategy_nodes.py`

**Step 1: Add state fields**

In `backend/app/core/agents/state.py`, add to `StrategyState`:

```python
    relevance_scores: list[dict]        # CRAG evaluation scores per result
    extracted_passages: list[dict]       # Key passages from relevant results
```

**Step 2: Add CRAG prompt for strategy context**

In `backend/app/core/legal/prompts.py`, add (reuse the research agent's `RESEARCH_EVALUATE_AND_EXTRACT_SYSTEM` and `EVALUATE_AND_EXTRACT_SCHEMA` directly — they're generic enough):

```python
# Import at top of strategy_nodes.py:
from app.core.legal.prompts import (
    RESEARCH_EVALUATE_AND_EXTRACT_SYSTEM,
    EVALUATE_AND_EXTRACT_SCHEMA,
)
```

No new prompt needed — the research agent's CRAG prompt is already generic.

**Step 3: Implement evaluate_relevance_node**

In `strategy_nodes.py`, add a new node function. Simplified version of research agent's evaluate_and_extract — no deep-read, no IK fragment fetching, just CRAG scoring and filtering:

```python
async def evaluate_relevance_node(
    state: StrategyState,
    llm: LLMProvider,
) -> dict:
    """CRAG relevance evaluation — score and filter search results."""
    search_results = state.get("search_results", [])
    case_facts = state.get("case_facts", "")
    legal_elements = state.get("legal_elements", [])

    if not search_results:
        return {"relevance_scores": [], "extracted_passages": []}

    # Build evaluation context
    elements_text = "\n".join(
        f"- {e.get('description', '')}" for e in legal_elements[:5]
    )
    query_context = f"Case facts: {case_facts[:500]}\n\nLegal elements:\n{elements_text}"

    # Format results for batch evaluation (batches of 15)
    relevance_scores: list[dict] = []
    extracted_passages: list[dict] = []
    kept_results: list[dict] = []

    for batch_start in range(0, len(search_results), 15):
        batch = search_results[batch_start:batch_start + 15]
        formatted = "\n\n".join(
            f"[Doc {i}] case_id={r.get('case_id', 'N/A')}\n"
            f"Title: {r.get('title', 'N/A')}\n"
            f"Court: {r.get('court', 'N/A')} | Year: {r.get('year', 'N/A')} | Bench: {r.get('bench_type', 'N/A')}\n"
            f"Ratio: {(r.get('ratio', '') or r.get('snippet', '') or r.get('chunk_text', ''))[:500]}"
            for i, r in enumerate(batch)
        )

        try:
            result = await llm.generate_structured(
                prompt=f"{query_context}\n\nDocuments:\n{formatted}",
                system=RESEARCH_EVALUATE_AND_EXTRACT_SYSTEM,
                output_schema=EVALUATE_AND_EXTRACT_SCHEMA,
            )
            for ev in result.get("evaluations", []):
                relevance_scores.append(ev)
                if ev.get("verdict") in ("correct", "ambiguous"):
                    # Keep this result
                    matching = [r for r in batch if r.get("case_id") == ev.get("case_id")]
                    if matching:
                        kept_results.append(matching[0])
                    if ev.get("passage"):
                        extracted_passages.append({
                            "case_id": ev.get("case_id"),
                            "passage": ev["passage"],
                            "is_verbatim": ev.get("is_verbatim", False),
                            "ratio_or_obiter": ev.get("ratio_or_obiter", "uncertain"),
                        })
        except Exception as e:
            logger.warning("CRAG evaluation batch failed: %s — keeping all results in batch", e)
            kept_results.extend(batch)

    # If CRAG filtered too aggressively, keep at least 5 results
    if len(kept_results) < 5 and len(search_results) >= 5:
        kept_results = search_results[:max(5, len(kept_results))]

    # Rebuild precedent_map for kept results only
    # (The downstream nodes will rebuild from search_results)

    return {
        "search_results": kept_results,
        "relevance_scores": relevance_scores,
        "extracted_passages": extracted_passages,
    }
```

**Step 4: Wire into graph**

In `strategy.py`, add the node closure:
```python
async def evaluate_relevance(state: StrategyState) -> dict:
    return await evaluate_relevance_node(state, flash_llm)
```

Register: `graph.add_node("evaluate_relevance", evaluate_relevance)`

Update edges:
```python
# OLD: search_precedents → assess_strength
# NEW: search_precedents → evaluate_relevance → assess_strength
graph.add_edge("search_precedents", "evaluate_relevance")
graph.add_edge("evaluate_relevance", "assess_strength")
```

Remove the old direct edge from search_precedents to assess_strength.

**Step 5: Update STRATEGY_STEPS in frontend**

In `frontend/src/app/agents/strategy/page.tsx`, add `"evaluate_relevance"` after `"search_precedents"`.

In `frontend/src/components/agent-step-timeline.tsx`, add label:
```typescript
evaluate_relevance: "Evaluating relevance (CRAG)",
```

**Step 6: Run tests, commit**

```bash
git commit -m "feat(strategy): add CRAG relevance evaluation node — filter irrelevant search results"
```

---

## Task B2: Footnote Management Node

**Files:**
- Modify: `backend/app/core/agents/nodes/strategy_nodes.py` (add new node)
- Modify: `backend/app/core/agents/state.py` (add footnotes field)
- Modify: `backend/app/core/agents/strategy.py` (wire into graph, update checkpoint_memo)

**Step 1: Add `footnotes` to StrategyState**

```python
footnotes: list[dict]              # Structured footnote objects
```

**Step 2: Implement format_strategy_footnotes_node**

Simplified version of research agent's footnote pipeline. The strategy memo uses `[N]` markers (not `[^N]`), so adjust the regex.

```python
async def format_strategy_footnotes_node(state: StrategyState) -> dict:
    """Parse [N] references from memo and build structured footnotes."""
    memo = state.get("strategy_memo", "")
    search_results = state.get("search_results", [])
    precedent_map = state.get("precedent_map", [])

    if not memo:
        return {"footnotes": []}

    # Step 1: Find all [N] references in memo
    ref_numbers = sorted(set(int(n) for n in re.findall(r"\[(\d+)\]", memo)))

    if not ref_numbers:
        return {"footnotes": []}

    # Step 2: Build citation lookup from search_results + precedent_map
    citation_lookup: dict[int, dict] = {}

    # Try to find a "Sources" section at the end of the memo
    sources_match = re.search(r"(?:Sources|References|Authorities Cited|Bibliography)\s*[-:]*\s*\n(.*)", memo, re.DOTALL | re.IGNORECASE)
    if sources_match:
        sources_text = sources_match.group(1)
        for line in sources_text.strip().split("\n"):
            line = line.strip()
            ref_match = re.match(r"\[(\d+)\]\s*(.+)", line)
            if ref_match:
                num = int(ref_match.group(1))
                citation_text = ref_match.group(2).strip()
                citation_lookup[num] = {"citation_text": citation_text}

    # Step 3: Match each reference to a search result
    footnotes: list[dict] = []
    for ref_num in ref_numbers:
        fn: dict = {
            "number": ref_num,
            "title": "",
            "citation": "",
            "court": "",
            "year": None,
            "case_id": None,
            "bench_size": None,
            "opinion_type": "",
            "verification_status": "pending",
            "source_url": "",
            "is_used": True,
        }

        # Try citation_lookup first (from Sources section)
        if ref_num in citation_lookup:
            citation_text = citation_lookup[ref_num].get("citation_text", "")
            # Match against precedent_map
            for p in precedent_map:
                p_title = (p.get("title") or "").upper()
                p_citation = (p.get("citation") or "").upper()
                if p_title and p_title[:30] in citation_text.upper():
                    fn["title"] = p.get("title", "")
                    fn["citation"] = p.get("citation", "")
                    fn["court"] = p.get("court", "")
                    fn["year"] = p.get("year")
                    fn["case_id"] = p.get("case_id")
                    fn["bench_size"] = p.get("coram_size")
                    fn["opinion_type"] = p.get("opinion_type", "")
                    fn["source_url"] = f"/case/{p['case_id']}" if p.get("case_id") else ""
                    fn["verification_status"] = "verified_pg"
                    break
                elif p_citation and p_citation in citation_text.upper():
                    fn["title"] = p.get("title", "")
                    fn["citation"] = p.get("citation", "")
                    fn["court"] = p.get("court", "")
                    fn["year"] = p.get("year")
                    fn["case_id"] = p.get("case_id")
                    fn["bench_size"] = p.get("coram_size")
                    fn["opinion_type"] = p.get("opinion_type", "")
                    fn["source_url"] = f"/case/{p['case_id']}" if p.get("case_id") else ""
                    fn["verification_status"] = "verified_pg"
                    break

            if not fn["title"]:
                fn["citation"] = citation_text
                fn["verification_status"] = "unverified"

        footnotes.append(fn)

    # Strip the Sources section from memo (footnotes are now structured data)
    if sources_match:
        clean_memo = memo[:sources_match.start()].rstrip()
    else:
        clean_memo = memo

    return {"footnotes": footnotes, "strategy_memo": clean_memo}
```

**Step 3: Wire into graph**

In `strategy.py`:
```python
async def format_footnotes(state: StrategyState) -> dict:
    return await format_strategy_footnotes_node(state)

graph.add_node("format_footnotes", format_footnotes)

# OLD: synthesize_strategy → verify
# NEW: synthesize_strategy → format_footnotes → verify
graph.add_edge("synthesize_strategy", "format_footnotes")
graph.add_edge("format_footnotes", "verify")
```

Remove old direct edge from synthesize_strategy to verify.

**Step 4: Update checkpoint_memo to include footnotes**

```python
checkpoint_memo = make_checkpoint_node(
    "memo",
    "Here is the argument memo with footnotes and quality assessment. Any revisions?",
    {
        "strategy_memo": ("strategy_memo", ""),
        "confidence": ("confidence", 0.0),
        "footnotes": ("footnotes", []),
        "contradictions": ("contradictions", []),
    },
)
```

**Step 5: Update frontend steps + timeline labels**

Add `"format_footnotes"` after `"synthesize_strategy"` in STRATEGY_STEPS.
Add label: `format_footnotes: "Building footnotes",` (already exists from research agent labels).

**Step 6: Run tests, commit**

```bash
git commit -m "feat(strategy): add footnote management node — structured [N] reference parsing"
```

---

## Task B3: Legal Quality Check Node + Retry Loop

**Files:**
- Modify: `backend/app/core/agents/nodes/strategy_nodes.py` (add new node)
- Modify: `backend/app/core/agents/state.py` (add quality fields)
- Modify: `backend/app/core/agents/strategy.py` (wire with retry loop)

**Step 1: Add state fields**

In `StrategyState`:
```python
    legal_quality_result: dict         # LeMAJ quality assessment
    quality_attempts: int              # retry counter
```

**Step 2: Implement quality_check_node**

```python
async def quality_check_node(
    state: StrategyState,
    llm: LLMProvider,
) -> dict:
    """LeMAJ-inspired legal quality assessment with retry routing."""
    memo = state.get("strategy_memo", "")
    search_results = state.get("search_results", [])
    quality_attempts = state.get("quality_attempts", 0)

    if not memo:
        return {"legal_quality_result": {"overall_score": 0, "pass_threshold": False}, "quality_attempts": quality_attempts + 1}

    # Build evidence context (flattened from search results)
    evidence_items = []
    for r in search_results[:30]:
        evidence_items.append(
            f"[{r.get('case_id', 'N/A')}] {r.get('title', 'N/A')} ({r.get('citation', '')})\n"
            f"Ratio: {(r.get('ratio', '') or r.get('snippet', ''))[:300]}"
        )
    evidence = "\n\n".join(evidence_items)

    try:
        result = await llm.generate_structured(
            prompt=f"MEMO:\n{memo}\n\nEVIDENCE:\n{evidence}",
            system=LEGAL_QUALITY_CHECK_SYSTEM,
            output_schema=LEGAL_QUALITY_CHECK_SCHEMA,
        )
    except Exception as e:
        logger.error("Quality check LLM failed: %s", e)
        return {"legal_quality_result": {"overall_score": 0.5, "pass_threshold": True}, "quality_attempts": quality_attempts + 1}

    overall_score = result.get("overall_score", 0.5)
    pass_threshold = overall_score >= 0.7
    quality_result = {
        "overall_score": overall_score,
        "data_points": result.get("data_points", []),
        "omissions": result.get("omissions", []),
        "logical_issues": result.get("logical_issues", []),
        "pass_threshold": pass_threshold,
    }

    output: dict = {
        "legal_quality_result": quality_result,
        "quality_attempts": quality_attempts + 1,
    }

    # If failed and can retry, build feedback for synthesis retry
    if not pass_threshold and quality_attempts < 2:
        issues = []
        for lp in result.get("logical_issues", []):
            issues.append(f"- Logical issue: {lp}")
        for om in result.get("omissions", []):
            issues.append(f"- Omission: {om.get('missed_authority', 'N/A')} ({om.get('relevance', '')})")
        for dp in result.get("data_points", []):
            if dp.get("supported") == "unsupported":
                issues.append(f"- Unsupported claim: {dp.get('claim', '')[:100]}")
        if issues:
            output["error"] = "[QUALITY_RETRY] Quality check failed. Please address:\n" + "\n".join(issues[:10])

    return output
```

**Step 3: Add imports**

At top of `strategy_nodes.py`:
```python
from app.core.legal.prompts import (
    LEGAL_QUALITY_CHECK_SYSTEM,
    LEGAL_QUALITY_CHECK_SCHEMA,
)
```

**Step 4: Wire into graph with retry loop**

In `strategy.py`:

```python
async def quality_check(state: StrategyState) -> dict:
    return await quality_check_node(state, llm)

graph.add_node("quality_check", quality_check)
```

Add routing function at module level:
```python
def route_after_quality(state: dict) -> str:
    """Route after quality check: retry synthesis or proceed to checkpoint."""
    qr = state.get("legal_quality_result", {})
    error = state.get("error", "")
    if error and "[QUALITY_RETRY]" in error and state.get("quality_attempts", 0) < 3:
        return "synthesize_strategy"
    return "checkpoint_memo"
```

Update edges:
```python
# OLD: verify → checkpoint_memo
# NEW: verify → quality_check → [conditional: synthesize_strategy or checkpoint_memo]
graph.add_edge("verify", "quality_check")
graph.add_conditional_edges(
    "quality_check",
    route_after_quality,
    {"synthesize_strategy": "synthesize_strategy", "checkpoint_memo": "checkpoint_memo"},
)
```

Remove old direct edge from verify to checkpoint_memo.

**Step 5: Update checkpoint_memo to show quality result**

Already done in Task B2's step 4. Add `legal_quality_result` if not already there:
```python
{"legal_quality_result": ("legal_quality_result", {})}
```

**Step 6: Update frontend steps**

Add `"quality_check"` after `"verify"` in STRATEGY_STEPS.
Add label: `quality_check: "Legal quality check",` (already exists from research agent labels).

**Step 7: Run ALL strategy tests**

```bash
cd backend && python -m pytest tests/unit/ -x -q -k "strategy" 2>&1 | tail -15
```

**Step 8: Commit**

```bash
git commit -m "feat(strategy): add legal quality check with retry loop — LeMAJ-inspired assessment"
```

---

## Summary

| Task | What | Files | New LLM Calls |
|------|------|-------|---------------|
| A1 | Enrich precedent_map (6 fields) | common.py, strategy_nodes.py | 0 |
| A2 | Add strength_note (unanimous/split) | strategy_nodes.py | 0 |
| A3 | Add arguments_raised to adversarial context | strategy_nodes.py | 0 |
| B1 | CRAG relevance evaluation | strategy_nodes.py, state.py, strategy.py, prompts.py | 1 Flash call |
| B2 | Footnote management | strategy_nodes.py, state.py, strategy.py | 0 |
| B3 | Legal quality check + retry loop | strategy_nodes.py, state.py, strategy.py | 1-2 Pro calls |

**Execution order:** A1 → A2 → A3 → B1 → B2 → B3

**New graph (17 nodes):**
```
START → analyze_facts → element_decomposition → fetch_judge → [HITL] →
search_precedents → evaluate_relevance → assess_strength →
generate_arguments_irac → [HITL] →
adversarial_search → counter_and_judge → argument_ordering →
synthesize_strategy → format_footnotes → verify →
quality_check → [route: pass→checkpoint_memo, fail→synthesize_strategy] →
[HITL] → END
```
