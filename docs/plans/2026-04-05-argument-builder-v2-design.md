# Argument Builder V2 — Quality Polish Design

**Date:** 2026-04-05
**Status:** Approved
**Goal:** Maximize argument quality by enriching metadata through existing nodes and porting 3 high-ROI research agent features.

---

## Overview

The argument builder currently operates at ~30% of available metadata richness. This design adds:
- **Bucket A:** 3 metadata enrichments (zero new LLM calls)
- **Bucket B:** 3 research agent features ported (adds ~2 min, ~30% cost)

Estimated impact: 17 nodes (up from 14), +2 min execution, +30% LLM cost.

---

## Bucket A: Metadata Enrichment

### A1. Enrich `precedent_map` with 6 new fields

Modify `search_precedents_node` in `strategy_nodes.py` to extend the SQL query in `enrich_results_with_ratio()` (or add a strategy-specific enrichment step) to fetch:

```sql
SELECT id, ratio_decidendi, bench_type, coram_size,
       opinion_type, split_ratio, disposal_nature,
       legal_propositions, statute_sections_interpreted, year
FROM cases WHERE id = ANY(:ids)
```

Each precedent in `precedent_map` gains:
- `opinion_type` — "unanimous" / "majority" / "plurality" / "per_curiam"
- `split_ratio` — "5-0", "3-2", "4-1" etc.
- `disposal_nature` — "Allowed", "Dismissed", etc.
- `legal_propositions` — discrete holdings with novelty flags (JSONB)
- `statute_sections_interpreted` — how specific sections were read (JSONB)
- `year` — already fetched, just not passed through to precedent_map

### A2. Enrich precedent strength with opinion_type and split_ratio

Modify `classify_precedent_strength()` in `backend/app/core/legal/precedent_strength.py`:
- Add `opinion_type` and `split_ratio` as optional parameters
- Unanimous 5-judge bench outranks 3-2 split 5-judge bench
- Majority > plurality for same bench size
- Refine strength into more granular levels for the LLM prompt

### A3. Add `arguments_raised` to adversarial/counter-argument context

In `adversarial_search_strategy_node` and `counter_arguments_node`, when building the precedent context for the LLM, include `arguments_raised` from search results. This grounds counter-arguments in real arguments courts actually heard.

Fetch via SQL after adversarial search:
```sql
SELECT id, arguments_raised FROM cases WHERE id = ANY(:ids) AND arguments_raised IS NOT NULL
```

---

## Bucket B: Port 3 Research Agent Features

### B1. CRAG Relevance Evaluation

**New node:** `evaluate_relevance_node` (adapted from research agent's `evaluate_and_extract_node`)

**Position in graph:** After `search_precedents`, before `assess_strength`

**What it does:**
1. Takes search_results + case_facts + legal_elements
2. Calls Flash LLM to score each result: `relevant` / `ambiguous` / `irrelevant`
3. For `ambiguous` results, fetches HOLDINGS/RATIO section from `case_sections` table
4. Filters out `irrelevant` results
5. Extracts key passages from `relevant` results into `extracted_passages`
6. Updates `search_results` and `precedent_map` with only relevant results

**Prompt:** Adapted from research agent's `CRAG_EVALUATE_SYSTEM` — scores each result against the specific legal elements and case facts.

**Schema output per result:**
```json
{
    "case_id": "...",
    "verdict": "relevant|ambiguous|irrelevant",
    "relevance_reasoning": "...",
    "key_passage": "...",
    "ratio_or_obiter": "ratio|obiter|mixed"
}
```

**Impact:** Currently ALL search results (13-48) reach argument generation, including irrelevant noise. After CRAG evaluation, only verified-relevant results reach the LLM, improving argument precision.

### B2. Footnote Management

**New node:** `format_strategy_footnotes_node` (adapted from research agent's `format_footnotes_node`)

**Position in graph:** After `synthesize_strategy`, before `verify`

**What it does:**
1. Parses `[N]` numbered references from the strategy memo
2. Builds a citation registry mapping each `[N]` to a search result:
   - Priority 1: Deterministic match (title/citation exact match)
   - Priority 2: Fuzzy match (word overlap > 60% with ratio_decidendi)
3. Builds structured `Footnote` objects:
   ```python
   {
       "number": 1,
       "title": "Soundarajan v. State",
       "citation": "[2023] 4 S.C.R. 133",
       "court": "Supreme Court of India",
       "year": 2023,
       "bench_size": 2,
       "opinion_type": "unanimous",
       "case_id": "uuid-...",
       "source_url": "/case/uuid-...",
       "verification_status": "pending",
   }
   ```
4. Strips phantom LLM-generated footnote sections (if LLM writes its own "Sources:" section)
5. Adds `footnotes` to state for frontend rendering

**State additions:** `footnotes: list[dict]` in StrategyState

**Impact:** Currently the memo has `[1]`, `[2]` markers but no structured data. This makes footnotes clickable, verifiable, and exportable — matching research agent quality.

### B3. Legal Quality Check

**New node:** `quality_check_node` (adapted from research agent's `legal_quality_check_node`)

**Position in graph:** After `verify`, before `checkpoint_memo`. With quality retry loop.

**What it does:**
1. Calls Pro LLM with LeMAJ-inspired assessment prompt
2. Decomposes the argument memo into Legal Data Points (claims, citations, applications)
3. Checks each point against the evidence base (search_results, precedent_map)
4. Identifies:
   - **Omissions:** Relevant precedents in search results but not cited in memo
   - **Unsupported claims:** Assertions without matching evidence
   - **Logical issues:** Gaps in IRAC reasoning (rule stated but not applied, etc.)
5. Returns: `{overall_score: 0.0-1.0, data_points: [...], omissions: [...], logical_issues: [...], pass_threshold: bool}`
6. If `overall_score < 0.7` and `quality_attempts < 2`: route back to `synthesize_strategy` with quality feedback appended to prompt
7. If pass or max attempts reached: proceed to `checkpoint_memo`

**State additions:** `legal_quality_result: dict`, `quality_attempts: int` in StrategyState

**Prompt:** Adapted from research agent's quality check — evaluates legal reasoning integrity, not just content coverage.

---

## Updated Graph Flow

```
START → analyze_facts → element_decomposition → fetch_judge → [HITL: checkpoint_analysis] →
search_precedents → evaluate_relevance (NEW B1) → assess_strength →
generate_arguments_irac → [HITL: checkpoint_arguments] →
adversarial_search → counter_and_judge → argument_ordering →
synthesize_strategy → format_footnotes (NEW B2) → verify →
quality_check (NEW B3) → [route: pass→checkpoint_memo, fail→synthesize_strategy] →
[HITL: checkpoint_memo] → END
```

**17 nodes total** (14 existing + 3 new).

**Quality retry loop:** `quality_check` can route back to `synthesize_strategy` up to 2 times if quality score < 0.7. The quality feedback is appended to the synthesis prompt so the LLM addresses specific gaps.

---

## Updated `checkpoint_memo` payload

After B2 and B3, the final checkpoint shows richer data:
```python
checkpoint_memo = make_checkpoint_node(
    "memo",
    "Here is the argument memo with footnotes and quality assessment. Any revisions?",
    {
        "strategy_memo": ("strategy_memo", ""),
        "confidence": ("confidence", 0.0),
        "footnotes": ("footnotes", []),
        "legal_quality_result": ("legal_quality_result", {}),
        "contradictions": ("contradictions", []),
    },
)
```

---

## Files Changed

| File | Changes |
|---|---|
| `backend/app/core/agents/state.py` | Add `footnotes`, `legal_quality_result`, `quality_attempts`, `extracted_passages`, `relevance_scores` to StrategyState |
| `backend/app/core/agents/strategy.py` | Add 3 new nodes, update edges, update checkpoint_memo payload |
| `backend/app/core/agents/nodes/strategy_nodes.py` | Add `evaluate_relevance_node`, `format_strategy_footnotes_node`, `quality_check_node`; modify `search_precedents_node` for enrichment |
| `backend/app/core/agents/nodes/common.py` | Extend `enrich_results_with_ratio` SQL query (or add strategy-specific variant) |
| `backend/app/core/legal/prompts.py` | Add `STRATEGY_CRAG_EVALUATE_SYSTEM/SCHEMA`, `STRATEGY_QUALITY_CHECK_SYSTEM/SCHEMA` |
| `backend/app/core/legal/precedent_strength.py` | Add `opinion_type`, `split_ratio` parameters |
| `frontend/src/app/agents/strategy/page.tsx` | Update STRATEGY_STEPS, add footnote panel rendering |
| `frontend/src/components/agent-step-timeline.tsx` | Add labels for 3 new nodes |

---

## What We're NOT Porting

| Research Feature | Reason |
|---|---|
| Worker fan-out (7 workers) | Argument builder needs focused precedents, not exhaustive coverage |
| Gap analysis + refinement loop | +2 min for marginal argument quality gain |
| 3-draft speculative synthesis | Single focused memo is correct for structured arguments |
| Pre-warm embeddings | Minimal gain with current checkpoint timing |
| Query rewriting + classification | Fact analysis replaces query understanding |
| Statute lookup node | Would need full graph restructuring |

---

## Implementation Order

1. A1 — Enrich precedent_map (extend SQL, modify search_precedents_node)
2. A2 — Enrich precedent strength (modify classify_precedent_strength)
3. B1 — CRAG evaluation node (new node + prompt + wire into graph)
4. A3 — Add arguments_raised to adversarial context
5. B2 — Footnote management node (new node + wire into graph)
6. B3 — Quality check node (new node + prompt + quality retry loop + wire into graph)
7. Frontend — Update steps, add footnote panel, quality badge
