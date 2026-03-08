# Smriti — "Cursor for Law" Strategy

> The legal operating system for India's 1.7M lawyers.
> Free search. Paid workflow. One brain connecting research, drafting, and contracts.

*Created March 2026*

---

## 1. THE INSIGHT: Why "Cursor for Law" Works

### The Competitive Landscape is All Point Solutions

Every Indian legal AI competitor does ONE thing:

```
RESEARCH tools ──── [gap] ──── DRAFTING tools ──── [gap] ──── CONTRACT tools
  Jhana AI                       DraftBot Pro                    SpotDraft
  BharatLaw.ai                   Vidur AI                        (no Indian player)
  Indian Kanoon                  Supreme Today
  Smriti (us)                                                    ContraRed (us)
```

| Competitor | What They Do | What They DON'T Do |
|---|---|---|
| **Jhana AI** | Research + drafting + B2G courts | No contract redlining, no Word integration |
| **BharatLaw.ai** | AI research, 1M+ judgments, voice search, multilingual. Going for Series A | No contracts, no drafting, no Word |
| **DraftBot Pro** | Free AI drafting, 1.4Cr judgment DB, 1L+ lawyers | No contract review, no citation graph, no grounding |
| **Supreme Today** | SC/HC judgments + AI tools, endorsed by High Courts | No contracts, no drafting workflow |
| **Vidur AI** | Drafting + tax + regulatory, WhatsApp access | No research engine, no contracts |
| **Harvey + SCC** | Full-stack AI for BigLaw ($1000+/mo) | India is an afterthought, not purpose-built |

**We are the only team in India that has built BOTH a research engine (Smriti) AND a contract engine (ContraRed).** That's the unfair advantage.

### The Cursor Playbook

Cursor didn't invent code completion (Copilot existed) or code editors (VS Code existed). Cursor connected them into one flow where AI understands your entire context. Result: $2B ARR, fastest-growing SaaS ever.

| Cursor's Move | Our Move |
|---|---|
| Forked VS Code (existing platform, billions of users) | Build inside Word (1.2B users) + browser. Don't make lawyers switch. |
| Served power users doing the hardest coding first | Serve associates doing the hardest legal grunt work first |
| Custom AI for workflow + foundation models for reasoning | Custom legal NLP (citation extraction, section tagging) + Gemini for reasoning |
| 36% free-to-paid conversion via genuinely useful free tier | Free SC search (genuinely useful) -> paid contracts + drafting + HC |
| Product-led, zero marketing spend to $100M ARR | Product so good one associate tells the whole firm |
| $20/mo individuals, enterprise for teams | Rs 999/mo individuals, Rs 2,500/seat for firms |

**Key Cursor lessons (from [Growth Machines analysis](https://www.builderlab.ai/p/growth-machines-the-cursor-story)):**
- Fork the existing platform, don't build from scratch -> We build inside Word + browser
- Power user obsession: 1M users generating 4x revenue of Copilot's 20M -> Serve 1,000 serious lawyers, not 100K casual ones
- Custom AI + foundation models split -> Our citation graph + section tagger are custom; Gemini is the foundation
- Free tier that's genuinely useful, not crippled -> Free search must be better than Indian Kanoon

---

## 2. TWO PRODUCTS BECOMING ONE

### The Brand

**Smriti** is the umbrella. ContraRed becomes **Smriti Contracts** (a module, not a separate product).

Tagline: *"Your AI legal workspace."*

One login. One subscription. One brain.

### The Lawyer's Actual Day (and Where Smriti Inserts)

```
                    A LAWYER'S DAY
                    ===============

   +----------+    +----------+    +----------+    +----------+
   | RESEARCH |---+|  DRAFT   |---+| REVIEW   |---+|  FILE    |
   |          |    |          |    |          |    |          |
   | Find     |    | Write    |    | Redline  |    | Submit   |
   | cases,   |    | petition,|    | contract,|    | to court |
   | check    |    | opinion, |    | check    |    | or       |
   | law      |    | memo,    |    | clauses  |    | client   |
   |          |    | notice   |    |          |    |          |
   +----------+    +----------+    +----------+    +----------+
        |                |                |
   +----v----+     +-----v-----+   +-----v------+
   | SMRITI  |     |  SMRITI   |   |  SMRITI    |
   | SEARCH  |<--->|  DRAFT    |<->| CONTRACTS  |
   | (today) |     |  (new)    |   | (ContraRed)|
   +---------+     +-----------+   +------------+
        ^                ^                ^
        +----------------+----------------+
              SHARED LEGAL INTELLIGENCE
           (citation graph, case law, playbooks)
```

---

## 3. CONVERGENCE ROADMAP: Feature by Feature

### Phase A: "Connect the Islands" (Month 1-2)

Ship both products under one login. Build three killer bridges:

| Bridge Feature | What It Does | Why It's Magic |
|---|---|---|
| **"Cite in Word"** | Found a case in Smriti Search? One click -> inserts formatted citation + ratio decidendi into your Word document | No competitor does this. Jhana can't inject into Word. |
| **"Research this clause"** | Select a contract clause in Word -> Smriti finds SC/HC cases where similar clauses were litigated | Connects contract review to case law. Nobody has this. |
| **"Check if good law"** | Hovering over a citation in Word? Smriti checks if it's overruled/distinguished | Citation intelligence meets Word. |

These three bridges make the two products feel like ONE brain.

**Technical implementation:**
- Smriti Search: Already built (FastAPI + Next.js + Pinecone + Neo4j)
- Smriti Contracts: Already built (ContraRed Word add-in + FastAPI backend)
- Bridges: Shared auth (JWT), shared API gateway, Word add-in calls Smriti's search API
- Effort: ~2-3 weeks to unify auth + build bridge endpoints

### Phase B: "Smriti Draft" (Month 3-4)

The missing middle between research and contracts.

| Draft Type | Market | Competitors | Our Edge |
|---|---|---|---|
| **Bail applications** | Every criminal lawyer, every day | DraftBot Pro (free) | Grounded in actual SC bail jurisprudence from our search engine |
| **Writ petitions (Art 226/32)** | Constitutional lawyers | DraftBot Pro, Vidur | Auto-cites relevant fundamental rights cases from Smriti |
| **Legal notices** | Every practicing lawyer | DraftBot Pro | Template + AI, statute-aware |
| **Legal opinions/memos** | Corporate/transactional lawyers | Nobody does this well | Research -> Opinion in one flow |
| **Contract clauses** | Transactional lawyers | ContraRed already does this | AI-generated clauses based on playbook + case law |

**DraftBot Pro counter-positioning:** DraftBot is free but it's a generic LLM wrapper. It can't cite actual cases from a verified database. Smriti Draft is grounded -- every draft links to real cases from our search engine. "AI that sounds right" vs "AI that IS right."

### Phase C: "The Intelligence Layer" (Month 5-7)

Features that only work because we have research + contracts + drafting:

| Feature | What | Why Only We Can Build This |
|---|---|---|
| **Clause Risk Score** | "This indemnity clause has been struck down in 3/7 SC cases" | Needs citation graph + contract analysis |
| **Precedent Strength Meter** | Visual: "Strong (cited 200x, never overruled)" vs "Weak (distinguished 5x)" | Needs typed citation graph (Neo4j) |
| **Auto-Research Brief** | Upload case file -> Smriti reads it, identifies issues, researches each, produces memo with citations | Needs research + drafting + document understanding |
| **Playbook x Case Law** | "Your playbook says cap liability at 1x. Here are 4 SC cases supporting this." | Needs contract playbooks + search engine |
| **Judge Intelligence** | "Justice X ruled against uncapped indemnity in 3 cases. Consider capping." | Needs metadata + search + contract analysis |

### Phase D: "New Verticals" (Month 8-12)

Each vertical = new revenue stream + stickier platform:

| Vertical | What | Market | Difficulty | Revenue |
|---|---|---|---|---|
| **Compliance Tracker** | Track RBI/SEBI/MCA circulars, alert when they affect your practice area | In-house counsel, corporate firms | Medium | Rs 500-2K/mo add-on |
| **Court Date + Case Tracker** | Sync with eCourts, track hearing dates, auto-pull orders | Every litigator | Low-Medium | Free (retention driver) |
| **Due Diligence Module** | Upload company docs -> AI checks compliance with Companies Act, FEMA, SEBI | M&A lawyers, in-house | High | Rs 5-15K per DD project |
| **Litigation Analytics** | "Judge X grants bail in 73% of NDPS cases" / disposal time averages | Litigators, strategic planning | Medium | Premium feature |
| **Filing Prep** | Generate court-ready documents with proper formatting, index, synopsis | Every litigator filing in SC/HC | Low | Free (stickiness) |

---

## 4. THE "GOOGLE MOMENT" — Distribution Strategy

Google's insight: Search should be free, fast, and everywhere. Revenue comes from the 1% who need more.

### The Free Layer (Indian Kanoon Killer)

**Completely free, forever, no login required:**

1. SC + HC judgment search (with AI -- not keyword garbage)
2. Case summaries (AI-generated, one-page)
3. Basic citation checking ("Is this case overruled?")
4. One-click citation formatting (SC/HC format)

This makes Smriti the default starting point for every Indian law search.

### Distribution Hacks

**WhatsApp virality:** Every time a lawyer shares a Smriti case link on WhatsApp (lawyers live on WhatsApp), the recipient sees the case for free + beautiful UI + "Powered by Smriti." Indian Kanoon links are ugly. Ours are beautiful. That's virality.

**SEO domination:** Every SC/HC judgment gets its own clean URL page with AI summary. Google indexes them. Lawyers searching on Google land on Smriti instead of Indian Kanoon. This is how Indian Kanoon originally grew -- by being indexed by Google. We do the same but 10x better.

**LinkedIn/Twitter content engine:** Weekly "This Week in Supreme Court" AI-generated digest. Citation graph visualizations that go viral. "The 50 most-cited SC judgments of 2025" -- shareable content that drives traffic.

### The Paid Layer

| Feature | Free | Pro (Rs 999/mo) | Firm (Rs 2,499/seat/mo) |
|---|---|---|---|
| SC/HC search | Unlimited | Unlimited | Unlimited |
| AI case summaries | 5/day | Unlimited | Unlimited |
| Citation checking | Basic | Full graph (overruled/distinguished/affirmed) | Full + alerts |
| **Smriti Draft** | -- | 20 drafts/mo | Unlimited |
| **Smriti Contracts** | -- | 10 redlines/mo | Unlimited + custom playbooks |
| **"Cite in Word" add-in** | -- | Yes | Yes |
| **Research <-> Contract bridge** | -- | Yes | Yes |
| Compliance tracker | -- | -- | Yes |
| Litigation analytics | -- | -- | Yes |
| Firm workspace (shared research) | -- | -- | Yes |
| API access | -- | -- | Yes |

### The New-Gen Lawyer Plays

**"Smriti for Law Students" -- Free forever for .edu emails**
- Full search + summaries access
- Limited drafting
- They graduate -> already on Smriti -> bring it to their firm
- This is Figma's playbook (free for students, paid when pro). GitHub did this too.

**"Smriti Certified" -- A Badge Program**
- Complete Smriti's AI legal research course -> "Smriti Certified Legal Researcher" badge for LinkedIn
- New-gen lawyers love LinkedIn credentials
- Free content marketing + brand awareness + trained users
- Cost to build: zero (auto-generated from help docs)

---

## 5. THE ANTI-IVY LEAGUE PLAYBOOK

We don't have Harvard. Here's what we have that they don't:

### 1. Speed (Weapon #1)

Jhana has 9 people and bureaucracy. BharatLaw is raising Series A (board meetings, not shipping). DraftBot Pro is free (no money to hire).

**Commitment:** Ship one user-facing feature every week. Post it on LinkedIn/Twitter. "Week 14: Smriti now detects overruled cases in your Word documents." Consistency builds credibility without pedigree.

### 2. Radical Transparency (Counter-Pedigree)

Harvard founders hide behind prestige. We build in public.
- Share architecture decisions on Twitter/LinkedIn
- Publish search quality benchmarks ("Smriti found relevant case in 3/5 queries vs Indian Kanoon's 1/5")
- Show citation graph growing (weekly visualizations)
- Open-source parts of legal NLP (citation extraction regex, court normalizer)

Developers trust Cursor because they could see the product working. Same energy.

### 3. Obsessive User Intimacy

Jhana has 10K users they barely know. We'll have 20 users we know by name.
- Weekly 15-min call with each of first 20 users
- Fix their specific workflow pain within 24 hours
- Build features they ask for
- This is the Collison Installation (Stripe founders installed for users personally)

### 4. The VC Pitch (Contrarian Narrative)

**Don't pitch:** "We're building AI legal research for India"

**DO pitch:** "We're building the legal operating system. Every other tool does one thing -- research OR drafting OR contracts. We connect the entire workflow. Harvey does this for US BigLaw at $1,000/mo. We do it for the rest of the world's lawyers at $13/mo. India is our starting market, not our ceiling."

**Addressable market reframed:**
- India: 1.7M lawyers
- South Asia (Bangladesh, Sri Lanka, Pakistan -- all common law): 500K+
- Africa (Nigeria, Kenya, South Africa -- common law, English-speaking): 200K+
- Southeast Asia (Singapore, Malaysia): 100K+
- **Total: 2.5M+ lawyers at $10/mo avg = $300M+ TAM**

Now VCs listen.

---

## 6. THE 12-MONTH EXECUTION TIMELINE

### The Beachhead Market (YC-style Narrow Focus)

**20-30 commercial litigation associates (2-6 year PQE) at 5 specific Delhi/Mumbai mid-tier firms.**

Why them:
- Do BOTH litigation (need Smriti Search) AND transactional work (need Smriti Contracts)
- Bill Rs 5,000-15,000/hr -- saving 5 hrs/week = Rs 25K-75K value/week
- Firms pay for tools if you prove ROI on associate time
- Small enough group to personally onboard every single one

Target firms: DSK Legal, Luthra, Economic Laws Practice, Nishith Desai, Trilegal litigation desk.

### Month-by-Month

| Month | Ship | Target |
|---|---|---|
| **1** | Smriti Search free (SC). ContraRed as Smriti Contracts (paid). One login, one brand. "Cite in Word" bridge. | 50 signups |
| **2** | "Research this clause" bridge. SEO pages for every SC judgment. WhatsApp share links. | 200 signups, 5 Pro |
| **3** | Smriti Draft v1 (bail, writ, legal notice). HC ingestion starts (Delhi). | 500 signups, 15 Pro |
| **4** | Citation graph intelligence (overruled/distinguished). Precedent Strength Meter. | 1K signups, 30 Pro, Rs 30K MRR |
| **5** | Bombay HC. Auto-Research Brief. Judge intelligence v1. | 2K signups, 60 Pro |
| **6** | "Smriti for Law Students" at 3 NLUs. LinkedIn certification badge. | 5K signups, 100 Pro, Rs 1L MRR |
| **7** | Clause Risk Score (case law x contract). Court date tracker (eCourts). | 8K signups, first firm deal |
| **8** | Madras + Karnataka HC. Compliance tracker v1 (SEBI/RBI). | 12K signups, Rs 3L MRR |
| **9** | Filing prep module. Playbook x Case Law intelligence. | Rs 5L MRR |
| **10** | All major HCs. Due diligence module v1. | 20K signups |
| **11** | API launch. Mobile-responsive web app. Hindi judgments. | Rs 8L MRR |
| **12** | Apply YC. Pitch: "Rs 10L MRR, 25K users, full-stack legal AI for India." | Fundable |

### Hiring Timeline

| When | Role | Why | Cost |
|---|---|---|---|
| Month 7-9 | Full-stack engineer | Share the codebase | Rs 80K-1.2L/mo |
| Month 10-12 | Legal domain expert (practicing lawyer) | Validate accuracy, build templates, user trust | Rs 60K-1L/mo |
| Month 12-15 | DevOps/data engineer | HC scraping pipeline, infrastructure | Rs 80K-1.2L/mo |

---

## 7. COMPETITIVE MOAT SUMMARY

### Why This Strategy Is Defensible

```
Point solutions (Jhana, BharatLaw, DraftBot, Vidur)
  can each do ONE thing.

Harvey + SCC
  can do everything but costs $1000+/mo.

Smriti
  connects research + drafting + contracts + compliance
  at Rs 999/mo
  with citation intelligence nobody else has
  inside the tools lawyers already use (Word + browser).
```

**The integration IS the moat.** Building each piece is hard. Connecting them is 10x harder. Nobody else has both a research engine and a contract engine to connect.

### The Flywheel

```
Free search (better than Indian Kanoon)
  -> Lawyers discover Smriti via Google/WhatsApp
    -> Some try Draft or Contracts (paid)
      -> Usage data improves search quality
        -> Better search attracts more lawyers
          -> More lawyers = more data = better AI
            -> Firms adopt for whole team
              -> Revenue grows, fund expansion
                -> More courts, more verticals
                  -> More reasons to stay
                    -> Switching costs compound
```

---

## 8. UPDATED FULL COMPETITIVE LANDSCAPE (March 2026)

### All Known Indian Legal AI Players

| Player | Category | Funding | Revenue | Users | Threat to Smriti |
|---|---|---|---|---|---|
| **Harvey + SCC Online** | Full-stack AI (premium) | Harvey: $300M+ | Unknown | Enterprise only | LOW (different market -- $1000+/mo) |
| **Jhana AI** | Research + draft + B2G | $1.8M seed | Rs 2.58Cr/yr | 10K+ | HIGH (closest competitor) |
| **BharatLaw.ai** | AI research + voice + multilingual | Pre-Series A | Unknown | Unknown | HIGH (direct research competitor) |
| **DraftBot Pro** | Free AI drafting | None | Rs 0 (free) | 1L+ claimed | MEDIUM (free kills drafting revenue) |
| **DecoverAI** | Research + multi-doc analysis | $2M seed | Unknown | Unknown | MEDIUM |
| **Supreme Today** | SC/HC judgments + AI | Unknown | Unknown | HC-endorsed | MEDIUM |
| **Vidur AI** | Drafting + tax + regulatory | Unknown | Unknown | Unknown | LOW-MEDIUM |
| **CaseMine** | AI case research (older ML) | Small seed | Unknown | Unknown | LOW (stagnant) |
| **Indian Kanoon** | Free keyword search | None | Ad-supported | 5-10M/mo | BASELINE (the floor to beat) |
| **SCC Online** | Premium database | Established biz | Dominant | Market leader | INDIRECT (now via Harvey) |
| **Manupatra** | Premium database | Established biz | #2 market | Large | LOW (adding AI slowly) |

### What Nobody Has (Our Unique Combo)

| Capability | Jhana | BharatLaw | DraftBot | Harvey+SCC | **Smriti** |
|---|---|---|---|---|---|
| AI search on Indian law | Yes | Yes | No | Yes | **Yes** |
| Citation graph (typed) | Basic | No | No | Unknown | **Yes (Neo4j)** |
| Contract redlining | No | No | No | Yes | **Yes (ContraRed)** |
| Legal drafting | Yes | No | Yes (free) | Yes | **Yes (grounded)** |
| Word add-in | No | No | No | Yes | **Yes** |
| Research <-> Contract bridge | No | No | No | Partial | **Yes (unique)** |
| Hybrid RRF search | Unknown | Unknown | No | Unknown | **Yes** |
| Section-aware retrieval | Unknown | Unknown | No | Unknown | **Yes** |
| Free tier | Limited | Unknown | Yes (all free) | No | **Yes** |
| Rs 999/mo price point | Unknown | Unknown | Free | $1000+/mo | **Yes** |

---

## Sources

- [Harvey + SCC Online Partnership (Jan 2026)](https://www.harvey.ai/blog/harvey-partners-with-scc-online)
- [SCC Online Blog: Harvey Partnership](https://www.scconline.com/blog/post/2026/01/15/scc-online-harvey-partner-ai-legal-workflowssynonyms-related/)
- [Jhana AI](https://jhana.ai/)
- [Jhana Courtroom](https://jhana.ai/courtroom/)
- [Jhana $1.6M Seed (Inc42)](https://inc42.com/buzz/jhana-ai-bags-funding-to-build-an-ai-powered-research-drafting-tool-for-lawyers/)
- [Jhana Seed (Entrackr)](https://entrackr.com/2024/09/ai-paralegal-startup-jhana-raises-1-6-mn-in-seed-round/)
- [Jhana + CADRE ODR (The Wire)](https://m.thewire.in/article/ptiprnews/jhana-and-cadre-odr-announce-strategic-partnership-to-bring-legal-ai-intelligence-to-online-arbitration-and-mediation/amp)
- [Jhana Profile (Tracxn)](https://tracxn.com/d/companies/jhana/__gXaolIU-U3Jmu66hIpL22OlmqeYLqBzCCNvP_6EeNYM)
- [AI Legal Innovation India (Inc42)](https://inc42.com/features/how-are-legaltech-startups-making-their-case-in-india/)
- [Legal Tech India 2025 (Tracxn)](https://tracxn.com/d/explore/legal-tech-startups-in-india/__E1QQRMw4NEjHwC6iLnpj5s5God9ZktQAeqwocPbdMfk)
- [AI in India's Courts (Global Voices)](https://advox.globalvoices.org/2025/12/05/when-the-judge-meets-the-algorithm-ai-tools-entering-indias-courts/)
- [India Startup Funding 2025 (TechCrunch)](https://techcrunch.com/2025/12/27/india-startup-funding-hits-11b-in-2025-as-investors-grow-more-selective/)
- [Legal Tech Turning Point (NASSCOM)](https://community.nasscom.in/communities/tech-good/legal-tech-turning-point-what-2025-has-shown-us-so-far)
- [Cursor $2B ARR (TechCrunch)](https://techcrunch.com/2026/03/02/cursor-has-reportedly-surpassed-2b-in-annualized-revenue/)
- [Cursor Growth Story (BuilderLab)](https://www.builderlab.ai/p/growth-machines-the-cursor-story)
- [Cursor Growth Playbook (ProductGrowth)](https://www.productgrowth.blog/p/how-cursor-ai-hacked-growth)
- [AI Helping India's Lawyers (Microsoft)](https://news.microsoft.com/source/asia/2026/01/21/code-of-law-how-ai-is-helping-indias-lawyers-work-faster/)
- [BharatLaw.ai](https://www.bharatlaw.ai/)
- [DraftBot Pro](https://www.draftbotpro.com/)
- [DraftBot Pro (Tracxn)](https://tracxn.com/d/companies/draft-bot-pro/__4l61zpN4TKtgcjXBDuB0oSYW27toBdkrvEeh5vxpugk)
- [Supreme Today AI](https://supremetoday.ai)
- [Vidur AI](https://vidur.in/top-10-ai-tools-for-lawyers-in-india/)

---

*Created March 2026 | "Cursor for Law" strategy | Internal use*
