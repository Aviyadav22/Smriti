# Chapter 10: The Road Ahead

---

Smriti started as a spark — a law student frustrated with keyword search, sitting in an NLP lecture, connecting dots.

In less than a month, it became a platform with 35,000 ingested judgments, 2.5 million vectors, a 5-stage research agent, a citation graph, Hindi support, and 2,500 tests. But the story isn't over. Not even close.

---

## What Smriti Can Do Today

Let's take a step back and appreciate what was built:

| Capability | What It Means |
|-----------|---------------|
| **Hybrid Search** | Find cases by meaning, not just keywords |
| **Citation Graph** | See how cases connect, who overruled whom |
| **Research Agent V3** | AI that reads statutes first, breaks down questions, finds counter-arguments |
| **HITL Checkpoints** | Lawyers guide the research, not just watch |
| **Judge Analytics** | Understand judicial patterns and bench compositions |
| **Document Upload** | Analyze your own PDFs — contracts, FIRs, judgments |
| **Audio Digests** | Listen to case summaries in 22 Indian languages |
| **Hindi Support** | Search and browse in Hindi |
| **DPDP Compliance** | Data erasure, consent tracking — India's privacy law |

---

## What's Coming Next

### More Courts
Right now, Smriti has Supreme Court judgments. But India has 25 High Courts, thousands of district courts, and specialized tribunals (NCLT, NCLAT, SAT, ITAT). Each one produces judgments daily.

The ingestion pipeline is designed to handle this — `source_dataset` metadata tracks where each case came from, and the architecture supports multiple data sources.

### Deeper Hindi NLP
Current Hindi support translates queries and results. But ideally, Smriti should understand Hindi legal text natively — many High Court judgments (especially from Hindi-speaking states) are written partly or entirely in Hindi.

### Citation Network Intelligence
The graph is built. The next step is smarter graph algorithms:
- **Precedent decay** — How much influence does a 1960 judgment have in 2026?
- **Landmark detection** — Automatically identify the most important cases on a topic
- **Prediction** — Which cases are likely to be cited in future judgments?

### Real-Time Updates
Currently, ingestion is batch. The future includes real-time ingestion — as soon as the Supreme Court publishes a new judgment, Smriti processes and indexes it within hours.

### Multi-Agent Workflows
The research agent is powerful, but it's one agent. Future agents include:
- **Case Prep Agent** — Prepare for a specific hearing (already has a page)
- **Strategy Agent** — Evaluate litigation strategy
- **Drafting Agent** — Draft legal documents using precedent
- **Compliance Agent** — Check contracts against relevant statutes

### Mobile App
Many Indian lawyers work from phones, not desktops. A mobile-first interface would dramatically expand reach.

---

## The Vision

Smriti isn't just a search engine. It's not just a chatbot. It's a **legal intelligence platform** — one that understands Indian law the way a senior lawyer does, but can process information at machine speed.

The vision:

> **Every law student, every small-town lawyer, every public interest litigant should have access to the same quality of legal research that top-tier firms charge lakhs for.**

That's the north star. Every feature, every optimization, every 3 AM debugging session was in service of that goal.

---

## The Brand: NeetiQ

Smriti lives under the brand **NeetiQ** — a play on "Neeti" (नीति, meaning policy/law in Sanskrit) and "IQ" (intelligence). The domain **neetiq.in** is the public face.

Behind the scenes:
- **Domain**: neetiq.in (registered via GoDaddy)
- **Hosting**: Hostinger VM (currently hosts the Smriti database)
- **Business email**: contact@neetiq.in — the identity for YouTube, Instagram, and other social channels
- All managed under Avi's primary email: aviyadav.official@gmail.com

The plan: build a content presence around legal tech in India — tutorials, case breakdowns, product demos — all under the NeetiQ banner. The product is Smriti. The brand is NeetiQ.

---

## A Note on Open Source and Attribution

Smriti stands on the shoulders of giants:
- **Dattam Labs** — For making 35,000 SC judgments publicly available (CC-BY-4.0)
- **Google Gemini** — For embedding and reasoning capabilities
- **Pinecone** — For managed vector search
- **Neo4j** — For the citation graph
- **Cohere** — For reranking
- **Sarvam AI** — For Indian language TTS
- **Indian Kanoon** — For supplementary legal data
- **The open-source community** — FastAPI, Next.js, LangGraph, and hundreds of libraries

---

## The Numbers That Matter

It's easy to get lost in technical metrics. But the numbers that really matter are:

- **Time saved**: A research memo that took a junior lawyer 4-6 hours now takes 2 minutes
- **Accessibility**: Free tier access for law students
- **Coverage**: Every Supreme Court judgment from the open dataset
- **Accuracy**: Every citation in the memo is verified against actual search results

---

## From Spark to Smriti

This project started in April 2024 because a student saw a gap between what AI could do and what legal tools were doing. The gap was enormous.

The first version was a basic RAG model coded from scratch — just enough to prove the idea worked. By October 2024, Avi switched to an open-source framework for a sturdier base. But both approaches hit the same ceiling: generic tools can't do domain-specific work. Legal research needs legal-aware architecture.

In March 2026, Avi threw away the old code and started fresh. In less than a month:

35,000 judgments. 2.5 million vectors. 7 vector types. 62+ recognized acts. 16+ citation formats. 40 agent nodes. 5 research stages. 22 languages for audio. 2,500 tests.

Neither the basic RAG model nor the open-source framework era was wasted — they were training. Every limitation taught a lesson. Every workaround revealed what the real architecture should look like. And when the time came to build it right, the decisions came fast because the problems were already understood.

All of it started with one question:

*"Why can't legal search understand what I'm actually looking for?"*

Now it can.

---

> **← [Back to Table of Contents](./README.md)**

---

## The Complete Architecture (One Last Look)

```
                          ┌─────────────┐
                          │   USER      │
                          │ (Browser)   │
                          └──────┬──────┘
                                 │
                          ┌──────▼──────┐
                          │  Next.js    │
                          │  Frontend   │
                          │  (32 pages) │
                          └──────┬──────┘
                                 │ REST + SSE
                          ┌──────▼──────┐
                          │  FastAPI    │
                          │  Backend    │
                          │ (68 routes) │
                          └──────┬──────┘
                                 │
         ┌───────────┬───────────┼───────────┬───────────┐
         ▼           ▼           ▼           ▼           ▼
    ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌──────┐
    │PostgreSQL│ │Pinecone │ │  Neo4j  │ │ Gemini  │ │Redis │
    │(metadata│ │(vectors)│ │(graph)  │ │ (AI)    │ │(cache│
    │  + FTS) │ │ 2.5M    │ │ 35K     │ │Pro+Flash│ │queue)│
    │ 35K rows│ │ vectors │ │ nodes   │ │         │ │      │
    └─────────┘ └─────────┘ └─────────┘ └─────────┘ └──────┘
```

---

*This is the story of Smriti. It's not finished. It's just getting started.*

*— Avi, March 2026*
