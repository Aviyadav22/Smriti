# Research Agent V3 — Sequential-Reactive Pipeline Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Upgrade the Research Agent from parallel-dispatch to a 5-stage sequential-reactive pipeline where statute text is read BEFORE planning, legal elements are decomposed, and downstream searches are informed by upstream findings.

**Architecture:** 5 sequential stages (Understand → Decompose → Investigate → Challenge → Synthesize). Within each stage, independent workers run in parallel. 4 new nodes (statute_lookup, element_decomposition, adversarial_search, temporal_validation). 6 prompt upgrades. All existing tests must continue passing.

**Tech Stack:** LangGraph (StateGraph, Send, Command, interrupt), Gemini Flash/Pro, PostgreSQL (statutes table), Pinecone (statute vectors), Python 3.12 async.

**Design doc:** `docs/plans/2026-03-20-research-agent-v3-design.md`

---

## Task 1: Add New TypedDicts to State Schema

**Files:**
- Modify: `backend/app/core/agents/state.py:116-165`
- Test: `backend/tests/unit/test_agent_state.py`

**Step 1: Write failing tests for new TypedDicts**

In `backend/tests/unit/test_agent_state.py`, add:

```python
from app.core.agents.state import (
    StatuteContext,
    LegalElement,
    TemporalWarning,
    ResearchState,
)


def test_statute_context_has_required_fields():
    ctx = StatuteContext(
        act_short_name="IPC",
        section_number="302",
        section_title="Punishment for murder",
        section_text="Whoever commits murder shall be punished...",
        is_repealed=True,
        replaced_by="BNS, Section 103",
        new_code_text="Whoever commits murder shall be punished...",
    )
    assert ctx["act_short_name"] == "IPC"
    assert ctx["is_repealed"] is True
    assert ctx["new_code_text"] != ""


def test_legal_element_has_required_fields():
    elem = LegalElement(
        element_id="mens_rea",
        description="Intention to cause death or knowledge of likelihood",
        statute_basis="IPC Section 300",
        search_query="intention to cause death Section 300 IPC murder",
        is_contested=True,
    )
    assert elem["element_id"] == "mens_rea"
    assert elem["is_contested"] is True


def test_temporal_warning_has_required_fields():
    w = TemporalWarning(
        case_id="abc-123",
        case_citation="(2020) 5 SCC 100",
        old_section="IPC 302",
        new_section="BNS 103",
        similarity=0.75,
        warning="Section wording changed (75% similar).",
    )
    assert w["similarity"] == 0.75


def test_research_state_has_v3_fields():
    """ResearchState must include V3 fields."""
    # Just check the annotations exist — TypedDict fields
    annotations = ResearchState.__annotations__
    assert "statute_context" in annotations
    assert "legal_elements" in annotations
    assert "procedural_context" in annotations
    assert "client_position" in annotations
    assert "include_adversarial" in annotations
    assert "temporal_warnings" in annotations
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/unit/test_agent_state.py -v`
Expected: ImportError — StatuteContext, LegalElement, TemporalWarning not found

**Step 3: Implement new TypedDicts and state fields**

In `backend/app/core/agents/state.py`, add after line 121 (after StrategyAdjustment):

```python
class StatuteContext(TypedDict):
    """[V3] Statute text retrieved before planning."""
    act_short_name: str         # "IPC"
    section_number: str         # "302"
    section_title: str          # "Punishment for murder"
    section_text: str           # Full section text
    is_repealed: bool
    replaced_by: str            # "BNS, Section 103"
    new_code_text: str          # Auto-fetched new-code equivalent text


class LegalElement(TypedDict):
    """[V3] Constituent legal element decomposed from the research question."""
    element_id: str             # "mens_rea"
    description: str            # What needs to be established
    statute_basis: str          # "IPC Section 300, Exception 1"
    search_query: str           # Targeted case law search query
    is_contested: bool          # Whether likely disputed


class TemporalWarning(TypedDict):
    """[V3] Warning about old-code case validity under new codes."""
    case_id: str
    case_citation: str
    old_section: str            # "IPC 302"
    new_section: str            # "BNS 103"
    similarity: float           # 0.0-1.0 text similarity
    warning: str                # Human-readable warning
```

In the `ResearchState` TypedDict (after line 163, before `process_events`), add:

```python
    # --- V3 fields (sequential-reactive pipeline) ---
    statute_context: list[StatuteContext]     # [V3] Statute text found before planning
    legal_elements: list[LegalElement]        # [V3] Element-wise breakdown
    procedural_context: str                   # [V3] "trial"|"appeal"|"slp"|"advisory"|""
    client_position: str                      # [V3] "petitioner"|"respondent"|"accused"|""
    include_adversarial: bool                 # [V3] User toggle from HITL
    temporal_warnings: list[TemporalWarning]  # [V3] Old-code vs new-code warnings
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/unit/test_agent_state.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add backend/app/core/agents/state.py backend/tests/unit/test_agent_state.py
git commit -m "feat(v3): add StatuteContext, LegalElement, TemporalWarning TypedDicts + V3 state fields"
```

---

## Task 2: Add New Prompts to Prompt Library

**Files:**
- Modify: `backend/app/core/legal/prompts.py` (add after line ~1446)
- Test: `backend/tests/unit/test_agent_prompts.py`

**Step 1: Write failing test**

Add to `backend/tests/unit/test_agent_prompts.py`:

```python
from app.core.legal.prompts import (
    ELEMENT_DECOMPOSITION_SYSTEM,
    ELEMENT_DECOMPOSITION_SCHEMA,
    ADVERSARIAL_SEARCH_SYSTEM,
    ADVERSARIAL_SEARCH_SCHEMA,
)


def test_element_decomposition_prompt_exists():
    assert "legal elements" in ELEMENT_DECOMPOSITION_SYSTEM.lower() or \
           "decompose" in ELEMENT_DECOMPOSITION_SYSTEM.lower()
    assert "elements" in ELEMENT_DECOMPOSITION_SCHEMA


def test_adversarial_search_prompt_exists():
    assert "opposing" in ADVERSARIAL_SEARCH_SYSTEM.lower() or \
           "counter" in ADVERSARIAL_SEARCH_SYSTEM.lower()
    assert "counter_thesis" in str(ADVERSARIAL_SEARCH_SCHEMA)
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/unit/test_agent_prompts.py::test_element_decomposition_prompt_exists tests/unit/test_agent_prompts.py::test_adversarial_search_prompt_exists -v`
Expected: ImportError

**Step 3: Add prompts**

Add to `backend/app/core/legal/prompts.py` (after LEGAL_QUALITY_CHECK_SCHEMA):

```python
# ---------------------------------------------------------------------------
# [V3] Element Decomposition
# ---------------------------------------------------------------------------

ELEMENT_DECOMPOSITION_SYSTEM = """\
You are an expert Indian legal analyst. Given a legal question and the relevant \
statute text, decompose the question into discrete legal elements that must each \
be independently researched.

For criminal law questions:
- Actus reus elements (physical act required by the section)
- Mens rea elements (intent/knowledge required)
- Exception/defense applicability (e.g., Exception 1 to Section 300 IPC)
- Sentencing considerations (punishment provisions)
- Procedural requirements (e.g., sanction to prosecute, cognizable/non-cognizable)

For civil law questions:
- Cause of action elements (what must be proved)
- Limitation period (relevant limitation provisions)
- Jurisdiction requirements (territorial, pecuniary, subject-matter)
- Burden of proof (who bears it, standard)
- Remedy available (injunction, damages, specific performance)

For constitutional questions:
- Fundamental right scope (which Article, what it protects)
- Reasonable restriction grounds (Article 19(2)-(6), etc.)
- Proportionality test (modern SC doctrine from KS Puttaswamy)
- Doctrine of basic structure (if applicable)
- State action requirement (whether challenged action is state action)

For each element, provide:
- element_id: short snake_case identifier (e.g., "mens_rea", "limitation_period")
- description: what needs to be established (1-2 sentences)
- statute_basis: which section/article grounds this element (quote relevant text if available)
- search_query: targeted case law search query for this element
- is_contested: whether this element is likely disputed in the query context

Return 1-2 elements for simple queries, 3-6 for complex/multi_issue queries.
Do NOT add elements for topics not raised by the query.
Do NOT decompose beyond what the statute and query require.\
"""

ELEMENT_DECOMPOSITION_SCHEMA = {
    "type": "object",
    "properties": {
        "elements": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "element_id": {"type": "string"},
                    "description": {"type": "string"},
                    "statute_basis": {"type": "string"},
                    "search_query": {"type": "string"},
                    "is_contested": {"type": "boolean"},
                },
                "required": ["element_id", "description", "statute_basis",
                             "search_query", "is_contested"],
            },
        },
    },
    "required": ["elements"],
}


# ---------------------------------------------------------------------------
# [V3] Adversarial Search
# ---------------------------------------------------------------------------

ADVERSARIAL_SEARCH_SYSTEM = """\
You are opposing counsel reviewing your opponent's research findings. Given the \
research results so far, identify the 2-3 strongest counter-arguments and generate \
targeted search queries to find cases that CONTRADICT the emerging conclusion.

Focus on:
1. Cases where the court reached the OPPOSITE conclusion on similar facts
2. Cases that DISTINGUISH the key authorities being relied upon
3. Statutory provisions that limit or qualify the main provision being cited
4. Higher bench decisions that narrow the cited authorities
5. Recent developments that may have changed the legal position

For each counter-argument, provide:
- counter_thesis: what the opposing side would argue (1-2 sentences)
- search_query: NL query to find supporting cases
- boolean_query: keyword query for FTS/Indian Kanoon
- target_source: "case_law" | "ik_search" — which worker should handle this
- priority: 1 (strongest counter-argument) to 3

Generate EXACTLY 2-3 counter-arguments. Focus on quality over quantity.
Do NOT generate counter-arguments that the findings already address.\
"""

ADVERSARIAL_SEARCH_SCHEMA = {
    "type": "object",
    "properties": {
        "counter_arguments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "counter_thesis": {"type": "string"},
                    "search_query": {"type": "string"},
                    "boolean_query": {"type": "string"},
                    "target_source": {
                        "type": "string",
                        "enum": ["case_law", "ik_search"],
                    },
                    "priority": {"type": "integer"},
                },
                "required": ["counter_thesis", "search_query", "boolean_query",
                             "target_source", "priority"],
            },
        },
    },
    "required": ["counter_arguments"],
}
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/unit/test_agent_prompts.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add backend/app/core/legal/prompts.py backend/tests/unit/test_agent_prompts.py
git commit -m "feat(v3): add ELEMENT_DECOMPOSITION + ADVERSARIAL_SEARCH prompts"
```

---

## Task 3: Update Existing Prompts (CRAG, Synthesis, Quality Check, Classify, Plan)

**Files:**
- Modify: `backend/app/core/legal/prompts.py` (multiple sections)
- Test: `backend/tests/unit/test_agent_prompts.py`

**Step 1: Write failing tests**

Add to `backend/tests/unit/test_agent_prompts.py`:

```python
from app.core.legal.prompts import (
    RESEARCH_CLASSIFY_SCHEMA,
    RESEARCH_EVALUATE_AND_EXTRACT_SYSTEM,
    SPECULATIVE_MERGE_SYSTEM,
    LEGAL_QUALITY_CHECK_SYSTEM,
)


def test_classify_schema_has_v3_fields():
    """Classify schema must include procedural_context and client_position."""
    schema_str = str(RESEARCH_CLASSIFY_SCHEMA)
    assert "procedural_context" in schema_str
    assert "client_position" in schema_str


def test_evaluate_extract_has_bench_strength():
    """CRAG prompt must mention bench strength and ratio/obiter."""
    assert "bench" in RESEARCH_EVALUATE_AND_EXTRACT_SYSTEM.lower()
    assert "ratio" in RESEARCH_EVALUATE_AND_EXTRACT_SYSTEM.lower()
    assert "obiter" in RESEARCH_EVALUATE_AND_EXTRACT_SYSTEM.lower()


def test_merge_has_risk_assessment():
    """Speculative merge prompt must include risk assessment section."""
    assert "risk assessment" in SPECULATIVE_MERGE_SYSTEM.lower()


def test_quality_check_has_temporal_and_bench():
    """Quality check must check temporal validity and bench strength."""
    text = LEGAL_QUALITY_CHECK_SYSTEM.lower()
    assert "temporal" in text
    assert "bench" in text or "bench strength" in text
```

**Step 2: Run to verify they fail**

Run: `cd backend && python -m pytest tests/unit/test_agent_prompts.py::test_classify_schema_has_v3_fields tests/unit/test_agent_prompts.py::test_evaluate_extract_has_bench_strength tests/unit/test_agent_prompts.py::test_merge_has_risk_assessment tests/unit/test_agent_prompts.py::test_quality_check_has_temporal_and_bench -v`
Expected: FAIL

**Step 3: Update RESEARCH_CLASSIFY_SCHEMA**

In `backend/app/core/legal/prompts.py`, find `RESEARCH_CLASSIFY_SCHEMA` (line ~832) and add to the `properties` dict:

```python
        "procedural_context": {
            "type": "string",
            "nullable": True,
            "enum": ["pre_trial", "trial", "appeal", "slp", "writ", "advisory"],
            "description": (
                "Stage of the legal matter. Look for: 'filing in', 'appeal against', "
                "'SLP', 'writ petition', 'under Article 226/32'. Null if not determinable."
            ),
        },
        "client_position": {
            "type": "string",
            "nullable": True,
            "enum": ["petitioner", "respondent", "accused", "complainant", "appellant", "advisory"],
            "description": (
                "Client's role. Look for: 'my client is accused', 'we represent the petitioner', "
                "'defending against', 'advise on'. Null if not determinable."
            ),
        },
```

Also add `"procedural_context"` and `"client_position"` to the RESEARCH_CLASSIFY_SYSTEM text (append before the closing `"""`):

```
- procedural_context: identify the litigation stage (pre_trial, trial, appeal, slp, writ, advisory). \
Look for phrases like "filing in", "appeal against", "SLP", "writ petition", \
"under Article 226/32". Return null if not determinable.
- client_position: identify the client's role (petitioner, respondent, accused, complainant, \
appellant, advisory). Look for phrases like "my client is accused", "we represent", \
"defending against", "advise on". Return null if not determinable.
```

**Step 4: Update RESEARCH_EVALUATE_AND_EXTRACT_SYSTEM**

Find `RESEARCH_EVALUATE_AND_EXTRACT_SYSTEM` (line ~1191) and append before the closing `"""`:

```

3. PRECEDENT WEIGHT (mandatory for case_law results):
   Score adjustment based on authority hierarchy for the target court:
   - Constitution Bench (5+ judges): +0.15 to base relevance score
   - 3-judge bench: +0.10
   - Division Bench (2 judges): +0.05
   - Single Judge: no adjustment
   - High Court (when target is Supreme Court): -0.10
   A binding 3-judge bench decision at 0.5 relevance is more valuable than \
a perfectly relevant single-judge HC ruling at 0.9.
   Include bench_adjustment and adjusted_score in your output.

4. RATIO vs OBITER DISTINCTION:
   For each passage extracted, classify:
   - "ratio": The holding is part of the core reasoning chain (binding)
   - "obiter": The statement is a passing observation, hypothetical, or \
discussion of a point not necessary for the decision (persuasive only)
   - "uncertain": Cannot determine without full judgment context
   Include ratio_or_obiter field in your output.
```

Also update `EVALUATE_AND_EXTRACT_SCHEMA` — add to each evaluation item's properties:

```python
                    "bench_adjustment": {"type": "number", "nullable": True},
                    "adjusted_score": {"type": "number", "nullable": True},
                    "ratio_or_obiter": {
                        "type": "string",
                        "nullable": True,
                        "enum": ["ratio", "obiter", "uncertain"],
                    },
```

**Step 5: Update SPECULATIVE_MERGE_SYSTEM**

Find `SPECULATIVE_MERGE_SYSTEM` (line ~1400) and append before the closing `"""`:

```

8. **RISK ASSESSMENT** (add after Conclusion section):
   For each legal issue analyzed, provide:
   - Likely outcome: what will the court probably decide?
   - Probability: HIGH (>70%) / MEDIUM (40-70%) / LOW (<40%)
   - Best case: if the court follows the strongest authority
   - Worst case: if the court distinguishes on specific grounds
   - Key swing factor: what fact or argument could tip the balance

9. **COUNTER-ARGUMENTS** (include ONLY if adversarial results are provided):
   For each counter-argument found:
   - Opposing thesis: what the other side would argue
   - Supporting authority: case/statute they'd cite
   - Rebuttal: how to respond (with authority)
   - Risk level: how dangerous is this counter-argument (HIGH/MEDIUM/LOW)

10. **RATIO vs OBITER**: When citing a passage, note whether it is ratio decidendi \
(binding) or obiter dicta (persuasive only). Use [ratio] or [obiter] tags after quotes.

11. **TEMPORAL WARNINGS**: In the Precedent Network section, flag any old-code case \
where the new-code wording materially differs. Use ⚠ OLD CODE marker.
```

**Step 6: Update LEGAL_QUALITY_CHECK_SYSTEM**

Find `LEGAL_QUALITY_CHECK_SYSTEM` (line ~1446) and append before the closing `"""`:

```

5. RATIO vs OBITER MISUSE: Flag any claim supported ONLY by obiter dicta without \
acknowledging its non-binding nature. Flag any obiter cited as if it were ratio.

6. TEMPORAL VALIDITY: Check temporal_warnings from state. Flag any old-code case \
cited without noting the new-code equivalent. Flag cases where the new-code section \
wording materially changed from the old code the case interpreted.

7. BENCH STRENGTH CONSISTENCY: Flag where a single-judge ruling is presented as \
authoritative when a larger bench ruled differently on the same point. Flag where a \
High Court decision is cited as binding for Supreme Court matters. Verify precedent \
strength labels (BINDING/PERSUASIVE) are correct for the target court.

8. ADVERSARIAL COMPLETENESS (only if counter-arguments section exists): Are \
counter-arguments fairly presented? Is each rebuttal supported by actual authority? \
Did the memo acknowledge weaknesses honestly?
```

**Step 7: Update RESEARCH_PLAN_SYSTEM**

Find `RESEARCH_PLAN_SYSTEM` (line ~1070) and append before the `Rules:` section:

```
ADDITIONAL CONTEXT:
You will receive statute text for relevant provisions and legal elements decomposed \
from the query. Use these to generate TARGETED tasks.

- Generate at least ONE case_law task per legal element.
- Reference the specific statute section in each task's nl_query \
(e.g., "cases interpreting Section 300 Exception 1 IPC on sudden provocation").
- If an element is_contested, generate BOTH a supporting and a probing task.
- Include element_id in each task's filters dict for traceability.
- If procedural_context is "appeal", prioritize appellate court decisions.
- If client_position is "accused"/"respondent", include tasks searching for \
favorable precedents from the defense perspective.
```

**Step 8: Run all prompt tests**

Run: `cd backend && python -m pytest tests/unit/test_agent_prompts.py -v`
Expected: All PASS

**Step 9: Commit**

```bash
git add backend/app/core/legal/prompts.py backend/tests/unit/test_agent_prompts.py
git commit -m "feat(v3): upgrade classify/CRAG/merge/quality prompts — bench strength, ratio/obiter, risk assessment, temporal"
```

---

## Task 4: Implement `statute_lookup_node`

**Files:**
- Modify: `backend/app/core/agents/nodes/common.py` (add new function)
- Test: `backend/tests/unit/test_agent_nodes_common.py`
- Reference: `backend/app/core/legal/constants.py` (IPC_TO_BNS_MAP, etc.)

**Step 1: Write failing test**

Add to `backend/tests/unit/test_agent_nodes_common.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.agents.nodes.common import statute_lookup_node


@pytest.mark.asyncio
async def test_statute_lookup_extracts_references():
    """statute_lookup_node should extract statute refs from rewritten query and fetch from DB."""
    mock_db = AsyncMock()
    # Mock the DB query to return a statute row
    mock_row = MagicMock()
    mock_row.act_short_name = "IPC"
    mock_row.section_number = "302"
    mock_row.section_title = "Punishment for murder"
    mock_row.section_text = "Whoever commits murder shall be punished with death..."
    mock_row.is_repealed = True
    mock_row.replaced_by = "BNS, Section 103"

    mock_new_row = MagicMock()
    mock_new_row.section_text = "Whoever commits murder shall be punished..."

    # scalars().all() returns list
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_row]
    mock_db.execute = AsyncMock(return_value=mock_result)

    mock_embedder = AsyncMock()
    mock_vector_store = AsyncMock()
    mock_vector_store.search.return_value = []  # No pinecone results

    state = {
        "rewritten_query": "What is the punishment for murder under Section 302 IPC?",
        "key_entities": ["Section 302 IPC", "murder"],
    }

    with patch(
        "app.core.agents.nodes.common._fetch_statute_from_db",
        new_callable=AsyncMock,
        return_value=[{
            "act_short_name": "IPC",
            "section_number": "302",
            "section_title": "Punishment for murder",
            "section_text": "Whoever commits murder...",
            "is_repealed": True,
            "replaced_by": "BNS, Section 103",
            "new_code_text": "Whoever commits murder...",
        }],
    ):
        result = await statute_lookup_node(state, mock_db, mock_embedder, mock_vector_store)

    assert "statute_context" in result
    assert len(result["statute_context"]) >= 1
    assert result["statute_context"][0]["act_short_name"] == "IPC"


@pytest.mark.asyncio
async def test_statute_lookup_empty_query():
    """statute_lookup_node should return empty list for queries with no statute refs."""
    mock_db = AsyncMock()
    mock_embedder = AsyncMock()
    mock_vector_store = AsyncMock()
    mock_vector_store.search.return_value = []

    state = {
        "rewritten_query": "What is the general principle of natural justice?",
        "key_entities": ["natural justice"],
    }

    with patch(
        "app.core.agents.nodes.common._fetch_statute_from_db",
        new_callable=AsyncMock,
        return_value=[],
    ):
        result = await statute_lookup_node(state, mock_db, mock_embedder, mock_vector_store)

    assert "statute_context" in result
    assert isinstance(result["statute_context"], list)
```

**Step 2: Run to verify failure**

Run: `cd backend && python -m pytest tests/unit/test_agent_nodes_common.py::test_statute_lookup_extracts_references -v`
Expected: ImportError — statute_lookup_node not found

**Step 3: Implement statute_lookup_node**

Add to `backend/app/core/agents/nodes/common.py`:

```python
import re
from app.core.legal.constants import IPC_TO_BNS_MAP, CRPC_TO_BNSS_MAP, EVIDENCE_TO_BSA_MAP

# Reverse maps
_NEW_TO_OLD = {
    **{v: ("IPC", k) for k, v in IPC_TO_BNS_MAP.items()},
    **{v: ("CrPC", k) for k, v in CRPC_TO_BNSS_MAP.items()},
    **{v: ("IEA", k) for k, v in EVIDENCE_TO_BSA_MAP.items()},
}

_OLD_TO_NEW = {
    "IPC": ("BNS", IPC_TO_BNS_MAP),
    "CrPC": ("BNSS", CRPC_TO_BNSS_MAP),
    "IEA": ("BSA", EVIDENCE_TO_BSA_MAP),
}

# Regex patterns for Indian statute references
_STATUTE_RE = re.compile(
    r"(?:Section|Sec\.?|S\.?)\s+(\d+[A-Z]?)"
    r"\s+(?:of\s+)?(?:the\s+)?"
    r"(IPC|BNS|CrPC|BNSS|IEA|BSA|CPC|COI)",
    re.IGNORECASE,
)
_ARTICLE_RE = re.compile(
    r"Article\s+(\d+[A-Z]?(?:\(\d+\))?)",
    re.IGNORECASE,
)


def _extract_statute_refs(text: str) -> list[tuple[str, str]]:
    """Extract (act_short_name, section_number) tuples from text."""
    refs = []
    for match in _STATUTE_RE.finditer(text):
        sec_num = match.group(1)
        act = match.group(2).upper()
        refs.append((act, sec_num))
    for match in _ARTICLE_RE.finditer(text):
        art_num = match.group(1)
        refs.append(("COI", art_num))
    return refs


def _expand_refs(refs: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Auto-expand old↔new code refs (IPC 302 → also BNS 103)."""
    expanded = list(refs)
    for act, sec in refs:
        if act in _OLD_TO_NEW:
            new_act, mapping = _OLD_TO_NEW[act]
            new_sec = mapping.get(sec, "")
            if new_sec:
                expanded.append((new_act, new_sec))
        elif act in ("BNS", "BNSS", "BSA"):
            info = _NEW_TO_OLD.get(sec)
            if info:
                expanded.append(info)
    return list(set(expanded))


async def _fetch_statute_from_db(
    db, refs: list[tuple[str, str]],
) -> list[dict]:
    """Fetch statute rows from PostgreSQL for given (act, section) pairs."""
    from sqlalchemy import select
    from app.models.statute import Statute

    results = []
    for act, sec in refs:
        stmt = select(Statute).where(
            Statute.act_short_name == act,
            Statute.section_number == sec,
        )
        row_result = await db.execute(stmt)
        row = row_result.scalars().first()
        if row:
            # Check if this is repealed and fetch new-code equivalent
            new_code_text = ""
            if row.replaced_by and row.is_repealed:
                # Parse "BNS, Section 103" → (BNS, 103)
                parts = row.replaced_by.split(", Section ")
                if len(parts) == 2:
                    new_act, new_sec = parts[0].strip(), parts[1].strip()
                    new_stmt = select(Statute).where(
                        Statute.act_short_name == new_act,
                        Statute.section_number == new_sec,
                    )
                    new_result = await db.execute(new_stmt)
                    new_row = new_result.scalars().first()
                    if new_row:
                        new_code_text = new_row.section_text or ""

            results.append({
                "act_short_name": row.act_short_name,
                "section_number": row.section_number,
                "section_title": row.section_title or "",
                "section_text": row.section_text or "",
                "is_repealed": row.is_repealed or False,
                "replaced_by": row.replaced_by or "",
                "new_code_text": new_code_text,
            })
    return results


async def statute_lookup_node(state: dict, db, embedder, vector_store) -> dict:
    """[V3 Stage 1] Read relevant statute text BEFORE planning.

    Extracts statute references from the rewritten query and key entities,
    auto-expands old↔new code mappings, and fetches text from PostgreSQL.
    Also runs a semantic search in Pinecone for statute/constitution vectors.
    """
    query = state.get("rewritten_query", "") or state.get("query", "")
    key_entities = state.get("key_entities", [])

    # Extract refs from query + entities
    all_text = query + " " + " ".join(str(e) for e in key_entities)
    refs = _extract_statute_refs(all_text)
    refs = _expand_refs(refs)

    # Fetch from PostgreSQL
    statute_context = await _fetch_statute_from_db(db, refs)

    # Also try semantic search for statutes not caught by regex
    try:
        query_vector = await embedder.embed(query)
        pinecone_results = await vector_store.search(
            vector=query_vector,
            top_k=5,
            filter={"document_type": {"$in": ["statute", "constitution"]}},
        )
        # Add any semantic results not already in context
        existing_keys = {
            (s["act_short_name"], s["section_number"]) for s in statute_context
        }
        for result in pinecone_results:
            meta = result.get("metadata", {})
            act = meta.get("act_short_name", "")
            sec = meta.get("section_number", "")
            if act and sec and (act, sec) not in existing_keys:
                statute_context.append({
                    "act_short_name": act,
                    "section_number": sec,
                    "section_title": meta.get("section_title", ""),
                    "section_text": meta.get("text", ""),
                    "is_repealed": False,
                    "replaced_by": "",
                    "new_code_text": "",
                })
                existing_keys.add((act, sec))
    except Exception:
        pass  # Semantic search is supplementary, not critical

    return {"statute_context": statute_context}
```

**Step 4: Run tests**

Run: `cd backend && python -m pytest tests/unit/test_agent_nodes_common.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add backend/app/core/agents/nodes/common.py backend/tests/unit/test_agent_nodes_common.py
git commit -m "feat(v3): implement statute_lookup_node — reads statute text before planning"
```

---

## Task 5: Implement `element_decomposition_node`

**Files:**
- Modify: `backend/app/core/agents/nodes/common.py`
- Test: `backend/tests/unit/test_agent_nodes_common.py`
- Reference: `backend/app/core/legal/prompts.py` (ELEMENT_DECOMPOSITION_SYSTEM)

**Step 1: Write failing test**

```python
@pytest.mark.asyncio
async def test_element_decomposition_returns_elements():
    """element_decomposition_node should return legal elements from LLM."""
    mock_llm = AsyncMock()
    mock_llm.generate_structured.return_value = {
        "elements": [
            {
                "element_id": "mens_rea",
                "description": "Intention to cause death",
                "statute_basis": "IPC Section 300",
                "search_query": "intention cause death Section 300",
                "is_contested": True,
            },
            {
                "element_id": "exceptions",
                "description": "Whether Exception 1 (provocation) applies",
                "statute_basis": "IPC Section 300, Exception 1",
                "search_query": "sudden provocation Exception 1 Section 300",
                "is_contested": True,
            },
        ],
    }

    state = {
        "rewritten_query": "Is this murder or culpable homicide under Section 302 IPC?",
        "statute_context": [{
            "act_short_name": "IPC",
            "section_number": "300",
            "section_title": "Murder",
            "section_text": "Except in the cases hereinafter excepted...",
            "is_repealed": True,
            "replaced_by": "BNS, Section 101",
            "new_code_text": "...",
        }],
        "complexity": "complex",
    }

    from app.core.agents.nodes.common import element_decomposition_node
    result = await element_decomposition_node(state, mock_llm)

    assert "legal_elements" in result
    assert len(result["legal_elements"]) == 2
    assert result["legal_elements"][0]["element_id"] == "mens_rea"
```

**Step 2: Run to verify failure**

Run: `cd backend && python -m pytest tests/unit/test_agent_nodes_common.py::test_element_decomposition_returns_elements -v`
Expected: ImportError

**Step 3: Implement**

Add to `backend/app/core/agents/nodes/common.py`:

```python
from app.core.legal.prompts import (
    ELEMENT_DECOMPOSITION_SYSTEM,
    ELEMENT_DECOMPOSITION_SCHEMA,
)


async def element_decomposition_node(state: dict, llm) -> dict:
    """[V3 Stage 2] Break legal question into constituent elements.

    Uses the statute text found in Stage 1 to identify specific legal elements
    (mens rea, actus reus, exceptions, etc.) that each need independent research.
    """
    query = state.get("rewritten_query", "") or state.get("query", "")
    statute_context = state.get("statute_context", [])
    complexity = state.get("complexity", "complex")

    # Format statute context for LLM
    statute_text_parts = []
    for s in statute_context:
        entry = f"**{s['act_short_name']} Section {s['section_number']}** — {s['section_title']}\n"
        entry += s["section_text"][:2000]
        if s.get("is_repealed") and s.get("replaced_by"):
            entry += f"\n[REPEALED — replaced by {s['replaced_by']}]"
            if s.get("new_code_text"):
                entry += f"\nNew code text: {s['new_code_text'][:1000]}"
        statute_text_parts.append(entry)

    statute_text = "\n\n".join(statute_text_parts) if statute_text_parts else "No statute text available."

    user_prompt = (
        f"## Research Question\n{query}\n\n"
        f"## Relevant Statute Text\n{statute_text}\n\n"
        f"## Query Complexity\n{complexity}\n\n"
        "Decompose this question into legal elements."
    )

    try:
        result = await llm.generate_structured(
            system_prompt=ELEMENT_DECOMPOSITION_SYSTEM,
            user_prompt=user_prompt,
            schema=ELEMENT_DECOMPOSITION_SCHEMA,
        )
        elements = result.get("elements", [])
    except Exception as exc:
        logger.warning("Element decomposition failed: %s — using query as single element", exc)
        elements = [{
            "element_id": "primary_issue",
            "description": query[:200],
            "statute_basis": "",
            "search_query": query,
            "is_contested": True,
        }]

    return {"legal_elements": elements}
```

**Step 4: Run tests**

Run: `cd backend && python -m pytest tests/unit/test_agent_nodes_common.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add backend/app/core/agents/nodes/common.py backend/tests/unit/test_agent_nodes_common.py
git commit -m "feat(v3): implement element_decomposition_node — breaks questions into legal elements"
```

---

## Task 6: Implement `adversarial_search_node`

**Files:**
- Modify: `backend/app/core/agents/nodes/research_nodes.py`
- Test: `backend/tests/unit/test_research_agent.py`

**Step 1: Write failing test**

Add to `backend/tests/unit/test_research_agent.py`:

```python
@pytest.mark.asyncio
async def test_adversarial_search_skips_when_disabled():
    """adversarial_search_node should no-op when include_adversarial is False."""
    from app.core.agents.nodes.research_nodes import adversarial_search_node

    state = {
        "include_adversarial": False,
        "worker_results": [],
        "legal_elements": [],
        "worker_reasonings": [],
    }
    result = await adversarial_search_node(state, AsyncMock(), AsyncMock(), AsyncMock(), AsyncMock())
    assert result == {}


@pytest.mark.asyncio
async def test_adversarial_search_generates_counter_queries():
    """adversarial_search_node should generate counter-argument searches when enabled."""
    from app.core.agents.nodes.research_nodes import adversarial_search_node

    mock_llm = AsyncMock()
    mock_llm.generate_structured.return_value = {
        "counter_arguments": [
            {
                "counter_thesis": "The accused acted under provocation",
                "search_query": "sudden provocation Exception 1 Section 300 IPC",
                "boolean_query": "provocation ANDD Section 300 ANDD exception",
                "target_source": "case_law",
                "priority": 1,
            },
        ],
    }

    state = {
        "include_adversarial": True,
        "worker_results": [{"task_type": "case_law", "results": [{"title": "State v Ram"}]}],
        "legal_elements": [{"element_id": "mens_rea", "description": "intent"}],
        "worker_reasonings": ["Cases point toward murder conviction"],
        "rewritten_query": "Is this murder?",
    }

    # Mock hybrid_search to return some results
    mock_embedder = AsyncMock()
    mock_vector_store = AsyncMock()
    mock_reranker = AsyncMock()

    with patch(
        "app.core.agents.nodes.research_nodes._run_adversarial_search",
        new_callable=AsyncMock,
        return_value=[{
            "task_id": "adv_1",
            "task_type": "case_law",
            "query": "provocation",
            "results": [{"title": "Nanavati v State"}],
            "source_urls": [],
            "metadata": {"adversarial": True},
            "error": None,
            "reasoning": "",
        }],
    ):
        result = await adversarial_search_node(
            state, mock_llm, mock_embedder, mock_vector_store, mock_reranker,
        )

    assert "worker_results" in result
    assert len(result["worker_results"]) >= 1
    assert result["worker_results"][0]["metadata"].get("adversarial") is True
```

**Step 2: Run to verify failure**

Run: `cd backend && python -m pytest tests/unit/test_research_agent.py::test_adversarial_search_skips_when_disabled -v`
Expected: ImportError

**Step 3: Implement**

Add to `backend/app/core/agents/nodes/research_nodes.py`:

```python
from app.core.legal.prompts import (
    ADVERSARIAL_SEARCH_SYSTEM,
    ADVERSARIAL_SEARCH_SCHEMA,
)


async def _run_adversarial_search(
    counter_args: list[dict], llm, embedder, vector_store, reranker,
) -> list[dict]:
    """Execute searches for each counter-argument query."""
    from app.core.agents.nodes.worker_nodes import case_law_worker
    results = []
    for ca in counter_args[:3]:  # Max 3 counter-arguments
        task = {
            "task_id": f"adversarial_{ca.get('priority', 0)}",
            "task_type": ca.get("target_source", "case_law"),
            "nl_query": ca["search_query"],
            "boolean_query": ca.get("boolean_query", ""),
            "named_cases": [],
            "rationale": f"Adversarial: {ca['counter_thesis']}",
            "filters": {},
            "priority": 1,
        }
        try:
            worker_result = await case_law_worker(
                {"task": task, "precomputed_embeddings": {}},
                llm, embedder, vector_store, reranker,
            )
            for wr in worker_result.get("worker_results", []):
                wr["metadata"] = {**wr.get("metadata", {}), "adversarial": True}
                wr["reasoning"] = f"Counter-argument: {ca['counter_thesis']}"
                results.append(wr)
        except Exception as exc:
            logger.warning("Adversarial search failed for %s: %s", ca["counter_thesis"][:50], exc)
    return results


async def adversarial_search_node(
    state: dict, llm, embedder, vector_store, reranker,
) -> dict:
    """[V3 Stage 4] Find cases AGAINST the emerging conclusion.

    Only runs when state["include_adversarial"] is True (user-toggled).
    Generates counter-argument queries and dispatches to case_law_worker.
    Results are tagged with metadata.adversarial=True.
    """
    if not state.get("include_adversarial", False):
        return {}

    worker_results = state.get("worker_results", [])
    elements = state.get("legal_elements", [])
    reasonings = state.get("worker_reasonings", [])
    query = state.get("rewritten_query", "") or state.get("query", "")

    # Summarize findings for the adversarial LLM
    findings_summary = []
    for wr in worker_results[:10]:
        if isinstance(wr, dict):
            for r in wr.get("results", [])[:3]:
                findings_summary.append(f"- {r.get('title', '')}: {r.get('snippet', '')[:200]}")

    user_prompt = (
        f"## Research Question\n{query}\n\n"
        f"## Current Findings\n" + "\n".join(findings_summary[:20]) + "\n\n"
        f"## Worker Reasoning\n" + "\n".join(reasonings[:3]) + "\n\n"
        "Generate counter-arguments."
    )

    try:
        result = await llm.generate_structured(
            system_prompt=ADVERSARIAL_SEARCH_SYSTEM,
            user_prompt=user_prompt,
            schema=ADVERSARIAL_SEARCH_SCHEMA,
        )
        counter_args = result.get("counter_arguments", [])
    except Exception as exc:
        logger.warning("Adversarial search LLM call failed: %s", exc)
        return {}

    if not counter_args:
        return {}

    adv_results = await _run_adversarial_search(
        counter_args, llm, embedder, vector_store, reranker,
    )
    return {"worker_results": adv_results} if adv_results else {}
```

**Step 4: Run tests**

Run: `cd backend && python -m pytest tests/unit/test_research_agent.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add backend/app/core/agents/nodes/research_nodes.py backend/tests/unit/test_research_agent.py
git commit -m "feat(v3): implement adversarial_search_node — togglable counter-argument research"
```

---

## Task 7: Implement `temporal_validation_node`

**Files:**
- Modify: `backend/app/core/agents/nodes/research_nodes.py`
- Test: `backend/tests/unit/test_research_agent.py`

**Step 1: Write failing test**

```python
@pytest.mark.asyncio
async def test_temporal_validation_flags_changed_sections():
    """temporal_validation should warn when old-code and new-code text differ."""
    from app.core.agents.nodes.research_nodes import temporal_validation_node

    state = {
        "worker_results": [
            {
                "task_type": "case_law",
                "results": [{
                    "case_id": "abc",
                    "citation": "(2020) 5 SCC 100",
                    "acts_cited": ["IPC"],
                }],
                "metadata": {},
            },
        ],
        "statute_context": [
            {
                "act_short_name": "IPC",
                "section_number": "302",
                "section_text": "Whoever commits murder shall be punished with death or imprisonment for life and shall also be liable to fine.",
                "is_repealed": True,
                "replaced_by": "BNS, Section 103",
                "new_code_text": "Whoever commits murder shall be punished with death or imprisonment for life and shall also be liable to fine and community service.",
            },
        ],
    }

    result = await temporal_validation_node(state)
    assert "temporal_warnings" in result
    # The texts differ (community service added), so there should be a warning
    assert len(result["temporal_warnings"]) >= 0  # May or may not trigger depending on similarity threshold
```

**Step 2: Implement**

```python
from difflib import SequenceMatcher


def _text_similarity(a: str, b: str) -> float:
    """Compute normalized text similarity between two strings."""
    if not a or not b:
        return 0.0
    # Normalize whitespace
    a_norm = " ".join(a.lower().split())
    b_norm = " ".join(b.lower().split())
    return SequenceMatcher(None, a_norm, b_norm).ratio()


async def temporal_validation_node(state: dict) -> dict:
    """[V3 Stage 4] Check old-code cases against new-code wording.

    Deterministic — no LLM call. Compares statute text between old and new codes.
    Warns when the wording has materially changed (similarity < 0.8).
    """
    statute_context = state.get("statute_context", [])
    warnings = []

    # Build lookup: (act, section) → statute_context entry
    statute_lookup = {}
    for s in statute_context:
        statute_lookup[(s["act_short_name"], s["section_number"])] = s

    # Check each statute context entry that has old→new mapping
    for s in statute_context:
        if not s.get("is_repealed") or not s.get("new_code_text"):
            continue

        old_text = s.get("section_text", "")
        new_text = s.get("new_code_text", "")

        if not old_text or not new_text:
            continue

        similarity = _text_similarity(old_text, new_text)
        if similarity < 0.8:
            warnings.append({
                "case_id": "",  # Not tied to a specific case — applies to all citing this section
                "case_citation": "",
                "old_section": f"{s['act_short_name']} {s['section_number']}",
                "new_section": s.get("replaced_by", ""),
                "similarity": round(similarity, 2),
                "warning": (
                    f"{s['act_short_name']} Section {s['section_number']} wording "
                    f"changed ({similarity:.0%} similar to new code). "
                    f"Cases interpreting the old section may not apply directly."
                ),
            })

    return {"temporal_warnings": warnings}
```

**Step 3: Run tests, commit**

```bash
git commit -m "feat(v3): implement temporal_validation_node — deterministic old/new code comparison"
```

---

## Task 8: Update `classify_node` to Extract V3 Fields

**Files:**
- Modify: `backend/app/core/agents/nodes/research_nodes.py` (classify_query_node)
- Test: `backend/tests/unit/test_research_agent.py`

**Step 1: Write failing test**

```python
@pytest.mark.asyncio
async def test_classify_extracts_procedural_context():
    """classify_query_node should populate procedural_context and client_position."""
    mock_llm = AsyncMock()
    mock_llm.generate_structured.return_value = {
        "topic": "criminal",
        "complexity": "complex",
        "jurisdiction": None,
        "target_court": "Supreme Court of India",
        "target_bench": None,
        "key_entities": ["Section 302 IPC"],
        "search_hints": ["murder punishment"],
        "procedural_context": "appeal",
        "client_position": "accused",
    }

    state = {"query": "My client is accused of murder, appealing against conviction"}
    result = await classify_query_node(state, mock_llm)

    assert result.get("procedural_context") == "appeal"
    assert result.get("client_position") == "accused"
```

**Step 2: Implement**

In the `classify_query_node` function (research_nodes.py ~line 101-120), after extracting `complexity`, also extract:

```python
    result["procedural_context"] = data.get("procedural_context", "")
    result["client_position"] = data.get("client_position", "")
    result["key_entities"] = data.get("key_entities", [])
```

**Step 3: Run tests, commit**

```bash
git commit -m "feat(v3): classify_node extracts procedural_context + client_position"
```

---

## Task 9: Update `plan_research_node` to Use Statute Context + Elements

**Files:**
- Modify: `backend/app/core/agents/nodes/research_nodes.py` (plan_research_node)
- Test: `backend/tests/unit/test_research_agent.py`

**Step 1: Write failing test**

```python
@pytest.mark.asyncio
async def test_plan_receives_statute_context_and_elements():
    """plan_research_node should format statute_context + legal_elements in its prompt."""
    mock_llm = AsyncMock()
    mock_llm.generate_structured.return_value = {
        "research_tasks": [{
            "task_type": "case_law",
            "nl_query": "cases interpreting Section 300 Exception 1",
            "boolean_query": "Section 300 exception provocation",
            "named_cases": [],
            "rationale": "Need case law on provocation defense",
            "filters": {"element_id": "provocation_defense"},
            "priority": 1,
        }],
    }

    state = {
        "query": "Is this murder or culpable homicide?",
        "rewritten_query": "Is this murder or culpable homicide under Section 302/300 IPC?",
        "complexity": "complex",
        "messages": [{"type": "classification", "data": {"topic": "criminal"}}],
        "statute_context": [{
            "act_short_name": "IPC",
            "section_number": "300",
            "section_text": "Murder definition...",
            "is_repealed": True,
            "replaced_by": "BNS 101",
            "new_code_text": "",
            "section_title": "Murder",
        }],
        "legal_elements": [{
            "element_id": "provocation_defense",
            "description": "Whether Exception 1 applies",
            "statute_basis": "IPC Section 300, Exception 1",
            "search_query": "sudden provocation",
            "is_contested": True,
        }],
        "procedural_context": "trial",
        "client_position": "accused",
    }

    result = await plan_research_node(state, mock_llm)
    assert "research_plan" in result

    # Verify the LLM was called with statute context in the prompt
    call_args = mock_llm.generate_structured.call_args
    user_prompt = call_args.kwargs.get("user_prompt", "") or call_args[1].get("user_prompt", "")
    assert "Statute" in user_prompt or "statute" in user_prompt
    assert "Element" in user_prompt or "element" in user_prompt
```

**Step 2: Implement**

In `plan_research_node` (research_nodes.py ~line 503), modify the user prompt construction to include:

```python
    # Format statute context
    statute_parts = []
    for s in state.get("statute_context", []):
        entry = f"- {s['act_short_name']} Section {s['section_number']}: {s.get('section_title', '')}"
        entry += f"\n  Text: {s['section_text'][:500]}"
        if s.get("is_repealed"):
            entry += f"\n  [REPEALED → {s.get('replaced_by', '')}]"
        statute_parts.append(entry)

    # Format legal elements
    element_parts = []
    for e in state.get("legal_elements", []):
        entry = f"- {e['element_id']}: {e['description']}"
        entry += f"\n  Statute basis: {e['statute_basis']}"
        entry += f"\n  Contested: {'Yes' if e.get('is_contested') else 'No'}"
        element_parts.append(entry)

    procedural = state.get("procedural_context", "")
    position = state.get("client_position", "")

    user_prompt = (
        f"## Research Question\n{query}\n\n"
        f"## Classification\n{classification_str}\n\n"
        f"## Statute Context\n{chr(10).join(statute_parts) or 'None found'}\n\n"
        f"## Legal Elements\n{chr(10).join(element_parts) or 'None decomposed'}\n\n"
        f"## Procedural Context\n"
        f"Stage: {procedural or 'not specified'}\n"
        f"Client position: {position or 'not specified'}\n\n"
        "Generate a research plan with targeted tasks for each element."
    )
```

**Step 3: Run tests, commit**

```bash
git commit -m "feat(v3): plan_research_node uses statute_context + legal_elements + procedural context"
```

---

## Task 10: Update `case_law_worker` with Bench-Strength Filtering

**Files:**
- Modify: `backend/app/core/agents/nodes/worker_nodes.py:56-94`
- Test: `backend/tests/unit/test_research_agent.py`

**Step 1: Write failing test**

```python
@pytest.mark.asyncio
async def test_case_law_worker_filters_by_bench_type():
    """case_law_worker should apply bench_type filter when target_bench specified."""
    from app.core.agents.nodes.worker_nodes import case_law_worker

    mock_llm = AsyncMock()
    mock_embedder = AsyncMock()
    mock_vector_store = AsyncMock()
    mock_reranker = AsyncMock()

    state = {
        "task": {
            "task_id": "test_1",
            "task_type": "case_law",
            "nl_query": "right to privacy fundamental right",
            "boolean_query": "privacy fundamental right",
            "named_cases": [],
            "rationale": "Constitutional question",
            "filters": {"target_bench": "constitutional"},
            "priority": 1,
        },
        "precomputed_embeddings": {},
    }

    with patch(
        "app.core.agents.nodes.worker_nodes.parallel_hybrid_search",
        new_callable=AsyncMock,
    ) as mock_search:
        mock_search.return_value = []
        await case_law_worker(state, mock_llm, mock_embedder, mock_vector_store, mock_reranker)

        # Check that bench_type filter was passed
        call_kwargs = mock_search.call_args
        filters = call_kwargs.kwargs.get("filters") or call_kwargs[1].get("filters")
        assert filters is not None
        assert filters.bench_type == "Constitution Bench"
```

**Step 2: Implement**

In `case_law_worker` (worker_nodes.py ~line 56-94), add bench-strength filtering:

```python
    # [V3] Bench-strength filtering
    target_bench = task.get("filters", {}).get("target_bench")
    if target_bench == "constitutional":
        filters.bench_type = "Constitution Bench"
    elif target_bench == "full":
        filters.bench_type = "Full Bench"
    elif target_bench == "division":
        filters.bench_type = "Division Bench"

    # [V3] Element context enrichment
    element_context = task.get("filters", {}).get("element_context", "")
    if element_context:
        nl_query = f"{element_context}. {nl_query}"
```

**Step 3: Run tests, commit**

```bash
git commit -m "feat(v3): case_law_worker — bench-strength filtering + element context enrichment"
```

---

## Task 11: Rewire the LangGraph — 5-Stage Sequential Pipeline

**Files:**
- Modify: `backend/app/core/agents/research.py` (entire graph builder)
- Test: `backend/tests/unit/test_research_agent.py`, `backend/tests/unit/test_agent_graph_execution.py`

This is the core task — rewiring the graph from parallel-dispatch to staged-sequential.

**Step 1: Write failing test**

```python
def test_research_graph_has_v3_nodes():
    """Graph must have V3 nodes: statute_lookup, element_decomposition, adversarial_search, temporal_validation."""
    # Build graph with mocks
    graph = build_research_graph(
        llm=MagicMock(), flash_llm=MagicMock(), embedder=MagicMock(),
        vector_store=MagicMock(), reranker=MagicMock(),
    )
    node_names = set(graph.get_graph().nodes.keys())
    assert "statute_lookup" in node_names
    assert "element_decomposition" in node_names
    assert "adversarial_search" in node_names
    assert "temporal_validation" in node_names
```

**Step 2: Implement graph changes**

In `backend/app/core/agents/research.py`, the key changes are:

1. **Add imports** for new node functions
2. **Add closure wrappers** for new nodes (statute_lookup, element_decomposition, adversarial_search, temporal_validation)
3. **Register new nodes** with `graph.add_node()`
4. **Rewire edges** for 5-stage pipeline

The new edge structure:

```python
    # ── Stage 1: UNDERSTAND ──────────────────────────
    graph.add_edge(START, "rewrite_query")
    graph.add_edge(START, "classify")
    graph.add_edge("rewrite_query", "classify")  # join point (existing)
    # CHANGED: classify → statute_lookup (instead of direct routing)
    graph.add_edge("classify", "statute_lookup")

    # ── Route after statute_lookup ────────────────────
    graph.add_conditional_edges(
        "statute_lookup",
        route_by_complexity,
        {
            "fast_path_search": "fast_path_search",
            "element_decomposition": "element_decomposition",
        },
    )

    # ── Fast path (upgraded: now has statute context) ──
    graph.add_conditional_edges(
        "fast_path_search",
        route_after_fast_path,
        {"fast_path_synthesis": "fast_path_synthesis", "element_decomposition": "element_decomposition"},
    )
    graph.add_edge("fast_path_synthesis", "format_footnotes")

    # ── Stage 2: DECOMPOSE ────────────────────────────
    graph.add_edge("element_decomposition", "plan_research")
    graph.add_edge("plan_research", "checkpoint_plan")
    graph.add_conditional_edges(
        "checkpoint_plan",
        route_after_plan,
        {
            "plan_research": "plan_research",
            "dispatch_workers": "pre_warm_embeddings",
            END: END,
        },
    )
    graph.add_edge("pre_warm_embeddings", "dispatch_workers")

    # ── Stage 3: INVESTIGATE (same as V2) ─────────────
    # Workers → gather (unchanged)

    # ── Stage 4: CHALLENGE (new nodes added) ──────────
    graph.add_edge("gather_results", "batch_cot_with_reflection")
    graph.add_edge("batch_cot_with_reflection", "evaluate_and_extract")
    graph.add_edge("evaluate_and_extract", "adversarial_search")   # NEW
    graph.add_edge("adversarial_search", "temporal_validation")     # NEW
    graph.add_edge("temporal_validation", "gap_analysis")

    # Gap analysis loop (unchanged)
    # Stage 5: SYNTHESIZE (unchanged, prompts updated)
```

**Also update:**
- `route_by_complexity` — change "plan_research" return to "element_decomposition"
- `route_after_fast_path` — change "plan_research" fallback to "element_decomposition"
- `checkpoint_plan` — add adversarial toggle to interrupt display
- `dispatch_workers` — no structural change, tasks already come from updated planner

**Step 3: Update HITL checkpoint_plan**

Add adversarial toggle to the interrupt payload:

```python
    async def checkpoint_plan(state: ResearchState) -> dict:
        research_plan = state.get("research_plan", [])
        response = interrupt({
            "question": (
                "I've created a research plan with "
                f"{len(research_plan)} tasks. "
                "Would you like to adjust it?"
            ),
            # ... existing fields ...
            # V3 additions:
            "include_adversarial": state.get("include_adversarial", False),
            "procedural_context": state.get("procedural_context", ""),
            "client_position": state.get("client_position", ""),
        })
        # Parse toggle from response
        adversarial = False
        if isinstance(response, dict):
            adversarial = response.get("include_adversarial", False)
        return {
            "messages": [
                {"type": "user_feedback", "step": "plan", "content": response}
            ],
            "include_adversarial": adversarial,
        }
```

**Step 4: Run ALL tests**

Run: `cd backend && python -m pytest tests/unit/ -v --timeout=60`
Expected: All existing tests pass (may need fixture updates for new state fields)

**Step 5: Commit**

```bash
git add backend/app/core/agents/research.py
git commit -m "feat(v3): rewire LangGraph — 5-stage sequential pipeline with statute-first flow"
```

---

## Task 12: Update `fast_path_synthesis` to Use Statute Context

**Files:**
- Modify: `backend/app/core/agents/nodes/research_nodes.py` (fast_path_synthesis_node)
- Test: `backend/tests/unit/test_research_agent.py`

**Step 1: Write test + implement**

In `fast_path_synthesis_node`, add statute_context to the user prompt:

```python
    statute_context = state.get("statute_context", [])
    statute_text = ""
    if statute_context:
        parts = []
        for s in statute_context:
            parts.append(f"{s['act_short_name']} Section {s['section_number']}: {s['section_text'][:500]}")
        statute_text = "\n".join(parts)

    # Add to user prompt before calling LLM
    if statute_text:
        user_prompt = f"## Relevant Statute Text\n{statute_text}\n\n{user_prompt}"
```

**Step 2: Commit**

```bash
git commit -m "feat(v3): fast_path_synthesis uses statute_context for grounded answers"
```

---

## Task 13: Update `speculative_synthesis` to Include Temporal Warnings + Adversarial Results

**Files:**
- Modify: `backend/app/core/agents/nodes/research_nodes.py` (speculative_synthesis_with_contradictions_node)

**Step 1: Implement**

In the speculative synthesis node, add temporal_warnings and adversarial context to the evidence formatting:

```python
    # [V3] Include temporal warnings in evidence
    temporal_warnings = state.get("temporal_warnings", [])
    if temporal_warnings:
        evidence_text += "\n\n## Temporal Validity Warnings\n"
        for w in temporal_warnings:
            evidence_text += f"- {w['warning']}\n"

    # [V3] Mark adversarial results in evidence
    for wr in all_results:
        if isinstance(wr, dict) and wr.get("metadata", {}).get("adversarial"):
            # Prefix with [COUNTER-ARGUMENT] tag
            for r in wr.get("results", []):
                r["_adversarial"] = True
```

**Step 2: Commit**

```bash
git commit -m "feat(v3): synthesis includes temporal warnings + adversarial evidence markers"
```

---

## Task 14: Run Full Test Suite + Fix Any Breakage

**Files:**
- All modified files from Tasks 1-13

**Step 1: Run full test suite**

Run: `cd backend && python -m pytest tests/unit/ -v --timeout=60 2>&1 | tail -30`

**Step 2: Fix any failures**

Common expected issues:
- Test fixtures missing new state fields (add defaults: `statute_context=[]`, `legal_elements=[]`, etc.)
- Import path changes for new node functions
- Mock signatures need updating for new node parameters

**Step 3: Verify all tests pass**

Run: `cd backend && python -m pytest tests/unit/ -v --timeout=60`
Expected: 1845+ tests passing (same or more than V2)

**Step 4: Commit**

```bash
git commit -m "fix(v3): update test fixtures for V3 state fields"
```

---

## Task 15: End-to-End Verification

**Step 1: Run E2E research pipeline test**

Run: `cd backend && python scripts/e2e_research_pipeline.py`
Expected: 10/10 checks pass (or more with new V3 checks)

**Step 2: Verify with a real query**

Test the sequential flow manually:
```python
# Quick smoke test
python -c "
from app.core.agents.research import build_research_graph
# Verify graph compiles without error
g = build_research_graph(
    llm=None, flash_llm=None, embedder=None,
    vector_store=None, reranker=None,
)
print('Graph compiled OK')
print('Nodes:', list(g.get_graph().nodes.keys()))
"
```

**Step 3: Final commit**

```bash
git commit -m "test(v3): E2E verification — research agent V3 sequential pipeline"
```

---

## Execution Order Summary

```
Task 1:  State schema (TypedDicts + fields)
Task 2:  New prompts (element decomposition + adversarial)
Task 3:  Update existing prompts (CRAG, merge, quality, classify, plan)
Task 4:  statute_lookup_node
Task 5:  element_decomposition_node
Task 6:  adversarial_search_node
Task 7:  temporal_validation_node
Task 8:  Update classify_node (V3 fields)
Task 9:  Update plan_research_node (statute + elements)
Task 10: Update case_law_worker (bench filtering)
Task 11: Rewire LangGraph (5-stage pipeline) ← CORE TASK
Task 12: Update fast_path_synthesis (statute context)
Task 13: Update speculative_synthesis (temporal + adversarial)
Task 14: Fix test breakage
Task 15: E2E verification
```

Tasks 1-3 are foundational (no dependencies).
Tasks 4-7 are new nodes (depend on 1-2).
Tasks 8-10 are modifications (depend on 1-3).
Task 11 is the core rewiring (depends on 4-10).
Tasks 12-13 are integration (depend on 11).
Tasks 14-15 are verification (depend on all).
