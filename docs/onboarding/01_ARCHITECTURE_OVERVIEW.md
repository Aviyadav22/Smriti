# Architecture Overview — Smriti

**Smriti** is an AI-powered Indian legal research platform — think "Harvey AI for Indian law." It combines hybrid semantic + keyword search, citation graph analysis, RAG chat, and autonomous research agents, all grounded in Indian Supreme Court judgments.

---

## System Diagram

```
                          ┌──────────────────────┐
                          │      Frontend         │
                          │   Next.js 16 (App     │
                          │   Router) + Tailwind  │
                          │   + shadcn/ui         │
                          │   Port: 3000          │
                          └──────────┬────────────┘
                                     │ REST + SSE
                          ┌──────────▼────────────┐
                          │      Backend           │
                          │   FastAPI (Python 3.12)│
                          │   Port: 8000           │
                          │                        │
                          │  ┌────────────────┐    │
                          │  │  API Routes     │    │
                          │  │  (16 routers)   │    │
                          │  └───────┬────────┘    │
                          │          │             │
                          │  ┌───────▼────────┐    │
                          │  │  Core Layer     │    │
                          │  │  - Search       │    │
                          │  │  - Chat (RAG)   │    │
                          │  │  - Agents       │    │
                          │  │  - Ingestion    │    │
                          │  │  - Legal        │    │
                          │  │  - Analytics    │    │
                          │  └───────┬────────┘    │
                          │          │             │
                          │  ┌───────▼────────┐    │
                          │  │  Interfaces     │    │
                          │  │  (Protocol      │    │
                          │  │   classes)      │    │
                          │  └───────┬────────┘    │
                          │          │             │
                          │  ┌───────▼────────┐    │
                          │  │  Providers      │    │
                          │  │  (Gemini, Pine- │    │
                          │  │  cone, Neo4j,   │    │
                          │  │  Cohere, etc.)  │    │
                          │  └────────────────┘    │
                          └────────────────────────┘
                                     │
           ┌─────────────┬───────────┼───────────┬──────────────┐
           │             │           │           │              │
    ┌──────▼─────┐ ┌─────▼────┐ ┌───▼───┐ ┌────▼────┐  ┌──────▼─────┐
    │ PostgreSQL │ │ Pinecone │ │ Neo4j │ │  Redis  │  │  Gemini AI │
    │ 16         │ │ (vector) │ │(graph)│ │ (cache) │  │  (LLM +    │
    │ - metadata │ │ 1536-dim │ │ Aura  │ │ Upstash │  │  embedding)│
    │ - FTS      │ │ cosine   │ │ DB    │ │         │  │            │
    │ - users    │ │          │ │       │ │         │  │            │
    └────────────┘ └──────────┘ └───────┘ └─────────┘  └────────────┘
                                                               │
                                              ┌────────────────┤
                                              │                │
                                        ┌─────▼─────┐  ┌──────▼─────┐
                                        │  Cohere   │  │  External  │
                                        │ (reranker)│  │  APIs      │
                                        └───────────┘  │ - IK       │
                                                       │ - Tavily   │
                                                       │ - Sarvam   │
                                                       └────────────┘
```

---

## Services

| Service | Technology | Purpose |
|---------|-----------|---------|
| **Backend** | FastAPI (Python 3.12) | Core API: auth, search, RAG chat, agents, ingestion, analytics |
| **Frontend** | Next.js 16 (TypeScript) | Web UI: search, case viewer, agent interfaces, chat, documents |
| **PostgreSQL** | PostgreSQL 16 | Metadata, FTS (tsvector), users, sessions, audit logs |
| **Pinecone** | Pinecone (managed) | Vector DB for semantic search (1536-dim, cosine, 7 vector types) |
| **Neo4j** | Neo4j AuraDB | Citation graph (cases cite cases, statutes) |
| **Redis** | Redis 7 / Upstash | Rate limiting, token revocation, search cache, semantic cache |
| **Gemini** | Google AI Studio / Vertex AI | LLM reasoning (Pro), fast tasks (Flash), embeddings |
| **Cohere** | Cohere API | Search result reranking (rerank-v4.0-pro) |
| **Nginx** | Nginx (prod only) | Reverse proxy, SSL termination, rate limiting |

---

## Key Architectural Patterns

### 1. Interface + Provider Pattern
Every external service is accessed through a `Protocol` class (interface) with concrete provider implementations. This enables swapping providers without changing business logic.

```
Interfaces (backend/app/core/interfaces/):
  LLMProvider, EmbeddingProvider, VectorStore, GraphStore,
  Reranker, FileStorage, TranslationProvider, TTSProvider,
  WebSearchProvider, ExternalDocProvider

Providers (backend/app/core/providers/):
  GeminiLLM, GeminiEmbedder, PineconeStore, Neo4jGraph,
  CohereReranker, GCSStorage, SarvamTTS, etc.

Dependencies (backend/app/core/dependencies.py):
  get_llm(), get_embedder(), get_vector_store(), etc.
  All @lru_cache singletons with config-based provider selection.
```

### 2. Modular Monolith
Single FastAPI application with clear module boundaries:
- `api/routes/` — HTTP endpoints (thin controllers)
- `core/` — Business logic modules (search, chat, agents, ingestion, legal)
- `models/` — SQLAlchemy ORM models
- `security/` — Auth, RBAC, encryption, sanitization
- `db/` — Database connection management

### 3. Hybrid Search with RRF
Search combines three signals merged via Reciprocal Rank Fusion (k=60):
1. **Semantic** — Pinecone vector similarity
2. **Keyword** — PostgreSQL `websearch_to_tsquery` FTS
3. **Reranking** — Cohere reranker scores

### 4. Multi-Vector Pinecone
Seven vector types per case in a single Pinecone index, filtered by `vector_type` metadata:
- `chunk` — Text segments (2000/200 or 1200/300)
- `proposition` — Atomic legal statements
- `ratio` — Ratio decidendi
- `headnote` — Case headnotes
- `statute` — Statute section text
- `summary` — Case summary
- `community` — Graph community description

### 5. LangGraph Agents
Research, case prep, drafting, and strategy agents use LangGraph `StateGraph`:
- Nodes are pure async functions returning partial state dicts
- Fan-out via `Send()` for parallel worker execution
- HITL via `interrupt()` for user checkpoint review
- Checkpointing: `MemorySaver` (dev) / `AsyncPostgresSaver` (prod)

### 6. SSE Streaming
All real-time features (chat, agents) use Server-Sent Events:
```
data: {"type": "status", "message": "Searching..."}\n\n
data: {"type": "chunk", "text": "Based on..."}\n\n
data: {"type": "source", "case_id": "...", "title": "..."}\n\n
data: {"type": "done"}\n\n
```

---

## Database Schema Overview

### PostgreSQL Tables (38 migrations)

**Core:**
- `cases` — Case metadata (title, citation, court, date, judges, full text, FTS vector)
- `users` — User accounts (email, hashed password, role)
- `statutes` — Statute sections (act name, section number, text, amendments)

**Search & Chat:**
- `search_history` — User search queries
- `chat_sessions` / `chat_messages` — Encrypted conversation history

**Agents:**
- `agent_sessions` — LangGraph agent sessions
- `agent_executions` — Individual agent run records

**Documents:**
- `documents` — User-uploaded PDFs
- `document_analyses` — Analysis results

**Compliance:**
- `audit_logs` — Security audit trail (IP-hashed)
- `user_consents` — DPDP consent records

**Relations:**
- `case_citation_equivalents` — Equivalent citations
- `case_sections` — Case-to-section mappings
- `case_statute_interpretations` — How cases interpret statutes

### Neo4j Graph Schema

**Nodes:** `Case`, `Statute`, `Community`
**Relationships:** `CITES` (with treatment: followed/distinguished/overruled), `INTERPRETS`, `ENACTED_UNDER`

### Pinecone Index

Single index `smriti-legal`, 1536 dimensions, cosine metric. Vectors are filtered by metadata fields including `case_id`, `vector_type`, `court`, `year`, `acts_cited`.

---

## External Dependencies

| Service | Purpose | Failure Mode |
|---------|---------|--------------|
| Gemini AI | LLM + embeddings | Circuit breaker + retry (tenacity) |
| Pinecone | Vector search | Circuit breaker (5 failures, 30s cooldown) |
| Neo4j AuraDB | Citation graph | Circuit breaker (5 failures, 60s cooldown) |
| Cohere | Reranking | Circuit breaker (3 failures, 30s cooldown) |
| Redis/Upstash | Cache + rate limiting | In-memory fallback for rate limiting |
| IndianKanoon | External legal docs | Graceful degradation |
| Tavily | Web search | Graceful degradation |
| Sarvam AI | TTS | Falls back to MockTTS |

---

## Production Deployment

- **Platform:** Google Cloud Run (containerized)
- **Domain:** smriti.legal
- **SSL:** Let's Encrypt (auto-renewed via certbot)
- **Reverse Proxy:** Nginx (API rate limiting, SSE support, gzip)
- **Monitoring:** Sentry (error tracking + performance)
- **Logging:** JSON structured logging → Google Cloud Logging
- **Migrations:** Auto-run on startup in production

### Self-hosted Alternative
The `docker-compose.prod.yml` supports a fully self-hosted deployment on an 8GB VPS using:
- `pgvector` (replaces Pinecone)
- `pg_graph_store` (replaces Neo4j)
- Total memory budget: ~5GB

---

## Data Source

**AWS S3 Open Data:** `s3://indian-supreme-court-judgments/`
- 35K+ Supreme Court judgments
- Parquet metadata (19 fields)
- CC-BY-4.0 license (attribution required)
- Public, no authentication needed
