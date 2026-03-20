# Research Agent V3 — Sequential-Reactive Pipeline Design

**Date:** 2026-03-20
**Status:** Approved
**Approach:** Staged Pipeline (5 stages, sequential between stages, parallel within)

## Problem Statement

Research Agent V2 dispatches all workers in parallel — statute, case law, graph, IK, web all fire at once. This is fast but dumb: the case law worker doesn't know what the statute says, so it searches with generic queries instead of element-specific ones. A world-class Indian lawyer reads the statute FIRST, decomposes it into legal elements, THEN searches for cases interpreting each element.

### 9 Gaps Identified in Audit

| # | Gap | Impact | Fix Type |
|---|-----|--------|----------|
| 1 | No statute-to-case linking | Case searches don't reference statute text | New node |
| 2 | No procedural posture awareness | Trial vs appeal changes which precedents matter | Schema + prompt |
| 3 | No element-wise decomposition | Complex questions not broken into testable elements | New node |
| 4 | No adversarial research | Doesn't search for counter-arguments | New node (togglable) |
| 5 | No bench-strength filtering in search | Retrieves all cases equally | Filter logic |
| 6 | No statutory-temporal validation | Old-code cases cited without checking new-code wording | New node |
| 7 | Ratio vs obiter not distinguished | All holdings treated equally | Prompt upgrade |
| 8 | No risk quantification | Confidence is HIGH/MEDIUM/LOW, no outcome probability | Prompt upgrade |
| 9 | No commentary sources | No Ratanlal, Mulla, Sarkar | Future (out of scope) |

Gap 9 (commentary sources) requires new data ingestion and is deferred.

## Design Decisions

- **Full sequential pipeline** — statute BEFORE case search, each stage informs the next
- **Fast path upgraded** — even simple queries read the statute before answering
- **Adversarial research user-togglable** — OFF by default, user enables at plan HITL checkpoint
- **All 9 gaps addressed** (gap 9 deferred to future)

---

## Architecture: 5-Stage Pipeline

```
START
  │
  ├── rewrite_query ──┐
  │                    ▼
  └── classify ──► statute_lookup          ◄── STAGE 1: UNDERSTAND
                       │
                       ▼
              element_decomposition         ◄── STAGE 2: DECOMPOSE
                       │
                       ▼
                plan_research
                       │
                       ▼
               checkpoint_plan (HITL)
                       │  [adversarial toggle, procedural context]
                       ▼
              pre_warm_embeddings
                       │
                       ▼
               dispatch_workers             ◄── STAGE 3: INVESTIGATE
              ┌────┬────┬────┬────┬────┬────┐
              │    │    │    │    │    │    │
           case named stat  ik  web graph community
           _law _case _ute      search
              │    │    │    │    │    │    │
              └────┴────┴────┴────┴────┴────┘
                       │
                       ▼
                gather_results
                       │
                       ▼
          batch_cot_with_reflection
                       │
                       ▼
           evaluate_and_extract             ◄── STAGE 4: CHALLENGE
                       │
                       ▼
             adversarial_search (if toggled)
                       │
                       ▼
            temporal_validation
                       │
                       ▼
               gap_analysis
                       │
              ┌────────┴────────┐
              ▼                 ▼
      dispatch_workers   checkpoint_findings (HITL)
      (refine, max 2)          │
                               ▼
                    speculative_synthesis    ◄── STAGE 5: SYNTHESIZE
                               │
                               ▼
                      format_footnotes
                               │
                               ▼
                         verify_v2
                               │
                               ▼
                       quality_check
                               │
                               ▼
                     checkpoint_memo (HITL)
                               │
                               ▼
                              END
```

### Fast Path (Simple Queries)

```
START → rewrite + classify (parallel) → statute_lookup → fast_path_search → fast_path_synthesis → format_footnotes → END
```

Fast path now goes through statute_lookup so even simple answers cite the actual statute text.

---

## New Nodes

### 1. `statute_lookup_node` (Stage 1)

**File:** `backend/app/core/agents/nodes/common.py`
**Purpose:** Read relevant statute text BEFORE planning.

**Input:** `state["rewritten_query"]`, `state["key_entities"]` from classify
**Output:** `state["statute_context"]`

**Logic:**
1. Extract statute references from rewritten_query + key_entities (regex: `Section \d+[A-Z]? (?:of |)(?:IPC|BNS|CrPC|BNSS|IEA|BSA|CPC|COI)` and `Article \d+`)
2. Auto-expand via IPC_TO_BNS_MAP / CRPC_TO_BNSS_MAP / EVIDENCE_TO_BSA_MAP
3. For each reference: `SELECT * FROM statutes WHERE act_short_name = :act AND section_number = :sec`
4. Semantic search in Pinecone: `filter={"document_type": {"$in": ["statute", "constitution"]}}`, top_k=5
5. Deduplicate by (act_short_name, section_number)
6. For repealed sections: also fetch the new-code equivalent text

**Performance:** ~500ms (PG query + 1 Pinecone call). Not a bottleneck.

### 2. `element_decomposition_node` (Stage 2)

**File:** `backend/app/core/agents/nodes/common.py`
**Purpose:** Break legal question into constituent elements.

**Input:** `state["rewritten_query"]`, `state["statute_context"]`, `state["complexity"]`
**Output:** `state["legal_elements"]`

**LLM:** Gemini Flash (fast, structured output)
**Prompt:** `ELEMENT_DECOMPOSITION_SYSTEM`

```
You are an expert Indian legal analyst. Given a legal question and the relevant
statute text, decompose the question into discrete legal elements that must each
be independently researched.

For criminal law questions:
- Actus reus elements (physical act required)
- Mens rea elements (intent/knowledge required)
- Exception/defense applicability
- Sentencing considerations
- Procedural requirements

For civil law questions:
- Cause of action elements
- Limitation period
- Jurisdiction requirements
- Burden of proof
- Remedy available

For constitutional questions:
- Fundamental right scope
- Reasonable restriction grounds
- Proportionality test
- Doctrine of basic structure (if applicable)

For each element:
- element_id: short snake_case identifier
- description: what needs to be established (1-2 sentences)
- statute_basis: which section/article grounds this element (quote the text)
- search_query: what to search for in case law
- is_contested: whether this element is likely disputed in the query context

Return 1-2 elements for simple queries, 3-6 for complex/multi_issue queries.
Do NOT add elements for topics not raised by the query.
```

**Schema:**
```json
{
  "elements": [
    {
      "element_id": "string",
      "description": "string",
      "statute_basis": "string",
      "search_query": "string",
      "is_contested": "boolean"
    }
  ]
}
```

### 3. `adversarial_search_node` (Stage 4)

**File:** `backend/app/core/agents/nodes/research_nodes.py`
**Purpose:** Find cases AGAINST the emerging conclusion.

**Input:** `state["worker_results"]`, `state["legal_elements"]`, `state["worker_reasonings"]`, `state["include_adversarial"]`
**Output:** Appends to `state["worker_results"]` with `metadata: {"adversarial": true}`

**Gate:** If `state["include_adversarial"]` is False, returns `{}` (no-op pass-through).

**LLM:** Gemini Flash
**Prompt:** `ADVERSARIAL_SEARCH_SYSTEM`

```
You are opposing counsel reviewing your opponent's research. Given the findings
so far, identify the 2-3 strongest counter-arguments and generate targeted
search queries.

Focus on:
1. Cases reaching the OPPOSITE conclusion on similar facts
2. Cases DISTINGUISHING the key authorities being relied upon
3. Statutory provisions that limit or qualify the main provision
4. Higher bench decisions that narrow the cited authorities

For each counter-argument:
- counter_thesis: the opposing argument (1-2 sentences)
- search_query: NL query to find supporting cases
- boolean_query: keyword query for FTS/IK
- target_source: "case_law" | "ik_search"
- priority: 1 (strongest) to 3

Do NOT generate more than 3 counter-arguments. Focus on quality over quantity.
```

**Execution:** For each counter-argument, dispatches a case_law_worker or ik_search_worker (reusing existing workers). Results are tagged with `adversarial: true` in metadata.

### 4. `temporal_validation_node` (Stage 4)

**File:** `backend/app/core/agents/nodes/research_nodes.py`
**Purpose:** Check old-code cases against new-code wording.

**Input:** `state["worker_results"]`, `state["statute_context"]`
**Output:** `state["temporal_warnings"]`

**Logic (deterministic — NO LLM call):**
```python
for result in worker_results:
    for case_result in result.results:
        acts_cited = case_result.get("acts_cited", [])
        for act_ref in acts_cited:
            # Check if this is an old code reference
            if is_old_code(act_ref):  # IPC, CrPC, IEA
                old_section = extract_section(act_ref)
                new_section = map_to_new_code(old_section)  # via constants.py

                old_text = find_in_statute_context(old_section)
                new_text = find_in_statute_context(new_section)

                if old_text and new_text:
                    similarity = text_similarity(old_text, new_text)
                    if similarity < 0.8:
                        warnings.append(TemporalWarning(
                            case_id=case_result["case_id"],
                            old_section=act_ref,
                            new_section=new_section_ref,
                            similarity=similarity,
                            warning=f"Section wording changed ({similarity:.0%} similar). "
                                    f"Case interpretation may not apply to new code."
                        ))
```

**Performance:** Pure Python, no external calls. ~10ms.

---

## Modified Nodes

### `plan_research_node` — Updated Prompt

The planner now receives `statute_context` and `legal_elements` as input. Updated system prompt:

```
[Existing RESEARCH_PLAN_SYSTEM content]

ADDITIONAL CONTEXT PROVIDED:
- Statute text for relevant provisions (READ THIS CAREFULLY before planning)
- Legal elements decomposed from the query (each element needs targeted tasks)

PLANNING RULES (additions):
- Generate at least ONE case_law task per legal element
- Reference the specific statute section in each task's nl_query
  (e.g., "cases interpreting Section 300 Exception 1 IPC on sudden provocation")
- If an element is_contested, generate BOTH a supporting and a probing task
- Include element_id in each task's filters for traceability
- If procedural_context is "appeal", prioritize appellate court decisions
- If client_position is "accused"/"respondent", include tasks searching for
  favorable precedents from the defense perspective
```

User prompt template addition:
```
## Statute Context
{statute_context_formatted}

## Legal Elements
{elements_formatted}

## Procedural Context
Procedural stage: {procedural_context or "not specified"}
Client position: {client_position or "not specified"}
```

### `evaluate_and_extract_node` — Upgraded Prompt

Add to `RESEARCH_EVALUATE_AND_EXTRACT_SYSTEM`:

```
ADDITIONAL EVALUATION CRITERIA:

3. PRECEDENT WEIGHT (mandatory for case_law results):
   Score adjustment based on authority hierarchy:
   - Constitution Bench (5+ judges): +0.15 to base score
   - 3-judge bench: +0.10
   - Division Bench (2 judges): +0.05
   - Single Judge: no adjustment
   - High Court (when target is SC): -0.10

   A binding 3-judge bench decision at 0.5 relevance is more valuable than
   a perfectly relevant single-judge HC ruling at 0.9.

   Include bench_adjustment in your score.

4. RATIO vs OBITER DISTINCTION:
   For each passage extracted, classify:
   - "ratio": The holding is part of the core reasoning chain (binding)
   - "obiter": The statement is a passing observation, hypothetical, or
     discussion of a point not necessary for the decision (persuasive only)
   - "uncertain": Cannot determine without full judgment context

   Include ratio_or_obiter field in your output.
```

Schema additions:
```json
{
  "evaluations": [
    {
      ... existing fields ...,
      "bench_adjustment": "number",
      "adjusted_score": "number",
      "ratio_or_obiter": "enum: ratio|obiter|uncertain"
    }
  ]
}
```

### `speculative_merge` — Updated Prompt

Add to `SPECULATIVE_MERGE_SYSTEM`:

```
ADDITIONAL REQUIRED SECTIONS:

## Risk Assessment
For each legal issue analyzed, provide:
- **Likely outcome**: What will the court probably decide?
- **Probability**: HIGH (>70%) / MEDIUM (40-70%) / LOW (<40%)
- **Best case**: If the court follows [strongest authority], the outcome is...
- **Worst case**: If the court distinguishes on [specific ground], the outcome is...
- **Key swing factor**: What fact or legal argument could tip the balance?

## Counter-Arguments {include only if adversarial research was conducted}
For each counter-argument found:
- **Opposing thesis**: What the other side would argue
- **Supporting authority**: Case/statute they'd cite
- **Rebuttal**: How to respond (with authority)
- **Risk level**: How dangerous is this counter-argument? (HIGH/MEDIUM/LOW)

ADDITIONAL RULES:
- When citing a passage, note whether it is RATIO DECIDENDI (binding) or
  OBITER DICTA (persuasive only). Use [ratio] or [obiter] tags.
- Include temporal warnings in the Precedent Network section: flag any
  old-code case where the new-code wording materially differs.
- In the Quick Reference Table, add a "Bench" column showing bench size.
```

### `legal_quality_check_node` — Updated Prompt

Add to `LEGAL_QUALITY_CHECK_SYSTEM`:

```
ADDITIONAL QUALITY CHECKS:

5. RATIO vs OBITER MISUSE:
   - Flag any claim supported ONLY by obiter dicta without acknowledging
     its non-binding nature
   - Flag any obiter cited as if it were ratio

6. TEMPORAL VALIDITY:
   - Check temporal_warnings from state
   - Flag any old-code case cited without noting the new-code equivalent
   - Flag cases where the section wording materially changed

7. BENCH STRENGTH CONSISTENCY:
   - Flag where a single-judge ruling is presented as authoritative when
     a larger bench ruled differently on the same point
   - Flag where a High Court decision is cited as binding for Supreme Court matters
   - Verify precedent strength labels (BINDING/PERSUASIVE) are correct for
     the target court

8. ADVERSARIAL COMPLETENESS (if adversarial research was conducted):
   - Are counter-arguments fairly presented?
   - Is each rebuttal supported by actual authority?
   - Did the memo acknowledge weaknesses honestly?
```

### `classify_node` — Schema Addition

Add to `RESEARCH_CLASSIFY_SCHEMA`:

```json
{
  ... existing fields ...,
  "procedural_context": {
    "type": "string",
    "enum": ["pre_trial", "trial", "appeal", "slp", "writ", "advisory", null],
    "description": "Stage of the legal matter. Look for: 'filing in', 'appeal against', 'SLP', 'writ petition', 'under Article 226/32'. Null if not determinable."
  },
  "client_position": {
    "type": "string",
    "enum": ["petitioner", "respondent", "accused", "complainant", "appellant", "advisory", null],
    "description": "Client's role. Look for: 'my client is accused', 'we represent the petitioner', 'defending against', 'advise on'. Null if not determinable."
  }
}
```

### `case_law_worker` — Bench-Strength Filtering

```python
async def case_law_worker(state):
    task = state["task"]
    filters = SearchFilters(...)

    # Bench-strength filtering based on target_bench
    target_bench = task.get("filters", {}).get("target_bench")
    if target_bench == "constitutional":
        filters.bench_type = "Constitution Bench"
    elif target_bench == "full":
        filters.bench_type = "Full Bench"

    # Element context in query
    element_context = task.get("filters", {}).get("element_context", "")
    if element_context:
        # Prepend element context to query for more targeted search
        enhanced_query = f"{element_context}. {task['nl_query']}"
    else:
        enhanced_query = task["nl_query"]

    results = await parallel_hybrid_search(enhanced_query, filters=filters, ...)
```

### `fast_path_search` — Statute Context

The fast_path_search node now receives `statute_context` and includes it in the synthesis prompt:

```python
async def fast_path_search_node(state):
    # ... existing search logic ...
    return {
        "search_results": results,
        "statute_context": state.get("statute_context", []),  # pass through
    }
```

`fast_path_synthesis` prompt addition:
```
## Relevant Statute Text
{formatted_statute_context}

Use this statute text as the primary legal basis for your answer.
Cite the section number and quote relevant text directly.
```

---

## New State Schema (Complete Additions)

```python
# In state.py, add to ResearchState:

class StatuteContext(TypedDict):
    act_short_name: str
    section_number: str
    section_title: str
    section_text: str
    is_repealed: bool
    replaced_by: str
    new_code_text: str          # Auto-fetched new-code equivalent

class LegalElement(TypedDict):
    element_id: str
    description: str
    statute_basis: str
    search_query: str
    is_contested: bool

class TemporalWarning(TypedDict):
    case_id: str
    case_citation: str
    old_section: str
    new_section: str
    similarity: float
    warning: str

# New fields in ResearchState:
statute_context: list[StatuteContext]
legal_elements: list[LegalElement]
procedural_context: str                 # from classify or HITL
client_position: str                    # from classify or HITL
include_adversarial: bool               # from HITL plan checkpoint
temporal_warnings: list[TemporalWarning]
```

---

## HITL Checkpoint Changes

### Plan Checkpoint (existing, modified)

Currently shows: research tasks for review.

**Add to checkpoint display:**
```
## Research Plan
[existing task list]

## Settings
- Include adversarial analysis: [YES/NO toggle, default NO]
- Procedural context: {auto-detected or "Not specified — please select"}
  Options: Pre-trial | Trial | Appeal | SLP | Writ | Advisory
- Client position: {auto-detected or "Not specified — please select"}
  Options: Petitioner | Respondent | Accused | Complainant | Appellant | Advisory
```

User feedback from checkpoint populates:
- `state["include_adversarial"]`
- `state["procedural_context"]` (if user overrides auto-detection)
- `state["client_position"]` (if user overrides auto-detection)

---

## Files Changed/Created Summary

| File | Change Type | Description |
|------|-------------|-------------|
| `backend/app/core/agents/state.py` | MODIFY | Add StatuteContext, LegalElement, TemporalWarning TypedDicts + new ResearchState fields |
| `backend/app/core/agents/research.py` | MODIFY | Rewire graph: 5-stage pipeline, new nodes, updated routing |
| `backend/app/core/agents/nodes/common.py` | MODIFY | Add statute_lookup_node, element_decomposition_node; modify plan_research_node, classify_node |
| `backend/app/core/agents/nodes/research_nodes.py` | MODIFY | Add adversarial_search_node, temporal_validation_node; modify evaluate_extract, gap_analysis, synthesis, quality_check |
| `backend/app/core/agents/nodes/worker_nodes.py` | MODIFY | Add bench-strength filtering to case_law_worker |
| `backend/app/core/legal/prompts.py` | MODIFY | Add ELEMENT_DECOMPOSITION_SYSTEM, ADVERSARIAL_SEARCH_SYSTEM; update 5 existing prompts |
| `backend/tests/unit/agents/` | MODIFY | Update all agent tests for new flow + add tests for new nodes |

---

## Testing Strategy

1. **Unit tests for each new node** (statute_lookup, element_decomposition, adversarial_search, temporal_validation)
2. **Integration test for sequential flow** — verify statute_lookup output feeds into element_decomposition
3. **Regression tests** — existing 1845 tests must still pass (prompt changes may need fixture updates)
4. **E2E test** — run full pipeline with a known query, verify memo includes:
   - Statute text citations
   - Element-wise analysis
   - Temporal warnings (if applicable)
   - Risk assessment section
   - Counter-arguments section (if adversarial toggled)

---

## Performance Impact

| Stage | Current V2 | V3 (estimated) | Delta |
|-------|-----------|-----------------|-------|
| Stage 1 (Understand) | ~2s (classify + rewrite parallel) | ~3s (+statute_lookup) | +1s |
| Stage 2 (Decompose) | N/A (plan only, ~3s) | ~5s (element decomp + plan) | +2s |
| Stage 3 (Investigate) | ~15s (all workers parallel) | ~15s (same parallelism) | 0 |
| Stage 4 (Challenge) | ~8s (CoT + CRAG + gap) | ~12s (+adversarial +temporal) | +4s |
| Stage 5 (Synthesize) | ~20s (3 drafts + merge + verify) | ~22s (longer prompts) | +2s |
| **Total** | **~48s** | **~57s** | **+9s** |

~19% slower wall-clock time for significantly smarter research. Adversarial search adds ~8s when enabled (one additional worker round).

---

## Out of Scope

- **Commentary sources** (Ratanlal, Mulla, Sarkar) — requires new data ingestion pipeline
- **Statute amendment tracking** — requires temporal versioning of statute text
- **Multi-language research** — Hindi statute text not yet available
- **Case section deep-linking** — linking to specific paragraphs within judgments
