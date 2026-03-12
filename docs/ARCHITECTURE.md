# Smriti — System Architecture

> Purpose-built Indian legal research platform.
> Harvey AI for Indian law.

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Data Flow Diagrams](#data-flow-diagrams)
3. [RAG Pipeline Design](#rag-pipeline-design)
4. [Auth Flow](#auth-flow)
5. [Security Architecture](#security-architecture)
6. [Modular Interface Pattern](#modular-interface-pattern)
7. [Infrastructure (GCP)](#infrastructure-gcp)
8. [Document Upload Pipeline](#document-upload-pipeline)
9. [Audio Digest Pipeline](#audio-digest-pipeline)
10. [Background Task Architecture (Celery)](#background-task-architecture-celery)
11. [Agent Execution Architecture (LangGraph)](#agent-execution-architecture-langgraph)
12. [Complete API Endpoint Inventory](#complete-api-endpoint-inventory)
13. [Celery Task Pipeline Detail](#celery-task-pipeline-detail)
14. [Admin Workflows](#admin-workflows)
15. [DPDP Compliance Architecture](#dpdp-compliance-architecture)
16. [Document Upload & Analysis Flow](#document-upload--analysis-flow)
17. [Audio Digest Generation Flow](#audio-digest-generation-flow)
18. [Judge Analytics Module](#judge-analytics-module)
19. [Security Architecture Detail](#security-architecture-detail)

---

## System Overview

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              CLIENTS                                        │
│         Browser (Next.js 15 SPA)  /  Mobile (future)  /  API consumers      │
└──────────────────────────┬───────────────────────────────────────────────────┘
                           │ HTTPS (TLS 1.3)
                           ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                      GOOGLE CLOUD LOAD BALANCER                             │
│                   (SSL termination, path-based routing)                      │
│                                                                              │
│        /*  ──────────► Cloud Run (Next.js 15 Frontend)                      │
│        /api/v1/*  ───► Cloud Run (FastAPI Backend)                          │
└──────────────────────────┬───────────────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                     FASTAPI BACKEND (Python 3.12)                           │
│                                                                              │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌──────────┐ ┌────────┐ ┌──────────┐ ┌────────┐ │
│  │ Search │ │ Ingest │ │  Chat  │ │  Auth  │ │ Citation │ │ Judges │ │Documents │ │ Audio  │ │
│  │ Router │ │ Router │ │ Router │ │ Router │ │ Graph    │ │ Router │ │ Router   │ │ Router │ │
│  └───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘ └────┬─────┘ └───┬────┘ └────┬─────┘ └───┬────┘ │
│      │          │          │          │           │           │           │           │      │
│  ┌───▼──────────▼──────────▼──────────▼───────────▼───────────▼───────────▼───────────▼───┐  │
│  │                             CORE SERVICE LAYER                                         │  │
│  │  HybridSearchOrchestrator / IngestionPipeline / ChatEngine / RBAC                      │  │
│  │  JudgeAnalytics / DocumentAnalyzer / AudioDigest                                       │  │
│  └───┬──────────┬──────────┬──────────┬───────────┬───────────┬───────────┬───────────┬───┘  │
│      │          │          │          │           │           │           │           │      │
│  ┌───▼──────────▼──────────▼──────────▼───────────▼───────────▼───────────▼───────────▼───┐  │
│  │                          PROVIDER INTERFACE LAYER                                      │  │
│  │  LLMProvider / VectorStore / EmbeddingProvider / Reranker / GraphStore                 │  │
│  │  TTSProvider / FileStorage                                                             │  │
│  └───────────────────────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────┬───────────────────────────────────────────────────┘
                           │
          ┌────────────────┼────────────────┬──────────────┬───────────────┐
          ▼                ▼                ▼              ▼               ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌───────────┐ ┌────────────┐
│  PostgreSQL  │ │   Pinecone   │ │   Neo4j      │ │   Redis   │ │    GCS     │
│  (Cloud SQL) │ │  (Vectors)   │ │  AuraDB      │ │ (Upstash) │ │  (PDFs)    │
│              │ │              │ │  (Graph)     │ │           │ │            │
│ - metadata   │ │ - 1536-dim   │ │ - citation   │ │ - cache   │ │ - original │
│ - FTS index  │ │   embeddings │ │   edges      │ │ - sessions│ │   PDFs     │
│ - users      │ │ - cosine     │ │ - traversals │ │ - rate    │ │ - sharded  │
│ - audit log  │ │   similarity │ │              │ │   limits  │ │   storage  │
└──────────────┘ └──────────────┘ └──────────────┘ └─────┬─────┘ └────────────┘
                                                         │ (broker, DB 1)
                                                         ▼
                                                  ┌──────────────┐
                                                  │ Celery Worker │
                                                  │              │
                                                  │ - document   │
                                                  │   analysis   │
                                                  │ - audio      │
                                                  │   generation │
                                                  │ - future     │
                                                  │   async tasks│
                                                  └──────────────┘
```

---

## Data Flow Diagrams

### 1. Document Ingestion Flow

```
┌─────────┐    ┌──────────┐    ┌───────────────┐    ┌────────────────────┐
│  Source  │───►│ Download │───►│ PDF Extractor │───►│  Section Parser    │
│  (S3 /  │    │  to GCS  │    │ (PyMuPDF +    │    │  (Facts, Ratio,    │
│  Upload)│    │          │    │  OCR fallback)│    │   Order, etc.)     │
└─────────┘    └──────────┘    └───────────────┘    └────────┬───────────┘
                                                             │
                                                             ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                    METADATA EXTRACTION (Gemini 2.5 Pro)                  │
│                                                                          │
│  Structured JSON output:                                                 │
│  {                                                                       │
│    "case_name": "...",                                                   │
│    "citation": "...",                                                    │
│    "court": "Supreme Court of India",                                    │
│    "bench": ["Justice A", "Justice B"],                                  │
│    "date": "2024-01-15",                                                 │
│    "case_type": "Criminal Appeal",                                       │
│    "statutes_cited": ["IPC Section 302", "CrPC Section 161"],            │
│    "cases_cited": ["(2020) 5 SCC 1", "AIR 1978 SC 597"],                │
│    "headnotes": "...",                                                   │
│    "outcome": "Appeal Dismissed"                                         │
│  }                                                                       │
│                                                                          │
│  + Regex validation pass (citation format, date format, court name)      │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     │
                                     ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                   CHUNKING (Section-Aware)                               │
│                                                                          │
│  Each section → split into chunks of ~2000 chars with 200-char overlap   │
│  Each chunk carries: doc_id, section_type, chunk_index, metadata         │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     │
                      ┌──────────────┼──────────────┐
                      ▼              ▼              ▼
             ┌──────────────┐ ┌───────────┐ ┌──────────────┐
             │   Embedding  │ │ PostgreSQL│ │    Neo4j     │
             │   (Gemini    │ │  INSERT   │ │  Citation    │
             │  text-embed- │ │ metadata  │ │  Graph       │
             │  ding-004)   │ │ + FTS     │ │  Edges       │
             │      │       │ │ tsvector  │ │              │
             │      ▼       │ │           │ │ (CITES)      │
             │  Pinecone    │ │           │ │ (CITED_BY)   │
             │  upsert      │ │           │ │ (OVERRULES)  │
             └──────────────┘ └───────────┘ └──────────────┘
```

**Step-by-step breakdown:**

| Step | Component | Action | Output |
|------|-----------|--------|--------|
| 1 | Downloader | Fetch PDF from source (S3, upload, URL) | Raw PDF in GCS |
| 2 | PDFExtractor | Extract text via PyMuPDF; OCR fallback via Tesseract | Raw text string |
| 3 | SectionDetector | Identify judgment sections using heading patterns | List of `(section_type, text)` |
| 4 | MetadataExtractor | Gemini structured output + regex validation | `CaseMetadata` object |
| 5 | LegalChunker | Section-aware chunking (2000 chars, 200 overlap) | List of `Chunk` objects |
| 6 | EmbeddingProvider | Gemini gemini-embedding-001 (1536-dim) | List of float vectors |
| 7 | VectorStore | Pinecone upsert with metadata filters | Indexed vectors |
| 8 | PostgreSQL | Insert case metadata + tsvector column | Searchable row |
| 9 | GraphStore | Create case node + citation edges in Neo4j | Graph updated |

---

### 2. Search Flow

```
                         User Query
                             │
                             ▼
                 ┌───────────────────────┐
                 │   Query Understanding │
                 │   (Gemini 2.5 Pro)    │
                 │                       │
                 │  Input: raw query     │
                 │  Output: {            │
                 │    intent,            │
                 │    entities,          │
                 │    filters,           │
                 │    reformulated_query │
                 │  }                    │
                 └───────────┬───────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
     ┌──────────────┐ ┌───────────┐ ┌──────────────┐
     │   Pinecone   │ │ PostgreSQL│ │  PostgreSQL   │
     │   Vector     │ │   FTS     │ │  Metadata     │
     │   Search     │ │  Search   │ │  Filter       │
     │              │ │           │ │               │
     │ embed(query) │ │ ts_rank_  │ │ WHERE court=  │
     │ → top 20     │ │ cd(query) │ │  AND year>=   │
     │ by cosine    │ │ → top 20  │ │  AND type=    │
     └──────┬───────┘ └─────┬─────┘ └──────┬───────┘
            │               │              │
            └───────────────┼──────────────┘
                            ▼
                 ┌───────────────────────┐
                 │  Reciprocal Rank      │
                 │  Fusion (RRF)         │
                 │  k = 60               │
                 │                       │
                 │  Merge → top 20       │
                 └───────────┬───────────┘
                             │
                             ▼
                 ┌───────────────────────┐
                 │  Cohere Rerank v3     │
                 │                       │
                 │  Rerank top 20 →      │
                 │  Return top 5         │
                 └───────────┬───────────┘
                             │
                             ▼
                 ┌───────────────────────┐
                 │  Enrich Results       │
                 │                       │
                 │  Fetch full metadata  │
                 │  from PostgreSQL      │
                 │  Attach court info,   │
                 │  bench, date, etc.    │
                 └───────────┬───────────┘
                             │
                             ▼
                     SearchResponse
```

---

### 3. Chat Flow

```
User Message
     │
     ▼
┌─────────────────────────┐
│  Context Retrieval       │
│  (Hybrid Search)         │
│                          │
│  Same pipeline as        │
│  Search Flow above,      │
│  but with conversation   │
│  history for query       │
│  reformulation           │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────────┐
│                     PROMPT CONSTRUCTION                         │
│                                                                 │
│  System: You are Smriti, an Indian legal research assistant.    │
│          Always cite sources. Use legal terminology precisely.  │
│                                                                 │
│  Context: [Retrieved chunks with metadata]                      │
│    - Chunk 1: {text, source: "AIR 2023 SC 450", section: ...}  │
│    - Chunk 2: {text, source: "(2022) 3 SCC 100", section: ...} │
│    ...                                                          │
│                                                                 │
│  Conversation History: [last N turns]                           │
│                                                                 │
│  User: {current message}                                        │
│                                                                 │
│  Instructions: Cite every factual claim using [source].         │
│                If unsure, say so. Do not hallucinate cases.     │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
              ┌──────────────────────────┐
              │  Gemini 2.5 Pro          │
              │  (Streaming Generation)  │
              │                          │
              │  temperature: 0.1        │
              │  max_tokens: 4096        │
              │  stream: true            │
              └────────────┬─────────────┘
                           │
                           ▼
              ┌──────────────────────────┐
              │  SSE Response            │
              │                          │
              │  event: token            │
              │  data: {"text": "..."}   │
              │                          │
              │  event: citation         │
              │  data: {"ref": "...",    │
              │         "case_id": "..."}│
              │                          │
              │  event: done             │
              │  data: {"usage": {...}}  │
              └──────────────────────────┘
```

---

### 4. Citation Graph Flow

```
                    Query Case ID
                         │
                         ▼
              ┌───────────────────────┐
              │  Neo4j Graph Query    │
              │                       │
              │  MATCH (c:Case {id})  │
              │                       │
              │  Traversal types:     │
              │  ─ CITES (outgoing)   │
              │  ─ CITED_BY (incoming)│
              │  ─ OVERRULES          │
              │  ─ FOLLOWS            │
              │  ─ DISTINGUISHES      │
              └───────────┬───────────┘
                          │
              ┌───────────┼───────────┐
              ▼           ▼           ▼
       ┌───────────┐ ┌────────┐ ┌──────────┐
       │  Cases    │ │ Cases  │ │ Citation │
       │  Cited    │ │ Citing │ │ Chain    │
       │  by this  │ │ this   │ │ (depth   │
       │  case     │ │ case   │ │  traversal│
       └─────┬─────┘ └───┬────┘ └────┬─────┘
             │            │           │
             └────────────┼───────────┘
                          ▼
              ┌───────────────────────┐
              │  Enrich from          │
              │  PostgreSQL           │
              │                       │
              │  case_name, court,    │
              │  date, outcome for    │
              │  each node            │
              └───────────┬───────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │  Visualization Data   │
              │                       │
              │  {                    │
              │    nodes: [...],      │
              │    edges: [...],      │
              │    stats: {           │
              │      total_citing,    │
              │      total_cited,     │
              │      overruled: bool  │
              │    }                  │
              │  }                    │
              └───────────────────────┘
```

---

## RAG Pipeline Design

This is the core of Smriti's intelligence. The Retrieval-Augmented Generation (RAG) pipeline ensures accurate, cited, and hallucination-resistant legal answers.

### Stage 1: Query Understanding

Gemini 2.5 Pro receives the raw user query and produces structured JSON:

```json
{
  "intent": "case_law_search",
  "entities": {
    "statute": "Section 498A IPC",
    "legal_concept": "cruelty to wife",
    "court": "Supreme Court of India"
  },
  "filters": {
    "court": "supreme_court",
    "year_from": 2015,
    "case_type": "criminal_appeal"
  },
  "reformulated_query": "Supreme Court judgments on Section 498A IPC cruelty to wife after 2015",
  "is_follow_up": false
}
```

**Why LLM-based query understanding?**
Indian legal queries are complex. A user might write: "What did SC say about 498A misuse recently?" — we need to:
- Expand "SC" to "Supreme Court of India"
- Understand "498A" refers to Section 498A of the Indian Penal Code
- Interpret "recently" as a year filter (e.g., last 5 years)
- Identify intent as case law search (not statute lookup)

### Stage 2: Parallel Retrieval (Three Channels)

All three channels execute concurrently via `asyncio.gather()`:

#### Channel A: Vector Search (Semantic)
```python
# Embed the reformulated query
query_embedding = await embedding_provider.embed(reformulated_query)

# Search Pinecone with metadata filters
vector_results = await pinecone.query(
    vector=query_embedding,
    top_k=20,
    filter={
        "court": {"$eq": "supreme_court"},
        "year": {"$gte": 2015}
    },
    include_metadata=True
)
# Returns: [(doc_id, score, metadata), ...]
```

**Strengths**: Captures semantic similarity — "cruelty to wife" matches "domestic violence" or "matrimonial cruelty."
**Weaknesses**: May miss exact citation matches or specific section numbers.

#### Channel B: Full-Text Search (Lexical)
```sql
SELECT doc_id, chunk_text,
       ts_rank_cd(search_vector, plainto_tsquery('english', :query)) AS rank
FROM document_chunks
WHERE search_vector @@ plainto_tsquery('english', :query)
ORDER BY rank DESC
LIMIT 20;
```

`ts_rank_cd` uses cover density ranking, which considers the proximity of matching lexemes. This is superior to `ts_rank` for legal text because legal arguments often have relevant terms clustered together.

**Strengths**: Exact matches for case citations, section numbers, specific legal phrases.
**Weaknesses**: Misses semantic variations ("murder" won't match "homicide").

#### Channel C: Metadata Filter
```sql
SELECT doc_id
FROM cases
WHERE court = :court
  AND date >= :year_from
  AND case_type = :case_type;
```

This returns a set of document IDs that match the structured filters. These IDs are used as a boost signal in the RRF merge — if a document appears in both a retrieval channel AND the metadata filter, its score gets an additional boost.

### Stage 3: Reciprocal Rank Fusion (RRF)

**Formula:**

```
RRF_score(d) = Σ  1 / (k + rank_i(d))
               i∈channels
```

Where:
- `d` is a document
- `k` is a constant (we use **k=60**, the standard value from the original Cormack et al. 2009 paper)
- `rank_i(d)` is the rank of document `d` in channel `i` (1-indexed; if absent, treated as infinity → contributes 0)

**Example calculation:**

| Document | Vector Rank | FTS Rank | Metadata Match | RRF Score |
|----------|-------------|----------|----------------|-----------|
| Doc A    | 1           | 3        | Yes (+0.5 boost) | 1/61 + 1/63 + 0.5 = 0.0164 + 0.0159 + 0.5 = 0.5323 |
| Doc B    | 2           | 1        | No             | 1/62 + 1/61 = 0.0161 + 0.0164 = 0.0325 |
| Doc C    | 5           | -        | Yes (+0.5 boost) | 1/65 + 0 + 0.5 = 0.5154 |
| Doc D    | -           | 2        | No             | 0 + 1/62 = 0.0161 |

**Why RRF over weighted sum?**

1. **Rank-invariant**: RRF uses ranks, not raw scores. Vector search scores (cosine: 0-1) and BM25 scores (unbounded positive) are on incompatible scales. Normalizing them is fragile. RRF sidesteps this entirely.
2. **Robust to outliers**: A single channel returning an irrelevant high-scoring result won't dominate — it still only contributes `1/(k+1)` at most.
3. **No tuning required**: Weighted sum needs weight hyperparameters (e.g., 0.7 vector + 0.3 BM25) that change as your data distribution shifts. RRF with k=60 works well out of the box.
4. **Proven in IR literature**: RRF consistently matches or beats trained fusion models in TREC evaluations.

### Stage 4: Reranking

```python
reranked = await cohere_reranker.rerank(
    query=original_query,
    documents=[result.text for result in merged_top_20],
    model="rerank-v4.0-pro",
    top_n=5
)
```

**Why rerank after fusion?**

RRF gives us a good candidate set, but a cross-encoder (Cohere rerank-v4.0-pro) can do pairwise query-document attention — something neither vector search nor BM25 can do. The reranker reads both the query and each document together, producing a much more accurate relevance score.

We rerank the top 20 (not all results) to keep latency under 500ms. The final top 5 are returned.

### Stage 5: Context Construction

Retrieved chunks are assembled into a structured prompt:

```
CONTEXT:
[1] Source: Arnesh Kumar v. State of Bihar, (2014) 8 SCC 273
    Court: Supreme Court of India | Section: Ratio Decidendi
    Text: "... the Magistrate should not authorize detention casually
    and mechanically... Section 498-A was intended to protect women
    from cruelty, not to be used as a weapon..."

[2] Source: Rajesh Sharma v. State of UP, (2017) 10 SCC 257
    Court: Supreme Court of India | Section: Order
    Text: "... Family Welfare Committees to be constituted in every
    district to look into complaints of Section 498-A..."

[3] ...
```

### Stage 6: Generation

```python
response = await gemini.generate_stream(
    model="gemini-3.1-pro",
    messages=[system_prompt, context_block, conversation_history, user_message],
    temperature=0.1,      # Low for factual accuracy
    max_tokens=4096,
    response_format="text"
)
```

The system prompt instructs Gemini to:
- Cite every factual claim using `[1]`, `[2]` notation
- Never fabricate case names or citations
- Clearly state when information is not found in the provided context
- Use precise Indian legal terminology

---

## Auth Flow

### Registration

```
Client                    Backend                   PostgreSQL
  │                          │                          │
  │  POST /api/v1/auth/register                         │
  │  {email, password, name} │                          │
  │─────────────────────────►│                          │
  │                          │ validate input (Pydantic) │
  │                          │ check email uniqueness    │
  │                          │─────────────────────────►│
  │                          │ hash = bcrypt(password,   │
  │                          │         rounds=12)        │
  │                          │ INSERT user               │
  │                          │─────────────────────────►│
  │                          │                          │
  │                          │ generate JWT access token │
  │                          │ (15 min expiry)           │
  │                          │ generate refresh token    │
  │                          │ (7 day expiry)            │
  │                          │ store refresh token hash  │
  │                          │─────────────────────────►│
  │  200 {access_token,      │                          │
  │       refresh_token,     │                          │
  │       user}              │                          │
  │◄─────────────────────────│                          │
```

### Login

```
Client                    Backend                   PostgreSQL
  │                          │                          │
  │  POST /api/v1/auth/login │                          │
  │  {email, password}       │                          │
  │─────────────────────────►│                          │
  │                          │ fetch user by email       │
  │                          │─────────────────────────►│
  │                          │◄─────────────────────────│
  │                          │                          │
  │                          │ bcrypt.verify(password,   │
  │                          │               user.hash)  │
  │                          │                          │
  │                          │ if valid:                 │
  │                          │   issue access_token (15m)│
  │                          │   issue refresh_token (7d)│
  │                          │   log login event         │
  │                          │─────────────────────────►│
  │  200 {access_token,      │                          │
  │       refresh_token}     │                          │
  │◄─────────────────────────│                          │
  │                          │                          │
  │                          │ if invalid:               │
  │  401 {error}             │   increment failed count  │
  │◄─────────────────────────│   check lockout threshold │
```

### Protected Route Access

```
Client                    Backend                   PostgreSQL
  │                          │                          │
  │  GET /api/v1/search      │                          │
  │  Authorization: Bearer   │                          │
  │  <access_token>          │                          │
  │─────────────────────────►│                          │
  │                          │ decode JWT                │
  │                          │ verify signature (HS256)  │
  │                          │ check expiry              │
  │                          │ extract user_id + role    │
  │                          │                          │
  │                          │ RBAC check:               │
  │                          │   role.has_permission(    │
  │                          │     "search:read"         │
  │                          │   )                       │
  │                          │                          │
  │                          │ audit log entry           │
  │                          │─────────────────────────►│
  │                          │                          │
  │                          │ execute request           │
  │  200 {results}           │                          │
  │◄─────────────────────────│                          │
```

### Token Refresh

```
Client                    Backend                   PostgreSQL
  │                          │                          │
  │  POST /api/v1/auth/      │                          │
  │       refresh             │                          │
  │  {refresh_token}         │                          │
  │─────────────────────────►│                          │
  │                          │ hash(refresh_token)       │
  │                          │ lookup in DB              │
  │                          │─────────────────────────►│
  │                          │◄─────────────────────────│
  │                          │                          │
  │                          │ verify not expired (7d)   │
  │                          │ verify not revoked        │
  │                          │                          │
  │                          │ ROTATE:                   │
  │                          │   revoke old refresh      │
  │                          │   issue new refresh (7d)  │
  │                          │   issue new access (15m)  │
  │                          │─────────────────────────►│
  │  200 {access_token,      │                          │
  │       refresh_token}     │                          │
  │◄─────────────────────────│                          │
```

**Token rotation** prevents replay attacks: each refresh token can be used exactly once. If a stolen token is used after the legitimate user has already refreshed, the stolen token is invalid and the system detects potential compromise.

---

## Security Architecture

### Input Validation Layer

Every API request passes through Pydantic models before reaching business logic:

```python
class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    filters: Optional[SearchFilters] = None
    page_size: int = Field(default=10, ge=1, le=50)

    @field_validator("query")
    @classmethod
    def sanitize_query(cls, v: str) -> str:
        # Strip control characters, normalize unicode
        return unicodedata.normalize("NFC", v.strip())
```

All user-supplied strings are sanitized. SQL queries use parameterized statements exclusively (SQLAlchemy ORM). No string interpolation in queries.

### Rate Limiting

Implemented as FastAPI middleware backed by Redis:

| Tier | Limit | Window | Scope |
|------|-------|--------|-------|
| Anonymous | 10 requests | 1 minute | Per IP |
| Authenticated (free) | 60 requests | 1 minute | Per user |
| Authenticated (pro) | 300 requests | 1 minute | Per user |
| Ingestion endpoints | 10 requests | 10 minutes | Per user |
| Auth endpoints | 5 requests | 1 minute | Per IP |

Rate limit state is stored in Redis using a sliding window counter pattern. Response headers include `X-RateLimit-Remaining` and `X-RateLimit-Reset`.

### Audit Logging

Every data access event is logged to PostgreSQL:

```python
class AuditLog(BaseModel):
    timestamp: datetime
    user_id: Optional[UUID]
    action: str          # "search", "view_case", "download_pdf", "login"
    resource_type: str   # "case", "user", "document"
    resource_id: str
    ip_address: str
    user_agent: str
    metadata: dict       # query text, filters used, etc.
```

Audit logs are append-only (no UPDATE/DELETE permissions on the audit table). They are retained for 2 years per DPDP Act requirements.

### Encryption

| Layer | Method | Details |
|-------|--------|---------|
| Transit | TLS 1.3 | Enforced at load balancer; HSTS header |
| At rest (database) | Cloud SQL encryption | Google-managed keys (CMEK available) |
| At rest (sensitive fields) | AES-256-GCM | User PII fields encrypted at application layer |
| At rest (GCS) | Google-managed encryption | Default SSE; CMEK available |
| Passwords | bcrypt | 12 rounds, per-password salt |
| Tokens | HMAC-SHA256 | Refresh tokens stored as SHA-256 hashes |

### DPDP Act Compliance

India's Digital Personal Data Protection Act, 2023 requires:

1. **Consent**: Users explicitly consent to data collection at registration. Consent is versioned and timestamped.
2. **Purpose limitation**: Personal data used only for stated purposes (search, recommendations).
3. **Right to erasure**: `DELETE /api/v1/user/me` triggers full data deletion pipeline — user record, search history, audit logs (anonymized, not deleted), cached data.
4. **Data breach notification**: Automated alerting if anomalous access patterns detected. Notification to Data Protection Board within 72 hours.
5. **Data localization**: All user data stored in GCP `asia-south1` (Mumbai) region.

---

## Modular Interface Pattern

Smriti uses Python `Protocol` classes (structural subtyping) to define interfaces for all external dependencies. This enables:
- Swapping providers without changing business logic
- Easy testing with mock implementations
- Gradual migration between services

### Interface Definitions

```python
# core/interfaces/llm.py
from typing import Protocol, AsyncIterator

class LLMProvider(Protocol):
    async def generate(
        self, messages: list[Message], **kwargs
    ) -> LLMResponse: ...

    async def generate_stream(
        self, messages: list[Message], **kwargs
    ) -> AsyncIterator[str]: ...

    async def generate_structured(
        self, messages: list[Message], schema: type[BaseModel], **kwargs
    ) -> BaseModel: ...
```

```python
# core/interfaces/vector_store.py
class VectorStore(Protocol):
    async def upsert(
        self, vectors: list[VectorRecord]
    ) -> None: ...

    async def query(
        self, vector: list[float], top_k: int,
        filters: Optional[dict] = None
    ) -> list[VectorSearchResult]: ...

    async def delete(
        self, ids: list[str]
    ) -> None: ...
```

```python
# core/interfaces/embedding.py
class EmbeddingProvider(Protocol):
    async def embed(self, text: str) -> list[float]: ...
    async def embed_batch(self, texts: list[str]) -> list[list[float]]: ...
    @property
    def dimensions(self) -> int: ...
```

```python
# core/interfaces/reranker.py
class Reranker(Protocol):
    async def rerank(
        self, query: str, documents: list[str], top_n: int
    ) -> list[RerankResult]: ...
```

```python
# core/interfaces/graph_store.py
class GraphStore(Protocol):
    async def add_case(self, case: CaseNode) -> None: ...
    async def add_citation(self, from_id: str, to_id: str, rel_type: str) -> None: ...
    async def get_cited_by(self, case_id: str, depth: int = 1) -> list[CaseNode]: ...
    async def get_cites(self, case_id: str, depth: int = 1) -> list[CaseNode]: ...
    async def get_citation_chain(self, case_id: str, max_depth: int = 3) -> GraphData: ...
```

```python
# core/interfaces/file_storage.py
class FileStorage(Protocol):
    async def upload(self, path: str, data: bytes, content_type: str) -> str: ...
    async def download(self, path: str) -> bytes: ...
    async def get_signed_url(self, path: str, expiry_seconds: int = 3600) -> str: ...
    async def delete(self, path: str) -> None: ...
```

### Dependency Injection

Provider selection happens at application startup via a factory pattern:

```python
# core/providers/factory.py
from core.config import Settings

def create_llm_provider(settings: Settings) -> LLMProvider:
    match settings.llm_provider:
        case "gemini":
            from core.providers.gemini import GeminiLLM
            return GeminiLLM(
                api_key=settings.gemini_api_key,
                model=settings.gemini_model,   # "gemini-3.1-pro"
            )
        case "openai":
            from core.providers.openai import OpenAILLM
            return OpenAILLM(api_key=settings.openai_api_key)
        case _:
            raise ValueError(f"Unknown LLM provider: {settings.llm_provider}")

def create_vector_store(settings: Settings) -> VectorStore:
    match settings.vector_store:
        case "pinecone":
            from core.providers.pinecone import PineconeStore
            return PineconeStore(
                api_key=settings.pinecone_api_key,
                index_name=settings.pinecone_index,  # "smriti-legal"
            )
        case _:
            raise ValueError(f"Unknown vector store: {settings.vector_store}")

# ... similar for EmbeddingProvider, Reranker, GraphStore, FileStorage
```

These factories are called once in the FastAPI `lifespan` and injected via `Depends()`:

```python
# api/dependencies.py
from fastapi import Depends

async def get_llm(request: Request) -> LLMProvider:
    return request.app.state.llm_provider

async def get_vector_store(request: Request) -> VectorStore:
    return request.app.state.vector_store

# Usage in routes:
@router.post("/search")
async def search(
    req: SearchRequest,
    llm: LLMProvider = Depends(get_llm),
    vector_store: VectorStore = Depends(get_vector_store),
    reranker: Reranker = Depends(get_reranker),
):
    orchestrator = HybridSearchOrchestrator(llm, vector_store, reranker)
    return await orchestrator.search(req)
```

### Adding a New Provider (Step by Step)

Example: Adding **Qdrant** as an alternative vector store.

**Step 1**: Create implementation file.
```
core/providers/qdrant.py
```

**Step 2**: Implement the `VectorStore` protocol.
```python
# core/providers/qdrant.py
from qdrant_client import AsyncQdrantClient
from core.interfaces.vector_store import VectorStore, VectorRecord, VectorSearchResult

class QdrantStore:
    """Implements VectorStore protocol for Qdrant."""

    def __init__(self, url: str, api_key: str, collection_name: str):
        self.client = AsyncQdrantClient(url=url, api_key=api_key)
        self.collection = collection_name

    async def upsert(self, vectors: list[VectorRecord]) -> None:
        points = [self._to_point(v) for v in vectors]
        await self.client.upsert(collection_name=self.collection, points=points)

    async def query(
        self, vector: list[float], top_k: int, filters: dict | None = None
    ) -> list[VectorSearchResult]:
        results = await self.client.search(
            collection_name=self.collection,
            query_vector=vector,
            limit=top_k,
            query_filter=self._build_filter(filters),
        )
        return [self._to_result(r) for r in results]

    async def delete(self, ids: list[str]) -> None:
        await self.client.delete(collection_name=self.collection, points_selector=ids)
```

**Step 3**: Add configuration to `Settings`.
```python
# core/config.py
class Settings(BaseSettings):
    vector_store: str = "pinecone"  # or "qdrant"
    qdrant_url: Optional[str] = None
    qdrant_api_key: Optional[str] = None
    qdrant_collection: str = "smriti-legal"
```

**Step 4**: Add to factory.
```python
# core/providers/factory.py
def create_vector_store(settings: Settings) -> VectorStore:
    match settings.vector_store:
        case "pinecone":
            from core.providers.pinecone import PineconeStore
            return PineconeStore(...)
        case "qdrant":
            from core.providers.qdrant import QdrantStore
            return QdrantStore(
                url=settings.qdrant_url,
                api_key=settings.qdrant_api_key,
                collection_name=settings.qdrant_collection,
            )
```

**Step 5**: Set environment variable.
```bash
VECTOR_STORE=qdrant
QDRANT_URL=https://your-qdrant-instance.cloud
QDRANT_API_KEY=...
```

No business logic changes required. The `HybridSearchOrchestrator` continues to call `vector_store.query()` without knowing whether it is talking to Pinecone or Qdrant.

---

## Infrastructure (GCP)

### Deployment Topology

```
                        ┌─────────────────────────────────────┐
                        │      Google Cloud Platform          │
                        │         asia-south1 (Mumbai)        │
                        │                                     │
                        │  ┌──────────────────────────────┐   │
Internet ──► HTTPS ────►│  │  Cloud Load Balancer          │   │
                        │  │  (Global, SSL termination)    │   │
                        │  │                                │   │
                        │  │  /*       ──► Cloud Run        │   │
                        │  │               (Next.js 15)     │   │
                        │  │               Frontend         │   │
                        │  │               - SSR / SSG      │   │
                        │  │               - 0→10 instances │   │
                        │  │               - 512MB / 1 vCPU │   │
                        │  │                                │   │
                        │  │  /api/v1/* ──► Cloud Run       │   │
                        │  │               (FastAPI)        │   │
                        │  │               Backend          │   │
                        │  │               - 0→20 instances │   │
                        │  │               - 2GB / 2 vCPU   │   │
                        │  │               - 300s timeout   │   │
                        │  └──────────────────────────────┘   │
                        │                                     │
                        │  ┌──────────────────────────────┐   │
                        │  │  Cloud SQL (PostgreSQL 15)    │   │
                        │  │  - db-custom-2-4096           │   │
                        │  │  - 50GB SSD                   │   │
                        │  │  - Private IP (VPC)           │   │
                        │  │  - Automated backups (daily)  │   │
                        │  │  - Point-in-time recovery     │   │
                        │  └──────────────────────────────┘   │
                        │                                     │
                        │  ┌──────────────────────────────┐   │
                        │  │  GCS Bucket                   │   │
                        │  │  smriti-legal-documents        │   │
                        │  │  - Standard storage class     │   │
                        │  │  - Directory sharding         │   │
                        │  │  - Signed URLs for access     │   │
                        │  └──────────────────────────────┘   │
                        │                                     │
                        │  ┌──────────────────────────────┐   │
                        │  │  Vertex AI                    │   │
                        │  │  - Gemini 2.5 Pro (LLM)      │   │
                        │  │  - gemini-embedding-001 (embed)│   │
                        │  └──────────────────────────────┘   │
                        │                                     │
                        └─────────────────────────────────────┘

            External Services (managed, outside GCP VPC):
            ┌──────────────────────────────────────────────┐
            │  Pinecone (Serverless)                        │
            │  - Index: smriti-legal                        │
            │  - Region: gcp-starter (us-east-1)           │
            │  - 1536 dimensions, cosine metric            │
            ├──────────────────────────────────────────────┤
            │  Neo4j AuraDB Free                           │
            │  - Citation graph                            │
            │  - ~100K nodes, ~500K relationships          │
            ├──────────────────────────────────────────────┤
            │  Upstash Redis                               │
            │  - Global replication                        │
            │  - REST API (serverless-friendly)            │
            ├──────────────────────────────────────────────┤
            │  Cohere API                                  │
            │  - rerank-v4.0-pro model                           │
            │  - Pay-per-request                           │
            └──────────────────────────────────────────────┘
```

### Cloud Run Configuration

```yaml
# Backend service
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: smriti-backend
spec:
  template:
    metadata:
      annotations:
        autoscaling.knative.dev/minScale: "0"
        autoscaling.knative.dev/maxScale: "20"
        run.googleapis.com/cpu-throttling: "false"
    spec:
      containerConcurrency: 80
      timeoutSeconds: 300
      containers:
        - image: gcr.io/smriti-prod/backend:latest
          resources:
            limits:
              memory: "2Gi"
              cpu: "2"
          env:
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: db-url
            - name: PINECONE_API_KEY
              valueFrom:
                secretKeyRef:
                  name: pinecone-key
            # ... other secrets from Secret Manager
```

### Cost Estimates (MVP Scale)

| Service | Tier | Monthly Estimate |
|---------|------|-----------------|
| Cloud Run (backend) | Pay-per-use | $15-50 |
| Cloud Run (frontend) | Pay-per-use | $5-15 |
| Cloud SQL PostgreSQL | db-custom-2-4096 | $50-80 |
| Pinecone | Serverless (starter) | $0 (free tier) |
| Neo4j AuraDB | Free tier | $0 |
| Upstash Redis | Free tier | $0 |
| GCS | Standard | $1-5 |
| Vertex AI (Gemini) | Pay-per-token | $20-100 |
| Cohere Rerank | Pay-per-request | $5-20 |
| Cloud Load Balancer | Per-rule + traffic | $20 |
| **Total** | | **$116-290/month** |

---

## Document Upload Pipeline

```
User uploads PDF → POST /documents/upload → Store file (GCS/local) → Queue Celery task
                                                                         │
  ┌──────────────────────────────────────────────────────────────────────┘
  ▼
Celery Worker (analyze_document task):
  1. Extract text (PDFParser + OCR fallback)
  2. Issue extraction (Gemini structured output → JSONB)
  3. Precedent mapping (parallel hybrid search per issue)
  4. Counter-argument generation (Gemini)
  5. Research memo generation (Gemini)
  6. Store results in DocumentAnalysis table

Status tracked: pending → extracting → analyzing → searching → generating → completed/failed
Frontend polls GET /documents/{id} for status updates
```

---

## Audio Digest Pipeline

```
POST /cases/{id}/audio/generate → Queue Celery task
                                       │
  ┌────────────────────────────────────┘
  ▼
Celery Worker (generate_audio task):
  1. Generate case summary (Gemini, 400-600 words, audio-optimized)
  2. Synthesize speech (Sarvam AI TTS, supports 22 Indian languages)
  3. Store MP3 (GCS/local)
  4. Update AudioDigest record (status, duration, storage_path)

GET /cases/{id}/audio/status — Check if audio exists + languages available
GET /cases/{id}/audio — Stream MP3 file

Cache: audio_digests has UNIQUE(case_id, language) — never regenerates existing
```

---

## Background Task Architecture (Celery)

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│  FastAPI     │────►│  Redis       │────►│  Celery      │
│  (enqueue)   │     │  (broker,    │     │  Worker      │
│              │     │   DB 1)      │     │              │
└─────────────┘     └──────────────┘     └──────┬───────┘
                                                │
                          ┌─────────────────────┼─────────────────┐
                          ▼                     ▼                 ▼
                    analyze_document      generate_audio     (future tasks)
                    (6-step pipeline)     (summary + TTS)
```

FastAPI enqueues background tasks via Celery, using Redis (DB 1) as the message broker. Each task type runs as a self-contained pipeline within the Celery worker process. Task status is persisted to PostgreSQL so the frontend can poll for progress. Failed tasks are retried up to 3 times with exponential backoff.

---

## Agent Execution Architecture (LangGraph)

Smriti includes 4 AI agents built with LangGraph for complex legal research workflows that go beyond single-turn chat. Each agent is a directed graph of async nodes with human-in-the-loop checkpoints.

### Agent Types

| Agent | Purpose | Key Workflow |
|-------|---------|-------------|
| **Research** | Precedent research | query_expand -> search_precedents -> analyze_results -> (checkpoint) -> synthesize |
| **Case Prep** | Issue analysis + deep search | extract_issues -> score_issues -> (checkpoint) -> deep_search per issue -> compile |
| **Strategy** | Legal strategy + risk analysis | analyze_position -> identify_risks -> (checkpoint) -> develop_arguments -> verify_citations |
| **Drafting** | Document generation + citation verification | select_template -> generate_draft -> (checkpoint) -> verify_citations -> finalize |

### Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                      FRONTEND (Next.js 15)                          │
│                                                                      │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌────────────┐  │
│  │  /agents/    │ │  /agents/    │ │  /agents/    │ │ /agents/   │  │
│  │  research    │ │  case-prep   │ │  strategy    │ │ drafting   │  │
│  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘ └─────┬──────┘  │
│         └────────────────┼────────────────┼────────────────┘         │
│                          ▼                                           │
│              ┌─────────────────────┐                                 │
│              │ Checkpoint Prompt   │  (renders at interrupt() points)│
│              │ Component           │                                 │
│              └──────────┬──────────┘                                 │
│                         │ SSE (EventSource)                          │
└─────────────────────────┼────────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────────────┐
│                      FASTAPI BACKEND                                 │
│                                                                      │
│  POST /api/v1/agents/{agent_type}/run   ─── Start/resume execution  │
│  GET  /api/v1/agents/executions         ─── List past executions    │
│                                                                      │
│  ┌───────────────────────────────────────────────────────────────┐   │
│  │                   LangGraph StateGraph                        │   │
│  │                                                               │   │
│  │  ┌─────────┐    ┌─────────┐    ┌────────────┐    ┌────────┐  │   │
│  │  │  Node 1  │───►│ Node 2  │───►│ interrupt() │───►│ Node 3 │  │   │
│  │  │ (async)  │    │ (async) │    │ (HITL)      │    │(async) │  │   │
│  │  └─────────┘    └─────────┘    └────────────┘    └────────┘  │   │
│  │                                                               │   │
│  │  Checkpointing: MemorySaver (dev) / AsyncPostgresSaver (prod)│   │
│  └───────────────────────────────────────────────────────────────┘   │
│                          │                                           │
│                          ▼ SSE Stream                                │
│          Event types: status | progress | checkpoint | memo |        │
│                        done | error                                  │
│                          │                                           │
│     ┌────────────────────┼────────────────────┐                      │
│     ▼                    ▼                    ▼                      │
│  Gemini 2.5 Pro     Hybrid Search       Neo4j (citations)           │
│  (reasoning)        (Pinecone + FTS)    (verification)              │
│                                                                      │
│  All providers use Tenacity retry: exponential backoff (2-60s, 5x)  │
└──────────────────────────────────────────────────────────────────────┘
```

### Execution Flow

1. **Client** sends `POST /api/v1/agents/{agent_type}/run` with input parameters
2. **Backend** constructs the appropriate LangGraph `StateGraph` and invokes it
3. **Nodes** execute sequentially, each returning a partial state dict merged into graph state
4. **SSE stream** sends real-time updates (status, progress, intermediate results) to the frontend
5. At **checkpoint** nodes, `interrupt()` pauses execution and sends a `checkpoint` event with a prompt
6. **Frontend** displays the checkpoint prompt component for user review/approval
7. **Client** resumes by re-calling the same endpoint with the checkpoint response
8. **Remaining nodes** execute and a `done` event signals completion
9. Execution metadata is persisted to the `agent_executions` PostgreSQL table

### Key Design Decisions

- **MemorySaver** for dev checkpointing (in-memory); **AsyncPostgresSaver** planned for production persistence
- **Pure async node functions** keep nodes testable and composable; dependencies injected via closures
- **Same SSE pattern as chat** (`data: JSON\n\n`) for frontend consistency
- **Tenacity retry** on all external provider calls within nodes (Gemini, Pinecone, Neo4j)

---

## Complete API Endpoint Inventory

62 endpoints across 15 route files, mounted via `app/main.py`.

### Auth (`/api/v1/auth` — `auth.py`)

| # | Method | Path | Auth | Rate Limit | Description |
|---|--------|------|------|------------|-------------|
| 1 | POST | `/register` | Public | 5/min | Register new user with DPDP consent, auto-login |
| 2 | POST | `/login` | Public | 5/min | Authenticate user, return JWT token pair |
| 3 | POST | `/refresh` | Public | 10/min | Rotate refresh token, issue new access token |
| 4 | POST | `/logout` | User | 20/min | Revoke access token + optional refresh token |
| 5 | DELETE | `/me` | User | — | Delete account and all personal data (DPDP Section 12) |

### Search (`/api/v1/search` — `search.py`)

| # | Method | Path | Auth | Rate Limit | Description |
|---|--------|------|------|------------|-------------|
| 6 | GET | `/` | Optional | 30/min | Hybrid search: query understanding, vector + FTS, RRF, rerank |
| 7 | GET | `/suggest` | Public | 60/min | Auto-complete suggestions from case titles and citations |
| 8 | GET | `/facets` | Public | 30/min | Distinct filter values (courts, case types, bench types, year range) |

### Cases (`/api/v1/cases` — `cases.py`)

| # | Method | Path | Auth | Rate Limit | Description |
|---|--------|------|------|------------|-------------|
| 9 | GET | `/{case_id}` | Public | 60/min | Full case metadata with section-detected judgment text |
| 10 | GET | `/{case_id}/summary` | User | 30/min | Case summary (ratio decidendi) with optional Hindi translation |
| 11 | GET | `/{case_id}/pdf` | Public | 30/min | Stream original PDF from storage |
| 12 | GET | `/{case_id}/citations` | Public | 60/min | Outgoing CITES edges from Neo4j, enriched with PG metadata |
| 13 | GET | `/{case_id}/cited-by` | Public | 60/min | Incoming CITES edges from Neo4j, enriched with PG metadata |
| 14 | GET | `/{case_id}/similar` | Optional | 20/min | Semantically similar cases via vector similarity on ratio_decidendi |

### Chat (`/api/v1/chat` — `chat.py`)

| # | Method | Path | Auth | Rate Limit | Description |
|---|--------|------|------|------------|-------------|
| 15 | POST | `/` | User | 20/min | Create new chat session + stream first response (SSE) |
| 16 | POST | `/{session_id}/message` | User | 20/min | Continue conversation, stream response (SSE, IDOR-protected) |
| 17 | GET | `/sessions` | User | — | List all chat sessions for current user |
| 18 | GET | `/{session_id}/history` | User | — | Full message history (with field-level decryption) |
| 19 | DELETE | `/{session_id}` | User | — | Delete session + cascade delete messages |

### Agents (`/api/v1/agents` — `agents.py`)

| # | Method | Path | Auth | Rate Limit | Description |
|---|--------|------|------|------------|-------------|
| 20 | POST | `/{agent_type}/run` | User | 10/min | Start agent execution (research/case_prep/strategy/drafting), SSE stream |
| 21 | GET | `/executions` | User | — | List user's agent executions (paginated) |
| 22 | GET | `/executions/{execution_id}` | User | — | Get execution detail (IDOR-protected) |
| 23 | POST | `/executions/{execution_id}/resume` | User | 10/min | Resume paused execution with user input (HITL) |
| 24 | DELETE | `/executions/{execution_id}` | User | — | Cancel a running/waiting execution |
| 25 | GET | `/drafting/templates` | User | — | List available document templates |
| 26 | POST | `/drafting/export/{execution_id}` | User | 20/min | Export completed draft as DOCX or PDF |

### Graph (`/api/v1/graph` — `graph.py`)

| # | Method | Path | Auth | Rate Limit | Description |
|---|--------|------|------|------------|-------------|
| 27 | GET | `/{case_id}/neighborhood` | Optional | 30/min | Citation network around a case (depth 1-3) |
| 28 | GET | `/{case_id}/chain` | Optional | 30/min | Forward citation chain (recursive, max depth 5) |
| 29 | GET | `/{case_id}/authorities` | Optional | 30/min | Most-cited cases in the neighborhood |
| 30 | GET | `/stats` | Optional | 30/min | Global citation graph statistics |

### Documents (`/api/v1/documents` — `documents.py`)

| # | Method | Path | Auth | Rate Limit | Description |
|---|--------|------|------|------------|-------------|
| 31 | POST | `/upload` | User | 10/min | Upload PDF for analysis (50MB limit, magic byte validation) |
| 32 | GET | `/` | User | — | List user's uploaded documents (paginated) |
| 33 | GET | `/{document_id}` | User | — | Get document detail with analysis results |
| 34 | DELETE | `/{document_id}` | User | — | Delete document + storage file (owner only) |
| 35 | GET | `/{document_id}/memo` | User | — | Get generated research memo |

### Audio (`/api/v1/cases` — `audio.py`)

| # | Method | Path | Auth | Rate Limit | Description |
|---|--------|------|------|------------|-------------|
| 36 | POST | `/{case_id}/audio/generate` | User | — | Queue async audio digest generation (en/hi) |
| 37 | GET | `/{case_id}/audio/status` | Public | — | Check audio availability and languages |
| 38 | GET | `/{case_id}/audio` | Public | 10/min | Stream audio MP3 file |

### Ingest (`/api/v1/ingest` — `ingest.py`)

| # | Method | Path | Auth | Rate Limit | Description |
|---|--------|------|------|------------|-------------|
| 39 | POST | `/upload` | Admin | — | Upload PDF for ingestion into case database |
| 40 | GET | `/status/{document_id}` | User | — | Check ingestion status of a document |
| 41 | GET | `/dashboard/completeness` | Admin | — | Field coverage, confidence distribution, year coverage |
| 42 | GET | `/review-queue` | Admin | — | List cases flagged for human review (needs_review) |
| 43 | PATCH | `/cases/{case_id}/metadata` | Admin | — | Update case metadata (allowlisted fields, audit logged) |
| 44 | POST | `/cases/{case_id}/approve` | Admin | — | Mark needs_review case as complete |
| 45 | POST | `/cases/{case_id}/retry` | Admin | — | Reset failed case to pending for re-ingestion |

### Judges (`/api/v1` — `judges.py`)

| # | Method | Path | Auth | Rate Limit | Description |
|---|--------|------|------|------------|-------------|
| 46 | GET | `/judges` | Public | 30/min | List judges with participation and authorship counts |
| 47 | GET | `/judges/compare` | Public | 30/min | Compare 2-3 judges side-by-side |
| 48 | GET | `/judges/{judge_name}` | Public | 30/min | Comprehensive judge profile with analytics (cached 1h) |
| 49 | GET | `/judges/{judge_name}/cases` | Public | 30/min | Paginated cases for a judge with filters |
| 50 | GET | `/courts/{court_name}/stats` | Public | 30/min | Court-level statistics (cached 1h) |

### DPDP (`/api/v1/dpdp` — `dpdp.py`)

| # | Method | Path | Auth | Rate Limit | Description |
|---|--------|------|------|------------|-------------|
| 51 | GET | `/data-summary` | User | 20/min | Summary of all personal data held (DPDP Section 11) |
| 52 | POST | `/erasure` | User | 5/hour | Delete all personal data, deactivate account (DPDP Section 12) |
| 53 | POST | `/consent-withdraw` | User | 10/hour | Withdraw data processing consent (DPDP Section 6) |
| 54 | GET | `/consent-status` | User | — | View current consent records |

### Health (`/` — `health.py`)

| # | Method | Path | Auth | Rate Limit | Description |
|---|--------|------|------|------------|-------------|
| 55 | GET | `/health` | Optional | 60/min | Dependency health checks (PG, Redis, Pinecone, Neo4j, Gemini) |

### Data Quality (`/api/v1/admin/data-quality` — `data_quality.py`)

| # | Method | Path | Auth | Rate Limit | Description |
|---|--------|------|------|------------|-------------|
| 56 | GET | `/` | Admin | — | Per-field population rates, citation resolution, avg fields/case |

### Admin Corrections (`/api/v1/admin/corrections` — `admin_corrections.py`)

| # | Method | Path | Auth | Rate Limit | Description |
|---|--------|------|------|------------|-------------|
| 57 | POST | `/{case_id}/correct` | Admin | — | Correct single metadata field with audit trail + provenance update |
| 58 | GET | `/{case_id}/history` | Admin | — | View correction history from audit logs |

### Admin Review (`/api/v1/admin/review` — `admin_review.py`)

| # | Method | Path | Auth | Rate Limit | Description |
|---|--------|------|------|------------|-------------|
| 59 | GET | `/` | Admin | — | List cases needing editorial review (sortable, paginated) |
| 60 | GET | `/{case_id}` | Admin | — | Full review detail with provenance metadata |
| 61 | POST | `/{case_id}/approve` | Admin | — | Approve case (set ingestion_status='complete') |
| 62 | POST | `/{case_id}/reject` | Admin | — | Reject case (set ingestion_status='rejected') |

### Auth Levels

| Level | Description |
|-------|-------------|
| **Public** | No authentication required |
| **Optional** | Works without auth; authenticated users get richer responses |
| **User** | Requires valid JWT access token (any role) |
| **Admin** | Requires JWT with `role="admin"` (enforced via `require_role("admin")`) |

---

## Celery Task Pipeline Detail

### Architecture

```
FastAPI (API Server)                  Redis (DB 1, broker)              Celery Worker
┌──────────────────┐                 ┌──────────────────┐              ┌──────────────────┐
│  POST /documents │                 │                  │              │                  │
│  /upload         │─── .delay() ──►│  Task Queue      │─── consume ─►│  analyze_document│
│                  │                 │                  │              │  generate_audio  │
│  POST /cases/    │                 │                  │              │                  │
│  {id}/audio/     │─── .delay() ──►│                  │              │                  │
│  generate        │                 │                  │              │                  │
└──────────────────┘                 └──────────────────┘              └──────────────────┘
```

### Configuration

- **Broker**: Redis DB 1 (`redis://localhost:6379/1`)
- **Result backend**: Disabled (status tracked in PostgreSQL instead)
- **Task retries**: Max 2 retries, 60-second delay between attempts (`bind=True, max_retries=2, default_retry_delay=60`)
- **Worker command**: `celery -A app.worker:celery_app worker --loglevel=info`
- **Flower monitoring** (optional): `celery -A app.worker:celery_app flower` on port 5555

### Document Analysis Task (`analyze_document`)

A 7-step pipeline executed within a Celery worker process. Each step updates the `documents` table status for frontend polling.

| Step | Status | Description | Services Used |
|------|--------|-------------|---------------|
| 1 | `extracting` | Extract text from PDF using PyMuPDF; falls back to OCR if text < 50 chars | PDFParser |
| 2 | `analyzing` | Extract legal issues, parties, key facts, and relief sought | Gemini 2.5 Pro (structured output) |
| 3 | `searching` | Find supporting precedents via hybrid search for each identified issue | Gemini Embedder + Pinecone + Cohere Reranker |
| 4 | `generating` | Generate counter-arguments for each issue based on precedents | Gemini 2.5 Pro |
| 5 | `generating` | Generate comprehensive research memo combining all analysis | Gemini 2.5 Pro |
| 6 | `indexing` | Chunk document text, embed in batches of 20, upsert to Pinecone | Chunker + Gemini Embedder + Pinecone |
| 7 | `completed` | Store all results in `document_analyses` table | PostgreSQL |

**Status progression**: `pending` → `extracting` → `analyzing` → `searching` → `generating` → `indexing` → `completed` (or `failed` on error)

**Error handling**: Transient errors (ConnectionError, TimeoutError, OSError) trigger Celery retry. Other exceptions mark the document as `failed` with the error message stored in `documents.error_message`.

**Analysis output** (stored in `document_analyses` table):
- `extracted_text`: Raw text from PDF (truncated to 50K chars)
- `issues`: JSON array of identified legal issues with supporting precedents
- `parties`: JSON object of parties involved
- `key_facts`: Key factual findings
- `relief_sought`: Relief requested
- `counter_arguments`: JSON array of counter-arguments per issue
- `research_memo`: Full research memo (Markdown formatted)

### Audio Generation Task (`generate_audio`)

A 4-step pipeline for generating audio digests of case summaries.

| Step | Description | Services Used |
|------|-------------|---------------|
| 1 | Generate audio-optimized summary (400-600 words) from case judgment text | Gemini 2.5 Pro |
| 2 | Synthesize speech from summary text | Sarvam AI TTS (or MockTTS in dev) |
| 3 | Store MP3 file to storage | LocalStorage / GCS |
| 4 | Update `audio_digests` record with path, duration estimate, status | PostgreSQL |

**Duration estimation**: word_count / 150 * 60 seconds (approximate 150 WPM speech rate).

**Idempotency**: Checks for existing completed digest before processing. UNIQUE constraint on `(case_id, language)` prevents duplicates.

---

## Admin Workflows

### Data Quality Dashboard

**Endpoint**: `GET /api/v1/admin/data-quality` (admin only)

Provides comprehensive data quality metrics computed via SQL aggregate queries:

```
┌─────────────────────────────────────────────────────────────────┐
│                    DATA QUALITY DASHBOARD                        │
├─────────────────────────────────────────────────────────────────┤
│  Total Cases: N                                                 │
│                                                                 │
│  Status Breakdown:                                              │
│    complete: X | needs_review: Y | failed: Z | processing: W   │
│                                                                 │
│  Field Population Rates (32 fields checked):                    │
│    Scalar: title, citation, court, year, decision_date,         │
│            case_type, jurisdiction, bench_type, petitioner,     │
│            respondent, author_judge, disposal_nature,           │
│            ratio_decidendi, case_number, headnotes,             │
│            outcome_summary, coram_size, lower_court,            │
│            opinion_type, split_ratio, petitioner_type,          │
│            respondent_type, is_pil, extraction_confidence,      │
│            text_hash                                            │
│    Array:  judge[], acts_cited[], cases_cited[], keywords[],    │
│            dissenting_judges[], concurring_judges[],            │
│            companion_cases[]                                    │
│                                                                 │
│  Average Non-Null Fields Per Case: X.XX                         │
│                                                                 │
│  Citation Stats:                                                │
│    Cases with citations: X                                      │
│    Known unique citations: Y                                    │
└─────────────────────────────────────────────────────────────────┘
```

### Ingestion Completeness Dashboard

**Endpoint**: `GET /api/v1/ingest/dashboard/completeness` (admin only)

A separate completeness dashboard in the ingest module providing:
- Per-field fill rates for 16 key metadata fields
- Ingestion status distribution
- Extraction confidence distribution (6 buckets: no_score, low, medium_low, medium, good, excellent)
- Year coverage (cases per year, top 50 years)

### Review Queue

**Flow**: Cases are flagged for review when extraction confidence is low, text quality is poor, or critical fields are missing during ingestion.

```
Ingestion Pipeline                Review Queue                    Admin Action
┌──────────────┐                ┌──────────────────┐            ┌─────────────┐
│  Cases with  │                │ GET /admin/review │            │             │
│  low-conf or │─── flagged ──►│  (paginated,      │──── view ─►│  Approve    │
│  missing     │  needs_review  │   sortable by     │            │  (complete) │
│  fields      │                │   confidence,     │            │     or      │
└──────────────┘                │   year, date)     │            │  Reject     │
                                │                   │            │  (rejected) │
                                │ GET /admin/review │            └─────────────┘
                                │  /{case_id}       │
                                │  (full detail     │
                                │   with provenance)│
                                └──────────────────┘
```

**Review queue features**:
- Filter by status: `needs_review`, `failed`, `processing`
- Sort by: `created_at`, `extraction_confidence`, `year` (ASC/DESC)
- Paginated (page/page_size)
- Full case detail view includes `metadata_provenance` (per-field source tracking)

### Metadata Corrections with Audit Trail

**Flow**: Admin corrects a field value, and the system records old value, new value, reason, and who made the correction.

```
Admin                         Backend                       PostgreSQL
  │                              │                              │
  │ POST /admin/corrections/     │                              │
  │   {case_id}/correct          │                              │
  │ {field, new_value, reason}   │                              │
  │─────────────────────────────►│                              │
  │                              │ Validate field in allowlist  │
  │                              │ Fetch old_value              │
  │                              │──────────────────────────────►│
  │                              │ UPDATE cases SET field=val   │
  │                              │──────────────────────────────►│
  │                              │ UPDATE metadata_provenance   │
  │                              │   field → 'admin_corrected'  │
  │                              │──────────────────────────────►│
  │                              │ INSERT audit_logs            │
  │                              │   {field, old, new, reason,  │
  │                              │    corrected_by, timestamp}  │
  │                              │──────────────────────────────►│
  │  {old_value, new_value,      │                              │
  │   status: "corrected"}       │                              │
  │◄─────────────────────────────│                              │
```

**Correctable fields** (36 total):
- Scalar: `title`, `citation`, `court`, `year`, `decision_date`, `case_type`, `jurisdiction`, `bench_type`, `petitioner`, `respondent`, `author_judge`, `disposal_nature`, `ratio_decidendi`, `case_number`, `headnotes`, `outcome_summary`, `coram_size`, `lower_court`, `lower_court_case_number`, `appeal_from`, `opinion_type`, `split_ratio`, `petitioner_type`, `respondent_type`, `is_pil`
- Array: `judge[]`, `acts_cited[]`, `cases_cited[]`, `keywords[]`, `dissenting_judges[]`, `concurring_judges[]`, `companion_cases[]`

**Audit trail**: Corrections are queryable via `GET /admin/corrections/{case_id}/history`, returning chronological list of all corrections with old/new values, reason, corrected_by user ID, and timestamp.

---

## DPDP Compliance Architecture

Smriti implements compliance with India's Digital Personal Data Protection Act, 2023 across multiple system layers.

### Consent Management Flow

```
Registration                              Database
┌─────────────────┐                     ┌────────────────────────┐
│  RegisterRequest │                     │  consents table        │
│  {               │                     │  ┌──────────────────┐  │
│    email,        │  consent_given      │  │ id               │  │
│    password,     │  MUST be true  ───► │  │ user_id          │  │
│    consent_given │  (no default)       │  │ consent_type     │  │
│    consent_ver   │                     │  │ granted (bool)   │  │
│  }               │                     │  │ version ("1.0")  │  │
└─────────────────┘                     │  │ created_at       │  │
                                         │  │ revoked_at       │  │
                                         │  └──────────────────┘  │
                                         └────────────────────────┘
```

- **Explicit consent**: `consent_given` field has no default value; must be explicitly set to `true` at registration
- **Versioned consent**: `consent_version` tracks which version of privacy terms was agreed to
- **Consent withdrawal**: `POST /api/v1/dpdp/consent-withdraw` sets `revoked_at` on all active consents
- **Consent status**: `GET /api/v1/dpdp/consent-status` returns full consent history with grant/revoke timestamps

### Data Erasure Pipeline

Two paths to data erasure, both compliant with DPDP Section 12:

**Path 1: Account Deletion** (`DELETE /api/v1/auth/me`)
**Path 2: DPDP Erasure Request** (`POST /api/v1/dpdp/erasure`)

Both execute the same cascade:

```
1. DELETE agent_executions WHERE user_id = :uid
2. DELETE chat_messages WHERE session_id IN (user's sessions)
3. DELETE chat_sessions WHERE user_id = :uid
4. DELETE documents WHERE user_id = :uid
5. DELETE consents WHERE user_id = :uid
6. INSERT dpdp_audit_log (erasure_completed, user_id, details)
7. UPDATE users SET is_active = false, email = 'deleted_{uid}@deleted.local'
8. Revoke current JWT tokens
```

**Key design decisions**:
- **Soft-delete for users**: Account is deactivated and email anonymized, not hard-deleted, to maintain audit trail integrity
- **Hard-delete for user data**: All personal data (chats, documents, agent executions, consents) is permanently deleted
- **DPDP audit log retained**: Erasure events are logged to a separate `dpdp_audit_log` table (retained for compliance, not user data)
- **Atomic transactions**: Path 2 uses `begin_nested()` for atomic deletion

### DPDP Audit Logging

The `dpdp_audit_log` table records all DPDP-relevant events:

| Action | Trigger |
|--------|---------|
| `account_deleted` | User deletes account via `DELETE /auth/me` |
| `erasure_completed` | User requests erasure via `POST /dpdp/erasure` |
| `consent_withdrawn` | User withdraws consent via `POST /dpdp/consent-withdraw` |

These entries are never deleted, even during erasure, as they serve as compliance evidence.

### Data Subject Rights (DPDP Section 11)

`GET /api/v1/dpdp/data-summary` returns a count of all personal data categories:
- Chat sessions and messages
- Uploaded documents
- Agent executions
- Audit log entries
- Consent records

### Startup Cleanup (Purpose Limitation)

On application startup, the `_cleanup_expired_uploads()` task deletes user-uploaded PDF files older than the configured retention period (`USER_UPLOAD_RETENTION_DAYS`), enforcing purpose-limited data retention.

---

## Document Upload & Analysis Flow

End-to-end flow from PDF upload to research memo availability:

```
User                  Frontend               Backend API              Celery Worker
  │                      │                       │                         │
  │  Upload PDF          │                       │                         │
  │─────────────────────►│                       │                         │
  │                      │  POST /documents/     │                         │
  │                      │       upload           │                         │
  │                      │  (multipart/form-data) │                         │
  │                      │──────────────────────►│                         │
  │                      │                       │  Validate:              │
  │                      │                       │  - Content-Type check   │
  │                      │                       │  - Size limit (50MB)    │
  │                      │                       │  - PDF magic bytes      │
  │                      │                       │  - Filename sanitize    │
  │                      │                       │                         │
  │                      │                       │  Store PDF to storage   │
  │                      │                       │  INSERT documents       │
  │                      │                       │   (status='pending')    │
  │                      │                       │                         │
  │                      │                       │  analyze_document       │
  │                      │                       │    .delay(doc_id)       │
  │                      │                       │────────────────────────►│
  │                      │  202 {document_id,    │                         │
  │                      │       status: pending} │                         │
  │                      │◄──────────────────────│                         │
  │                      │                       │                         │
  │                      │  Poll: GET /documents/ │                        │
  │                      │       {document_id}    │                        │
  │                      │──────────────────────►│                         │
  │                      │                       │                         │
  │                      │                       │         ┌──────────────┤
  │                      │                       │         │ Step 1: PDF  │
  │                      │                       │         │  → text      │
  │                      │                       │         │ Step 2: LLM  │
  │                      │                       │         │  → issues    │
  │                      │                       │         │ Step 3: search│
  │                      │                       │         │  → precedents│
  │                      │                       │         │ Step 4: LLM  │
  │                      │                       │         │  → counter   │
  │                      │                       │         │    arguments │
  │                      │                       │         │ Step 5: LLM  │
  │                      │                       │         │  → research  │
  │                      │                       │         │    memo      │
  │                      │                       │         │ Step 6: chunk│
  │                      │                       │         │  → embed     │
  │                      │                       │         │  → index     │
  │                      │                       │         │ Step 7: store│
  │                      │                       │         │  results     │
  │                      │                       │         └──────────────┤
  │                      │                       │                         │
  │                      │  GET /documents/       │                        │
  │                      │  {id} → status:        │                        │
  │                      │  "completed" +          │                        │
  │                      │  analysis: {issues,     │                        │
  │                      │  parties, key_facts,    │                        │
  │                      │  relief, counter_args,  │                        │
  │                      │  research_memo}         │                        │
  │                      │◄──────────────────────│                         │
  │                      │                       │                         │
  │  View research memo  │  GET /documents/      │                         │
  │◄─────────────────────│  {id}/memo            │                         │
```

**PDF validation pipeline**:
1. `Content-Type` header must be `application/pdf`
2. File size check against 50MB limit (both from header and actual content)
3. PDF magic bytes validation (`%PDF` prefix)
4. Filename sanitization (path traversal prevention, extension enforcement, 200-char limit)

**Post-analysis**: After Step 6, the uploaded document becomes searchable via hybrid search and RAG chat, as its chunks are indexed in Pinecone with metadata including `source: "upload"`.

---

## Audio Digest Generation Flow

```
User                     Frontend                Backend API          Celery Worker
  │                         │                       │                      │
  │  Request audio digest   │                       │                      │
  │────────────────────────►│                       │                      │
  │                         │ POST /cases/{id}/     │                      │
  │                         │  audio/generate       │                      │
  │                         │  ?language=en          │                      │
  │                         │──────────────────────►│                      │
  │                         │                       │ Check existing:      │
  │                         │                       │  completed → return  │
  │                         │                       │  generating → return │
  │                         │                       │                      │
  │                         │                       │ generate_audio       │
  │                         │                       │  .delay(case_id,     │
  │                         │                       │         language)    │
  │                         │                       │─────────────────────►│
  │                         │ 202 {status: queued}  │                      │
  │                         │◄──────────────────────│                      │
  │                         │                       │                      │
  │                         │                       │     ┌────────────────┤
  │                         │                       │     │ 1. Generate    │
  │                         │                       │     │    summary     │
  │                         │                       │     │    (Gemini,    │
  │                         │                       │     │    400-600w,   │
  │                         │                       │     │    audio-      │
  │                         │                       │     │    optimized)  │
  │                         │                       │     │                │
  │                         │                       │     │ 2. TTS synth   │
  │                         │                       │     │    (Sarvam AI  │
  │                         │                       │     │    or fallback)│
  │                         │                       │     │                │
  │                         │                       │     │ 3. Store MP3   │
  │                         │                       │     │    (GCS/local) │
  │                         │                       │     │                │
  │                         │                       │     │ 4. Update DB   │
  │                         │                       │     │    (status,    │
  │                         │                       │     │    duration,   │
  │                         │                       │     │    path)       │
  │                         │                       │     └────────────────┤
  │                         │                       │                      │
  │  Poll status            │ GET /cases/{id}/      │                      │
  │────────────────────────►│  audio/status          │                      │
  │                         │──────────────────────►│                      │
  │                         │  {available: ["en"],   │                      │
  │                         │   digests: [{...}]}    │                      │
  │                         │◄──────────────────────│                      │
  │                         │                       │                      │
  │  Play audio             │ GET /cases/{id}/audio │                      │
  │────────────────────────►│  ?language=en          │                      │
  │                         │──────────────────────►│                      │
  │                         │  StreamingResponse    │                      │
  │                         │  (audio/mpeg, chunked)│                      │
  │                         │◄──────────────────────│                      │
```

**TTS providers** (selected via interface pattern):
- **Sarvam AI**: Primary provider, supports 22 Indian languages (en, hi, bn, ta, te, mr, gu, kn, ml, pa, etc.)
- **MockTTS**: Development fallback (silent audio generation)

**Language support**: Audio digests can be generated in English (`en`) or Hindi (`hi`). The summary text is generated by Gemini with language-specific prompts from `core/legal/prompts.py` (`AUDIO_SUMMARY_SYSTEM`, `AUDIO_SUMMARY_USER`).

**Caching**: Existing completed digests are never regenerated. The `audio_digests` table has a `UNIQUE(case_id, language)` constraint.

---

## Judge Analytics Module

Located in `backend/app/core/analytics/judge_analytics.py`, the `JudgeAnalyticsService` provides comprehensive analytics computed from PostgreSQL queries on the `cases` table.

### Data Model

The analytics engine leverages the `judge[]` array column (all bench members) and `author_judge` scalar column (opinion author) to derive:

```
cases table
┌──────────────────────────────────────────────────────┐
│ judge: TEXT[]           — All bench members           │
│ author_judge: TEXT      — Author of the opinion       │
│ disposal_nature: TEXT   — Outcome (allowed/dismissed) │
│ case_type: TEXT         — Type of case                │
│ acts_cited: TEXT[]      — Statutes referenced         │
│ year: INTEGER           — Year of judgment            │
│ decision_date: DATE     — Date of decision            │
│ court: TEXT             — Court name                  │
└──────────────────────────────────────────────────────┘
```

### Service Methods

| Method | Description | Key SQL Pattern |
|--------|-------------|-----------------|
| `list_judges()` | Paginated list with case counts | `UNNEST(judge)` + `GROUP BY` + author match count |
| `get_judge_profile()` | Full profile with analytics | 7 separate queries for different dimensions |
| `get_judge_cases()` | Paginated case list with filters | `Case.judge.any(name)` + year/type filters |
| `compare_judges()` | Side-by-side comparison (2-3 judges) | Fetches profile for each, returns array |
| `calculate_disposal_rates()` | Conviction/acquittal rates | `GROUP BY disposal_nature` on authored cases |
| `calculate_temporal_trends()` | Year-over-year trends | `COALESCE(EXTRACT(YEAR FROM decision_date), year)` grouping |
| `calculate_sentencing_stats()` | Case type distribution | `GROUP BY case_type` on authored cases |
| `get_court_stats()` | Court-level statistics | Cases by year, type, disposal, top judges |

### Judge Profile Components

A `JudgeProfile` contains:

1. **Total cases**: Cases where judge participated (on bench)
2. **Cases authored**: Cases where judge wrote the opinion
3. **Cases by year**: Year-wise distribution `{2020: 15, 2021: 23, ...}`
4. **Disposal patterns**: `{allowed: 45, dismissed: 30, ...}` with counts
5. **Bench combinations**: Top 10 co-sitting judges with case count `[{judge: "...", cases_together: N}]`
6. **Top cited judgments**: Judge's cases with most outgoing citations (by `cases_cited[]` array length)
7. **Acts frequency**: Top 20 most-cited statutes across the judge's cases
8. **Case types**: Distribution of case types `{Criminal Appeal: 40, Civil Appeal: 25, ...}`

### Court Statistics

A `CourtStats` contains: total cases, year distribution, case type breakdown, disposal patterns, and top 20 judges by case count.

### Caching

Judge profiles and court stats are cached in Redis with a 1-hour TTL. Cache keys follow the pattern `judge:profile:{name}` and `court:stats:{name}`.

---

## Security Architecture Detail

### JWT Authentication Flow

```
┌───────────────────────────────────────────────────────────────┐
│                    TOKEN LIFECYCLE                              │
│                                                                │
│  Access Token (short-lived)          Refresh Token (long-lived)│
│  ┌────────────────────────┐          ┌────────────────────────┐│
│  │ Algorithm: HS256       │          │ Algorithm: HS256       ││
│  │ Signing key: JWT_SECRET│          │ Signing key: JWT_      ││
│  │ Expiry: 15 minutes     │          │   REFRESH_SECRET       ││
│  │ (configurable)         │          │ Expiry: 7 days         ││
│  │                        │          │ (configurable)         ││
│  │ Claims:                │          │ Claims:                ││
│  │  sub: user_id          │          │  sub: user_id          ││
│  │  role: "researcher"    │          │  role: "refresh"       ││
│  │  type: "access"        │          │  type: "refresh"       ││
│  │  iss: "smriti"         │          │  iss: "smriti"         ││
│  │  aud: "smriti-api"     │          │  aud: "smriti-api"     ││
│  │  jti: uuid4()          │          │  jti: uuid4()          ││
│  │  iat: issued_at        │          │  iat: issued_at        ││
│  │  exp: expiry           │          │  exp: expiry           ││
│  └────────────────────────┘          └────────────────────────┘│
└───────────────────────────────────────────────────────────────┘
```

**Token verification**:
1. Decode JWT with signature verification (HS256)
2. Validate `iss` = "smriti" and `aud` = "smriti-api"
3. Check token `type` matches expected ("access" or "refresh")
4. Check JTI against Redis revocation blacklist (fail-closed: if Redis is unavailable, token is treated as revoked)
5. 30-second clock skew tolerance for distributed systems

**Token revocation**: Redis sorted set with key `revoked:jti:{jti}`, auto-expires when the token would naturally expire.

**Refresh token rotation**: On every refresh, the old refresh token is revoked and a new one is issued. Replay of a previously-used refresh token fails because the JTI is in the revocation list.

### Account Lockout

| Threshold | Action |
|-----------|--------|
| 5 failed logins | Account locked for 15 minutes |
| Successful login | Reset `failed_login_count` to 0, clear `locked_until` |
| Locked account | Returns HTTP 423 (Locked) |

Failed login attempts are tracked in `users.failed_login_count` and `users.locked_until`.

### RBAC Model

```
┌──────────────────────────────────────────────────────┐
│                    ROLE HIERARCHY                      │
│                                                        │
│  admin ──────── Full access to all endpoints           │
│    │             + admin routes (/admin/*, /ingest/*)  │
│    │                                                    │
│  researcher ─── Standard user access                   │
│    │             Search, chat, agents, documents, etc.  │
│    │                                                    │
│  viewer ─────── Read-only access (future)              │
└──────────────────────────────────────────────────────┘
```

**Implementation**: `require_role(*roles)` is a FastAPI dependency factory that:
1. Extracts the current user via `get_current_user` (JWT decode)
2. Checks `current_user.role` against the allowed roles list
3. Raises `AuthorizationError` (HTTP 403) if role is not permitted

**Optional auth**: `get_current_user_optional` returns `None` for unauthenticated requests (used by search, graph, health endpoints to provide richer responses for authenticated users).

### Rate Limiting Architecture

```
Request → Extract client IP + endpoint path → Build key "rate:{ip}:{path}"
                                                     │
                                          ┌──────────┼──────────┐
                                          ▼                     ▼
                                    Redis Available       Redis Unavailable
                                    ┌───────────────┐    ┌───────────────┐
                                    │ Sliding Window│    │ In-Memory     │
                                    │ (Sorted Set)  │    │ Fallback      │
                                    │               │    │               │
                                    │ ZREMRANGESCORE│    │ Thread-safe   │
                                    │ ZCARD         │    │ dict with     │
                                    │ ZADD          │    │ timestamp     │
                                    │ EXPIRE        │    │ pruning       │
                                    │ (pipelined)   │    │ (max 10K     │
                                    └───────┬───────┘    │  buckets)    │
                                            │            └───────┬───────┘
                                            ▼                    ▼
                                    count < limit?         count < limit?
                                    ├── yes → allow         ├── yes → allow
                                    └── no  → 429 +         └── no  → 429 +
                                        Retry-After             Retry-After
```

**Algorithm**: Sliding window using Redis sorted sets:
1. Remove entries older than the window (`ZREMRANGEBYSCORE`)
2. Count remaining entries (`ZCARD`)
3. If under limit, add current timestamp (`ZADD`)
4. Set key TTL to window size (`EXPIRE`)
5. All 4 operations in a single Redis pipeline for atomicity

**Fallback**: When Redis is unavailable, an in-memory sliding window (thread-safe dict with `threading.Lock`) prevents abuse. The in-memory store auto-clears when it exceeds 10,000 buckets.

### Field-Level Encryption

**Algorithm**: AES-256-GCM (authenticated encryption with associated data)

```
Plaintext → AES-256-GCM encrypt → nonce (12 bytes) + ciphertext + tag (16 bytes) → Base64 encode
                  │
                  ▼
    Key: ENCRYPTION_KEY env var (64-char hex or base64-encoded 32 bytes)
    Nonce: os.urandom(12) — unique per encryption operation
```

**Usage**: Chat message content is encrypted at rest in the `chat_messages` table. The `safe_decrypt()` function provides migration safety — it returns plaintext as-is if decryption fails, allowing pre-existing unencrypted messages to be read after encryption is enabled.

**Implementation**: Uses Python `cryptography` library's `AESGCM` class with:
- 12-byte random nonce per operation
- Automatic integrity verification via GCM authentication tag
- Key derived from environment variable (hex or base64 format accepted)

### Input Sanitization

Two-layer defense against injection attacks:

**Layer 1: Sanitization** (`sanitize_input` / `sanitize_search_query`)
- Strip HTML tags
- Remove null bytes and control characters (preserving whitespace)
- Collapse excessive newlines (max 3 consecutive)
- Remove known prompt injection markers (30+ patterns including "ignore previous instructions", "jailbreak", ChatML tags, etc.)
- Remove role-switching patterns (`system:`, `assistant:`, etc.)

**Layer 2: Detection** (`detect_prompt_injection`)
- Check for known injection markers (case-insensitive)
- Check for role-switching patterns
- Check for excessive special characters (>15% of input is `` ` | < > { } [ ] ``)
- Returns `True` if injection detected → HTTP 400 response

### Audit Logging

All security-sensitive operations are logged to the `audit_logs` table:

| Action | Trigger |
|--------|---------|
| `login.success` | Successful authentication |
| `login.failure` | Failed login attempt (with attempt count) |
| `token.refresh` | Token rotation |
| `account.deleted` | Account deletion |
| `session.delete` | Chat session deleted |
| `document.delete` | Document deleted |
| `agent.run` | Agent execution started |
| `agent.resume` | Agent execution resumed (HITL) |
| `agent.cancel` | Agent execution cancelled |
| `agent.export` | Draft exported as DOCX/PDF |
| `metadata.correction` | Admin metadata correction |
| `metadata.corrected` | Admin metadata correction (ingest route) |

**PII protection**: IP addresses are hashed with SHA-256 (salted with `ENCRYPTION_KEY`) before storage — the raw IP is never persisted.

### Security Headers

Applied via `SecurityHeadersMiddleware` on all responses:

| Header | Value | Purpose |
|--------|-------|---------|
| `X-Content-Type-Options` | `nosniff` | Prevent MIME-type sniffing |
| `X-Frame-Options` | `DENY` | Prevent clickjacking |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` | Force HTTPS |
| `X-XSS-Protection` | `0` | Disable legacy XSS filter (CSP preferred) |
| `Cache-Control` | `no-store` (API routes only) | Prevent caching of API responses |

**Production-only**: `TrustedHostMiddleware` rejects requests with unexpected `Host` headers.

### Middleware Stack

Middleware executes in reverse registration order (outermost first):

```
Incoming Request
    │
    ▼
TrustedHostMiddleware (prod only) — reject bad Host headers
    │
    ▼
SecurityHeadersMiddleware — add security response headers
    │
    ▼
CORSMiddleware — handle CORS preflight and headers
    │
    ▼
RequestIDMiddleware — assign X-Request-ID for distributed tracing
    │
    ▼
Route Handler
```

### Error Handling

Custom exception handlers prevent information leakage:

| Exception | Status | Response |
|-----------|--------|----------|
| `AuthenticationError` | 401 | `{error, code: "UNAUTHORIZED"}` |
| `AuthorizationError` | 403 | `{error, code: "FORBIDDEN"}` |
| `RateLimitExceededError` | 429 | `{error, code: "RATE_LIMITED"}` + `Retry-After` header |
| Unhandled `Exception` | 500 | `{error: "An internal error occurred", code: "INTERNAL_ERROR"}` |

Unhandled exceptions are captured by Sentry (if configured) with sensitive headers (`authorization`, `cookie`, `x-csrf-token`) stripped before transmission.

---

*This document describes Smriti's architecture as of March 2026. For implementation details, see [HLD.md](./HLD.md).*
