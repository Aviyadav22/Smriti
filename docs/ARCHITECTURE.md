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
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐  │
│  │  Search   │ │ Ingest   │ │  Chat    │ │  Auth    │ │ Citation Graph   │  │
│  │  Router   │ │ Router   │ │  Router  │ │  Router  │ │ Router           │  │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────────┬─────────┘  │
│       │             │            │             │                │            │
│  ┌────▼─────────────▼────────────▼─────────────▼────────────────▼────────┐  │
│  │                        CORE SERVICE LAYER                             │  │
│  │  HybridSearchOrchestrator / IngestionPipeline / ChatEngine / RBAC     │  │
│  └────┬─────────────┬────────────┬─────────────┬────────────────┬────────┘  │
│       │             │            │             │                │            │
│  ┌────▼─────────────▼────────────▼─────────────▼────────────────▼────────┐  │
│  │                     PROVIDER INTERFACE LAYER                           │  │
│  │  LLMProvider / VectorStore / EmbeddingProvider / Reranker / GraphStore │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
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
└──────────────┘ └──────────────┘ └──────────────┘ └───────────┘ └────────────┘
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

*This document describes Smriti's architecture as of March 2026. For implementation details, see [HLD.md](./HLD.md).*
