# Data Flows — Smriti

---

## Core User Journeys

### 1. Legal Search Query

The most common user action — searching for case law.

```
User                  Frontend                    Backend
  │                      │                           │
  │  types query         │                           │
  ├─────────────────────►│                           │
  │                      │  GET /api/v1/search       │
  │                      │  ?q=...&page=1            │
  │                      ├──────────────────────────►│
  │                      │                           │ sanitize_search_query()
  │                      │                           │ understand_query() ──► Gemini Flash
  │                      │                           │   (entity extraction, query type)
  │                      │                           │
  │                      │                           │ ┌─── PARALLEL ───┐
  │                      │                           │ │ embed_query()   │──► Gemini Embedder
  │                      │                           │ │ → Pinecone      │──► Vector search
  │                      │                           │ │                 │
  │                      │                           │ │ search_fulltext │──► PostgreSQL FTS
  │                      │                           │ └─────────────────┘
  │                      │                           │
  │                      │                           │ rrf_merge(k=60)
  │                      │                           │ cohere_reranker()──► Cohere API
  │                      │                           │ enrich_from_postgres()
  │                      │                           │ check_treatment()
  │                      │                           │
  │                      │  SearchResponse (JSON)    │
  │                      │◄──────────────────────────┤
  │  renders results     │                           │
  │◄─────────────────────┤                           │
```

**Key files:**
- `backend/app/api/routes/search.py` — HTTP endpoint
- `backend/app/core/search/hybrid.py` — Hybrid search orchestrator
- `backend/app/core/search/query.py` — Query understanding (LLM)
- `backend/app/core/search/fulltext.py` — PostgreSQL FTS
- `frontend/src/app/search/page.tsx` — Search page component

### 2. RAG Chat

Conversational legal Q&A with source citations.

```
User                  Frontend                    Backend
  │                      │                           │
  │  sends message       │                           │
  ├─────────────────────►│                           │
  │                      │  POST /api/v1/chat/stream │
  │                      │  (SSE connection)         │
  │                      ├──────────────────────────►│
  │                      │                           │ load/create session
  │                      │                           │ encrypt & store message
  │                      │                           │ load chat history (decrypt)
  │                      │                           │ hybrid_search(message)
  │                      │                           │   (same as search flow above)
  │                      │                           │ check_treatment(Neo4j)
  │                      │                           │ build_grounded_prompt()
  │                      │                           │
  │                      │  SSE: {type: "session"}   │
  │                      │◄──────────────────────────┤
  │                      │  SSE: {type: "chunk"}     │ stream from Gemini Pro
  │                      │◄──────────────────────────┤
  │                      │  SSE: {type: "chunk"}     │
  │                      │◄──────────────────────────┤
  │                      │  SSE: {type: "source"}    │
  │                      │◄──────────────────────────┤
  │                      │  SSE: {type: "done"}      │
  │                      │◄──────────────────────────┤ encrypt & store response
  │  renders markdown    │                           │
  │  with citations      │                           │
  │◄─────────────────────┤                           │
```

**Key files:**
- `backend/app/api/routes/chat.py` — Chat endpoint
- `backend/app/core/chat/rag.py` — RAG pipeline
- `backend/app/core/legal/prompts.py` — System prompts
- `frontend/src/app/chat/page.tsx` — Chat page

### 3. Research Agent (Deep Legal Research)

Multi-stage autonomous research pipeline with HITL checkpoints.

```
Stage 1: UNDERSTAND
  rewrite_query → classify → statute_lookup → element_decomposition
  → route_by_complexity (simple or complex?)

Stage 2: DECOMPOSE (complex path only)
  plan_research → [HITL: user reviews plan] → approve/edit

Stage 3: INVESTIGATE
  dispatch_workers (parallel via Send()):
  ├── case_law_worker ──────► Pinecone + FTS hybrid search
  ├── named_case_worker ────► Specific case lookup
  ├── statute_worker ───────► Statute section search
  ├── graph_worker ─────────► Neo4j citation traversal
  ├── graph_community_worker► Community detection
  ├── ik_search_worker ─────► IndianKanoon API
  └── web_search_worker ────► Tavily web search

  gather_results → batch_cot_with_reflection → evaluate_and_extract
  → gap_analysis → [refine if gaps found, up to 2 rounds]

Stage 4: CHALLENGE
  adversarial_search → temporal_validation

Stage 5: SYNTHESIZE
  speculative_synthesis → format_footnotes → verify_citations_v2
  → quality_check → [HITL: user reviews memo]
```

**Worker timeouts:**
| Worker | Timeout |
|--------|---------|
| web_search_worker | 10s |
| graph_community_worker | 10s |
| graph_worker | 15s |
| statute_worker | 20s |
| case_law_worker | 30s |
| named_case_worker | 30s |
| ik_search_worker | 45s |

**Key files:**
- `backend/app/core/agents/research.py` — Graph definition
- `backend/app/core/agents/state.py` — State schema
- `backend/app/core/agents/nodes/research_nodes.py` — Research node implementations
- `backend/app/core/agents/nodes/worker_nodes.py` — Search workers
- `frontend/src/app/agents/research/page.tsx` — Research agent UI

### 4. Case Ingestion Pipeline

Batch processing of legal documents from S3 to all storage layers.

```
S3 (Public)                 Backend Script              Storage
  │                              │                         │
  │  HTTPS download              │                         │
  ├─────────────────────────────►│                         │
  │                              │ PDF text extraction     │
  │                              │ (pdfminer + NFKC +      │
  │                              │  header dedup + OCR)    │
  │                              │                         │
  │                              │ Metadata extraction     │
  │                              │ (Gemini Flash + regex)  │
  │                              │                         │
  │                              │ Legal entity extraction │
  │                              │ (acts, citations,       │
  │                              │  sections, judges)      │
  │                              │                         │
  │                              │ Chunk text              │
  │                              │ (section-aware,         │
  │                              │  sentence-boundary)     │
  │                              │                         │
  │                              │ Generate embeddings     │
  │                              │ (7 vector types)        │──► Gemini Embedder
  │                              │                         │
  │                              │ Store vectors           │──► Pinecone
  │                              │ Store metadata          │──► PostgreSQL
  │                              │ Store graph             │──► Neo4j
  │                              │                         │
  │                              │ Circuit breaker:        │
  │                              │ 10 failures → pause     │
  │                              │ Graceful shutdown       │
```

**Key files:**
- `backend/scripts/ingest_s3.py` — Standard ingestion script
- `backend/scripts/batch_ingest_vertex.py` — Vertex AI batch pipeline
- `backend/app/core/ingestion/pipeline.py` — Core pipeline logic
- `backend/app/core/ingestion/pdf.py` — PDF extraction
- `backend/app/core/ingestion/chunker.py` — Text chunking
- `backend/app/core/ingestion/metadata.py` — Metadata extraction

---

## Service Communication Map

```
┌────────────┐     REST/SSE      ┌──────────────────────────────────┐
│  Frontend   │ ◄──────────────► │            Backend               │
│  (Next.js)  │  localhost:3000  │         (FastAPI)                │
└────────────┘    → :8000       │                                  │
                                 │  Middleware Stack:               │
                                 │  TrustedHost → SecurityHeaders  │
                                 │  → SizeLimit → CORS → RequestID │
                                 │                                  │
                                 │  16 API Routers                  │
                                 │  ┌─────────────────────────┐    │
                                 │  │ auth, search, cases,     │    │
                                 │  │ chat, agents, graph,     │    │
                                 │  │ documents, judges,       │    │
                                 │  │ counsel, audio, ingest,  │    │
                                 │  │ dpdp, admin, sharing,    │    │
                                 │  │ preferences, health      │    │
                                 │  └─────────────────────────┘    │
                                 └────────────────┬─────────────────┘
                                                  │
              ┌───────────────────────────────────┼──────────────────────┐
              │                 │                  │                      │
        ┌─────▼─────┐   ┌──────▼──────┐   ┌──────▼──────┐   ┌─────────▼──────┐
        │ PostgreSQL │   │  Pinecone   │   │   Neo4j     │   │     Redis      │
        │            │   │             │   │   AuraDB    │   │   (Upstash)    │
        │ Tables:    │   │ Index:      │   │             │   │                │
        │ - cases    │   │ smriti-     │   │ Nodes:      │   │ - Rate limits  │
        │ - users    │   │ legal       │   │ Case,       │   │ - Token revoke │
        │ - statutes │   │             │   │ Statute,    │   │ - Search cache │
        │ - chat_*   │   │ 1536-dim    │   │ Community   │   │ - Semantic $   │
        │ - agents   │   │ 7 vec types │   │             │   │                │
        │ - audit    │   │             │   │ Rels:       │   │                │
        │ - docs     │   │             │   │ CITES,      │   │                │
        │            │   │             │   │ INTERPRETS  │   │                │
        └────────────┘   └──────────────┘  └─────────────┘   └────────────────┘
```

---

## Caching Strategy

| What | Where | TTL | Purpose |
|------|-------|-----|---------|
| Search results | Redis | 300s (5 min) | Avoid re-running expensive hybrid search |
| Search facets | Redis | 900s (15 min) | Court/year/type facet aggregations |
| Semantic query cache | Redis | Varies | Cache query embeddings to avoid re-embedding |
| Rate limit counters | Redis | Window-based | Sliding window rate limiting |
| Token revocation | Redis | Token expiry | JWT revocation blacklist |
| Chat history | PostgreSQL (encrypted) | Permanent | Conversation persistence |
| Agent checkpoints | PostgreSQL | Permanent | LangGraph state for resume |
| Research results | PostgreSQL | Permanent | Cached agent research outputs |
| Provider instances | `@lru_cache` (in-memory) | Process lifetime | Singleton service providers |

---

## Error Propagation

```
Client Request
    │
    ▼
Middleware (RequestID, CORS, etc.)
    │
    ▼
Route Handler
    │
    ├── AuthenticationError → 401 {"error": "...", "code": "UNAUTHORIZED"}
    ├── AuthorizationError  → 403 {"error": "...", "code": "FORBIDDEN"}
    ├── RateLimitExceeded   → 429 {"error": "...", "code": "RATE_LIMITED"}
    │                              + Retry-After header
    ├── HTTPException       → status_code + detail
    └── Unhandled Exception → 500 {"error": "An internal error occurred",
                                    "code": "INTERNAL_ERROR"}
                                   + Sentry capture
                                   + Structured log entry
```

---

## Startup / Shutdown Lifecycle

### Startup
1. Configure structured logging (JSON in prod, human-readable in dev)
2. Initialize Sentry if `SENTRY_DSN` is set
3. Run Alembic migrations (production only, auto-runs `alembic upgrade head`)
4. Health checks (non-blocking, logs warnings):
   - PostgreSQL: `SELECT 1`
   - Redis: `PING`
   - Pinecone: `describe_index_stats()` (verify 1536 dimensions)
   - Gemini: `list models`
5. Launch expired upload cleanup task (DPDP compliance)

### Shutdown (with 10s timeouts per step)
1. Dispose SQLAlchemy engine (release DB connections)
2. Close Redis connection
3. Close cached providers (graph store, reranker, IndianKanoon, Tavily)
