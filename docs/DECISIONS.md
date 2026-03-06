# Smriti — Architecture Decision Records (ADRs)

Each ADR follows: **Context → Decision → Alternatives → Consequences**.

---

## ADR-001: Build From Scratch vs. Modify AnythingLLM

**Status**: Accepted
**Date**: 2026-03

### Context
We had a working ParalegalAI prototype built on AnythingLLM (Node.js/Express). It had hybrid search, metadata extraction, and a chat interface. However:
- ~70% of the AnythingLLM codebase was irrelevant (multi-model support, workspace management, embed widgets)
- Search accuracy was poor: no real BM25, weak embeddings (MiniLM-L6-v2, 384-dim), small chunks (1000/20), regex-only metadata
- JavaScript ecosystem is weaker for AI/ML workloads
- Code was messy and hard to extend

### Decision
**Build from scratch** in Python (FastAPI) + Next.js. Reference old codebase only for:
- Indian citation regex patterns (5 formats)
- Court name dictionary and case type lists
- PostgreSQL schema design (fields, indexes, FTS weights)
- Metadata relevance scoring logic

No code is copied. Everything is rewritten cleanly.

### Alternatives Considered
1. **Fork and modify AnythingLLM**: Faster start, but 70% dead code, wrong language for AI, hard to add legal-specific features
2. **Use another open-source RAG framework (Danswer, PrivateGPT)**: Still generic, not designed for legal domain

### Consequences
- (+) Clean, purpose-built codebase optimized for Indian legal research
- (+) Python ecosystem for AI/ML (Gemini SDK, pdfplumber, sentence-transformers)
- (+) Full control over architecture and security
- (-) Longer initial development time
- (-) No working prototype while building

---

## ADR-002: FastAPI Over Express.js

**Status**: Accepted
**Date**: 2026-03

### Context
Need a backend framework for AI-heavy workloads: LLM calls, embedding generation, PDF processing, graph queries.

### Decision
**FastAPI** (Python 3.12)

### Alternatives Considered
1. **Express.js (Node.js)**: Good for I/O, but weak AI/ML ecosystem, no native async LLM streaming, poor PDF processing libraries
2. **Django**: Too heavy for API-first design, ORM doesn't play well with async
3. **Flask**: No async support, no built-in validation, would need many extensions

### Consequences
- (+) Native async/await for concurrent LLM + DB + vector calls
- (+) Pydantic for input validation (security) and structured LLM output
- (+) First-class OpenAPI docs (auto-generated)
- (+) Best AI/ML library ecosystem (Google GenAI SDK, pdfplumber, Neo4j driver)
- (+) Type hints throughout
- (-) Slightly more complex deployment than Express

---

## ADR-003: Next.js 15 Over React + Vite

**Status**: Accepted
**Date**: 2026-03

### Context
Need a frontend framework for a search-heavy, SEO-friendly application.

### Decision
**Next.js 15** (App Router) with TypeScript, Tailwind CSS, and shadcn/ui

### Alternatives Considered
1. **React + Vite**: Lighter, but no SSR (bad for SEO), no API routes, manual routing
2. **Remix**: Good SSR, but smaller ecosystem, fewer deployment options
3. **Svelte/SvelteKit**: Excellent performance, but smaller talent pool

### Consequences
- (+) SSR for search results (SEO for case law pages)
- (+) App Router: layouts, loading states, error boundaries built-in
- (+) Deploy to Vercel free tier (0 cost for frontend)
- (+) shadcn/ui: accessible, customizable components without CSS-in-JS overhead
- (-) App Router still evolving, some patterns aren't well documented

---

## ADR-004: PostgreSQL Over MySQL / MongoDB

**Status**: Accepted
**Date**: 2026-03

### Context
Need a primary database for case metadata, user data, chat history, audit logs. Must support full-text search.

### Decision
**PostgreSQL 16** (Neon free tier → Cloud SQL for production)

### Alternatives Considered
1. **MySQL**: Weaker FTS, no tsvector/ts_rank_cd equivalent, less advanced indexing
2. **MongoDB**: No relational integrity, FTS is basic, harder to enforce schema
3. **SQLite**: No concurrent access, not suitable for production web app

### Consequences
- (+) Best-in-class FTS with tsvector, ts_rank_cd, weighted lexemes
- (+) GIN indexes for fast text search
- (+) Relational integrity for metadata (foreign keys, constraints)
- (+) Neon free tier for development (0 cost)
- (+) Cloud SQL on GCP for production (managed backups, SSL)
- (+) Excellent SQLAlchemy async support
- (-) More setup than MongoDB for flexible schemas

---

## ADR-005: Pinecone Over pgvector / Qdrant / Weaviate

**Status**: Accepted
**Date**: 2026-03

### Context
Need a vector database for semantic search. Must handle 100K+ vectors with metadata filtering.

### Decision
**Pinecone** (free tier → Starter plan)

### Alternatives Considered
1. **pgvector**: Keeps everything in PostgreSQL, but query performance degrades at scale, no native metadata filtering optimization
2. **Qdrant**: Open-source, good performance, but requires self-hosting (more ops burden)
3. **Weaviate**: Feature-rich but complex, heavy resource requirements
4. **Chroma**: Good for prototyping, not production-ready at scale

### Consequences
- (+) Managed service: zero ops overhead
- (+) Free tier: 100K vectors (enough for 5,000+ judgments with chunking)
- (+) Native metadata filtering (court, year, case_type) at query time
- (+) Excellent Python SDK
- (+) Scales well if we need Starter plan ($70/mo for 1M vectors)
- (-) Vendor lock-in (mitigated by VectorStore interface)
- (-) Data leaves our infra (Pinecone is US-hosted; judgment data is public domain so acceptable)

---

## ADR-006: Neo4j Over Recursive CTEs / NetworkX

**Status**: Accepted
**Date**: 2026-03

### Context
Indian case law is inherently a citation graph. Judgments cite, overrule, affirm, and distinguish other judgments. Need graph traversal: "what cases cite this case?", "citation chain from A to B", "most authoritative case on topic X".

### Decision
**Neo4j AuraDB** (free tier: 200K nodes, 400K relationships)

### Alternatives Considered
1. **PostgreSQL recursive CTEs**: Can model graphs, but painful for multi-hop traversals, no native graph algorithms
2. **NetworkX (in-memory)**: Good for analysis, but doesn't persist, can't scale to millions of relationships
3. **Amazon Neptune**: Expensive, AWS-only
4. **No graph (flat references)**: Lose the ability to traverse citation chains

### Consequences
- (+) Native graph queries (Cypher): citation chains, authority scoring, pattern matching
- (+) Graph algorithms: PageRank for "most authoritative" cases
- (+) Free tier: 200K nodes covers SC judgments + statutes easily
- (+) Visual graph exploration in Neo4j Browser (useful for debugging)
- (+) Separation of concerns: relational data in PostgreSQL, graph data in Neo4j
- (-) Another service to manage
- (-) Data synchronization between PostgreSQL and Neo4j

---

## ADR-007: Gemini 3.1 Pro Over Claude / GPT-4

**Status**: Accepted
**Date**: 2026-03

### Context
Need an LLM for: metadata extraction, query understanding, RAG chat, section detection. Budget: $300 GCP credits (3-month trial).

### Decision
**Gemini 3.1 Pro** via Vertex AI

### Alternatives Considered
1. **Claude 3.5 Sonnet/Opus**: Excellent reasoning, but no free credits, $3-15/M input tokens
2. **GPT-4o**: Strong all-rounder, but no free credits, $2.50/M input
3. **Gemini Flash**: Cheaper but weaker for complex legal analysis
4. **Open-source (Llama 3)**: Free but requires GPU hosting ($200+/mo)

### Consequences
- (+) $300 free credits for 3 months covers MVP development
- (+) 1M token context window (entire judgments in one call)
- (+) Structured JSON output mode (native, not prompt-hacked)
- (+) $2/M input, $12/M output — competitive pricing after credits
- (+) Vertex AI integration with other GCP services
- (-) Vendor lock-in to Google ecosystem (mitigated by LLMProvider interface)
- (-) May need to switch to Flash for cost optimization on bulk tasks

---

## ADR-008: Cohere Rerank-v3 Over Cross-Encoder / Gemini Reranking

**Status**: Accepted
**Date**: 2026-03

### Context
Hybrid search produces merged results from vector + FTS. Need reranking to improve final result quality.

### Decision
**Cohere rerank-v4.0-pro** (1,000 free API calls/month)

### Alternatives Considered
1. **Cross-encoder reranking (local)**: Good quality but requires GPU or is very slow on CPU
2. **Gemini as reranker**: Possible but expensive (uses LLM tokens for a ranking task)
3. **No reranking**: RRF alone may be sufficient, but legal queries benefit from semantic reranking
4. **ColBERT v2**: Research-grade, complex setup

### Consequences
- (+) Best-in-class reranking quality
- (+) 1,000 free calls/month (enough for ~200 search queries/day if reranking top 20)
- (+) Simple API: pass query + documents, get ranked results
- (+) Fast: <200ms for 20 documents
- (-) 1,000 free calls may not be enough at scale ($1/1K calls after)
- (-) Another external dependency (mitigated by Reranker interface, can fallback to Gemini)

---

## ADR-009: Reciprocal Rank Fusion Over Weighted Sum

**Status**: Accepted
**Date**: 2026-03

### Context
Need to merge results from multiple search sources (vector, FTS, metadata) into a single ranked list.

### Decision
**Reciprocal Rank Fusion (RRF)** with k=60

### Alternatives Considered
1. **Weighted score sum** (e.g., 0.6 × vector + 0.3 × FTS + 0.1 × metadata): Requires score normalization across different scales
2. **Learned-to-rank**: Requires training data we don't have yet
3. **Take top-N from each, deduplicate**: Loses ranking information

### Consequences
- (+) Score-agnostic: works with any ranking source regardless of score scale
- (+) Well-studied in IR literature, proven effective
- (+) Simple formula: `score = Σ 1/(k + rank_i)` — easy to implement and debug
- (+) k=60 is standard, balances head and tail results
- (-) All sources weighted equally (can add source-specific weights later if needed)
- (-) Doesn't learn from user feedback (future enhancement)

---

## ADR-010: Monolith for MVP Over Microservices

**Status**: Accepted
**Date**: 2026-03

### Context
System has multiple concerns: search, ingestion, chat, graph, auth. Could be separate services or one monolith.

### Decision
**Modular monolith**: Single FastAPI application with clear module boundaries (core/search, core/ingestion, core/legal, etc.). Deploy as one Cloud Run service.

### Alternatives Considered
1. **Microservices**: Search service, ingestion service, chat service, auth service — independent deployment
2. **Serverless functions**: Each endpoint as a Cloud Function

### Consequences
- (+) Simple deployment: one Docker image, one Cloud Run service
- (+) No inter-service communication overhead (no gRPC, no message queues)
- (+) Shared database connections (connection pool efficiency)
- (+) Easy to refactor modules without service boundary changes
- (+) Lower cost: one Cloud Run instance vs. multiple
- (-) Must be disciplined about module boundaries (no circular imports)
- (-) Can't scale search independently from ingestion (acceptable for MVP)
- **Migration path**: If a module needs independent scaling, extract it as a separate Cloud Run service behind the same API gateway

---

## ADR-011: Protocol Pattern for Dependency Injection

**Status**: Accepted
**Date**: 2026-03

### Context
External services (LLM, vector DB, graph DB, reranker, storage) will change over time. Need to swap implementations without touching business logic.

### Decision
**Python Protocol classes** (structural subtyping) for all external interfaces, with FastAPI `Depends()` for injection.

### Alternatives Considered
1. **ABC (Abstract Base Class)**: Explicit inheritance required, more rigid
2. **Duck typing (no interface)**: Works in Python but no IDE support, no type checking
3. **Dependency injection frameworks** (python-inject, injector): Overhead for a small team

### Consequences
- (+) Structural subtyping: any class with matching methods satisfies the Protocol (no inheritance needed)
- (+) mypy verifies implementations at type-check time
- (+) FastAPI Depends() is the natural injection point (already built into the framework)
- (+) Swapping providers is config change + new file, zero business logic changes
- (+) Easy to mock for testing
- (-) Protocols don't enforce method implementation at class definition time (only at call site or type-check)

---

## ADR-012: Legal-Aware Chunking Over Fixed-Size

**Status**: Accepted
**Date**: 2026-03

### Context
Judgments have distinct sections (Facts, Arguments, Ratio, Order). Chunking across section boundaries loses context and degrades search quality.

### Decision
**Section-aware chunking**: detect judgment sections first, then chunk within sections. 2000-char chunks with 200-char overlap. Each chunk tagged with section type.

### Alternatives Considered
1. **Fixed-size chunking** (1000 chars, 20 overlap): Simple but loses section context, chunks may span Facts→Order
2. **Semantic chunking** (sentence-level clustering): Complex, slow, unpredictable chunk sizes
3. **Paragraph-based chunking**: Paragraph boundaries don't align with legal sections
4. **No chunking (full document)**: Embedding quality degrades on long text, exceeds embedding model limits

### Consequences
- (+) Each chunk has a known section type (useful for search: "find ratio decidendi about X")
- (+) No cross-section contamination
- (+) 2000 chars captures meaningful legal reasoning (vs. 1000 in old system)
- (+) 200-char overlap preserves context across chunk boundaries
- (+) Parent-child: retrieve small chunk, return full section for context
- (-) Section detection adds complexity (regex + LLM fallback)
- (-) Some judgments don't follow standard section structure

---

## ADR-013: LLM Metadata Extraction Over Regex-Only

**Status**: Accepted
**Date**: 2026-03

### Context
Need to extract structured metadata from judgment text: acts cited, cases cited, ratio decidendi, keywords, bench type. Regex alone can't extract semantic fields like ratio decidendi.

### Decision
**Gemini 3.1 Pro structured output** as primary extraction, with regex patterns as validation/fallback.

### Alternatives Considered
1. **Regex-only**: Fast, deterministic, but can't extract ratio decidendi, keywords, or bench type
2. **NER models (spaCy, HuggingFace)**: Would need legal-specific training data we don't have
3. **LLM-only (no regex validation)**: Risk of hallucinated citations or incorrect dates

### Consequences
- (+) Can extract semantic fields (ratio decidendi, keywords, bench type)
- (+) Handles diverse formatting across 75 years of judgments
- (+) Regex validates LLM output (catches hallucinated citations, dates)
- (+) Parquet metadata from S3 is ground truth for structured fields (title, court, year)
- (-) Cost: ~$0.046 per judgment for Gemini extraction
- (-) Latency: ~2-3 seconds per judgment (acceptable for batch ingestion)
- (-) LLM may hallucinate (mitigated by regex validation + Parquet ground truth)

---

## ADR-014: Cloud Run Over GKE / Compute Engine

**Status**: Accepted
**Date**: 2026-03

### Context
Need to deploy FastAPI backend on GCP. Budget-conscious ($300 credits, then <$500/mo).

### Decision
**Cloud Run** (fully managed, auto-scaling, pay-per-use)

### Alternatives Considered
1. **GKE (Kubernetes)**: Overkill for a single service, $70+/mo minimum for control plane
2. **Compute Engine (VM)**: Always-on costs, manual scaling, more ops work
3. **Cloud Functions**: Cold start issues, not suited for long-running LLM calls
4. **App Engine**: Less flexible, pricing less predictable

### Consequences
- (+) Scale to zero when not in use (save money during low traffic)
- (+) Auto-scale up to 10 instances under load
- (+) Simple deployment: push Docker image, set env vars
- (+) Built-in HTTPS, load balancing, health checks
- (+) ~$10-30/mo for expected MVP traffic
- (-) Cold start latency (~2-5s) on first request after scale-down (mitigate with min instances = 1)
- (-) Request timeout of 60 minutes (sufficient for any API call)

---

## ADR-015: CC-BY-4.0 Dataset Over Web Scraping

**Status**: Accepted
**Date**: 2026-03

### Context
Need Indian court judgment data. Options: scrape from ecourts.gov.in, use IndianKanoon API, or use pre-compiled AWS Open Data dataset.

### Decision
**AWS Open Data S3 dataset** (indian-supreme-court-judgments) as primary source.

### Alternatives Considered
1. **Web scraping ecourts.gov.in**: Legal gray area, unreliable, rate-limited, could get blocked
2. **IndianKanoon API**: Good coverage (30M+ docs) but costs money at scale, commercial licensing required
3. **SCC Online / Manupatra API**: Premium services, expensive partnerships needed

### Consequences
- (+) CC-BY-4.0 license: explicitly allows commercial use with attribution
- (+) Pre-compiled: 35K SC judgments in tar/zip + Parquet metadata (19 fields)
- (+) No authentication required: `--no-sign-request`
- (+) Bi-monthly updates by Dattam Labs
- (+) Also available: 16.7M High Court judgments (same license, Phase 2)
- (+) Parquet metadata saves LLM costs (structured fields already extracted)
- (-) Only SC judgments initially (HCs in Phase 2)
- (-) Dataset may lag 1-2 months behind live court orders
- (-) Must display attribution: "Indian Supreme Court Judgments dataset by Dattam Labs, licensed under CC-BY-4.0"
