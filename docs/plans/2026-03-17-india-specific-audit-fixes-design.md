# India-Specific Audit Fixes Design (U1–U4)

**Date:** 2026-03-17
**Status:** Approved
**Scope:** Fix 4 India-specific risks identified in codebase audit

---

## U1: Hindi FTS Support

### Problem
All `to_tsvector` calls hardcode `'english'`. Hindi/Devanagari text in `full_text` gets zero FTS recall. The `cases.language` column exists but is unused by triggers or queries.

### Approach: Hybrid (skip FTS for Hindi + forward-looking `'simple'` tsvector)

**Immediate (skip FTS for Hindi queries):**
- `fulltext.py`: Add `language` parameter to `search_fulltext()`. When `language == "hi"`, return empty list immediately.
- `hybrid.py`: Accept `language` param in `hybrid_search()`. When Hindi detected:
  - Skip FTS task in `asyncio.gather()` (don't fire it)
  - Force `vector_heavy` strategy (vector=2.0, FTS=0.0)
  - Reranker still runs on vector results
- `search.py`: Pass detected language into `hybrid_search()`.

**Forward-looking (migration 015):**
- Add `hindi_searchable_text TSVECTOR` column to `cases` table
- Trigger: `to_tsvector('simple', COALESCE(NEW.full_text, ''))` — only fires when `NEW.language = 'hindi'`
- GIN index on `hindi_searchable_text`
- No data populates it yet — infrastructure for when Hindi HC judgments are ingested

### Why not pg_bigm?
Requires extension installation, may not be available on managed PostgreSQL (Cloud SQL). `'simple'` dictionary tokenizes on whitespace — sufficient for Devanagari since PostgreSQL has no Hindi stemmer anyway. Semantic recall comes from Gemini embeddings (multilingual).

---

## U2: HC Citation Format Expansion

### Problem
`HC_REPORTER_PATTERN` covers only 13 reporters. Missing: LNIND, CDJ, BomLR, CalWN, and no catch-all for unknown formats.

### Approach: Expand whitelist + guarded catch-all

**Expand HC_REPORTER_PATTERN alternation:**
```
Current:  ILR|MLJ|KLT|BLR|GLR|ALJ|DLT|ALD|CLT|PLR|DRJ|KHC|RLW
Adding:   LNIND|CDJ|BomLR|CalWN|WLC|JLJ|AIJEL|CriLJ|FLR|GujLR|MPLJ|OLR|WLR
```

**Add GENERIC_REPORTER_PATTERN (catch-all):**
```python
GENERIC_REPORTER_PATTERN = re.compile(
    r"(?:(\d{4})\s+|\((\d{4})\)\s+(?:\d+\s+)?)"
    r"([A-Z][A-Za-z]{1,5})"
    r"\s+(\d+)"
)
```
- Runs LAST in `extract_citations()`, after all specific patterns
- Skips spans already matched by specific patterns (track via `seen_spans` set of `(start, end)` tuples)
- Tags with `reporter="Unknown"` for review
- Capped at 10 catch-all matches per document to limit noise

**Files changed:**
- `backend/app/core/legal/extractor.py` — pattern + extraction logic
- `backend/tests/unit/test_extractor.py` — new test cases

---

## U3: BNS/BNSS/BSA Ingestion-Time Dual-Tagging

### Problem
Query-time expansion (`expand_statute_references()`) works for FTS, but Pinecone metadata `acts_cited` only contains the original statute references. Searching with Pinecone filter `act=BNS` misses cases that only cite IPC.

### Approach: Enrich `acts_cited` at ingestion time

**New module: `backend/app/core/legal/statute_enrichment.py`**

```python
def enrich_statute_cross_references(acts_cited: list[str]) -> list[str]:
    """Add cross-references for old↔new criminal statutes.

    For each IPC/CrPC/IEA reference, adds BNS/BNSS/BSA equivalent.
    For each BNS/BNSS/BSA reference, adds IPC/CrPC/IEA equivalent.
    Uses IPC_TO_BNS_MAP, CRPC_TO_BNSS_MAP, EVIDENCE_TO_BSA_MAP from constants.py.
    """
```

**Logic:**
1. Parse each `acts_cited` entry for act name + section number
2. Look up in forward map (IPC→BNS) or reverse map (BNS→IPC)
3. Add mapped entry to the list (e.g., "Indian Penal Code, Section 302" → also add "Bharatiya Nyaya Sanhita, Section 103")
4. Deduplicate and sort

**Pipeline insertion** in `pipeline.py` after line 182 (after regex acts supplementation):
```python
from app.core.legal.statute_enrichment import enrich_statute_cross_references
metadata.acts_cited = enrich_statute_cross_references(metadata.acts_cited)
```

**Effect:** Both old and new statute references stored in PostgreSQL `acts_cited` (GIN) and Pinecone metadata `acts_cited` (filterable).

---

## U4: PII Anonymization for Sensitive Cases

### Problem
Zero anonymization of party names or PII in ingested judgment text. POCSO/sexual assault cases may contain victim/minor identifying info. SC anonymization guidelines require masking.

### Approach: Detection + PII masking at ingestion (new ingestions only)

**New module: `backend/app/core/ingestion/anonymizer.py`**

### `detect_sensitive_case(full_text, metadata) -> bool`

Returns `True` if ANY of:
- `acts_cited` contains "Protection of Children from Sexual Offences Act" or "POCSO"
- `acts_cited` contains IPC sections 375, 376, 354, 354A-D, 363, 366, 366A, 366B, 370, 372, 373, 509 (or BNS equivalents 63-70, 74-79)
- Text contains keywords: "prosecutrix", "minor victim", "POCSO", "sexual assault on minor", "identity of the victim", "name of the victim cannot be disclosed"
- `case_type == "Criminal"` AND certain sensitive statutes are cited

### `anonymize_text(full_text) -> tuple[str, bool]`

Masks Indian PII patterns in judgment body text:
- Aadhaar numbers (12 digits) → `[AADHAAR REDACTED]`
- PAN numbers (AAAAA9999A) → `[PAN REDACTED]`
- Indian mobile numbers (+91/0 prefix + 10 digits) → `[PHONE REDACTED]`

Reuses patterns from `logging_config.py` `_PII_PATTERNS`. Does NOT attempt party name replacement (too error-prone for regex).

Returns `(cleaned_text, was_modified)`.

### CaseMetadata changes

Add to `CaseMetadata` dataclass in `metadata.py`:
```python
is_anonymized: bool = False
anonymization_flags: list[str] = field(default_factory=list)
```

Flags for audit trail: `"pocso_detected"`, `"sensitive_statutes"`, `"aadhaar_masked"`, `"pan_masked"`, `"phone_masked"`.

### Pipeline insertion

In `ingest_judgment()`:

**After line 103** (text extraction, before dedup hash):
```python
full_text, pii_masked = anonymize_text(full_text)
```

**After line 182** (after metadata enrichment):
```python
if detect_sensitive_case(full_text, metadata):
    metadata.is_anonymized = True
    metadata.anonymization_flags.append("sensitive_case_detected")
if pii_masked:
    metadata.anonymization_flags.append("pii_masked")
```

### Migration 015

Add to `cases` table:
- `is_anonymized BOOLEAN DEFAULT FALSE`
- `anonymization_flags TEXT[] DEFAULT '{}'`
- `hindi_searchable_text TSVECTOR` (from U1)
- GIN index on `hindi_searchable_text`
- Trigger for `hindi_searchable_text` (conditional on `language = 'hindi'`)

---

## Files Changed Summary

| File | Changes |
|------|---------|
| `backend/app/core/search/fulltext.py` | Add `language` param, skip for Hindi |
| `backend/app/core/search/hybrid.py` | Accept `language`, skip FTS for Hindi, force vector_heavy |
| `backend/app/api/routes/search.py` | Pass language to `hybrid_search()` |
| `backend/app/core/legal/extractor.py` | Expand HC_REPORTER_PATTERN, add GENERIC_REPORTER_PATTERN |
| `backend/app/core/legal/statute_enrichment.py` | **NEW** — `enrich_statute_cross_references()` |
| `backend/app/core/ingestion/anonymizer.py` | **NEW** — `detect_sensitive_case()`, `anonymize_text()` |
| `backend/app/core/ingestion/pipeline.py` | Insert anonymization + statute enrichment calls |
| `backend/app/core/ingestion/metadata.py` | Add `is_anonymized`, `anonymization_flags` to CaseMetadata |
| `backend/migrations/versions/015_india_audit_fixes.py` | **NEW** — hindi tsvector, anonymization columns |
| `backend/tests/unit/test_extractor.py` | New citation tests |
| `backend/tests/unit/test_statute_enrichment.py` | **NEW** — enrichment tests |
| `backend/tests/unit/test_anonymizer.py` | **NEW** — detection + masking tests |
| `backend/tests/unit/test_hindi_fts_skip.py` | **NEW** — Hindi FTS skip tests |
