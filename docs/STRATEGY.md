# Smriti — Strategic Analysis: Becoming Harvey AI of India

---

## 1. MARKET OPPORTUNITY: Is This Relevant?

**Emphatically yes.** India has the 2nd largest legal profession globally.

| Metric | Number |
|--------|--------|
| Registered advocates | ~1.7 million (~1.2M active) |
| Pending cases | 50 million+ |
| Legal services market | $15-18 billion, 8-10% CAGR |
| Legal tech market | $600-900M today, $2-3B by 2030 (20-25% CAGR) |
| Legal research databases TAM | $200-400M |

### Pain Points (Why Lawyers Need Smriti)

1. **Keyword search fails for legal concepts** — Searching "right to privacy" misses "informational self-determination" or "bodily autonomy." Lawyers spend 3-8 hours on research that should take 30 min. **Smriti's hybrid semantic search directly solves this.**
2. **No citation intelligence** — No Indian equivalent of Shepard's/KeyCite. Manual tracing of which cases are overruled/distinguished. **Smriti's Neo4j graph is a genuine differentiator.**
3. **No AI summarization** — 50-100 page judgments, hours to extract ratio decidendi. Junior associates spend 60-70% of time on this.
4. **Poor metadata** — Indian Kanoon has wrong dates, missing bench composition. SCC Online better but still gaps.
5. **Dated UX** — SCC Online/Manupatra interfaces are from 2005. Young lawyers expect modern UX.
6. **Price barrier** — 80%+ of lawyers can't afford SCC Online (₹15K-50K/yr). Indian Kanoon is free but terrible.

### Regulatory Tailwinds

- **eCourts Phase III** (2023-2027): ₹7,210 crore budget for judiciary digitization
- **Supreme Court AI Committee**: Explicitly endorsing AI for legal research (SUPACE)
- **Open Data**: SC judgments on AWS S3 (CC-BY-4.0), Delhi HC publishing in machine-readable format
- **DPDP Act 2023**: Creates new legal complexity = more research demand
- **No restrictive AI regulation** in India as of 2025

### Adoption Readiness

| Segment | Size | Tech Ready | Will Pay | Priority |
|---------|------|-----------|----------|----------|
| Top-tier law firms | 3-5K lawyers | High | High (firm pays) | **Tier 1** |
| Mid-tier firms | 5-15K lawyers | High | Moderate | **Tier 1** |
| In-house counsel | 30-50K | High | High (company pays) | **Tier 1** |
| Litigation boutiques | 50-100K | Moderate-High | Moderate | Tier 2 |
| Solo practitioners (metros) | 200-300K | Moderate | Low-Moderate | Tier 2 (freemium) |
| Solo practitioners (Tier 2/3) | 500K+ | Low-Moderate | Low | Tier 3 |
| Law students | 1M+ | High | Very low | Tier 3 (growth) |

**Adoption-ready, willing-to-pay segment: ~50-70K professionals.** Mass market needs freemium.

---

## 2. COMPETITIVE LANDSCAPE (Updated March 2026)

### The Elephant in the Room: Harvey AI + SCC Online (Jan 2026)

**This changes everything.** On January 15, 2026, [Harvey AI partnered with SCC Online](https://www.harvey.ai/blog/harvey-partners-with-scc-online) to bring SCC's entire Indian legal database into Harvey's AI platform. This is no longer a hypothetical — Harvey is IN India.

**What the partnership offers:**
- SCC Online's full repository (case law, legislation, commentary, transcripts, forms) as a knowledge source inside Harvey
- Lawyers can query Indian legal materials alongside internal documents
- AI-powered case research, statutory analysis, drafting with Indian authorities
- Available to mutual customers of Harvey and SCC Online
- Pricing: Not disclosed, but Harvey is enterprise-only ($1,000+/user/month globally)

**What this means for Smriti:**
- The "no one is doing AI for Indian law" narrative is **dead**. Harvey + SCC = the most comprehensive Indian legal AI offering.
- BUT: this targets **only top-tier firms** that can afford Harvey. The 95% of Indian lawyers who can't pay $1,000/month are still completely unserved.
- SCC Online gets AI capabilities without building anything. Harvey gets Indian content without understanding Indian law deeply.
- The partnership is a **data integration, not a purpose-built Indian product**. Generic Harvey prompts + Indian data ≠ India-specific legal intelligence.

**Smriti's counter-positioning:** You're not competing with Harvey+SCC. You're building for the **99% of Indian lawyers Harvey will never serve.** Your price point (₹999/mo vs $1,000/mo) is a 100x difference.

---

### The Real Competitor: Jhana AI

**Jhana is the most important competitor to understand.** Here's the full picture:

**Company Profile:**
- Founded: 2022 at Harvard by Hemanth Bharatha Chakravarthy, Em McGlone, Ben Hoffner-Brodsky
- HQ: Bengaluru
- Funding: ₹15 Cr (~$1.8M seed) led by Together Fund (Girish Mathrubootham/Freshworks + Manav Garg/Eka Software)
- Angel investors: Shyamal Anadkat (OpenAI), Scott Davis (VMware), Kunal Shah (CRED), Harshil Mathur + Shashank Kumar (Razorpay)
- Team: ~9 employees (as of May 2025), claims 25 on website
- Revenue: ₹2.58 Cr annual (as of March 2025)
- Users: 10,000+ claimed, 800+ beta users at funding time

**Jhana's Products (3 layers):**

| Product | Target | What It Does |
|---------|--------|-------------|
| **Searcher** | Lawyers | Legal research across 16M+ Indian documents, keywords + prompts + booleans |
| **Paralegal** | Lawyers | Generates arguments, opinions, draft documents |
| **Suit** | Lawyers | Bulk document upload, data extraction |
| **Courtroom** (NEW) | **Judiciary/Government** | AI APIs for courts — filing scrutiny, docket generation, headnotes, AI dictation for judges |
| **PUBSEC** (NEW) | **Government** | GovTech benchmark for admin and governance |

**The Pivot Signal:**

Jhana is **not abandoning legal research but expanding aggressively into B2G (government/judiciary)**:

- **Courtroom** is deployed in 5+ courts, used by 150+ judges and registrars
- Features include: AI filing scrutiny (scanning PDFs for defects), "Steno" (voice-to-court-order), "Clerk" (automated case briefings), headnote generation
- Courtroom is sold as **composable APIs** that courts host on their own infrastructure
- They partnered with CADRE ODR (Jan 2026) for AI in online arbitration
- This B2G pivot makes sense: eCourts Phase III has ₹7,210 Cr budget, government contracts are large and recurring

**Why the pivot matters for you:**

The investor who told you "VCs aren't interested because Jhana is pivoting" is reading the signal correctly:
1. Jhana tried B2C/B2B legal research first → ₹2.58 Cr revenue with 10K users = ~₹215/user/month average. That's very low ARPU.
2. They're diversifying into government because **lawyers don't pay enough**
3. The B2G pivot validates the core problem: Indian lawyers' willingness to pay is brutally low
4. BUT: Jhana hasn't abandoned the lawyer product. They're doing both. With 9 employees and ₹2.58 Cr revenue, they're stretched thin.

**Jhana's Technical Approach:**
- Model-agnostic architecture (routes across GPT, Claude, Gemini — not locked to one provider)
- "National Legal Archive" — 16M+ judgments and statutes (much larger corpus than Smriti's current 35K SC)
- Full document ingestion (1000+ pages, unlimited file sizes)
- Positions as "infrastructure layer" above generic AI models

**Jhana vs Smriti — Honest Comparison:**

| Dimension | Jhana | Smriti |
|-----------|-------|--------|
| Founded | 2022 (Harvard) | 2024-2025 |
| Funding | ₹15 Cr ($1.8M) | Bootstrapped |
| Team | ~9-25 people | Solo founder |
| Data corpus | 16M+ documents (all courts) | 35K SC judgments (expanding) |
| Revenue | ₹2.58 Cr/yr | ₹0 |
| Users | 10,000+ | Pre-launch |
| Tech | Model-agnostic, multi-LLM | Gemini + Pinecone + Neo4j |
| Citation graph | Basic citation networks | **Full Neo4j graph with typed relationships** |
| Hybrid search (RRF) | Unknown | **Yes — semantic + keyword + metadata fusion** |
| Section-aware chunking | Unknown | **Yes — FACTS/ARGUMENTS/RATIO tagged** |
| B2G presence | 5+ courts, 150+ judges | None |
| Differentiator | Breadth (16M docs, B2G) | Depth (search quality, citation intelligence) |

---

### Other AI Competitors (Updated)

| Startup | Status | Threat |
|---------|--------|--------|
| **DecoverAI** | Raised $2M seed (2024), legal research + multi-document analysis | Medium — newer player, watch closely |
| **Jurisphere.ai** | Active, targets in-house counsel + corporate law firms | Low-Medium — niche |
| **CaseMine** | Still active, CaseIQ feature, but pre-LLM era AI, stagnant growth | Low |
| **Nearlaw** | Small, Maharashtra-focused | Low |
| **Adalat.AI** | Speech-to-text for courts (Kerala), different segment | Low |
| **SpotDraft** | Contract lifecycle ($105M total funding) — NOT a competitor, different segment | None |

### Established Players

| Platform | Strength | Weakness | 2026 Status |
|----------|----------|----------|-------------|
| **SCC Online** | Comprehensive, court-trusted, gold-standard headnotes | Expensive, dated UX | **Now partnered with Harvey AI** — getting AI capabilities |
| **Manupatra** | Good coverage, decent pricing | Weak search, "Manu/AI" is surface-level | Adding AI features slowly |
| **Indian Kanoon** | Free, 5-10M monthly users | No AI, poor metadata, basic UI | Unchanged, still the default for price-sensitive lawyers |

### The Real Competitive Landscape (Brutally Honest)

```
                        PREMIUM ($1000+/mo)
                        ┌─────────────────┐
                        │  Harvey + SCC    │  ← Top 50 firms only
                        │  (Jan 2026)      │
                        └─────────────────┘

                        MID-TIER (₹1K-5K/mo)
                        ┌─────────────────┐
                        │  Jhana AI        │  ← 10K users, ₹2.58Cr rev
                        │  CaseMine        │  ← Stagnant
                        │  DecoverAI       │  ← New, $2M funded
                        │  ★ SMRITI ★      │  ← Pre-launch
                        └─────────────────┘

                        FREE
                        ┌─────────────────┐
                        │  Indian Kanoon   │  ← 5-10M users, no AI
                        │  eCourts         │  ← Government portal
                        └─────────────────┘
```

**Smriti's battleground is the mid-tier.** You compete with Jhana and CaseMine for lawyers willing to pay ₹1-5K/month. Harvey+SCC is out of reach for 95% of the market. Indian Kanoon is the floor you must dramatically beat.

### Updated Comparison Matrix

| Feature | Harvey+SCC | Jhana AI | Indian Kanoon | **Smriti** |
|---------|-----------|----------|--------------|-----------|
| Pricing | $1000+/mo | Unknown (est. ₹1-3K/mo) | Free | **₹999/mo** |
| Data corpus | SCC's full database | 16M+ docs | Millions | **35K SC (expanding)** |
| Semantic Search | Harvey's AI | Multi-model | No | **Gemini embeddings** |
| Hybrid RRF Search | Unknown | Unknown | No | **Yes** |
| RAG Chat | Yes | Yes (Paralegal) | No | **Yes** |
| Citation Graph | Unknown | Basic | Basic | **Neo4j with typed relationships** |
| Section-aware search | Unknown | Unknown | No | **Yes (RATIO/FACTS/etc.)** |
| B2G/Courts | No | Yes (5+ courts) | No | **No** |
| Target | BigLaw | Lawyers + Govt | Everyone | **Lawyers** |

---

## 3. THE VC PROBLEM: Why Investors Are Skeptical

### The Investor's Warning is Correct

An investor told you: *"Not many VCs are interested in legal tech — Jhana is the only funded company and even they're pivoting."*

**This is substantially true.** Here's the data:

**Indian legal tech funding reality:**
- Out of 960+ legal tech companies in India, only 86 have received any funding
- Only 17 have reached Series A or higher
- The actually-funded companies (SpotDraft $105M, Vakilsearch/Zolvit) are either serving **global markets** or doing **compliance/services** — NOT Indian legal research
- In the "AI legal research for Indian courts" vertical specifically: Jhana ($1.8M) and DecoverAI ($2M) are essentially it
- Total Indian legal tech funding in 2025: $119M across 8 rounds — sounds big but most went to SpotDraft and non-research companies

**Why VCs say no:**

| VC Objection | Reality | Counter-argument |
|-------------|---------|-----------------|
| "TAM is too small" | Paying lawyers = ~50-70K. At ₹12K/yr = ₹84Cr ($10M) TAM | Expand to common-law markets (SEA, Africa, UK) for $100M+ TAM |
| "Willingness to pay is too low" | SCC Online charges ₹15K-50K/yr. Indian Kanoon is free. | AI that saves 10 hrs/week justifies ₹1K/mo even for price-sensitive lawyers |
| "Jhana is pivoting to B2G" | True — B2G has larger contracts | B2G is slow, political. B2B/B2C can move faster |
| "No successful Indian legal research AI exists" | True — pattern matching says avoid | Someone will crack it. AI changes the economics fundamentally |
| "Billing rates are 10-20x lower than US" | Top Indian lawyers bill ₹15-50K/hr vs US $500-2K/hr | Still enough ROI if the tool saves 5+ hours/week |

**What this means for Smriti's fundraising strategy:**

1. **Don't pitch "AI legal research for India"** — VCs will pattern-match to failures
2. **DO pitch**: "We're building the legal intelligence layer for 1.7M Indian lawyers. Here's our revenue proving they'll pay."
3. **Revenue-first approach is non-negotiable** — get to ₹5-10L MRR before talking to VCs
4. **The contrarian narrative**: Harvey entering India via SCC proves the market is real. Jhana's ₹2.58Cr revenue proves lawyers will pay. The question is who builds the best product at an Indian price point.
5. **Consider**: YC, Antler India, 100X.VC, gradCapital (they backed Jhana) as most likely early investors

---

## 3. MOAT STRATEGY

### Moat Stack (Ranked by Priority)

| Moat | Difficulty | Defensibility | Time | Priority |
|------|-----------|--------------|------|----------|
| **Legal Knowledge Graph** | 4/5 | 5/5 | 6-12 mo | CRITICAL |
| **Search Quality** | 4/5 | 4/5 | 3-6 mo | CRITICAL |
| **Brand Trust** | 3/5 | 5/5 | 6-18 mo | HIGH |
| **User Behavior Data** | 2/5 | 5/5 | 12-18 mo | HIGH |
| **Switching Costs** | 2/5 | 4/5 | 3-6 mo | HIGH |
| **Citation Analysis Algorithms** | 3/5 | 4/5 | 3-6 mo | HIGH |
| **Network Effects** | 3/5 | 5/5 | 12-24 mo | MEDIUM |
| **Legal NLP Models** | 3/5 | 3/5 | 6-12 mo | MEDIUM |

### 3A. Knowledge Graph Moat (CRITICAL)

The base data is public. Your moat is **derived intelligence**:

- **Typed citation relationships**: CITES → OVERRULES / DISTINGUISHES / AFFIRMS / FOLLOWS (requires legal reasoning, not just regex)
- **Authority scores**: PageRank-style scoring weighted by bench strength + recency
- **Precedent chains**: Follow a legal principle through decades of cases
- **Overruling cascades**: When Case X is overruled, flag every case that relied on it
- **Statute-to-case mapping**: Section 302 IPC → every case that interpreted it

### 3B. Search Quality Moat (CRITICAL)

A lawyer who finds the right case in 3 searches instead of 15 will never go back.

- Section-aware retrieval (search within RATIO DECIDENDI only)
- Citation-aware ranking (boost cases cited 500 times over those cited 3 times)
- Bench strength weighting (Constitution Bench > Division Bench > Single Judge)
- Legal query understanding (fine-tuned for Indian legal concepts)

### 3C. Data Flywheel

```
More users → More search queries → Better relevance signals
  → Better search quality → More users → ...
```

- Log every search, click, time-on-page, bookmark
- "Lawyers who read this case also read..." recommendations
- This flywheel is nearly impossible to replicate once established

### 3D. Switching Costs

- Saved searches with alerts
- Organized case folders by matter/client
- Annotated cases (highlights, notes, tags)
- Chat history (institutional memory)
- Firm-level shared workspaces

### 3E. Trust (THE Moat in Legal)

- **Always show sources** — every AI answer cites exact judgment paragraphs
- **Confidence indicators** — "High confidence (cited in 47 judgments)"
- **Citation accuracy score** — publicly report: "98.5% citation accuracy"
- **Precedent health warnings** — flag overruled cases everywhere they appear
- **DPDP Act compliant from day 1** — market this aggressively

**The bottom line**: Incumbents will bolt AI onto 20-year-old architectures. You're building the right architecture from day zero. The knowledge graph + user data flywheel = structural advantage.

---

## 4. ROADMAP: Becoming Harvey of India

### Harvey's Timeline (Reference)

| Date | Milestone |
|------|-----------|
| 2022 Q1 | Founded |
| 2022 Q4 | OpenAI partnership, early GPT-4 access |
| 2023 Q1 | Landed Allen & Overy |
| 2023 Q2 | $21M Series A (Sequoia) |
| 2024 Q1 | $80M Series B |
| 2024 Q3 | $100M+ Series C |
| 2025 Q1 | $300M raise, $3B+ valuation |

### Smriti's Roadmap

#### 90-Day Sprint (NOW)

**Week 1-2: Ship**
- Complete Phase 3-4, deploy to production
- Get domain (smriti.law / smriti.legal)
- Send to 20 lawyers via LinkedIn/personal network

**Week 3-4: Listen**
- 10 user interviews (30 min each)
- Fix top 3 UX issues
- Start tracking: searches/day, return visits

**Week 5-8: Build the Moat**
- Ingest all 35K SC judgments
- Build citation analysis (overruled/distinguished/followed)
- Launch newsletter ("This Week in SC")
- Get to 50 weekly active users

**Week 9-12: Validate Payment**
- Launch Pro tier at ₹999/month
- Convert 5 free users to paid
- Start Delhi HC ingestion
- Apply to YC / Antler / 100X.VC
- Get to 100 WAU

#### Quarter 2 (Months 4-6): Product-Market Fit

- Citation intelligence (precedent strength scoring)
- Petition drafting v1 (bail, writ, appeal templates)
- 100 WAU, 3 paying customers
- Newsletter → 1,000 subscribers

#### Quarter 3 (Months 7-9): Fundable

- Delhi + Bombay HC judgments (~3M docs)
- Raise angel/pre-seed (₹50L-1Cr)
- First engineer hire
- 300 WAU, 20 paying users
- "Smriti for Law Students" free tier
- Present at 2 legal conferences

#### Quarter 4 (Months 10-12): Scaling

- 3 more High Courts (Madras, Karnataka, Calcutta)
- NCLT/NCLAT coverage (corporate lawyers will pay for this)
- 500 WAU, ₹3L MRR
- Enterprise pilot with 1 mid-size firm
- Hire legal domain expert

#### Year 2 (Months 13-24): Market Leader

- Seed round: ₹3-7Cr ($350K-850K)
- All 25 High Courts covered
- Contract analysis for Indian law
- RBI/SEBI compliance tracking
- 2,000 WAU, ₹25L MRR
- Team of 8-10
- 5+ enterprise clients

#### Year 3 (Months 25-36): Series A & Dominance

- Series A: ₹25-50Cr ($3-6M)
- ₹1Cr+ MRR
- Full tribunal coverage
- Hindi / regional language support
- API platform launch
- 10,000+ users, 50+ firm clients

### Product Expansion Sequence

| Phase | What to Build | Why This Order |
|-------|--------------|----------------|
| Now | SC search + citation graph + RAG chat | Core value prop, validates demand |
| Next | Petition/brief drafting | Highest-frequency task for Indian lawyers |
| Then | High Court judgments (top 5 first) | Expands addressable market 10x |
| Then | Tribunal coverage (NCLT first) | Corporate lawyers will pay premium |
| Later | Contract analysis, compliance tracking | Revenue diversification |
| Later | Multi-language, API platform | Mass market + platform play |

### Pricing Strategy

| Tier | Price | Target | Key Features |
|------|-------|--------|-------------|
| **Free** | ₹0 | Students, casual users | 10 searches/day, SC only, no drafting |
| **Pro** | ₹999/mo (₹9,999/yr) | Solo/small firm lawyers | Unlimited search, all courts, citation analysis, 50 drafts/mo |
| **Team** | ₹2,499/user/mo | Mid-tier firms | + Shared workspaces, analytics, priority support |
| **Enterprise** | Custom (₹5-15L/yr) | Big Law, corporates | + API, custom integrations, SLA, dedicated support |

**₹999/mo = cheaper than SCC Online, with AI capabilities SCC Online doesn't have. "Better AND cheaper."**

### Go-to-Market Sequence

1. **"20 Lawyers" Program** (Month 1-3) — Free lifetime access for feedback + testimonials
2. **Content-led growth** (Month 3-6) — Newsletter, AI-generated SC summaries, social content
3. **Law firm pilots** (Month 6-9) — 5 firms, free 3-month trial, measure hours saved
4. **Conference circuit** (Month 9-12) — NLSIU, IBA, HC bar associations
5. **Law school partnerships** (Month 6+) — Free access to NLUs, build pipeline

### Funding Path

| Stage | Timing | Amount | From | Milestones Needed |
|-------|--------|--------|------|------------------|
| Bootstrapped | Now-Month 6 | ₹0-5L | Personal | 20 users, working product |
| Angel/Pre-seed | Month 6-9 | ₹50L-1Cr | Angels, iSPIRT | 100 WAU, 3 paying users |
| Seed | Month 12-18 | ₹3-7Cr | Blume, 100X, Antler | 500 WAU, ₹5L MRR, 5 HC coverage |
| Series A | Month 24-30 | ₹25-50Cr | Accel, Sequoia/Surge | ₹50L MRR, 50+ firm clients |

### Infrastructure Costs at Scale (16.7M docs)

| Service | Monthly |
|---------|---------|
| Pinecone (167M vectors) | $10-17K |
| PostgreSQL (Cloud SQL) | $500-1K |
| Neo4j AuraDB | $500-1K |
| Cloud Run | $200-500 |
| GCS | $300-500 |
| Gemini API | $2-5K |
| **Total** | **$14-25K/mo** |

Need ~500 Pro users OR 2-3 enterprise clients to cover.

### Key Metrics to Track

| Metric | Target | Why |
|--------|--------|-----|
| WAU | 100→500→2K→10K | Core growth metric |
| Searches/user/week | 10+ | Habit formation signal |
| Net Revenue Retention | 120%+ | Users expanding/upgrading |
| Hallucination rate | <2% | Trust metric — track rigorously |
| Time saved per user | Measurable hours/week | ROI proof for enterprise sales |
| CAC:LTV | 1:3+ | Unit economics |

---

## 5. RISKS & MITIGATION (Updated March 2026)

| Risk | Severity | Mitigation |
|------|----------|------------|
| **Harvey + SCC Online partnership** | CRITICAL | They serve top 50 firms at $1000+/mo. You serve the 99%. Different markets. Go deeper on Indian-specific features they can't match. |
| **Jhana AI has 2-year head start + funding** | HIGH | They have breadth (16M docs), you build depth (search quality, citation intelligence). Their pivot to B2G means less focus on B2C. 9 employees = stretched thin. |
| **AI hallucination kills trust** | HIGH | RAG grounding (always show sources), hallucination test suite, confidence scores, "verify" buttons |
| **VCs won't fund Indian legal tech** | HIGH | Revenue-first. Get to ₹5-10L MRR before approaching VCs. Pitch common-law expansion path, not just India TAM. |
| **Low willingness to pay** | HIGH | This is the #1 structural risk. Jhana's ₹2.58Cr/10K users = ₹215/user/month proves it. Focus on the paying segment (firms, in-house), not solo practitioners. |
| **Running out of money** | HIGH | Keep burn <₹50K/mo pre-funding. Apply for Google Cloud, AWS, Azure startup credits ($100K+ available). |
| **Data corpus gap vs Jhana (16M vs 35K)** | MEDIUM | Expand HC ingestion aggressively. 35K SC is fine for MVP but you need HC coverage fast. |
| **Regulatory changes** | LOW | DPDP compliant from day 1, monitor SC AI Committee guidance |

---

## 6. THE HONEST ASSESSMENT: Where Smriti Stands Today

### Strengths (What You Have)
- **Superior architecture**: Hybrid RRF search + Neo4j citation graph + section-aware chunking. Neither Jhana nor Harvey+SCC has confirmed this combination.
- **Citation intelligence**: Typed relationship classification (OVERRULES/DISTINGUISHES/AFFIRMS) is a genuine moat nobody else has built for Indian law.
- **Price point**: ₹999/mo makes you 100x cheaper than Harvey+SCC and competitive with Jhana.
- **Open-source data foundation**: CC-BY-4.0 dataset means zero data acquisition cost for SC.
- **Modern tech stack**: Built for 2026, not bolted onto 2005 infrastructure.

### Weaknesses (Be Honest)
- **Data corpus gap**: 35K SC vs Jhana's 16M. This is your biggest weakness.
- **No users, no revenue**: Jhana has 10K users and ₹2.58Cr revenue. You have zero.
- **Solo founder**: Jhana has 9-25 people, Harvard pedigree, and $1.8M.
- **No court/government relationships**: Jhana has 150+ judges using their Courtroom product.
- **No funding**: In a market where VCs are already skeptical.

### The Path Forward

**You don't need to be Harvey. You need to be the "Indian Kanoon that's actually good."**

Indian Kanoon has 5-10M monthly users but zero AI. If you can be "Indian Kanoon with AI, citation intelligence, and great UX" at a free/₹999 price point, you've found the biggest gap in the market:

```
Indian Kanoon (free, terrible search, no AI)
        ↓ 10M users want better
★ SMRITI (free tier + ₹999/mo, AI search, citations) ★
        ↑ Lawyers who can't afford ₹15K+/yr
SCC Online / Harvey (₹15K-₹85K+/yr)
```

### What To Do RIGHT NOW

1. **Stop planning, start shipping.** Your Phase 2 is done. Get 20 real lawyers using it this month.
2. **Expand data FAST.** 35K SC judgments is table stakes. Start HC ingestion (Delhi, Bombay first).
3. **Build citation intelligence.** This is your only clear moat vs Jhana. Make it world-class.
4. **Revenue before fundraising.** Even ₹50K/month proves the thesis. VCs need to see lawyers paying.
5. **Don't copy Jhana's B2G pivot.** Government contracts are slow, political, and require relationships you don't have. Stay focused on lawyers.

---

## Sources

- [Harvey + SCC Online Partnership (Jan 2026)](https://www.harvey.ai/blog/harvey-partners-with-scc-online)
- [SCC Online Blog: Harvey Partnership](https://www.scconline.com/blog/post/2026/01/15/scc-online-harvey-partner-ai-legal-workflowssynonyms-related/)
- [Jhana AI — Official Website](https://jhana.ai/)
- [Jhana Courtroom Product](https://jhana.ai/courtroom/)
- [Jhana $1.6M Seed Funding (Inc42)](https://inc42.com/buzz/jhana-ai-bags-funding-to-build-an-ai-powered-research-drafting-tool-for-lawyers/)
- [Jhana Seed Funding (Entrackr)](https://entrackr.com/2024/09/ai-paralegal-startup-jhana-raises-1-6-mn-in-seed-round/)
- [Jhana + CADRE ODR Partnership (The Wire)](https://m.thewire.in/article/ptiprnews/jhana-and-cadre-odr-announce-strategic-partnership-to-bring-legal-ai-intelligence-to-online-arbitration-and-mediation/amp)
- [Jhana Company Profile (Tracxn)](https://tracxn.com/d/companies/jhana/__gXaolIU-U3Jmu66hIpL22OlmqeYLqBzCCNvP_6EeNYM)
- [How AI Is Powering Legal Innovation in India (Inc42)](https://inc42.com/features/how-are-legaltech-startups-making-their-case-in-india/)
- [Legal Tech India 2025 Market Trends (Tracxn)](https://tracxn.com/d/explore/legal-tech-startups-in-india/__E1QQRMw4NEjHwC6iLnpj5s5God9ZktQAeqwocPbdMfk)
- [AI Tools Entering India's Courts (Global Voices)](https://advox.globalvoices.org/2025/12/05/when-the-judge-meets-the-algorithm-ai-tools-entering-indias-courts/)
- [India Startup Funding 2025 (TechCrunch)](https://techcrunch.com/2025/12/27/india-startup-funding-hits-11b-in-2025-as-investors-grow-more-selective/)
- [Legal Tech at a Turning Point (NASSCOM)](https://community.nasscom.in/communities/tech-good/legal-tech-turning-point-what-2025-has-shown-us-so-far)

---

*Updated March 2026 | Strategic analysis for internal use | All competitive data sourced from public web*
