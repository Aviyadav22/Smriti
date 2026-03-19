# Smriti

**AI-powered Indian legal research platform -- Harvey AI for Indian law.**

Smriti combines hybrid semantic + keyword search, citation graph analysis, RAG-powered chat, and autonomous AI agents to help legal professionals navigate India's vast body of Supreme Court jurisprudence. Every answer is grounded in real judgments, not hallucinated.

![Tests: 1443 backend](https://img.shields.io/badge/backend_tests-1443-brightgreen)
![Tests: 298 frontend](https://img.shields.io/badge/frontend_tests-298-brightgreen)
![Phase: 8 complete](https://img.shields.io/badge/phase-8%20complete-blue)
![Python 3.12](https://img.shields.io/badge/python-3.12-blue)
![Next.js 16](https://img.shields.io/badge/next.js-16-black)

---

## Features

### Hybrid Search
- **Semantic search** powered by Gemini embeddings (1536-dim) via Pinecone
- **Full-text search** with PostgreSQL tsvector, legal term boosting, and weighted RRF
- **Reciprocal Rank Fusion (RRF, k=60)** merges results from multiple retrieval strategies
- **Cohere reranking** (rerank-v4.0-pro) for precision at the top of results
- Faceted filtering: court, year range, case type, bench type, judge, act
- Search strategy routing: exact citation, topical, and filtered queries

### Citation Graph
- Neo4j-backed citation network: CITES, OVERRULES, AFFIRMS, DISTINGUISHES
- Interactive force-directed graph visualization (react-force-graph-2d)
- Authority scoring, citation chain analysis (up to 3 hops)
- Citation equivalence matching (AIR, SCC, SCR cross-format)
- Precedent strength classification (binding / persuasive / distinguished / overruled)

### RAG Chat
- Streaming chat with inline citation grounding (SSE)
- Every claim linked to source judgment chunks with verification
- Chat history encrypted per-user (AES-256-GCM)
- Anti-sycophancy prompts and legal disclaimers on all AI output

### AI Agents (LangGraph)
Four autonomous agents with human-in-the-loop checkpoints:
- **Research Agent** -- Decomposes legal questions into sub-queries, runs parallel search, detects contradictions, produces structured research memos
- **Case Prep Agent** -- Builds on document analysis, prioritizes issues, deep precedent search via citation graph, generates strategy memos
- **Strategy Agent** -- Predicts opposing arguments, assesses case strength, provides judge-specific considerations
- **Drafting Agent** -- Generates bail applications, writ petitions, written statements, legal notices, appeals, and interim applications

### Judge Analytics
- Judge profiles with disposal patterns, bench combinations, top cited judgments
- Side-by-side judge comparison
- Court-level aggregate statistics

### Document Upload and Analysis
- Upload briefs (PDF, up to 50MB) for automated precedent mapping
- Issue identification, per-issue precedent search, counter-argument detection
- Structured research memo generation with citations

### Audio Digests
- AI-generated case summaries converted to speech via Sarvam AI (22 Indian languages)
- Google Cloud TTS fallback
- In-browser audio player with playback speed control (0.5x--2x)

### Security and Compliance
- JWT auth with refresh token rotation
- Role-based access control (admin, researcher, viewer)
- DPDP Act compliance: consent flow, right to erasure, data retention policies
- Input sanitization, audit logging, rate limiting, field-level encryption

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | Next.js 16 (App Router), TypeScript, Tailwind CSS, shadcn/ui |
| **Backend** | FastAPI, Python 3.12, fully async |
| **Primary DB** | PostgreSQL 16 on Supabase (metadata, FTS via tsvector) |
| **Vector DB** | Pinecone (1536-dim, Gemini embeddings) |
| **Graph DB** | Neo4j AuraDB (citation graph) |
| **LLM (reasoning)** | Gemini 2.5 Pro |
| **LLM (fast)** | Gemini 2.5 Flash (ingestion, classification) |
| **Embeddings** | Gemini gemini-embedding-001 (1536-dim, Matryoshka) |
| **Reranker** | Cohere rerank-v4.0-pro |
| **Agent Framework** | LangGraph (StateGraph, HITL checkpoints) |
| **TTS** | Sarvam AI / Google Cloud TTS fallback |
| **Cache** | Redis (Upstash in production) |
| **Background Jobs** | Celery + Redis |
| **Storage** | Google Cloud Storage (prod), local filesystem (dev) |
| **Deploy** | Google Cloud Run |

---

## Architecture

```
Client (Next.js 16)
    |
    v  HTTPS
Google Cloud Load Balancer
    |
    +-- /*        --> Cloud Run (Next.js Frontend)
    +-- /api/v1/* --> Cloud Run (FastAPI Backend)
                        |
                        +-- PostgreSQL 16 / Supabase (metadata + FTS)
                        +-- Pinecone (vector search, 1536-dim)
                        +-- Neo4j AuraDB (citation graph)
                        +-- Redis / Upstash (cache + rate limiting)
                        +-- GCS (PDF + audio storage)
                        +-- Gemini 2.5 Pro / Flash (LLM)
                        +-- Cohere (reranking)
                        +-- Sarvam AI (TTS)
                        +-- Celery workers (async tasks)
```

### Key Design Patterns
- **Interface + Provider pattern**: All external services behind Protocol classes -- swap implementations without touching business logic
- **Modular monolith**: Single FastAPI app with clear module boundaries
- **LangGraph agents**: StateGraph with interrupt() for HITL, checkpointing via MemorySaver (AsyncPostgresSaver for prod)
- **Security-first**: JWT auth, RBAC, input sanitization, audit logging, DPDP Act compliance, rate limiting -- all from Phase 1

---

## Project Structure

```
smriti/
+-- backend/
|   +-- app/
|   |   +-- api/routes/          # REST endpoints (health, auth, cases, search, chat, graph, agents, audio, ingest)
|   |   +-- core/
|   |   |   +-- interfaces/      # Protocol classes (LLM, embedder, vector, graph, reranker, storage, etc.)
|   |   |   +-- providers/       # Concrete implementations (Gemini, Pinecone, Neo4j, Cohere, Sarvam, etc.)
|   |   |   +-- ingestion/       # PDF -> text -> metadata -> chunks -> embeddings pipeline
|   |   |   +-- search/          # Hybrid search, query understanding, RRF fusion
|   |   |   +-- legal/           # Indian law domain: citations, courts, constants, prompts
|   |   |   +-- agents/          # LangGraph agents (research, case prep, strategy, drafting)
|   |   |   +-- chat/            # RAG chat pipeline
|   |   |   +-- graph/           # Citation graph operations
|   |   |   +-- analysis/        # Document analyzer, precedent mapper
|   |   |   +-- analytics/       # Judge analytics
|   |   +-- tasks/               # Celery async tasks (document processing, audio generation)
|   |   +-- security/            # Auth, RBAC, encryption, sanitizer, rate limiter, audit, consent
|   |   +-- models/              # SQLAlchemy 2.0 ORM models
|   |   +-- db/                  # Async PostgreSQL + Redis connections
|   +-- migrations/              # Alembic migrations (001-014)
|   +-- scripts/                 # S3 bulk ingestion, Neo4j population
|   +-- tests/                   # 1443 unit + 31 integration tests
+-- frontend/
|   +-- src/app/                 # Next.js App Router pages (20+ routes)
|   +-- src/components/          # React components (search, chat, agents, audio, graph, etc.)
|   +-- src/lib/                 # API client, types, utilities
+-- docs/                        # Architecture, decisions, phase plan, prompt library
+-- docker-compose.yml           # Local dev: PostgreSQL, Redis, Neo4j
+-- Makefile                     # dev, test, lint, migrate, ingest commands
```

---

## Getting Started

### Prerequisites
- Python 3.12+
- Node.js 20+ and npm
- Docker and Docker Compose
- API keys: Google Gemini, Pinecone, Cohere, Neo4j AuraDB

### Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/Avi-Yadav/Smriti.git
   cd Smriti
   ```

2. **Start infrastructure**
   ```bash
   docker compose up -d  # PostgreSQL, Redis, Neo4j
   ```

3. **Backend setup**
   ```bash
   cd backend
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   cp .env.example .env       # Fill in your API keys
   alembic upgrade head       # Run database migrations
   uvicorn app.main:app --reload --port 8000
   ```

4. **Start Celery worker** (for document processing and audio generation)
   ```bash
   cd backend
   celery -A app.worker:celery_app worker --loglevel=info
   ```

5. **Frontend setup**
   ```bash
   cd frontend
   npm install
   npm run dev                # Start Next.js dev server at http://localhost:3000
   ```

6. **Ingest sample data**
   ```bash
   cd backend
   python scripts/ingest_s3.py --year 2024 --limit 100
   ```

### Running Tests
```bash
# Backend
cd backend
pytest tests/ -v             # 1443 unit + 31 integration tests

# Frontend
cd frontend
npm test                     # 298 tests
```

### Key URLs (Local Dev)
- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8000`
- API Docs (Swagger): `http://localhost:8000/docs`

---

## Data Source

Supreme Court judgments from the [Indian Supreme Court Judgments](https://registry.opendata.aws/indian-supreme-court-judgments/) open dataset on AWS (35,000+ judgments).

> **Attribution**: Indian Supreme Court Judgments dataset by Dattam Labs, licensed under [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/).

---

## Roadmap

- [x] **Phase 1** -- Foundation + Ingestion: Backend scaffold, security, database, ingestion pipeline
- [x] **Phase 2** -- Search + Frontend: Hybrid search (RRF), search API, Next.js frontend
- [x] **Phase 3** -- Intelligence: RAG chat with streaming, citation graph visualization
- [x] **Phase 4** -- Judge Analytics: Judge profiles, comparison, court stats
- [x] **Phase 5** -- Document Upload + Audio: Upload briefs for analysis, TTS audio digests
- [x] **Phase 6** -- Agent Framework: LangGraph infrastructure, Research Agent, Case Prep Agent
- [x] **Phase 6.5** -- Quality Excellence: Search quality, precedent classification, confidence scoring
- [x] **Phase 7** -- Strategy + Drafting Agents, Hindi foundations (partial)
- [x] **Phase 7.5** -- Audit v2: IRAC enforcement, statute mappings, Hindi glossary
- [x] **Phase 8** -- Production Hardening: DPDP compliance, enterprise readiness, ingestion overhaul
- [ ] **Phase 9** -- Scalability: Connection pooling, horizontal scaling, 50K case ingestion

See [docs/PHASE_PLAN.md](docs/PHASE_PLAN.md) for detailed deliverables per phase.

---

## Documentation

| Document | Description |
|----------|-------------|
| [CLAUDE.md](docs/CLAUDE.md) | Operating manual and coding conventions |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | System diagrams and data flow |
| [PHASE_PLAN.md](docs/PHASE_PLAN.md) | Build phases and deliverables |
| [DECISIONS.md](docs/DECISIONS.md) | Architecture Decision Records |
| [LLD.md](docs/LLD.md) | DB schemas, API specs, component tree |
| [PROMPT_LIBRARY.md](docs/PROMPT_LIBRARY.md) | All LLM prompts |
| [LEGAL_DOMAIN.md](docs/LEGAL_DOMAIN.md) | Indian court system and citation formats |

---

## License

This project is proprietary software. All rights reserved.

The underlying Supreme Court judgment data is licensed under [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/) by Dattam Labs.
