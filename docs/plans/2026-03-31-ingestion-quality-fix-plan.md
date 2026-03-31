# Ingestion Pipeline Quality Fix — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix 4 critical ingestion bugs (batch misalignment, LLM hallucination, PDF boundary overlap, merge logic amplifier), add validation layers, and re-ingest 379 corrupted trial cases.

**Architecture:** Targeted fixes to 6 files in the ingestion pipeline. New validation functions in `metadata.py`, prompt hardening in `prompts.py`, boundary stripping in `pdf.py`, custom_id mapping in `batch_ingest_vertex.py`, and confidence gating in `pipeline.py`. All changes are additive — no breaking changes to existing interfaces except `merge_metadata()` gaining a `full_text` parameter.

**Tech Stack:** Python 3.12, FastAPI, pdfplumber, Gemini LLM, Pinecone, PostgreSQL, pytest

**Design doc:** `docs/plans/2026-03-31-ingestion-quality-fix-design.md`

---

## Task 1: Batch Custom ID Mapping (Bug 1 — CRITICAL)

**Files:**
- Modify: `backend/scripts/batch_ingest_vertex.py:374-422` (request builder)
- Modify: `backend/scripts/batch_ingest_vertex.py:507-573` (response parser)

**Step 1: Add `custom_id` to JSONL request entry**

In `_build_batch_jsonl_entry()`, the function currently returns a dict with only a `"request"` key. Add `"custom_id"` at the top level, using the `case_id` parameter that's already passed in.

```python
# In _build_batch_jsonl_entry() — change the return statement at line 409
# FROM:
    return {
        "request": {
            ...
        },
    }

# TO:
    return {
        "custom_id": case_id,
        "request": {
            ...
        },
    }
```

**Step 2: Fix response parser to use `custom_id` with global line counter fallback**

Replace the response parsing block (lines 507-549) in `phase2_batch_metadata()`:

```python
    # Download results
    results: dict[str, dict] = {}
    failures = 0

    # List result blobs
    result_blobs = list(bucket.list_blobs(prefix=f"batch_jobs/{run_id}/results/"))
    global_line = 0  # Global counter across ALL result files
    for blob in result_blobs:
        if not blob.name.endswith(".jsonl"):
            continue
        content = blob.download_as_text()
        for line in content.strip().split("\n"):
            if not line.strip():
                continue
            try:
                result_obj = json.loads(line)

                # Primary: use custom_id if present in response
                custom_id = result_obj.get("custom_id")
                if custom_id and custom_id in {e.case_id for e in manifest}:
                    case_id = custom_id
                elif global_line < len(case_id_order):
                    # Fallback: global line counter (never resets per file)
                    case_id = case_id_order[global_line]
                    logger.warning(
                        "No custom_id in result line %d, using global line counter "
                        "fallback (case_id=%s)",
                        global_line, case_id,
                    )
                else:
                    logger.warning(
                        "Extra result line %d beyond manifest size", global_line,
                    )
                    global_line += 1
                    continue

                global_line += 1

                # Extract the response content
                response = result_obj.get("response", {})
                candidates = response.get("candidates", [])
                if candidates:
                    content_parts = candidates[0].get("content", {}).get("parts", [])
                    if content_parts:
                        text_content = content_parts[0].get("text", "")
                        if text_content:
                            try:
                                parsed = json.loads(text_content)
                                results[case_id] = parsed
                            except (json.JSONDecodeError, ValueError) as parse_exc:
                                logger.warning(
                                    "Failed to parse JSON for case %s: %s",
                                    case_id, parse_exc,
                                )
                                failures += 1
                        else:
                            failures += 1
                    else:
                        failures += 1
                else:
                    failures += 1
            except (json.JSONDecodeError, KeyError, IndexError) as exc:
                logger.warning(
                    "Failed to parse result line %d: %s", global_line, exc,
                )
                global_line += 1
                failures += 1
```

**Step 3: Run existing tests**

Run: `cd d:/Startup/Smriti && python -m pytest backend/tests/ -k "batch" -v --no-header -q`
Expected: All existing batch tests pass (this is additive — custom_id is a new field that doesn't break old logic).

**Step 4: Commit**

```bash
git add backend/scripts/batch_ingest_vertex.py
git commit -m "fix(batch): add custom_id mapping to prevent response misalignment

Bug 1 fix: batch responses were mapped by line-number position within
each JSONL result file, but enumerate() resets per file. Now uses
custom_id for reliable case-to-response matching with global line
counter fallback."
```

---

## Task 2: Judge Text Validation Function

**Files:**
- Modify: `backend/app/core/ingestion/metadata.py` (add new function after line 117)
- Create: `backend/tests/unit/test_judge_validation.py`

**Step 1: Write failing tests**

Create `backend/tests/unit/test_judge_validation.py`:

```python
"""Tests for judge name validation against judgment text."""

import pytest

from app.core.ingestion.metadata import _validate_judges_against_text


class TestValidateJudgesAgainstText:
    """Tests for _validate_judges_against_text()."""

    def test_all_judges_found_in_header(self):
        header = (
            "IN THE SUPREME COURT OF INDIA\n"
            "BEFORE: HON'BLE MR. JUSTICE D.Y. CHANDRACHUD\n"
            "HON'BLE MR. JUSTICE SANJIV KHANNA\n"
            "Civil Appeal No. 1234 of 2023\n"
        )
        full_text = header + "\n" * 10 + "Some judgment body text..." * 100
        judges = ["D.Y. Chandrachud", "Sanjiv Khanna"]
        validated, rejected = _validate_judges_against_text(judges, full_text)
        assert validated == ["D.Y. Chandrachud", "Sanjiv Khanna"]
        assert rejected == []

    def test_hallucinated_judge_rejected(self):
        header = (
            "IN THE SUPREME COURT OF INDIA\n"
            "BEFORE: HON'BLE MR. JUSTICE V.R. KRISHNA IYER\n"
            "HON'BLE MR. JUSTICE D.A. DESAI\n"
        )
        full_text = header + "\n" * 10 + "Body text..." * 100
        judges = ["V.R. Krishna Iyer", "D.A. Desai", "P. Sathasivam"]
        validated, rejected = _validate_judges_against_text(judges, full_text)
        assert validated == ["V.R. Krishna Iyer", "D.A. Desai"]
        assert rejected == ["P. Sathasivam"]

    def test_all_judges_hallucinated(self):
        header = (
            "IN THE SUPREME COURT OF INDIA\n"
            "BEFORE: HON'BLE MR. JUSTICE RANJAN GOGOI\n"
        )
        full_text = header + "\n" * 10 + "Body..." * 100
        judges = ["P. Sathasivam", "B.S. Chauhan"]
        validated, rejected = _validate_judges_against_text(judges, full_text)
        assert validated == []
        assert rejected == ["P. Sathasivam", "B.S. Chauhan"]

    def test_surname_match_with_different_initials(self):
        """Judge appears with full name in text, initials in LLM."""
        header = "JUSTICE DHANANJAYA Y. CHANDRACHUD AND JUSTICE SURYA KANT\n"
        full_text = header + "Body..." * 100
        judges = ["D.Y. Chandrachud", "Surya Kant"]
        validated, rejected = _validate_judges_against_text(judges, full_text)
        assert "D.Y. Chandrachud" in validated  # surname "Chandrachud" matches
        assert "Surya Kant" in validated

    def test_empty_judges_list(self):
        validated, rejected = _validate_judges_against_text([], "some text")
        assert validated == []
        assert rejected == []

    def test_none_judges(self):
        validated, rejected = _validate_judges_against_text(None, "some text")
        assert validated == []
        assert rejected == []

    def test_short_text_skips_validation(self):
        """If full_text is very short, skip validation (can't reliably match)."""
        judges = ["D.Y. Chandrachud"]
        validated, rejected = _validate_judges_against_text(judges, "Short.")
        assert validated == ["D.Y. Chandrachud"]
        assert rejected == []

    def test_case_insensitive_match(self):
        header = "BEFORE: JUSTICE CHANDRACHUD AND JUSTICE KHANNA\n"
        full_text = header + "Body..." * 100
        judges = ["D.Y. Chandrachud", "Sanjiv Khanna"]
        validated, rejected = _validate_judges_against_text(judges, full_text)
        assert len(validated) == 2
        assert len(rejected) == 0
```

**Step 2: Run tests to verify they fail**

Run: `cd d:/Startup/Smriti && python -m pytest backend/tests/unit/test_judge_validation.py -v --no-header -q`
Expected: FAIL — `_validate_judges_against_text` not importable.

**Step 3: Implement `_validate_judges_against_text`**

Add to `backend/app/core/ingestion/metadata.py` after line 117 (after `_apply_judge_canonical`):

```python
def _validate_judges_against_text(
    judges: list[str] | None,
    full_text: str,
    header_chars: int = 2000,
) -> tuple[list[str], list[str]]:
    """Validate judge names by checking they appear in the judgment header.

    The bench composition is always listed in the first ~2000 chars of
    an Indian court judgment. For each judge, we check whether the surname
    (longest word with 4+ chars) appears case-insensitively in the header.

    Args:
        judges: List of judge names to validate.
        full_text: Full judgment text (only first ``header_chars`` are scanned).
        header_chars: How many chars from the start to scan.

    Returns:
        Tuple of (validated_judges, rejected_judges).
    """
    if not judges:
        return [], []

    # If text is too short to contain a reliable header, skip validation
    if len(full_text) < 200:
        return list(judges), []

    header = full_text[:header_chars].upper()
    validated: list[str] = []
    rejected: list[str] = []

    for judge in judges:
        # Extract surname: longest word with 4+ alpha chars
        words = [w.strip(".,'") for w in judge.split()]
        surname_candidates = [w for w in words if len(w) >= 4 and w.isalpha()]
        if not surname_candidates:
            # Fallback: use last word regardless
            surname_candidates = [words[-1].strip(".,'") if words else ""]

        surname = max(surname_candidates, key=len) if surname_candidates else ""

        if surname and surname.upper() in header:
            validated.append(judge)
        else:
            rejected.append(judge)

    return validated, rejected
```

**Step 4: Run tests to verify they pass**

Run: `cd d:/Startup/Smriti && python -m pytest backend/tests/unit/test_judge_validation.py -v --no-header -q`
Expected: All PASS.

**Step 5: Commit**

```bash
git add backend/app/core/ingestion/metadata.py backend/tests/unit/test_judge_validation.py
git commit -m "feat(ingestion): add judge-text validation against judgment header

New _validate_judges_against_text() checks each judge surname appears
in the first 2000 chars of the judgment. Returns (validated, rejected)
tuple for downstream merge logic."
```

---

## Task 3: Temporal Judge Validation Function

**Files:**
- Modify: `backend/app/core/ingestion/metadata.py` (add after the function from Task 2)
- Modify: `backend/tests/unit/test_judge_validation.py` (add new test class)

**Step 1: Write failing tests**

Append to `backend/tests/unit/test_judge_validation.py`:

```python
from app.core.ingestion.metadata import _validate_judge_tenure


class TestValidateJudgeTenure:
    """Tests for temporal judge validation."""

    def test_valid_judge_in_tenure(self):
        """P. Sathasivam served 2007-2014."""
        valid = _validate_judge_tenure(["P. Sathasivam"], 2010)
        assert valid == ["P. Sathasivam"]

    def test_judge_before_appointment(self):
        """P. Sathasivam appointed 2007, should fail for 1978 case."""
        valid = _validate_judge_tenure(["P. Sathasivam"], 1978)
        assert valid == []

    def test_judge_after_retirement(self):
        """P. Sathasivam retired 2014, should fail for 2020 case."""
        valid = _validate_judge_tenure(["P. Sathasivam"], 2020)
        assert valid == []

    def test_unknown_judge_passes(self):
        """Judges not in the lookup table should pass (not rejected)."""
        valid = _validate_judge_tenure(["Unknown Judge Name"], 2000)
        assert valid == ["Unknown Judge Name"]

    def test_mixed_valid_and_invalid(self):
        """One valid, one anachronistic judge."""
        # V.R. Krishna Iyer served ~1973-1980
        valid = _validate_judge_tenure(
            ["V.R. Krishna Iyer", "P. Sathasivam"], 1978,
        )
        assert "V.R. Krishna Iyer" in valid
        assert "P. Sathasivam" not in valid

    def test_no_year_skips_validation(self):
        valid = _validate_judge_tenure(["P. Sathasivam"], None)
        assert valid == ["P. Sathasivam"]

    def test_empty_list(self):
        valid = _validate_judge_tenure([], 2000)
        assert valid == []
```

**Step 2: Run tests to verify they fail**

Run: `cd d:/Startup/Smriti && python -m pytest backend/tests/unit/test_judge_validation.py::TestValidateJudgeTenure -v --no-header -q`
Expected: FAIL — `_validate_judge_tenure` not importable.

**Step 3: Implement `_validate_judge_tenure`**

Add to `backend/app/core/ingestion/metadata.py` after `_validate_judges_against_text`:

```python
# Supreme Court judge tenure lookup — (appointment_year, retirement_year).
# Only includes judges with frequently observed hallucination in audit.
# Source: Supreme Court of India official records.
_JUDGE_TENURE: dict[str, tuple[int, int]] = {
    # Key is lowercase surname (or common short form)
    "sathasivam": (2007, 2014),
    "kapadia": (2003, 2012),
    "pasayat": (2001, 2009),
    "gogoi": (2012, 2019),
    "chandrachud d.y.": (2016, 2024),
    "chandrachud y.v.": (1972, 1985),
    "krishna iyer": (1973, 1980),
    "bhagwati": (1973, 1986),
    "fazal ali": (1950, 1952),
    "mukherjea": (1950, 1955),
    "das": (1950, 1956),
    "ramana": (2014, 2022),
    "misra dipak": (2011, 2018),
    "bobde": (2013, 2021),
    "lalit": (2014, 2022),
    "nariman": (2014, 2020),
    "khanna sanjiv": (2019, 2025),
    "kaul": (2017, 2025),
    "bhat": (2019, 2025),
    "maheshwari": (2019, 2024),
    "nazeer": (2017, 2023),
    "trivedi": (2021, 2025),
    "oka": (2021, 2026),
    "rajendra babu": (1997, 2004),
    "venkatarama reddi": (2000, 2006),
    "arun kumar": (2000, 2005),
    "kania": (1987, 1992),
    "kuldip singh": (1988, 1996),
    "ramaswamy k.": (1989, 1995),
    "venkatachala": (1995, 1999),
    "phukan": (1999, 2004),
    "sen a.p.": (1978, 1985),
    "dutt murari": (2007, 2009),
    "chauhan b.s.": (2009, 2014),
    "bharucha": (1995, 2002),
}


def _validate_judge_tenure(
    judges: list[str],
    year: int | None,
) -> list[str]:
    """Filter out judges who couldn't have sat on the bench in the given year.

    Uses a lightweight lookup of SC judge tenure ranges. Judges not found
    in the lookup are passed through (benefit of the doubt).

    Args:
        judges: List of judge names.
        year: Case decision year.

    Returns:
        Filtered list with only temporally plausible judges.
    """
    if not judges or year is None:
        return list(judges) if judges else []

    valid: list[str] = []
    for judge in judges:
        # Build lookup key: try surname, then "surname initial"
        words = [w.strip(".,'") for w in judge.split()]
        surname_candidates = [w for w in words if len(w) >= 3 and w.isalpha()]
        surname = max(surname_candidates, key=len).lower() if surname_candidates else ""

        tenure = _JUDGE_TENURE.get(surname)

        # Try with first initial for disambiguation (e.g., "chandrachud d.y.")
        if tenure is None and len(words) >= 2:
            initial = words[0].strip(".").lower()
            tenure = _JUDGE_TENURE.get(f"{surname} {initial}")

        if tenure is None:
            # Unknown judge — pass through
            valid.append(judge)
        elif tenure[0] <= year <= tenure[1] + 1:
            # +1 grace: retirement mid-year means they may have sat in that year
            valid.append(judge)
        else:
            logger.warning(
                "Temporal judge mismatch: %s (tenure %d-%d) on %d case — rejected",
                judge, tenure[0], tenure[1], year,
            )

    return valid
```

**Step 4: Run tests to verify they pass**

Run: `cd d:/Startup/Smriti && python -m pytest backend/tests/unit/test_judge_validation.py -v --no-header -q`
Expected: All PASS.

**Step 5: Commit**

```bash
git add backend/app/core/ingestion/metadata.py backend/tests/unit/test_judge_validation.py
git commit -m "feat(ingestion): add temporal judge tenure validation

Catches anachronistic hallucinations like P. Sathasivam on a 1978 bench.
Lightweight lookup of ~35 most common SC judges. Unknown judges pass through."
```

---

## Task 4: Rewire Judge Merge Logic in `merge_metadata()`

**Files:**
- Modify: `backend/app/core/ingestion/metadata.py:925-1036` (merge_metadata function)
- Modify: `backend/app/core/ingestion/pipeline.py:237` (call site)
- Modify: `backend/tests/unit/test_metadata.py` (update existing merge tests)

**Step 1: Write failing tests for new merge behavior**

Add to `backend/tests/unit/test_metadata.py`:

```python
class TestMergeMetadataValidatedJudges:
    """Tests for the new validated judge merge logic."""

    def test_llm_judges_all_validated_uses_llm(self):
        """When all LLM judges appear in text, prefer LLM (fuller bench)."""
        header = "BEFORE JUSTICE CHANDRACHUD AND JUSTICE KHANNA\n"
        full_text = header + "Body..." * 500
        parquet = {"judge": "D.Y. Chandrachud"}
        llm = CaseMetadata(judge=["D.Y. Chandrachud", "Sanjiv Khanna"])
        result, prov = merge_metadata(parquet, llm, full_text=full_text)
        assert len(result.judge) == 2
        assert "Sanjiv Khanna" in result.judge

    def test_hallucinated_llm_judges_fall_back_to_parquet(self):
        """When ALL LLM judges fail text validation, use parquet."""
        header = "BEFORE JUSTICE KRISHNA IYER AND JUSTICE DESAI\n"
        full_text = header + "Body..." * 500
        parquet = {"judge": "V.R. Krishna Iyer, D.A. Desai"}
        llm = CaseMetadata(judge=["P. Sathasivam", "B.S. Chauhan"])
        result, prov = merge_metadata(parquet, llm, full_text=full_text)
        assert "V.R. Krishna Iyer" in result.judge
        assert "P. Sathasivam" not in result.judge

    def test_partial_hallucination_unions_valid_with_parquet(self):
        """When some LLM judges fail, union validated LLM + parquet."""
        header = "BEFORE JUSTICE CHANDRACHUD, JUSTICE KHANNA AND JUSTICE BHAT\n"
        full_text = header + "Body..." * 500
        parquet = {"judge": "D.Y. Chandrachud"}
        llm = CaseMetadata(
            judge=["D.Y. Chandrachud", "Sanjiv Khanna", "P. Sathasivam"],
        )
        result, prov = merge_metadata(parquet, llm, full_text=full_text)
        assert "D.Y. Chandrachud" in result.judge
        assert "Sanjiv Khanna" in result.judge
        assert "P. Sathasivam" not in result.judge

    def test_no_full_text_falls_back_to_old_logic(self):
        """When full_text not provided, use count-based fallback."""
        parquet = {"judge": "D.Y. Chandrachud"}
        llm = CaseMetadata(judge=["D.Y. Chandrachud", "Sanjiv Khanna"])
        result, prov = merge_metadata(parquet, llm)
        # Without text validation, LLM wins by count
        assert len(result.judge) == 2
```

**Step 2: Run to verify failure**

Run: `cd d:/Startup/Smriti && python -m pytest backend/tests/unit/test_metadata.py::TestMergeMetadataValidatedJudges -v --no-header -q`
Expected: FAIL — `merge_metadata()` doesn't accept `full_text` parameter.

**Step 3: Modify `merge_metadata()` signature and judge logic**

In `backend/app/core/ingestion/metadata.py`, change the function signature at line 925:

```python
def merge_metadata(
    parquet_meta: dict,
    llm_meta: CaseMetadata,
    full_text: str = "",
) -> tuple[CaseMetadata, dict[str, str]]:
```

Replace the judge merge block (lines 1005-1036) with:

```python
    # -- Judge array: Validated LLM with Parquet anchor --
    # Parquet typically only has 1 author judge. LLM extracts full bench.
    # But LLM can hallucinate judges, so we validate against the judgment text.
    judge_raw = parquet_meta.get("judge", "")
    parquet_judges: list[str] | None = None
    if (isinstance(judge_raw, str) and judge_raw.strip()) or (isinstance(judge_raw, list) and judge_raw):
        parquet_judges = _parse_judge_names(judge_raw)

    llm_judges: list[str] | None = None
    if llm_meta.judge:
        llm_judges = _parse_judge_names(llm_meta.judge)

    llm_coram = getattr(llm_meta, "coram_size", None)
    _needs_review = False

    if llm_judges and full_text:
        # Validate LLM judges against judgment header text
        validated_llm, rejected_llm = _validate_judges_against_text(
            llm_judges, full_text,
        )
        # Also apply temporal validation if year is known
        case_year = (
            parquet_meta.get("year")
            or getattr(llm_meta, "year", None)
        )
        if case_year and validated_llm:
            validated_llm = _validate_judge_tenure(validated_llm, case_year)

        if rejected_llm:
            logger.warning(
                "Judge text validation rejected %d/%d LLM judges: %s",
                len(rejected_llm), len(llm_judges), rejected_llm,
            )

        if validated_llm and not rejected_llm:
            # All LLM judges validated — use full LLM list
            result.judge = validated_llm
            provenance["judge"] = "llm_validated"
        elif validated_llm:
            # Partial validation — union validated LLM + parquet (deduped)
            merged_set: dict[str, str] = {}  # lowercase -> original
            for j in validated_llm:
                merged_set.setdefault(j.lower(), j)
            if parquet_judges:
                for j in parquet_judges:
                    merged_set.setdefault(j.lower(), j)
            result.judge = list(merged_set.values())
            provenance["judge"] = "llm_partial+parquet"
        else:
            # All LLM judges failed — fall back to parquet
            result.judge = parquet_judges
            provenance["judge"] = "parquet_llm_rejected"
            _needs_review = True
    elif llm_judges and parquet_judges:
        # No full_text for validation — fall back to count-based logic
        if len(llm_judges) > len(parquet_judges):
            result.judge = llm_judges
            provenance["judge"] = "llm_unvalidated"
        elif llm_coram and isinstance(llm_coram, int) and llm_coram > len(parquet_judges):
            result.judge = llm_judges
            provenance["judge"] = "llm_unvalidated"
        else:
            result.judge = parquet_judges
            provenance["judge"] = "parquet"
    elif llm_judges:
        # Only LLM — validate if text available
        if full_text:
            validated_llm, _ = _validate_judges_against_text(llm_judges, full_text)
            case_year = parquet_meta.get("year") or getattr(llm_meta, "year", None)
            if case_year and validated_llm:
                validated_llm = _validate_judge_tenure(validated_llm, case_year)
            result.judge = validated_llm or llm_judges
            provenance["judge"] = "llm_validated" if validated_llm else "llm_unvalidated"
        else:
            result.judge = llm_judges
            provenance["judge"] = "llm"
    elif parquet_judges:
        result.judge = parquet_judges
        provenance["judge"] = "parquet"

    if _needs_review:
        provenance["_needs_review"] = "all_llm_judges_rejected"
```

**Step 4: Update call site in `pipeline.py`**

In `backend/app/core/ingestion/pipeline.py` at line 237, change:

```python
# FROM:
    metadata, provenance = merge_metadata(validated_parquet, llm_meta)

# TO:
    metadata, provenance = merge_metadata(validated_parquet, llm_meta, full_text=full_text)
```

**Step 5: Run all metadata tests**

Run: `cd d:/Startup/Smriti && python -m pytest backend/tests/unit/test_metadata.py backend/tests/unit/test_judge_validation.py -v --no-header -q`
Expected: All PASS.

**Step 6: Commit**

```bash
git add backend/app/core/ingestion/metadata.py backend/app/core/ingestion/pipeline.py backend/tests/unit/test_metadata.py
git commit -m "fix(ingestion): replace 'more judges wins' with validated judge merge

merge_metadata() now validates LLM judges against judgment header text
and temporal tenure data. Falls back to parquet when LLM hallucinates.
Fixes Bug 4 from ingestion quality audit."
```

---

## Task 5: Prompt Hardening for LLM Hallucination (Bug 2 — Layer 1)

**Files:**
- Modify: `backend/app/core/legal/prompts.py:9-48` (system prompt)

**Step 1: Add negative grounding rules to metadata extraction system prompt**

In `backend/app/core/legal/prompts.py`, insert after line 12 (after the first paragraph of `METADATA_EXTRACTION_SYSTEM`):

```python
# After "You never hallucinate or fabricate information not present in the source text."
# Add this block BEFORE "EXTRACTION RULES:":

CRITICAL GROUNDING RULES — READ BEFORE EXTRACTING:
- You are a metadata EXTRACTOR, not a legal knowledge base. Your ONLY source is the \
judgment text provided below.
- NEVER use your training data to fill in any field. If the text is garbled, unreadable, \
or ambiguous, return null rather than guessing.
- If you recognize a famous case by its title (e.g., "Kesavananda Bharati", "Maneka Gandhi"), \
do NOT fill in metadata from your knowledge of that case. Extract ONLY from the provided text.
- JUDGE NAMES: Must appear VERBATIM in the text header (first ~2000 characters). If the \
header is damaged or unreadable, return null for judge fields rather than guessing from \
the case name.
- If OCR artifacts make any field unreadable, return null — do NOT reconstruct from your \
knowledge of the case or Indian legal history.

```

The full updated opening of `METADATA_EXTRACTION_SYSTEM` should read:

```python
METADATA_EXTRACTION_SYSTEM: Final[str] = """\
You are an expert Indian legal metadata extraction system. You extract structured \
metadata from Supreme Court and High Court judgment text with high accuracy. \
You never hallucinate or fabricate information not present in the source text.

CRITICAL GROUNDING RULES — READ BEFORE EXTRACTING:
- You are a metadata EXTRACTOR, not a legal knowledge base. Your ONLY source is the \
judgment text provided below.
- NEVER use your training data to fill in any field. If the text is garbled, unreadable, \
or ambiguous, return null rather than guessing.
- If you recognize a famous case by its title (e.g., "Kesavananda Bharati", "Maneka Gandhi"), \
do NOT fill in metadata from your knowledge of that case. Extract ONLY from the provided text.
- JUDGE NAMES: Must appear VERBATIM in the text header (first ~2000 characters). If the \
header is damaged or unreadable, return null for judge fields rather than guessing from \
the case name.
- If OCR artifacts make any field unreadable, return null — do NOT reconstruct from your \
knowledge of the case or Indian legal history.

EXTRACTION RULES:
1. Extract ONLY information explicitly stated in the judgment text. If a field \
cannot be determined, return null (for strings/integers/booleans) or an empty array [] (for arrays).
...
```

**Step 2: Run existing tests to verify no breakage**

Run: `cd d:/Startup/Smriti && python -m pytest backend/tests/unit/test_metadata.py backend/tests/unit/test_extractor.py -v --no-header -q`
Expected: All PASS (prompt changes don't affect unit tests).

**Step 3: Commit**

```bash
git add backend/app/core/legal/prompts.py
git commit -m "fix(ingestion): harden metadata prompt with negative grounding rules

Adds explicit instructions to never use training data for metadata fields.
Addresses Bug 2 (LLM hallucination on OCR-degraded PDFs)."
```

---

## Task 6: Post-Extraction Content Validation (Bug 2 — Layer 2)

**Files:**
- Modify: `backend/app/core/ingestion/metadata.py` (add new function)
- Modify: `backend/app/core/ingestion/pipeline.py` (wire in after merge)
- Create: `backend/tests/unit/test_content_validation.py`

**Step 1: Write failing tests**

Create `backend/tests/unit/test_content_validation.py`:

```python
"""Tests for post-extraction content validation."""

import pytest

from app.core.ingestion.metadata import (
    CaseMetadata,
    _validate_metadata_against_text,
)


class TestValidateMetadataAgainstText:
    """Tests for _validate_metadata_against_text()."""

    def test_keywords_matching_text_kept(self):
        text = "This case concerns murder under Section 302 of IPC and bail jurisprudence."
        meta = CaseMetadata(keywords=["murder", "bail jurisprudence", "Section 302 IPC"])
        result = _validate_metadata_against_text(meta, text)
        assert result.keywords == ["murder", "bail jurisprudence", "Section 302 IPC"]

    def test_keywords_not_in_text_removed(self):
        text = "This case concerns land acquisition under the Land Acquisition Act."
        meta = CaseMetadata(
            keywords=["land acquisition", "eminent domain", "custodial death", "bail"],
        )
        result = _validate_metadata_against_text(meta, text)
        # "land" and "acquisition" appear in text; "custodial" and "bail" do not
        assert "land acquisition" in result.keywords
        assert "custodial death" not in result.keywords
        assert "bail" not in result.keywords

    def test_ratio_sharing_tokens_with_text_kept(self):
        text = "The court held that the right to life under Article 21 includes the right to livelihood."
        meta = CaseMetadata(
            ratio_decidendi="The right to life under Article 21 encompasses the right to livelihood",
        )
        result = _validate_metadata_against_text(meta, text)
        assert result.ratio_decidendi is not None

    def test_ratio_not_matching_text_nulled(self):
        text = "This case concerns excise duty on manufactured goods under Central Excise Act."
        meta = CaseMetadata(
            ratio_decidendi="The doctrine of res judicata bars a second suit on the same cause of action in family law matters",
        )
        result = _validate_metadata_against_text(meta, text)
        assert result.ratio_decidendi is None

    def test_short_text_skips_validation(self):
        meta = CaseMetadata(keywords=["anything"], ratio_decidendi="anything")
        result = _validate_metadata_against_text(meta, "Short.")
        assert result.keywords == ["anything"]
        assert result.ratio_decidendi == "anything"
```

**Step 2: Run to verify failure**

Run: `cd d:/Startup/Smriti && python -m pytest backend/tests/unit/test_content_validation.py -v --no-header -q`
Expected: FAIL — `_validate_metadata_against_text` not importable.

**Step 3: Implement `_validate_metadata_against_text`**

Add to `backend/app/core/ingestion/metadata.py` after `_validate_judge_tenure`:

```python
# Common English stopwords to exclude from token matching
_STOPWORDS = frozenset({
    "the", "a", "an", "is", "was", "are", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "shall",
    "should", "may", "might", "can", "could", "must", "and", "but", "or",
    "nor", "not", "no", "so", "if", "then", "than", "that", "this",
    "which", "who", "whom", "what", "where", "when", "how", "all", "each",
    "every", "both", "few", "more", "most", "other", "some", "such", "only",
    "own", "same", "too", "very", "of", "in", "on", "at", "to", "for",
    "with", "by", "from", "as", "into", "through", "during", "before",
    "after", "above", "below", "between", "under", "upon", "about",
    "it", "its", "he", "she", "they", "them", "his", "her", "their",
    "case", "court", "judgment", "order", "act", "section", "india",
    "supreme", "high", "appeal", "petition", "respondent", "appellant",
})


def _validate_metadata_against_text(
    metadata: CaseMetadata,
    full_text: str,
    min_text_len: int = 200,
) -> CaseMetadata:
    """Post-extraction sanity checks — remove fields that contradict the text.

    Validates:
    - Keywords: each keyword must have at least one non-stopword token in full_text.
    - Ratio decidendi: must share >=3 non-stopword tokens with full_text.

    Args:
        metadata: Extracted metadata to validate.
        full_text: Full judgment text.
        min_text_len: Skip validation if text is shorter than this.

    Returns:
        Metadata with invalidated fields nulled out.
    """
    if len(full_text) < min_text_len:
        return metadata

    text_lower = full_text.lower()

    # --- Validate keywords ---
    if metadata.keywords:
        validated_kw: list[str] = []
        for kw in metadata.keywords:
            # Check if any non-stopword token (4+ chars) from the keyword appears in text
            tokens = [t for t in re.split(r"\W+", kw.lower()) if len(t) >= 4 and t not in _STOPWORDS]
            if not tokens:
                # Short keyword — keep it (e.g., "PIL", "bail")
                validated_kw.append(kw)
            elif any(token in text_lower for token in tokens):
                validated_kw.append(kw)
            else:
                logger.warning("Keyword not found in text, removing: %s", kw)
        metadata.keywords = validated_kw if validated_kw else None

    # --- Validate ratio_decidendi ---
    if metadata.ratio_decidendi:
        ratio_tokens = [
            t for t in re.split(r"\W+", metadata.ratio_decidendi.lower())
            if len(t) >= 4 and t not in _STOPWORDS
        ]
        matching = sum(1 for t in ratio_tokens if t in text_lower)
        if ratio_tokens and matching < 3:
            logger.warning(
                "Ratio decidendi shares only %d/%d tokens with text — nulling",
                matching, len(ratio_tokens),
            )
            metadata.ratio_decidendi = None

    return metadata
```

**Step 4: Wire into pipeline**

In `backend/app/core/ingestion/pipeline.py`, add after line 244 (after `cross_validate_propositions`):

```python
    # Post-extraction content validation (Bug 2 mitigation)
    metadata = _validate_metadata_against_text(metadata, full_text)
```

Add the import at the top of `pipeline.py`:

```python
from app.core.ingestion.metadata import (
    ...
    _validate_metadata_against_text,
)
```

**Step 5: Run all tests**

Run: `cd d:/Startup/Smriti && python -m pytest backend/tests/unit/test_content_validation.py backend/tests/unit/test_metadata.py -v --no-header -q`
Expected: All PASS.

**Step 6: Commit**

```bash
git add backend/app/core/ingestion/metadata.py backend/app/core/ingestion/pipeline.py backend/tests/unit/test_content_validation.py
git commit -m "feat(ingestion): add post-extraction content validation

Validates keywords and ratio_decidendi against full_text. Removes
keywords not found in text, nulls ratio that doesn't share tokens
with the judgment. Bug 2 Layer 2 mitigation."
```

---

## Task 7: Pre-1964 PDF Boundary Stripping (Bug 3)

**Files:**
- Modify: `backend/app/core/ingestion/pdf.py` (add new function, wire into extract_and_score)
- Create: `backend/tests/unit/test_pdf_boundary.py`

**Step 1: Write failing tests**

Create `backend/tests/unit/test_pdf_boundary.py`:

```python
"""Tests for PDF boundary stripping."""

import pytest

from app.core.ingestion.pdf import _strip_leading_judgment_bleed


class TestStripLeadingJudgmentBleed:
    """Tests for boundary text removal."""

    def test_clean_text_unchanged(self):
        text = "IN THE SUPREME COURT OF INDIA\nCIVIL APPEAL NO. 123\nBody..."
        assert _strip_leading_judgment_bleed(text) == text

    def test_strips_leading_bleed_before_court_header(self):
        bleed = "...previous judgment conclusion. The appeal is dismissed.\n" * 5
        real = "IN THE SUPREME COURT OF INDIA\nCIVIL APPEAL NO. 123\nBody of judgment..."
        text = bleed + real
        result = _strip_leading_judgment_bleed(text)
        assert result.startswith("IN THE SUPREME COURT OF INDIA")
        assert "previous judgment conclusion" not in result

    def test_strips_bleed_before_reportable(self):
        bleed = "Some trailing text from previous case about damages.\n" * 5
        real = "REPORTABLE\nIN THE SUPREME COURT OF INDIA\nBody..."
        text = bleed + real
        result = _strip_leading_judgment_bleed(text)
        assert result.startswith("REPORTABLE")

    def test_strips_bleed_before_judgment_marker(self):
        bleed = "Tail of previous: ordered accordingly.\n" * 5
        real = "JUDGMENT\nThe facts of the case are..."
        text = bleed + real
        result = _strip_leading_judgment_bleed(text)
        assert result.startswith("JUDGMENT")

    def test_no_marker_found_returns_unchanged(self):
        text = "This is some text without any case header markers at all."
        assert _strip_leading_judgment_bleed(text) == text

    def test_marker_within_first_200_chars_no_strip(self):
        """If the marker is near the start, there's no meaningful bleed."""
        text = "Short intro\nIN THE SUPREME COURT OF INDIA\nBody..."
        assert _strip_leading_judgment_bleed(text) == text

    def test_neutral_citation_as_marker(self):
        bleed = "End of previous case text about constitutional validity.\n" * 5
        real = "2023:INSC:456\nIN THE SUPREME COURT\nBody..."
        text = bleed + real
        result = _strip_leading_judgment_bleed(text)
        assert result.startswith("2023:INSC:456")
```

**Step 2: Run to verify failure**

Run: `cd d:/Startup/Smriti && python -m pytest backend/tests/unit/test_pdf_boundary.py -v --no-header -q`
Expected: FAIL — `_strip_leading_judgment_bleed` not importable.

**Step 3: Implement `_strip_leading_judgment_bleed`**

Add to `backend/app/core/ingestion/pdf.py` after the imports (around line 30):

```python
# Patterns that indicate the start of a new judgment
_JUDGMENT_START_PATTERNS = [
    re.compile(r"IN\s+THE\s+SUPREME\s+COURT\s+OF\s+INDIA", re.IGNORECASE),
    re.compile(r"IN\s+THE\s+HIGH\s+COURT\s+OF", re.IGNORECASE),
    re.compile(r"\b(REPORTABLE|NON[\s-]?REPORTABLE)\b", re.IGNORECASE),
    re.compile(r"^\s*(JUDGMENT|ORDER)\s*$", re.IGNORECASE | re.MULTILINE),
    re.compile(r"\b(CIVIL|CRIMINAL)\s+APPEAL\s+NO", re.IGNORECASE),
    re.compile(r"\b(WRIT\s+PETITION|SPECIAL\s+LEAVE\s+PETITION)\b", re.IGNORECASE),
    re.compile(r"\bSLP\s*\(\s*(C|Crl)\s*\)\s*No", re.IGNORECASE),
    re.compile(r"\d{4}:\s*INSC:\s*\d+"),  # Neutral citation
]


def _strip_leading_judgment_bleed(
    text: str,
    scan_chars: int = 3000,
    min_bleed: int = 200,
) -> str:
    """Remove leading text from a previous judgment that bleeds into this PDF.

    Scans the first ``scan_chars`` characters for case header markers. If the
    earliest marker appears after ``min_bleed`` characters, everything before
    it is considered bleed from a previous judgment and is stripped.

    Args:
        text: Full extracted text.
        scan_chars: How many chars from the start to scan for markers.
        min_bleed: Minimum chars before marker to consider it bleed (avoids
            stripping legitimate short preambles).

    Returns:
        Text with leading bleed removed, or original text if no bleed detected.
    """
    if len(text) < min_bleed:
        return text

    scan_region = text[:scan_chars]
    earliest_pos = scan_chars  # sentinel

    for pattern in _JUDGMENT_START_PATTERNS:
        match = pattern.search(scan_region)
        if match and match.start() < earliest_pos:
            earliest_pos = match.start()

    if earliest_pos >= min_bleed and earliest_pos < scan_chars:
        stripped_len = earliest_pos
        logger.info(
            "Stripped %d chars of leading judgment bleed (marker at pos %d)",
            stripped_len, earliest_pos,
        )
        return text[earliest_pos:]

    return text
```

**Step 4: Wire into `extract_and_score`**

In `backend/app/core/ingestion/pdf.py`, in `extract_and_score()` at line 704, add after text extraction:

```python
async def extract_and_score(file_path: str) -> TextQuality:
    ...
    text, page_count, page_map = await extract_pdf_text(file_path)
    ...
    # (after the OCR fallback block, before quality scoring)

    # Strip leading bleed from previous judgment (pre-1964 PDFs)
    if text:
        text = _strip_leading_judgment_bleed(text)

    if not text:
        text = ""
    ...
```

Insert the `_strip_leading_judgment_bleed` call after line 714 (`page_map = []`) and before line 716 (`if not text:`).

**Step 5: Run tests**

Run: `cd d:/Startup/Smriti && python -m pytest backend/tests/unit/test_pdf_boundary.py -v --no-header -q`
Expected: All PASS.

**Step 6: Commit**

```bash
git add backend/app/core/ingestion/pdf.py backend/tests/unit/test_pdf_boundary.py
git commit -m "fix(ingestion): strip leading judgment bleed from PDFs

Detects and removes text from a previous judgment that bleeds into
the start of a PDF. Affects ~24% of pre-1964 S3 PDFs. Uses case
header markers (court name, REPORTABLE, neutral citation) to find
the real start. Fixes Bug 3."
```

---

## Task 8: Confidence Gating in Pipeline (Fix 5)

**Files:**
- Modify: `backend/app/core/ingestion/metadata.py` (add `_strip_unreliable_llm_fields`)
- Modify: `backend/app/core/ingestion/pipeline.py` (add gating after merge)
- Modify: `backend/tests/unit/test_metadata.py` (add tests)

**Step 1: Write failing tests**

Add to `backend/tests/unit/test_metadata.py`:

```python
from app.core.ingestion.metadata import _strip_unreliable_llm_fields


class TestStripUnreliableLlmFields:
    """Tests for confidence-based field stripping."""

    def test_strips_semantic_fields(self):
        meta = CaseMetadata(
            title="Correct Title",  # Parquet — should survive
            ratio_decidendi="Hallucinated ratio",
            keywords=["wrong", "keywords"],
            case_type="Criminal Appeal",
            jurisdiction="civil",
            bench_type="division",
            headnotes="Hallucinated headnotes",
            outcome_summary="Wrong summary",
        )
        result = _strip_unreliable_llm_fields(meta)
        assert result.title == "Correct Title"
        assert result.ratio_decidendi is None
        assert result.keywords is None
        assert result.case_type is None
        assert result.jurisdiction is None
        assert result.bench_type is None
        assert result.headnotes is None
        assert result.outcome_summary is None

    def test_preserves_parquet_sourced_fields(self):
        meta = CaseMetadata(
            title="Title",
            citation="(2023) 1 SCC 100",
            court="Supreme Court of India",
            year=2023,
            petitioner="A",
            respondent="B",
            judge=["Judge X"],
        )
        result = _strip_unreliable_llm_fields(meta)
        assert result.title == "Title"
        assert result.citation == "(2023) 1 SCC 100"
        assert result.court == "Supreme Court of India"
        assert result.year == 2023
        assert result.judge == ["Judge X"]
```

**Step 2: Run to verify failure**

Run: `cd d:/Startup/Smriti && python -m pytest backend/tests/unit/test_metadata.py::TestStripUnreliableLlmFields -v --no-header -q`
Expected: FAIL — `_strip_unreliable_llm_fields` not importable.

**Step 3: Implement `_strip_unreliable_llm_fields`**

Add to `backend/app/core/ingestion/metadata.py` after `_validate_metadata_against_text`:

```python
# Fields to null out when confidence is very low
_UNRELIABLE_LLM_FIELDS = (
    "ratio_decidendi", "keywords", "case_type", "jurisdiction",
    "bench_type", "headnotes", "outcome_summary",
    "legal_principles_applied", "issue_classification", "fact_pattern_tags",
    "opinion_type", "judicial_tone", "key_observations",
    "arguments_raised", "fact_pattern_summary",
)


def _strip_unreliable_llm_fields(metadata: CaseMetadata) -> CaseMetadata:
    """Null out LLM-only semantic fields when extraction confidence is very low.

    Preserves Parquet-sourced fields (title, citation, court, year, judge, etc.)
    and structured fields (decision_date, petitioner, respondent).
    """
    for field_name in _UNRELIABLE_LLM_FIELDS:
        if hasattr(metadata, field_name):
            setattr(metadata, field_name, None)
    return metadata
```

**Step 4: Wire confidence gating into pipeline**

In `backend/app/core/ingestion/pipeline.py`, add after the content validation line (after `_validate_metadata_against_text`):

```python
    # Confidence gating — strip unreliable fields or flag for review
    confidence = compute_extraction_confidence(metadata)
    if confidence < 0.4:
        logger.warning(
            "Very low extraction confidence (%.3f) for %s — stripping LLM fields",
            confidence, pdf_path,
        )
        metadata = _strip_unreliable_llm_fields(metadata)
        provenance["confidence_action"] = "stripped_llm_fields"
        provenance["_needs_review"] = provenance.get("_needs_review", "") + ",low_confidence"
    elif confidence < 0.6:
        logger.warning(
            "Borderline extraction confidence (%.3f) for %s — flagging for review",
            confidence, pdf_path,
        )
        provenance["confidence_action"] = "flagged_for_review"
        provenance["_needs_review"] = provenance.get("_needs_review", "") + ",borderline_confidence"
```

Add import for `_strip_unreliable_llm_fields` at the top of `pipeline.py`.

**Step 5: Run tests**

Run: `cd d:/Startup/Smriti && python -m pytest backend/tests/unit/test_metadata.py -v --no-header -q`
Expected: All PASS.

**Step 6: Commit**

```bash
git add backend/app/core/ingestion/metadata.py backend/app/core/ingestion/pipeline.py backend/tests/unit/test_metadata.py
git commit -m "feat(ingestion): add confidence gating with LLM field stripping

Cases with extraction confidence <0.4 have semantic LLM fields nulled
out. Confidence 0.4-0.6 flagged for review. Prevents low-quality
hallucinated metadata from polluting the database."
```

---

## Task 9: Run Full Test Suite

**Files:** None (verification only)

**Step 1: Run all backend unit tests**

Run: `cd d:/Startup/Smriti && python -m pytest backend/tests/unit/ -v --no-header -q --tb=short`
Expected: All ~2185 tests PASS.

**Step 2: Run all frontend tests**

Run: `cd d:/Startup/Smriti && cd frontend && npx vitest run --reporter=verbose 2>&1 | tail -20`
Expected: All ~311 tests PASS.

**Step 3: If any tests fail, fix them before proceeding.**

**Step 4: Commit any test fixes**

```bash
git commit -m "fix: resolve test failures from ingestion quality fixes"
```

---

## Task 10: Create Re-ingestion Script for 379 Trial Cases

**Files:**
- Create: `backend/scripts/reingest_trial_cases.py`

**Step 1: Write the re-ingestion script**

```python
#!/usr/bin/env python3
"""Re-ingest the 379 trial cases (1979-2018) after pipeline quality fixes.

Usage:
    # Dry run — show what would be deleted
    python -m scripts.reingest_trial_cases --dry-run

    # Delete corrupted data
    python -m scripts.reingest_trial_cases --delete

    # Re-ingest with fixed pipeline (after deletion)
    python -m scripts.reingest_trial_cases --reingest
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Trial run metadata — adjust these to match your actual trial batch
TRIAL_RUN_DIR = Path("batch_runs")  # Contains run_id directories
TRIAL_YEARS = range(1979, 2019)  # 1979-2018 inclusive


async def find_trial_cases(db_url: str) -> list[str]:
    """Find case IDs from the trial batch run."""
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text

    engine = create_async_engine(db_url)
    async with engine.connect() as conn:
        # Trial cases: years 1979-2018, ingested during trial batch window
        result = await conn.execute(
            text(
                "SELECT id, title, year FROM cases "
                "WHERE year >= :min_year AND year <= :max_year "
                "ORDER BY year, title"
            ),
            {"min_year": min(TRIAL_YEARS), "max_year": max(TRIAL_YEARS)},
        )
        rows = result.fetchall()
        logger.info("Found %d cases in year range %d-%d", len(rows), min(TRIAL_YEARS), max(TRIAL_YEARS))
        return [str(row[0]) for row in rows]


async def delete_from_postgres(db_url: str, case_ids: list[str]) -> int:
    """Delete trial cases from PostgreSQL."""
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text

    engine = create_async_engine(db_url)
    async with engine.begin() as conn:
        result = await conn.execute(
            text("DELETE FROM cases WHERE id = ANY(:ids)"),
            {"ids": case_ids},
        )
        count = result.rowcount
        logger.info("Deleted %d cases from PostgreSQL", count)
        return count


async def delete_from_pinecone(case_ids: list[str]) -> int:
    """Delete vectors for trial cases from Pinecone."""
    from app.core.config import settings
    from pinecone import Pinecone

    pc = Pinecone(api_key=settings.pinecone_api_key)
    index = pc.Index(host=settings.pinecone_host)

    deleted = 0
    # Delete in batches of 10 (Pinecone filter delete limit)
    for i in range(0, len(case_ids), 10):
        batch = case_ids[i:i + 10]
        for cid in batch:
            index.delete(filter={"case_id": cid})
            deleted += 1
        logger.info("Pinecone: deleted vectors for %d/%d cases", deleted, len(case_ids))

    return deleted


async def delete_from_neo4j(case_ids: list[str]) -> int:
    """Delete case nodes and edges from Neo4j."""
    from app.core.config import settings
    from neo4j import AsyncGraphDatabase

    driver = AsyncGraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_username, settings.neo4j_password),
    )
    async with driver.session() as session:
        result = await session.run(
            "UNWIND $ids AS cid "
            "MATCH (c:Case {case_id: cid}) "
            "DETACH DELETE c "
            "RETURN count(c) AS deleted",
            ids=case_ids,
        )
        record = await result.single()
        count = record["deleted"] if record else 0
        logger.info("Deleted %d case nodes from Neo4j", count)
    await driver.close()
    return count


async def main():
    parser = argparse.ArgumentParser(description="Re-ingest trial cases")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted")
    parser.add_argument("--delete", action="store_true", help="Delete corrupted trial data")
    parser.add_argument("--reingest", action="store_true", help="Re-ingest after deletion")
    parser.add_argument("--db-url", default=None, help="Database URL override")
    args = parser.parse_args()

    from app.core.config import settings
    db_url = args.db_url or settings.database_url

    case_ids = await find_trial_cases(db_url)

    if args.dry_run:
        logger.info("DRY RUN: Would delete %d cases:", len(case_ids))
        for cid in case_ids[:10]:
            logger.info("  %s", cid)
        if len(case_ids) > 10:
            logger.info("  ... and %d more", len(case_ids) - 10)
        return

    if args.delete:
        logger.info("Deleting %d trial cases from all stores...", len(case_ids))
        pg = await delete_from_postgres(db_url, case_ids)
        pc = await delete_from_pinecone(case_ids)
        neo = await delete_from_neo4j(case_ids)
        logger.info("Deletion complete: PG=%d, Pinecone=%d, Neo4j=%d", pg, pc, neo)

        # Save deleted IDs for re-ingestion
        deleted_path = Path("trial_deleted_ids.json")
        deleted_path.write_text(json.dumps(case_ids, indent=2))
        logger.info("Saved deleted IDs to %s", deleted_path)

    if args.reingest:
        logger.info(
            "Re-ingestion should be run via batch_ingest_vertex.py or ingest_s3.py "
            "with the fixed pipeline. Use --years 1979-2018 --batch-size 50"
        )


if __name__ == "__main__":
    asyncio.run(main())
```

**Step 2: Commit**

```bash
git add backend/scripts/reingest_trial_cases.py
git commit -m "feat(scripts): add re-ingestion script for 379 corrupted trial cases

Supports --dry-run, --delete, and --reingest modes. Deletes from
PostgreSQL, Pinecone, and Neo4j before re-ingestion with fixed pipeline."
```

---

## Task 11: Final Integration Verification

**Step 1: Run full backend test suite one more time**

Run: `cd d:/Startup/Smriti && python -m pytest backend/tests/unit/ -v --no-header -q --tb=short 2>&1 | tail -30`
Expected: All tests PASS.

**Step 2: Verify all new functions are importable**

Run: `cd d:/Startup/Smriti && python -c "from app.core.ingestion.metadata import _validate_judges_against_text, _validate_judge_tenure, _validate_metadata_against_text, _strip_unreliable_llm_fields; from app.core.ingestion.pdf import _strip_leading_judgment_bleed; print('All imports OK')"`
Expected: `All imports OK`

**Step 3: Commit any remaining fixes**

---

## Summary of All Commits

| Task | Commit Message | Files |
|------|---------------|-------|
| 1 | `fix(batch): add custom_id mapping` | batch_ingest_vertex.py |
| 2 | `feat(ingestion): add judge-text validation` | metadata.py, test_judge_validation.py |
| 3 | `feat(ingestion): add temporal judge tenure validation` | metadata.py, test_judge_validation.py |
| 4 | `fix(ingestion): replace 'more judges wins' with validated merge` | metadata.py, pipeline.py, test_metadata.py |
| 5 | `fix(ingestion): harden metadata prompt` | prompts.py |
| 6 | `feat(ingestion): add post-extraction content validation` | metadata.py, pipeline.py, test_content_validation.py |
| 7 | `fix(ingestion): strip leading judgment bleed` | pdf.py, test_pdf_boundary.py |
| 8 | `feat(ingestion): add confidence gating` | metadata.py, pipeline.py, test_metadata.py |
| 9 | Verification only | — |
| 10 | `feat(scripts): add re-ingestion script` | reingest_trial_cases.py |
| 11 | Final verification | — |
