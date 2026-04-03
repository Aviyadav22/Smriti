# Vansh's Onboarding Roadmap

Welcome to Smriti! This document is your guided path from "just cloned the repo" to "ready to contribute code." It's organized as a 3-week plan with specific reading, exploration, and contribution targets.

---

## Suggested Reading Order

Read the onboarding docs in this order:

1. **[00_QUICK_START.md](00_QUICK_START.md)** — Get the app running locally
2. **[07_GLOSSARY.md](07_GLOSSARY.md)** — Learn the terminology (legal + technical)
3. **[01_ARCHITECTURE_OVERVIEW.md](01_ARCHITECTURE_OVERVIEW.md)** — Understand the big picture
4. **[05_DATA_FLOWS.md](05_DATA_FLOWS.md)** — See how data moves through the system
5. **[02_BACKEND_REFERENCE.md](02_BACKEND_REFERENCE.md)** — Deep dive into the API
6. **[03_RAG_PIPELINE_REFERENCE.md](03_RAG_PIPELINE_REFERENCE.md)** — Understand the AI core
7. **[04_FRONTEND_REFERENCE.md](04_FRONTEND_REFERENCE.md)** — Learn the UI structure
8. **[06_DEVELOPMENT_GUIDE.md](06_DEVELOPMENT_GUIDE.md)** — How to actually write code
9. **[08_KNOWN_ISSUES_AND_TODOS.md](08_KNOWN_ISSUES_AND_TODOS.md)** — What needs fixing

---

## Week 1: Understand the Foundation

### Day 1-2: Setup & Exploration
- [ ] Follow `00_QUICK_START.md` — get everything running locally
- [ ] Create a test account, run a search query, try the chat
- [ ] Explore the Neo4j browser at `http://localhost:7474` — run `MATCH (n:Case) RETURN n LIMIT 25`
- [ ] Read `07_GLOSSARY.md` — bookmark this, you'll reference it often
- [ ] Read `01_ARCHITECTURE_OVERVIEW.md` — understand the system diagram

### Day 3-4: Backend Architecture
- [ ] Read `backend/app/main.py` — understand startup, middleware, router registration
- [ ] Read `backend/app/core/dependencies.py` — understand the Interface+Provider pattern
- [ ] Read `backend/app/core/config.py` — understand all settings
- [ ] Browse the API at `http://localhost:8000/docs` (Swagger UI)
- [ ] Try calling endpoints manually (search, case detail, health)

### Day 5: Frontend Architecture
- [ ] Read `frontend/src/app/layout.tsx` and `providers.tsx`
- [ ] Read `frontend/src/lib/api.ts` — understand how the frontend talks to the backend
- [ ] Read `frontend/src/lib/auth-context.tsx` — understand auth flow
- [ ] Navigate every page in the app and understand what each does

### By end of Week 1, you should be able to answer:
- What databases does Smriti use and what does each store?
- How does a search query flow from the frontend to results?
- What's the difference between the 4 agent types?
- How does authentication work?

---

## Week 2: Understand the AI Core

### Day 6-7: RAG Pipeline
- [ ] Read `03_RAG_PIPELINE_REFERENCE.md`
- [ ] Read `backend/app/core/ingestion/pipeline.py` — trace the full ingestion flow
- [ ] Read `backend/app/core/search/hybrid.py` — understand hybrid search + RRF
- [ ] Read `backend/app/core/chat/rag.py` — understand RAG chat
- [ ] Read `backend/app/core/legal/extractor.py` — see how citations/statutes are extracted

### Day 8-9: Agent Architecture
- [ ] Read `backend/app/core/agents/research.py` — understand the LangGraph graph
- [ ] Read `backend/app/core/agents/state.py` — understand the state schema
- [ ] Read a few worker nodes in `backend/app/core/agents/nodes/worker_nodes.py`
- [ ] Try the research agent in the UI — watch the SSE events in browser DevTools

### Day 10: Legal Domain
- [ ] Read `backend/app/core/legal/prompts.py` (skim — it's huge, focus on structure)
- [ ] Read `backend/app/core/legal/constants.py` — court names, act names
- [ ] Read `backend/app/core/legal/courts.py` — court normalization
- [ ] Understand: how does Smriti know what a "Section 302 IPC" reference means?

### By end of Week 2, you should be able to answer:
- How does a PDF become searchable vectors?
- What are the 7 vector types and why do they exist?
- How does the research agent decide what to search for?
- What makes Smriti's search different from just doing a Pinecone query?

---

## Week 3: First Contributions

### Day 11-12: Run the Test Suite
- [ ] Run all backend tests: `make test` — understand the test structure
- [ ] Run frontend tests: `cd frontend && npm test -- --run`
- [ ] Read `06_DEVELOPMENT_GUIDE.md` — understand how to add endpoints, pages, providers
- [ ] Read `08_KNOWN_ISSUES_AND_TODOS.md` — identify your first contribution

### Day 13-14: Make Your First Change
Suggested starter tasks (pick one):
- [ ] **Fix a configuration discrepancy** — `.env.example` model names don't match `config.py` defaults
- [ ] **Add a missing API test** — find an endpoint without test coverage
- [ ] **Improve a frontend error page** — make error messages more helpful
- [ ] **Add a new field to search results** — add `bench_type` badge or `case_number` display

### Day 15: Plan What's Next
- [ ] Review `docs/PHASE_PLAN.md` — understand the product roadmap
- [ ] Review `docs/DECISIONS.md` — understand architectural decisions (ADRs)
- [ ] Identify areas where you can add the most value (see below)

---

## Areas Where a Co-Founder Can Add Most Value

### 1. Data Scale (BIGGEST GAP)
Currently ~35K cases vs competitors with millions. Need to:
- Scale the ingestion pipeline (multi-account Vertex AI is set up)
- Add High Court judgments (not just Supreme Court)
- Improve ingestion speed and reliability

### 2. Hindi Language Support
`next-intl` is configured but Hindi translations are incomplete. Need:
- Complete Hindi translation files
- Hindi search query handling
- Hindi response generation from LLM

### 3. Production Operations
- Set up proper CI/CD with Docker build + push to Cloud Run
- Add monitoring/alerting beyond Sentry
- Implement database backup strategy
- Performance optimization (caching, query tuning)

### 4. Frontend Polish
- Responsive design improvements
- Accessibility (a11y) audit
- Loading state improvements
- Better onboarding flow for new users

### 5. New Features (from roadmap)
- Multi-language TTS (infrastructure exists via Sarvam AI)
- Enhanced judge analytics
- Case prediction models
- Mobile app / PWA

---

## Questions to Ask Avi

These are things that couldn't be determined from the code alone:

1. **Deployment**: What's the current deployment process? Is it manual `docker push` or automated?
2. **Production state**: Is smriti.legal live? What's the current user base?
3. **Data pipeline**: How often is new data ingested? Is it automated?
4. **API keys**: Which service tiers are we on? (Gemini, Pinecone, Cohere, Neo4j)
5. **Cost**: What's the current monthly infrastructure cost?
6. **Priorities**: What should I focus on first — data scale, features, or operations?
7. **Competitive intel**: What have you learned from Jhana AI, BharatLaw AI, CaseMine users?
8. **Legal compliance**: Are there any pending legal/compliance requirements beyond DPDP?
9. **The `ingestion/accounts/env_template` file has real credentials** — have those been rotated?
10. **Business model**: What's the current thinking on pricing/monetization?

---

## Key Files to Bookmark

| File | Why |
|------|-----|
| `backend/app/main.py` | Application entry point, middleware, routes |
| `backend/app/core/config.py` | All configuration settings |
| `backend/app/core/dependencies.py` | Service provider factories |
| `backend/app/core/search/hybrid.py` | Core search pipeline |
| `backend/app/core/agents/research.py` | Research agent graph |
| `backend/app/core/legal/prompts.py` | All LLM prompts |
| `backend/app/core/ingestion/pipeline.py` | Ingestion pipeline |
| `frontend/src/lib/api.ts` | Frontend API client |
| `frontend/src/lib/auth-context.tsx` | Auth state management |
| `docs/DECISIONS.md` | Architecture decisions (never violate these) |
| `docs/CLAUDE.md` | Operating manual (coding rules) |
| `docs/PHASE_PLAN.md` | Product roadmap |

---

Good luck, Vansh. This codebase is well-structured and thoroughly tested. The architecture is solid — your biggest impact will be on data scale and bringing this to market.
