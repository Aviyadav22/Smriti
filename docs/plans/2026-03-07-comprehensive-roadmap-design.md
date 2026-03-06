# Smriti — Comprehensive Product Roadmap Design

**Date:** 2026-03-07
**Status:** Approved
**Scope:** Full product roadmap from current state to production + post-launch

---

## 1. Vision & Positioning

Smriti is **India's AI-powered legal intelligence platform** — the Harvey AI for Indian law.

**Three pillars:**

1. **Search & Discovery** — Hybrid search (RRF), citation graph visualization, section-aware case viewer
2. **Intelligence & Agents** — AI agents that do legal work: research memos, case prep, strategy analysis, document drafting, outcome prediction
3. **Accessibility** — Hindi/multilingual, audio digests, mobile-first — law accessible to 1.4B people

**Target users (priority order):**

1. Litigation lawyers (daily research, case prep)
2. Law students & junior associates (learning, exam prep)
3. In-house legal teams (compliance, contract review)
4. Judges & registrars (research assistance)
5. Pro-se litigants / citizens (accessibility)

---

## 2. Competitive Landscape

| Competitor | Data Scale | Differentiator | Our Advantage |
|---|---|---|---|
| SCC Online | 35+ yrs | Gold standard citations | AI-native, free tier, agents |
| Manupatra | Comprehensive | Neutral citations | Modern UX, graph viz, agents |
| Jhana AI (16M docs) | 16M+ judgments | AI paralegal, $1.6M funded | Citation graph, section-aware, agents |
| BharatLaw AI | 1M+ judgments | Zero-prompt search, Hindi | Graph viz, agents, deeper AI |
| CaseMine | Multi-jurisdiction | CaseIQ, visual precedent mapping | Open data, agents, strategy |
| LegitQuest | All courts | Judge Analytics, iSearch | Full agent suite, audio, Hindi |
| Harvey AI ($8B) | US/UK focus | Multi-model agents, workflows | India-specific, affordable |

**Our moat:**
- Citation graph + Neo4j (only CaseMine has similar, ours is interactive force-directed)
- Section-aware legal chunking (FACTS/ARGUMENTS/ANALYSIS/RATIO/ORDER)
- Agent framework (no Indian competitor has multi-step autonomous agents)
- DPDP compliance built-in from day 1
- Open data foundation (CC-BY-4.0, transparent, auditable)

---

## 3. Agent Architecture

### Design Principles (modeled after Harvey + LexisNexis Protege)

- **Orchestrator Agent** — Routes intent to specialized agents, manages multi-step workflows
- **Specialized Agents** — Each has a focused domain, uses shared infrastructure
- **Human-in-the-loop** — Checkpoints at critical decisions, lawyers verify before final output
- **Multi-model routing** — Gemini Pro for reasoning, Flash for extraction/classification
- **LangGraph** — Graph-based state machines for workflow orchestration

### Agent Roster

| Agent | Purpose | Inputs | Outputs |
|---|---|---|---|
| **Research Agent** | Multi-step legal research | Natural language question | Structured research memo with citations |
| **Case Prep Agent** | Brief/petition analysis | Uploaded document (PDF) | Issue map + precedents per issue + counter-arguments |
| **Strategy Agent** | Litigation strategy | Case facts + judge info | Argument prediction, weak points, strategy suggestions |
| **Drafting Agent** | Document generation | Document type + facts + context | Legal document (petition, application, notice) |
| **Document Review Agent** | Contract/agreement analysis | Uploaded document | Clause analysis, risk flags, compliance check |
| **Compliance Agent** | Regulatory monitoring | Domain/industry | Regulatory changes, compliance gaps |

### Technical Foundation

- LangGraph for orchestration (graph-based state machines)
- Agent state persisted in PostgreSQL (encrypted)
- Agent execution tracking (steps, tool calls, intermediate results)
- Agent Protocol interfaces (extends existing provider pattern)
- Shared infrastructure: hybrid search, Neo4j graph, RAG pipeline, Judge Analytics data

---

## 4. Tech Stack (Updated)

| Component | Choice | Rationale |
|---|---|---|
| Backend | FastAPI (Python 3.12) | Async, AI/ML ecosystem |
| Frontend | Next.js 15 + Tailwind + shadcn/ui | SSR for SEO, modern DX |
| Primary DB | PostgreSQL 16 + tsvector FTS | Metadata, FTS, agent state |
| Vector DB | Pinecone (upgrade to Starter at 100K) | Managed, low-latency |
| Graph DB | Neo4j AuraDB | Citation network, legal knowledge graph |
| LLM (reasoning) | Gemini 2.5 Pro | 1M context, structured output |
| LLM (fast/cheap) | Gemini 2.5 Flash | Metadata extraction, classification |
| Embeddings | Gemini gemini-embedding-001 (1536-dim) | Integrated with LLM provider |
| Reranker | Cohere rerank-v4.0-pro | Best-in-class, free tier |
| Agent Framework | LangGraph | Graph-based, proven for legal (Definely) |
| TTS | Sarvam AI / Google Cloud TTS | 22 Indian languages, legal domain |
| Translation | Gemini / Sarvam Translate | Hindi search + summaries |
| Cache | Redis (Upstash prod) | Search, metadata, agent results |
| Storage | GCS (prod) / Local (dev) | PDFs, audio files |
| Deploy | Google Cloud Run | Auto-scaling, pay-per-use |
| i18n | next-intl | Hindi UI localization |

---

## 5. Phase Plan

### Phase 1: Foundation + Ingestion — COMPLETE

- Backend scaffold, security, DB, interfaces/providers, ingestion pipeline
- 153 unit tests, all security middleware active
- All 7 Protocol interfaces defined and implemented

### Phase 2: Search + Frontend — COMPLETE

- Hybrid search pipeline (RRF k=60), 3 search + 5 cases API endpoints
- Next.js frontend: landing, search, case detail, auth pages
- 25 unit tests for search pipeline

### Phase 3: Intelligence + Graph — COMPLETE

- RAG chat with SSE streaming and inline citations
- Citation graph API (neighborhood, chain, authorities, stats)
- Graph visualization (react-force-graph-2d, force-directed)
- Chat message encryption (AES-256-GCM)
- 33 unit tests (RAG + graph traversal)
- 11 frontend tests (chat + graph pages)

---

### Phase 4: Data + Judge Analytics

**Goal:** Fill the database. Ship Judge Analytics as the first "intelligence" feature.

**Why first:** Every feature depends on data. Judge Analytics is low-effort/high-impact — LegitQuest charges premium, no free tool has it.

#### 4.1 Full SC Ingestion
- [ ] Ingest all 35K SC judgments from S3 (max out dataset)
- [ ] Use Gemini Flash for metadata extraction (conserve Pro credits)
- [ ] Citation graph integrity verification (Neo4j edges match extracted citations)
- [ ] Metadata quality audit: sample 100 cases, verify accuracy
- [ ] Upgrade Pinecone to Starter when free tier exhausts
- [ ] Progress dashboard: ingestion stats, error rates, quality scores

#### 4.2 Judge Analytics API
- [ ] `GET /judges` — List all judges with case counts
- [ ] `GET /judges/{name}` — Judge profile:
  - Cases authored (count by year)
  - Disposal patterns (dismissed/allowed/remanded percentages)
  - Most frequent bench combinations
  - Average case duration (filing → decision)
  - Most-cited judgments authored
  - Acts/sections most frequently dealt with
  - Landmark judgments authored
- [ ] `GET /judges/{name}/cases` — Paginated case list with filters
- [ ] `GET /judges/compare` — Compare 2-3 judges side by side
- [ ] `GET /courts/{court}/stats` — Court-level statistics
- [ ] Redis caching (judge stats: 1-hour TTL)

#### 4.3 Judge Analytics UI
- [ ] Judge directory page (`/judges`) — searchable list with key stats
- [ ] Judge profile page (`/judge/[name]`) — stats dashboard:
  - Disposal pattern pie chart
  - Cases per year bar chart
  - Bench combination heatmap
  - Top cited judgments list
  - Acts/sections word cloud or bar chart
- [ ] Judge comparison page (`/judges/compare`) — side-by-side stats
- [ ] Link judges from case detail page (clickable judge names)
- [ ] Court statistics page (`/courts`) — aggregate stats

#### 4.4 Tests (Phase 4)
- [ ] Unit tests: judge analytics SQL queries (mock DB)
- [ ] Unit tests: ingestion quality metrics
- [ ] Frontend: judge profile page tests, comparison tests
- [ ] Data validation: 10 sample judges with manually verified stats

#### Exit Criteria
- [ ] 35,000 SC judgments in PostgreSQL + Pinecone + Neo4j
- [ ] Judge Analytics working for all SC judges in dataset
- [ ] Search works with real data (10 test queries verified)
- [ ] Citation graph renders for any ingested case

---

### Phase 5: Document Upload + Audio Digests

**Goal:** Two killer features competitors charge for. Upload briefs for precedent mapping, listen to summaries.

#### 5.1 Document Upload Pipeline
- [ ] Upload endpoint: `POST /documents/upload` (PDF, max 50MB)
- [ ] File validation (type, size, virus scan optional)
- [ ] Store to GCS/local storage
- [ ] Background processing pipeline:
  1. Text extraction (pdfplumber + OCR fallback)
  2. Issue identification (Gemini Pro: extract legal issues from document)
  3. Per-issue precedent search (hybrid search, parallel)
  4. Counter-argument identification
  5. Research memo generation (structured, with citations)
- [ ] Processing status tracking: pending → extracting → analyzing → searching → generating → complete → failed
- [ ] Documents private per-user (row-level security via user_id)
- [ ] `GET /documents` — List user's uploaded documents
- [ ] `GET /documents/{id}` — Document detail + analysis results
- [ ] `DELETE /documents/{id}` — Delete document + all analysis

#### 5.2 Document Upload UI
- [ ] Upload page (`/upload`) — drag-and-drop PDF upload
- [ ] Processing status with step-by-step progress
- [ ] Analysis results page:
  - Extracted issues listed
  - Per-issue: supporting precedents, opposing precedents, key statutes
  - Downloadable research memo (PDF export)
- [ ] Document history in user dashboard

#### 5.3 Audio Digests
- [ ] Audio generation pipeline:
  1. Case summary generation (Gemini Pro: concise 2-3 min summary)
  2. TTS conversion via Sarvam AI API (Hindi + English)
  3. Audio file storage (GCS/local, MP3 format)
  4. Cache generated audio (don't regenerate)
- [ ] `GET /cases/{id}/audio` — Stream or download audio digest
- [ ] `GET /cases/{id}/audio/status` — Check if audio exists or needs generation
- [ ] `POST /cases/{id}/audio/generate` — Trigger audio generation (async)
- [ ] Audio player component on case detail page (`/case/[id]`)
  - Play/pause, progress bar, playback speed (0.5x-2x)
  - Download button
  - Language selector (English / Hindi)
- [ ] Batch audio generation for popular/landmark cases

#### 5.4 Tests (Phase 5)
- [ ] Unit tests: document processing pipeline (mock Gemini, verify issue extraction)
- [ ] Unit tests: audio generation pipeline (mock TTS API)
- [ ] Frontend: upload page tests, audio player tests
- [ ] Integration test: upload PDF → receive analysis results

#### Exit Criteria
- [ ] Document upload produces accurate issue mapping for sample legal briefs
- [ ] Audio digests play correctly in English and Hindi
- [ ] Processing status updates in real-time
- [ ] Documents are private per-user

---

### Phase 6: Agent Framework + Research & Case Prep Agents

**Goal:** Build the agent infrastructure and ship the first two agents. Transition from "search tool" to "AI legal assistant."

#### 6.1 Agent Infrastructure
- [ ] `core/agents/base.py` — Base agent Protocol:
  - `plan(input) -> list[Step]` — Break task into steps
  - `execute(step) -> StepResult` — Execute a single step
  - `adapt(results) -> list[Step]` — Revise plan based on results
  - `interact(checkpoint) -> UserInput` — Request human input
- [ ] `core/agents/orchestrator.py` — Orchestrator agent:
  - Intent classification (which agent to route to)
  - Multi-agent coordination (parallel sub-tasks)
  - Result aggregation and formatting
- [ ] `core/agents/state.py` — Agent state management:
  - PostgreSQL-backed state persistence
  - Step tracking (planned → running → completed → failed)
  - Intermediate results storage (encrypted)
  - Execution history and audit trail
- [ ] LangGraph integration:
  - Graph-based workflow definitions
  - Conditional routing (branching based on step results)
  - Parallel node execution
  - Human-in-the-loop breakpoints
- [ ] Multi-model routing:
  - Gemini Pro for reasoning, analysis, synthesis
  - Gemini Flash for classification, extraction, summarization
  - Router logic based on task type and complexity
- [ ] Agent execution API:
  - `POST /agents/{agent_type}/run` — Start agent execution (SSE streaming)
  - `GET /agents/executions/{id}` — Get execution status and results
  - `GET /agents/executions` — List user's agent executions
  - `POST /agents/executions/{id}/input` — Provide human input at checkpoint
  - `DELETE /agents/executions/{id}` — Cancel running execution

#### 6.2 Research Agent
- [ ] `core/agents/research.py` — Research Agent implementation:
  - **Plan**: Decompose complex legal question into 3-7 sub-queries
  - **Search**: Run parallel hybrid searches per sub-query
  - **Cross-reference**: Identify cases appearing across multiple sub-queries (high relevance signal)
  - **Contradiction detection**: Flag cases with conflicting holdings
  - **Synthesize**: Produce structured research memo:
    - Executive summary
    - Key findings per sub-query
    - Supporting precedents (with relevance scores)
    - Opposing/distinguishing precedents
    - Statutory provisions cited
    - Recommended further research areas
  - **Follow-up**: Handle follow-up questions within same research session
- [ ] Citation verification: every cited case exists in DB
- [ ] Confidence scoring per finding (based on source quality, recency, authority)

#### 6.3 Case Prep Agent
- [ ] `core/agents/case_prep.py` — Case Prep Agent implementation:
  - **Input**: Uploaded brief, petition, or case facts (PDF or text)
  - **Extract**: Identify legal issues, parties, relief sought, key facts
  - **Research**: Per issue — find supporting precedents, opposing precedents, key statutes
  - **Counter-arguments**: Identify likely opposing arguments and responses
  - **Memo**: Generate structured research memo:
    - Case overview
    - Issues identified
    - Per-issue analysis with precedent mapping
    - Counter-argument matrix
    - Recommended strategy points
  - **Export**: Downloadable PDF/Word research memo

#### 6.4 Agent UI
- [ ] Agent hub page (`/agents`) — agent selector with descriptions
- [ ] Agent workspace page (`/agents/[type]`):
  - Input panel (text input or file upload depending on agent)
  - Step-by-step execution visualization (plan → search → analyze → synthesize)
  - Real-time streaming of intermediate results
  - Human-in-the-loop input prompts
  - Final result display with citations
- [ ] Agent execution history in user dashboard
- [ ] Share agent results (generate shareable link)

#### 6.5 Tests (Phase 6)
- [ ] Unit tests: orchestrator routing logic
- [ ] Unit tests: research agent planning (verify decomposition quality)
- [ ] Unit tests: case prep agent issue extraction (sample documents)
- [ ] Unit tests: agent state management (persistence, recovery)
- [ ] Frontend: agent hub tests, workspace tests
- [ ] Integration test: research agent end-to-end with mock LLM

#### Exit Criteria
- [ ] Research Agent produces coherent memos for 10 test legal questions
- [ ] Case Prep Agent correctly identifies issues from 5 sample briefs
- [ ] Agent execution streams progress in real-time
- [ ] Human-in-the-loop checkpoints work correctly
- [ ] Agent state persists and can be resumed

---

### Phase 7: Strategy Agent + Drafting Agent + Hindi

**Goal:** Advanced agents for litigation strategy. Hindi support to unlock mass market.

#### 7.1 Strategy Agent
- [ ] `core/agents/strategy.py` — Strategy Agent implementation:
  - **Input**: Case facts + target judge/bench (optional) + desired relief
  - **Judge Analysis**: Pull Judge Analytics data — disposal patterns, tendencies
  - **Precedent Analysis**: Find cases with similar fact patterns, track outcomes
  - **Argument Prediction**: Likely arguments from opposing side (based on similar cases)
  - **Weak Point Detection**: Identify vulnerable aspects of user's position
  - **Strategy Output**:
    - Case strength assessment (strong/moderate/weak with reasoning)
    - Recommended legal arguments (ordered by predicted effectiveness)
    - Key precedents to cite (with relevance explanation)
    - Anticipated counter-arguments and rebuttals
    - Judge-specific considerations (if judge data available)
    - Procedural strategy suggestions (timing, forum selection)

#### 7.2 Drafting Agent
- [ ] `core/agents/drafting.py` — Drafting Agent implementation:
  - **Input**: Document type + case facts + relevant precedents (auto-suggested or user-selected)
  - **Document types** (Phase 7 scope):
    - Bail applications (Section 439 CrPC)
    - Writ petitions (Article 226/32)
    - Written statements
    - Legal notices
    - Appeals (civil/criminal)
    - Applications (interim relief, stay, adjournment)
  - **Generation**: Grounded in precedents and statutory provisions
  - **Citation verification**: Every cited case/statute verified against DB
  - **Template system**: Customizable per document type
  - **Export**: Word (.docx) and PDF formats
  - **Revision**: Accept feedback, regenerate specific sections

#### 7.3 Hindi Support
- [ ] `next-intl` setup for frontend i18n
- [ ] Hindi translations for all UI strings
- [ ] Language toggle in header (EN / HI)
- [ ] Hindi search pipeline:
  - Detect Hindi query input
  - Translate to English via Gemini / Sarvam Translate API
  - Execute hybrid search
  - Translate result snippets back to Hindi
  - Display bilingual results (Hindi snippet + English original available)
- [ ] Hindi judgment summaries: Gemini-generated Hindi summaries for case detail page
- [ ] Hindi audio digests via Sarvam AI TTS (extends Phase 5 audio)
- [ ] Hindi agent responses: agents can respond in Hindi when query is in Hindi

#### 7.4 Document Review Agent (if time permits)
- [ ] `core/agents/review.py` — Document Review Agent:
  - Upload contract/agreement → clause-by-clause analysis
  - Risk flagging (high/medium/low per clause)
  - Missing clause detection (based on document type)
  - Compliance check against relevant statutes
  - Comparison with standard templates

#### 7.5 Tests (Phase 7)
- [ ] Unit tests: strategy agent (mock judge data, verify strategy output)
- [ ] Unit tests: drafting agent (verify document structure, citation integrity)
- [ ] Unit tests: Hindi translation pipeline
- [ ] Frontend: Hindi UI rendering tests, drafting workspace tests
- [ ] Integration test: strategy agent with real judge analytics data
- [ ] Translation quality test: 10 Hindi queries, verify search accuracy

#### Exit Criteria
- [ ] Strategy Agent produces actionable strategy for 5 test cases
- [ ] Drafting Agent generates valid legal documents for all 6 document types
- [ ] Hindi search returns relevant results for 10 Hindi test queries
- [ ] Hindi audio digests play correctly
- [ ] Language toggle works across all pages

---

### Phase 8: Production Hardening + Launch

**Goal:** Production-grade deployment. Everything needed for real lawyers.

#### 8.1 GCP Production Deployment
- [ ] Cloud Run (backend): auto-scaling, min 1 instance, max 10
- [ ] Cloud SQL PostgreSQL 16: SSL-only, automated backups, point-in-time recovery
- [ ] GCP Secret Manager: all API keys, DB passwords, JWT secrets
- [ ] `providers/storage/gcs.py` — GCSStorage for PDFs + audio files
- [ ] Cloud CDN for static assets
- [ ] Custom domain + SSL certificate (smriti.law or similar)
- [ ] Cloud Armor: WAF rules for common attacks
- [ ] Vercel deployment for frontend (or Cloud Run SSR)

#### 8.2 Performance Optimization
- [ ] Redis caching layer:
  - Search results: 5-min TTL
  - Case metadata: 1-hour TTL
  - Judge stats: 1-hour TTL
  - Facet counts: 15-min TTL
  - Agent results: 24-hour TTL
- [ ] Database query optimization: EXPLAIN ANALYZE on slow queries
- [ ] Connection pooling: SQLAlchemy pool tuning
- [ ] Pinecone query optimization: metadata pre-filtering
- [ ] Frontend: image optimization, code splitting, prefetching
- [ ] Audio file CDN caching (long TTL, immutable)

#### 8.3 DPDP Act Compliance
- [ ] Consent flow: explicit consent at registration with purpose listing
- [ ] Consent versioning: track which version user consented to
- [ ] Right to erasure: `DELETE /auth/me` — deletes all user data
- [ ] Data retention policy: configurable (default: 2 years inactive)
- [ ] Breach notification process documented (72-hour requirement)
- [ ] Privacy policy page on frontend
- [ ] Cookie consent banner

#### 8.4 Monitoring + Observability
- [ ] Structured JSON logging with PII redaction
- [ ] Cloud Logging integration
- [ ] Health check with all dependency statuses
- [ ] Sentry error tracking
- [ ] Uptime monitoring alerts
- [ ] Metrics dashboard:
  - Search: latency p50/p95/p99, result quality
  - API: error rate, request count
  - LLM: token usage, cost tracking
  - Agents: execution time, success rate, step counts
  - Users: DAU/WAU/MAU, feature usage
- [ ] Alert rules: >5% error rate, p95 >3s, auth spike, agent failure spike

#### 8.5 Security Audit
- [ ] OWASP Top 10 review
- [ ] JWT implementation review
- [ ] SQL injection test (parameterized queries verified)
- [ ] XSS test (CSP headers, output escaping)
- [ ] Rate limiting verified under load
- [ ] Secrets not in code or logs
- [ ] CORS restricted to known origins
- [ ] Agent prompt injection testing

#### 8.6 Landing Page + Onboarding
- [ ] Landing page redesign:
  - Hero with live demo / search preview
  - Features grid (search, graph, agents, audio, Hindi)
  - Agent showcase with before/after
  - How-it-works section (3 steps)
  - Pricing tiers (Free / Pro / Enterprise)
  - Testimonials / early user quotes
  - Attribution (CC-BY-4.0, Dattam Labs)
- [ ] Onboarding tour: first-time walkthrough
- [ ] About page with team, mission, dataset info

#### 8.7 Load Testing + QA
- [ ] Search accuracy: 30 test queries
  - Citation lookup (10): >90% recall@5
  - Topic search (10): >70% recall@5
  - Filtered search (5): correct filter application
  - Complex queries (5): multi-facet, natural language
- [ ] Agent quality: 20 test scenarios across all agents
- [ ] Load test: 50 concurrent users, <2s search, <5s agent first token
- [ ] Mobile responsiveness audit (all pages)
- [ ] Cross-browser testing (Chrome, Safari, Firefox, Edge)

#### Exit Criteria
- [ ] Production deployment stable on GCP
- [ ] Search accuracy meets targets
- [ ] Agent quality verified on test scenarios
- [ ] Security audit passed (no critical/high findings)
- [ ] DPDP compliance features active
- [ ] Monitoring + alerting operational
- [ ] <2s average search response time
- [ ] Landing page converts visitors to signups

---

### Post-Launch Roadmap

#### Phase 9: High Court Expansion
- Indian Kanoon / eCourts data integration
- 100K+ High Court judgments (start with top 5 HCs by volume)
- Regional court support (district courts via NJDG)
- State-specific statutes and rules
- Expand Judge Analytics to HC judges

#### Phase 10: Compliance Agent + Enterprise
- Compliance Agent: regulatory change monitoring, compliance gap analysis
- Multi-tenant workspaces (team collaboration)
- SSO (SAML/OIDC) for enterprise clients
- Admin panel for team management
- Usage analytics for team leads
- API rate limits per tier

#### Phase 11: Mobile + API Platform
- React Native mobile app (iOS + Android)
- Offline mode (cached cases, downloaded audio)
- Public API for third-party integrations
- Webhook system for notifications
- SDK for embedding Smriti search in other apps

#### Phase 12: Marketplace + Community
- Workflow marketplace (share custom agent workflows)
- Community-contributed document templates
- Lawyer profiles with expertise areas
- Peer review system for agent outputs
- Legal education modules (for law students)

---

## 6. Risk Register (Updated)

| Risk | Severity | Mitigation |
|---|---|---|
| Dataset too small (35K vs 16M competitors) | CRITICAL | Max out S3 dataset Phase 4, plan HC expansion Phase 9 |
| No users / zero distribution | HIGH | Ship early, target 10 law students for feedback, free tier |
| Pinecone cost at scale | MEDIUM | Upgrade to Starter ($70/mo), monitor usage |
| Gemini credit exhaustion | MEDIUM | Flash for ingestion, Pro for RAG/agents, monitor burn rate |
| Agent hallucination | HIGH | Citation verification, human-in-the-loop, confidence scores |
| LangGraph complexity | MEDIUM | Start with simple 2-3 step agents, iterate |
| Hindi translation quality | MEDIUM | Use Gemini for translation, verify with native speakers |
| Sarvam AI TTS availability | LOW | Google Cloud TTS as fallback |
| DPDP enforcement timeline | LOW | Compliance built in from Phase 1 |
| Neo4j free tier limits (200K nodes) | LOW | Sufficient for 35K SC cases, upgrade when expanding to HC |

---

## 7. What We're NOT Building

| Item | Reason | When |
|---|---|---|
| Multiple LLM providers | Gemini covers all needs, multi-model within Gemini family | Post-launch if needed |
| Browser extension | Low priority, complex | Phase 11+ |
| Automated web scraping | Legal gray area, S3 + partnerships preferred | Phase 9 (structured data sources) |
| Custom embedding model | Fine-tuning is expensive, Gemini embeddings adequate | Post-launch R&D |
| Real-time court updates | Requires scraping/APIs not available | Phase 9 (eCourts integration) |
| Billing / payments | Free for initial launch | When monetizing |
| Video tutorials | Content creation, not engineering | Marketing team |
| Arbitration/ADR module | Niche, defer | Phase 12+ |

---

## 8. Success Metrics

| Metric | Target (Launch) | Target (6 months) |
|---|---|---|
| Cases ingested | 35,000 SC | 100,000+ (SC + HC) |
| Registered users | 100 | 5,000 |
| DAU | 10 | 500 |
| Search queries/day | 50 | 2,000 |
| Agent executions/day | 10 | 500 |
| Search latency (p95) | <2s | <1.5s |
| Agent first token (p95) | <5s | <3s |
| Audio digests generated | 1,000 | 10,000 |
| Hindi search queries | 10% of total | 30% of total |

---

## Sources

- [Indian Legal Tech Market - Tracxn](https://tracxn.com/d/explore/legal-tech-startups-in-india/__E1QQRMw4NEjHwC6iLnpj5s5God9ZktQAeqwocPbdMfk)
- [Jhana AI - Analytics India](https://analyticsindiamag.com/ai-origins-evolution/jhana-ai-wants-to-disrupt-indias-legaltech-with-ai-powered-research/)
- [Harvey AI Agents](https://www.harvey.ai/blog/introducing-harvey-agents)
- [Harvey Workflow Builder](https://www.harvey.ai/blog/introducing-workflow-builder)
- [LexisNexis Protege Multi-Agent](https://natlawreview.com/article/ten-ai-predictions-2026-what-leading-analysts-say-legal-teams-should-expect)
- [Definely + LangGraph](https://www.blog.langchain.com/customers-definely/)
- [Neo4j Legal Knowledge Graphs](https://neo4j.com/blog/developer/from-legal-documents-to-knowledge-graphs/)
- [NyayGraph - ACL 2025](https://aclanthology.org/2025.nllp-1.11.pdf)
- [Legal Graph RAG - arXiv 2025](https://arxiv.org/html/2502.20364v2)
- [Agentic AI in Legal - ContractPod](https://contractpodai.com/news/agentic-ai-legal/)
- [Multi-Agent Legal Systems Survey](https://www.oaepublish.com/articles/aiagent.2025.06)
- [Sarvam AI TTS](https://www.sarvam.ai/apis/text-to-speech/)
- [AI4Bharat Indic TTS](https://github.com/AI4Bharat/Indic-TTS)
- [BharatLaw AI](https://www.bharatlaw.ai/)
- [CaseMine CaseIQ](https://www.casemine.com/caseiq)
- [LegitQuest](https://www.legitquest.com/legal-research-tool)
