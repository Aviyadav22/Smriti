# Chapter 1: Laying the Foundation

---

Every building needs a foundation. Before Smriti could understand a single judgment, Avi had to make a hundred decisions about *how* to build it.

But these weren't blind decisions. Avi had nearly two years of experience — first with a basic RAG model coded from scratch (April 2024), then building on an open-source framework (October 2024 onwards). He knew exactly where both approaches broke — generic chunking, no citation awareness, no Indian law specificity, architectural limitations that made every new feature a fight. The March 2026 rewrite was informed by every mistake and limitation from both eras.

This chapter is about those decisions — and the reasoning behind each one.

---

## Choosing the Weapons

### The Backend: FastAPI (Python)

Why Python? Simple — the entire AI/ML ecosystem lives in Python. Every embedding model, every LLM SDK, every NLP library speaks Python first. And FastAPI is the fastest way to build async APIs in Python.

**Why not Express.js or Django?**
- Express would mean juggling two languages (Python for AI, JavaScript for APIs). Too much friction.
- Django is great, but FastAPI's native async support is critical when you're making dozens of LLM calls per request.

> **ADR-002**: FastAPI chosen for async LLM workloads and Python AI/ML ecosystem.

### The Frontend: Next.js (TypeScript)

The law students who'd use Smriti expect a modern, fast interface. Next.js with its App Router gives server-side rendering (great for SEO — important when lawyers Google for legal tools), built-in routing, and React Server Components.

> **ADR-003**: Next.js 16 chosen for SSR, SEO, and built-in App Router.

### The Databases: Three of Them

This might seem like overkill. Why three databases? Because each one does something the others can't:

**PostgreSQL** — The workhorse. Stores case metadata (title, court, year, judge, citations). Also does full-text search with `tsvector` — think of it as a really smart index that understands word stems and phrases.

> **ADR-004**: PostgreSQL for best-in-class FTS (tsvector, ts_rank_cd) and relational integrity.

**Pinecone** — The memory. Stores vector embeddings — mathematical representations of what text *means*. When you search "bail conditions for economic offenses," Pinecone finds judgments about that concept even if they never use those exact words.

> **ADR-005**: Pinecone for managed vector search with metadata filtering.

**Neo4j** — The web. Stores the citation graph — which case cites which. This is something no other Indian legal AI does. When you find a relevant case, Neo4j can tell you every case that cited it, distinguished it, or overruled it.

> **ADR-006**: Neo4j AuraDB for native graph queries and citation traversal.

### The AI Brain: Google Gemini

For the LLM (the "thinking" part), Avi chose Google Gemini. Not GPT-4. Not Claude. Why?

- **$300 in free credits** — crucial for a student project
- **1 million token context window** — can read an entire judgment at once
- **Structured JSON output** — when you ask it to extract metadata, it returns clean JSON, not prose
- **Two speed modes**: Gemini Pro (smart, for reasoning) and Gemini Flash (fast and cheap, for bulk tasks)

> **ADR-007**: Gemini chosen for free credits, 1M context, and structured output.

---

## The Architecture: One App, Clear Boundaries

Avi could have built microservices — separate apps for search, for ingestion, for agents. But that would mean Kubernetes, service meshes, distributed tracing... overkill for a team of one.

Instead: a **modular monolith**. One FastAPI application with clear internal boundaries. Every module talks through defined interfaces, so any piece could be extracted into its own service later if needed.

> **ADR-010**: Modular monolith over microservices for simple deployment.

### The Interface Pattern

This is the most important architectural decision in Smriti, and it's beautifully simple.

Every external service — Gemini, Pinecone, Neo4j, Cohere, Sarvam AI — is hidden behind a **Protocol** (Python's version of an interface). The rest of the code never talks to Gemini directly. It talks to an `LLMProvider`. The fact that `LLMProvider` happens to be Gemini today is an implementation detail.

```
Your Code → Protocol (contract) → Provider (implementation)
                                      ↓
                                  Could be Gemini today
                                  Could be Claude tomorrow
                                  Could be a mock for testing
```

Why? Because if Google doubles Gemini's prices tomorrow, or if a better model comes along, Avi can swap the provider without touching a single line of business logic.

> **ADR-011**: Protocol pattern for all external interfaces with FastAPI dependency injection.

---

## The Skeleton (March 3-4, 2026)

With decisions made, the first commits landed:

```
March 3: acc5317 — Project scaffold
         ├── backend/
         │   ├── app/
         │   │   ├── api/routes/          → API endpoints
         │   │   ├── core/
         │   │   │   ├── interfaces/      → 7 Protocol classes
         │   │   │   ├── providers/       → Implementations
         │   │   │   ├── ingestion/       → PDF → vectors pipeline
         │   │   │   ├── legal/           → Indian law-specific logic
         │   │   │   ├── search/          → Hybrid search engine
         │   │   │   └── agents/          → Research agent (later)
         │   │   └── models/              → Database models
         │   ├── migrations/              → Alembic (DB evolution)
         │   └── tests/                   → 2,185 tests (eventually)
         └── frontend/
             └── src/
                 ├── app/                 → 32 pages
                 ├── components/          → 47 components
                 └── lib/                 → API client, types, auth
```

March 4 brought the database layer — SQLAlchemy models, Alembic migrations, and the first API endpoints (health check, auth, case CRUD).

The foundation was laid. Now it was time to teach Smriti to read.

---

> **Next: [Chapter 2 — Teaching Smriti to Read →](./02-teaching-smriti-to-read.md)**
>
> *Where PDFs get cracked open, OCR saves the day, and text gets cleaned of invisible garbage characters.*

---

### In the Code

| What | Where |
|------|-------|
| Interface protocols | [backend/app/core/interfaces/](../../backend/app/core/interfaces/) |
| Gemini LLM provider | [backend/app/core/providers/llm/gemini.py](../../backend/app/core/providers/llm/gemini.py) |
| Gemini embedder | [backend/app/core/providers/embeddings/gemini.py](../../backend/app/core/providers/embeddings/gemini.py) |
| Pinecone provider | [backend/app/core/providers/vector/pinecone_store.py](../../backend/app/core/providers/vector/pinecone_store.py) |
| Neo4j provider | [backend/app/core/providers/graph/neo4j_store.py](../../backend/app/core/providers/graph/neo4j_store.py) |
| Dependency injection | [backend/app/core/dependencies.py](../../backend/app/core/dependencies.py) |
| Database models | [backend/app/models/](../../backend/app/models/) |
| All ADRs | [docs/DECISIONS.md](../DECISIONS.md) |
| Architecture overview | [docs/ARCHITECTURE.md](../ARCHITECTURE.md) |
