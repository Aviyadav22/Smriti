# The Smriti Story

### How a law student's frustration became an AI-powered legal research platform

---

This is the story of **Smriti** — told not in technical jargon, but like a journey. Each chapter walks you through what was built, why it was built, and how the pieces connect — from a simple idea to a full production system.

> **"Smriti"** means *memory* in Sanskrit. Because the law is only as powerful as the memory that carries it.

---

## Chapters

| # | Chapter | What You'll Learn |
|---|---------|-------------------|
| 0 | [The Spark](./00-the-spark.md) | How Avi stumbled on the problem and saw the opportunity |
| 1 | [Laying the Foundation](./01-laying-the-foundation.md) | Choosing the tech stack and building the skeleton |
| 2 | [Teaching Smriti to Read](./02-teaching-smriti-to-read.md) | PDF extraction, OCR fallback, and text cleaning |
| 3 | [Understanding What She Reads](./03-understanding-what-she-reads.md) | Metadata extraction — how Smriti figures out *what* a judgment is about |
| 4 | [The Memory Palace](./04-the-memory-palace.md) | Embeddings, vectors, and how Smriti remembers 35,000 judgments |
| 5 | [The Art of Finding](./05-the-art-of-finding.md) | Hybrid search — combining keywords, meaning, and AI reranking |
| 6 | [The Web of Citations](./06-the-web-of-citations.md) | The citation graph — how cases reference each other |
| 7 | [The Research Agent](./07-the-research-agent.md) | The AI lawyer — from V1 to V3, how the agent thinks |
| 8 | [The Face of Smriti](./08-the-face-of-smriti.md) | The frontend — what users actually see and interact with |
| 9 | [Scaling the Mountain](./09-scaling-the-mountain.md) | Batch ingestion, Vertex AI, and going from 100 to 35,000 cases |
| 10 | [The Road Ahead](./10-the-road-ahead.md) | What's next — Hindi support, more courts, and beyond |

---

## How to Read This

- **Start from Chapter 0** if you want the full story
- **Jump to any chapter** if you're curious about a specific part
- Each chapter has **"In the Code"** sections that point you to the actual files
- Written for anyone — law students, developers, investors, or curious minds

---

## The Timeline (at a glance)

```
April 2024     — The idea is born. First version: basic RAG model coded from scratch.
October 2024   — Switched to an open-source framework. Better, but still limited.
Early 2026     — Decision: build from scratch, purpose-built for Indian law.
March 3, 2026  — The rewrite begins. Project scaffold. First lines of code.
March 4        — Database, interfaces, API skeleton.
March 6        — Search works! First semantic results.
March 7        — Judge analytics. Document upload. Audio digests.
March 20       — Research Agent V2 goes live. V3 design begins.
March 22       — V3 complete. 10-step audit fix. Premium UI.
March 23       — Ingestion V3. Multi-vector search. 2,479 tests pass.
March 24       — Vertex AI batch ingestion. 50% cost savings.
March 27       — Security hardening. Production ready.
```

---

*Built by Avi. Powered by curiosity.*
