# Smriti

**AI-powered Indian legal research platform — Harvey AI for Indian law.**

Smriti combines hybrid semantic + keyword search, citation graph analysis, and RAG-powered chat to help legal professionals navigate India's vast body of Supreme Court jurisprudence. Every answer is grounded in real judgments, not hallucinated.

---

## Features

### Hybrid Search
- **Semantic search** powered by Gemini embeddings (1536-dim) via Pinecone
- **Full-text search** with PostgreSQL tsvector and legal term boosting
- **Reciprocal Rank Fusion (RRF, k=60)** merges results from multiple retrieval strategies
- **Cohere reranking** (rerank-v4.0-pro) for precision at the top of results
- Faceted filtering: court, year range, case type, bench type, judge, act

### Intelligent Ingestion
- PDF text extraction with OCR fallback (pdfplumber + Tesseract)
- LLM-based metadata extraction (Gemini structured output) with regex validation
- Legal-aware chunking: 2000-char chunks, 200-char overlap, section-tagged (Facts, Arguments, Analysis, Ratio Decidendi, Order)
- Indian citation regex (5 formats), acts/sections parser, court name normalization

### Citation Graph (Planned)
- Neo4j-backed citation network: CITES, OVERRULES, AFFIRMS, DISTINGUISHES
- Interactive force-directed graph visualization
- Authority scoring and citation chain analysis

### RAG Chat (Planned)
- Streaming chat with inline citation grounding
- Every claim linked to source judgment chunks
- Chat history encrypted per-user

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | Next.js 15 (App Router), TypeScript, Tailwind CSS, shadcn/ui |
| **Backend** | FastAPI, Python 3.12, async throughout |
| **Primary DB** | PostgreSQL 16 (metadata, FTS via tsvector) |
| **Vector DB** | Pinecone (1536-dim, Gemini embeddings) |
| **Graph DB** | Neo4j AuraDB (citation graph) |
| **LLM** | Google Gemini 2.5 Pro |
| **Reranker** | Cohere rerank-v4.0-pro |
| **Cache** | Redis (Upstash in production) |
| **Storage** | Google Cloud Storage (prod), local filesystem (dev) |
| **Deploy** | Google Cloud Run |

---

## Architecture

```
Client (Next.js 15)
    │
    ▼ HTTPS
Google Cloud Load Balancer
    │
    ├── /*        → Cloud Run (Next.js Frontend)
    └── /api/v1/* → Cloud Run (FastAPI Backend)
                        │
                        ├── PostgreSQL 16 (metadata + FTS)
                        ├── Pinecone (vector search)
                        ├── Neo4j AuraDB (citation graph)
                        ├── Redis/Upstash (cache + rate limiting)
                        └── GCS (PDF storage)
```

### Key Design Patterns
- **Interface + Provider pattern**: All external services behind Protocol classes — swap implementations without touching business logic
- **Modular monolith**: Single FastAPI app with clear module boundaries
- **Security-first**: JWT auth, RBAC, input sanitization, audit logging, DPDP Act compliance, rate limiting — all from Phase 1

---

## Project Structure

```
smriti/
├── backend/
│   ├── app/
│   │   ├── api/routes/          # FastAPI endpoints (health, auth, cases, search, ingest)
│   │   ├── core/
│   │   │   ├── interfaces/      # Protocol classes (LLM, embedder, vector, graph, etc.)
│   │   │   ├── providers/       # Concrete implementations (Gemini, Pinecone, Neo4j, etc.)
│   │   │   ├── ingestion/       # PDF → text → metadata → chunks → embeddings pipeline
│   │   │   ├── search/          # Hybrid search, query understanding, RRF fusion
│   │   │   ├── legal/           # Indian law domain: citations, courts, constants
│   │   │   └── security/        # Auth, RBAC, sanitizer, rate limiter, audit, encryption
│   │   ├── db/                  # SQLAlchemy models, migrations, connection management
│   │   └── config.py            # Dependency injection + settings
│   ├── tests/                   # 150+ unit tests
│   └── scripts/                 # S3 bulk ingestion, utilities
├── frontend/
│   ├── src/app/                 # Next.js App Router pages
│   ├── src/components/          # React components (search, case viewer, auth)
│   └── src/lib/                 # API client, types, utilities
├── docs/                        # Architecture, decisions, phase plan, prompt library
├── docker-compose.yml           # Local dev: PostgreSQL, Redis, Neo4j
└── Makefile                     # dev, test, lint, migrate, ingest commands
```

---

## Getting Started

### Prerequisites
- Python 3.12+
- Node.js 20+ and pnpm
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
   make migrate               # Run database migrations
   make dev                   # Start FastAPI server
   ```

4. **Frontend setup**
   ```bash
   cd frontend
   pnpm install
   pnpm dev                   # Start Next.js dev server
   ```

5. **Ingest sample data**
   ```bash
   cd backend
   python scripts/ingest_s3.py --year 2024 --limit 100
   ```

### Running Tests
```bash
cd backend
make test          # Run all tests
make lint          # ruff + mypy
```

---

## Data Source

Supreme Court judgments from the [Indian Supreme Court Judgments](https://registry.opendata.aws/indian-supreme-court-judgments/) open dataset on AWS.

> **Attribution**: Indian Supreme Court Judgments dataset by Dattam Labs, licensed under [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/).

---

## Roadmap

- [x] **Phase 1** — Foundation + Ingestion: Backend scaffold, security, database, ingestion pipeline, 150+ tests
- [x] **Phase 2** — Search + Frontend: Hybrid search pipeline (RRF), search API, Next.js frontend with legal aesthetic
- [ ] **Phase 3** — Intelligence: RAG chat with streaming, citation graph visualization, section viewer
- [ ] **Phase 4** — Production: GCP deployment, performance optimization, DPDP compliance, monitoring

---

## License

This project is proprietary software. All rights reserved.

The underlying Supreme Court judgment data is licensed under [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/) by Dattam Labs.
