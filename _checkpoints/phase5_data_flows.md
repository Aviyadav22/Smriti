# Phase 5: Data Flow Mapping
**Generated:** 2026-04-03

## Core User Journeys

### Journey 1: Legal Research Query (Search)

```
1. User types query in SearchPage (frontend/src/app/search/page.tsx)
2. Frontend calls GET /api/v1/search?q={query}&page=1&page_size=10
3. Backend search route → sanitize_search_query(query)
4. hybrid_search() orchestrates:
   a. understand_query(query, llm) — LLM-based query understanding
      → extracts entities (acts, sections, courts, dates)
      → classifies query type (factual, conceptual, case-specific)
   b. Parallel execution:
      - Semantic search: embed query → Pinecone vector search (top-K)
      - FTS search: search_fulltext() → PostgreSQL websearch_to_tsquery
   c. RRF merge (k=60): Reciprocal Rank Fusion of both result sets
   d. Cohere reranker: rerank merged results
   e. PostgreSQL enrichment: fetch metadata (title, court, date, judges)
   f. Treatment detection: check for overruling language
5. Response: SearchResponse with results, facets, query_understanding
6. Frontend renders search results with snippets, citations, badges
```

### Journey 2: RAG Chat (Conversational Legal Research)

```
1. User types message in ChatPage (frontend/src/app/chat/page.tsx)
2. Frontend POST /api/v1/chat/stream (SSE streaming)
   Body: { message, session_id?, case_id? }
3. Backend chat route:
   a. Load/create chat session in PostgreSQL
   b. Encrypt and store user message
   c. Load conversation history (last N messages, decrypt each)
   d. hybrid_search(user_message) — same pipeline as Journey 1
   e. Fetch ratios, bench info, judge names for top results
   f. Check treatment status via Neo4j graph
   g. Build grounded prompt: CHAT_SYSTEM_PROMPT + context passages + history
   h. Stream response from Gemini 3.1 Pro via SSE
4. SSE events:
   - type: "session" → session_id
   - type: "chunk" → text delta
   - type: "source" → { case_id, title, citation, ratio, bench_type }
   - type: "done" → final signal
5. Backend: encrypt and store assistant response
6. Frontend: renders markdown stream with inline citations
```

### Journey 3: Research Agent (Deep Legal Research Memo)

```
1. User types research question in ResearchPage
2. Frontend POST /api/v1/agents/research/start (SSE streaming)
3. Backend builds LangGraph StateGraph:

   STAGE 1 — UNDERSTAND:
   a. rewrite_query: Reformulate for legal precision
   b. classify_query: Determine complexity (simple vs complex)
   c. statute_lookup: Read relevant statute text from DB BEFORE planning
   d. element_decomposition: Break legal question into testable elements
   e. route_by_complexity: Simple → fast path, Complex → full pipeline

   STAGE 2 — DECOMPOSE (complex path):
   f. plan_research: Create research plan with sub-queries
   g. checkpoint_plan: HITL interrupt — user reviews/edits plan

   STAGE 3 — INVESTIGATE:
   h. dispatch_workers: Fan-out via LangGraph Send() to parallel workers:
      - case_law_worker: Pinecone semantic + FTS hybrid search
      - named_case_worker: Specific case lookups
      - statute_worker: Statute section search
      - graph_worker: Neo4j citation graph traversal
      - graph_community_worker: Community detection in graph
      - ik_search_worker: IndianKanoon external API
      - web_search_worker: Tavily web search
   i. gather_results: Collect all worker outputs
   j. batch_cot_with_reflection: Chain-of-thought analysis + self-reflection
   k. evaluate_and_extract: Score relevance, extract key findings
   l. gap_analysis → conditional refinement loop (up to 2 iterations)

   STAGE 4 — CHALLENGE:
   m. adversarial_search: Find counter-arguments and opposing precedents
   n. temporal_validation: Verify precedent currency (not overruled)

   STAGE 5 — SYNTHESIZE:
   o. speculative_synthesis: Generate comprehensive legal memo
   p. format_footnotes: Create proper legal citation footnotes
   q. verify_citations_v2: Cross-check all cited cases exist
   r. quality_check: Legal quality scoring
   s. checkpoint_memo: HITL — user reviews final memo

4. SSE events throughout:
   - status: Stage progress updates
   - progress: Worker completion tracking
   - checkpoint: HITL pause points for user input
   - memo: Final research memo
   - done: Completion
5. Frontend renders step timeline, progress bar, memo viewer
```

### Journey 4: Case Detail View

```
1. User clicks case from search results
2. Frontend GET /api/v1/cases/{case_id}
3. Backend: Full case metadata + text from PostgreSQL
4. Frontend GET /api/v1/graph/mini/{case_id}
5. Backend: Neo4j citation subgraph (citing/cited cases, 2 hops)
6. Frontend renders: case metadata, full text, citation graph mini-view,
   equivalent citations, section analysis, timeline
```

### Journey 5: Document Upload & Analysis

```
1. User uploads PDF in UploadPage
2. Frontend POST /api/v1/documents/upload (multipart/form-data)
3. Backend:
   a. Validate file type + size (<10MB)
   b. Store PDF via FileStorage (local or GCS)
   c. Create document record in PostgreSQL
   d. Launch background task: document_tasks.process_document()
      - PDF text extraction (pdfminer + OCR fallback)
      - LLM metadata extraction
      - Document analysis
4. Frontend polls GET /api/v1/documents/{id} for processing status
```

## Service Communication Map

```
┌────────────┐     REST/SSE      ┌─────────────┐
│  Frontend   │ ◄──────────────► │   Backend    │
│  (Next.js)  │                  │  (FastAPI)   │
└────────────┘                  └──────┬───────┘
                                       │
              ┌────────────────────────┼────────────────────────┐
              │                        │                        │
        ┌─────▼─────┐          ┌──────▼──────┐          ┌─────▼──────┐
        │ PostgreSQL │          │  Pinecone   │          │   Neo4j    │
        │   (FTS +   │          │  (vectors)  │          │  (graph)   │
        │  metadata) │          └─────────────┘          └────────────┘
        └────────────┘                │
              │                 ┌─────▼─────┐
        ┌─────▼─────┐          │  Gemini AI │
        │   Redis    │          │ (LLM/Embed)│
        │  (cache +  │          └────────────┘
        │  sessions) │                │
        └────────────┘          ┌─────▼──────┐
                                │   Cohere   │
                                │ (reranker) │
                                └────────────┘
                                      │
              ┌───────────────────────┼───────────────┐
              │                       │               │
        ┌─────▼──────┐        ┌──────▼─────┐  ┌─────▼──────┐
        │   Sarvam   │        │   Tavily   │  │IndianKanoon│
        │   (TTS)    │        │ (web srch) │  │ (ext docs) │
        └────────────┘        └────────────┘  └────────────┘
```

## Provider Architecture (Dependency Injection)

All external services accessed via Interface → Provider pattern:

| Interface (Protocol) | Provider | Config Switch |
|----------------------|----------|---------------|
| `LLMProvider` | `GeminiLLM` | `llm_provider=gemini` |
| `EmbeddingProvider` | `GeminiEmbedder` | `llm_provider=gemini` |
| `VectorStore` | `PineconeStore` / `PgvectorStore` | `vector_provider=pinecone|pgvector` |
| `GraphStore` | `Neo4jGraph` / `PgGraphStore` | `graph_provider=neo4j|postgresql` |
| `Reranker` | `CohereReranker` | `reranker_provider=cohere` |
| `FileStorage` | `LocalStorage` / `GCSStorage` | `storage_provider=local|gcs` |
| `TranslationProvider` | `GeminiTranslator` | `llm_provider=gemini` |
| `TTSProvider` | `SarvamTTS` / `MockTTS` | `tts_provider=sarvam` |
| `WebSearchProvider` | `TavilySearchClient` | (always tavily) |
| `ExternalDocProvider` | `IndianKanoonClient` | (always IK) |

### Circuit Breakers
- `pinecone_breaker`: 5 failures → 30s cooldown
- `neo4j_breaker`: 5 failures → 60s cooldown
- `cohere_breaker`: 3 failures → 30s cooldown

## Caching Strategy

| Cache | Storage | Purpose |
|-------|---------|---------|
| Semantic cache | Redis (shared) | Cache query→embedding mappings |
| Rate limit buckets | Redis (shared) | Sliding window counters |
| Token revocation | Redis (shared) | JWT revocation blacklist |
| Chat history | PostgreSQL (encrypted) | Persistent conversation history |
| Agent sessions | PostgreSQL | LangGraph checkpoints |
| Provider instances | `@lru_cache` (in-memory) | Singleton service providers |
| LangGraph checkpointer | MemorySaver (dev) / AsyncPostgresSaver (prod) | Agent state persistence |
| Research cache | PostgreSQL | Cache previous research results |

## Batch Processing Flows

### Ingestion Pipeline (ingest_s3.py / batch_ingest_vertex.py)

```
Trigger: Manual CLI command (python scripts/ingest_s3.py)
         or Vertex AI batch (python scripts/batch_ingest_vertex.py)

Standard Pipeline (ingest_s3.py):
1. Download PDFs from S3 (HTTPS, public bucket)
2. For each PDF:
   a. Extract text (pdfminer + NFKC normalization + OCR fallback)
   b. Extract metadata via Gemini Flash (JSON schema output)
   c. Regex supplementation (acts, citations, case_number)
   d. Chunk text (section-aware, 2000/200 standard, 1200/300 dense)
   e. Generate embeddings (Gemini, 7 vector types)
   f. Upsert vectors to Pinecone (with enriched metadata)
   g. Insert/update PostgreSQL (case metadata + FTS)
   h. MERGE nodes/relationships to Neo4j
3. Circuit breaker: 10 consecutive failures → pause
4. Graceful shutdown: SIGINT/SIGTERM handler

Vertex AI Batch Pipeline (batch_ingest_vertex.py):
Phase 1: Text extraction + GCS upload (all PDFs)
Phase 2: Batch metadata extraction (Vertex AI batch job, 50% cheaper)
Phase 3: Per-case online processing (chunks, embeddings, storage)
Phase 4: Quality check (sample 10 cases, verify 5 vector types)

Cost: ~$34/1K cases
Resume: --resume <run_id> reloads progress.json
```

### Statute Ingestion (ingest_statutes.py)

```
1. Read JSON statute files from data/statutes/
2. Parse sections, titles, text
3. Insert to PostgreSQL statutes table
4. Generate embeddings → Pinecone (vector_type=statute)
5. Create Neo4j Statute nodes with ENACTED_UNDER relationships
```

## Startup Lifecycle

```
Application Start (main.py lifespan):
1. Configure structured logging (JSON prod / human-readable dev)
2. Initialize Sentry (if DSN configured)
3. Run Alembic migrations (production only)
4. Validate startup:
   - PostgreSQL: SELECT 1
   - Redis: PING
   - Pinecone: describe_index_stats (verify 1536 dimensions)
   - Gemini: list models
5. Launch expired upload cleanup (DPDP compliance)

Shutdown:
1. Dispose SQLAlchemy engine (10s timeout)
2. Close Redis connection (10s timeout)
3. Close cached providers (graph store, reranker, etc.) (10s timeout)
```

## Middleware Stack (Order of Execution)

```
Request → TrustedHost (prod only) → SecurityHeaders → RequestSizeLimit
        → CORS → RequestID → Route Handler
Response ← TrustedHost ← SecurityHeaders ← CORS ← RequestID ← Handler
```

## Error Propagation

```
Route Handler
  → catches domain exceptions → HTTPException
  → uncaught → @app.exception_handler(Exception)
    → logs error + Sentry capture
    → returns 500 { error: "An internal error occurred", code: "INTERNAL_ERROR" }

Custom exceptions:
  AuthenticationError → 401 { error, code: "UNAUTHORIZED" }
  AuthorizationError → 403 { error, code: "FORBIDDEN" }
  RateLimitExceededError → 429 { error, code: "RATE_LIMITED", Retry-After header }
```

## File Upload/Download Flow

```
Upload:
  User → POST /api/v1/documents/upload (multipart, <10MB)
  → FileStorage.save() (local: data/uploads/, GCS: gs://bucket/path)
  → Document record in PostgreSQL
  → Background processing task

Download:
  User → GET /api/v1/documents/{id}/download
  → FileStorage.get() → StreamingResponse

Audio (TTS):
  User → POST /api/v1/cases/{id}/audio
  → background_task: generate audio via Sarvam TTS
  → FileStorage.save()
  → GET /api/v1/cases/{id}/audio → StreamingResponse
```
