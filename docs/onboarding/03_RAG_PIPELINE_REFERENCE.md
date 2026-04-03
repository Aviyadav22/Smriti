# 03 -- RAG Pipeline Reference

**Audience**: Technical co-founder (Vansh) -- zero-context onboarding.
**Scope**: End-to-end trace of how a PDF judgment becomes searchable knowledge, how search works, and how agents consume it.

---

## Table of Contents

1. [Ingestion Pipeline](#1-ingestion-pipeline)
2. [PDF Extraction](#2-pdf-extraction)
3. [Chunking Strategy](#3-chunking-strategy)
4. [Metadata Extraction](#4-metadata-extraction)
5. [Embedding Configuration](#5-embedding-configuration)
6. [Vector Storage Schema (Pinecone)](#6-vector-storage-schema-pinecone)
7. [Retrieval Pipeline](#7-retrieval-pipeline)
8. [Knowledge Graph Schema (Neo4j)](#8-knowledge-graph-schema-neo4j)
9. [Agent Architecture](#9-agent-architecture)
10. [Prompt Templates](#10-prompt-templates)
11. [Legal Domain Logic](#11-legal-domain-logic)
12. [Batch Ingestion (Vertex AI)](#12-batch-ingestion-vertex-ai)
13. [How to Add New Case Law](#13-how-to-add-new-case-law)
14. [How to Debug Retrieval Issues](#14-how-to-debug-retrieval-issues)

---

## 1. Ingestion Pipeline

**File**: `backend/app/core/ingestion/pipeline.py`

The master function is `ingest_judgment()`. It takes a PDF path, Parquet metadata row, and injected dependencies (db, llm, embedder, vector_store, graph_store, storage). Returns the case UUID on success, `None` on failure.

### Step-by-Step Flow

```
PDF file on disk
    |
    v
1.  extract_and_score(pdf_path)              [pdf.py]
    Returns TextQuality(text, char_count, tier, ocr_used, page_map).
    Hard fail if < 50 chars.
    |
    v
1a. anonymize_text(full_text)                [anonymizer.py]
    Masks Aadhaar (12-digit), PAN (AAAPA9999A), phone (+91...).
    |
    v
1b. _compute_text_hash(full_text)            SHA-256 of whitespace-normalized text.
    Duplicate check: if hash exists with chunk_count > 0 -> SKIP.
    If hash exists with chunk_count = 0 -> RE-INGEST (broken prior run).
    |
    v
2.  PARALLEL:
      2a. extract_metadata_llm(full_text, llm)   [metadata.py, 3x tenacity retry]
      2b. storage.store(pdf_path, dest)           GCS upload
    |
    v
2c. merge_metadata(parquet_validated, llm_meta, full_text)
    Parquet wins: title, citation, court, year, decision_date, petitioner, respondent.
    LLM wins:    ratio_decidendi, acts_cited, cases_cited, keywords, bench_type, jurisdiction.
    Judge:       LLM-extracted -> header validation -> tenure check -> canonical normalization.
    |
    v
3.  VALIDATE METADATA
      3a. validate_with_regex        (year range, ISO date, court normalization,
                                      enum checks, list dedup, length caps)
      3b. validate_cross_fields      (year vs date, bench_type vs judge count,
                                      self-citation removal, etc.)
      3c. cross_validate_propositions (ratio <-> propositions consistency)
      3d. _validate_metadata_against_text (keywords and ratio must appear in text)
      3e. Confidence gating: score < 0.4 strips LLM fields; < 0.6 flags for review
    |
    v
3f. Regex supplementation:
      extract_acts_cited + normalize -> union with LLM acts
      enrich_statute_cross_references -> old<->new law bidirectional
      extract_citations -> union with LLM cases_cited
      classify_case_citations -> named vs bare refs
      detect_sensitive_case -> POCSO / sexual offence flags
    |
    v
5.  _insert_case(db)   INSERT INTO cases ... ON CONFLICT (citation) DO UPDATE
    Upserts ~60+ columns. searchable_text tsvector computed by DB trigger.
    If already_ingested: SKIP remaining steps.
    |
    v
6.  SECTION DETECTION + CHUNKING
      detect_judgment_sections -> chunk_judgment
      -> persist sections + statute interpretations + citation equivalents
    |
    v
6c. CONTEXTUAL EMBEDDINGS (optional, controlled by SKIP_CONTEXTUAL_EMBEDDINGS=1)
      batch_contextualize_chunks -> 1-2 sentence context prefix per chunk
    |
    v
7.  GENERATE EMBEDDINGS
      _embed_chunks: batch size 100, dimension validation 1536,
      3 retries (4s/8s/16s backoff)
    |
    v
8.  UPSERT TO PINECONE
      8a. _upsert_vectors -> chunk vectors (vector_type="chunk")
      8b. _upsert_proposition_vectors -> proposition, ratio, headnote vectors
      Stale vector cleanup: delete old vectors not in new set
    |
    v
8b. RAPTOR SECTION SUMMARIES (optional, SKIP_RAPTOR_SUMMARIES=1)
      generate_section_summaries -> vector_type="summary"
    |
    v
9.  BUILD CITATION GRAPH (Neo4j, non-critical)
      MERGE Case node -> placeholder resolution -> create CITES edges
      with treatment detection.
      On failure: queued to graph_build_queue for async retry (max 3).
    |
    v
    COMMIT + set ingestion_status = "complete" | "needs_review" | "failed"
```

### Error Handling

| Scenario | Behavior |
|---|---|
| DB uncommitted + vectors upserted | Rolls back DB, cleans orphan vectors from Pinecone |
| DB committed + later failure | Updates `ingestion_status = 'failed'` |
| Any failure | `_record_ingestion_failure()` writes to `audit_logs` (fresh session) |
| Graph build failure | Queued to `graph_build_queue` table for async retry (max 3 retries) |

---

## 2. PDF Extraction

**File**: `backend/app/core/ingestion/pdf.py`

### Pipeline

```
extract_and_score(file_path)
    |
    v
extract_pdf_text  (runs in asyncio.to_thread)
    For each page via pdfplumber:
      1. page.extract_text()
      2. If < 30 chars -> OCR fallback
      3. If alpha_ratio < 0.5 -> OCR fallback (garbled text)
      OCR: pdf2image + pytesseract (DPI 300, --oem 3 --psm 6 -l eng+hin)
    |
    v
_remove_repeated_headers_footers_pages
    Lines on 3+ pages removed (keep first). Common boilerplate stripped.
    |
    v
_smart_page_join
    Hyphenated word rejoining: "juris-\n" + "diction" -> "jurisdiction"
    Mid-sentence page break: space join.  Otherwise: double newline.
    |
    v
clean_extracted_text
    1. Unicode NFKC normalization
    2. Zero-width char removal (preserves ZWNJ/ZWJ for Devanagari)
    3. Control character removal (except \n, \t, \r)
    4. Page number removal, editorial metadata removal
    5. Em/en dash normalization, excess newline collapse
    |
    v
_build_page_map
    Maps page_number -> (char_start, char_end) for chunk -> page mapping
    |
    v
_strip_leading_judgment_bleed
    Detects text from previous judgment (pre-1964 PDFs).
    Strips if earliest case header marker appears after 200+ chars.
    |
    v
score_text_quality
    "high":   > 2000 chars, >= 3 legal keywords, alpha ratio > 0.4
    "medium": > 500 chars, >= 1 legal keyword
    "low":    everything else
```

### Safety Limits

| Limit | Value |
|---|---|
| `MAX_PAGES` | 5000 (refuses larger PDFs) |
| `MAX_OCR_PAGES` | 500 (caps OCR, sets `ocr_truncated` flag) |
| Password-protected | Logged and skipped |

### Additional Features

- `reattach_footnotes(text)`: Inlines footnotes as `[Footnote N: text]` near references.
- `extract_tables(file_path)`: Returns `{page, headers, rows, markdown}` via pdfplumber table detection.
- 28 legal keywords used for quality scoring (court, petitioner, respondent, section, act, judgment, etc.).

---

## 3. Chunking Strategy

**File**: `backend/app/core/ingestion/chunker.py`

### Section Detection

16 section types detected via regex at line-start positions (short lines < 100 chars). Roman numeral/digit prefixes allowed (e.g., "I.", "1.", "(a)").

| Section Type | Example Headings |
|---|---|
| `HEADER` | IN THE SUPREME COURT, JUDGMENT, REPORTABLE |
| `FACTS` | FACTS OF THE CASE, FACTUAL BACKGROUND |
| `ARGUMENTS` | SUBMISSIONS OF THE PARTIES, RIVAL CONTENTIONS |
| `ISSUES` | ISSUES FOR DETERMINATION, QUESTIONS FOR CONSIDERATION |
| `ANALYSIS` | ANALYSIS AND DISCUSSION, OUR ANALYSIS |
| `RATIO` | RATIO DECIDENDI, CONCLUSION, FINDINGS |
| `ORDER` | ORDER, FINAL ORDER, DISPOSITION |
| `DISSENT` | DISSENTING OPINION/JUDGMENT/VIEW |
| `CONCURRENCE` | CONCURRING OPINION/JUDGMENT/VIEW |
| `PRELIMINARY` | PRELIMINARY, BACKGROUND |
| `EVIDENCE` | EVIDENCE ON RECORD, APPRECIATION OF EVIDENCE |
| `STATUTORY` | STATUTORY FRAMEWORK, RELEVANT PROVISIONS |
| `TOC` | TABLE OF CONTENTS, INDEX, HEADNOTE |
| `EDITORIAL` | EDITOR'S NOTE, CATCHWORDS, CITATOR |
| `DIRECTIONS` | DIRECTIONS ISSUED, RELIEF GRANTED |
| `PER_CURIAM` | PER CURIAM, BY THE COURT |

Same-type markers within 50 chars are deduplicated; different-type within 20 chars are deduplicated.

### Chunk Sizes

| Section Type | Chunk Size | Overlap | Rationale |
|---|---|---|---|
| Standard (HEADER, FACTS, ARGUMENTS, ISSUES, etc.) | 2000 chars | 200 chars | General prose |
| Dense (ANALYSIS, RATIO, ORDER, DISSENT, CONCURRENCE) | 1200 chars | 300 chars | Holdings/orders need smaller, focused chunks with more context overlap |

### Break-Point Priority

1. **Paragraph break** (`\n\n`) -- cleanest boundary
2. **Sentence break** (`. `, `.\n`, `;\n`, `?\n`, `!\n`) -- abbreviation-aware
3. **Word break** (` `) -- last resort

**Abbreviation awareness**: `_is_abbreviation()` checks the 10 chars before a period against legal abbreviations (vs., Dr., Mr., Mrs., Smt., Hon., Ld., I.P.C., Cr.P.C., C.P.C., B.N.S., S.C.C., A.I.R., etc.) to avoid false sentence breaks.

**Overlap snapping**: Overlap start position snaps to nearest non-abbreviation sentence boundary within 100 chars forward.

**Trailing chunk guard**: If remaining text < overlap size, the loop stops to avoid near-duplicate trailing chunks.

### Per-Chunk Metadata

Each `Chunk` dataclass carries:

| Field | Description |
|---|---|
| `text` | Raw text content |
| `section_type` | One of 16 types, or `FULL` if no sections detected |
| `chunk_index` | Sequential index within the case |
| `case_id` | Parent case UUID |
| `page_number` | From page_map (optional) |
| `para_start`, `para_end` | Detected paragraph number range |
| `opinion_author` | Judge name from per-judge opinion boundary detection |
| `legal_signal` | Signal phrase density per 1000 chars |

### Legal Signal Scoring

16 signal phrases: "held that", "we hold", "in our opinion", "it is well settled", "the ratio", "we are of the view", "the principle", "we approve", "we overrule", "we distinguish", "the question is answered", "the appeal is allowed/dismissed", "we are of the considered view", "in our considered opinion", "we accordingly hold".

Formula: `count_of_phrases / len(text) * 1000` -- higher scores = more likely to contain holdings.

### Per-Judge Opinion Detection

Regex detects judge name headers like `D.Y. CHANDRACHUD, J.` or `[Per S. RAVINDRA BHAT, J.]`. Each chunk is assigned the `opinion_author` of the most recent preceding boundary.

---

## 4. Metadata Extraction

**File**: `backend/app/core/ingestion/metadata.py`

### CaseMetadata Fields (60+)

**Core**: title, citation, court, judge, author_judge, year, decision_date, case_type, bench_type, jurisdiction, petitioner, respondent, ratio_decidendi, acts_cited, cases_cited, citation_refs, keywords, disposal_nature

**Phase C (Legal completeness)**: coram_size, lower_court, lower_court_case_number, appeal_from, opinion_type (unanimous/majority/plurality/per_curiam), dissenting_judges, concurring_judges, split_ratio, petitioner_type, respondent_type, is_pil, companion_cases

**V2 (Judge Behavior / Citation Intelligence / Procedural)**: arguments_raised, relief_granted/sought, sentence_details, damages_awarded, judicial_tone, key_observations, hearing_count, citation_treatments, distinguished_cases, overruled_cases, legal_principles_applied, procedural_history, interim_orders, filing_date, urgency_indicators, party_counsel, issue_classification, fact_pattern_tags, operative_order, conditions_imposed, costs_awarded

**V3**: legal_propositions `[{proposition_text, paragraph_number, is_novel, related_section}]`, statute_sections_interpreted `[{section, act, interpretation_summary}]`, fact_pattern_summary

### LLM Extraction

`extract_metadata_llm(text, llm, pdf_path)`:

1. **PDF multimodal** (preferred): If `pdf_path` provided and LLM supports `generate_structured_from_pdf`, sends actual PDF for layout-aware extraction.
2. **Text fallback**: Head+tail truncation (30K head + 20K tail with `[...middle section truncated...]`), then `generate_structured()` with `METADATA_OUTPUT_SCHEMA`.
3. **Empty result check**: All-null response raises `RuntimeError` for retry.
4. **Schema filtering**: Only fields matching `CaseMetadata` field names are accepted.

### Judge Name Processing

Multi-stage pipeline:

1. **Parse**: Handles pipe/semicolon/comma-delimited strings; strips "Hon'ble", "Justice", "Mr. Justice", "Dr.", trailing ", J.", "JJ."
2. **Normalize**: Collapse spaces, normalize initials ("D. Y." -> "D.Y."), strip OCR artifacts.
3. **Canonical lookup**: 40+ known SC judge variants mapped (e.g., "dy chandrachud" -> "D.Y. Chandrachud").
4. **Header validation**: Surname (longest 4+ char word) must appear in first 2000 chars.
5. **Tenure validation**: Cross-reference against `_JUDGE_TENURE` dict (50+ entries); reject temporally impossible judges (grace +1 year).
6. **Deduplication**: By lowercased name.

### Merge Strategy (Parquet vs LLM)

| Field | Priority | Rationale |
|---|---|---|
| title, citation, court, year, decision_date, petitioner, respondent | **Parquet** | Reliably present in dataset |
| disposal_nature | **LLM** | Parquet has 67-81% NULLs |
| author_judge | **LLM** | Parquet has 0% for un-enriched cases |
| judge (array) | **Validated LLM** | LLM extracts full bench; Parquet usually only 1 name |
| ratio_decidendi, acts_cited, cases_cited, keywords, bench_type, jurisdiction | **LLM** | Semantic extraction from unstructured text |
| case_type | **LLM with normalization** | 27 abbreviation mappings (e.g., "slp(crl)" -> "Special Leave Petition") |

### Confidence Score

Weighted formula (0.0 - 1.0):

| Field | Weight |
|---|---|
| title, citation | 0.12 each |
| court, year | 0.10 each |
| judge | 0.08 |
| ratio_decidendi | 0.08 |
| decision_date | 0.06 |
| petitioner, respondent | 0.05 each |
| acts_cited, cases_cited | 0.05 each |
| keywords | 0.04 |
| case_type, disposal_nature | 0.03 each |
| bench_type, jurisdiction | 0.02 each |

Empty strings and empty lists count as absent. Score < 0.4 strips LLM fields; < 0.6 flags for review.

---

## 5. Embedding Configuration

**File**: `backend/app/core/providers/embeddings/gemini.py`

### Model and Dimensions

| Setting | Value |
|---|---|
| Model | `gemini-embedding-2-preview` (configurable via `settings.gemini_embedding_model`) |
| Dimensions | 1536 (Matryoshka output dimensionality control) |
| Context window | 8K tokens |

### Task Types

| Task Type | Used When | Purpose |
|---|---|---|
| `RETRIEVAL_DOCUMENT` | Ingestion (`embed_batch`) | Optimized for document storage |
| `RETRIEVAL_QUERY` | Search (`embed_text`) | Optimized for query representation |
| `SEMANTIC_SIMILARITY` | Specific comparison scenarios | Optimized for similarity comparison |

### AI Studio vs Vertex AI Paths

- **AI Studio**: Uses `genai.Client(api_key=...)` with SDK batch embedding in a single call.
- **Vertex AI**: The SDK's `:predict` endpoint returns 400 for `gemini-embedding-2-preview`. The provider works around this by calling the `:embedContent` REST endpoint directly via `httpx.AsyncClient`.

**Vertex AI batching** (since `:embedContent` only supports one content per call):

| Parameter | Default | Purpose |
|---|---|---|
| `EMBED_SUB_BATCH` | 5 | Sub-batch size |
| `EMBED_CONCURRENCY` | 3 | Max concurrent requests (semaphore) |
| `EMBED_SLEEP` | 0.5s | Delay between sub-batches |

### Retry Configuration

- 5 attempts, exponential backoff (2s min, 60s max)
- Retries on: `GoogleAPIError`, `ResourceExhausted`, `ServiceUnavailable`, `InternalServerError`, `ConnectionError`, `OSError`, `TimeoutError`, `httpx.ReadTimeout/ConnectTimeout/TimeoutException`
- 60s timeout per individual embed call

---

## 6. Vector Storage Schema (Pinecone)

**Files**: `backend/app/core/providers/vector/pinecone_store.py`, `backend/app/core/ingestion/pipeline.py`

### Index Configuration

- Single index, all vector types coexist
- 1536 dimensions (Gemini embedding)
- Connected via host URL (`PINECONE_HOST`) or index name

### 7 Vector Types

| `vector_type` | Source | ID Format | Description |
|---|---|---|---|
| `chunk` | Judgment text chunks | `{case_id}_{chunk_index}` | Standard 2000/1200-char text chunks |
| `proposition` | LLM-extracted propositions | `{case_id}_prop_{i}` | Direct legal-point vectors (min 20 chars) |
| `ratio` | LLM-extracted ratio decidendi | `{case_id}_ratio` | One per case (min 30 chars) |
| `headnote` | Structured headnotes | `{case_id}_headnote_{i}` | Reporter-style headnote propositions |
| `statute` | Statute section text | `{statute_id}_chunk_{i}` | Bare act section text (from `ingest_statutes.py`) |
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
    "text": str,                 # Chunk text (truncated to 2000 for 40KB metadata cap)
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

Proposition/ratio/headnote vectors carry the same base fields plus `related_section` and `is_novel` (propositions only), but without `chunk_index`, `opinion_author`, or page/char position fields.

### Metadata Filters at Search Time

`court`, `year` (range), `case_type`, `bench_type`, `jurisdiction`, `disposal_nature`, `acts_cited` (array contains), `vector_type`, `document_type`

### Circuit Breaker

All Pinecone operations go through `AsyncCircuitBreaker`:
- Opens after configurable failure threshold
- When open: upserts raise `CircuitBreakerOpen`; searches return empty results
- Retry: 3 attempts, exponential backoff (1-10s)
- Timeouts: upsert 120s, search 10s

---

## 7. Retrieval Pipeline

**Files**: `backend/app/core/chat/rag.py`, `backend/app/core/search/hybrid.py`, `backend/app/core/search/fulltext.py`, `backend/app/core/search/query.py`

### RAG Chat Flow

```
User question
    |
    v
1.  Session management (create or validate ownership)
    |
    v
2.  Load chat history (last MAX_HISTORY_MESSAGES messages)
    |
    v
2.5 Reformulate query with conversation context (if history exists)
    LLM rewrites follow-up questions as standalone queries.
    |
    v
3.  hybrid_search(search_query, ...) -> SearchResponse
    (see Hybrid Search Pipeline below)
    |
    v
4.  _build_sources(results, db) -> list[ChatSource]
    Fetches ratio_decidendi, bench_type, judge from PostgreSQL.
    Checks overruled status via graph (check_treatment_from_graph).
    |
    v
5.  _format_context(sources) -> context string
    Per source: citation, year, court, bench label, ratio, chunk text.
    Treatment warnings appended (e.g., "NOTE: This case was overruled by ...").
    Context truncated to MAX_SNIPPET_CHARS per source.
    |
    v
5.5 Prompt size guard:
    If user_prompt > 100K chars (~25K tokens):
      Truncate to 3 sources, last 4 history messages.
      Emit context_notice event to client.
    |
    v
6.  LLM streaming -> yields RAGEvent(type="chunk", data={"content": token})
    |
    v
7.  Source events -> RAGEvent(type="source", data={case_id, title, ...})
    |
    v
8.  Persist user + assistant messages (encrypted) to chat_messages table.
    |
    v
9.  Done event -> RAGEvent(type="done", data={tokens_used, source_count})
```

### Hybrid Search Pipeline

```
User query
    |
    v
1.  Redis cache check (hash of query + filters + page)
    |
    v
2.  Query understanding (LLM structured output)
    Extracts: intent, expanded_query, filters, entities, search_strategy
    Intent types:  citation_lookup, topic_search, case_search,
                   statute_search, judge_search, general
    Strategy types: vector_heavy, keyword_heavy, balanced, exact_match
    Skippable via pre_understood=True (agent optimization, saves ~2s)
    |
    v
2.5 Statute reference expansion
    IPC Section 302 -> also Section 103 BNS (and vice versa)
    Expanded terms added to FTS query with OR; vector search uses original only.
    |
    v
3.  Strategy-based retrieval:

    exact_match:
        _exact_citation_search -> direct lookup in cases + case_citation_equivalents
        If found: return immediately (no reranking)
        Fallback: FTS only

    vector_heavy / keyword_heavy / balanced:
        PARALLEL:
          a. _vector_search: embed query (RETRIEVAL_QUERY) -> Pinecone search
          b. search_fulltext: websearch_to_tsquery + phraseto_tsquery + ts_rank_cd
             Hindi queries: skip FTS (Devanagari not tokenizable by English tsvector)
    |
    v
4.  RRF merge
    Formula: RRF(d) = Sum(w_i / (k + rank_i(d)))

    | Strategy | Weights [vector, FTS] | k |
    |---|---|---|
    | keyword_heavy | [1.0, 2.0] | 40 |
    | vector_heavy | [2.0, 1.0] | 80 |
    | balanced | [1.0, 1.0] | 60 |
    | Hindi | [2.0, 0.0] | 80 (vector-only) |
    |
    v
5.  Rerank: Top N*2 candidates -> Cohere rerank-v4.0-pro
    On failure: falls back to RRF order.
    |
    v
6.  Paginate
    |
    v
7.  Enrich from PostgreSQL (title, citation, court, year, etc.)
    Adds equivalent_citations + treatment warnings.
    |
    v
8.  Build facets (court, year, case_type, bench_type distributions)
    |
    v
8b. Outcome bias check (for bail/sentence queries)
    |
    v
9.  Cache result to Redis
    |
    v
    Return SearchResponse {results, total_count, page, page_size,
                           query_understanding, facets,
                           outcome_bias_warning, search_degraded}
```

### FTS Implementation

**File**: `backend/app/core/search/fulltext.py`

| Setting | Value |
|---|---|
| Column | `searchable_text` (tsvector, computed by trigger from full_text + title + keywords + acts_cited) |
| Ranking | `ts_rank_cd` (cover density) -- chosen over `ts_rank`/BM25 for legal text (ADR-019) |
| Query parsing | `websearch_to_tsquery` for Google-like syntax (AND, OR, negation, quoted phrases) |
| Quoted phrases | Combined with `phraseto_tsquery` using `&&` for phrase proximity |
| Act filter | `normalize_act_name()` + `unnest()`/`EXISTS` for GIN-compatible array matching |

### Graceful Degradation

| Component Failure | Behavior |
|---|---|
| Vector search fails | FTS-only with `search_degraded = True` |
| FTS fails | Vector-only with warning |
| Reranker fails | RRF order preserved |
| Redis unavailable | No caching, continues normally |

---

## 8. Knowledge Graph Schema (Neo4j)

**Files**: `backend/app/core/providers/graph/neo4j_store.py`, `backend/app/core/graph/traversal.py`

### Node Labels

| Label | Primary Key | Key Properties |
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

| Relationship | Direction | Properties |
|---|---|---|
| `CITES` | Case -> Case | reporter, treatment (overruled/affirmed/distinguished/followed/not_followed/doubted/explained/per_incuriam/referred_to), context |
| `EQUIVALENT_TO` | Case -> Case | (citation equivalents, e.g., SCC and AIR for same case) |
| `APPLIES_DOCTRINE` | Case -> Doctrine | -- |
| `DECIDED_BY` | Case -> Judge | -- |
| `REPRESENTED_BY` | Case -> Counsel | -- |
| `APPLIES_PRINCIPLE` | Case -> LegalPrinciple | -- |
| `ADDRESSES` | Case -> Issue | -- |
| `BELONGS_TO` | Case -> Community | -- |
| `INTERPRETS` | Case -> Statute | interpretation_summary |
| `AUTHORED_BY` | Case -> Judge | -- |

### Placeholder Resolution

When a cited case is not yet in the database, a placeholder node is created with `id = "ref_{hex12}"` and `title = citation_text`. When the actual case is later ingested, the placeholder is promoted: its `id` is updated to the real UUID and all properties are set, preserving existing `CITES` edges.

### Graph Traversal Operations

**File**: `backend/app/core/graph/traversal.py`

| Operation | Description |
|---|---|
| `get_neighborhood(case_id, depth=1)` | Nodes and edges within N hops (max 3), capped at 200 nodes |
| `get_citation_chain(case_id, max_depth=3)` | Forward citation chain recursively (max 5 depth) |
| Authority ranking | Uses `cited_by_count` from graph |
| Statistics | Aggregated graph stats |

### Circuit Breaker

- 5 retry attempts, exponential backoff (2-30s)
- Retries on: `ServiceUnavailable`, `OSError`, `ConnectionError`
- Query timeout: 30s, connection pool: 50 max, 60s acquisition timeout

---

## 9. Agent Architecture

**Files**: `backend/app/core/agents/research.py`, `backend/app/core/agents/case_prep.py`, `backend/app/core/agents/drafting.py`, `backend/app/core/agents/strategy.py`

All agents use LangGraph `StateGraph` with typed state dictionaries, HITL checkpoints via `interrupt()`, and SSE streaming for real-time progress.

### 9.1 Research Agent V3

**File**: `backend/app/core/agents/research.py`

5-stage sequential-reactive pipeline:

```
Stage 1: UNDERSTAND
  rewrite_query -> classify -> statute_lookup -> element_decomposition
  -> route_by_complexity

Stage 2: INVESTIGATE (complex path)
  plan_research -> checkpoint_plan (HITL) -> dispatch_workers -> [Send() fan-out]

  Workers (parallel via Send):
    case_law_worker        hybrid_search for case law
    named_case_worker      DB lookup + IK search for specific cases
    statute_worker         statute section search in Pinecone + PG
    graph_worker           Neo4j citation graph traversal
    graph_community_worker GraphRAG community summaries
    ik_search_worker       Indian Kanoon external search
    web_search_worker      Tavily web search for recent developments

  Per-worker timeouts:
    web(10s), ik(45s), case_law(30s), named_case(30s),
    graph(15s), graph_community(10s), statute(20s)

Stage 3: EVALUATE
  gather_results -> batch_cot_with_reflection -> evaluate_and_extract
  -> gap_analysis -> [should_refine?]
  -> dispatch_workers (refinement, max 2) | checkpoint_findings (HITL)

Stage 4: CHALLENGE
  adversarial_search -> temporal_validation

Stage 5: SYNTHESIZE
  speculative_synthesis -> format_footnotes -> verify_v2 -> quality_check
  -> checkpoint_memo (HITL) -> END
```

**Fast path** (simple queries): Skips stages 2-4, goes directly to `fast_path_search -> fast_path_synthesis -> format_footnotes -> verify_v2 -> quality_check`.

**Key state fields** (`ResearchState` TypedDict):

| Field | Description |
|---|---|
| `query`, `rewritten_query` | Original and rewritten query |
| `complexity` | simple / moderate / complex / multi_issue |
| `research_plan` | list of `ResearchTask` with task_type, nl_query, boolean_query, filters, priority |
| `worker_results` | Annotated with `operator.add` reducer for Send() fan-out |
| `relevance_scores` | CRAG per-document evaluations (correct / ambiguous / incorrect) |
| `extracted_passages` | Verbatim passages with source tracking |
| `evidence_gaps` | Gaps with suggested_query and conditioned_on (MC-RAG) |
| `synthesis_drafts` | Speculative RAG parallel drafts (relevance / authority / recency strategies) |
| `footnotes` | Structured footnotes with verification_status |
| `statute_context`, `legal_elements`, `temporal_warnings` | V3 additions |
| `process_events` | Accumulated SSE events for real-time UI |

**Degenerate output detection**: Checks for LLM refusal loops, extreme repetition (same 50-char substring 5+ times), low alpha ratio (<25%), low character diversity (<15 unique chars), low word density.

### 9.2 Case Prep Agent

**File**: `backend/app/core/agents/case_prep.py`

```
START -> load_analysis -> prioritize -> checkpoint_issues (HITL) ->
deep_search -> argument_order -> checkpoint_strategy (HITL) ->
strategy_memo -> verify -> checkpoint_memo (HITL) -> END
```

Takes a previously analyzed document (from document upload pipeline), prioritizes issues, performs deep precedent search via citation graph, orders arguments, generates a strategy memo.

### 9.3 Drafting Agent

**File**: `backend/app/core/agents/drafting.py`

```
START -> [parse_opposing_doc (if opposing text)] -> resolve_template ->
gather_provisions -> verify_precedents -> checkpoint_sources (HITL) ->
draft_sections -> assemble -> checkpoint_draft (HITL) ->
verify_final -> checkpoint_final (HITL) -> END

Revision loop:
  checkpoint_draft --(feedback)--> revise_section -> assemble -> checkpoint_draft
```

Resolves a document template (e.g., bail application, writ petition), gathers relevant statutory provisions, drafts sections, and assembles the full document with iterative revision support.

### 9.4 Strategy Agent

**File**: `backend/app/core/agents/strategy.py`

```
START -> analyze_facts -> element_decomposition -> fetch_judge ->
checkpoint_analysis (HITL) -> search_precedents -> assess_strength ->
generate_arguments_irac -> checkpoint_arguments (HITL) ->
adversarial_search -> counter_and_judge -> argument_ordering ->
synthesize_strategy -> verify -> checkpoint_memo (HITL) -> END
```

Takes case facts and optional target judge/bench, generates IRAC-structured arguments, runs adversarial search for counter-arguments, provides judge-specific strategic notes, synthesizes an argument strategy memo.

### Common Agent Patterns

| Pattern | Description |
|---|---|
| **Dependency injection via closures** | Node functions receive dependencies (llm, db, etc.) when the graph is built, not at runtime |
| **Fresh DB sessions** | Nodes create sessions via `async_session_factory()` (FastAPI Depends session closes before StreamingResponse generator runs) |
| **HITL checkpoints** | `make_checkpoint_node(step_name)` calls `interrupt()`, pausing for user review. `make_feedback_router(step, retry_node, next_node)` routes on feedback |
| **SSE streaming** | `process_events` accumulates events: status, progress, checkpoint, memo, done, error |
| **Feedback routing** | `check_error=True` routes to END on error state |
| **Auto-approve** | `auto_approve=True` skips HITL checkpoints |
| **Worker fan-out** | Research agent uses `Send()` for parallel workers, results merged via `operator.add` reducer |

---

## 10. Prompt Templates

**Files**: `docs/PROMPT_LIBRARY.md`, `backend/app/core/legal/prompts.py`

### Metadata Extraction Prompt

- **System**: 16-rule specialized prompt for Indian court judgment metadata extraction. Rules enforce: extract only explicit content, array/null defaults, citation format requirements, enum constraints for bench_type/case_type/jurisdiction.
- **Output Schema**: Structured JSON with all CaseMetadata fields.
- **Few-Shot Examples**: 2 examples (Criminal Appeal + Constitutional Writ).

### Query Understanding Prompt

Legal search query analyzer for Indian law. Parses into: intent, expanded_query, filters, entities, search_strategy. Handles Indian legal abbreviations (SC, HC, IPC, CrPC, CPC, BNS, BNSS).

### Research Agent Prompts

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

`CHAT_SYSTEM_PROMPT` and `CHAT_USER_WITH_CONTEXT` -- legal research assistant grounded in retrieved case law with inline citations.

---

## 11. Legal Domain Logic

### 11.1 Citation Extraction

**File**: `backend/app/core/legal/extractor.py`

15+ citation formats recognized via compiled regex:

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
| HC reporters | 25+ regional (ILR, MLJ, KLT, BLR, etc.) | 2020 ILR 145 |
| LiveLaw | `YYYY LiveLaw (Court) NNN` | 2024 LiveLaw (SC) 123 |
| ITR | `[YYYY] Vol ITR Page` | [2020] 123 ITR 456 |
| Taxmann | `[YYYY] Vol taxmann.com NNN` | [2020] 123 taxmann.com 456 |
| Name-based | `Party v. Party` with context | "held in X v. Y" |

**GAN-style discriminator**: `classify_case_citations()` separates named citations ("X v. Y (2020) 3 SCC 145") from bare reporter refs ("(2020) 3 SCC 145"). Bare refs go to `citation_refs` for graph linking only.

### 11.2 Act/Section Extraction

42+ short act name mappings (IPC, CrPC, CPC, BNS, BNSS, BSA, NDPS, POCSO, NI, FEMA, RTI, SARFAESI, IBC, etc.).

Section patterns handle: "Section X of the Y Act", plural sections ("Sections 302, 304"), Order/Rule patterns, Schedule/Appendix references.

- `normalize_act_name()`: Converts abbreviations to full canonical names.
- `normalize_acts_cited_list()`: Deduplicates and normalizes an entire list.

### 11.3 Statute Cross-References

**File**: `backend/app/core/legal/constants.py`

Complete section-level mappings between old and new criminal codes:

| Old Code | New Code | Map Constant |
|---|---|---|
| IPC (Indian Penal Code, 1860) | BNS (Bharatiya Nyaya Sanhita, 2023) | 100+ sections |
| CrPC (Code of Criminal Procedure, 1973) | BNSS (Bharatiya Nagarik Suraksha Sanhita, 2023) | `CRPC_TO_BNSS_MAP` |
| IEA (Indian Evidence Act, 1872) | BSA (Bharatiya Sakshya Adhiniyam, 2023) | `EVIDENCE_TO_BSA_MAP` |

**Temporal guard** (`statute_enrichment.py`): Pre-2024 cases get old codes only; post-2024/unknown get bidirectional enrichment.

### 11.4 Court Hierarchy

**File**: `backend/app/core/legal/courts.py`

- Supreme Court + 25 High Courts + district courts + 20+ tribunals
- 200+ short-name to canonical full-name mappings
- AIR court code mapping (SC, All, Bom, Cal, Del, Mad, Kar, Ker, etc.)
- `normalize_court_name()`: Maps variants to canonical form
- `get_court_level()`: Returns "supreme", "high", "district", "tribunal", "unknown"

### 11.5 Precedent Strength

**File**: `backend/app/core/legal/precedent_strength.py`

Deterministic classification (no LLM):

```
classify_precedent_strength(source_court, source_bench,
                            target_court, target_bench, overruled)

    OVERRULED                          -> 0.0
    Supreme Court                      -> BINDING for all courts (1.0)
    Same court, larger bench           -> BINDING
    Same court, same/smaller bench     -> PERSUASIVE (0.6)
    Higher court                       -> BINDING
    Lower court                        -> PERSUASIVE
    Unknown                            -> UNKNOWN (0.4)
```

Bench hierarchy: constitutional (4) > full (3) > division (2) > single (1).
`coram_size` overrides bench label: 5+ = constitutional, 3-4 = full, 2 = division, 1 = single.

### 11.6 Citation Treatment

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

**Negative-first detection**: NOT_FOLLOWED patterns detected before FOLLOWED to prevent false positives.

**LLM fallback**: `classify_treatment_llm()` for ambiguous cases, gated by `enable_treatment_llm_fallback` config flag when regex confidence falls below threshold.

### 11.7 PII Anonymization

**File**: `backend/app/core/ingestion/anonymizer.py`

| PII Type | Pattern | Masking |
|---|---|---|
| Aadhaar | 12 digits (spaced groups of 4, or bare) | Masked |
| PAN | AAAPA9999A (4th char validated) | Masked |
| Phone | 10 digits starting 6-9, optional +91/91/0 prefix | Masked |
| Sensitive case | POCSO, IPC 354-376/509, BNS 63-79, keyword patterns | Flagged |

Masking order: spaced Aadhaar first (to avoid phone overlap), then phone (before bare Aadhaar), then bare Aadhaar, then PAN.

---

## 12. Batch Ingestion (Vertex AI)

### 12.1 Vertex AI Batch Pipeline

**File**: `backend/scripts/batch_ingest_vertex.py`

4-phase hybrid batch+online pipeline:

```
Phase 1: TEXT EXTRACTION + GCS UPLOAD
    For each PDF:
      extract_and_score(pdf_path) -> text quality
      Upload text to GCS: gs://smriti-batch-ingestion/{run_id}/texts/{filename}.txt
      Save progress to progress.json

Phase 2: BATCH METADATA EXTRACTION (50% cheaper)
    Build JSONL request file with METADATA_EXTRACTION_SYSTEM prompt
    Upload to GCS: gs://smriti-batch-ingestion/{run_id}/batch_request.jsonl
    Submit Vertex AI batch job (model: gemini-2.5-flash)
    Poll for completion
    Download + parse structured metadata from responses

Phase 3: ONLINE PROCESSING PER CASE
    For each case with extracted text + metadata:
      merge_metadata -> validate -> regex supplementation -> anonymize
      _insert_case (PostgreSQL)
      detect_judgment_sections + chunk_judgment
      Optional: batch_contextualize_chunks
      _embed_chunks -> _upsert_vectors (chunk + proposition + ratio + headnote)
      Optional: generate_section_summaries (RAPTOR)
      _build_citation_graph (Neo4j)
      Stale vector cleanup
      Update chunk_count + ingestion_status

Phase 4: QUALITY CHECK
    Sample 10 cases
    Check 5 vector types per case
    Verify PostgreSQL record completeness
```

| Setting | Value |
|---|---|
| Cost | ~$34/1K cases (~50% savings via batch pricing) |
| Resume | `--resume <run_id>` reloads `progress.json`, skips completed cases |
| Model | `gemini-2.5-flash` (NOT preview models -- unavailable on Vertex AI) |
| GCS bucket | `gs://smriti-batch-ingestion/` |

### 12.2 Turbo Ingestion Orchestrator

**File**: `ingestion/turbo_ingest.py`

Multi-account parallel orchestrator for full 35K-case ingestion:

- 4 accounts (a, b, c, d) with independent GCP service account credentials
- Progressive rollout: trial (50) -> small (500) -> medium (2000) -> full (remaining)
- Per-account environment files in `ingestion/accounts/env_{a,b,c,d}`
- Each account runs `batch_ingest_vertex.py` as a subprocess
- Commands: `--setup`, `--trial`, `--extract-all`, `--run`, `--resume`, `--status`, `--quality-check`, `--retry-failed`
- Queue-based workers with circuit breaker (10 failures)
- Graceful shutdown, download retries, ETA logging

### 12.3 Rate Limiting

**File**: `backend/app/core/ingestion/rate_limiter.py`

- `AsyncRateLimiter`: Token-bucket style, tracks timestamps in deque, blocks via `asyncio.sleep` when window full
- `RateLimiterPool`: Per-key rate limiters for API key rotation
- Default: 30 RPM per key, 60-second window

### 12.4 Graph Retry Queue

**File**: `backend/app/core/ingestion/graph_retry.py`

- `graph_build_queue` table: case_id, error, retry_count, timestamps
- `record_graph_failure()`: INSERT ON CONFLICT DO UPDATE
- `get_pending_retries()`: WHERE retry_count < max_retries ORDER BY created_at
- Max 3 retries per case

---

## 13. How to Add New Case Law

Based on the ingestion pipeline described above, adding new case law follows this path:

1. **Obtain the PDF** -- Source is `s3://indian-supreme-court-judgments/` (CC-BY-4.0, no auth needed). Download via HTTPS (no AWS CLI required).

2. **Obtain Parquet metadata** -- The dataset includes Parquet files with 19 metadata fields per case (title, citation, court, year, etc.).

3. **Single-case ingestion**: Call `ingest_judgment(pdf_path, parquet_row, db, llm, embedder, vector_store, graph_store, storage)` from `backend/app/core/ingestion/pipeline.py`. This runs the full pipeline (extract -> metadata -> chunk -> embed -> Pinecone -> Neo4j).

4. **Batch ingestion** (cheaper): Use `backend/scripts/batch_ingest_vertex.py` for bulk ingestion. Phase 2 uses Vertex AI batch pricing (50% cheaper). Resume with `--resume <run_id>` if interrupted.

5. **Multi-account at scale**: Use `ingestion/turbo_ingest.py` with 4 GCP accounts for 35K-case runs. Progressive rollout: trial (50) -> small (500) -> medium (2000) -> full.

6. **Statutes**: Use `ingest_statutes.py` for bare act section text (vector_type="statute").

7. **Verify after ingestion**:
   - **PostgreSQL**: `SELECT * FROM cases WHERE citation = '...'` -- confirm metadata fields populated
   - **Pinecone**: Search by `case_id` metadata filter -- confirm chunk + proposition + ratio vectors exist
   - **Neo4j**: `MATCH (c:Case {citation: '...'}) RETURN c` -- confirm node and CITES edges

---

## 14. How to Debug Retrieval Issues

### "Search returns no results"

1. **Check query understanding**: Look at the `query_understanding` field in the `SearchResponse`. Is the intent correct? Is `search_strategy` set to `exact_match` when it should be `balanced`?
2. **Check FTS**: Run a direct `websearch_to_tsquery` query against the `searchable_text` column. Remember: Hindi queries skip FTS entirely.
3. **Check vector search**: Embed the query with `RETRIEVAL_QUERY` task type and search Pinecone directly. Check if metadata filters are too restrictive.
4. **Check statute expansion**: If searching for IPC sections, verify that the old-to-new code mapping (`IPC_TO_BNS_MAP`, etc.) is expanding correctly.

### "Search returns irrelevant results"

1. **Check reranker**: Is Cohere reranker running? If it fails silently, results fall back to RRF order which may be less precise.
2. **Check RRF weights**: The strategy weights determine vector vs FTS balance. `keyword_heavy` doubles FTS weight; `vector_heavy` doubles vector weight.
3. **Check vector types**: The agent worker applies 1.5x RRF boost for proposition/ratio/headnote vectors. Main search does not.
4. **Check chunk quality**: Low text quality tier ("low") may indicate OCR issues or garbled text in the source PDF.

### "Chat gives wrong citations"

1. **Check treatment warnings**: Is `check_treatment_from_graph` returning overruled status? Neo4j circuit breaker may be open.
2. **Check source enrichment**: `_build_sources` fetches ratio and bench_type from PostgreSQL. If DB is slow, sources may be incomplete.
3. **Check prompt size guard**: If the user prompt exceeds 100K chars, context is truncated to 3 sources and 4 history messages.

### "Ingestion failed for a case"

1. **Check `ingestion_status`**: In PostgreSQL, check the `ingestion_status` column (complete / needs_review / failed).
2. **Check `audit_logs`**: `_record_ingestion_failure()` writes error details to the `audit_logs` table.
3. **Check `graph_build_queue`**: If graph build failed, the case is queued for retry (max 3).
4. **Check for orphan vectors**: If DB rolled back but vectors were already upserted, the pipeline should have cleaned them. Verify by searching Pinecone for the case_id.
5. **Check confidence score**: Score < 0.4 strips LLM fields; < 0.6 flags for review. Low confidence may indicate poor PDF quality.

---

## Key Environment Variables

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
