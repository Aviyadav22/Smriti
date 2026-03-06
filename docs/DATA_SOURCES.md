# Smriti — Data Sources & Ingestion Pipeline

---

## 1. Primary Data Source: AWS Open Data

### Indian Supreme Court Judgments

| Property | Value |
|----------|-------|
| **Bucket** | `s3://indian-supreme-court-judgments/` |
| **License** | CC-BY-4.0 (commercial use allowed with attribution) |
| **Coverage** | 1950–2025 |
| **Total** | ~35,000 English judgments |
| **Size** | ~52 GB |
| **Update frequency** | Bi-monthly |
| **Source** | ecourts.gov.in |
| **Managed by** | Dattam Labs (Pradeep Vanga) |
| **Contact** | contact@dattam.in |
| **Auth required** | No (public, `--no-sign-required`) |

### S3 Bucket Structure

```
s3://indian-supreme-court-judgments/
├── data/
│   ├── tar/
│   │   └── year=YYYY/
│   │       ├── english/
│   │       │   ├── english.tar            (or part-TIMESTAMP.tar if >1GB)
│   │       │   └── english.index.json
│   │       └── regional/
│   │           ├── regional.tar
│   │           └── regional.index.json
│   └── zip/
│       └── year=YYYY/
│           ├── english.zip
│           └── regional.zip
└── metadata/
    ├── tar/
    │   └── year=YYYY/
    │       ├── metadata.tar
    │       └── metadata.index.json
    └── parquet/
        └── year=YYYY/
            └── metadata.parquet
```

### Parquet Metadata Schema (19 Fields)

| Field | Type | Description | Maps To |
|-------|------|-------------|---------|
| `title` | STRING | Case title | cases.title |
| `petitioner` | STRING | Petitioner name(s) | cases.petitioner |
| `respondent` | STRING | Respondent name(s) | cases.respondent |
| `description` | STRING | Case description | cases.description |
| `judge` | STRING | Judge(s) who delivered | cases.judge (parse to array) |
| `author_judge` | STRING | Authoring judge | cases.author_judge |
| `citation` | STRING | Legal citation | cases.citation |
| `case_id` | STRING | Case identifier | cases.case_id |
| `cnr` | STRING | Case Number Register | cases.cnr |
| `decision_date` | DATE | Date of judgment | cases.decision_date |
| `disposal_nature` | STRING | How disposed | cases.disposal_nature |
| `court` | STRING | Court designation | cases.court |
| `available_languages` | STRING | Available languages | cases.available_languages |
| `raw_html` | STRING | Original HTML | (discard — extract text from PDF) |
| `path` | STRING | S3 file path | cases.s3_source_path |
| `nc_display` | STRING | Nature of case | cases.case_type (normalize) |
| `scraped_at` | TIMESTAMP | When scraped | (internal tracking) |
| `year` | INTEGER | Year (partition key) | cases.year |

### Index File Format

```json
{
    "parts": [
        {
            "name": "english.tar",
            "file_count": 1234,
            "size_bytes": 1073741824,
            "size_human": "1.0 GB",
            "created_at": "2025-01-15T10:30:00Z"
        }
    ],
    "total_size_bytes": 1073741824,
    "total_files": 1234
}
```

### Access Methods

```bash
# List years
aws s3 ls s3://indian-supreme-court-judgments/data/tar/ --no-sign-request

# Download one year of English judgments
aws s3 cp s3://indian-supreme-court-judgments/data/tar/year=2024/english/english.tar ./data/ --no-sign-request

# Download metadata parquet
aws s3 cp s3://indian-supreme-court-judgments/metadata/parquet/year=2024/metadata.parquet ./data/ --no-sign-request

# HTTPS direct download (no AWS CLI needed)
curl -O https://indian-supreme-court-judgments.s3.amazonaws.com/data/zip/year=2024/english.zip
```

### Indian High Court Judgments (Phase 2)

| Property | Value |
|----------|-------|
| **Bucket** | `s3://indian-high-court-judgments/` |
| **Coverage** | 25 High Courts |
| **Total** | ~16.7 million judgments |
| **Size** | ~1.11 TB |
| **License** | CC-BY-4.0 |
| **Managed by** | Dattam Labs |

---

## 2. Secondary Data Sources

### IndianKanoon API

| Property | Value |
|----------|-------|
| **URL** | https://api.indiankanoon.org/ |
| **Coverage** | 30M+ orders/decisions, 24 HCs, 17 Tribunals |
| **Auth** | API key (public-private key crypto) |
| **Free tier** | Rs 500 credit for development |
| **Non-commercial** | Rs 10,000/month free (requires verification) |
| **Commercial** | Licensing available (contact required) |
| **Formats** | JSON, XML |
| **Python library** | ikapi.py |
| **Newer API** | kanoon.dev (Node.js library available) |

**Use case for Smriti**: Supplementary data source. If a case isn't in the S3 dataset, try IndianKanoon.

### IndiaCode (Bare Acts)

| Property | Value |
|----------|-------|
| **URL** | https://www.indiacode.nic.in/ |
| **Coverage** | All Central and State Acts |
| **Access** | Free, public |
| **Format** | HTML pages |

**Use case**: Reference for statute sections. Link out to IndiaCode for full act text.

### Legislative.gov.in

| Property | Value |
|----------|-------|
| **URL** | https://www.legislative.gov.in/ |
| **Coverage** | Central legislation, year-wise |
| **Access** | Free, public |

### SCC Online & Manupatra (Future Partnerships)

- **SCC Online** (scconline.com): Most comprehensive. Premium subscription. Potential API partnership.
- **Manupatra** (manupatrafast.com): Updated daily. Flexible licensing. Contact: contact@manupatra.com

**Not for MVP**: These require paid partnerships. Consider for Phase 3+.

---

## 3. Ingestion Pipeline Design

### Architecture

```
DATA SOURCE                    INGESTION PIPELINE                              STORAGE

S3 Bucket    ──→ Download ──→ Extract ──→ Parse ──→ Enrich ──→ Chunk ──→ Embed ──→ Store
(tar/zip)        (year)       (PDFs)     (text)    (meta)    (legal)   (vec)     (multi)
                                │          │         │         │         │         │
                                ▼          ▼         ▼         ▼         ▼         ▼
                             Local FS   pdfplumber Gemini  LegalChunker Gemini  PostgreSQL
                                        +Tesseract 3.1 Pro  (sections) embed   Pinecone
                                                   JSON                 -004    Neo4j
                                                                                GCS
```

### Pipeline Steps (Per Judgment)

```python
async def ingest_judgment(pdf_path: str, parquet_metadata: dict) -> str:
    """
    Full ingestion pipeline for one judgment.
    Returns: case_id (UUID)
    """

    # 1. EXTRACT TEXT
    text = extract_pdf_text(pdf_path)          # pdfplumber
    if not text or len(text) < 100:
        text = extract_with_ocr(pdf_path)      # Tesseract fallback

    # 2. MERGE METADATA (Parquet fields + LLM extraction)
    parquet_meta = normalize_parquet(parquet_metadata)
    llm_meta = await extract_metadata_llm(text) # Gemini structured output
    metadata = merge_metadata(parquet_meta, llm_meta)
    # Parquet wins for: title, petitioner, respondent, case_id, cnr, court, year, decision_date
    # LLM wins for: ratio_decidendi, acts_cited, cases_cited, keywords, bench_type

    # 3. VALIDATE METADATA (regex patterns as sanity checks)
    metadata = validate_with_regex(metadata)    # Catch LLM hallucinations

    # 4. STORE PDF to GCS/local
    storage_path = await store_pdf(pdf_path, metadata)

    # 5. INSERT TO POSTGRESQL
    case_id = await insert_case(metadata, text, storage_path)

    # 6. DETECT SECTIONS
    sections = detect_judgment_sections(text)    # Facts, Arguments, Ratio, Order

    # 7. LEGAL-AWARE CHUNKING
    chunks = chunk_judgment(text, sections)      # 2000 chars, 200 overlap, section-tagged

    # 8. GENERATE EMBEDDINGS
    embeddings = await embed_chunks(chunks)      # Gemini gemini-embedding-001

    # 9. UPSERT TO PINECONE
    await upsert_vectors(case_id, chunks, embeddings, metadata)

    # 10. BUILD CITATION GRAPH
    cited_cases = metadata.get("cases_cited", [])
    await build_citation_edges(case_id, cited_cases)  # Neo4j

    return case_id
```

### Bulk Ingestion Script (`scripts/ingest_s3.py`)

```
Usage:
  python scripts/ingest_s3.py --year 2024              # Ingest one year
  python scripts/ingest_s3.py --year-from 2020 --year-to 2024  # Range
  python scripts/ingest_s3.py --all                     # Everything
  python scripts/ingest_s3.py --resume                  # Resume interrupted run

Features:
  - Downloads tar/zip + parquet metadata per year
  - Processes judgments in batches (configurable batch size)
  - Progress tracking: stores processed doc IDs in a local SQLite tracker
  - Resume support: skips already-ingested documents
  - Rate limiting for Gemini API calls (avoid quota exhaustion)
  - Error logging: failed documents logged for retry
  - Parallel processing: configurable concurrency (default: 5)
  - Estimated time: ~2 seconds per judgment (text + LLM + embed + store)
  - 1 year (~500-1500 judgments) ≈ 20-50 minutes
```

### Metadata Merge Strategy

The Parquet metadata from S3 provides structured fields, but some are missing or need enrichment. We combine with LLM extraction:

| Field | Parquet Source | LLM Source | Winner |
|-------|---------------|------------|--------|
| title | `title` | Extracted | Parquet (authoritative) |
| citation | `citation` | Regex from text | Parquet, LLM fills gaps |
| court | `court` | Extracted | Parquet |
| year | `year` | From citation/date | Parquet |
| decision_date | `decision_date` | Extracted | Parquet |
| petitioner | `petitioner` | Extracted | Parquet |
| respondent | `respondent` | Extracted | Parquet |
| judge | `judge` | Extracted | Parquet (parse to array) |
| author_judge | `author_judge` | Extracted | Parquet |
| case_type | `nc_display` | Extracted | Merge (nc_display + LLM) |
| disposal_nature | `disposal_nature` | Extracted | Parquet |
| **ratio_decidendi** | Not available | **LLM only** | LLM |
| **acts_cited** | Not available | **LLM only** | LLM |
| **cases_cited** | Not available | **LLM only** | LLM |
| **keywords** | Not available | **LLM only** | LLM |
| **bench_type** | Not available | **LLM only** | LLM |
| **jurisdiction** | Not available | **LLM only** | LLM |

### Cost Estimation (Gemini 2.5 Pro for Metadata Extraction)

```
Per judgment:
  - Average judgment: ~20,000 tokens input
  - Structured output: ~500 tokens output
  - Cost: 20K × $2/1M + 500 × $12/1M = $0.04 + $0.006 = ~$0.046

Per year (1000 judgments):
  - ~$46

Full SC dataset (35K judgments):
  - ~$1,610 (within $300 credits if done in batches with strategic model choice)

Optimization: Use Gemini Flash for bulk extraction (~10x cheaper),
              reserve 3.1 Pro for complex/important cases.
```

---

## 4. Legal Considerations

### CC-BY-4.0 License Requirements

The AWS dataset is licensed under Creative Commons Attribution 4.0:

- **You CAN**: Use commercially, modify, distribute, sublicense
- **You MUST**: Give appropriate credit to Dattam Labs, indicate changes made, include license notice
- **Attribution format**: "Indian Supreme Court Judgments dataset by Dattam Labs, licensed under CC-BY-4.0"
- **Display**: Include attribution in About/Credits page

### Indian Court Judgment Copyright

- Indian court judgments are **public domain** (not copyrightable as government works)
- The dataset compilation and metadata are covered by CC-BY-4.0
- Users can freely view, download, and cite any judgment
- No copyright issues with displaying judgment text

### Data Residency

- S3 bucket is in `ap-south-1` (Mumbai region)
- For DPDP Act compliance, user data (not judgment data) should stay in India
- GCP Cloud Run in `asia-south1` (Mumbai) satisfies this requirement
