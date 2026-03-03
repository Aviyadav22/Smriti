# Smriti -- Product Requirements Document

**Version:** 1.0
**Last Updated:** 2026-03-02
**Status:** Draft
**Product:** Smriti -- AI-Powered Indian Legal Research Platform

---

## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [Market Opportunity](#2-market-opportunity)
3. [Target Users](#3-target-users)
4. [Core Features](#4-core-features)
5. [Indian-Specific Requirements](#5-indian-specific-requirements)
6. [Out of Scope (MVP)](#6-out-of-scope-mvp)
7. [Non-Functional Requirements](#7-non-functional-requirements)
8. [Success Metrics](#8-success-metrics)
9. [Appendix](#9-appendix)

---

## 1. Problem Statement

### 1.1 The Current State of Indian Legal Research

Indian lawyers spend **3 to 5 hours daily** on legal research -- locating precedents, reading lengthy judgments, tracing citation chains, and mapping statutory changes. This is time billed to clients or absorbed as overhead, and it relies on tools and workflows that have not meaningfully changed in two decades.

### 1.2 Shortcomings of Existing Tools

| Tool | Strength | Critical Weakness |
|------|----------|-------------------|
| **IndianKanoon** | Free, large corpus | Keyword-only search, no AI analysis, cluttered UI, no citation graph |
| **SCC Online** | Authoritative database, editorial notes | Expensive (INR 30,000+/year), keyword search with limited Boolean, no semantic understanding |
| **Manupatra** | Statute tracking, notifications | Legacy interface, slow search, no AI features |
| **CaseMine** | Some AI features (CaseIQ) | Limited Indian law depth, expensive, citation analysis is shallow |

**No existing tool combines** semantic search, citation network analysis, and AI-powered judgment analysis purpose-built for Indian law.

### 1.3 The New Criminal Laws Crisis

On **1 July 2024**, three new criminal statutes replaced the colonial-era criminal code framework:

| Old Law | New Law | Scope |
|---------|---------|-------|
| Indian Penal Code, 1860 (IPC) | Bharatiya Nyaya Sanhita, 2023 (BNS) | Substantive criminal law |
| Code of Criminal Procedure, 1973 (CrPC) | Bharatiya Nagarik Suraksha Sanhita, 2023 (BNSS) | Criminal procedure |
| Indian Evidence Act, 1872 | Bharatiya Sakshya Adhiniyam, 2023 (BSA) | Law of evidence |

This transition has created widespread confusion:
- Decades of precedent reference IPC/CrPC/Evidence Act sections that now have new numbering.
- Lawyers must map between old and new section numbers daily.
- Courts are simultaneously hearing cases under both regimes (pre-July 2024 offenses under old law, post-July 2024 under new).
- No existing tool provides automatic old-to-new section mapping with relevant precedent linkage.

### 1.4 The Core Problem (One Sentence)

Indian lawyers lack an intelligent research tool that understands legal semantics, tracks precedent relationships, maps statutory transitions, and provides AI-grounded analysis -- all within the context of the Indian legal system.

---

## 2. Market Opportunity

### 2.1 Market Size

- **1.7 million** registered advocates with the Bar Council of India (2024)
- **~70,000** law firms operating in India
- **~1,500** law schools producing **~100,000** graduates annually
- Indian legal services market estimated at **~$35 billion** (2025), growing at 8-10% CAGR
- Corporate legal spend in India growing at **15%+ CAGR** driven by regulatory complexity

### 2.2 Addressable Segments

| Segment | Size | Willingness to Pay | Priority |
|---------|------|---------------------|----------|
| Tier 1 city litigation lawyers | ~200,000 | High (INR 500-2,000/month) | P0 |
| Corporate law firms (5-50 lawyers) | ~5,000 firms | Very high (INR 5,000-50,000/month/firm) | P0 |
| In-house legal counsel | ~50,000 | High (enterprise pricing) | P1 |
| Tier 2/3 city lawyers | ~500,000 | Medium (INR 200-500/month) | P1 |
| Law students | ~500,000 active | Low (freemium) | P2 |

### 2.3 Competitive Moat

- **Indian-law-first** semantic model trained/fine-tuned on Indian judgments, statutes, and legal terminology
- **Citation graph** built specifically for Indian citation formats (SCC, AIR, SCR, INSC, etc.)
- **Old-to-new law mapping** as a unique feature during the BNS/BNSS/BSA transition window
- **Structured judgment parsing** extracting ratio decidendi, obiter dicta, and holding from Indian judgment formats

---

## 3. Target Users

### 3.1 Primary Persona: Litigation Lawyer (Tier 1/2 City)

**Name:** Advocate Priya Sharma
**Location:** Delhi
**Experience:** 8 years at the bar
**Practice:** Criminal and constitutional law

**Daily workflow:**
1. Receives brief or client instructions
2. Identifies legal issues and relevant statutory provisions
3. Searches for Supreme Court and Delhi High Court precedents
4. Reads 5-15 judgments (often 50-100 pages each)
5. Extracts ratio decidendi and distinguishes unfavorable cases
6. Drafts arguments with citations

**Pain points:**
- Spends 3+ hours daily just searching and reading judgments
- Keyword search on SCC Online misses semantically relevant cases
- Manually traces citation chains ("which cases cited this landmark judgment?")
- Struggles with IPC-to-BNS section mapping
- No way to get a quick summary of a 200-page judgment before reading it

**What she wants from Smriti:**
- "Find me all Supreme Court cases where Section 302 IPC / Section 103 BNS was applied in circumstantial evidence cases in the last 5 years"
- "Show me which cases have overruled or distinguished *Sharad Birdhichand Sarda v. State of Maharashtra*"
- "Summarize the ratio decidendi of this 150-page judgment in 5 bullet points"
- "Which High Courts have interpreted Section 138 NI Act differently from the Supreme Court?"

### 3.2 Secondary Persona: Law Firm Associate

**Name:** Arjun Mehta
**Location:** Mumbai
**Experience:** 3 years, mid-size corporate law firm (25 lawyers)

**Context:** Works on commercial disputes, arbitration, and corporate advisory. Needs to research quickly to meet partner deadlines.

**Pain points:**
- Partners expect research memos within hours
- Needs to cover multiple jurisdictions (Bombay HC, Delhi HC, Supreme Court)
- Must track how a legal principle has evolved across decades
- Firm pays for SCC Online but the search is still keyword-based

### 3.3 Tertiary Persona: In-House Legal Counsel

**Name:** Kavita Reddy
**Location:** Bangalore
**Role:** Senior Legal Counsel, fintech company

**Context:** Handles regulatory compliance, litigation oversight, and contract review. Needs quick answers to legal questions without engaging external counsel for every query.

**Pain points:**
- Not a full-time researcher but needs accurate legal positions quickly
- Needs to understand regulatory landscape (RBI, SEBI, IT Act implications)
- Cannot afford to miss recent regulatory changes or landmark judgments

### 3.4 Tertiary Persona: Law Student / Researcher

**Name:** Rohan Iyer
**Location:** Pune
**Context:** 4th year NLU student, preparing for moot courts and writing research papers

**Pain points:**
- Free tools (IndianKanoon) have poor search quality
- Cannot afford SCC Online subscription
- Needs citation chains for research papers
- Wants to understand how a legal principle developed across cases

---

## 4. Core Features

### 4.1 Hybrid Legal Search

**Description:**
A search engine that combines semantic understanding (vector similarity), keyword matching (BM25/full-text), and structured metadata filtering to deliver highly relevant Indian legal case results. The system understands legal concepts, not just keywords -- a search for "right to privacy as fundamental right" should surface *K.S. Puttaswamy v. Union of India* even if those exact words do not appear prominently in the judgment text.

**User Story:**
> As a litigation lawyer, I want to search for cases using natural language queries, specific citations, statute sections, or any combination thereof, so that I can find relevant precedents in under 30 seconds instead of browsing through hundreds of keyword results.

**Acceptance Criteria:**

| ID | Criterion | Priority |
|----|-----------|----------|
| HS-1 | User can enter a free-text query (natural language, case name, citation, or statute reference) in a single search bar | P0 |
| HS-2 | System returns results ranked by a composite relevance score combining semantic similarity and keyword match | P0 |
| HS-3 | Each result displays: case title, citation(s), court, year, 2-3 line contextual snippet with highlighted matches, relevance score | P0 |
| HS-4 | User can apply faceted filters: court (multi-select), year range (slider or input), case type (civil/criminal/constitutional/writ/arbitration), bench type (single/division/full/constitution bench), jurisdiction (state) | P0 |
| HS-5 | System recognizes and resolves Indian citation formats: if user types "(2017) 10 SCC 1" the system returns that exact case | P0 |
| HS-6 | System recognizes statute references: searching "Section 302 IPC" also surfaces results for "Section 103 BNS" (with toggle for old/new law mapping) | P1 |
| HS-7 | Search supports Boolean operators (AND, OR, NOT) for power users | P1 |
| HS-8 | Search auto-suggests case names, statute sections, and common legal phrases as user types | P1 |
| HS-9 | Response time for search results is under 2 seconds (p95) for the first page of results | P0 |
| HS-10 | Pagination: results load in pages of 20, with infinite scroll or explicit pagination | P0 |
| HS-11 | User can sort results by: relevance (default), date (newest/oldest), citation count (most cited) | P1 |
| HS-12 | Empty state: when no results found, system suggests alternative queries or broader filters | P2 |

**Technical Notes:**
- Vector search via embeddings (legal-domain fine-tuned model or high-quality general model with Indian legal corpus)
- Keyword search via Elasticsearch/OpenSearch BM25
- Hybrid ranking: weighted combination of vector score and BM25 score, tunable per query type
- Metadata stored in structured fields for fast filtering (court, year, case_type, bench_type, jurisdiction, statutes_cited)

---

### 4.2 Case Viewer

**Description:**
A structured, readable display of individual judgments that breaks down the often 50-200 page Indian judgment format into navigable sections. Combines the original PDF with AI-parsed structured data and rich metadata.

**User Story:**
> As a lawyer, I want to view a judgment with its key sections (facts, arguments, ratio, order) clearly separated and its metadata (citation, court, judges, statutes) displayed alongside, so that I can understand the essence of the case without reading the entire document.

**Acceptance Criteria:**

| ID | Criterion | Priority |
|----|-----------|----------|
| CV-1 | Full judgment text displayed in a readable, paginated format with font size controls | P0 |
| CV-2 | Original PDF available for download and in-browser viewing | P0 |
| CV-3 | AI-parsed sections displayed as navigable tabs or anchored sections: Facts, Issues, Petitioner Arguments, Respondent Arguments, Court Analysis, Ratio Decidendi, Order/Disposition | P0 |
| CV-4 | Metadata sidebar showing: case title, all known citations, court, bench (judge names), date of judgment, date of hearing, parties (petitioner/respondent with advocates), statutes cited with section numbers, subject/topic tags | P0 |
| CV-5 | "Cited Cases" panel listing all cases referenced in the judgment, each clickable to navigate to that case in Smriti | P0 |
| CV-6 | "Cited By" panel listing all cases in the database that cite this judgment, with count | P0 |
| CV-7 | AI-generated summary (3-5 bullet points covering facts, issue, holding) displayed at the top | P1 |
| CV-8 | Highlight and annotate functionality: user can highlight text and add personal notes (saved to user account) | P2 |
| CV-9 | Copy citation in multiple formats (SCC, AIR, neutral citation) with one click | P1 |
| CV-10 | Section-wise deep linking: user can share a URL that opens the judgment at a specific section | P2 |
| CV-11 | Statute section references in judgment text are hyperlinked to the relevant Bare Act section | P1 |

**Technical Notes:**
- Judgment parsing via NLP pipeline: section detection, entity extraction (judge names, party names, statute references)
- PDF rendering via PDF.js or equivalent
- Parsed sections stored in database for fast retrieval; original PDF stored in object storage (S3/equivalent)
- AI summary generated at ingestion time and cached

---

### 4.3 Citation Graph

**Description:**
An interactive network visualization showing how cases cite, overrule, affirm, and distinguish each other. This is the legal equivalent of Google's PageRank -- the more a case is cited, the more authoritative it is. The graph allows lawyers to trace precedent chains, discover landmark cases, and identify when a precedent has been weakened or overruled.

**User Story:**
> As a lawyer, I want to see a visual graph of how a case relates to other cases through citations, so that I can quickly assess its authority, find related precedents, and ensure it has not been overruled.

**Acceptance Criteria:**

| ID | Criterion | Priority |
|----|-----------|----------|
| CG-1 | From any case page, user can open a citation graph centered on that case | P0 |
| CG-2 | Graph displays nodes (cases) and directed edges (citation relationships) | P0 |
| CG-3 | Edge types are visually distinct: **cites** (neutral, gray), **affirms/follows** (green), **distinguishes** (yellow/orange), **overrules** (red) | P0 |
| CG-4 | Node size proportional to "cited by" count (authority indicator) | P1 |
| CG-5 | User can expand any node to load its citations (lazy loading for performance) | P0 |
| CG-6 | User can filter graph by: edge type, court level, year range | P1 |
| CG-7 | Clicking a node shows a tooltip with: case name, citation, year, court, cited-by count | P0 |
| CG-8 | Double-clicking a node navigates to that case's full viewer page | P0 |
| CG-9 | "Citation chain" feature: user selects two cases and the system shows the shortest citation path between them | P2 |
| CG-10 | "Authority timeline" view: chronological display of how a legal principle was cited/modified over time | P2 |
| CG-11 | Export graph as PNG or SVG | P2 |
| CG-12 | Graph is responsive and handles up to 200 visible nodes without significant lag | P1 |

**Technical Notes:**
- Graph stored in a graph database (Neo4j) or as adjacency lists in the primary database
- Frontend graph rendering via D3.js, Cytoscape.js, or vis.js
- Citation relationship extraction is an NLP pipeline task: parse judgment text to identify cited cases and classify the relationship type
- For MVP, relationship classification can be simplified to "cites" and "overrules" only, with "affirms" and "distinguishes" added in v2

---

### 4.4 RAG Chat (AI Research Assistant)

**Description:**
A conversational AI assistant that answers legal research questions grounded in actual Indian judgments and statutes. Every factual claim in the response is backed by a citation to a specific case or statutory provision. The system uses Retrieval-Augmented Generation (RAG) to fetch relevant documents before generating a response, ensuring factual accuracy and eliminating hallucination of non-existent cases.

**User Story:**
> As a lawyer, I want to ask legal research questions in natural language and get accurate, well-cited answers referencing real judgments, so that I can get preliminary research done in minutes instead of hours.

**Acceptance Criteria:**

| ID | Criterion | Priority |
|----|-----------|----------|
| RC-1 | User can type a legal question in natural language in a chat interface | P0 |
| RC-2 | System retrieves relevant judgments/statutes from the database before generating a response | P0 |
| RC-3 | Response streams token-by-token for perceived performance (SSE or WebSocket) | P0 |
| RC-4 | Every factual claim in the response includes an inline citation linking to the source judgment or statute section | P0 |
| RC-5 | Citations in the response are clickable and navigate to the case viewer or bare act section | P0 |
| RC-6 | Response includes a "Sources" section at the bottom listing all referenced judgments with their citations | P0 |
| RC-7 | If the system cannot find relevant sources, it explicitly states "I could not find relevant cases for this query" instead of generating unsourced content | P0 |
| RC-8 | Chat history is persisted per session; user can view and continue previous sessions | P1 |
| RC-9 | User can start a new chat session at any time | P0 |
| RC-10 | User can provide context for the chat: "I am arguing for the petitioner in a bail application under Section 439 CrPC / Section 483 BNSS" | P1 |
| RC-11 | System understands follow-up questions within the same session (conversational context) | P1 |
| RC-12 | Response latency: first token within 3 seconds, complete response within 30 seconds for typical queries | P0 |
| RC-13 | System can handle comparative questions: "How does the Bombay HC and Delhi HC differ on Section 138 NI Act?" | P1 |
| RC-14 | Rate limiting: reasonable usage limits per user tier to manage LLM costs | P0 |

**Technical Notes:**
- RAG pipeline: query embedding -> vector search -> top-K document retrieval -> LLM generation with retrieved context
- LLM: GPT-4 / Claude / open-source legal-tuned model (configurable)
- Citation verification: post-generation check that every cited case actually exists in the database
- Chunk strategy: judgments split into overlapping chunks (~500-1000 tokens) with section metadata preserved
- Embedding model: must handle Indian legal text well (test against legal benchmarks)

---

### 4.5 Document Upload

**Description:**
Allows users to upload their own PDF judgments or legal documents for personal research. Uploaded documents go through the same processing pipeline as the main corpus -- metadata extraction, section parsing, embedding generation -- and become searchable within the user's personal collection.

**User Story:**
> As a lawyer, I want to upload PDF judgments that I have collected or received from colleagues, so that I can search across my personal collection alongside the main database.

**Acceptance Criteria:**

| ID | Criterion | Priority |
|----|-----------|----------|
| DU-1 | User can upload PDF files (single or batch, up to 10 files at once) | P0 |
| DU-2 | Maximum file size: 50 MB per file | P0 |
| DU-3 | System extracts text from PDF (OCR for scanned documents) | P0 |
| DU-4 | System automatically extracts metadata: case title, citation, court, date, judge names, parties, statutes cited | P1 |
| DU-5 | User can review and correct extracted metadata before finalizing | P1 |
| DU-6 | Processing status is visible: uploaded, processing, ready, failed | P0 |
| DU-7 | Uploaded documents appear in search results (marked as "Personal Collection") | P0 |
| DU-8 | User can organize uploads into folders/collections | P2 |
| DU-9 | Uploaded documents are private to the user who uploaded them | P0 |
| DU-10 | Duplicate detection: system warns if an uploaded document already exists in the main corpus | P2 |
| DU-11 | Processing time: under 5 minutes for a typical 50-page judgment | P1 |

**Technical Notes:**
- PDF text extraction: PyMuPDF (fitz) for text-based PDFs, Tesseract OCR for scanned documents
- Metadata extraction: NLP pipeline with regex patterns for citations, NER for parties and judges
- Embeddings generated and stored in user-scoped vector namespace
- Storage: original PDF in object storage, extracted text and metadata in database

---

## 5. Indian-Specific Requirements

These requirements are non-negotiable for the product to be useful to Indian legal professionals. They differentiate Smriti from any generic legal AI tool.

### 5.1 Citation Format Support

The system MUST recognize, parse, and normalize all major Indian citation formats:

| Format | Pattern | Example | Priority |
|--------|---------|---------|----------|
| SCC | (Year) Volume SCC Page | (2017) 10 SCC 1 | P0 |
| AIR | AIR Year Court Page | AIR 2023 SC 100 | P0 |
| SCR | Year Volume SCR Page | 2023 2 SCR 100 | P0 |
| INSC (neutral) | Year INSC Number | 2023 INSC 1 | P0 |
| SCC Online | Year SCC OnLine Court Number | 2023 SCC OnLine SC 1234 | P0 |
| Criminal Law Journal | Year CrLJ Page | 2023 CrLJ 100 | P1 |
| Scale | Year Volume SCALE Page | 2023 1 SCALE 100 | P2 |
| High Court reporters | Varies by court | 2023 BomLR 100, (2023) 2 Cal WN 50 | P1 |

Each case may have **multiple citation formats** (e.g., the same judgment cited as SCC, AIR, and INSC). The system must treat these as aliases for the same case and merge them.

### 5.2 Court Hierarchy Awareness

The system must encode and use the Indian court hierarchy:

```
Authority Level 1: Supreme Court of India
Authority Level 2: High Courts (25)
Authority Level 3: District & Sessions Courts
Authority Level 4: Tribunals (NCLT, NCLAT, SAT, CAT, ITAT, NGT, etc.)
Authority Level 5: Quasi-judicial bodies
```

**Usage in product:**
- Search results should indicate court level
- Citation graph should visually distinguish authority levels
- RAG chat should weight Supreme Court holdings higher than High Court holdings when they conflict
- When a High Court judgment contradicts a Supreme Court judgment on the same point, the system should flag this

### 5.3 Bare Acts and Statutory Mapping

**Old Law to New Law Mapping (Critical for 2024-2027 transition period):**

| Old Statute | New Statute | Section Count | Mapping Complexity |
|-------------|-------------|---------------|-------------------|
| IPC 1860 (511 sections) | BNS 2023 (358 sections) | Many-to-many | High -- sections merged, split, renumbered |
| CrPC 1973 (484 sections) | BNSS 2023 (531 sections) | Many-to-many | High |
| Evidence Act 1872 (167 sections) | BSA 2023 (170 sections) | Mostly 1:1 | Medium |

**Requirements:**
- Maintain a complete section-mapping table between old and new laws
- When user searches for an old section (e.g., "Section 302 IPC"), also show results for the corresponding new section (Section 103 BNS) and vice versa
- Display both old and new section numbers in case metadata
- Bare Act browser: user can browse any major statute section by section with the full text

**Key Bare Acts to support (v1):**
- Constitution of India (all 470 articles)
- BNS 2023 / IPC 1860
- BNSS 2023 / CrPC 1973
- BSA 2023 / Evidence Act 1872
- CPC 1908 (with Orders and Rules)
- Companies Act 2013
- Arbitration and Conciliation Act 1996
- Negotiable Instruments Act 1881 (especially Section 138)
- Information Technology Act 2000
- Consumer Protection Act 2019
- SEBI Act 1992
- Insolvency and Bankruptcy Code 2016
- Right to Information Act 2005
- Prevention of Corruption Act 1988

### 5.4 Indian Legal Terminology

The system (especially RAG chat) must understand and correctly use Indian legal terminology:

- **Procedural terms:** FIR, Chargesheet, Bail (regular/anticipatory/default/interim), Vakalatnama, Challan, Remand (judicial/police custody), Cognizance, Committal
- **Court terms:** Bench (single/division/full/constitution), Roster, Cause list, Mentioning, Adjournment, Reserved for judgment
- **Writs:** Habeas Corpus, Mandamus, Certiorari, Prohibition, Quo Warranto (Article 32 for SC, Article 226 for HCs)
- **Case types:** Writ Petition (Civil/Criminal), Special Leave Petition (SLP), Criminal Appeal, Civil Appeal, Transfer Petition, Original Suit, Review Petition, Curative Petition
- **Roles:** Senior Advocate, Advocate, Advocate on Record (AoR), Amicus Curiae, Solicitor General, Attorney General, Additional Solicitor General, Public Prosecutor, Standing Counsel
- **Identifiers:** CNR (Case Number Register) number format: `XXHCYY-NNNNNN-YYYY` (state code + district code + serial + year)

### 5.5 Language Support (v1)

- **Search and AI:** English only in v1
- **Display:** Judgments in Hindi and regional languages must be displayable (UTF-8 support for Devanagari, Tamil, Telugu, Kannada, Bengali, Gujarati, Malayalam, Marathi, Odia, Punjabi scripts)
- **Metadata:** All metadata fields stored in English; original language preserved where available
- **Future:** Multi-language search is a v2 feature requiring translation pipeline

---

## 6. Out of Scope (MVP)

The following features are explicitly excluded from the MVP (v1) release to maintain focus:

| Feature | Reason for Exclusion | Planned Version |
|---------|---------------------|-----------------|
| Multi-language search | Requires translation pipeline and multilingual embeddings | v2 |
| Contract review / drafting | Different product category (document AI vs. research) | v3 or separate product |
| Court date tracking / calendar | Integration with e-courts required | v2 |
| Billing and time tracking | Practice management, not research | Out of scope |
| Native mobile app (iOS/Android) | Web responsive is sufficient for v1 | v2 |
| Multi-tenant firm management | Requires org-level permissions, SSO, admin panel | v2 |
| Automated web scraping of court websites | Legal and technical complexity; rely on bulk data sources for v1 | v2 |
| Browser extension | Chrome/Edge extension for research on any page | v2 |
| Legal news / alerts | "Alert me when a new case cites X" | v2 |
| E-filing integration | Integration with e-courts filing system | Out of scope |
| Comparison of judgments | Side-by-side diff view of similar judgments | v2 |
| API for third-party developers | Public API for integration with other legal tools | v2 |

---

## 7. Non-Functional Requirements

### 7.1 Performance

| Metric | Target | Measurement |
|--------|--------|-------------|
| Search response time (p50) | < 1 second | Time from query submission to first result rendered |
| Search response time (p95) | < 2 seconds | Time from query submission to first result rendered |
| Case viewer load time | < 3 seconds | Time from click to full page rendered (text; PDF may lazy-load) |
| RAG chat first token | < 3 seconds | Time from question submission to first token streamed |
| RAG chat complete response | < 30 seconds | Time from question to full response rendered |
| Document upload processing | < 5 minutes | Time from upload to document being searchable |
| Concurrent users | 500+ simultaneous | Without performance degradation |

### 7.2 Reliability

- **Uptime:** 99.5% monthly (allows ~3.6 hours downtime/month)
- **Data durability:** 99.99% (no loss of ingested judgments or user data)
- **Backup:** Daily automated backups with 30-day retention
- **Disaster recovery:** RPO < 1 hour, RTO < 4 hours

### 7.3 Security

- **Authentication:** Email/password with bcrypt hashing; Google OAuth as alternative
- **Authorization:** Role-based (free user, paid user, admin)
- **Data isolation:** User uploads and chat history are private; no cross-user data leakage
- **Encryption:** TLS 1.2+ in transit; AES-256 at rest for user data
- **Compliance:** Indian IT Act 2000, IT Rules 2011, Digital Personal Data Protection Act 2023

### 7.4 Scalability

- **Corpus size:** System must handle 1 million+ judgments at launch, scaling to 5 million+
- **Vector store:** Must support 10 million+ vectors (multiple chunks per judgment)
- **User base:** Architecture must support 100,000+ registered users
- **Storage:** 5 TB+ for PDFs, 500 GB+ for structured data, 200 GB+ for vector indices

### 7.5 Usability

- **Responsive design:** Works on desktop (primary), tablet, and mobile browsers
- **Browser support:** Chrome 90+, Firefox 90+, Safari 15+, Edge 90+
- **Accessibility:** WCAG 2.1 AA compliance
- **Onboarding:** New user should complete first successful search within 60 seconds of signing up

---

## 8. Success Metrics

### 8.1 Search Quality Metrics

| Metric | Target | Measurement Method |
|--------|--------|--------------------|
| Citation query recall@5 | > 80% | Given a citation, the correct case appears in top 5 results |
| Topic query recall@5 | > 70% | Given a legal topic query, relevant cases appear in top 5 results |
| Search precision@10 | > 60% | At least 6 of top 10 results are relevant to the query |
| Mean Reciprocal Rank (MRR) | > 0.5 | Average of 1/rank of first relevant result |
| Statute mapping accuracy | > 95% | Old section correctly mapped to new section |

### 8.2 RAG Chat Quality Metrics

| Metric | Target | Measurement Method |
|--------|--------|--------------------|
| Citation accuracy | 100% | Every cited case must actually exist in the database |
| Grounding rate | > 95% | Percentage of factual claims backed by a source citation |
| Answer relevance | > 80% | Human evaluation: does the answer address the question? |
| Hallucination rate | 0% | No fabricated case names, citations, or legal principles |

### 8.3 User Engagement Metrics

| Metric | Target | Measurement Method |
|--------|--------|--------------------|
| Time to find relevant precedent | < 30 seconds | Measured from search query to user clicking a relevant result |
| Ratio decidendi identification | Without reading full judgment | User can identify holding via AI-parsed sections or summary |
| Daily active users / Monthly active users | > 30% | DAU/MAU ratio |
| Searches per session | > 5 | Average searches per user session |
| Chat questions per session | > 3 | Average chat interactions per session |
| User retention (Week 1) | > 40% | Users returning within 7 days of signup |
| NPS | > 40 | Quarterly survey |

### 8.4 Business Metrics

| Metric | Target (Month 6) | Target (Month 12) |
|--------|-------------------|---------------------|
| Registered users | 5,000 | 25,000 |
| Paying users | 500 | 3,000 |
| Monthly recurring revenue | INR 5,00,000 | INR 30,00,000 |
| Corpus size (judgments) | 1,000,000 | 2,500,000 |
| Average revenue per user | INR 1,000/month | INR 1,000/month |

---

## 9. Appendix

### 9.1 Glossary

| Term | Definition |
|------|-----------|
| BNS | Bharatiya Nyaya Sanhita 2023, the new substantive criminal law replacing IPC |
| BNSS | Bharatiya Nagarik Suraksha Sanhita 2023, the new criminal procedure replacing CrPC |
| BSA | Bharatiya Sakshya Adhiniyam 2023, the new evidence law replacing the Indian Evidence Act |
| Ratio decidendi | The legal principle or rule that forms the basis of the court's decision; binding on lower courts |
| Obiter dicta | Incidental remarks by the court that are not binding but may be persuasive |
| RAG | Retrieval-Augmented Generation, an AI technique that retrieves relevant documents before generating a response |
| SCC | Supreme Court Cases, the primary law reporter for Supreme Court of India judgments |
| AIR | All India Reporter, another major law reporter |
| CNR | Case Number Register, a unique identifier for cases in the Indian e-courts system |
| Hybrid search | Combination of semantic (vector) search and keyword (BM25) search for improved retrieval |

### 9.2 References

- Bar Council of India advocate enrollment statistics
- Supreme Court of India: e-SCR portal (https://e-scr.icloud.nic.in)
- Gazette notifications for BNS, BNSS, BSA (Ministry of Law and Justice)
- SCC Online (https://www.scconline.com)
- Indian Kanoon (https://indiankanoon.org)
- e-Courts Services (https://ecourts.gov.in)

### 9.3 Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-03-02 | Smriti Product Team | Initial PRD |
