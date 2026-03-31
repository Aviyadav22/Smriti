# Chapter 0: The Spark

---

One fine day, Avi was sitting in a classroom at UPES, half-listening to a lecture on Natural Language Processing. The professor was explaining how machines could understand the *meaning* of text — not just match keywords, but actually grasp what sentences are *about*.

At the same time, a thought kept nagging him.

He'd watched law students — friends, classmates — struggle with the most fundamental task in legal research: **finding the right precedent**. Not because precedents didn't exist. They did. Thousands of them. Buried in PDFs. Scattered across databases. Hidden behind paywalls.

The tools they had? Keyword search. Type "murder Section 302 IPC" and hope for the best. If the judgment used the word "homicide" instead of "murder," tough luck. If the judge discussed the concept without naming the section? Invisible.

**The problem was clear:**
> Legal research in India was stuck in the keyword era. Students and lawyers were finding cases by *matching words*, not by *understanding law*.

And here was Avi, sitting in an NLP class, learning about embeddings — a way to convert text into numbers that capture *meaning*. Two sentences that say the same thing in different words would be recognized as similar. Not because of shared keywords, but because of shared meaning.

The timing was perfect.

---

## The First Attempt (April 2024)

Avi didn't wait. He started building immediately.

The very first version of Smriti was as raw as it gets — a basic RAG model coded from scratch. Extract text from PDFs, embed it, store it in a vector database, and when someone asks a question, find the closest matching chunks and feed them to an LLM. Simple. Scrappy. And it *kind of* worked.

But "kind of" isn't good enough when you're dealing with law. The basic model had no understanding of legal structure, no way to extract metadata, no citation awareness. It was a proof of concept — enough to confirm the idea had legs, not enough to be useful.

## The Open-Source Detour (October 2024)

By October 2024, Avi decided to level up. Instead of reinventing every wheel, he adopted an open-source software framework to build on top of. It gave him a more solid foundation — better document processing, a proper UI, built-in embedding pipelines.

He customized it for legal research. It worked better than the scratch-built model. But over the next few months, the cracks showed:

- **No legal awareness** — The framework chunked text the same way whether it was a recipe or a Supreme Court judgment. It had no concept of FACTS, ISSUES, RATIO DECIDENDI, or ORDER sections.
- **No citation graph** — Cases cite each other. That's fundamental to law. The framework had no way to represent or search these relationships.
- **No metadata extraction** — Who's the judge? What's the case type? Which acts were discussed? It just saw raw text.
- **No Indian law specificity** — Citation formats (SCC, AIR, INSC), act references (IPC, CrPC, BNS), court hierarchy — none of this was built in.
- **Architectural ceiling** — Every time Avi wanted to add a feature (hybrid search, reranking, agent workflows), he was fighting the existing codebase more than building.

Two versions. Two sets of lessons. By early 2026, the verdict was clear:

> **To build what Smriti needed to be, he had to start from scratch — for real this time.**

Not patch-on-top. Not fork-and-extend. A clean slate — taking every lesson learned from the basic RAG model and the open-source era and building purpose-built architecture for Indian legal research.

In March 2026, the final rewrite began.

---

## The Idea

What if you could take every Supreme Court judgment — all 35,000 of them — and teach a machine to *understand* them? Not just index the words, but grasp the legal concepts, the arguments, the holdings, the citations?

What if a law student could type a question in plain English — or Hindi — and get back not just matching documents, but a *researched memo* with citations, counter-arguments, and confidence scores?

What if, instead of spending hours manually cross-referencing cases, an AI agent could do it in minutes — reading statute text first, breaking down legal elements, searching for supporting and opposing precedents, and then writing a synthesis that a lawyer could actually use?

That was the spark. That was the beginning of **Smriti**.

---

## Why "Smriti"?

In Sanskrit, *Smriti* (स्मृति) means "memory" or "that which is remembered." In Hindu legal tradition, the *Smritis* were ancient texts that codified laws and social conduct — Manusmriti being the most famous.

The name carries a double meaning:
1. **The AI's memory** — it remembers and retrieves from 35,000 judgments
2. **Legal tradition** — connecting to India's oldest tradition of codified law

---

## The Data Goldmine

Before writing a single line of code, Avi needed data. Good data. Legal data.

He found it in an unlikely place: **Amazon Web Services**.

An organization called Dattam Labs had uploaded the entire collection of Indian Supreme Court judgments as an open dataset on AWS S3 — 35,000 PDFs with Parquet metadata, licensed under CC-BY-4.0 (free to use, just give credit).

No login needed. No paywall. No scraping. Just download and go.

```
s3://indian-supreme-court-judgments/
├── judgments/
│   ├── 2024/
│   │   ├── judgment_001.pdf
│   │   ├── judgment_002.pdf
│   │   └── ...
│   ├── 2023/
│   └── ...
└── metadata/
    └── cases_metadata.parquet  (19 fields per case)
```

This was the raw material. 35,000 stories of justice, waiting to be understood.

---

## The Competition

Avi wasn't the first to think about legal AI in India. The landscape had some serious players:

- **Jhana AI** — $1.6M funded, 16 million documents
- **BharatLaw AI** — 1 million+ docs, free tier
- **CaseMine** — CaseIQ feature, established player
- **LegitQuest** — Judge analytics focus

But Avi noticed gaps:
- None of them had a **citation graph** — a map showing how cases connect to each other
- None did **section-aware chunking** — they treated legal text like any other text
- None had a **research agent** that could think through a legal question step by step
- None cared about **DPDP compliance** (India's new data privacy law)

These gaps became Smriti's superpowers.

---

## The Plan

Avi sketched out a phased approach — build in layers, each one adding capability:

1. **Phase 1**: Get the basics right — extract text, store metadata, set up the database
2. **Phase 2**: Make search work — combine keyword search with semantic search
3. **Phase 3**: Add AI chat — ask questions, get answers grounded in real cases
4. **Phase 4**: Judge analytics — understand how different judges rule
5. **Phase 5**: Document upload — let users analyze their own PDFs
6. **Phase 6**: The research agent — the big one, an AI that researches like a lawyer
7. **Phase 7-9**: Quality, security, scalability — make it production-ready

No shortcuts. No "move fast and break things." Legal research demands accuracy. When a lawyer cites a case that doesn't exist, real people suffer real consequences.

---

> **Next: [Chapter 1 — Laying the Foundation →](./01-laying-the-foundation.md)**
>
> *Where Avi picks his weapons — FastAPI, Next.js, Pinecone, Neo4j — and writes the first lines of code.*

---

### In the Code

| What | Where |
|------|-------|
| Project scaffold | First commit: `acc5317` (March 3, 2026) |
| Phase plan | [docs/PHASE_PLAN.md](../PHASE_PLAN.md) |
| Architecture decisions | [docs/DECISIONS.md](../DECISIONS.md) |
| Data source details | [docs/DATA_SOURCES.md](../DATA_SOURCES.md) |
| Competitive analysis | [docs/STRATEGY.md](../STRATEGY.md) |
