# Chapter 8: The Face of Smriti

---

All the intelligence in the world means nothing if nobody can use it. The backend can extract metadata, embed vectors, and run research agents — but what does the *user* see?

This chapter is about Smriti's frontend — the interface that makes 35,000 judgments and an AI research agent accessible to law students, practicing lawyers, and legal scholars.

---

## The Tech Stack

Smriti's frontend is built with:
- **Next.js 16** — React framework with server-side rendering
- **TypeScript** — Type-safe JavaScript (no `any` allowed!)
- **Tailwind CSS** — Utility-first styling
- **shadcn/ui** — Beautiful, accessible UI components built on Radix primitives
- **Vitest** — For testing (311 tests and counting)

Three fonts set the visual tone:
- **Inter** — Clean and modern (UI elements)
- **Lora** — Elegant serif (legal text, memos)
- **Noto Sans Devanagari** — Hindi support

---

## The Pages (32 of Them)

### Home Page
The first thing you see — a hero section with Smriti's tagline, a prominent search bar, and example queries to get started. Like Google for legal research, but smarter.

### Search Page
Type a question. Get results. But it's much more than that:

```
┌──────────────────────────────────────────────────┐
│ Search: "bail conditions economic offenses"       │
├──────────────────────────────────────────────────┤
│ Query Understanding:                              │
│ "Searching for bail jurisprudence in economic     │
│  offense cases, particularly under PMLA..."       │
├──────────────────────────────────────────────────┤
│ Filters: Court ▼  Year ▼  Case Type ▼  Act ▼    │
├──────────────────────────────────────────────────┤
│ Results (847 found):                              │
│                                                   │
│ 1. Vijay Madanlal v. Union of India (2022)       │
│    (2022) 7 SCC 1 • Supreme Court                │
│    BINDING • Cited by 234 cases                   │
│    "The court held that the twin conditions..."   │
│    [Precedent Badge: BINDING]                     │
│                                                   │
│ 2. P. Chidambaram v. Directorate of...           │
│    ...                                            │
├──────────────────────────────────────────────────┤
│ Facets:                                           │
│ Courts: SC (600) • Delhi HC (100) • Bombay (50)  │
│ Years:  2024 (45) • 2023 (78) • 2022 (120)      │
│ Types:  Criminal Appeal (200) • Writ (150)        │
└──────────────────────────────────────────────────┘
```

Each result shows a **Precedent Badge** — color-coded treatment strength:
- 🟢 **BINDING** — Must be followed
- 🔵 **PERSUASIVE** — Can be considered
- 🟡 **DISTINGUISHABLE** — Similar but different
- 🔴 **OVERRULED** — No longer good law

### Case Detail Page
Click a result to see the full judgment with:
- Structured metadata (parties, judges, bench size, date)
- Ratio decidendi (the core legal principle)
- Acts cited (with links to statute sections)
- Cases cited (with links to those cases)
- Equivalent citations (SCC, AIR, neutral citation formats)
- Similar cases (based on semantic similarity)

### Research Agent Workspace
The star of the show. This is where users interact with the AI research agent:

```
┌─────────────────────────────┬─────────────────────────┐
│  RESEARCH WORKSPACE         │  RESEARCH MEMO           │
│                             │                          │
│  ┌─────────────────────┐    │  ## Bail Under NDPS Act  │
│  │ Ask a legal question │    │                          │
│  │ "Can a person get    │    │  Section 37 of the NDPS  │
│  │  bail under NDPS?"   │    │  Act creates a special   │
│  └─────────────────────┘    │  regime for bail...      │
│                             │                          │
│  PROGRESS BAR               │  The Supreme Court in    │
│  ■■■■■■■□□□ 70%            │  *Union of India v.      │
│  Stage: Investigate         │  Ram Samujh*[1] held...  │
│                             │                          │
│  STEP TIMELINE              │  **Counter-view:**       │
│  ✅ Understand              │  However, in *Tofan      │
│  ✅ Decompose               │  Singh*[2], the court    │
│  🔄 Investigate             │  noted that...           │
│  ○ Challenge                │                          │
│  ○ Synthesize               │  ---                     │
│                             │  FOOTNOTES ──────────    │
│  PROCESS PANEL              │  [1] (1999) 6 SCC 681   │
│  • Reading Section 37 NDPS  │  [2] (2020) 3 SCC 145   │
│  • Found 8 case law results │                          │
│  • Searching Indian Kanoon  │  CONFIDENCE: 0.82       │
└─────────────────────────────┴─────────────────────────┘
```

Key UI components:
- **5-Stage Progress Bar** — Shows where the agent is (Understand → Decompose → Investigate → Challenge → Synthesize)
- **Step Timeline** — Vertical timeline with active glow on the current step
- **Process Panel** — Real-time updates as the agent works
- **Memo Viewer** — The research memo streams in real-time
- **Footnotes Panel** — Slide-out panel with citation details
- **Checkpoint Prompt** — When the agent pauses for approval, a prompt appears
- **Confidence Meter** — Visual score at the bottom

### Footnote Hover Preview
Hover over any footnote reference in the memo and see:

```
┌────────────────────────────────────────┐
│ Union of India v. Ram Samujh           │
│ (1999) 6 SCC 681                       │
│ Supreme Court of India                 │
│ Judge: K.T. Thomas, M.B. Shah         │
│ Bench: Division Bench (2 judges)       │
│ Treatment: FOLLOWED                    │
│ [Click to view full case]              │
└────────────────────────────────────────┘
```

### Chat Page
A conversational interface for asking legal questions. Unlike the research agent (which produces a formal memo), the chat is informal and iterative:

```
User: What is the "rarest of rare" doctrine?
Smriti: The "rarest of rare" doctrine was established by the Supreme Court
        in Bachan Singh v. State of Punjab (1980)...

        Sources:
        • Bachan Singh v. State of Punjab, (1980) 2 SCC 684
        • Machhi Singh v. State of Punjab, (1983) 3 SCC 470

User: Has it been modified recently?
Smriti: Yes, in several recent judgments...
```

### Judge Analytics
Explore judges: their case history, bench compositions, disposition patterns, and citation networks.

### Document Upload
Upload your own PDFs (contract, judgment, FIR) and Smriti analyzes them through a 6-step pipeline:
1. Extract text
2. Identify document type
3. Extract key entities
4. Find relevant precedents
5. Generate analysis
6. Create audio digest (in 22 Indian languages via Sarvam AI!)

### Agent History
Browse past research sessions, replay the agent's thought process, and continue with follow-up questions.

---

## SSE Streaming: The Technical Magic

The research agent's real-time updates work through **Server-Sent Events** — a one-way stream from server to browser:

```
Browser opens connection → Server starts sending events:

data: {"type": "status", "step": "classify", "message": "Understanding..."}

data: {"type": "progress", "stage": "investigate", "progress": 0.45}

data: {"type": "memo_stream", "chunk": "The Supreme Court held..."}

data: {"type": "done", "confidence": 0.82}
```

The browser processes each event as it arrives, updating the UI in real-time. The memo text literally appears word by word, like watching someone type.

**Keepalive heartbeats** every 15 seconds prevent the connection from timing out. If the stream disconnects unexpectedly, the frontend detects it and alerts the user.

---

## Security: Protecting the Users

The frontend handles security seriously:

### JWT Authentication
- **Access token**: 60-minute expiry
- **Refresh token**: 7-day expiry
- **Proactive refresh**: Before every API call, check if the token expires within 60 seconds; if so, refresh it silently
- **Session expired event bus**: When any API call detects an expired session, it broadcasts to all components simultaneously

### Account Lockout
- 10 failed login attempts → account locked for 5 minutes
- Warning messages: "3 attempts remaining"

### Error Handling
Every `catch` block surfaces errors to the user — no silent failures. This was a deliberate fix during the Silent Failure Audit (March 2026).

---

## Hindi Support (i18n)

Smriti supports Hindi through `next-intl`:
- All UI text has Hindi translations (`messages/hi.json`)
- Search queries can be in Hindi (translated to English for search, results translated back)
- Language toggle in the header

This matters because many Indian lawyers, especially in lower courts and rural areas, are more comfortable in Hindi than English.

---

## The Test Suite: 311 Tests

Every page, every component, every API interaction has tests:
- **Page tests**: Each of the 32 pages renders correctly
- **Component tests**: UI components behave as expected
- **Integration tests**: Search, agents, and chat work end-to-end
- **API client tests**: Token refresh, error handling, SSE streaming

All using **Vitest** (not Jest — Smriti uses Vite for builds, so Vitest is the natural choice).

---

> **Next: [Chapter 9 — Scaling the Mountain →](./09-scaling-the-mountain.md)**
>
> *Where Smriti goes from handling 100 test cases to ingesting 35,000 judgments — and how Vertex AI batch processing cut costs in half.*

---

### In the Code

| What | Where |
|------|-------|
| Home page | [frontend/src/app/page.tsx](../../frontend/src/app/page.tsx) |
| Search page | [frontend/src/app/search/page.tsx](../../frontend/src/app/search/page.tsx) |
| Research workspace | [frontend/src/app/agents/research/page.tsx](../../frontend/src/app/agents/research/page.tsx) |
| Agent components | [frontend/src/components/agents/](../../frontend/src/components/agents/) |
| Progress bar | [frontend/src/components/research-progress-bar.tsx](../../frontend/src/components/research-progress-bar.tsx) |
| Step timeline | [frontend/src/components/agent-step-timeline.tsx](../../frontend/src/components/agent-step-timeline.tsx) |
| Footnotes panel | [frontend/src/components/footnotes-panel.tsx](../../frontend/src/components/footnotes-panel.tsx) |
| API client (SSE) | [frontend/src/lib/api.ts](../../frontend/src/lib/api.ts) |
| Type definitions | [frontend/src/lib/types.ts](../../frontend/src/lib/types.ts) |
| Auth context | [frontend/src/lib/auth-context.tsx](../../frontend/src/lib/auth-context.tsx) |
| Hindi translations | [frontend/src/messages/hi.json](../../frontend/src/messages/hi.json) |
| All tests | [frontend/src/__tests__/](../../frontend/src/__tests__/) |
