# Ingestion Pipeline Quality Fix — Design Document

**Date:** 2026-03-31
**Status:** Approved
**Scope:** Fix 4 critical ingestion bugs + add validation layers + re-ingest 379 corrupted trial cases

---

## Problem Statement

A quality audit of 379 trial-ingested cases (1979-2018) revealed **4 independent bugs** compounding into a metadata corruption disaster affecting ~62% of LLM-extracted fields. Cases 2023-2026 were ingested via online pipeline and are unaffected by the worst bug (batch misalignment).

### Bug Summary

| Bug | Severity | Pipeline | Root Cause |
|-----|----------|----------|------------|
| 1. Batch response misalignment | CRITICAL | Batch only | `enumerate()` resets per JSONL file; no `custom_id` |
| 2. LLM hallucination on OCR-degraded PDFs | CRITICAL | Both | Gemini uses training data instead of extracting from text |
| 3. PDF boundary overlap (pre-1964) | MEDIUM | Both | Early S3 PDFs share boundary pages (~24% of 1950-1964) |
| 4. Merge logic amplifier | MEDIUM | Both | "More judges wins" lets hallucinated lists override correct parquet |

### Affected Fields (batch-corrupted)

- **WRONG for ~62% of batch cases:** judge, author_judge, coram_size, bench_type, opinion_type, keywords, case_type, jurisdiction, disposal_nature, ratio_decidendi, headnotes, outcome_summary, acts_cited (partial), legal_principles_applied, issue_classification, fact_pattern_tags
- **CORRECT (from Parquet/PDF):** title, citation, year, decision_date, court, petitioner, respondent, full_text, text_hash, s3_source_path

### Impact on Features

| Feature | Impact | Severity |
|---------|--------|----------|
| Search by judge | Returns wrong cases | CRITICAL |
| Case type / jurisdiction filtering | Wrong filters for 62% of batch cases | CRITICAL |
| Ratio decidendi display | Shows ratio from wrong case | CRITICAL |
| Citation graph | Partially wrong (cases_cited partially from regex) | HIGH |
| Keyword search | Keywords from wrong cases | HIGH |
| Full-text search | WORKS CORRECTLY | OK |
| Case title/citation | WORKS CORRECTLY | OK |

---

## Fix 1: Batch Custom ID Mapping

**File:** `backend/scripts/batch_ingest_vertex.py`
**Bug:** Line-number positional mapping with `enumerate()` resetting per JSONL result file.

### Design

Add `custom_id` field to each batch JSONL request entry. Vertex AI Batch API preserves `custom_id` in responses. Parse responses by `custom_id` instead of line position.

**Request side (JSONL entry):**
```json
{
    "custom_id": "case_2018_1_123_456_EN",
    "request": { "..." }
}
```

**Response parsing:**
```python
for blob in result_blobs:
    for line in content.strip().split("\n"):
        result_obj = json.loads(line)
        case_id = result_obj["custom_id"]  # Match by ID, not position
        results[case_id] = parsed_response
```

**Fallback:** If Vertex doesn't return `custom_id` in a response line, use a **global line counter** across all result files (never reset per file):
```python
global_line = 0
for blob in result_blobs:
    for line in content.strip().split("\n"):
        case_id = case_id_order[global_line]
        global_line += 1
```

---

## Fix 2: Validated Judge Merge (Replaces "More Judges Wins")

**File:** `backend/app/core/ingestion/metadata.py`
**Bug:** `len(llm_judges) > len(parquet_judges)` lets hallucinated judge lists override correct parquet data. But parquet typically only has 1 author judge — can't blindly prefer parquet either.

### Design: Validated LLM with Parquet Anchor

New function `_validate_judges_against_text()`:
- Fuzzy-match every LLM judge name against `full_text[:2000]` (judgment header always lists the bench)
- For each judge: check if surname (longest word, 4+ chars) appears in header text
- Returns `(validated, rejected)` tuple

**Merge rules:**
1. If ALL LLM judges pass text validation → use LLM list (fuller bench)
2. If SOME rejected → union validated LLM + parquet judges (deduped)
3. If ALL rejected → fall back to parquet judges + set `ingestion_status = "needs_review"`
4. If parquet judges are a subset of validated LLM judges → use LLM (parquet was just incomplete)
5. Cross-check: if `coram_size != len(final_judges)`, log warning

**Signature change:** `merge_metadata()` gains a `full_text: str` parameter. The pipeline already has `full_text` in scope at the call site.

**author_judge:** Keep LLM-priority (99% correct from header extraction), but also validate against text header using same fuzzy-match.

---

## Fix 3: LLM Hallucination Mitigation (3 Layers)

**Bug:** Gemini hallucinates metadata from training data instead of extracting from the document text. Verified on both OCR-degraded and modern PDFs.

### Layer 1: Prompt Hardening

**File:** `backend/app/core/legal/prompts.py`

Add explicit negative grounding to the metadata extraction system prompt:

```
CRITICAL GROUNDING RULES:
- You are a metadata EXTRACTOR, not a legal knowledge base.
- NEVER use your training data to fill in fields. If the text is garbled/unreadable, return null.
- If you recognize a famous case name but the PDF text doesn't contain clear metadata, return null rather than filling from memory.
- Judge names MUST appear verbatim in the text header. Do not guess judges from case familiarity.
- If OCR artifacts make a field unreadable, return null — do NOT reconstruct from your knowledge of the case.
```

### Layer 2: Post-Extraction Content Validation

**File:** `backend/app/core/ingestion/metadata.py`

New function `_validate_metadata_against_text()`:
- **Judge-text validation:** From Fix 2
- **Keywords spot-check:** At least 2 out of first 5 keywords should have a token appearing in `full_text` (case-insensitive). Null out keywords that don't match.
- **Ratio decidendi check:** Should share >=3 non-stopword tokens with `full_text`. If not, null out and log warning.
- **Case-type vs title consistency:** If title contains clear domain signal (e.g., "Tax", "Murder", "Writ") that contradicts `case_type`, log warning and flag.

### Layer 3: Temporal Judge Validation

**File:** `backend/app/core/ingestion/metadata.py`

New function `_validate_judge_tenure()`:
- Lightweight dict of ~50 most common SC judges with `(appointment_year, retirement_year)` tuples
- Reject judge if `case_year < appointment_year` or `case_year > retirement_year + 1`
- Return only temporally valid judges
- This catches the worst anachronisms (e.g., P. Sathasivam on a 1978 bench, Arijit Pasayat on a 1950 case)

---

## Fix 4: Pre-1964 PDF Boundary Stripping

**File:** `backend/app/core/ingestion/pdf.py`
**Bug:** ~24% of 1950-1964 S3 PDFs start with tail content from the previous judgment.

### Design

New function `_strip_leading_judgment_bleed()`:
- Scan first 3000 chars for case header markers:
  - `"IN THE SUPREME COURT OF INDIA"`
  - `"JUDGMENT"` / `"ORDER"` / `"REPORTABLE"`
  - `"CIVIL APPEAL"` / `"CRIMINAL APPEAL"` / `"WRIT PETITION"` / `"SLP"`
  - Neutral citation pattern `YYYY:INSC:NNNN`
- If first marker appears after position 200, strip everything before it
- Log stripped content length
- Applied to ALL PDFs (cheap regex scan), but only triggers when significant text precedes first header
- **Safety:** If no marker found within 3000 chars, leave text untouched

---

## Fix 5: Confidence Gating

**File:** `backend/app/core/ingestion/pipeline.py`
**Current:** `compute_extraction_confidence()` scores 0.0-1.0 but pipeline always proceeds.

### Design

Add thresholds after metadata merge:

| Confidence | Action |
|------------|--------|
| < 0.4 | Strip all LLM-only semantic fields, keep parquet ground truth, set `needs_review` |
| 0.4 - 0.6 | Keep fields but set `needs_review` |
| >= 0.6 | Proceed normally |

`_strip_unreliable_llm_fields()` nulls out: `ratio_decidendi`, `keywords`, `case_type`, `jurisdiction`, `bench_type`, `headnotes`, `outcome_summary`, `legal_principles_applied`, `issue_classification`, `fact_pattern_tags`. Keeps parquet-sourced fields intact.

---

## Fix 6: Re-ingestion of 379 Trial Cases

### Step 1: Delete corrupted data
- **PostgreSQL:** DELETE cases matching trial batch run (identify by `s3_source_path` year range + `created_at` timestamp)
- **Pinecone:** Delete vectors by `case_id` filter for those 379 cases
- **Neo4j:** DETACH DELETE case nodes + citation edges

### Step 2: Re-ingest with fixed pipeline
- Use fixed batch pipeline (custom_id mapping) or online pipeline
- All new validation layers active
- Smaller batches (~50 cases per batch job) instead of one mega-batch

### Step 3: Post-ingestion verification
- Run judge-text validation audit — expect >90% match rate
- Spot-check 10 known-bad cases (Brij Bhushan, Budhadev, Bachan Singh, Lingala Vijayakumar, Harshad Mehta, PK Biswas, Mr. X v. Hospital Z, Era Sezhiyan, Venus Castings)
- Run `verify_ingestion.py` for cross-store consistency
- Compare against audit's web-verified judge names

### Step 4: Lightweight validation pass on 2023-2026 cases (follow-up)
- Run `_validate_judges_against_text()` on existing online-ingested cases as read-only audit
- Report mismatch rate
- Only re-ingest if mismatch rate > 5%

---

## Additional Issues Found During Exploration

These were discovered during codebase exploration and are included in the fix scope:

| Issue | Severity | Location | Fix |
|-------|----------|----------|-----|
| Metadata truncation loses middle content | MEDIUM | `metadata.py` head+tail (30K+20K) | Not in scope — separate initiative |
| Contextual embedding no prefix validation | LOW | `contextual_embeddings.py` | Not in scope |
| Chunk overlap snapping silent failure | LOW | `chunker.py` | Not in scope |
| Newlines in cases_cited | LOW | Already handled by `backfill_ingestion_quality.py` | Existing fix sufficient |

---

## Effort Estimate

| Fix | Effort |
|-----|--------|
| 1. Batch custom_id mapping | 1 hour |
| 2. Validated judge merge | 2 hours |
| 3. LLM hallucination mitigation (3 layers) | 3 hours |
| 4. Pre-1964 boundary stripping | 1 hour |
| 5. Confidence gating | 1 hour |
| 6. Re-ingestion + verification | 1 hour |
| **Total** | **~9 hours** |

---

## Files Modified

| File | Changes |
|------|---------|
| `backend/scripts/batch_ingest_vertex.py` | Add custom_id to JSONL, parse by ID |
| `backend/app/core/ingestion/metadata.py` | New: `_validate_judges_against_text()`, `_validate_judge_tenure()`, `_validate_metadata_against_text()`, `_strip_unreliable_llm_fields()`. Modified: `merge_metadata()` signature + judge logic |
| `backend/app/core/legal/prompts.py` | Add negative grounding rules to system prompt |
| `backend/app/core/ingestion/pdf.py` | New: `_strip_leading_judgment_bleed()` |
| `backend/app/core/ingestion/pipeline.py` | Add confidence gating after merge |
| `backend/tests/unit/test_metadata.py` | Tests for all new validation functions |
| `backend/tests/unit/test_extractor.py` | Tests for boundary stripping |
