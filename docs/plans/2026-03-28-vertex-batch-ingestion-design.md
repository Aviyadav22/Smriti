# Vertex AI Batch Ingestion Pipeline Design

**Date**: 2026-03-28
**Status**: Approved
**Goal**: Ingest remaining ~31K Supreme Court judgments using Vertex AI with GCP free credits ($300/account), maximizing quality while minimizing cost via batch API (50% discount on LLM calls).

## Context

### Problem
- Current pipeline (`ingest_s3.py`) uses AI Studio API keys with online Gemini calls
- Cost: ~$0.11/case = ~$3,400 for 31K cases on paid accounts
- Free trial credits available across multiple GCP accounts ($300 each)

### Validated Assumptions
- **Vertex AI batch supports `responseSchema` + PDF multimodal + `systemInstruction`** (verified via A/B test on 2026-03-28)
- **Batch vs online quality is equivalent**: title, citation, court, year, judges all match; array fields 75-100% overlap; text fields within 97% length
- **`gemini-2.5-flash` available on Vertex AI** for both batch and online inference
- **`gemini-embedding-2-preview` works on Vertex AI** with 1536-dim output
- **Service account auth (ADC)** working with `google-genai` SDK `vertexai=True`

### Cost Estimate

| Component | Model | Mode | Cost/1K cases |
|-----------|-------|------|---------------|
| Metadata extraction | gemini-2.5-flash | Batch (50% off) | ~$15 |
| Contextual prefixes | gemini-2.5-flash | Online | ~$12 |
| RAPTOR summaries | gemini-2.5-flash | Online | ~$5 |
| Embeddings | gemini-embedding-2-preview | Online | ~$2 |
| **Total** | | | **~$34/1K** |

- 31K cases total: ~$1,054
- ~3.5 GCP accounts needed ($300 credits each)

## Architecture

### 4-Phase Hybrid Batch + Online Pipeline

```
Phase 1 (CPU, ~5 min/1K)          Phase 2 (Batch LLM, ~30 min wait)
+---------------------+           +---------------------------+
| For each case:      |           | Vertex AI Batch Job       |
| - Download PDF      |--JSONL--->| gemini-2.5-flash          |
| - Extract text      |           | PDF multimodal            |
| - Dedup check (PG)  |           | + responseSchema          |
| - Upload PDF to GCS |           | + systemInstruction       |
| - Build manifest    |           | 50% cost discount         |
+---------------------+           +-------------+-------------+
                                                |
                                                v metadata results
Phase 3 (Online LLM + Embed, ~2-3 hrs/1K cases)
+----------------------------------------------------------+
| For each case (sequential, rate-limited):                |
|                                                          |
| A. Process batch metadata result                         |
|    - Validate with regex                                 |
|    - Merge with parquet                                  |
|    - Cross-validate propositions                         |
|    - Supplement acts_cited with regex                    |
|    - Insert case into PostgreSQL                         |
|                                                          |
| B. Chunk text (CPU)                                      |
|    - detect_judgment_sections()                          |
|    - chunk_judgment()                                    |
|    - Insert case_sections + statute_interpretations      |
|    - Insert citation_equivalents                         |
|                                                          |
| C. Contextual prefixes (flash, online, 10 concurrent)   |
|    - 1 LLM call per chunk via batch_contextualize_chunks |
|    - Prepend prefix to chunk text                        |
|                                                          |
| D. Embed ALL vectors (online, embedding-2-preview)       |
|    - Batch 1: chunk texts (100 per API call)             |
|    - Batch 2: proposition + ratio + headnote texts       |
|                                                          |
| E. RAPTOR summaries (flash, online)                      |
|    - 1 LLM call per section via generate_section_summaries|
|    - Embed all summaries                                 |
|                                                          |
| F. Upsert ALL vectors to Pinecone                        |
|    - 5 vector types: chunk, proposition, ratio,          |
|      headnote, summary                                   |
|    - Stale vector cleanup                                |
|                                                          |
| G. Build citation graph (Neo4j)                          |
|    - Case node + CITES edges + Counsel + Principles      |
|    - Issue nodes + APPLIES_PRINCIPLE + ADDRESSES          |
|                                                          |
| H. Update PG: chunk_count, ingestion_status=complete     |
+----------------------------------------------------------+

Phase 4 (Quality Check, ~2 min)
+---------------------------------+
| - Sample 10 random cases        |
| - Check all 5 vector types exist|
| - Verify PG fields populated    |
| - Print extraction confidence   |
| - Flag cases < 0.5 confidence   |
+---------------------------------+
```

## Phase Details

### Phase 1: Prepare & Extract Text

**Input**: S3 tar files + parquet metadata per year
**Output**: `{run_dir}/manifest.json` + PDFs uploaded to GCS

Steps per case:
1. Download PDF from S3 (HTTPS, public bucket)
2. Extract text via `extract_and_score()` (pdfplumber + OCR fallback)
3. Skip PII anonymization (already handled server-side in prod)
4. Compute `text_hash`, check PG for duplicates
5. Upload PDF to `gs://smriti-batch-ingestion/pdfs/{case_id}.pdf`
6. Record in manifest: `{case_id, pdf_gcs_uri, extracted_text, text_hash, parquet_metadata, quality_tier}`

**Skip conditions**:
- Text extraction fails (< 50 chars)
- Duplicate text_hash already exists in PG with chunk_count > 0

### Phase 2: Batch Metadata Extraction

**Input**: Manifest from Phase 1
**Output**: `{run_dir}/metadata_results.json`

Steps:
1. Build JSONL file — one line per case:
   ```json
   {
     "request": {
       "model": "gemini-2.5-flash",
       "contents": [
         {"role": "user", "parts": [
           {"fileData": {"fileUri": "gs://smriti-batch-ingestion/pdfs/{case_id}.pdf", "mimeType": "application/pdf"}},
           {"text": "<METADATA_EXTRACTION_USER prompt>"}
         ]}
       ],
       "systemInstruction": {"parts": [{"text": "<METADATA_EXTRACTION_SYSTEM>"}]},
       "generationConfig": {
         "temperature": 0.1,
         "responseMimeType": "application/json",
         "responseSchema": "<METADATA_OUTPUT_SCHEMA>"
       }
     }
   }
   ```
2. Upload JSONL to GCS
3. Submit Vertex AI batch job (`client.batches.create()`)
4. Poll until `JOB_STATE_SUCCEEDED` (check every 2 min)
5. Download output JSONL from GCS
6. Parse responses, map back to case_ids (using JSONL line order)
7. Save to `metadata_results.json`

**Error handling**:
- If batch job fails, log error and allow manual retry
- Individual case failures (no candidates) logged and skipped
- Quality gate: if >10% of cases have no metadata, abort

### Phase 3: Online Processing (Sequential Per Case)

**Input**: Manifest + metadata results
**Output**: Fully ingested cases in PG + Pinecone + Neo4j

For each case, reuse existing pipeline functions:

#### A. Metadata Processing
- `validate_with_regex(metadata)`
- `validate_cross_fields(metadata)`
- `cross_validate_propositions(metadata)`
- `extract_acts_cited(full_text)` — regex supplementation
- `normalize_acts_cited_list()`
- `enrich_statute_cross_references()`
- `compute_extraction_confidence()`
- Merge with `validate_parquet_data(parquet_metadata)`

#### B. PostgreSQL Insert
- Insert case record with all metadata fields
- Insert `case_sections` (one per detected section)
- Insert `case_statute_interpretations` (from metadata.statute_sections_interpreted)
- Insert `case_citation_equivalents` (from extracted citations)

#### C. Contextual Prefixes (Online LLM)
- Model: `gemini-2.5-flash` via Vertex AI
- Function: `batch_contextualize_chunks()` (existing, batch_size=10 concurrent)
- ~50 calls per case, ~500ms-2s each
- Prepends 1-2 sentence prefix to each chunk text

#### D. Embedding Generation (Online)
- Model: `gemini-embedding-2-preview` via Vertex AI
- Function: `_embed_chunks()` + `_upsert_proposition_vectors()` (existing)
- Batch size: 100 texts per API call
- Produces all 5 vector types:
  1. **chunk**: contextualized chunk text → 1536-dim
  2. **proposition**: metadata.legal_propositions[].proposition_text → 1536-dim
  3. **ratio**: metadata.ratio_decidendi → 1536-dim
  4. **headnote**: metadata.headnotes[].proposition → 1536-dim
  5. **summary**: RAPTOR section summaries → 1536-dim

#### E. RAPTOR Summaries (Online LLM)
- Model: `gemini-2.5-flash` via Vertex AI
- Function: `generate_section_summaries()` (existing)
- ~8 calls per case (one per section >= 200 chars)
- Embed summaries, create summary vectors

#### F. Pinecone Upsert
- All 5 vector types with full metadata
- Vector IDs: `{case_id}_{chunk_index}`, `{case_id}_prop_{i}`, `{case_id}_ratio`, `{case_id}_headnote_{i}`, `{case_id}_summary_{section_type}`
- Metadata per vector:
  - case_id, title (200ch), citation, court, year, case_type, bench_type
  - disposal_nature, author_judge, judge (max 20), acts_cited (max 25)
  - document_type="case_law", vector_type, section_type
  - jurisdiction, judicial_tone, fact_pattern_tags (max 5), issue_classification (max 5)
  - text (2000ch), legal_signal, para_start/end, page_start/end, char_start/end
- Stale vector cleanup after upsert

#### G. Neo4j Graph
- MERGE Case node
- CITES edges with treatment detection
- Counsel nodes + REPRESENTED_BY edges
- LegalPrinciple nodes + APPLIES_PRINCIPLE edges
- Issue nodes + ADDRESSES edges
- Citation equivalents + EQUIVALENT_TO edges

#### H. Finalize
- UPDATE cases SET chunk_count=N, ingestion_status='complete'
- Commit transaction

### Phase 4: Quality Check

After each 1K batch run:
1. Sample 10 random cases from the batch
2. For each sampled case:
   - Query Pinecone for all vectors with this case_id
   - Verify 5 vector types present (chunk, proposition, ratio, headnote, summary)
   - Verify chunk count matches PG chunk_count
   - Verify proposition count matches metadata.legal_propositions length
   - Read PG record, check key fields non-null (title, citation, court, year, judge, ratio_decidendi)
   - Print extraction_confidence score
3. Flag any case with:
   - extraction_confidence < 0.5
   - Missing vector types
   - chunk_count = 0
4. Print summary: total ingested, success rate, avg confidence, flagged cases

## Vectors Required by Research Agent

The research agent queries these vector types with specific behavior:

| Vector Type | Agent Query | RRF Boost | Filter |
|-------------|-------------|-----------|--------|
| chunk | hybrid_search (FTS + vector) | 1.0x | court, year, bench_type, etc. |
| proposition | case_law_worker secondary query | **1.5x** | vector_type $in [proposition, ratio, headnote] |
| ratio | case_law_worker secondary query | **1.5x** | (same) |
| headnote | case_law_worker secondary query | **1.5x** | (same) |
| summary | hybrid_search | 1.0x | vector_type filter |

**All 5 vector types are mandatory** for full research agent functionality.

## Dependency Chain (Critical Path)

```
PDF Extract (CPU)
    |
    v
LLM Metadata Extraction (BATCH) --- produces ratio, propositions, headnotes
    |
    v
Regex Validation + Parquet Merge (CPU)
    |
    v
PostgreSQL Insert (DB)
    |
    v
Chunking (CPU) --- produces chunk texts + section detection
    |
    v
Contextual Prefixes (ONLINE LLM) --- 1 call per chunk, needs chunk text + case metadata
    |
    v
Embed Chunks (ONLINE EMBED) --- needs contextualized chunk texts
    |
    +---> Embed Propositions/Ratio/Headnotes (ONLINE EMBED) --- needs metadata from step 2
    |
    v
RAPTOR Summaries (ONLINE LLM) --- 1 call per section, needs section texts
    |
    v
Embed RAPTOR Summaries (ONLINE EMBED)
    |
    v
Pinecone Upsert (all 5 vector types)
    |
    v (parallel, non-blocking)
Neo4j Graph Build
```

Every step depends on the previous one. No steps can be reordered.

## Script Interface

```bash
# Full run: 1K cases from a specific year
python scripts/batch_ingest_vertex.py --year 2020 --limit 1000

# Full run: all remaining cases across all years
python scripts/batch_ingest_vertex.py --all --limit 1000

# Resume Phase 3 from existing batch results
python scripts/batch_ingest_vertex.py --resume batch_run_20260328_1400

# Quality check on a completed run
python scripts/batch_ingest_vertex.py --quality-check batch_run_20260328_1400

# Dry run (Phase 1 only, no API calls)
python scripts/batch_ingest_vertex.py --year 2020 --limit 10 --dry-run
```

## Configuration

New env vars in `.env`:
```
GEMINI_USE_VERTEXAI=true
GEMINI_VERTEXAI_PROJECT=project-9642efb2-7b75-4a7d-811
GEMINI_VERTEXAI_LOCATION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=<path-to-service-account-json>
```

GCS bucket: `gs://smriti-batch-ingestion/`
- `pdfs/` — uploaded PDFs for batch processing
- `batch-jobs/` — JSONL input/output for batch jobs
- `runs/` — manifest and metadata results per run

## Error Handling

| Error | Handling |
|-------|----------|
| PDF extraction fails | Skip case, log to manifest as failed |
| Duplicate text_hash | Skip case (already ingested) |
| Batch job fails | Log, allow manual retry from Phase 2 |
| Individual metadata empty | Log, skip case in Phase 3 |
| Contextual prefix LLM fails | Graceful fallback: use raw chunk text (existing behavior) |
| RAPTOR summary LLM fails | Skip summary vectors for that section (existing behavior) |
| Embedding fails | Retry 5x with exponential backoff (existing tenacity) |
| Pinecone upsert fails | Retry, mark case as vectors_failed |
| Neo4j fails | Log, non-critical (existing behavior) |
| GCP credits exhausted | Script detects 403, pauses, prompts to switch account |

## Reuse from Existing Pipeline

The batch script reuses these existing functions directly (no reimplementation):

| Function | From | Used in |
|----------|------|---------|
| `extract_and_score()` | ingestion/pdf.py | Phase 1 |
| `validate_parquet_data()` | ingestion/metadata.py | Phase 3A |
| `validate_with_regex()` | ingestion/metadata.py | Phase 3A |
| `validate_cross_fields()` | ingestion/metadata.py | Phase 3A |
| `cross_validate_propositions()` | ingestion/metadata.py | Phase 3A |
| `merge_metadata()` | ingestion/metadata.py | Phase 3A |
| `compute_extraction_confidence()` | ingestion/metadata.py | Phase 3A |
| `extract_acts_cited()` | legal/extractor.py | Phase 3A |
| `normalize_acts_cited_list()` | legal/extractor.py | Phase 3A |
| `enrich_statute_cross_references()` | legal/statute_enrichment.py | Phase 3A |
| `detect_judgment_sections()` | ingestion/chunker.py | Phase 3B |
| `chunk_judgment()` | ingestion/chunker.py | Phase 3B |
| `batch_contextualize_chunks()` | ingestion/contextual_embeddings.py | Phase 3C |
| `_embed_chunks()` | ingestion/pipeline.py | Phase 3D |
| `_upsert_proposition_vectors()` | ingestion/pipeline.py | Phase 3D |
| `generate_section_summaries()` | ingestion/section_summarizer.py | Phase 3E |
| `_upsert_vectors()` | ingestion/pipeline.py | Phase 3F |
| `_build_citation_graph()` | ingestion/pipeline.py | Phase 3G |
| `detect_treatment_in_text()` | legal/treatment.py | Phase 3G |

## Non-Goals

- No changes to the existing online pipeline (`ingest_s3.py`) — it stays as-is for single-case ingestion
- No changes to the research agent — batch pipeline produces identical output
- No changes to the frontend — data format is identical
- No PII anonymization in batch pipeline — already handled server-side
