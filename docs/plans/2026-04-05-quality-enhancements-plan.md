# Quality Enhancements Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix 5 confirmed search/ingestion quality gaps: legal signal boosting in RRF, summary vector routing for broad queries, ratio cross-contamination detection, era-adaptive extraction, and headnote→proposition pipeline.

**Architecture:** Each enhancement is independent and can be implemented/tested in isolation. Changes touch search (hybrid.py), ingestion quality gates, metadata extraction, and the ingestion pipeline. No schema migrations needed.

**Tech Stack:** Python 3.12, FastAPI, Pinecone, PostgreSQL, Gemini LLM, pytest

---

## Task 1: Legal Signal Boost in RRF (Enhancement A)

**Context:** `legal_signal` (density of "held that", "we hold" etc. per 1000 chars) is computed in `chunker.py:56-62` and stored in Pinecone metadata (`pipeline.py:1173`), but completely ignored during search. The RRF merge (`hybrid.py:81-120`) only uses rank position, discarding original scores.

**Approach:** Apply a post-RRF signal boost rather than modifying RRF itself. After RRF merge produces `(doc_id, rrf_score)` pairs, boost scores for chunks that had high legal_signal. This requires carrying `legal_signal` through from Pinecone results.

**Files:**
- Modify: `backend/app/core/search/hybrid.py:439-501` (_vector_search — carry legal_signal through)
- Modify: `backend/app/core/search/hybrid.py:270-289` (post-RRF boost)
- Test: `backend/tests/unit/test_rrf.py`
- Test: `backend/tests/unit/test_hybrid_search.py`

### Step 1: Write failing test for signal boost function

```python
# In backend/tests/unit/test_rrf.py — add new test class

class TestLegalSignalBoost:
    def test_boost_increases_high_signal_scores(self):
        """High legal_signal chunks get boosted RRF score."""
        from app.core.search.hybrid import apply_legal_signal_boost

        merged = [("doc_a", 0.5), ("doc_b", 0.5)]
        signal_map = {"doc_a": 80.0, "doc_b": 5.0}  # doc_a has high signal
        boosted = apply_legal_signal_boost(merged, signal_map)
        # doc_a should now rank higher
        assert boosted[0][0] == "doc_a"
        assert boosted[0][1] > 0.5

    def test_boost_no_signal_unchanged(self):
        """Chunks without signal data keep original score."""
        from app.core.search.hybrid import apply_legal_signal_boost

        merged = [("doc_a", 0.5), ("doc_b", 0.3)]
        signal_map = {}
        boosted = apply_legal_signal_boost(merged, signal_map)
        assert boosted == merged

    def test_boost_preserves_order_when_equal_signal(self):
        from app.core.search.hybrid import apply_legal_signal_boost

        merged = [("doc_a", 0.5), ("doc_b", 0.3)]
        signal_map = {"doc_a": 10.0, "doc_b": 10.0}
        boosted = apply_legal_signal_boost(merged, signal_map)
        assert boosted[0][0] == "doc_a"  # original order preserved
```

Run: `cd backend && python -m pytest tests/unit/test_rrf.py::TestLegalSignalBoost -v`
Expected: FAIL — `apply_legal_signal_boost` not found

### Step 2: Implement signal boost function

Add to `backend/app/core/search/hybrid.py` after the `rrf_merge` function (after line 121):

```python
def apply_legal_signal_boost(
    merged: list[tuple[str, float]],
    signal_map: dict[str, float],
    *,
    boost_factor: float = 1.0,
    signal_denominator: float = 500.0,
) -> list[tuple[str, float]]:
    """Boost RRF scores for chunks with high legal_signal density.

    Formula: boosted_score = rrf_score * (1 + boost_factor * legal_signal / signal_denominator)

    A chunk with legal_signal=100 (very dense legal language) gets a 20% boost.
    A chunk with legal_signal=10 gets a 2% boost. Zero signal = no change.
    """
    if not signal_map:
        return merged
    boosted = [
        (doc_id, score * (1.0 + boost_factor * signal_map.get(doc_id, 0.0) / signal_denominator))
        for doc_id, score in merged
    ]
    boosted.sort(key=lambda x: x[1], reverse=True)
    return boosted
```

Run: `cd backend && python -m pytest tests/unit/test_rrf.py::TestLegalSignalBoost -v`
Expected: PASS

### Step 3: Carry legal_signal through _vector_search

Modify `_vector_search` (line 439-501) to return legal_signal alongside results.

Currently returns `list[tuple[str, float, str, int, int]]` (case_id, score, text, char_start, char_end).

Change the `seen` dict to also track legal_signal:

```python
# Line 488: Change from
seen: dict[str, tuple[float, str, int, int]] = {}
# To:
seen: dict[str, tuple[float, str, int, int, float]] = {}

# Line 491-495: Change from
chunk_text = r.metadata.get("text", "") or r.metadata.get("chunk_text", "")
char_start = int(r.metadata.get("char_start", 0) or 0)
char_end = int(r.metadata.get("char_end", 0) or 0)
if case_id not in seen or r.score > seen[case_id][0]:
    seen[case_id] = (r.score, chunk_text, char_start, char_end)
# To:
chunk_text = r.metadata.get("text", "") or r.metadata.get("chunk_text", "")
char_start = int(r.metadata.get("char_start", 0) or 0)
char_end = int(r.metadata.get("char_end", 0) or 0)
legal_signal = float(r.metadata.get("legal_signal", 0) or 0)
if case_id not in seen or r.score > seen[case_id][0]:
    seen[case_id] = (r.score, chunk_text, char_start, char_end, legal_signal)

# Line 497-501: Change return to include signal
return sorted(
    [(cid, score, text, cs, ce, sig) for cid, (score, text, cs, ce, sig) in seen.items()],
    key=lambda x: x[1],
    reverse=True,
)
```

### Step 4: Apply boost in hybrid_search after RRF merge

In `hybrid_search` (around line 270-289), after `merged = rrf_merge(...)`:

```python
# Line 271: Update tuple unpacking for new return shape
vector_ranked = [(r[0], r[1]) for r in vector_results]
# Add signal map extraction:
signal_map = {r[0]: r[5] for r in vector_results if r[5] > 0}

# After line 289 (after merged = rrf_merge(...)):
merged = apply_legal_signal_boost(merged, signal_map)
```

**Important:** Also update any callers that unpack `_vector_search` results to handle the new 6th element. Check line 304 `_build_snippets_map` — it receives vector_results and may need updating.

### Step 5: Update _build_snippets_map and tests

Check `_build_snippets_map` to ensure it handles the new tuple length. Update existing hybrid search tests to include `legal_signal` in mock Pinecone metadata.

Run: `cd backend && python -m pytest tests/unit/test_rrf.py tests/unit/test_hybrid_search.py -v`
Expected: ALL PASS

### Step 6: Commit

```bash
git add backend/app/core/search/hybrid.py backend/tests/unit/test_rrf.py backend/tests/unit/test_hybrid_search.py
git commit -m "feat(search): boost high legal_signal chunks in RRF merge"
```

---

## Task 2: Summary Vector Routing for Broad Queries (Enhancement B)

**Context:** Summary vectors (`vector_type: "summary"`) exist per section type per case (created by `section_summarizer.py:91-135`), but no search path targets them. Agent workers explicitly filter for `["proposition", "ratio", "headnote"]` (`worker_nodes.py:177`), excluding summaries. For broad queries ("what is the law on bail in NDPS cases"), summary vectors would give case-level overview before drilling into chunks.

**Approach:** Add `"summary"` to the agent worker's vector_type filter. Summaries are section-level condensations — they naturally complement proposition/ratio/headnote vectors. No routing logic needed; just include them in the existing filter.

**Files:**
- Modify: `backend/app/core/agents/nodes/worker_nodes.py:177`
- Test: `backend/tests/unit/test_worker_nodes.py` (if exists, verify filter)

### Step 1: Write failing test

```python
# In test file for worker nodes — verify prop_filter includes summary
class TestWorkerVectorTypes:
    def test_case_law_worker_includes_summary_vectors(self):
        """case_law_worker should search summary vectors alongside proposition/ratio/headnote."""
        # This test verifies the filter constant. Implementation tested via integration.
        from app.core.agents.nodes.worker_nodes import _AGENT_VECTOR_TYPES
        assert "summary" in _AGENT_VECTOR_TYPES
        assert "proposition" in _AGENT_VECTOR_TYPES
        assert "ratio" in _AGENT_VECTOR_TYPES
        assert "headnote" in _AGENT_VECTOR_TYPES
```

Run: `cd backend && python -m pytest tests/unit/test_worker_nodes.py::TestWorkerVectorTypes -v`
Expected: FAIL — `_AGENT_VECTOR_TYPES` not defined

### Step 2: Extract constant and add summary

In `backend/app/core/agents/nodes/worker_nodes.py`, add at module level (near top, after imports):

```python
_AGENT_VECTOR_TYPES: list[str] = ["proposition", "ratio", "headnote", "summary"]
```

Then at line 177, change:
```python
# From:
prop_filter: dict = {"vector_type": {"$in": ["proposition", "ratio", "headnote"]}}
# To:
prop_filter: dict = {"vector_type": {"$in": _AGENT_VECTOR_TYPES}}
```

Run: `cd backend && python -m pytest tests/unit/test_worker_nodes.py::TestWorkerVectorTypes -v`
Expected: PASS

### Step 3: Commit

```bash
git add backend/app/core/agents/nodes/worker_nodes.py backend/tests/unit/test_worker_nodes.py
git commit -m "feat(agents): include summary vectors in agent search filter"
```

---

## Task 3: Ratio Cross-Contamination Detection (Enhancement D)

**Context:** `quality_gates.py:89-105` checks title uniqueness (85%) and citation uniqueness (80%), but not `ratio_decidendi`. If batch LLM extraction produces identical ratio text across different cases, that's a strong contamination signal.

**Approach:** Add ratio uniqueness check after the citation check, following the identical pattern. Use 80% threshold (same as citations).

**Files:**
- Modify: `ingestion/quality_gates.py:105` (insert after citation check)
- Test: `ingestion/` or `backend/tests/unit/test_quality_gates.py` (check where tests live)

### Step 1: Write failing test

```python
# In the quality gates test file
class TestRatioUniqueness:
    def test_detects_duplicate_ratios(self):
        """Flag when too many cases share identical ratio_decidendi."""
        from quality_gates import validate_batch_metadata

        # 20 cases with only 3 unique ratios = 15% unique = should FAIL
        metadata = {}
        for i in range(20):
            metadata[f"case_{i}"] = {
                "title": f"Case Title {i}",
                "citation": f"2025 INSC {i}",
                "year": 2025,
                "ratio_decidendi": f"Ratio text {i % 3}",  # Only 3 unique
            }
        result = validate_batch_metadata(metadata)
        assert not result["passed"]
        assert any("ratio" in f.lower() for f in result["failures"])

    def test_accepts_unique_ratios(self):
        """Pass when ratios are sufficiently unique."""
        from quality_gates import validate_batch_metadata

        metadata = {}
        for i in range(20):
            metadata[f"case_{i}"] = {
                "title": f"Case Title {i}",
                "citation": f"2025 INSC {i}",
                "year": 2025,
                "ratio_decidendi": f"Unique ratio for case {i}",
            }
        result = validate_batch_metadata(metadata)
        # Should not fail on ratio uniqueness
        assert not any("ratio" in f.lower() for f in result.get("failures", []))
```

Run: `cd ingestion && python -m pytest test_quality_gates.py::TestRatioUniqueness -v`  
(or wherever tests live — check first)
Expected: FAIL

### Step 2: Add ratio uniqueness check

In `ingestion/quality_gates.py`, after line 105 (after citation uniqueness block), add:

```python
    ratios = [m.get("ratio_decidendi", "") for m in metadata_results.values() if m.get("ratio_decidendi")]
    unique_ratios = len(set(ratios))
    checks["unique_ratios"] = f"{unique_ratios}/{len(ratios)}"
    if len(ratios) > 10 and unique_ratios < len(ratios) * 0.80:
        failures.append(
            f"Only {unique_ratios}/{len(ratios)} unique ratio_decidendi -- "
            f"possible cross-contamination!"
        )
```

Run tests again.
Expected: PASS

### Step 3: Commit

```bash
git add ingestion/quality_gates.py
git commit -m "feat(quality): add ratio_decidendi uniqueness check to cross-contamination gate"
```

---

## Task 4: Era-Adaptive Metadata Extraction (Enhancement E)

**Context:** `extract_metadata_llm()` in `metadata.py:664-736` uses a single system prompt (`METADATA_EXTRACTION_SYSTEM` in `prompts.py:9-188`) for all cases 1950-2025. Pre-1970 cases have different formatting: shorter judgments, fewer structured sections, different citation formats (AIR vs SCC/SCALE), less precise judge lists. The LLM confidence is lower on older cases.

**Approach:** Add an era-specific preamble to the system prompt rather than maintaining separate full prompts. The extraction function already receives the case text — derive approximate year from text (or pass it in), then prepend era-specific guidance. Three eras: pre-1970 (early SC), 1970-2000 (modern), 2000+ (digital).

**Files:**
- Modify: `backend/app/core/ingestion/metadata.py:664-736` (extract_metadata_llm)
- Modify: `backend/app/core/legal/prompts.py` (add era preambles)
- Test: `backend/tests/unit/test_metadata.py`

### Step 1: Write failing test

```python
class TestEraAdaptiveExtraction:
    def test_pre_1970_preamble_applied(self):
        """Pre-1970 cases get era-specific extraction guidance."""
        from app.core.legal.prompts import get_era_preamble

        preamble = get_era_preamble(1955)
        assert "AIR" in preamble  # AIR citations common in this era
        assert preamble  # non-empty

    def test_modern_preamble_applied(self):
        from app.core.legal.prompts import get_era_preamble

        preamble = get_era_preamble(1985)
        assert "SCC" in preamble or preamble  # SCC citations

    def test_digital_era_preamble(self):
        from app.core.legal.prompts import get_era_preamble

        preamble = get_era_preamble(2020)
        assert "neutral citation" in preamble.lower() or "INSC" in preamble

    def test_no_year_returns_empty(self):
        from app.core.legal.prompts import get_era_preamble

        preamble = get_era_preamble(None)
        assert preamble == ""
```

Run: `cd backend && python -m pytest tests/unit/test_metadata.py::TestEraAdaptiveExtraction -v`
Expected: FAIL

### Step 2: Add era preambles to prompts.py

In `backend/app/core/legal/prompts.py`, add after the imports:

```python
def get_era_preamble(year: int | None) -> str:
    """Return era-specific extraction guidance based on judgment year."""
    if year is None:
        return ""
    if year < 1970:
        return (
            "\n## ERA NOTE: Pre-1970 Supreme Court Judgment\n"
            "- Citations are typically AIR format (e.g., AIR 1954 SC 300), not SCC or SCALE.\n"
            "- Judgments are shorter with less structured sections.\n"
            "- Judge names may use older spellings or honorifics.\n"
            "- Legal propositions may be stated less explicitly — infer from reasoning.\n"
            "- case_type is often 'Civil Appeal' or 'Writ Petition'.\n"
        )
    if year < 2000:
        return (
            "\n## ERA NOTE: 1970-1999 Supreme Court Judgment\n"
            "- Citations may use SCC, AIR, or SCR formats.\n"
            "- Structured sections (FACTS, ANALYSIS) emerge but aren't always labeled.\n"
            "- Look for ratio in 'We hold that...' or 'In our opinion...' paragraphs.\n"
        )
    return (
        "\n## ERA NOTE: 2000+ Supreme Court Judgment\n"
        "- Neutral citations (YYYY:INSC:NNNN) may be present alongside SCC/SCALE.\n"
        "- Structured formatting with numbered paragraphs is common.\n"
        "- Look for explicit headnotes at the start of SCC-reported judgments.\n"
    )
```

### Step 3: Wire era preamble into extract_metadata_llm

In `backend/app/core/ingestion/metadata.py`, in `extract_metadata_llm()`:

1. The function receives case text. Extract approximate year from text (regex for common patterns) or accept it as a parameter.
2. Prepend `get_era_preamble(year)` to the system prompt.

```python
# In extract_metadata_llm(), before the LLM call:
# Try to detect year from filename or text for era-adaptive prompts
from app.core.legal.prompts import get_era_preamble
era_preamble = get_era_preamble(hint_year)  # hint_year passed from caller or extracted
system_prompt = METADATA_EXTRACTION_SYSTEM + era_preamble
```

The caller (`pipeline.py` or `batch_ingest_vertex.py`) typically has the year from the Parquet metadata or filename. Add `hint_year: int | None = None` parameter to `extract_metadata_llm()`.

### Step 4: Run tests

Run: `cd backend && python -m pytest tests/unit/test_metadata.py -v`
Expected: PASS

### Step 5: Commit

```bash
git add backend/app/core/legal/prompts.py backend/app/core/ingestion/metadata.py backend/tests/unit/test_metadata.py
git commit -m "feat(ingestion): era-adaptive extraction prompts for pre-1970/modern/digital eras"
```

---

## Task 5: Headnote → Proposition Pipeline (Enhancement F)

**Context:** `cross_validate_propositions()` in `metadata.py:1152-1176` creates propositions from `ratio_decidendi` when `legal_propositions` is empty, but never from headnotes. Many cases (especially pre-V3 ingested ones) have reporter headnotes but no propositions. Headnotes contain concise legal holdings that are ideal proposition sources.

**Approach:** Extend `cross_validate_propositions()` to generate propositions from headnotes when both `legal_propositions` and `ratio_decidendi` are empty. Headnotes already contain structured text — each headnote becomes a proposition with `is_novel: False`.

**Files:**
- Modify: `backend/app/core/ingestion/metadata.py:1152-1176`
- Test: `backend/tests/unit/test_metadata.py`

### Step 1: Write failing test

```python
class TestHeadnoteToProposition:
    def test_generates_propositions_from_headnotes_when_both_empty(self):
        """When ratio and propositions are empty, derive propositions from headnotes."""
        from app.core.ingestion.metadata import cross_validate_propositions, CaseMetadata

        meta = CaseMetadata()
        meta.ratio_decidendi = ""
        meta.legal_propositions = []
        meta.headnotes = '[{"text": "Right to life includes right to livelihood"}, {"text": "Article 21 has wide amplitude"}]'

        result = cross_validate_propositions(meta)
        assert len(result.legal_propositions) == 2
        assert result.legal_propositions[0]["proposition_text"] == "Right to life includes right to livelihood"
        assert result.legal_propositions[0]["is_novel"] is False

    def test_skips_when_propositions_already_exist(self):
        """Don't generate from headnotes if propositions already populated."""
        from app.core.ingestion.metadata import cross_validate_propositions, CaseMetadata

        meta = CaseMetadata()
        meta.ratio_decidendi = ""
        meta.legal_propositions = [{"proposition_text": "Existing", "is_novel": True, "paragraph_number": None, "related_section": None}]
        meta.headnotes = '[{"text": "Headnote text"}]'

        result = cross_validate_propositions(meta)
        assert len(result.legal_propositions) == 1
        assert result.legal_propositions[0]["proposition_text"] == "Existing"

    def test_skips_when_headnotes_empty(self):
        """No crash when headnotes are empty/null."""
        from app.core.ingestion.metadata import cross_validate_propositions, CaseMetadata

        meta = CaseMetadata()
        meta.ratio_decidendi = ""
        meta.legal_propositions = []
        meta.headnotes = ""

        result = cross_validate_propositions(meta)
        assert result.legal_propositions == []
```

Run: `cd backend && python -m pytest tests/unit/test_metadata.py::TestHeadnoteToProposition -v`
Expected: FAIL

### Step 2: Extend cross_validate_propositions

In `backend/app/core/ingestion/metadata.py`, modify `cross_validate_propositions()` (lines 1152-1176):

Add after the existing `if ratio.strip() and not props:` block (after line 1174), before `return metadata`:

```python
    # If still no propositions, try to derive from headnotes
    if not metadata.legal_propositions:
        headnotes_raw = metadata.headnotes or ""
        if headnotes_raw.strip():
            try:
                import json
                headnotes = json.loads(headnotes_raw) if isinstance(headnotes_raw, str) else headnotes_raw
                if isinstance(headnotes, list):
                    metadata.legal_propositions = [
                        {
                            "proposition_text": (h.get("text", "") or h.get("proposition", "")).strip(),
                            "paragraph_number": None,
                            "is_novel": False,
                            "related_section": None,
                        }
                        for h in headnotes
                        if (h.get("text", "") or h.get("proposition", "")).strip()
                    ]
            except (json.JSONDecodeError, TypeError, AttributeError):
                pass  # Malformed headnotes — skip silently
```

Run: `cd backend && python -m pytest tests/unit/test_metadata.py::TestHeadnoteToProposition -v`
Expected: PASS

### Step 3: Commit

```bash
git add backend/app/core/ingestion/metadata.py backend/tests/unit/test_metadata.py
git commit -m "feat(ingestion): derive propositions from headnotes when ratio and props are empty"
```

---

## Final Verification

After all 5 tasks:

```bash
cd backend && python -m pytest tests/unit/test_rrf.py tests/unit/test_hybrid_search.py tests/unit/test_metadata.py tests/unit/test_common_nodes.py tests/unit/test_worker_nodes.py -v
```

Then run the full test suite:

```bash
cd backend && python -m pytest tests/ --timeout=120 -x -q
```

Expected: All tests pass, no regressions.
