# Acts Cited Normalization — Full Audit & Fix Plan

**Date:** 2026-03-22
**Status:** READY FOR IMPLEMENTATION
**Severity:** HIGH — affects search quality, agent accuracy, statute coverage analysis
**Estimated scope:** 10 parallel subagents, ~15 files touched

---

## 1. ROOT CAUSE ANALYSIS

### 1.1 The Core Bug: `normalize_act_name()` exists but is NEVER called on final `acts_cited`

The function `normalize_act_name()` in `extractor.py:359-382` correctly maps full names → short codes (e.g., "Indian Penal Code" → "IPC"). **But it's never applied to the `acts_cited` list before storage.**

**Current flow (BROKEN):**
```
LLM → "Section 302 of Indian Penal Code, 1860"   ← stored as-is (WRONG)
Regex → ActReference(act_name="Indian Penal Code") → "Indian Penal Code, 1860" ← stored as-is (WRONG)
                                                      ↓
                                              PostgreSQL acts_cited[]
                                                      ↓
                                              Pinecone metadata.acts_cited
```

**What should happen:**
```
LLM → "Section 302 of Indian Penal Code, 1860"
                     ↓
           extract act name → "Indian Penal Code"
                     ↓
           normalize_act_name() → "IPC"          ← SHORT CODE
                     ↓
              PostgreSQL acts_cited = ["IPC"]
                     ↓
              Pinecone metadata.acts_cited = ["IPC"]
```

### 1.2 The LLM Prompt Asks for the WRONG Format

`prompts.py` Rule 5 says:
```
5. ACTS CITED: Use format "Section X of Act Name, Year".
```

This produces **section-level references** ("Section 302 of Indian Penal Code, 1860") instead of **act-level names** ("IPC"). The `acts_cited` field should store which **acts** are cited, not which **sections**. Section-level data already exists in `extract_acts_cited()` → `ActReference` objects.

### 1.3 Full Inventory of Data Quality Issues

| Issue | Example | Count | Severity |
|-------|---------|-------|----------|
| **Full names instead of short codes** | "Constitution of India, 1950" instead of "COI" | ~64 | CRITICAL |
| **Section-level refs stored as acts** | "Section 482 of Code of Criminal Procedure, 1973" | ~50+ | CRITICAL |
| **Garbage tokens** | "Unknown Act" (89), "Act" (29), "Code" (18), "Cr" (14), "M" (5), "s" (5) | ~160 | HIGH |
| **Newline-broken strings** | "Code of Criminal\nProcedure", "Evidence\nAct" | ~10 | HIGH |
| **State names as acts** | "Maharashtra" (5), "Rajasthan" (3), "Gujarat" (3) | ~25 | MEDIUM |
| **Vague references** | "said Act" (5), "that Act" (3), "same Act" (3), "1996 Act" (6) | ~20 | MEDIUM |
| **Duplicate act variants** | "IPC" + "Indian Penal Code" + "Penal Code, 1860" all in DB | ~100+ | HIGH |
| **Missing acts in statutes table** | Limitation Act, Prevention of Corruption Act, General Clauses Act | 10+ | MEDIUM |

### 1.4 Downstream Impact Assessment

| System | Impact | Severity |
|--------|--------|----------|
| **Pinecone search filtering** | `{"acts_cited": {"$in": ["IPC"]}}` will NOT match cases stored as "Indian Penal Code, 1860" | CRITICAL |
| **Case detail display** | Frontend shows messy, inconsistent act names to users | HIGH |
| **Statute gap analysis** | Can't accurately identify which acts are missing from statutes table because acts_cited uses different names | HIGH |
| **Agent research** | Statute lookup node can't cross-reference `acts_cited` with `statutes.act_short_name` | HIGH |
| **Analytics / dashboards** | Any future "most cited acts" dashboard will show fragmented data | MEDIUM |
| **Neo4j graph** | No ACT nodes in graph currently, but if added, would inherit bad data | LOW |

---

## 2. FIX STRATEGY — 10 SUBAGENTS

### Architecture Principle
**Normalize at write time, store canonical short codes, display full names on read.**

The canonical form is the `act_short_name` from the statutes table (e.g., "IPC", "CrPC", "COI"). Full display names are looked up from `statutes.act_name` when rendering.

---

### SUBAGENT 1: Normalize acts_cited in the ingestion pipeline
**Files:** `backend/app/core/ingestion/pipeline.py`, `backend/app/core/legal/extractor.py`
**Impact:** All future ingestions produce clean, normalized acts_cited

#### Tasks:
- [ ] 1.1 — Create `normalize_acts_cited_list(raw_acts: list[str]) -> list[str]` in `extractor.py`
  - Parses "Section X of Act Name, Year" → extracts just "Act Name"
  - Strips section references, article references, year suffixes
  - Calls `normalize_act_name()` on each extracted act name
  - Filters garbage tokens (length < 4, "Unknown Act", state names, "said Act", etc.)
  - Deduplicates (since "Indian Penal Code" and "IPC" both → "IPC")
  - Returns sorted list of canonical short codes
- [ ] 1.2 — Wire `normalize_acts_cited_list()` into `pipeline.py` AFTER regex supplementation and BEFORE storage
  - Insert call between lines 233-236 (after regex merge, before statute enrichment)
  - Update provenance to include "+normalized"
- [ ] 1.3 — Update `_upsert_vectors()` to ensure Pinecone metadata uses the same normalized short codes
- [ ] 1.4 — Add unit tests for `normalize_acts_cited_list()` covering all edge cases:
  - Full name → short code ("Indian Penal Code, 1860" → "IPC")
  - Section-level ref → act only ("Section 302 of Indian Penal Code, 1860" → "IPC")
  - Article ref → act only ("Article 21 of Constitution of India" → "COI")
  - Garbage filtering ("Unknown Act" → filtered, "M" → filtered, "Rajasthan" → filtered)
  - Newline-broken names ("Code of Criminal\nProcedure" → "CrPC")
  - Already-normalized ("IPC" → "IPC")
  - Read-with format ("Section 302 r/w Section 34 IPC" → "IPC")
  - Unknown acts pass through as title-cased full names

---

### SUBAGENT 2: Fix LLM prompt to request short codes
**Files:** `backend/app/core/legal/prompts.py`
**Impact:** LLM output is cleaner from the start, reducing normalization burden

#### Tasks:
- [ ] 2.1 — Rewrite Rule 5 in `METADATA_EXTRACTION_SYSTEM` prompt:
  ```
  OLD: "5. ACTS CITED: Use format 'Section X of Act Name, Year'."
  NEW: "5. ACTS CITED: List ONLY the act names (not section numbers).
        Use standard short codes where possible: IPC, CrPC, CPC, COI, IEA,
        BNS, BNSS, BSA, IBC, PMLA, NDPS Act, NI Act, UAPA, IT Act, etc.
        For acts without a standard code, use the full name with year
        (e.g., 'Limitation Act, 1963'). Do NOT include section numbers —
        those are extracted separately. Do NOT include generic references
        like 'the Act', 'said Act', or state names."
  ```
- [ ] 2.2 — Update `METADATA_OUTPUT_SCHEMA` description for acts_cited:
  ```
  OLD: "List of statutes/acts cited with section numbers"
  NEW: "List of act short codes cited (e.g., ['IPC', 'CrPC', 'COI', 'Limitation Act, 1963']).
        Use standard abbreviations. Do NOT include section numbers."
  ```
- [ ] 2.3 — Update all few-shot examples in prompts.py:
  ```
  OLD: "acts_cited": ["Section 302 of Indian Penal Code, 1860", ...]
  NEW: "acts_cited": ["IPC", "IEA", "CrPC"]
  ```
  Update Example 1 (Criminal Appeal), Example 2 (Civil Appeal), Example 3 (Constitutional PIL)
- [ ] 2.4 — Add a new few-shot example showing BNS/BNSS/BSA short codes for post-2024 cases
- [ ] 2.5 — Run the existing prompt unit tests to ensure no regressions

---

### SUBAGENT 3: Expand `_SHORT_ACT_NAMES` with missing acts
**Files:** `backend/app/core/legal/extractor.py`
**Impact:** Regex extraction and normalization can handle more acts

#### Tasks:
- [ ] 3.1 — Add these missing high-frequency acts to `_SHORT_ACT_NAMES`:
  | Short Code | Full Name |
  |------------|-----------|
  | `LA` | Limitation Act |
  | `PCA` | Prevention of Corruption Act |
  | `GCA` | General Clauses Act |
  | `LARR` | Right to Fair Compensation and Transparency in Land Acquisition, Rehabilitation and Resettlement Act |
  | `LAA` | Land Acquisition Act |
  | `ARMS ACT` | Arms Act |
  | `MVA` | Motor Vehicles Act |
  | `CPA` | Consumer Protection Act |
  | `DPA` | Dowry Prohibition Act |
  | `NHA` | National Highways Act |
  | `FA` | Foreigners Act |
  | `POCSO ACT` | Protection of Children from Sexual Offences Act |
  | `LSA` | Legal Services Authorities Act |
  | `MACT` | Motor Accident Claims Tribunal Act |
  | `TADA` | Terrorist and Disruptive Activities (Prevention) Act |
  | `POTA` | Prevention of Terrorism Act |
  | `RPA` | Representation of the People Act |
  | `GA` | Guardians and Wards Act |
  | `IWDP` | Indian Wireless Telegraphy Act |
  | `MACP` | Mines and Minerals (Development and Regulation) Act |
- [ ] 3.2 — Add common variations/aliases for these acts:
  - "Limitation Act" / "Limitation Act, 1963" → `LA`
  - "PC Act" / "Prevention of Corruption Act" / "Prevention of Corruption Act, 1988" → `PCA`
  - "General Clauses Act" / "General Clauses Act, 1897" → `GCA`
  - "Consumer Protection Act" / "Consumer Act" → `CPA`
  - "Motor Vehicles Act" / "MV Act" → `MVA` (MV ACT already exists, add MVA)
  - "Arms Act" / "Arms Act, 1959" → `ARMS ACT`
  - "Land Acquisition Act" / "Land Acquisition Act, 1894" / "LA Act" → `LAA`
- [ ] 3.3 — Rebuild `_FULL_TO_SHORT` reverse mapping (automatic, just verify)
- [ ] 3.4 — Update `_SHORT_ACT_ALTERNATION` regex (automatic from `_SHORT_ACT_NAMES` keys)
- [ ] 3.5 — Add unit tests for new act name normalization cases

---

### SUBAGENT 4: Build garbage filter for acts_cited
**Files:** `backend/app/core/ingestion/metadata.py`
**Impact:** Prevents junk from ever entering the database

#### Tasks:
- [ ] 4.1 — Create `_ACTS_CITED_BLOCKLIST` set in `metadata.py`:
  ```python
  _ACTS_CITED_BLOCKLIST = frozenset({
      "unknown act", "act", "code", "the act", "said act", "that act",
      "same act", "this act", "the code", "india", "protocols",
      # Single letters/fragments
      "cr", "m", "s", "p", "r",
      # State names (not acts)
      "maharashtra", "rajasthan", "gujarat", "uttar pradesh", "karnataka",
      "punjab", "haryana", "bihar", "kerala", "tamil nadu", "andhra pradesh",
      "telangana", "madhya pradesh", "west bengal", "odisha", "assam",
      "nct of delhi", "delhi", "goa", "jharkhand", "chhattisgarh",
      "uttarakhand", "himachal pradesh", "jammu and kashmir",
      # Year-only entries
      "2013", "2017", "2020", "2022",
  })
  ```
- [ ] 4.2 — Create `_is_valid_act_name(name: str) -> bool` function:
  - Returns False if lowercase name in blocklist
  - Returns False if length < 4
  - Returns False if it looks like a section reference ("Section \d+")
  - Returns False if it contains newlines
  - Returns False if it matches a year-only pattern (r"^\d{4}$")
  - Returns False if it matches "Order.*Rule.*" pattern (these are CPC procedural refs, not act names)
- [ ] 4.3 — Wire `_is_valid_act_name()` into `validate_with_regex()` list validation
  - After dedup/trim, filter each `acts_cited` entry through `_is_valid_act_name()`
- [ ] 4.4 — Add unit tests for garbage filtering

---

### SUBAGENT 5: Write migration script to fix existing 112 cases
**Files:** NEW `backend/scripts/normalize_acts_cited.py`
**Impact:** Fixes all existing data in PostgreSQL

#### Tasks:
- [ ] 5.1 — Create `normalize_acts_cited.py` script:
  - Connects to PostgreSQL
  - For each case: reads `acts_cited`, applies `normalize_acts_cited_list()`, writes back
  - Logs before/after for audit trail
  - Dry-run mode by default (`--commit` flag to actually write)
  - Generates a summary report: acts normalized, acts filtered, acts unchanged
- [ ] 5.2 — Handle edge cases:
  - Newline-broken names: join with space, then normalize
  - "1996 Act" → try to infer (Arbitration and Conciliation Act, 1996 → "ACA")
  - Section-level references → extract act name only
  - Already-normalized short codes → keep as-is
- [ ] 5.3 — Add a Pinecone re-sync step:
  - After PostgreSQL update, re-upsert Pinecone metadata for affected cases
  - Uses existing `_upsert_vectors()` or a lightweight metadata-only update
- [ ] 5.4 — Add dry-run test that verifies the script doesn't error on real data

---

### SUBAGENT 6: Fix Pinecone search filter compatibility
**Files:** `backend/app/core/search/hybrid.py`
**Impact:** Search filtering actually works after normalization

#### Tasks:
- [ ] 6.1 — Ensure `SearchFilters.act` is normalized before use:
  - In `hybrid_search()`, call `normalize_act_name(filters.act)` before passing to Pinecone
  - This ensures user queries like "Indian Penal Code" are normalized to "IPC" to match stored data
- [ ] 6.2 — Update any frontend/API layer that constructs act filters:
  - Check `backend/app/api/routes/cases.py` and search endpoints
  - Normalize the `act` query parameter
- [ ] 6.3 — Add integration test: search with act="Indian Penal Code" should find cases stored with acts_cited=["IPC"]
- [ ] 6.4 — Verify agent worker nodes pass normalized act filters through routing

---

### SUBAGENT 7: Add display name lookup (short code → full name)
**Files:** `backend/app/core/legal/extractor.py`, `backend/app/api/routes/cases.py`
**Impact:** Frontend displays human-readable act names despite storing short codes

#### Tasks:
- [ ] 7.1 — Create `get_act_display_name(short_code: str) -> str` in `extractor.py`:
  - Looks up `_SHORT_ACT_NAMES[short_code]` → returns full name
  - Falls back to the short_code itself if not found
  - Optionally appends year from a `_ACT_YEARS` dict
- [ ] 7.2 — Create `_ACT_YEARS` dict for display purposes:
  ```python
  _ACT_YEARS: dict[str, int] = {
      "IPC": 1860, "CrPC": 1973, "CPC": 1908, "COI": 1950,
      "IEA": 1872, "BNS": 2023, "BNSS": 2023, "BSA": 2023,
      "ICA": 1872, "TPA": 1882, "ACA": 1996, "IBC": 2016,
      # ... etc
  }
  ```
- [ ] 7.3 — Update GET `/cases/{case_id}` to return both:
  ```json
  {
    "acts_cited": ["IPC", "CrPC", "COI"],
    "acts_cited_display": ["Indian Penal Code, 1860", "Code of Criminal Procedure, 1973", "Constitution of India, 1950"]
  }
  ```
  Or alternatively, return objects: `[{"code": "IPC", "name": "Indian Penal Code, 1860"}, ...]`
- [ ] 7.4 — Add unit tests for display name lookup

---

### SUBAGENT 8: Ingest missing statutes
**Files:** `backend/scripts/ingest_statutes.py`, statute source data
**Impact:** Statute lookup works for more acts, closes coverage gaps

#### Tasks:
- [ ] 8.1 — Add these acts to `ingest_statutes.py` source list:
  | Priority | Act | Year | Why |
  |----------|-----|------|-----|
  | P0 | Limitation Act | 1963 | Cited in virtually all civil litigation |
  | P0 | Prevention of Corruption Act | 1988 | Staple of criminal law |
  | P0 | General Clauses Act | 1897 | Interpretive foundation for ALL statutes |
  | P1 | Right to Fair Compensation (Land Acquisition) Act | 2013 | Major land law |
  | P1 | Land Acquisition Act | 1894 | Still cited for pre-2013 cases |
  | P1 | Motor Vehicles Act | 1988 | Accident/insurance cases |
  | P1 | Consumer Protection Act | 2019 | Consumer disputes (replaces 1986) |
  | P2 | Arms Act | 1959 | Criminal cases |
  | P2 | Dowry Prohibition Act | 1961 | Matrimonial cases |
  | P2 | Representation of the People Act | 1951 | Election disputes |
  | P2 | Legal Services Authorities Act | 1987 | Access to justice |
  | P2 | Specific Relief Act | 1963 | May already be partially ingested (check "SRA") |
- [ ] 8.2 — Source statute text (India Code / legislative.gov.in HTML scraping or manual collection)
- [ ] 8.3 — Add replacement mappings if applicable (e.g., Consumer Protection Act 1986 → 2019)
- [ ] 8.4 — Run ingestion and verify section counts match expected
- [ ] 8.5 — Verify statutes appear in `act_short_name` index and FTS index

---

### SUBAGENT 9: Add `enrich_statute_cross_references()` normalization
**Files:** `backend/app/core/legal/statute_enrichment.py` (or wherever this function lives)
**Impact:** Statute enrichment step works with normalized short codes

#### Tasks:
- [ ] 9.1 — Locate `enrich_statute_cross_references()` and audit its logic
  - Does it expect full act names or short codes?
  - Does it add IPC→BNS cross-references correctly?
- [ ] 9.2 — Update to work with short codes:
  - Input: `["IPC", "CrPC"]`
  - Output: `["IPC", "CrPC", "BNS", "BNSS"]` (adds new-code equivalents)
  - Must NOT re-expand short codes to full names
- [ ] 9.3 — Ensure enrichment doesn't re-introduce full names or garbage
- [ ] 9.4 — Add unit tests for enrichment with short-code inputs
- [ ] 9.5 — Verify the IPC_TO_BNS_MAP, CRPC_TO_BNSS_MAP, EVIDENCE_TO_BSA_MAP in `constants.py` are keyed correctly for bidirectional lookup

---

### SUBAGENT 10: Comprehensive integration tests + re-audit
**Files:** NEW `backend/tests/unit/test_acts_cited_normalization.py`, existing test files
**Impact:** Ensures all fixes work end-to-end and catches regressions

#### Tasks:
- [ ] 10.1 — Create `test_acts_cited_normalization.py` with test cases:
  - **test_full_pipeline_normalization**: Mock LLM returns messy acts_cited → pipeline produces clean short codes
  - **test_regex_supplementation_normalized**: Regex extraction → normalized short codes
  - **test_garbage_filtered**: Garbage tokens never reach database
  - **test_pinecone_filter_matches**: Search filter "Indian Penal Code" normalized to "IPC" matches stored data
  - **test_display_name_roundtrip**: IPC → "Indian Penal Code, 1860" → display
  - **test_statute_enrichment_with_short_codes**: IPC enriched to include BNS
  - **test_newline_broken_names**: "Code of Criminal\nProcedure" → "CrPC"
  - **test_section_level_refs_stripped**: "Section 302 of IPC" → "IPC" (not the full string)
- [ ] 10.2 — Run migration script in dry-run mode and verify output
- [ ] 10.3 — Re-run the original audit query (from this conversation) and verify:
  - Zero "MISSING" entries for known acts (all mapped to short codes)
  - Zero garbage tokens
  - Zero section-level references
  - All 59 statutes table acts match their short codes
- [ ] 10.4 — Update existing tests that may assert old format:
  - `test_extractor.py` — may test for "Indian Penal Code" instead of "IPC"
  - `test_ingestion_pipeline.py` — may assert old acts_cited format
  - `test_metadata_llm_retry.py` — may have old prompt examples
- [ ] 10.5 — Create a SQL query as a "health check" that can be run periodically:
  ```sql
  -- Acts cited health check: should return 0 rows if normalization is working
  SELECT act, COUNT(*)
  FROM cases, unnest(acts_cited) AS act
  WHERE length(act) < 4
     OR act LIKE 'Section %'
     OR act LIKE 'Article %'
     OR act IN ('Unknown Act', 'Act', 'Code', 'said Act', 'that Act')
     OR act ~ E'\\n'
  GROUP BY act ORDER BY count DESC;
  ```

---

## 3. EXECUTION ORDER & DEPENDENCIES

```
Phase 1 (parallel — no dependencies):
  ├── Subagent 1: Pipeline normalization function
  ├── Subagent 2: Fix LLM prompts
  ├── Subagent 3: Expand _SHORT_ACT_NAMES
  └── Subagent 4: Build garbage filter

Phase 2 (after Phase 1):
  ├── Subagent 5: Migration script (needs normalization function from SA1)
  ├── Subagent 6: Search filter fix (needs normalization from SA1)
  ├── Subagent 7: Display name lookup (needs expanded names from SA3)
  └── Subagent 9: Statute enrichment (needs short codes from SA1)

Phase 3 (after Phase 2):
  ├── Subagent 8: Ingest missing statutes (needs expanded names from SA3)
  └── Subagent 10: Integration tests (needs everything)
```

---

## 4. LARGER IMPACT OPPORTUNITIES

### 4.1 Neo4j ACT Nodes (Future)
Once `acts_cited` is normalized, we can create `(:Act {short_name: "IPC"})` nodes in Neo4j with `(:Case)-[:CITES_ACT]->(:Act)` edges. This enables:
- "Find all cases citing both IPC and NDPS Act"
- "Which acts are most commonly cited together?"
- Citation graph traversal across acts

### 4.2 Act-Level Analytics Dashboard
Normalized data enables:
- Most-cited acts ranking
- Acts cited by year (trend analysis)
- Acts cited by court/bench type
- Act citation co-occurrence matrix

### 4.3 Smart Statute Suggestions
When a user searches for "murder charge", the system can:
1. Identify relevant acts (IPC → Section 302, BNS → Section 103)
2. Show statute text inline
3. Link to related cases

### 4.4 Cross-Reference Completeness Score
For each case, compute: "What % of acts_cited have matching statutes in our DB?"
This becomes a data quality metric and prioritizes statute ingestion.

### 4.5 Agent Research Quality
The research agent's `statute_lookup_node` can automatically look up every act cited in a case, providing much richer legal context. Currently it can't because acts_cited doesn't match statutes.act_short_name.

### 4.6 Pinecone Filter Reliability
After normalization, act-based search filters will actually work. Currently, searching for cases citing "IPC" misses ~80% of results because they're stored as "Indian Penal Code, 1860" or "Section 302 of Indian Penal Code, 1860".

---

## 5. RISK ASSESSMENT

| Risk | Mitigation |
|------|------------|
| Migration script corrupts data | Dry-run mode default, before/after logging, backup first |
| Prompt change causes LLM regression | Few-shot examples anchor behavior, validation catches garbage |
| Short codes ambiguous (IT = Income Tax or Information Technology?) | Use "IT Act" and "ITA" to disambiguate (already in _SHORT_ACT_NAMES) |
| Unknown acts lose information | Unknown acts pass through as title-cased full names, not discarded |
| Pinecone metadata out of sync | Migration script includes Pinecone re-sync step |
| Existing tests break | Subagent 10 explicitly updates affected tests |

---

## 6. SUCCESS CRITERIA

After all 10 subagents complete:

1. **Zero garbage** in `acts_cited` — no "Unknown Act", single letters, state names, newlines
2. **100% short-code normalization** — every known act stored as its canonical short code
3. **Pinecone filters work** — searching by act name finds all relevant cases
4. **Display names available** — API returns human-readable names alongside codes
5. **12+ new acts** in statutes table covering top gaps
6. **All existing tests pass** + new normalization tests
7. **Health check query returns 0 rows** — no data quality issues remain
