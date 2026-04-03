# Phase 3: RAG Pipeline Deep Dive

**Author**: Claude Opus 4.6 (automated codebase analysis)
**Date**: 2026-04-03
**Scope**: Complete trace of the Retrieval-Augmented Generation pipeline from PDF ingestion to agent-synthesized legal memos.

---

## Table of Contents

1. [Ingestion Pipeline](#1-ingestion-pipeline)
2. [PDF Extraction](#2-pdf-extraction)
3. [Chunking Strategy](#3-chunking-strategy)
4. [Metadata Extraction](#4-metadata-extraction)
5. [Embedding Configuration](#5-embedding-configuration)
6. [Vector Storage Schema](#6-vector-storage-schema)
7. [Retrieval Pipeline](#7-retrieval-pipeline)
8. [Search Architecture](#8-search-architecture)
9. [Knowledge Graph Schema](#9-knowledge-graph-schema)
10. [Agent Architecture](#10-agent-architecture)
11. [Prompt Templates](#11-prompt-templates)
12. [Legal Domain Logic](#12-legal-domain-logic)
13. [Batch Ingestion](#13-batch-ingestion)

---

## 1. Ingestion Pipeline

**File**: `backend/app/core/ingestion/pipeline.py`

The `ingest_judgment()` function is the master orchestrator. It accepts a PDF path, Parquet metadata, and injected dependencies (db, llm, embedder, vector_store, graph_store, storage). It returns the case UUID on success or None on failure.

### Step-by-Step Flow

```
PDF file on disk
    |
    v
1. extract_and_score(pdf_path)           -- pdf.py
    |  Returns TextQuality(text, char_count, tier, ocr_used, page_map)
    |  Hard fail if <50 chars
    v
1a. anonymize_text(full_text)            -- anonymizer.py
    |  Masks Aadhaar (12-digit), PAN (AAAPA9999A), phone (+91...)
    |  Returns (cleaned_text, was_modified)
    v
1b. _compute_text_hash(full_text)        -- SHA-256 of whitespace-normalized text
    |  SELECT id FROM cases WHERE text_hash = :hash
    |  If match found with chunk_count > 0: SKIP (duplicate)
    |  If match found with chunk_count = 0: RE-INGEST (broken prior run)
    v
2. PARALLEL:
   2a. extract_metadata_llm(full_text, llm) -- metadata.py (with 3x tenacity retry)
   2b. storage.store(pdf_path, dest)         -- GCS upload
    |
    v
2c. merge_metadata(parquet_validated, llm_meta, full_text)
    |  Parquet wins: title, citation, court, year, decision_date, petitioner, respondent
    |  LLM wins: ratio_decidendi, acts_cited, cases_cited, keywords, bench_type, jurisdiction
    |  Judge: LLM-extracted -> validated against judgment header text -> tenure check -> canonical name normalization
    v
3. VALIDATE METADATA
   3a. validate_with_regex(metadata)
       - Year range [1800, current_year]
       - ISO 8601 decision_date, no future dates
       - Normalize court name via courts.py
       - bench_type in {single, division, full, constitutional}
       - jurisdiction in {civil, criminal, constitutional, tax, labor, ...}
       - disposal_nature in {Allowed, Dismissed, Partly Allowed, ...}
       - List dedup, cap counts (judges: 20, acts: 50, cases: 100, keywords: 15)
       - String length caps (title: 500, ratio: 3000, ...)
       - V2 field validation (judicial_tone, filing_date, hearing_count, ...)
   3b. validate_cross_fields(metadata)
       - Year must match decision_date year
       - bench_type vs judge count (single shouldn't have 3+ judges)
       - coram_size -> bench_type inference
       - author_judge must appear in judge list
       - petitioner != respondent
       - case_type vs case_number consistency
       - Self-citation removal from cases_cited
       - is_reportable inference from SCR citation
   3c. cross_validate_propositions(metadata)
       - If ratio empty but propositions exist: synthesize ratio from top 3
       - If propositions empty but ratio exists: create single proposition
   3d. _validate_metadata_against_text(metadata, full_text)
       - Keywords: each must have non-stopword token in full_text
       - Ratio: must share >=3 non-stopword tokens with text
   3e. Confidence gating:
       - compute_extraction_confidence(metadata) -- weighted score 0.0-1.0
       - < 0.4: strip LLM fields (ratio, keywords, case_type, ...)
       - < 0.6: flag for review
    v
3f. Regex supplementation:
   - extract_acts_cited(full_text) -> union with LLM acts
   - normalize_acts_cited_list() -> canonical short codes
   - enrich_statute_cross_references() -> old<->new law bidirectional
   - extract_citations(full_text) -> union with LLM cases_cited
   - classify_case_citations() -> named citations vs bare refs (GAN discriminator)
   - detect_sensitive_case() -> POCSO / sexual offence flags
    v
5. _insert_case(db, ...) -- INSERT INTO cases ... ON CONFLICT (citation) DO UPDATE
   |  Upserts ~60+ columns into PostgreSQL
   |  searchable_text computed by BEFORE INSERT trigger (weighted tsvector)
   |  Returns (case_id, already_ingested)
   |  If already_ingested: SKIP remaining steps
    v
6. SECTION DETECTION + CHUNKING
   detect_judgment_sections(full_text) -> list[Section]
   chunk_judgment(full_text, sections, case_id) -> list[Chunk]
   _persist_sections() -> case_sections table
   _persist_statute_interpretations() -> case_statute_interpretations table
   _extract_citation_equivalents() -> case_citation_equivalents table
    v
6c. CONTEXTUAL EMBEDDINGS (optional, requires fast_llm)
   batch_contextualize_chunks() -> each chunk gets a 1-2 sentence context prefix
   Controlled by SKIP_CONTEXTUAL_EMBEDDINGS=1 env var
    v
7. GENERATE EMBEDDINGS
   _embed_chunks(chunks, embedder) -> list[list[float]]
   Batch size: 100 (configurable via _EMBED_BATCH_SIZE)
   Dimension validation: 1536 (configurable via EMBEDDING_DIMENSION)
   3 retries with exponential backoff (4s, 8s, 16s)
    v
8. UPSERT TO VECTOR STORE (Pinecone)
   8a. _upsert_vectors() -> chunk vectors (vector_type="chunk")
   8b. _upsert_proposition_vectors() -> proposition, ratio, headnote vectors
   8c. Stale vector cleanup: delete_by_metadata({case_id}, exclude_ids=new_vector_ids)
    v
8b. RAPTOR SECTION SUMMARIES (optional, requires fast_llm)
   generate_section_summaries() -> 2-4 sentence per-section summaries
   build_pinecone_summary_vectors() -> vector_type="summary"
   Controlled by SKIP_RAPTOR_SUMMARIES=1 env var
    v
9. BUILD CITATION GRAPH (Neo4j, non-critical)
   _build_citation_graph(case_id, metadata, full_text, graph_store)
   - MERGE Case node with properties
   - Placeholder resolution: promote ref_ nodes if citation matches
   - Extract citations from full_text -> create CITES edges
   - Treatment detection per citation context window (500 chars each side)
   - Batch UNWIND for creating placeholder nodes + edges
   - Update cited_by_count on target nodes
   - On failure: record_graph_failure() for async retry queue
    v
COMMIT + set ingestion_status = "complete" | "needs_review" | "failed"
```

### Error Handling

- **DB uncommitted + vectors upserted**: Rolls back DB, then cleans orphan vectors from Pinecone.
- **DB committed + later failure**: Updates `ingestion_status = 'failed'`.
- **All failures**: `_record_ingestion_failure()` writes to `audit_logs` table using a fresh session (in case pipeline session is broken).
- **Graph build failure**: Queued to `graph_build_queue` table for async retry (max 3 retries).

---

## 2. PDF Extraction

**File**: `backend/app/core/ingestion/pdf.py`

### Extraction Pipeline

```
extract_and_score(file_path)
    |
    v
extract_pdf_text(file_path) -> asyncio.to_thread(_extract_pdf_text_sync)
    |
    |  For each page (pdfplumber):
    |    1. page.extract_text()
    |    2. If < 30 chars: OCR fallback (_ocr_single_page)
    |    3. If alpha_ratio < 0.5: OCR fallback (garbled text check)
    |    4. OCR: pdf2image + pytesseract (DPI 300, --oem 3 --psm 6 -l eng+hin)
    |
    v
_remove_repeated_headers_footers_pages(page_texts)
    |  Lines appearing on 3+ pages removed (keep first occurrence)
    |  Common boilerplate patterns also removed (REPORTABLE, IN THE SUPREME COURT, etc.)
    v
_smart_page_join(page_texts)
    |  Hyphenated word rejoining: "juris-\n" + "diction" -> "jurisdiction"
    |  Mid-sentence page break: no terminal punct + next starts lowercase -> space join
    |  Otherwise: double newline join
    v
clean_extracted_text(text)
    |  1. Unicode NFKC normalization
    |  2. Zero-width char removal (U+200B, BOM, soft hyphen) — preserves ZWNJ/ZWJ for Devanagari
    |  3. Control character removal (except \n, \t, \r)
    |  4. Repeated header/footer dedup (again, post-join)
    |  5. Standalone page number removal
    |  6. Editorial metadata removal (headnote bylines, reporter page markers)
    |  7. Em/en dash normalization between words
    |  8. Excess newline collapse (3+ -> 2)
    |  9. Trailing whitespace strip
    v
_build_page_map(page_texts, joined_text)
    |  Maps page_number -> (char_start, char_end) in joined text
    |  Used later for chunk -> page number mapping
    v
_strip_leading_judgment_bleed(text)
    |  Detects text from a previous judgment at the start (pre-1964 PDFs)
    |  Strips if earliest case header marker appears after 200+ chars
    v
score_text_quality(text, ocr_used, page_count)
    |  Tiers:
    |    - "high": >2000 chars, >=3 legal keywords, alpha ratio > 0.4
    |    - "medium": >500 chars, >=1 legal keyword
    |    - "low": everything else
    |  Forced "low" for: alpha_ratio < 0.4, chars_per_page < 100
```

### Safety Limits

- `MAX_PAGES = 5000` -- refuses PDFs larger than this
- `MAX_OCR_PAGES = 500` -- caps OCR processing (ocr_truncated flag set)
- Password-protected PDFs: logged and skipped

### Additional Features

- `reattach_footnotes(text)`: Detects footnote definitions, removes from original location, inlines as `[Footnote N: text]` near references.
- `extract_tables(file_path)`: Uses pdfplumber table detection, returns list of dicts with `{page, headers, rows, markdown}`.
- 28 legal keywords used for quality scoring (court, petitioner, respondent, section, act, judgment, etc.).

---

## 3. Chunking Strategy

**File**: `backend/app/core/ingestion/chunker.py`

### Section Detection

16 section types detected via regex patterns:

| Section Type | Example Headings |
|---|---|
| HEADER | IN THE SUPREME COURT, JUDGMENT, REPORTABLE |
| FACTS | FACTS OF THE CASE, FACTUAL BACKGROUND, BRIEF FACTS |
| ARGUMENTS | SUBMISSIONS OF THE PARTIES, RIVAL CONTENTIONS |
| ISSUES | ISSUES FOR DETERMINATION, QUESTIONS FOR CONSIDERATION |
| ANALYSIS | ANALYSIS AND DISCUSSION, OUR ANALYSIS, REASONING |
| RATIO | RATIO DECIDENDI, CONCLUSION, FINDINGS |
| ORDER | ORDER, FINAL ORDER, DISPOSITION |
| DISSENT | DISSENTING OPINION/JUDGMENT/VIEW |
| CONCURRENCE | CONCURRING OPINION/JUDGMENT/VIEW |
| PRELIMINARY | PRELIMINARY, BACKGROUND |
| EVIDENCE | EVIDENCE ON RECORD, APPRECIATION OF EVIDENCE |
| STATUTORY | STATUTORY FRAMEWORK, RELEVANT PROVISIONS |
| TOC | TABLE OF CONTENTS, INDEX, HEADNOTE |
| EDITORIAL | EDITOR'S NOTE, CATCHWORDS, CITATOR |
| DIRECTIONS | DIRECTIONS ISSUED, RELIEF GRANTED |
| PER_CURIAM | PER CURIAM, BY THE COURT |

**Heading position check**: Matches only at line-start positions (short lines <100 chars) to prevent mid-sentence false positives. Allows Roman numeral/digit prefixes like "I.", "1.", "(a)".

**Deduplication**: Same-type markers within 50 chars are deduplicated; different-type markers within 20 chars are deduplicated.

### Chunk Sizes

| Section Type | Chunk Size | Overlap |
|---|---|---|
| Standard (HEADER, FACTS, ARGUMENTS, ISSUES, etc.) | 2000 chars | 200 chars |
| Dense (ANALYSIS, RATIO, ORDER, DISSENT, CONCURRENCE) | 1200 chars | 300 chars |

**Rationale**: Dense legal sections contain holdings, ratios, and orders that benefit from smaller, more focused chunks with higher overlap for context continuity.

### Break-Point Detection

Priority order (highest to lowest preference):
1. **Paragraph break** (`\n\n`) -- cleanest boundary
2. **Sentence break** (`. `, `.\n`, `;\n`, `?\n`, `!\n`) -- abbreviation-aware
3. **Word break** (` `) -- last resort

**Abbreviation awareness**: The `_is_abbreviation()` function checks the 10 chars preceding a period against legal abbreviations (vs., Dr., Mr., Mrs., Smt., Hon., Ld., I.P.C., Cr.P.C., C.P.C., B.N.S., S.C.C., A.I.R., etc.) to avoid splitting on "Section 302 I.P.C. " as a sentence boundary.

**Overlap snapping**: Overlap start position is snapped to the nearest non-abbreviation sentence boundary within 100 chars forward, preventing mid-word overlap fragments.

**Trailing chunk guard**: If remaining text after next position is smaller than the overlap, the loop stops to avoid near-duplicate trailing chunks.

### Per-Chunk Metadata

Each `Chunk` dataclass carries:
- `text`: Raw text content
- `section_type`: One of 16 types above, or "FULL" if no sections detected
- `chunk_index`: Sequential index within the case
- `case_id`: Parent case UUID
- `page_number`: From page_map (optional)
- `para_start`, `para_end`: Detected paragraph number range
- `opinion_author`: Judge name from per-judge opinion boundary detection
- `legal_signal`: Signal phrase density per 1000 chars

### Legal Signal Scoring

16 signal phrases scored: "held that", "we hold", "in our opinion", "it is well settled", "the ratio", "we are of the view", "the principle", "we approve", "we overrule", "we distinguish", "the question is answered", "the appeal is allowed/dismissed", "we are of the considered view", "in our considered opinion", "we accordingly hold".

Formula: `count_of_phrases / len(text) * 1000` -- higher scores indicate chunks more likely to contain holdings.

### Per-Judge Opinion Detection

Regex detects judge name headers like `D.Y. CHANDRACHUD, J.` or `[Per S. RAVINDRA BHAT, J.]`. Each chunk is assigned the `opinion_author` of the judge whose opinion boundary most recently preceded it.

---

## 4. Metadata Extraction

**File**: `backend/app/core/ingestion/metadata.py`

### CaseMetadata Dataclass

60+ fields organized in groups:

**Core fields**: title, citation, court, judge, author_judge, year, decision_date, case_type, bench_type, jurisdiction, petitioner, respondent, ratio_decidendi, acts_cited, cases_cited, citation_refs, keywords, disposal_nature

**Phase C (Legal completeness)**: coram_size, lower_court, lower_court_case_number, appeal_from, opinion_type (unanimous/majority/plurality/per_curiam), dissenting_judges, concurring_judges, split_ratio, petitioner_type, respondent_type, is_pil, companion_cases

**V2 fields (Judge Behavior / Citation Intelligence / Procedural)**: arguments_raised, relief_granted/sought, sentence_details, damages_awarded, judicial_tone, key_observations, hearing_count, citation_treatments, distinguished_cases, overruled_cases, legal_principles_applied, procedural_history, interim_orders, filing_date, urgency_indicators, party_counsel, issue_classification, fact_pattern_tags, operative_order, conditions_imposed, costs_awarded

**V3 fields**: legal_propositions `[{proposition_text, paragraph_number, is_novel, related_section}]`, statute_sections_interpreted `[{section, act, interpretation_summary}]`, fact_pattern_summary

### LLM Extraction

`extract_metadata_llm(text, llm, pdf_path)`:

1. **PDF multimodal** (preferred): If `pdf_path` is provided and LLM supports `generate_structured_from_pdf`, sends the actual PDF to Gemini for layout-aware extraction.
2. **Text fallback**: Head+tail truncation (30K head + 20K tail with `[...middle section truncated...]` marker), then `generate_structured()` with `METADATA_OUTPUT_SCHEMA`.
3. **Empty result check**: If LLM returns all-null, raises `RuntimeError` for retry.
4. **Schema filtering**: Only fields matching `CaseMetadata` field names are accepted.

### Judge Name Processing

Multi-stage pipeline:
1. **Parse**: Handles pipe/semicolon/comma-delimited strings; strips "Hon'ble", "Justice", "Mr. Justice", "Dr.", trailing ", J.", "JJ."
2. **Normalize**: Collapse multiple spaces, normalize initials ("D. Y." -> "D.Y."), strip OCR artifacts
3. **Canonical lookup**: 40+ known SC judge variants mapped to canonical forms (e.g., "dy chandrachud" -> "D.Y. Chandrachud")
4. **Header validation**: Surname (longest 4+ char word) must appear in first 2000 chars of judgment
5. **Tenure validation**: Cross-reference against `_JUDGE_TENURE` dict (50+ entries with appointment/retirement years); reject temporally impossible judges (grace +1 year for mid-year retirement)
6. **Deduplication**: After normalization, dedup by lowercased name

### Merge Strategy (Parquet vs LLM)

| Field | Priority | Rationale |
|---|---|---|
| title, citation, court, year, decision_date, petitioner, respondent | Parquet | Reliably present in dataset |
| disposal_nature | LLM | Parquet has 67-81% NULLs; LLM reads operative portion |
| author_judge | LLM | Parquet has 0% for un-enriched cases |
| judge (array) | Validated LLM | LLM extracts full bench; Parquet usually only 1 name |
| ratio_decidendi, acts_cited, cases_cited, keywords, bench_type, jurisdiction | LLM | Semantic extraction from unstructured text |
| case_type | LLM with normalization | 27 abbreviation mappings (e.g., "slp(crl)" -> "Special Leave Petition") |

### Confidence Score

Weighted formula (0.0-1.0):
- title: 0.12, citation: 0.12, court: 0.10, year: 0.10, judge: 0.08
- decision_date: 0.06, petitioner: 0.05, respondent: 0.05
- ratio_decidendi: 0.08, acts_cited: 0.05, cases_cited: 0.05
- keywords: 0.04, case_type: 0.03, disposal_nature: 0.03
- bench_type: 0.02, jurisdiction: 0.02

Empty strings and empty lists count as absent.

---

## 5. Embedding Configuration

**File**: `backend/app/core/providers/embeddings/gemini.py`

### Model and Dimensions

- **Model**: `gemini-embedding-2-preview` (configurable via `settings.gemini_embedding_model`)
- **Dimensions**: 1536 (configurable via `settings.gemini_embedding_dimension`; uses Matryoshka output dimensionality control)
- **Context**: 8K tokens

### Task Types

Three task types used throughout the system:

| Task Type | Used When | Purpose |
|---|---|---|
| `RETRIEVAL_DOCUMENT` | Ingestion (`embed_batch`) | Optimized for document storage |
| `RETRIEVAL_QUERY` | Search (`embed_text`) | Optimized for query representation |
| `SEMANTIC_SIMILARITY` | Used in specific comparison scenarios | Optimized for similarity comparison |

### Implementation Details

**AI Studio path**: Uses `genai.Client(api_key=...)` with SDK batch embedding in a single call.

**Vertex AI path**: The SDK routes Vertex AI embed calls to the `:predict` endpoint, which Google dropped for `gemini-embedding-2-preview` (returns 400 FAILED_PRECONDITION). The provider works around this by calling the `:embedContent` REST endpoint directly via `httpx.AsyncClient`.

**Vertex AI batching**: Since `:embedContent` only supports one content per call, batch embedding uses `asyncio.gather` with configurable concurrency:
- `EMBED_SUB_BATCH` (default 5): sub-batch size
- `EMBED_CONCURRENCY` (default 3): max concurrent requests via semaphore
- `EMBED_SLEEP` (default 0.5s): delay between sub-batches

### Retry Configuration

- 5 attempts, exponential backoff (2s min, 60s max)
- Retries on: `GoogleAPIError`, `ResourceExhausted`, `ServiceUnavailable`, `InternalServerError`, `ConnectionError`, `OSError`, `TimeoutError`, `httpx.ReadTimeout/ConnectTimeout/TimeoutException`
- 60s timeout per individual embed call

---

## 6. Vector Storage Schema

**File**: `backend/app/core/providers/vector/pinecone_store.py`, `backend/app/core/ingestion/pipeline.py`

### Pinecone Index

- Single index, all vector types coexist
- 1536 dimensions (Gemini embedding)
- Connected via host URL (`PINECONE_HOST`) or index name

### 7 Vector Types

| vector_type | Source | ID Format | Description |
|---|---|---|---|
| `chunk` | Judgment text chunks | `{case_id}_{chunk_index}` | Standard 2000/1200-char text chunks |
| `proposition` | LLM-extracted propositions | `{case_id}_prop_{i}` | Direct legal-point vectors (min 20 chars) |
| `ratio` | LLM-extracted ratio decidendi | `{case_id}_ratio` | One per case (min 30 chars) |
| `headnote` | Structured headnotes | `{case_id}_headnote_{i}` | Reporter-style headnote propositions |
| `statute` | Statute section text | `{statute_id}_chunk_{i}` | Bare act section text (from ingest_statutes.py) |
| `summary` | RAPTOR section summaries | `{case_id}_summary_{section_type}` | 2-4 sentence per-section summaries |
| `community` | Citation graph communities | `community_{community_id}_{i}` | GraphRAG community summaries |

### Chunk Vector Metadata Fields

```python
{
    "case_id": str,              # Parent case UUID
    "chunk_index": int,          # Sequential within case
    "section_type": str,         # HEADER, FACTS, ANALYSIS, RATIO, etc.
    "court": str,                # "Supreme Court of India"
    "year": int,                 # Decision year
    "case_type": str,            # "Criminal Appeal", etc.
    "jurisdiction": str,         # "criminal", etc.
    "bench_type": str,           # "division", etc.
    "disposal_nature": str,      # "Dismissed", etc.
    "title": str,                # Truncated to 200 chars
    "citation": str,             # Full citation string
    "author_judge": str,         # Authoring judge
    "judge": list[str],          # Full bench (max 20)
    "acts_cited": list[str],     # Statutes cited (max 25)
    "opinion_author": str,       # Per-chunk opinion author
    "para_start": int,           # Paragraph number range
    "para_end": int,
    "text": str,                 # Chunk text (truncated to 2000 for Pinecone 40KB metadata cap)
    "document_type": str,        # "case_law"
    "vector_type": str,          # "chunk"
    "legal_signal": float,       # Signal phrase density
    "judicial_tone": str,        # "formal", "assertive", etc.
    "fact_pattern_tags": list[str],  # Max 5
    "issue_classification": list[str],  # Max 5
    "page_start": int,           # Page number range
    "page_end": int,
    "char_start": int,           # Character offset in full_text
    "char_end": int,
}
```

### Proposition/Ratio/Headnote Vector Metadata

Same base fields as chunk vectors plus:
- `related_section`: For propositions, the statute section it relates to
- `is_novel`: Whether the proposition is novel (propositions only)
- No `chunk_index`, `opinion_author`, or page/char position fields

### Filtering

Pinecone metadata filters used at search time:
- `court`, `year` (range), `case_type`, `bench_type`, `jurisdiction`, `disposal_nature`
- `acts_cited` (array contains)
- `vector_type` (to target specific vector types)
- `document_type` (to separate case_law from statute)

### Circuit Breaker

All Pinecone operations go through an `AsyncCircuitBreaker`:
- Opens after configurable failure threshold
- When open: upserts raise `CircuitBreakerOpen`; searches return empty results
- Retry: 3 attempts, exponential backoff (1-10s)
- Timeouts: upsert 120s, search 10s

---

## 7. Retrieval Pipeline

**File**: `backend/app/core/chat/rag.py`

### RAG Chat Flow

```
User question
    |
    v
1. Session management (create or validate ownership)
    |
    v
2. Load chat history (last MAX_HISTORY_MESSAGES messages)
    |
    v
2.5. Reformulate query with conversation context (if history exists)
    |  Uses LLM to rewrite follow-up questions as standalone queries
    v
3. hybrid_search(search_query, ...) -> SearchResponse
    |  (See Section 8 for details)
    v
4. _build_sources(results, db) -> list[ChatSource]
    |  Fetches ratio_decidendi, bench_type, judge from PostgreSQL
    |  Checks for overruled cases via graph (check_treatment_from_graph)
    v
5. _format_context(sources) -> context string
    |  For each source: citation, year, court, bench label, ratio, chunk text
    |  Treatment warnings appended (e.g., "NOTE: This case was overruled by ...")
    |  Context truncated to MAX_SNIPPET_CHARS per source
    v
5.5. Prompt size guard:
    |  If user_prompt > 100K chars (~25K tokens):
    |    Truncate to 3 sources, last 4 history messages
    |    Emit context_notice event to client
    v
6. LLM streaming: llm.stream(user_prompt, system=CHAT_SYSTEM_PROMPT)
    |  Yields RAGEvent(type="chunk", data={"content": token})
    v
7. Yield source events: RAGEvent(type="source", data={case_id, title, ...})
    v
8. Persist: user message + assistant response to chat_messages table
    |  Messages encrypted with encrypt_field() before storage
    v
9. Yield done event: RAGEvent(type="done", data={tokens_used, source_count})
```

### Treatment Checking

Before sending sources to the LLM:
1. **Graph check**: Query Neo4j for `CITES` edges with `treatment = 'overruled'`
2. **Text heuristic fallback**: If graph unavailable, scan ratio text for overruling language

---

## 8. Search Architecture

**File**: `backend/app/core/search/hybrid.py`, `backend/app/core/search/fulltext.py`, `backend/app/core/search/query.py`

### Hybrid Search Pipeline

```
User query
    |
    v
1. Redis cache check (hash of query + filters + page)
    |  Cache hit: return immediately
    v
2. Query understanding (LLM structured output)
    |  understand_query(query, llm) -> QueryUnderstanding
    |  Extracts: intent, expanded_query, filters, entities, search_strategy
    |  Intent types: citation_lookup, topic_search, case_search, statute_search, judge_search, general
    |  Strategy types: vector_heavy, keyword_heavy, balanced, exact_match
    |  Skippable via pre_understood=True (agent worker optimization, saves ~2s)
    v
2.5. Statute reference expansion
    |  expand_statute_references(query) -> (original, expanded_terms)
    |  IPC Section 302 -> also Section 103 BNS (and vice versa)
    |  Uses IPC_TO_BNS_MAP, CRPC_TO_BNSS_MAP, EVIDENCE_TO_BSA_MAP
    |  Expanded terms added to FTS query with OR; vector search uses original only
    v
3. Strategy-based retrieval:

    exact_match:
        _exact_citation_search(query, db) -> direct citation lookup
        Checks cases.citation AND case_citation_equivalents table
        If found: return immediately (no reranking needed)
        Fallback: FTS only

    vector_heavy / keyword_heavy / balanced:
        PARALLEL:
          a. _vector_search(query, embedder, vector_store, filters, pre_embedded)
             |  embedder.embed_text(query, task_type="RETRIEVAL_QUERY")
             |  vector_store.search(query_vector, top_k, filters)
             |  Returns: [(case_id, score, chunk_text, char_start, char_end)]
          b. search_fulltext(fts_query, filters, limit, db)
             |  Uses websearch_to_tsquery for boolean support
             |  Supports quoted phrases via phraseto_tsquery
             |  ts_rank_cd (cover density ranking) for proximity-aware scoring
             |  ts_headline for snippet generation
             |  Hindi queries: skip FTS entirely (Devanagari not tokenizable by English tsvector)
    v
4. RRF merge
    |  rrf_merge([vector_ranked, fts_ranked], k=60, weights=strategy_weights)
    |  Formula: RRF(d) = Sum(w_i / (k + rank_i(d)))
    |
    |  Strategy weights:
    |    keyword_heavy: [1.0, 2.0], k=40
    |    vector_heavy:  [2.0, 1.0], k=80
    |    balanced:      [1.0, 1.0], k=60
    |    Hindi:         [2.0, 0.0], k=80 (vector-only)
    v
5. Rerank top candidates
    |  Top N*2 candidates sent to Cohere rerank-v4.0-pro
    |  Snippets used as reranking documents (FTS snippets preferred, then vector chunk text)
    |  On failure: falls back to RRF order
    v
6. Paginate
    v
7. Enrich from PostgreSQL
    |  Fetches: title, citation, court, year, decision_date, case_type, judge, bench_type
    |  Adds equivalent_citations from case_citation_equivalents
    |  Adds treatment warnings for overruled cases (heuristic check)
    v
8. Build facets (court, year, case_type, bench_type distributions)
    v
8b. Outcome bias check (for bail/sentence queries)
    v
9. Cache result to Redis
    v
Return SearchResponse {results, total_count, page, page_size, query_understanding, facets, outcome_bias_warning, search_degraded}
```

### FTS Implementation

**File**: `backend/app/core/search/fulltext.py`

- Column: `searchable_text` (tsvector, computed by trigger from full_text + title + keywords + acts_cited)
- Ranking: `ts_rank_cd` (cover density) -- chosen over `ts_rank`/BM25 for legal text (ADR-019)
- Query parsing: `websearch_to_tsquery` for Google-like syntax (AND, OR, negation, quoted phrases)
- Quoted phrases: Combined with `phraseto_tsquery` using `&&` for phrase proximity enforcement
- Filter clauses: Dynamically built from SearchFilters (court, year range, case_type, bench_type, act, judge, judgment_section)
- Section search: Joins `case_sections` table when `judgment_section` filter is active
- Act filter: Uses `normalize_act_name()` + unnest/EXISTS for GIN-compatible array matching

### Graceful Degradation

- If vector search fails: FTS-only with warning (`search_degraded = True`)
- If FTS fails: Vector-only with warning
- If reranker fails: RRF order preserved
- If Redis unavailable: No caching, continues normally

---

## 9. Knowledge Graph Schema

**Files**: `backend/app/core/providers/graph/neo4j_store.py`, `backend/app/core/ingestion/pipeline.py`, `backend/app/core/graph/traversal.py`

### Node Labels

| Label | Primary Key | Properties |
|---|---|---|
| `Case` | `id` (UUID or `ref_` placeholder) | title, citation, court, year, bench_type, case_type, disposal_nature, judge, keywords, acts_cited, ratio, cited_by_count, is_overruled |
| `Statute` | `id` | act_name, section_number, section_title, section_text, year, is_repealed, replaced_by |
| `Judge` | `id` | name |
| `Act` | `id` | name |
| `Doctrine` | `id` | name, description |
| `Counsel` | `id` | name |
| `LegalPrinciple` | `id` | principle_text |
| `Issue` | `id` | description |
| `Community` | `id` | title, summary, size |

### Relationship Types

| Relationship | From -> To | Properties |
|---|---|---|
| `CITES` | Case -> Case | reporter, treatment (overruled/affirmed/distinguished/followed/not_followed/doubted/explained/per_incuriam/referred_to), context |
| `EQUIVALENT_TO` | Case -> Case | (citation equivalents, e.g., SCC and AIR citations for same case) |
| `APPLIES_DOCTRINE` | Case -> Doctrine | |
| `DECIDED_BY` | Case -> Judge | |
| `REPRESENTED_BY` | Case -> Counsel | |
| `APPLIES_PRINCIPLE` | Case -> LegalPrinciple | |
| `ADDRESSES` | Case -> Issue | |
| `BELONGS_TO` | Case -> Community | |
| `INTERPRETS` | Case -> Statute | interpretation_summary |
| `AUTHORED_BY` | Case -> Judge | |

### Placeholder Resolution

When a cited case doesn't exist in the database yet, a placeholder node is created with `id = "ref_{hex12}"` and `title = citation_text`. When the actual case is later ingested, the placeholder is promoted: its `id` is updated to the real UUID and all properties are set, preserving existing `CITES` edges.

### Graph Traversal Operations

**File**: `backend/app/core/graph/traversal.py`

- `get_neighborhood(case_id, depth=1)`: Returns nodes and edges within N hops (max 3), capped at 200 nodes. Treatment labels are display-mapped (e.g., "overruled" -> "overrules").
- `get_citation_chain(case_id, max_depth=3)`: Forward citation chain -- cases this case cites, recursively (max 5 depth).
- Authority ranking: Uses `cited_by_count` from graph.
- Statistics: Aggregated graph stats.

### Circuit Breaker

Neo4j operations use `AsyncCircuitBreaker`:
- 5 retry attempts, exponential backoff (2-30s)
- Retries on: `ServiceUnavailable`, `OSError`, `ConnectionError`
- Query timeout: 30s
- Connection pool: 50 max, 60s acquisition timeout

---

## 10. Agent Architecture

**Files**: `backend/app/core/agents/research.py`, `backend/app/core/agents/case_prep.py`, `backend/app/core/agents/drafting.py`, `backend/app/core/agents/strategy.py`

All agents use LangGraph `StateGraph` with typed state dictionaries, HITL checkpoints via `interrupt()`, and SSE streaming for real-time progress.

### 10.1 Research Agent V3

**File**: `backend/app/core/agents/research.py`

5-stage sequential-reactive pipeline:

```
Stage 1: UNDERSTAND
  rewrite_query -> classify -> statute_lookup -> element_decomposition -> route_by_complexity

Stage 2: INVESTIGATE (complex path)
  plan_research -> checkpoint_plan (HITL) -> dispatch_workers -> [Send() fan-out]

  Workers (parallel via Send):
    case_law_worker:     hybrid_search for case law
    named_case_worker:   DB lookup + IK search for specific cases
    statute_worker:      statute section search in Pinecone + PG
    graph_worker:        Neo4j citation graph traversal
    graph_community_worker: GraphRAG community summaries
    ik_search_worker:    Indian Kanoon external search
    web_search_worker:   Tavily web search for recent developments

  Per-worker timeouts: web(10s), ik(45s), case_law(30s), named_case(30s),
                       graph(15s), graph_community(10s), statute(20s)

Stage 3: EVALUATE
  gather_results -> batch_cot_with_reflection -> evaluate_and_extract -> gap_analysis
  -> [should_refine?] -> dispatch_workers (refinement round, max 2) | checkpoint_findings (HITL)

Stage 4: CHALLENGE
  adversarial_search -> temporal_validation

Stage 5: SYNTHESIZE
  speculative_synthesis -> format_footnotes -> verify_v2 -> quality_check
  -> checkpoint_memo (HITL) -> END
```

**Fast path** (simple queries): Skips stages 2-4, goes directly to `fast_path_search -> fast_path_synthesis -> format_footnotes -> verify_v2 -> quality_check`.

**Key state fields** (ResearchState TypedDict):
- `query`, `rewritten_query`, `complexity` (simple/moderate/complex/multi_issue)
- `research_plan`: list[ResearchTask] with task_type, nl_query, boolean_query, filters, priority
- `worker_results`: Annotated with `operator.add` reducer for Send() fan-out
- `relevance_scores`: CRAG per-document evaluations with verdict (correct/ambiguous/incorrect)
- `extracted_passages`: Verbatim passages with source tracking
- `evidence_gaps`: Gaps with suggested_query and conditioned_on (MC-RAG)
- `synthesis_drafts`: Speculative RAG parallel drafts (relevance/authority/recency strategies)
- `footnotes`: Structured footnotes with verification_status
- `statute_context`, `legal_elements`, `temporal_warnings`: V3 additions
- `process_events`: Accumulated SSE events for real-time UI updates

**Degenerate output detection**: Checks for LLM refusal loops, extreme repetition (same 50-char substring 5+ times), low alpha ratio (<25%), low character diversity (<15 unique chars), low word density.

### 10.2 Case Prep Agent

**File**: `backend/app/core/agents/case_prep.py`

```
START -> load_analysis -> prioritize -> checkpoint_issues (HITL) ->
deep_search -> argument_order -> checkpoint_strategy (HITL) ->
strategy_memo -> verify -> checkpoint_memo (HITL) -> END
```

Takes a previously analyzed document (from document upload pipeline), prioritizes issues, performs deep precedent search via citation graph, orders arguments, and generates a strategy memo.

### 10.3 Drafting Agent

**File**: `backend/app/core/agents/drafting.py`

```
START -> [parse_opposing_doc (if opposing text)] -> resolve_template ->
gather_provisions -> verify_precedents -> checkpoint_sources (HITL) ->
draft_sections -> assemble -> checkpoint_draft (HITL) ->
verify_final -> checkpoint_final (HITL) -> END

With revision loop:
  checkpoint_draft --(feedback)--> revise_section -> assemble -> checkpoint_draft
```

Resolves a document template (e.g., bail application, writ petition), gathers relevant statutory provisions, drafts sections, and assembles the full document with iterative revision support.

### 10.4 Strategy Agent

**File**: `backend/app/core/agents/strategy.py`

```
START -> analyze_facts -> element_decomposition -> fetch_judge ->
checkpoint_analysis (HITL) -> search_precedents -> assess_strength ->
generate_arguments_irac -> checkpoint_arguments (HITL) ->
adversarial_search -> counter_and_judge -> argument_ordering ->
synthesize_strategy -> verify -> checkpoint_memo (HITL) -> END
```

Takes case facts and optional target judge/bench, generates IRAC-structured arguments, runs adversarial search for counter-arguments, provides judge-specific strategic notes, and synthesizes an argument strategy memo.

### Common Agent Patterns

1. **Dependency injection via closures**: Node functions receive dependencies (llm, db, etc.) when the graph is built, not at runtime.
2. **DB sessions**: Nodes that need database access create fresh sessions via `async_session_factory()` (FastAPI Depends session closes before StreamingResponse generator runs).
3. **HITL checkpoints**: `make_checkpoint_node(step_name)` creates a node that calls `interrupt()`, pausing execution for user review. `make_feedback_router(step, retry_node, next_node)` routes based on user feedback.
4. **SSE streaming**: `process_events` list accumulates events of types: status, progress, checkpoint, memo, done, error.
5. **Feedback routing**: `check_error=True` parameter routes to END on error state.
6. **Auto-approve**: `auto_approve=True` in state skips HITL checkpoints.
7. **Worker fan-out**: Research agent uses `Send()` to dispatch parallel workers, with results accumulated via `operator.add` reducer.

---

## 11. Prompt Templates

**File**: `docs/PROMPT_LIBRARY.md`, `backend/app/core/legal/prompts.py`

### Metadata Extraction Prompt

**System**: 16-rule specialized system prompt for Indian court judgment metadata extraction. Rules enforce: extract only explicit content, array/null defaults, citation format requirements, enum constraints for bench_type/case_type/jurisdiction.

**Output Schema**: Structured JSON with all CaseMetadata fields.

**Few-Shot Examples**: 2 examples provided:
1. Criminal Appeal (State of Maharashtra v. Rajesh Kumar)
2. Constitutional Writ (Justice K.S. Puttaswamy v. Union of India)

### Query Understanding Prompt

**System**: Legal search query analyzer for Indian law. Parses into: intent, expanded_query, filters, entities, search_strategy. Handles Indian legal abbreviations (SC, HC, IPC, CrPC, CPC, BNS, BNSS).

### Research Agent Prompts (from prompts.py imports)

| Prompt Constant | Purpose |
|---|---|
| `RESEARCH_REWRITE_SYSTEM` | Query rewriting for legal precision |
| `RESEARCH_CLASSIFY_SYSTEM/SCHEMA` | Query complexity classification |
| `RESEARCH_PLAN_SYSTEM/SCHEMA` | Research plan generation |
| `RESEARCH_WORKER_COT_SYSTEM` | Worker-level chain-of-thought reasoning |
| `BATCH_COT_WITH_REFLECTION_SCHEMA` | Batched CoT with reflection |
| `RESEARCH_EVALUATE_AND_EXTRACT_SYSTEM` | CRAG evaluation + passage extraction |
| `EVALUATE_AND_EXTRACT_SCHEMA` | Schema for evaluation results |
| `RESEARCH_GAP_ANALYSIS_SYSTEM/SCHEMA` | Evidence gap identification |
| `RESEARCH_SYNTHESIZE_SYSTEM/USER` | Memo synthesis |
| `RESEARCH_CONTRADICTIONS_SYSTEM` | Contradiction detection between precedents |
| `RESEARCH_DISTINGUISH_SYSTEM` | Case distinguishing analysis |
| `RESEARCH_FAST_PATH_SYNTHESIS_SYSTEM` | Fast path synthesis for simple queries |
| `SPECULATIVE_DRAFT_SYSTEM` | Speculative RAG parallel drafts |
| `SPECULATIVE_MERGE_SYSTEM` | Merge best speculative draft |
| `SYNTHESIS_RETRY_SYSTEM` | Retry synthesis on degenerate output |
| `ADVERSARIAL_SEARCH_SYSTEM/SCHEMA` | V3 adversarial search |
| `ADVERSARIAL_MINI_CRAG_SYSTEM/SCHEMA` | Mini-CRAG for adversarial results |
| `RESEARCH_DECOMPOSE_SYSTEM/USER/SCHEMA` | V3 element decomposition |
| `LEGAL_QUALITY_CHECK_SYSTEM/SCHEMA` | LeMAJ legal quality assessment |
| `LEGAL_DISCLAIMER` | Standard legal disclaimer appended to memos |

### Contextual Embedding Prompts

- **Case law**: "Generate a concise 1-2 sentence context prefix stating: (1) what legal question the chunk addresses, (2) the court's position."
- **Statute**: "Generate a 1-sentence context prefix including: full act name, part/chapter, whether replaced by another section."

### Section Summary Prompt

"Summarize this section of an Indian court judgment in 2-4 sentences. Preserve: key legal principles, case names cited, statute sections referenced, and the court's reasoning."

### Chat System Prompt

`CHAT_SYSTEM_PROMPT` and `CHAT_USER_WITH_CONTEXT` — legal research assistant grounded in retrieved case law with inline citations.

---

## 12. Legal Domain Logic

### 12.1 Citation Extraction

**File**: `backend/app/core/legal/extractor.py`

15+ citation formats recognized via compiled regex patterns:

| Reporter | Pattern | Example |
|---|---|---|
| SCC | `(YYYY) Vol SCC Page` | (2020) 3 SCC 145 |
| SCC Sub-reporters | `(YYYY) Vol SCC (Sub) Page` | (2020) 3 SCC (Cri) 145 |
| SCC OnLine | `YYYY SCC OnLine Court NNNN` | 2020 SCC OnLine SC 1234 |
| AIR | `AIR YYYY Court Page` | AIR 2020 SC 145 |
| Neutral SC | `YYYY:INSC:NNNN` | 2023:INSC:1234 |
| Neutral HC | `YYYY:XXHC:NNNN` | 2023:DELHC:1234 |
| INSC (legacy) | `YYYY INSC NNN` | 2020 INSC 145 |
| SCR | `[YYYY] Vol SCR Page` | [2020] 3 SCR 145 |
| CrLJ | `YYYY CrLJ Page` | 2020 CrLJ 145 |
| SCALE | `(YYYY) Vol SCALE Page` | (2020) 3 SCALE 145 |
| MANU | `MANU/Court/NNNN/YYYY` | MANU/SC/1234/2020 |
| JT | `JT YYYY (Vol) Court Page` | JT 2020 (3) SC 145 |
| HC reporters | 25+ regional reporters (ILR, MLJ, KLT, BLR, etc.) | 2020 ILR 145 |
| LiveLaw | `YYYY LiveLaw (Court) NNN` | 2024 LiveLaw (SC) 123 |
| ITR | `[YYYY] Vol ITR Page` | [2020] 123 ITR 456 |
| Taxmann | `[YYYY] Vol taxmann.com NNN` | [2020] 123 taxmann.com 456 |
| Name-based | `Party v. Party` with contextual prefix | "held in X v. Y" |

**GAN-style discriminator**: `classify_case_citations()` separates named citations ("X v. Y (2020) 3 SCC 145") from bare reporter refs ("(2020) 3 SCC 145") using `is_bare_citation_ref()`. Bare refs go to `citation_refs` for graph linking only.

### 12.2 Act/Section Extraction

42+ short act name mappings (IPC, CrPC, CPC, BNS, BNSS, BSA, NDPS, POCSO, NI, FEMA, RTI, SARFAESI, IBC, etc.)

Section patterns handle: "Section X of the Y Act", plural sections ("Sections 302, 304"), Order/Rule patterns, Schedule/Appendix references.

`normalize_act_name()`: Converts abbreviations to full canonical names.
`normalize_acts_cited_list()`: Deduplicates and normalizes an entire list.

### 12.3 Statute Cross-References

**File**: `backend/app/core/legal/constants.py`

Complete section-level mappings between old and new criminal codes:

| Old Code | New Code | Entries |
|---|---|---|
| IPC (Indian Penal Code, 1860) | BNS (Bharatiya Nyaya Sanhita, 2023) | 100+ sections |
| CrPC (Code of Criminal Procedure, 1973) | BNSS (Bharatiya Nagarik Suraksha Sanhita, 2023) | Maps in `CRPC_TO_BNSS_MAP` |
| IEA (Indian Evidence Act, 1872) | BSA (Bharatiya Sakshya Adhiniyam, 2023) | Maps in `EVIDENCE_TO_BSA_MAP` |

**Statute enrichment** (`statute_enrichment.py`): Temporal guard -- pre-2024 cases get old codes only; post-2024/unknown get bidirectional enrichment.

### 12.4 Court Hierarchy

**File**: `backend/app/core/legal/courts.py`

- Supreme Court + 25 High Courts + district courts + 20+ tribunals
- Short-name -> canonical full name mapping (200+ entries)
- AIR court code mapping (SC, All, Bom, Cal, Del, Mad, Kar, Ker, etc.)
- `normalize_court_name()`: Maps variants to canonical form
- `get_court_level()`: Returns "supreme", "high", "district", "tribunal", "unknown"

### 12.5 Precedent Strength

**File**: `backend/app/core/legal/precedent_strength.py`

Deterministic classification (no LLM needed):

```
classify_precedent_strength(source_court, source_bench, target_court, target_bench, overruled)
    |
    v
    OVERRULED -> 0.0 (if overruled flag set)
    Supreme Court -> BINDING for all courts (1.0)
    Same court, larger bench -> BINDING
    Same court, same/smaller bench -> PERSUASIVE (0.6)
    Higher court -> BINDING
    Lower court -> PERSUASIVE
    Unknown -> UNKNOWN (0.4)
```

Bench hierarchy: constitutional (4) > full (3) > division (2) > single (1)

`coram_size` overrides bench label: 5+ = constitutional, 3-4 = full, 2 = division, 1 = single.

### 12.6 Citation Treatment

**File**: `backend/app/core/legal/treatment.py`

8 treatment types detected via regex:

| Treatment | Patterns |
|---|---|
| OVERRULED | overruled, no longer good law, per incuriam, expressly/impliedly overruled |
| DISTINGUISHED | distinguished, distinguishable, distinguishing from/in/on |
| AFFIRMED | affirmed, upheld, approved, endorsed, confirmed |
| NOT_FOLLOWED | not followed, declined to follow, refused to follow |
| FOLLOWED | followed, applied, relied upon, reiterated |
| EXPLAINED | explained, clarified, interpreted |
| DOUBTED | doubted, questioned, expressed doubt/reservation |
| PER_INCURIAM | declared as decided per incuriam |

**Negative-first detection**: NOT_FOLLOWED patterns are detected before FOLLOWED to prevent false-positive classification. Match spans from negative patterns are excluded from positive matching.

**LLM fallback**: `classify_treatment_llm()` provides higher accuracy for ambiguous cases, gated by `enable_treatment_llm_fallback` config flag when regex confidence falls below `treatment_llm_confidence_threshold`.

### 12.7 PII Anonymization

**File**: `backend/app/core/ingestion/anonymizer.py`

- **Aadhaar**: 12 digits (spaced groups of 4, or bare 12-digit)
- **PAN**: AAAPA9999A (4th char must be valid entity-type code ABCFGHJLPT)
- **Phone**: 10 digits starting 6-9, optional +91/91/0 prefix
- **Sensitive case detection**: POCSO, IPC sexual offence sections (354-376, 509), BNS equivalents (63-79), keyword patterns (prosecutrix, minor victim)

Masking order matters: spaced Aadhaar first (to avoid phone overlap), then phone (before bare Aadhaar), then bare Aadhaar, then PAN.

---

## 13. Batch Ingestion

### 13.1 Vertex AI Batch Pipeline

**File**: `backend/scripts/batch_ingest_vertex.py`

4-phase hybrid batch+online pipeline:

```
Phase 1: TEXT EXTRACTION + GCS UPLOAD
  For each PDF:
    - extract_and_score(pdf_path) -> text quality
    - Upload text to GCS: gs://smriti-batch-ingestion/{run_id}/texts/{filename}.txt
    - Save progress to progress.json

Phase 2: BATCH METADATA EXTRACTION (50% cheaper)
  - Build JSONL request file with METADATA_EXTRACTION_SYSTEM prompt
  - Upload to GCS: gs://smriti-batch-ingestion/{run_id}/batch_request.jsonl
  - Submit Vertex AI batch job (model: gemini-2.5-flash)
  - Poll for completion
  - Download results from GCS output
  - Parse structured metadata from each response

Phase 3: ONLINE PROCESSING PER CASE
  For each case with extracted text + metadata:
    - merge_metadata(parquet, llm_meta)
    - validate_with_regex, validate_cross_fields, cross_validate_propositions
    - Regex supplementation (acts, citations)
    - anonymize_text
    - _insert_case into PostgreSQL
    - detect_judgment_sections + chunk_judgment
    - Optional: batch_contextualize_chunks (contextual embeddings)
    - _embed_chunks -> _upsert_vectors (chunk vectors)
    - _upsert_proposition_vectors (proposition, ratio, headnote vectors)
    - Optional: generate_section_summaries (RAPTOR)
    - _build_citation_graph (Neo4j)
    - Stale vector cleanup
    - Update chunk_count + ingestion_status

Phase 4: QUALITY CHECK
  - Sample 10 cases
  - Check 5 vector types per case
  - Verify PostgreSQL record completeness
```

**Cost**: ~$34/1K cases (~50% savings via batch pricing).
**Resume**: `--resume <run_id>` reloads `progress.json` and skips completed cases.
**Model**: `gemini-2.5-flash` (NOT preview models -- unavailable on Vertex AI).
**GCS bucket**: `gs://smriti-batch-ingestion/`.

### 13.2 Turbo Ingestion Orchestrator

**File**: `ingestion/turbo_ingest.py`

Multi-account parallel orchestrator for full 35K-case ingestion:

- 4 accounts (a, b, c, d) with independent GCP service account credentials
- Progressive rollout: trial (50) -> small (500) -> medium (2000) -> full (remaining)
- Per-account environment files in `ingestion/accounts/env_{a,b,c,d}`
- Each account runs `batch_ingest_vertex.py` as a subprocess
- Commands: `--setup`, `--trial`, `--extract-all`, `--run`, `--resume`, `--status`, `--quality-check`, `--retry-failed`
- Credential path resolution to absolute paths
- Queue-based workers with circuit breaker (10 failures)
- Graceful shutdown, download retries, ETA logging

### 13.3 Rate Limiting

**File**: `backend/app/core/ingestion/rate_limiter.py`

- `AsyncRateLimiter`: Token-bucket style, tracks timestamps in deque, blocks via `asyncio.sleep` when window full
- `RateLimiterPool`: Per-key rate limiters for API key rotation
- Default: 30 RPM per key, 60-second window
- Supports both context manager (`async with limiter:`) and explicit `acquire()/release()`

### 13.4 Graph Retry Queue

**File**: `backend/app/core/ingestion/graph_retry.py`

- `graph_build_queue` table: case_id, error, retry_count, timestamps
- `record_graph_failure()`: INSERT ON CONFLICT DO UPDATE
- `get_pending_retries()`: WHERE retry_count < max_retries ORDER BY created_at
- `mark_retry_success()`: DELETE from queue
- `increment_retry_count()`: retry_count + 1
- Max 3 retries per case

---

## Key Configuration Environment Variables

| Variable | Purpose | Default |
|---|---|---|
| `GEMINI_API_KEY` | Gemini API key (AI Studio) | Required |
| `GEMINI_USE_VERTEXAI` | Use Vertex AI instead of AI Studio | false |
| `GEMINI_VERTEXAI_PROJECT` | GCP project ID for Vertex AI | Required if Vertex |
| `GEMINI_MODEL` | LLM model name | gemini-3.1-pro-preview |
| `GEMINI_EMBEDDING_MODEL` | Embedding model | gemini-embedding-2-preview |
| `GEMINI_EMBEDDING_DIMENSION` | Embedding dimensions | 1536 |
| `GEMINI_THINKING_BUDGET` | Thinking budget (0=disabled, saves cost) | None |
| `PINECONE_API_KEY` | Pinecone API key | Required |
| `PINECONE_HOST` | Pinecone host URL | Required |
| `NEO4J_URI` | Neo4j connection URI | Required |
| `NEO4J_PASSWORD` | Neo4j password | Required |
| `COHERE_API_KEY` | Cohere reranker API key | Required |
| `EMBEDDING_DIMENSION` | Expected embedding dimension (validation) | 1536 |
| `SKIP_CONTEXTUAL_EMBEDDINGS` | Skip contextual prefix generation | 0 |
| `SKIP_RAPTOR_SUMMARIES` | Skip RAPTOR section summaries | 0 |
| `PINECONE_UPSERT_BATCH` | Pinecone upsert batch size | 100 |
| `GCS_BUCKET_NAME` | GCS bucket for PDF storage | smriti-production-documents |

---

*End of Phase 3 RAG Pipeline Deep Dive.*
