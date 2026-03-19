# RESEARCH AGENT V2 — IMPLEMENTATION BIBLE

> **Purpose**: Complete reference for building the orchestrated multi-agent legal research system.
> **Optimized for**: Claude Opus — contains full context to execute any phase cold.
> **Date**: 2026-03-19 | **Project**: Smriti (d:\Startup\Smriti)
> **Version**: 2.2 — Added CRAG, Contextual Embeddings, GraphRAG, Speculative RAG, MA-RAG CoT, Speed Optimizations (S1-S9)

---

## TABLE OF CONTENTS
0. [Competitive Intelligence](#0-competitive-intelligence)
1. [Vision & Goals](#1-vision--goals)
2. [Current Architecture (What Exists)](#2-current-architecture-what-exists)
3. [Target Architecture (What We're Building)](#3-target-architecture-what-were-building)
4. [Data Architecture](#4-data-architecture)
5. [Phase 1: Core Orchestration](#5-phase-1-core-orchestration)
6. [Phase 2: Statute/Constitution Ingestion + Data Expansion](#6-phase-2-statuteconstitution-ingestion--data-expansion)
7. [Phase 3: Multi-Source Workers + Indian Kanoon + Web Search](#7-phase-3-multi-source-workers--indian-kanoon--web-search)
8. [Phase 4: Structured Footnotes & Output Quality](#8-phase-4-structured-footnotes--output-quality)
9. [Phase 5: Polish & Production Hardening](#9-phase-5-polish--production-hardening)
10. [Key Design Decisions](#10-key-design-decisions)
11. [Existing Code Reference (Exact Signatures)](#11-existing-code-reference)
12. [Output Format Specification](#12-output-format-specification)
13. [Verification Plan](#13-verification-plan)
14. [Appendix: Research References](#14-appendix-research-references)

---

## 0. COMPETITIVE INTELLIGENCE

### 0.1 Reverse-Engineered Competitor Workflow

We analyzed a production legal AI competitor (likely Jhana AI tier) processing this query:
> "Prepare a list of judgments with relevant case laws on whether a place of infringement can be the sole criteria for instituting suit under Section 20(c) CPC..."

**Their visible pipeline (9 searches total):**

```
USER QUERY
  → PLAN (LLM generates detailed research strategy, names specific landmark cases)
  → 6x JUDG searches (each with DUAL queries: natural language + structured boolean)
  → 1x ACTS search (separate statute index, filtered by act/state)
  → 1x WEB search (Indian Kanoon, 8 results)
  → 1x FETCH (actual document from indiankanoon.org, 0-30% of text)
  → SYNTHESIS (structured table + analytical memo + numbered footnotes)
```

### 0.2 Key Techniques Decoded

| Technique | How They Do It | Our Equivalent |
|-----------|---------------|----------------|
| **Dual-query per search** | NL query (vector) + boolean query (BM25) per intent | We send same query to both — gap |
| **Named case retrieval** | Plan step names landmark cases by name from LLM knowledge | Our decompose generates generic sub-queries — gap |
| **4/file diversity** | Max 4 chunks per judgment prevents result domination | We keep best chunk per case — needs enhancement |
| **Separate ACTS search** | Dedicated statute index with act/section/state filters | No statute DB yet — Phase 2 |
| **WEB + FETCH fallback** | Web search for cases not in DB, then fetch full text | No external fetch — Phase 3 |
| **Verbatim extraction** | Quote actual judgment text, not LLM-synthesized | We synthesize ratio — gap |
| **51 footnotes (15 used, 36 unused)** | Shows full research audit trail | No audit trail — Phase 4 |
| **Source document links** | Footnotes link to Indian Kanoon URLs / internal viewer | No clickable links — Phase 4 |

### 0.3 Their Output Structure (What Lawyers Love)

1. **Executive Summary** — 3 bullet points with inline citations, answer-first
2. **Case Law Table** — 10 rows: Citation | Court | Issue | Key Extract (VERBATIM) | Holding
3. **Analytical Synthesis** — Sub-sections:
   - A. Two-tier table (Natural Persons vs Corporations) with authority references
   - B. Conjunctive vs Disjunctive analysis with quoted extracts
   - C. Reconciliation table mapping 5 fact-pattern scenarios → outcomes
4. **Conclusion** — 3 numbered points with "practical effect"
5. **Footnotes** — Numbered [1]-[51], each linking to actual judgment PDF/web page

### 0.4 Where We're STRONGER (Double Down)

| Our Advantage | They Lack |
|--------------|-----------|
| **Neo4j citation graph** — overruled/followed/distinguished chains | No citation graph visible |
| **Precedent strength** (BINDING/PERSUASIVE/DISTINGUISHABLE/OVERRULED) | All cases treated equally |
| **HITL checkpoints** — lawyer stays in control, can steer research | Fully autonomous |
| **Iterative gap analysis** (FAIR-RAG, max 2 rounds) | Fixed 9 searches, no adaptation |
| **Contradiction detection** — systematic conflict analysis | No systematic contradictions |
| **Overruled case flagging** with treatment warnings | No treatment warnings |
| **Confidence scoring** with component breakdown | No confidence indicators |
| **Hindi support** | English only |
| **GraphRAG community detection** — macro-level legal landscape summaries | No community detection |
| **Research process visualization** — live SSE showing every search step | No process transparency |
| **Zero-tolerance citation guardrail** — every citation verified against primary sources | No systematic verification |
| **Complete IPC↔BNS code mapping** — auto-search old AND new codes | No old↔new code awareness |

### 0.5 Where We Must Close Gaps (Critical)

| Gap | Severity | Fix |
|-----|----------|-----|
| **Data scale** (35K SC vs millions) | CRITICAL | AWS HC dataset (free) + Indian Kanoon API |
| **No external document fetch** | HIGH | Indian Kanoon API + Tavily |
| **No dual NL+boolean queries** | HIGH | Modify plan_research schema |
| **No named case retrieval** | HIGH | Leverage LLM knowledge in planning |
| **Synthesis-only output** (no verbatim quotes) | HIGH | Increase context, add extraction step |
| **No per-doc diversity** (4/file equivalent) | MEDIUM | Add chunks_per_case parameter |
| **No clickable source links** | MEDIUM | Map case_id → viewer URL + IK URLs |
| **No conditioned retrieval** (round 2 doesn't build on round 1 findings) | HIGH | MC-RAG: pass round 1 results as context to gap_analysis — Phase 1 |
| **No research reflection** (plan-then-execute, no mid-research pivots) | HIGH | Deep Research-style reflection in batch_worker_cot — Phase 1 |
| **No legal reasoning verification** (citation check only, not logic check) | HIGH | LeMAJ-inspired quality check node — Phase 4 |
| **No fake citation guardrail** (SC flagged this Feb 2026) | CRITICAL | Zero-tolerance: verify every citation against PG/IK/Neo4j — Phase 4 |
| **Incomplete old↔new code mapping** (28 mappings, need full tables) | HIGH | Complete IPC→BNS, CrPC→BNSS, IEA→BSA — Phase 2 |
| **No RAPTOR-style section summaries** (chunks lose macro context) | MEDIUM | Hierarchical summaries during ingestion — Phase 2 |

---

## 1. VISION & GOALS

The current research agent is a **linear pipeline** — classify → decompose → search → gather → synthesize. It searches a single Pinecone index + PostgreSQL FTS table, has no web search, no separate statute/constitution retrieval, no iterative refinement, and outputs a flat memo without structured footnotes.

**The goal**: Make it work like a real lawyer — AND beat the best competitor:
1. **Rewrite** the query into a detailed, legally precise formulation
2. **Orchestrate** like a senior lawyer — divide into typed research tasks with **dual queries** (NL + boolean) and **named landmark cases**
3. **Fan out** to specialized workers that search the right source for each task — including **Indian Kanoon API** for cases not in our DB
4. **Assess evidence** — check if results satisfy the research plan, identify gaps
5. **Iterate** — if gaps exist, generate targeted sub-queries and loop back (max 2 rounds, FAIR-RAG pattern)
6. **Cross-verify** — detect contradictions, check overruled cases, compare holdings across sources
7. **Extract verbatim** — pull actual quoted text from judgments, not LLM-synthesized summaries
8. **Synthesize** — structured output with Quick Reference Table + IRAC analysis + scenario reconciliation + numbered footnotes linking to real sources
9. **Show work** — research audit trail showing all sources searched, used, and unused

**Key finding**: The existing LangGraph foundation, provider interfaces, hybrid search, Neo4j graph, citation verification, HITL checkpoints, and SSE streaming are all solid and reusable. **This is an evolution, not a rewrite.**

---

## 2. CURRENT ARCHITECTURE (WHAT EXISTS)

### 2.1 Current Research Agent Graph
**File**: `backend/app/core/agents/research.py` (221 lines)

```
START → classify → decompose → checkpoint_plan (HITL) → search → gather →
contradictions → checkpoint_findings (HITL) → synthesize → verify →
checkpoint_memo (HITL) → END
```

**Current limitations**:
- Single search path: `parallel_hybrid_search()` searches ONE Pinecone index + ONE FTS table
- No web search at all
- No separate statute/article/constitution databases or retrieval
- No iterative refinement loop (no evidence gap analysis)
- Query "decomposition" generates sub-queries but no orchestration strategy
- No structured footnotes in output — flat memo text
- No named case retrieval — LLM knowledge of landmark cases wasted
- No dual query generation — same NL query sent to both vector and FTS
- No per-document diversity control — one chunk per case
- Context per result limited: 500-char snippet + 1500-char ratio (Gemini 1M context vastly underutilized)

### 2.2 Current State Schema
**File**: `backend/app/core/agents/state.py`

```python
class ResearchState(TypedDict):
    query: str
    target_court: str
    target_bench: str
    language: str
    sub_queries: list[str]
    search_results: list[dict]
    cross_references: list[dict]
    contradictions: list[dict]
    draft_memo: str
    confidence: float
    messages: Annotated[list[dict], operator.add]  # Reducer for HITL messages
    iteration: int
    error: str
```

### 2.3 Current Node Functions
**File**: `backend/app/core/agents/nodes/research_nodes.py` (399 lines)

| Node | LLM | Purpose |
|------|-----|---------|
| `classify_query_node(state, llm)` | Flash | Classify by topic/complexity, extract court/bench |
| `decompose_query_node(state, llm)` | Pro | Generate 3-5 focused sub-queries |
| `parallel_search_node(state, llm, embedder, vector_store, reranker, db)` | — | Run `parallel_hybrid_search()` for each sub-query |
| `gather_results_node(state)` | — | Deduplicate, identify cross-references |
| `detect_contradictions_node(state, llm)` | Pro | Find conflicting holdings |
| `synthesize_memo_node(state, llm)` | Pro | Generate research memo + confidence score |
| `verify_citations_node(state, db)` | — | 3-layer citation verification |

### 2.4 Shared Search Utilities
**File**: `backend/app/core/agents/nodes/common.py` (604 lines)

```python
MAX_RESULTS_FOR_LLM: int = 30

async def parallel_hybrid_search(
    queries: list[str],
    llm: LLMProvider,
    embedder: EmbeddingProvider,
    vector_store: VectorStore,
    reranker: Reranker,
    db: AsyncSession,
    **search_kwargs: Any,
) -> list[dict]:

async def enrich_results_with_ratio(
    results: list[dict], db: AsyncSession, max_ratio_len: int = 1500
) -> list[dict]:

def format_search_results_for_llm(
    results: list[dict], max_snippet_len: int = 500, max_ratio_len: int = 1500
) -> str:
    """Format: [N] Title (Citation) / Court (Bench) | Year / Ratio / Snippet"""

def collect_grounding_citations(results: list[dict]) -> list[str]:

async def verify_memo_citations(
    memo: str, db: AsyncSession, grounding_citations: list[str]
) -> str:
    """4-layer: UUID check, human-readable match, grounding check, holding accuracy"""

def detect_overruled_cases(results: list[dict]) -> set[str]:

async def get_citation_neighbors(
    case_ids: list[str], graph_store: GraphStore, depth: int = 2
) -> list[dict]:
    """2-hop Neo4j citation graph traversal"""

def safe_json_parse(raw: str) -> dict:
def safe_json_parse_list(raw: str) -> list:
```

### 2.5 Routing & HITL Utilities
**File**: `backend/app/core/agents/routing_utils.py` (115 lines)

```python
def compile_graph(graph: Any, checkpointer: Any | None = None) -> Any:

def make_checkpoint_node(
    step: str, question: str,
    state_fields: dict[str, tuple[str, Any]],
    extra_return: Callable | None = None,
) -> Callable:

def make_feedback_router(
    step: str, loop_back: str, proceed: str | None = None,
    max_iterations: int = 3, check_error: bool = False,
) -> Callable:

def is_proceed(content: str) -> bool:
    """Checks: 'looks good', 'okay', 'yes', 'lgtm', 'proceed', etc."""
```

HITL flow: `interrupt()` pauses → client receives checkpoint SSE → user responds → `Command(resume=user_input)` → feedback stored in `messages` list → router checks if "proceed" or "revise".

### 2.6 Hybrid Search Pipeline
**File**: `backend/app/core/search/hybrid.py` (806 lines)

```python
async def hybrid_search(
    query: str, *,
    filters: SearchFilters | None = None,
    page: int = 1, page_size: int | None = None,
    llm: LLMProvider, embedder: EmbeddingProvider,
    vector_store: VectorStore, reranker: Reranker,
    db: AsyncSession, redis_client=None, language: str = "en",
) -> SearchResponse:

async def _exact_citation_search(query: str, db: AsyncSession) -> list[SearchResultItem]:
    """Direct ILIKE match on cases.citation + case_citation_equivalents table."""

async def _vector_search(query, *, embedder, vector_store, filters) -> list[tuple[str, float, str]]:
    """Returns (case_id, score, chunk_text). Deduplicates by case_id, keeps best chunk."""

def rrf_merge(ranked_lists, *, k: int = 60, weights: list[float] | None = None) -> list[tuple[str, float]]:
    """RRF(d) = Sum(w_i / (k + rank_i(d)))"""
```

Pipeline: Redis cache → LLM query understanding → statute expansion → strategy selection → parallel vector+FTS → RRF merge (k=60) → Cohere rerank → PG enrichment → bias detection → facet building → cache store.

**Strategy weights**: keyword_heavy=[1.0,2.0], vector_heavy=[2.0,1.0], balanced=[1.0,1.0].

**SearchResultItem fields**: `case_id, score, title, citation, court, year, date, case_type, judge, snippet, chunk_text, bench_type, equivalent_citations, relevance_sources, treatment_warning`

### 2.7 Query Understanding
**File**: `backend/app/core/search/query.py`

```python
@dataclass(frozen=True, slots=True)
class QueryUnderstanding:
    intent: str       # citation_lookup | topic_search | case_search | statute_search | judge_search | general
    original_query: str
    expanded_query: str
    filters: SearchFilters
    entities: QueryEntities  # case_names[], statutes[], legal_concepts[], judges[], courts[]
    search_strategy: str  # vector_heavy | keyword_heavy | balanced | exact_match

def expand_statute_references(query: str) -> tuple[str, list[str]]:
    """Bidirectional: IPC↔BNS (28 mappings), CrPC↔BNSS, IEA↔BSA."""
```

### 2.8 Provider Interfaces
**File**: `backend/app/core/interfaces/`

| Interface | File | Key Methods |
|-----------|------|-------------|
| `LLMProvider` | `llm.py` | `generate()`, `generate_structured()`, `stream()` |
| `EmbeddingProvider` | `embedder.py` | `embed_text()`, `embed_batch()`, `.dimension` |
| `VectorStore` | `vector_store.py` | `search(query_vector, top_k, filters)`, `upsert()`, `delete_by_metadata()` |
| `Reranker` | `reranker.py` | `rerank(query, documents, top_n)` |
| `GraphStore` | `graph_store.py` | `create_node()`, `get_neighbors()`, `query()`, `batch_create_citation_edges()` |
| `WebSearchProvider` | **DOES NOT EXIST YET** | To be created in Phase 3 |
| `ExternalDocProvider` | **DOES NOT EXIST YET** | To be created in Phase 3 (Indian Kanoon API) |

### 2.9 Dependency Factories
**File**: `backend/app/core/dependencies.py`

All `@lru_cache` singletons:
- `get_llm()` → GeminiLLM (gemini-2.5-pro)
- `get_flash_llm()` → GeminiLLM (gemini-2.5-flash)
- `get_embedder()` → GeminiEmbedder (gemini-embedding-001, 1536-dim)
- `get_vector_store()` → PineconeStore
- `get_graph_store()` → Neo4jGraph
- `get_reranker()` → CohereReranker (rerank-v4.0-pro)
- `get_checkpointer()` → AsyncPostgresSaver (prod) / MemorySaver (dev)
- `get_translator()`, `get_storage()`, `get_tts()`

### 2.10 Agent API Route
**File**: `backend/app/api/routes/agents.py`

```python
if agent_type == "research":
    graph = build_research_graph(
        llm=llm, flash_llm=get_flash_llm(),
        embedder=embedder, vector_store=vector_store,
        reranker=reranker, checkpointer=checkpointer,
    )
    initial_input = {"query": request_body.query, "language": request_language}
```

SSE streaming via `_stream_agent_events(graph, initial_input, config, exec_id)`.
Event types: `status`, `checkpoint`, `memo`, `done`, `error`. Keepalive every 15s.

### 2.11 Confidence Scoring
**File**: `backend/app/core/agents/confidence.py` (165 lines)

```python
# Weights
_W_RELEVANCE = 0.40      # reranker scores (mean of top-5)
_W_COVERAGE = 0.20       # cross-reference ratio
_W_AUTHORITY = 0.20      # precedent strength
_W_CONTRADICTION = 0.20  # contradiction penalty

# Strength mapping
BINDING = 1.0, PERSUASIVE = 0.7, DISTINGUISHABLE = 0.4, OVERRULED = 0.1

def calculate_confidence(reranker_scores, cross_ref_ratio, precedent_strengths,
                        contradiction_count, total_results) -> float:

def calculate_confidence_detailed(...) -> ConfidenceBreakdown:
    """Returns: overall, data_confidence, legal_confidence, consistency_confidence"""
```

### 2.12 Current Prompts
**File**: `backend/app/core/legal/prompts.py`

Research-related constants:
- `RESEARCH_CLASSIFY_SYSTEM`, `RESEARCH_CLASSIFY_SCHEMA`
- `RESEARCH_DECOMPOSE_SYSTEM`, `RESEARCH_DECOMPOSE_USER`, `RESEARCH_DECOMPOSE_SCHEMA`
- `RESEARCH_CONTRADICTIONS_SYSTEM`
- `RESEARCH_SYNTHESIZE_SYSTEM`, `RESEARCH_SYNTHESIZE_USER`
- `LEGAL_DISCLAIMER`
- `HINDI_SYSTEM_SUFFIX` (in common.py)

### 2.13 Current Data in Each Store

**Pinecone** (single index, 1536-dim):
- Only case law chunks. IDs: `{case_id}_{chunk_index}`
- 18 metadata fields: `case_id, chunk_index, section_type, court, year, case_type, jurisdiction, bench_type, disposal_nature, title, citation, author_judge, judge[], acts_cited[], opinion_author, para_start, para_end, text`
- **No `document_type` field yet** — all vectors are implicitly case law

**PostgreSQL**:
- `cases` table (53 columns) — full judgment metadata + FTS via `searchable_text` tsvector
- `case_sections` table — 17 section types (FACTS, ISSUES, ARGUMENTS, HOLDINGS, etc.)
- `case_citation_equivalents` — parallel reporter citations
- `agent_executions` — agent run tracking
- **No statute/constitution tables**

**Neo4j**:
- `Case` nodes (id, title, citation, court, year, bench_type, case_type, disposal_nature, judge)
- `CITES` edges (with `treatment` property: referred_to, approved, overruled, distinguished)
- `EQUIVALENT_TO` edges (parallel citations)
- **No Statute nodes**

### 2.14 Settings
**File**: `backend/app/core/config.py` (202 lines)

```python
# Search
search_rrf_k: int = 60
search_vector_top_k: int = 20
search_fts_top_k: int = 20
search_rerank_top_n: int = 10
# LLM
gemini_model: str = "gemini-2.5-pro"
gemini_flash_model: str = "gemini-2.5-flash"
gemini_embedding_dimension: int = 1536
# Vector
pinecone_host: str = ""
pinecone_index_name: str = "smriti-legal"
# Reranker
cohere_rerank_model: str = "rerank-v4.0-pro"
cohere_rerank_top_n: int = 10
# Chat/RAG
chat_max_context_results: int = 5
chat_max_snippet_length: int = 3000
```

### 2.15 Existing Patterns to Follow

**Interface + Provider**: All external services behind Protocol classes in `core/interfaces/`, implementations in `core/providers/`.

**Node functions**: Pure async, take state + injected deps, return partial state dict. Dependencies captured via closures in graph builder.

**LLM allocation**: Flash for classification/routing, Pro for reasoning/synthesis.

**Hindi support**: `language` param in all calls. Skip FTS for Hindi (vector-only). Append `HINDI_SYSTEM_SUFFIX` to system prompts.

**Error handling**: Tenacity retry on all providers (2-60s, 3-5 attempts). Individual search failures logged, not propagated.

**Security**: `sanitize_search_query()` on all user input. `detect_prompt_injection()` check. Parameterized SQL only.

---

## 3. TARGET ARCHITECTURE (WHAT WE'RE BUILDING)

### 3.1 New Graph Flow

```
START
  → [S2] rewrite_query ∥ classify  [PARALLEL]  Both read original query, run simultaneously
  │   ├─ rewrite_query       [NEW]  Flash — detailed legal query expansion (~2s)
  │   └─ classify            [KEEP] Flash — topic/complexity/court/bench + complexity rating (~1.5s)
  │
  → [S9] route_by_complexity [NEW]  Conditional edge based on classify.complexity:
  │   ├─ "simple" → fast_path_search → fast_path_synthesis → checkpoint_memo → END
  │   └─ "complex"/"multi_issue" → plan_research (full pipeline below)
  │
  ── FULL PIPELINE (complex queries) ──────────────────────────────────────────
  → plan_research            [NEW]  Flash — orchestrator: typed tasks + dual queries + named cases (~3s)
  → checkpoint_plan          [KEEP] HITL — user reviews research plan
  → [S6] pre_warm_embeddings [NEW]  Async during HITL wait — embed planned queries
  → dispatch_workers         [NEW]  Send() fan-out to parallel workers (results only, no CoT):
     ├─ case_law_worker      [WRAPS EXISTING] parallel_hybrid_search + multi-chunk
     ├─ named_case_worker    [NEW] Direct citation lookup for LLM-named landmark cases
     ├─ statute_worker       [NEW] PG statutes table + Pinecone doc_type filter
     ├─ constitution_worker  [NEW] PG statutes table + Pinecone doc_type filter
     ├─ ik_search_worker     [NEW] Indian Kanoon API search + fragment extraction
     ├─ web_search_worker    [NEW] Tavily API with legal domain filtering
     ├─ graph_worker         [NEW] Neo4j citation + statute traversal
     ├─ graph_community_worker [NEW] Neo4j Leiden community summaries (GraphRAG)
     └─ llm_direct_worker    [NEW] Flash LLM for definitional queries
  → gather_results           [ENHANCED] Merge multi-source, tag source_type, dedup, diversity limit
  → [S4] batch_worker_cot_with_reflection [ENHANCED] Flash — batched CoT + reflection (~3s)
  │   Asks: what did we learn? should we pivot? any surprises? [Q5 Deep Research Reflection]
  │   Outputs: worker_reasonings + strategy_adjustment (consumed by gap_analysis)
  → [S3] evaluate_and_extract [ENHANCED] Flash — CRAG scoring + passage extraction + deep_read (~5-7s)
  │   [Q2 A-RAG Deep Read]: For "ambiguous" results (CRAG 0.3-0.7), fetches full HOLDINGS/RATIO
  │   from case_sections table before deciding keep/filter — reduces false negatives
  → gap_analysis             [ENHANCED] Flash — MC-RAG conditioned evidence assessment (~3s)
  │   [Q1 MC-RAG]: Round 2+ queries are CONDITIONED on round 1 findings —
  │   e.g., "find cases that OVERRULED Bachan Singh" instead of generic gap-fill
  │   Consumes: CRAG scores + worker CoT + reflection strategy_adjustment
  → [conditional: gaps AND round < 2 → dispatch_workers | else → checkpoint_findings]
  → checkpoint_findings      [KEEP] HITL — user reviews findings + contradictions preview
  → [S1,S5] speculative_synthesis_with_contradictions [ENHANCED]
  │   3x Flash parallel drafts → Pro verification/merge/contradiction-detection (STREAMED)
  → verify                   [ENHANCED] Dual-stage: deterministic checks THEN LLM verification
  │   [Q6] Stage 1 (instant, free): regex footnote match, citation format validation,
  │         quote-vs-passage fuzzy match, overruled cross-ref via Neo4j, URL validation
  │   [Q6] Stage 2 (LLM): does cited case support the proposition? is reasoning sound?
  │   [T4 Zero-Tolerance Guardrail]: Every citation verified against PG/IK API/Neo4j —
  │         unverifiable citations REMOVED and replaced with [CITATION NEEDED]
  → legal_quality_check      [NEW] Flash — LeMAJ-inspired legal reasoning verification (~3s)
  │   [Q4]: Decomposes memo into Legal Data Points, checks each against evidence,
  │   checks for omissions, scores logical coherence. If quality < threshold → flag for user.
  → checkpoint_memo          [KEEP] HITL — user reviews final memo
  → END

  ── FAST PATH (simple queries) ───────────────────────────────────────────────
  → fast_path_search         [NEW]  Single worker dispatch based on classify.intent (~3-5s)
  → fast_path_synthesis      [NEW]  Flash — lightweight synthesis, no speculative drafts (~3s)
  → verify                   [REUSE] Same citation verification
  → checkpoint_memo          [KEEP] HITL
  → END
```

### 3.1a Speed Optimization Summary

| ID | Optimization | Saves | Where Applied |
|----|-------------|-------|---------------|
| **S1** | Merge contradictions into synthesis Pro call | **~30-40s** | speculative_synthesis prompt |
| **S2** | Parallel rewrite_query + classify | ~1.5s | Graph parallel branches |
| **S3** | Merge CRAG + extract_passages into one Flash call | ~3-4s | evaluate_and_extract node |
| **S4** | Decouple worker CoT → single batched Flash call | ~2-3s | batch_worker_cot node |
| **S5** | Stream Pro synthesis to frontend | **~25s perceived** | SSE `memo_stream` events |
| **S6** | Pre-warm embeddings during HITL wait | ~3-5s | Async during checkpoint_plan |
| **S7** | _(Subsumed by S3)_ | — | — |
| **S8** | Redis cache for hot queries + intermediate results | **Full pipeline** | Cache layer |
| **S9** | Fast path for simple queries | **~60-80s** | route_by_complexity |
| **S10** | Gemini context caching for static system prompts | ~cost 90% ↓ | LLM provider layer |
| **S11** | Semantic caching (vector similarity, not just hash match) | ~2-3x hit rate ↑ | Cache layer (before S8 hash cache) |
| **S12** | Parallel Flash batches in evaluate_and_extract | ~2-5s | evaluate_and_extract node |

**Projected latency (complex query)**: ~45-55s actual, ~20-25s perceived (vs ~92-117s before)
**Projected latency (simple query)**: ~5-10s (fast path)
**Projected latency (cached query)**: ~0.5s (Redis hit)
**Projected latency (semantic cache hit)**: ~1-2s (embed query + vector lookup + cached memo)

### 3.2 New State Schema

```python
# New TypedDicts (add to state.py)

class ResearchTask(TypedDict):
    task_id: str          # UUID
    task_type: str        # "case_law"|"named_case"|"statute"|"constitution"|"ik_search"|"web"|"graph"|"llm_direct"
    nl_query: str         # Natural language query (for vector/semantic search)
    boolean_query: str    # Structured boolean query (for FTS/keyword search)
    named_cases: list[dict]  # [{name, citation, relevance}] — LLM-known landmark cases
    rationale: str        # Why this task exists (shown in HITL review)
    filters: dict         # year, court, act, etc.
    priority: int         # 1=high, 3=low

class WorkerResult(TypedDict):
    task_id: str
    task_type: str
    query: str
    results: list[dict]   # Standard search result dicts
    source_urls: list[str] # Indian Kanoon URLs, web URLs for linking
    metadata: dict        # source-specific: ik_doc_id, web_domain, etc.
    error: str | None
    reasoning: str        # [MA-RAG] Worker-level CoT: key findings, tensions, relevance summary

class EvidenceGap(TypedDict):
    description: str
    suggested_query: str
    suggested_source: str  # Which worker should handle it
    priority: int
    conditioned_on: list[str]  # [MC-RAG] Case IDs/citations from prior round that informed this gap
    conditioning_context: str  # [MC-RAG] "Overrule chain for Bachan Singh" — why this gap exists

class ExtractedPassage(TypedDict):
    case_id: str
    citation: str
    passage: str          # Verbatim text from source
    source_field: str     # "chunk_text" | "ratio" | "ik_fragment" | "full_text"
    relevance: str        # Why this passage matters for the research question
    is_verbatim: bool     # True if exact copy, False if paraphrased

class RelevanceScore(TypedDict):
    """[CRAG] Per-document relevance evaluation from the retrieval evaluator."""
    case_id: str
    score: float          # 0.0-1.0 relevance to research question
    verdict: str          # "correct" | "ambiguous" | "incorrect" (CRAG classification)
    reason: str           # Why this document is/isn't relevant
    action: str           # "keep" | "filter" | "needs_web_fallback"

class CommunitySummary(TypedDict):
    """[GraphRAG] Pre-computed summary of a citation community cluster."""
    community_id: str
    title: str            # "Section 498A IPC misuse cluster" — generated by LLM
    summary: str          # 2-3 paragraph summary of the community's legal position
    key_cases: list[str]  # Top 5 case_ids in this community
    legal_principles: list[str]  # Extracted principles from this community
    size: int             # Number of cases in community

class SynthesisDraft(TypedDict):
    """[Speculative RAG] One of N parallel synthesis drafts."""
    draft_id: str
    strategy: str         # "relevance" | "authority" | "recency" — which evidence subset
    memo_text: str        # The draft memo
    confidence: float     # Self-assessed confidence
    sources_used: list[str]  # Citations referenced in this draft

class Footnote(TypedDict):
    number: int
    citation: str         # Full case citation or statute reference
    source_type: str      # "case_law"|"statute"|"constitution"|"web"|"llm_knowledge"
    source_url: str       # Link to case viewer, IK page, or web URL
    case_id: str | None   # Our internal case_id if available
    excerpt: str          # Relevant passage (verbatim or paraphrased)
    is_used: bool         # True if cited in memo, False if searched but not cited
    verification_status: str  # [T4] "verified_pg"|"verified_ik"|"verified_neo4j"|"unverified"|"removed"
    verified_against: str     # [T4] Which source confirmed: "PostgreSQL cases table"|"IK API /docmeta/"|"Neo4j Case node"

class LegalQualityResult(TypedDict):
    """[Q4 LeMAJ] Legal reasoning quality assessment of final memo."""
    overall_score: float      # 0.0-1.0 legal reasoning quality
    data_points: list[dict]   # [{claim: str, supported: bool, evidence_id: str, issue: str|None}]
    omissions: list[dict]     # [{missed_authority: str, relevance: str}] — important cases in evidence but not cited
    logical_issues: list[str] # ["IRAC analysis skips APPLICATION for Issue 2", ...]
    pass_threshold: bool      # True if score >= 0.7 (safe to show to user without flag)

class StrategyAdjustment(TypedDict):
    """[Q5 Deep Research Reflection] Mid-research strategy pivot from reflection."""
    should_pivot: bool
    pivot_reason: str         # "BNS replaced IPC 499 — need to search new code"
    new_tasks: list[dict]     # Additional ResearchTask-shaped dicts to add to plan
    reframe_query: str | None # If the research question itself should be reframed

# Updated ResearchState — new fields:
#   rewritten_query: str
#   research_plan: list[ResearchTask]
#   worker_results: Annotated[list[WorkerResult], operator.add]  # CRITICAL: reducer for Send()
#   worker_reasonings: list[str]          # [MA-RAG] Collected CoT reasoning from all workers
#   relevance_scores: list[RelevanceScore] # [CRAG] Per-document relevance evaluations
#   community_summaries: list[CommunitySummary]  # [GraphRAG] Relevant community summaries
#   extracted_passages: list[ExtractedPassage]
#   evidence_gaps: list[EvidenceGap]
#   refinement_round: int   (0, 1, or 2 max)
#   synthesis_drafts: list[SynthesisDraft]  # [Speculative RAG] Parallel draft memos
#   footnotes: list[Footnote]
#   source_attribution: dict   # {citation: {source_type, worker, url, case_id}}
#   research_audit: dict       # {total_sources_searched, sources_cited, sources_unused, searches_executed}
#   --- New fields from enhancement merge ---
#   strategy_adjustment: StrategyAdjustment | None  # [Q5] Reflection output consumed by gap_analysis
#   legal_quality_result: LegalQualityResult | None # [Q4] LeMAJ quality check output
#   citation_verification_results: list[dict]        # [T4] Per-citation verification status
#   process_events: list[dict]                       # [T1] Accumulated SSE events for research audit UI
```

The `operator.add` reducer on `worker_results` is critical — it lets each parallel `Send()` worker append results without overwriting others.

### 3.3 Implementation Strategy

**Phases 1 + 2 run in parallel** (independent work):
- Phase 1: Agent graph restructure (week 1-2)
- Phase 2: Statute/constitution data ingestion + AWS HC expansion (week 1-2)

**Phase 3 depends on both** completing (week 3-4).
**Phases 4-5** are output quality + polish (week 5-6).

---

## 4. DATA ARCHITECTURE

### 4.1 Three-Tier Data Strategy

**Tier 1: Own Database (Primary, Fastest, Deepest)**
- SC judgments from AWS Open Data (current: ~796 ingested, target: 35K)
- **HC judgments from AWS Open Data** `s3://indian-high-court-judgments/` — 25 High Courts, CC-BY-4.0 [NEW]
- Fully indexed: PostgreSQL (FTS + metadata) + Pinecone (semantic) + Neo4j (citation graph)
- This is the backbone — deep metadata, section-aware chunks, citation graph, precedent strength

**Tier 2: Indian Kanoon API (Supplementary, Real-time)** [NEW]
- **28M+ documents**, adding ~20K daily
- Official API at `api.indiankanoon.org` — explicitly permits RAG/LLM use
- Pricing: Rs 0.05/fragment, Rs 0.20/full doc, Rs 0.50/search
- **Rs 10,000/month FREE** for non-commercial (50K fragment requests)
- Authentication: Token-based (`Authorization: Token <token>`)
- Key endpoints:
  - `/search/?formInput=<query>` — full-text search with court/date/judge filters
  - `/doc/<docid>/` — full document retrieval
  - `/docfragment/<docid>/?formInput=<query>` — relevant sections only (cheapest!)
  - `/docmeta/<docid>/` — metadata only
- **Structural analysis**: Paragraphs classified into 8 categories (Facts, Issues, Arguments, Analysis, etc.)
- **Built-in citation graph**: Top 5-50 citing/cited-by documents per doc
- **Attribution required**: Display "Powered by IKanoon" logo

**Tier 3: Live Web Search (Fallback, Latest)**
- Tavily API with `include_domains=["indiankanoon.org", "livelaw.in", "barandbench.com", "scconline.com"]`
- For very recent judgments, commentary, analysis not in any database
- Results include URL for footnote linking

### 4.2 How Workers Use Each Tier

| Worker | Tier 1 (Own DB) | Tier 2 (IK API) | Tier 3 (Web) |
|--------|----------------|-----------------|--------------|
| `case_law_worker` | Pinecone + FTS + PG enrichment | — | — |
| `named_case_worker` | `_exact_citation_search()` | `/search/` by case name | — |
| `statute_worker` | PG `statutes` + Pinecone `doc_type:statute` | — | — |
| `constitution_worker` | PG `statutes` + Pinecone `doc_type:constitution` | — | — |
| `ik_search_worker` | — | `/search/` + `/docfragment/` | — |
| `web_search_worker` | — | — | Tavily |
| `graph_worker` | — (Neo4j) | — | — |
| `llm_direct_worker` | — | — | — |

### 4.3 Statute Storage (Three-Layer)

#### Layer 1: PostgreSQL `statutes` Table
```sql
CREATE TABLE statutes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    act_name VARCHAR(200) NOT NULL,        -- "Bharatiya Nyaya Sanhita"
    act_short_name VARCHAR(50) NOT NULL,   -- "BNS"
    act_number VARCHAR(50),                -- "45 of 2023"
    act_year INTEGER NOT NULL,             -- 2023
    part VARCHAR(100),                     -- "Part I"
    chapter VARCHAR(100),                  -- "Chapter XVI - Of Offences..."
    section_number VARCHAR(20) NOT NULL,   -- "103" (varchar for "302A", "34(1)(a)")
    section_title VARCHAR(500),            -- "Punishment for murder"
    section_text TEXT NOT NULL,
    explanation TEXT,
    effective_date DATE,
    is_repealed BOOLEAN DEFAULT FALSE,
    replaced_by VARCHAR(200),              -- "BNS, Section 103" (IPC→BNS)
    replaces VARCHAR(200),                 -- "IPC, Section 302" (BNS→IPC)
    document_type VARCHAR(20) NOT NULL,    -- "statute" | "constitution" | "rules"
    searchable_text TSVECTOR,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (act_short_name, section_number)
);

CREATE INDEX ix_statutes_act ON statutes (act_short_name);
CREATE INDEX ix_statutes_section ON statutes (act_short_name, section_number);
CREATE INDEX ix_statutes_fts ON statutes USING GIN (searchable_text);
CREATE INDEX ix_statutes_doc_type ON statutes (document_type);
```

#### Layer 2: Pinecone — Same Index, `document_type` Metadata Filter
```python
{
    "id": f"statute:{act_short_name}:{section_number}",
    "values": embedding,  # 1536-dim Gemini
    "metadata": {
        "document_type": "statute",    # "case_law" | "statute" | "constitution"
        "act_name": "...", "act_short_name": "BNS", "section_number": "103",
        "section_title": "...", "chapter": "...", "act_year": 2023,
        "replaces": "IPC, Section 302", "text": section_text[:2000],
    }
}
```

#### Layer 3: Neo4j — Statute Nodes + APPLIES Relationships
```cypher
MERGE (s:Statute {act: "BNS", section: "103"})
SET s.title = "Punishment for murder", s.act_year = 2023

MATCH (c:Case {id: $case_id}), (s:Statute {act: $act, section: $section})
MERGE (c)-[:APPLIES {context: "ratio_decidendi"}]->(s)
```

### 4.4 Data Sources

| Source | Data | Sections | Cost |
|--------|------|----------|------|
| AWS S3 `indian-supreme-court-judgments` | SC judgments | 35K | Free |
| AWS S3 `indian-high-court-judgments` | 25 HC judgments | 100K+ | Free |
| Indian Kanoon API | All courts, tribunals | 28M+ | Rs 10K/mo free |
| civictech-India/constitution-of-india | Constitution | ~450 articles | Free |
| civictech-India/Indian-Law-Penal-Code-Json | IPC, CrPC, IEA, CPC | ~1,500 sections | Free |
| Kaggle BNS Dataset | BNS (new penal code) | 358 sections | Free |
| BNSS, BSA | New criminal/evidence codes | ~750 sections | Parse PDFs |

---

## 5. PHASE 1: CORE ORCHESTRATION (Week 1-2)

**Goal**: Replace linear decompose→search with orchestrator→worker pattern. Only `case_law_worker` + `named_case_worker` active initially — but with dual-query generation, named case retrieval, multi-chunk results, and passage extraction infrastructure.

### Files to Create/Modify

#### 5.1 `backend/app/core/agents/state.py` — ADD new TypedDicts + state fields
- Add `ResearchTask`, `WorkerResult`, `EvidenceGap`, `ExtractedPassage`, `Footnote` TypedDicts (see Section 3.2)
- Add new fields to `ResearchState` with safe defaults for backward compat:
  ```python
  rewritten_query: str                                           # default ""
  research_plan: list[ResearchTask]                              # default []
  worker_results: Annotated[list[WorkerResult], operator.add]    # REDUCER
  extracted_passages: list[ExtractedPassage]                     # default []
  evidence_gaps: list[EvidenceGap]                               # default []
  refinement_round: int                                          # default 0
  footnotes: list[Footnote]                                      # default []
  source_attribution: dict                                       # default {}
  research_audit: dict                                           # default {}
  # Speed optimization fields:
  complexity: str                                                # [S9] "simple"|"complex"|"multi_issue" from classify
  precomputed_embeddings: dict                                   # [S6] {query_str: vector} pre-warmed during HITL
  worker_reasonings: list[str]                                   # [S4] Batched CoT, not per-worker
  ```

#### 5.2 `backend/app/core/legal/prompts.py` — ADD new prompts

**`RESEARCH_REWRITE_SYSTEM`**: "You are an expert Indian legal researcher. Rewrite this query to be comprehensive, specific, and legally precise. Identify exact legal issues, relevant statutes, constitutional provisions, and affected parties."

**`RESEARCH_CLASSIFY_SCHEMA` — MODIFY** [S9]: Add `complexity` field to classify output:
```python
# Add to existing RESEARCH_CLASSIFY_SCHEMA:
"complexity": {
    "type": "string",
    "enum": ["simple", "complex", "multi_issue"],
    "description": "simple = definitional/single statute/single citation lookup. complex = multi-faceted legal question. multi_issue = requires analysis of multiple intersecting legal issues."
}
```
The existing classify node already runs Flash — this just adds one field to its structured output. The `complexity` value drives the `route_by_complexity` conditional edge [S9].

**`RESEARCH_PLAN_SYSTEM` + `RESEARCH_PLAN_SCHEMA`**: Critical prompt — must generate dual queries + named cases:
```python
RESEARCH_PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "research_tasks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "task_type": {"type": "string", "enum": ["case_law", "named_case", "statute", "constitution", "ik_search", "web", "graph", "llm_direct"]},
                    "nl_query": {"type": "string"},           # For vector/semantic search
                    "boolean_query": {"type": "string"},      # For FTS: "Section 20 AND jurisdiction AND CPC"
                    "named_cases": {                           # Landmark cases LLM knows about
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "citation": {"type": "string", "nullable": true},
                                "relevance": {"type": "string"}
                            }
                        }
                    },
                    "rationale": {"type": "string"},
                    "filters": {"type": "object"},
                    "priority": {"type": "integer"}
                }
            }
        }
    }
}
```

System prompt must instruct:
> "For each task, provide BOTH a natural language query (for semantic search) AND a structured boolean query (for keyword search). Name 2-3 specific landmark Indian cases you know are relevant, with citations if possible. The named cases will be looked up directly in our database."

**`RESEARCH_EVALUATE_RELEVANCE_SYSTEM` + `RESEARCH_EVALUATE_RELEVANCE_SCHEMA`** [CRAG]: Corrective RAG retrieval evaluator.
```python
RESEARCH_EVALUATE_RELEVANCE_SYSTEM = """You are a legal research quality evaluator. For each retrieved document, assess its relevance to the research question.

Score each document 0.0-1.0 and classify as:
- "correct" (score >= 0.7): Directly relevant, contains applicable legal principles or holdings
- "ambiguous" (0.3 <= score < 0.7): Tangentially relevant or related but not directly on point
- "incorrect" (score < 0.3): Irrelevant, wrong jurisdiction, or mismatched legal issue

For "incorrect" documents, suggest whether a web search fallback might find a better source.
Be strict — a document about a different section of the same act is "ambiguous", not "correct"."""

RESEARCH_EVALUATE_RELEVANCE_SCHEMA = {
    "type": "object",
    "properties": {
        "evaluations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "case_id": {"type": "string"},
                    "score": {"type": "number"},
                    "verdict": {"type": "string", "enum": ["correct", "ambiguous", "incorrect"]},
                    "reason": {"type": "string"},
                    "action": {"type": "string", "enum": ["keep", "filter", "needs_web_fallback"]}
                }
            }
        },
        "overall_quality": {"type": "number"},  # 0-1, mean of all scores
        "filter_count": {"type": "integer"},     # How many filtered out
        "web_fallback_needed": {"type": "boolean"}  # True if too many incorrect
    }
}
```

**`RESEARCH_WORKER_COT_SYSTEM`** [MA-RAG]: Worker-level chain-of-thought reasoning prompt.
```python
RESEARCH_WORKER_COT_SYSTEM = """You are a legal research analyst reviewing search results for a specific research sub-task.

Given the search results below, provide a brief chain-of-thought analysis:
1. How many results are relevant vs noise?
2. What are the 2-3 most important findings and WHY?
3. What legal tension or ambiguity exists in these results?
4. What is MISSING that the gap analysis should look for?

Be concise (3-5 sentences). This reasoning will guide the synthesis agent."""
```

**`RESEARCH_GAP_ANALYSIS_SYSTEM` + `RESEARCH_GAP_ANALYSIS_SCHEMA`**: FAIR-RAG evidence assessment. Enhanced to consume CRAG scores + worker CoT reasoning for more targeted gap identification.

**`RESEARCH_EVALUATE_AND_EXTRACT_SYSTEM`** [S3]: Merged CRAG + passage extraction prompt (saves one Flash round-trip):
```python
RESEARCH_EVALUATE_AND_EXTRACT_SYSTEM = """You are a legal research quality evaluator AND passage extractor.

For each retrieved document, do TWO things:

1. EVALUATE RELEVANCE: Score 0.0-1.0 and classify:
   - "correct" (>= 0.7): Directly relevant, applicable legal principles/holdings
   - "ambiguous" (0.3-0.7): Tangentially relevant, not directly on point
   - "incorrect" (< 0.3): Irrelevant, wrong jurisdiction, mismatched issue

2. EXTRACT PASSAGE (only for "correct" and "ambiguous" documents):
   - Copy the single most relevant verbatim passage from the source text
   - EXACT text only — do not paraphrase or fabricate
   - If paraphrasing is unavoidable, prefix with [paraphrased]

Be strict — a document about a different section of the same act is "ambiguous", not "correct"."""
```

**`RESEARCH_FAST_PATH_SYNTHESIS_SYSTEM`** [S9]: Lightweight synthesis for simple queries:
```python
RESEARCH_FAST_PATH_SYNTHESIS_SYSTEM = """You are a legal research assistant providing a concise answer.

Given the search results, write a focused response with:
1. Direct answer (2-3 sentences)
2. Key authority (the most relevant case or statute, with citation)
3. Brief legal context (1 paragraph)
4. Footnotes linking to sources

Keep it concise — this is a simple query that doesn't need full IRAC analysis."""
```

#### 5.3 `backend/app/core/agents/nodes/research_nodes.py` — ADD new nodes

**`rewrite_query_node(state, llm)`** — Flash LLM:
- Takes `state["query"]`, returns `{"rewritten_query": expanded_text}`
- Expansion: 2-3 paragraphs identifying legal issues, statutes, constitutional provisions
- [S2] Runs in PARALLEL with classify — both read `state["query"]`, neither depends on the other

**`classify_query_node(state, llm)`** — Flash LLM [ENHANCED]:
- Same as current classify, but now also outputs `complexity: "simple"|"complex"|"multi_issue"`
- [S2] Runs in PARALLEL with rewrite_query
- Returns `{"complexity": ..., ...existing fields...}`
- The `complexity` field drives `route_by_complexity` [S9]

**`plan_research_node(state, llm)`** — Flash LLM structured output:
- Reads `state["rewritten_query"]` + classification from messages
- Produces `list[ResearchTask]` with dual queries, named cases, typed tasks
- Returns `{"research_plan": tasks, "sub_queries": [t["nl_query"] for t in tasks]}`
- `sub_queries` populated for backward compat with existing HITL checkpoint

**`pre_warm_embeddings_node(state, embedder)`** [S6] — Runs async during HITL wait:
- Pre-computes query embeddings for all planned research tasks while user reviews plan
- Returns `{"precomputed_embeddings": {query_str: vector_list}}`
- Workers check this dict before calling `embedder.embed_text()` — skip if pre-warmed
- **Quality safeguard**: If user modifies the plan during HITL, pre-warmed embeddings for changed queries are discarded; workers fall back to live embedding
```python
async def pre_warm_embeddings_node(state: dict, embedder: EmbeddingProvider) -> dict:
    """[S6] Pre-compute embeddings during HITL wait. Non-blocking, best-effort."""
    queries = []
    for task in state.get("research_plan", []):
        if task.get("nl_query"):
            queries.append(task["nl_query"])
        if task.get("boolean_query"):
            queries.append(task["boolean_query"])

    if not queries:
        return {"precomputed_embeddings": {}}

    try:
        vectors = await embedder.embed_batch(queries)
        return {"precomputed_embeddings": dict(zip(queries, vectors))}
    except Exception:
        # Best-effort — don't block the pipeline if embedding fails
        return {"precomputed_embeddings": {}}
```

**`batch_worker_cot_with_reflection_node(state, llm)`** [S4 + Q5] — Flash LLM, single batched call:
- **Purpose**: Generate MA-RAG chain-of-thought reasoning for ALL worker results in one Flash call, instead of N separate Flash calls inside each worker. Saves ~2-3s because workers no longer block on CoT.
- **[Q5 Deep Research Reflection]**: Also performs a reflection step — asks whether findings change our understanding of the question and whether we should pivot strategy. This is NOT an extra LLM call; the reflection questions are added to the SAME batched CoT prompt.
- Takes `state["worker_results"]` (all workers have finished), formats a summary of each worker's results
- One Flash call produces: (a) per-worker reasoning, (b) cross-worker tensions, (c) strategy adjustment recommendation
- Returns `{"worker_reasonings": [str, ...], "strategy_adjustment": StrategyAdjustment | None}`
- **Quality safeguard**: The single-batch prompt sees ALL results at once, so it can identify cross-worker tensions (e.g., "case_law_worker found X but statute_worker found contradicting Y") that per-worker CoT would miss. The reflection adds near-zero latency since it's in the same prompt.
```python
async def batch_worker_cot_with_reflection_node(state: dict, llm: LLMProvider) -> dict:
    """[S4+Q5] Single batched CoT + Deep Research reflection for all worker results.
    Sees all results at once → identifies cross-worker tensions + recommends strategy pivots."""
    worker_summaries = []
    for wr in state["worker_results"]:
        n_results = len(wr.get("results", []))
        top_titles = [r.get("title", "?")[:80] for r in wr.get("results", [])[:3]]
        top_citations = [r.get("citation", "?")[:60] for r in wr.get("results", [])[:3]]
        worker_summaries.append(
            f"[{wr['task_type']}] Query: {wr['query'][:100]} | "
            f"{n_results} results. Top: {', '.join(top_titles)} ({', '.join(top_citations)})"
        )

    prompt = (
        f"Research question: {state['rewritten_query']}\n\n"
        f"Worker results summary:\n" + "\n".join(worker_summaries) + "\n\n"
        "PART 1 — ANALYSIS (for each worker, 2-3 sentences):\n"
        "- Key findings, tensions, what's missing\n"
        "- CROSS-WORKER conflicts (e.g., case law vs statute contradictions)\n\n"
        "PART 2 — REFLECTION (Deep Research-style strategy check):\n"
        "1. What did we learn that changes our understanding of the research question?\n"
        "2. Should we pivot our research strategy? (e.g., wrong statute version, "
        "question is moot, need different jurisdiction, missed a key legal concept)\n"
        "3. Are there any surprising results that suggest the question should be reframed?\n"
        "4. If pivoting: what specific new search tasks should we add?\n\n"
        "If no pivot needed, say 'No strategy change needed' for Part 2."
    )
    response = await llm.generate_structured(
        system=RESEARCH_WORKER_COT_SYSTEM,
        user=prompt,
        schema=BATCH_COT_WITH_REFLECTION_SCHEMA,  # See Section 5.2 prompts
    )

    strategy_adj = None
    if response.get("should_pivot"):
        strategy_adj = StrategyAdjustment(
            should_pivot=True,
            pivot_reason=response.get("pivot_reason", ""),
            new_tasks=response.get("new_tasks", []),
            reframe_query=response.get("reframe_query"),
        )

    return {
        "worker_reasonings": [response.get("reasoning", "")],
        "strategy_adjustment": strategy_adj,
    }
```

**`BATCH_COT_WITH_REFLECTION_SCHEMA`** (add to `prompts.py`):
```python
BATCH_COT_WITH_REFLECTION_SCHEMA = {
    "type": "object",
    "properties": {
        "reasoning": {"type": "string"},          # Part 1: per-worker analysis + cross-worker tensions
        "should_pivot": {"type": "boolean"},       # Part 2: does strategy need changing?
        "pivot_reason": {"type": "string", "nullable": True},
        "reframe_query": {"type": "string", "nullable": True},
        "new_tasks": {                             # New ResearchTask-shaped dicts
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "task_type": {"type": "string"},
                    "nl_query": {"type": "string"},
                    "boolean_query": {"type": "string"},
                    "rationale": {"type": "string"},
                }
            }
        },
    }
}
```

**`evaluate_and_extract_node(state, llm, db)`** [S3 + Q2] — Flash LLM, merged CRAG + passage extraction + deep read:
- **Purpose**: Combines CRAG relevance scoring AND verbatim passage extraction into ONE Flash call. Saves one full Flash round-trip (~3-4s) because both operations read the same results.
- **[Q2 A-RAG Deep Read]**: For results scored as "ambiguous" (0.3-0.7), BEFORE deciding keep/filter, fetches the full HOLDINGS and RATIO sections from the PostgreSQL `case_sections` table. This gives the evaluator significantly more context to make a correct/incorrect decision. Particularly valuable for cases where the 500-char snippet is misleading but the full holdings section IS relevant.
- **[S12]**: All batches of 15 processed in PARALLEL via `asyncio.gather()`, not sequentially.
- Takes all results from `state["worker_results"]`, batched (15 per LLM call)
- For each result: scores relevance (CRAG) AND extracts best verbatim passage
- Filters "incorrect" results, keeps passages from "correct" and "ambiguous"
- Returns `{"relevance_scores": [...], "extracted_passages": [...], "worker_results": filtered}`
- **Quality safeguard**: Passage extraction is ONLY attempted for documents that score ≥ 0.3 (ambiguous or correct). For "incorrect" documents, no passage is extracted — this prevents wasting extraction effort on irrelevant docs and ensures extracted passages are always from relevant sources.
- **Deep read safeguard**: Deep read is only triggered for internal case_ids (not `ik:` prefixed), and only for the first CRAG pass. If the deep read promotes an "ambiguous" result to "correct", the passage is extracted from the full section text (higher quality than snippet).
```python
EVALUATE_AND_EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "evaluations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "case_id": {"type": "string"},
                    "score": {"type": "number"},
                    "verdict": {"type": "string", "enum": ["correct", "ambiguous", "incorrect"]},
                    "reason": {"type": "string"},
                    "action": {"type": "string", "enum": ["keep", "filter", "needs_web_fallback"]},
                    # Passage extraction (null for "incorrect" docs):
                    "passage": {"type": "string", "nullable": True},
                    "passage_source_field": {"type": "string", "nullable": True},
                    "is_verbatim": {"type": "boolean", "nullable": True},
                }
            }
        },
        "overall_quality": {"type": "number"},
        "web_fallback_needed": {"type": "boolean"}
    }
}

async def evaluate_and_extract_node(state: dict, llm: LLMProvider, db: AsyncSession) -> dict:
    all_results = []
    for wr in state["worker_results"]:
        all_results.extend(wr["results"])

    # --- [Q2 A-RAG Deep Read] helper: fetch full sections for ambiguous results ---
    async def deep_read_sections(case_id: str) -> str:
        """Fetch HOLDINGS + RATIO from case_sections for deeper CRAG evaluation."""
        if case_id.startswith("ik:"):
            return ""  # Only for internal cases
        rows = await db.execute(
            select(CaseSection.content).where(
                CaseSection.case_id == case_id,
                CaseSection.section_type.in_(["HOLDINGS", "RATIO_DECIDENDI", "ANALYSIS"]),
            )
        )
        sections = [row[0] for row in rows.fetchall()]
        return "\n\n".join(sections)[:5000]  # Cap at 5K chars

    # --- [S12] Process all batches in PARALLEL ---
    batches = list(chunked(all_results, 15))

    async def process_batch(batch):
        formatted = format_search_results_for_llm_extended(batch)
        return await llm.generate_structured(
            system=RESEARCH_EVALUATE_AND_EXTRACT_SYSTEM,
            user=f"Research question: {state['rewritten_query']}\n\nDocuments:\n{formatted}",
            schema=EVALUATE_AND_EXTRACT_SCHEMA,
        )

    evaluations = await asyncio.gather(*[process_batch(b) for b in batches])

    relevance_scores = []
    extracted_passages = []
    ambiguous_ids = []  # Track for deep read

    for evaluation, batch in zip(evaluations, batches):
        for ev in evaluation["evaluations"]:
            relevance_scores.append(RelevanceScore(
                case_id=ev["case_id"], score=ev["score"],
                verdict=ev["verdict"], reason=ev["reason"], action=ev["action"],
            ))
            if ev["verdict"] == "ambiguous":
                ambiguous_ids.append((ev["case_id"], batch))
            if ev.get("passage") and ev["verdict"] != "incorrect":
                extracted_passages.append(ExtractedPassage(
                    case_id=ev["case_id"],
                    citation=next((r.get("citation", "") for r in batch if r.get("case_id") == ev["case_id"]), ""),
                    passage=ev["passage"],
                    source_field=ev.get("passage_source_field", "chunk_text"),
                    relevance=ev["reason"],
                    is_verbatim=ev.get("is_verbatim", True),
                ))

    # --- [Q2] Deep read pass for ambiguous results (up to 10 to limit latency) ---
    if ambiguous_ids:
        deep_read_tasks = []
        for case_id, _ in ambiguous_ids[:10]:
            deep_read_tasks.append(deep_read_sections(case_id))
        section_texts = await asyncio.gather(*deep_read_tasks, return_exceptions=True)

        for (case_id, _), section_text in zip(ambiguous_ids[:10], section_texts):
            if isinstance(section_text, Exception) or not section_text:
                continue
            # Re-evaluate with full section context (single lightweight Flash call)
            re_eval = await llm.generate_structured(
                system=RESEARCH_EVALUATE_AND_EXTRACT_SYSTEM,
                user=f"Research question: {state['rewritten_query']}\n\n"
                     f"Full HOLDINGS/RATIO for re-evaluation:\n{section_text}",
                schema=EVALUATE_AND_EXTRACT_SCHEMA,
            )
            for ev in re_eval.get("evaluations", []):
                if ev["case_id"] == case_id:
                    # Update the score if deep read changed verdict
                    for i, s in enumerate(relevance_scores):
                        if s["case_id"] == case_id:
                            relevance_scores[i] = RelevanceScore(
                                case_id=case_id, score=ev["score"],
                                verdict=ev["verdict"], reason=f"[deep_read] {ev['reason']}",
                                action=ev["action"],
                            )
                    # Extract passage from full section if now "correct"
                    if ev.get("passage") and ev["verdict"] == "correct":
                        extracted_passages.append(ExtractedPassage(
                            case_id=case_id, citation="",
                            passage=ev["passage"], source_field="case_sections",
                            relevance=ev["reason"], is_verbatim=ev.get("is_verbatim", True),
                        ))

    # Filter incorrect results (after deep read re-evaluation)
    incorrect_ids = {s["case_id"] for s in relevance_scores if s["verdict"] == "incorrect"}
    filtered_worker_results = []
    for wr in state["worker_results"]:
        filtered = [r for r in wr["results"] if r.get("case_id") not in incorrect_ids]
        filtered_worker_results.append({**wr, "results": filtered})

    return {
        "relevance_scores": relevance_scores,
        "extracted_passages": extracted_passages,
        "worker_results": filtered_worker_results,
    }
```

**`gap_analysis_node(state, llm)`** — Flash LLM [ENHANCED with CRAG + MA-RAG + MC-RAG + Reflection]:
- Compares `state["research_plan"]` (checklist) against `state["worker_results"]` (evidence)
- Consumes `state["relevance_scores"]` — if CRAG flagged `web_fallback_needed`, prioritizes IK/web workers in refinement tasks
- Consumes `state["worker_reasonings"]` — batched CoT reasoning highlights what's missing and cross-worker tensions
- **[Q5 Reflection integration]**: Consumes `state["strategy_adjustment"]` — if reflection recommended a pivot, the gap analysis incorporates those new tasks and the reframed query. Strategy adjustments take PRIORITY over standard gap-filling because they represent a fundamental change in research direction (e.g., "search BNS instead of IPC").
- **[Q1 MC-RAG Conditioned Retrieval]**: Round 2+ queries are CONDITIONED on round 1 findings. The prompt receives `top_results_summary` (top 5 cases from round 1 with citations and key holdings) and is instructed:
  > "Generate follow-up queries that BUILD ON what was found in round 1. For example:
  > - If Bachan Singh v. State of Punjab was found, search for cases that DISTINGUISHED or OVERRULED it
  > - If a statute section was found but no interpretation cases, search for interpretation cases
  > - If conflicting holdings were found, search for the reconciling authority
  > Do NOT repeat the same generic queries from round 1."
- Each `EvidenceGap` now includes `conditioned_on` (case IDs from round 1) and `conditioning_context` (why this gap exists in light of what was found)
- If gaps AND `refinement_round < 2`: returns new conditioned tasks + incremented round
- If no gaps OR max rounds: returns empty gaps (conditional edge proceeds)
- **Quality safeguard**: MC-RAG conditioning prevents the refinement loop from being a dumb retry. Round 2 queries are qualitatively different from round 1 — they follow evidence chains, not just fill keyword gaps.

**`fast_path_search_node(state, ...)`** [S9] — Lightweight single-worker dispatch:
- Routes to exactly ONE worker based on `classify.intent`:
  - `citation_lookup` → `named_case_worker`
  - `statute_search` → `statute_worker`
  - `general` / definitional → `llm_direct_worker`
  - Default → `case_law_worker` (single query, no dual)
- Returns results directly, no multi-worker fan-out
- **Quality safeguard**: If the single worker returns < 3 results, falls back to full pipeline by setting `complexity = "complex"` and re-routing. This prevents fast path from producing shallow answers for queries that were misclassified as "simple".
```python
async def fast_path_search_node(state: dict, **deps) -> dict:
    """[S9] Single-worker search for simple queries. Falls back to full pipeline if insufficient results."""
    intent = state.get("intent", "topic_search")
    query = state.get("rewritten_query") or state["query"]

    # Route to single best worker
    if intent == "citation_lookup":
        results = await _exact_citation_search(query, db)
    elif intent == "statute_search":
        results = await _statute_direct_lookup(query, db)
    elif intent == "general":
        results = [{"content": await flash_llm.generate(system="...", user=query), "source": "llm_knowledge"}]
    else:
        results = await parallel_hybrid_search([query], llm, embedder, vector_store, reranker, db)

    # Quality gate: fall back to full pipeline if too few results
    if len(results) < 3 and intent not in ("general", "citation_lookup"):
        return {"complexity": "complex"}  # re-routes via conditional edge

    return {"search_results": results, "worker_results": [WorkerResult(
        task_id="fast_path", task_type=intent, query=query,
        results=results, source_urls=[], metadata={}, error=None, reasoning="",
    )]}
```

**`fast_path_synthesis_node(state, llm)`** [S9] — Flash synthesis (no speculative drafts):
- Single Flash call using `RESEARCH_FAST_PATH_SYNTHESIS_SYSTEM`
- Produces a shorter memo (no IRAC, no reconciliation tables — just answer + authority + context + footnotes)
- **Quality safeguard**: Still runs `verify_citations_node` after synthesis
- Latency: ~3s (one Flash call)

#### 5.4 `backend/app/core/agents/nodes/worker_nodes.py` — NEW FILE

All workers follow a **search → enrich → return** pattern. Workers do NOT generate CoT reasoning individually — that was moved to `batch_worker_cot_node` [S4] which runs a single Flash call after all workers finish, saving ~2-3s per worker.

Workers use pre-warmed embeddings [S6] when available:
```python
def _get_embedding(query: str, precomputed: dict, embedder: EmbeddingProvider):
    """[S6] Use pre-warmed embedding if available, else compute live."""
    if query in precomputed:
        return precomputed[query]
    return await embedder.embed_text(query)
```

**`case_law_worker(state)`** — Enhanced wrapper around `parallel_hybrid_search()`:
```python
async def case_law_worker(state: dict) -> dict:
    task = state["task"]
    precomputed = state.get("precomputed_embeddings", {})

    # Use BOTH nl_query (vector-heavy) and boolean_query (keyword-heavy)
    queries = [task["nl_query"]]
    if task.get("boolean_query"):
        queries.append(task["boolean_query"])

    async with async_session_factory() as db:
        results = await parallel_hybrid_search(
            queries, llm, embedder, vector_store, reranker, db,
            precomputed_embeddings=precomputed,  # [S6] Skip re-embedding if pre-warmed
        )
        results = await enrich_results_with_ratio(results, db, max_ratio_len=3000)

    # [S4] No per-worker CoT — batched after gather_results
    return {"worker_results": [WorkerResult(
        task_id=task["task_id"], task_type="case_law",
        query=task["nl_query"], results=results,
        source_urls=[], metadata={}, error=None,
        reasoning="",  # Populated by batch_worker_cot_node
    )]}
```

**`named_case_worker(state)`** — Direct citation lookup [NEW]:
```python
async def named_case_worker(state: dict) -> dict:
    task = state["task"]
    results = []
    async with async_session_factory() as db:
        for named in task.get("named_cases", []):
            # Try exact citation search first
            if named.get("citation"):
                found = await _exact_citation_search(named["citation"], db)
                results.extend(found)
            # Fallback: search by case name in title
            if not found and named.get("name"):
                found = await _search_by_title(named["name"], db)
                results.extend(found)
        results = await enrich_results_with_ratio(results, db, max_ratio_len=3000)

    return {"worker_results": [WorkerResult(
        ...,
        reasoning="",  # [S4] Populated by batch_worker_cot_node
    )]}
```

#### 5.5 `backend/app/core/agents/research.py` — MAJOR REWRITE

New graph structure with `Send()` fan-out:

```python
from langgraph.types import Send

def dispatch_workers(state: ResearchState) -> list[Send]:
    """Fan out to appropriate worker for each research task."""
    sends = []
    for task in state["research_plan"]:
        worker_name = f"{task['task_type']}_worker"
        # [S6] Pass pre-warmed embeddings if available
        sends.append(Send(worker_name, {
            "task": task,
            "parent_state": state,
            "precomputed_embeddings": state.get("precomputed_embeddings", {}),
        }))
    return sends

def should_refine(state: ResearchState) -> str:
    """[S1] No separate contradictions node — merged into synthesis.
    [Q5] If reflection recommended a pivot, strategy_adjustment tasks are injected
    into research_plan by gap_analysis before this check runs."""
    if state.get("evidence_gaps") and state.get("refinement_round", 0) < 2:
        return "dispatch_workers"
    return "checkpoint_findings"

# [S9] Fast path routing based on query complexity
def route_by_complexity(state: ResearchState) -> str:
    """Route simple queries to fast path, complex to full pipeline.
    Reads complexity from classify output in state messages."""
    complexity = state.get("complexity", "complex")
    if complexity == "simple":
        return "fast_path_search"
    return "plan_research"
```

Graph edges:
```
# [S2] Parallel rewrite + classify
START → [rewrite_query ∥ classify] → route_by_complexity

# [S9] Fast path for simple queries
route_by_complexity →("simple")→ fast_path_search → fast_path_synthesis → verify → checkpoint_memo → END

# Full pipeline for complex queries
route_by_complexity →("complex")→ plan_research → checkpoint_plan
checkpoint_plan → [route_after_plan] → plan_research | dispatch_workers | END

# [S4+Q5] Workers return results-only, CoT + reflection batched after gather
# [S3+Q2+S12] CRAG + extract + deep_read merged, batches in parallel
dispatch_workers → [Send()] → gather_results → batch_worker_cot_with_reflection → evaluate_and_extract → gap_analysis

# [Q1 MC-RAG] gap_analysis generates CONDITIONED queries for round 2+
# [Q5] gap_analysis also integrates strategy_adjustment from reflection
# [S1] No separate contradictions — merged into synthesis
gap_analysis → [should_refine] → dispatch_workers | checkpoint_findings
checkpoint_findings → [route_after_findings] → ...

# [S1] Contradictions detected inside synthesis. [S5] Pro output is streamed.
speculative_synthesis_with_contradictions → verify → legal_quality_check → checkpoint_memo → [route_after_memo] → ... | END

# NOTE: verify is now [Q6] dual-stage (deterministic + LLM) with [T4] zero-tolerance guardrail
# NOTE: legal_quality_check is [Q4] LeMAJ-inspired reasoning verification (Flash, ~3s)
```

#### 5.6 `backend/app/core/agents/nodes/common.py` — MODIFY

1. **Increase context limits for research agent**:
   - Add `format_search_results_for_llm_extended(results, max_snippet_len=1500, max_ratio_len=3000)` — Gemini Pro has 1M context, we're using <1%
   - Keep original function unchanged for other agents

2. **Add per-document diversity**:
   ```python
   def deduplicate_with_diversity(results: list[dict], max_chunks_per_case: int = 4) -> list[dict]:
       """Keep top N chunks per case_id, sorted by score. Prevents one case from dominating."""
   ```

3. **Add title-based case search**:
   ```python
   async def _search_by_title(title: str, db: AsyncSession) -> list[SearchResultItem]:
       """ILIKE search on cases.title for named case retrieval."""
   ```

#### 5.7 `backend/app/api/routes/agents.py` — MINOR MODIFY
- Pass `graph_store=get_graph_store()` to `build_research_graph()`

### Phase 1 Testing
- Unit test each new node with mocked LLM/deps
- Test dual-query generation (verify both NL and boolean queries produced)
- Test named-case lookup (verify `_exact_citation_search` + `_search_by_title` fallback)
- **[CRAG] Test evaluate_relevance_node**: Mock 10 results (5 relevant, 3 ambiguous, 2 irrelevant) → verify filtering removes irrelevant, keeps correct+ambiguous, sets `web_fallback_needed` when >50% incorrect
- **[CRAG] Test CRAG→gap_analysis flow**: When CRAG flags web_fallback_needed, verify gap_analysis generates IK/web worker tasks in refinement round
- **[MA-RAG] Test worker CoT generation**: Verify each worker returns non-empty `reasoning` field, verify CoT is consumed by gap_analysis
- Integration test: full graph run verifying Send() fan-out with checkpointer
- Regression: existing 1411 tests must pass (new state fields have defaults)

---

## 6. PHASE 2: STATUTE/CONSTITUTION INGESTION + DATA EXPANSION (Week 1-2, parallel with Phase 1)

**Goal**: Ingest statutes, constitutional provisions, AND start expanding case law coverage.

### Files to Create

#### 6.1 `backend/app/db/migrations/versions/017_create_statutes_table.py` — NEW
- Creates `statutes` table with FTS trigger (see Section 4.3)
- FTS trigger: `searchable_text = setweight(to_tsvector('english', section_title), 'A') || setweight(to_tsvector('english', section_text), 'B') || setweight(to_tsvector('english', act_name), 'C')`

#### 6.2 `backend/app/models/statute.py` — NEW
- SQLAlchemy model matching the migration schema
- Follow same patterns as `backend/app/models/case.py`

#### 6.3 `backend/scripts/ingest_statutes.py` — NEW
Pipeline per source file:
1. Parse JSON/CSV
2. INSERT into `statutes` table (ON CONFLICT DO UPDATE)
3. **[Contextual Embeddings]** Generate context prefix via Flash (see 6.8 below)
4. Embed **contextualized** section_text via `get_embedder().embed_batch()`
5. Upsert to Pinecone with `document_type` metadata + `context_prefix` in metadata
6. Create Neo4j Statute nodes via `get_graph_store().create_node("Statute", ...)`
7. Build `replaces`/`replaced_by` cross-references (IPC↔BNS, CrPC↔BNSS, IEA↔BSA)

#### 6.4 AWS High Court Ingestion [NEW]
- Download from `s3://indian-high-court-judgments/` (same pattern as SC dataset)
- Use existing ingestion pipeline (`backend/app/core/ingestion/pipeline.py`)
- **[Contextual Embeddings]** Apply contextual prefix generation during chunking (see 6.8)
- Add `document_type: "case_law"` to Pinecone metadata for all new vectors
- Massively expands coverage from 35K SC to 100K+ SC+HC judgments

#### 6.5 Pinecone Metadata Backfill
- One-time script to add `document_type: "case_law"` to ALL existing case law vectors
- This enables `document_type` filtering for statute/constitution workers without breaking existing case law searches

#### 6.6 Neo4j Statute Linkage
- Batch script: scan `cases.acts_cited`, parse act+section references, create `APPLIES` edges to matching Statute nodes
- Enables: "Which cases cite Section 302 IPC?" → graph traversal

#### 6.7 Data Source Download
- Download to `backend/data/statutes/` (gitignored)
- Constitution: civictech-India/constitution-of-india (GitHub JSON)
- IPC/CrPC/IEA/CPC: civictech-India/Indian-Law-Penal-Code-Json (GitHub JSON)
- BNS: Kaggle dataset (CSV)

#### 6.8 `backend/app/core/ingestion/contextual_embeddings.py` — NEW [Contextual Retrieval]

**Purpose**: Implement Anthropic's Contextual Retrieval technique — prepend a chunk-specific context summary to each chunk BEFORE embedding. This reduced retrieval failures by 49% in benchmarks (67% with reranking + BM25). Particularly valuable for statutes where individual sections lose meaning without act context, and for case law chunks that need judgment-level framing.

**How it works**:
1. For each chunk, Flash generates a 1-2 sentence context prefix grounding the chunk within its parent document
2. The context prefix + original chunk text are concatenated and embedded together
3. The original chunk text is stored separately for display (users see original, not contextualized)
4. The BM25 index also uses the contextualized text for better keyword matching

```python
CONTEXTUAL_PREFIX_SYSTEM = """You are a legal document analyst. Given a chunk of text from a legal document and metadata about the full document, generate a concise 1-2 sentence context prefix that situates this chunk within the document.

The prefix should include:
- The case name/statute name and citation (if available)
- The section of the document this chunk comes from (facts, holdings, arguments, etc.)
- The key legal issue the overall document addresses

Format: "<context prefix>\\n\\n<original chunk text>"
Do NOT summarize or paraphrase the chunk. Only add contextual framing."""

CONTEXTUAL_PREFIX_STATUTE = """You are a legal document analyst. Given a section of an Indian statute, generate a 1-sentence context prefix.

Include: the full act name, which part/chapter this section belongs to, and whether this section was replaced by or replaces another section (if applicable).

Example: "This is Section 302 (Punishment for murder) of the Indian Penal Code, 1860, Chapter XVI (Of Offences Affecting the Human Body), now replaced by Section 103 of Bharatiya Nyaya Sanhita, 2023."
"""

async def generate_contextual_prefix(
    chunk_text: str,
    document_metadata: dict,
    flash_llm: LLMProvider,
    document_type: str = "case_law",  # "case_law" | "statute" | "constitution"
) -> str:
    """Generate a contextual prefix for a chunk using Flash LLM.

    Args:
        chunk_text: The original chunk text
        document_metadata: Dict with keys like title, citation, court, year, section_type, act_name, etc.
        flash_llm: Flash LLM instance for cheap/fast generation
        document_type: Type of document for prompt selection

    Returns:
        Contextualized text: "{prefix}\n\n{chunk_text}"
    """
    if document_type == "statute":
        system = CONTEXTUAL_PREFIX_STATUTE
        user = f"Act: {document_metadata.get('act_name', 'Unknown')}\n"
               f"Section: {document_metadata.get('section_number', '')}\n"
               f"Title: {document_metadata.get('section_title', '')}\n"
               f"Chapter: {document_metadata.get('chapter', '')}\n"
               f"Replaces: {document_metadata.get('replaces', 'N/A')}\n"
               f"Replaced by: {document_metadata.get('replaced_by', 'N/A')}\n\n"
               f"Section text:\n{chunk_text[:500]}"
    else:
        system = CONTEXTUAL_PREFIX_SYSTEM
        user = f"Document: {document_metadata.get('title', 'Unknown')}\n"
               f"Citation: {document_metadata.get('citation', 'Unknown')}\n"
               f"Court: {document_metadata.get('court', 'Unknown')}\n"
               f"Year: {document_metadata.get('year', 'Unknown')}\n"
               f"Section type: {document_metadata.get('section_type', 'Unknown')}\n\n"
               f"Chunk text:\n{chunk_text[:1000]}"

    prefix = await flash_llm.generate(system=system, user=user)
    return f"{prefix.strip()}\n\n{chunk_text}"


async def batch_contextualize_chunks(
    chunks: list[dict],
    document_metadata: dict,
    flash_llm: LLMProvider,
    document_type: str = "case_law",
    batch_size: int = 10,
) -> list[dict]:
    """Batch-contextualize chunks for a single document.

    Each chunk dict must have a "text" key. Returns chunks with added
    "contextualized_text" key (original "text" preserved for display).

    Rate: ~10 Flash calls per document (10 chunks avg). At $0.0001/call, ~$0.001/document.
    For 100K documents: ~$100 total. Negligible cost.
    """
    contextualized = []
    for batch in chunked(chunks, batch_size):
        tasks = [
            generate_contextual_prefix(
                chunk["text"], document_metadata, flash_llm, document_type
            )
            for chunk in batch
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for chunk, result in zip(batch, results):
            if isinstance(result, Exception):
                # Fallback: use original text if contextualization fails
                logger.warning(f"Contextual prefix failed for chunk: {result}")
                chunk["contextualized_text"] = chunk["text"]
            else:
                chunk["contextualized_text"] = result
            contextualized.append(chunk)
    return contextualized
```

#### 6.9 Integration with Existing Ingestion Pipeline

**Modify `backend/app/core/ingestion/pipeline.py`**:
- After chunking (`chunker.py`), call `batch_contextualize_chunks()` to generate contextual prefixes
- Embed `chunk["contextualized_text"]` instead of `chunk["text"]`
- Store `chunk["text"]` (original) in Pinecone metadata `text` field for display
- Store `chunk["contextualized_text"]` in a new metadata field `contextualized_text` (optional, for debugging)
- **BM25/FTS**: Index `contextualized_text` in `searchable_text` tsvector for better keyword matching

**Modify `backend/app/core/ingestion/chunker.py`**:
- No changes to chunking logic itself — contextual prefix is added AFTER chunking, BEFORE embedding
- This keeps the chunker pure (text → chunks) and adds context as a post-processing step

**Backfill strategy for existing 796 SC judgments**:
- Run a one-time backfill script: `backend/scripts/backfill_contextual_embeddings.py`
- For each existing case: load chunks from Pinecone metadata → generate contextual prefix → re-embed → upsert
- Batch size: 100 cases at a time, rate-limited to avoid Pinecone/Gemini throttling
- **Estimated cost**: 796 cases × ~10 chunks × $0.0001/Flash call = ~$0.80 total
- **Estimated time**: ~2 hours with batching

#### 6.10 Phase 2 Testing — Contextual Embeddings
- **Unit test**: Verify `generate_contextual_prefix()` returns text starting with context and ending with original chunk
- **Integration test**: Ingest one test statute with contextual embeddings, verify Pinecone vector has `contextualized_text` metadata
- **Quality test**: Compare retrieval recall for 10 test queries with/without contextual embeddings on a dev Pinecone namespace
- **Regression**: Ensure existing search pipeline works with contextualized vectors (format_search_results_for_llm uses `text` field, which remains the original)

#### 6.11 [Q3] RAPTOR-Style Hierarchical Section Summaries — NEW

**Purpose**: Build RAPTOR-inspired hierarchical summaries during ingestion to give the research agent macro-level judgment context without requiring the full 100-page document. RAPTOR showed 20% absolute accuracy improvement on complex multi-step reasoning tasks.

**Three-level hierarchy** (per judgment):
- **Level 0**: Original chunks (existing, 2000-char, section-tagged) — for fine-grained retrieval
- **Level 1**: Section summaries (1 per section type: FACTS, ISSUES, HOLDINGS, ARGUMENTS, etc.) — NEW, generated by Flash during ingestion
- **Level 2**: Full judgment summary — already stored as `ratio_decidendi` in `cases` table

**Implementation** — `backend/app/core/ingestion/section_summarizer.py` — NEW:
```python
SECTION_SUMMARY_SYSTEM = """You are a legal analyst. Summarize this section of an Indian court judgment in 2-4 sentences.
Preserve: key legal principles, case names cited, statute sections referenced, and the court's reasoning.
Do NOT paraphrase quotes — if a specific holding is important, include the exact phrasing."""

async def generate_section_summaries(
    case_id: str,
    sections: list[dict],  # [{section_type, content}] from case_sections table
    flash_llm: LLMProvider,
) -> list[dict]:
    """Generate Level-1 summaries for each section of a judgment."""
    summaries = []
    tasks = []
    for section in sections:
        if len(section["content"]) < 200:  # Skip trivially short sections
            continue
        tasks.append(flash_llm.generate(
            system=SECTION_SUMMARY_SYSTEM,
            user=f"Section type: {section['section_type']}\n\n{section['content'][:8000]}",
        ))
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for section, result in zip(sections, results):
        if isinstance(result, Exception):
            continue
        summaries.append({
            "case_id": case_id,
            "section_type": section["section_type"],
            "summary_text": result,
            "summary_level": 1,
        })
    return summaries
```

**Pinecone storage**:
- ID format: `{case_id}_summary_{section_type}` (e.g., `abc123_summary_HOLDINGS`)
- Metadata: `{document_type: "case_law", summary_level: 1, section_type: "HOLDINGS", case_id: "...", text: summary_text}`
- Embed the summary text (NOT the full section) — summaries are denser and embed better

**Integration with ingestion pipeline** (`pipeline.py`):
- After `case_sections` are stored in PostgreSQL, call `generate_section_summaries()`
- Embed summaries via `get_embedder().embed_batch()`
- Upsert to Pinecone alongside Level-0 chunk vectors

**Integration with `case_law_worker`** (Phase 1):
- When retrieving results, optionally also retrieve `summary_level: 1` vectors for the same query
- These give the synthesis node section-level context: "The HOLDINGS section of Bachan Singh establishes the rarest-of-rare doctrine..."
- Retrieve at most 3 Level-1 summaries per query (to not bloat context)

**Cost**: ~$0.001/judgment × 35K SC = ~$35 total. ~$0.001/judgment × 100K HC = ~$100 total.
**Not blocking**: This is an ingestion-time enhancement. It can be added after initial ingestion as a backfill, similar to contextual embeddings (6.9).

#### 6.12 [T3] Complete Old↔New Indian Code Mapping — ENHANCE

**Purpose**: India replaced IPC/CrPC/IEA with BNS/BNSS/BSA in July 2024. The existing `expand_statute_references()` in `backend/app/core/search/query.py` has 28 bidirectional mappings. This must become comprehensive — BharatLaw AI promotes this as a key feature, and the SC/HCs still cite old codes extensively.

**Enhancement 1**: Expand mappings from 28 to COMPLETE tables:
- **IPC → BNS**: All ~511 IPC sections mapped to BNS equivalents (some merged, some split, some repealed)
- **CrPC → BNSS**: All ~484 CrPC sections mapped to BNSS equivalents
- **IEA → BSA**: All ~167 IEA sections mapped to BSA equivalents
- Source: Ministry of Home Affairs concordance tables (published July 2024)
- Store in `backend/app/core/legal/code_mappings.py` as frozen dicts

**Enhancement 2**: `statute_worker` auto-searches BOTH old and new codes:
```python
# In statute_worker, when searching for IPC Section 302:
async def statute_worker(state: dict) -> dict:
    task = state["task"]
    # ... existing statute lookup ...

    # [T3] Auto-expand old↔new codes
    expanded = expand_statute_references(task["nl_query"])
    if expanded.new_references:  # IPC 302 → also search BNS 103
        for ref in expanded.new_references:
            additional = await _statute_direct_lookup(ref, db)
            results.extend(additional)
```

**Enhancement 3**: Synthesis prompt instruction:
> "When citing a statute section, ALWAYS include both old and new code references. Format: 'Section 302 IPC (now Section 103 BNS)'. This is critical for Indian practitioners transitioning between codes."

**Enhancement 4**: Statutes `replaces`/`replaced_by` fields in the PostgreSQL `statutes` table (already defined in Section 4.3) should be populated from the complete mapping tables during `ingest_statutes.py`.

#### 6.13 Phase 2 Testing — RAPTOR + Code Mapping
- **RAPTOR unit test**: Verify `generate_section_summaries()` produces non-empty summaries for each section type
- **RAPTOR integration test**: Ingest one test case, verify Pinecone has both Level-0 chunks AND Level-1 summary vectors with correct metadata
- **RAPTOR retrieval test**: Query "rarest of rare doctrine" → verify Level-1 HOLDINGS summary for Bachan Singh appears alongside raw chunks
- **Code mapping unit test**: Verify `expand_statute_references("Section 302 IPC")` returns both IPC 302 AND BNS 103
- **Code mapping completeness test**: Verify all IPC sections have BNS mappings (where applicable), all CrPC→BNSS, all IEA→BSA
- **Code mapping synthesis test**: Verify synthesis output includes both old and new code references

---

## 7. PHASE 3: MULTI-SOURCE WORKERS + INDIAN KANOON + WEB SEARCH (Week 3-4)

**Goal**: Add all remaining workers, including Indian Kanoon API integration. Depends on Phase 1 (graph) + Phase 2 (data).

### Files to Create

#### 7.1 `backend/app/core/interfaces/web_search.py` — NEW
```python
@runtime_checkable
class WebSearchProvider(Protocol):
    async def search(self, query: str, *, max_results: int = 5,
                     search_depth: str = "advanced",
                     include_domains: list[str] | None = None) -> list[dict]: ...
```

#### 7.2 `backend/app/core/interfaces/external_doc.py` — NEW [INDIAN KANOON]
```python
@runtime_checkable
class ExternalDocProvider(Protocol):
    async def search(self, query: str, *, max_results: int = 10,
                     court_filter: str | None = None,
                     from_date: str | None = None,
                     to_date: str | None = None) -> list[dict]: ...

    async def get_document(self, doc_id: str) -> dict: ...

    async def get_fragment(self, doc_id: str, query: str) -> dict: ...

    async def get_metadata(self, doc_id: str) -> dict: ...
```

#### 7.3 `backend/app/core/providers/external/indiankanoon.py` — NEW
```python
class IndianKanoonClient:
    """Indian Kanoon API client. https://api.indiankanoon.org/documentation/"""
    BASE_URL = "https://api.indiankanoon.org"

    def __init__(self, token: str):
        self.token = token
        self.headers = {"Authorization": f"Token {token}"}

    async def search(self, query: str, *, max_results: int = 10, **filters) -> list[dict]:
        """POST /search/?formInput=<query>&pagenum=0"""

    async def get_fragment(self, doc_id: str, query: str) -> dict:
        """POST /docfragment/<doc_id>/?formInput=<query>
        Rs 0.05/req — cheapest option for RAG context"""

    async def get_document(self, doc_id: str) -> dict:
        """POST /doc/<doc_id>/  Rs 0.20/req — full document text"""

    async def get_metadata(self, doc_id: str) -> dict:
        """POST /docmeta/<doc_id>/  Rs 0.02/req — title, citation, date, court"""
```

Tenacity retry: 3 attempts, 2-10s exponential backoff. Rate limit: 2 req/sec.

#### 7.4 `backend/app/core/providers/web_search/tavily.py` — NEW
- Tavily API implementation
- `include_domains=["indiankanoon.org", "scconline.com", "livelaw.in", "barandbench.com"]`
- 10s timeout, returns `[{title, url, content, score}]`
- Tenacity retry: 3 attempts, exponential backoff

#### 7.5 `backend/app/core/config.py` — ADD settings
```python
# Indian Kanoon API
ik_api_token: str = ""
ik_rate_limit: float = 2.0  # requests per second
# Tavily
tavily_api_key: str = ""
web_search_timeout: int = 10
# Research Agent
research_max_refinement_rounds: int = 2
research_max_chunks_per_case: int = 4
research_max_snippet_len: int = 1500   # up from 500
research_max_ratio_len: int = 3000     # up from 1500
# CRAG
research_crag_threshold_correct: float = 0.7    # score >= this → "correct"
research_crag_threshold_ambiguous: float = 0.3  # score >= this → "ambiguous", below → "incorrect"
research_crag_fallback_ratio: float = 0.5       # if >50% incorrect → trigger web fallback
```

**New pip dependency**: `graspologic>=3.4.0` (MIT license, for GraphRAG Leiden community detection)

#### 7.6 `backend/app/core/dependencies.py` — ADD factories
```python
@lru_cache
def get_web_search() -> WebSearchProvider: ...

@lru_cache
def get_ik_client() -> IndianKanoonClient: ...
```

#### 7.7 Worker Implementations in `worker_nodes.py` — ADD remaining workers

**`statute_worker`**: PG `statutes` direct lookup (exact section) + Pinecone `document_type: "statute"` (semantic) + `expand_statute_references()` for IPC↔BNS.

**`constitution_worker`**: PG `statutes` where `document_type='constitution'` + Pinecone filter. Hardcoded lookup for commonly cited articles (14, 19, 21, 32, 226, 136, 141, 142).

**`ik_search_worker`** [NEW — KEY CAPABILITY]:
```python
async def ik_search_worker(state: dict) -> dict:
    """Search Indian Kanoon API for cases not in our database.
    Uses /search/ for discovery + /docfragment/ for targeted passage extraction."""
    task = state["task"]
    ik = get_ik_client()

    # Search IK
    search_results = await ik.search(task["nl_query"], max_results=10)

    results = []
    source_urls = []
    for doc in search_results:
        doc_id = doc["tid"]
        # Get relevant fragment (Rs 0.05 — cheapest way to get context)
        fragment = await ik.get_fragment(doc_id, task["nl_query"])
        results.append({
            "case_id": f"ik:{doc_id}",
            "title": doc.get("title", ""),
            "citation": doc.get("citation", ""),
            "court": doc.get("court", ""),
            "year": doc.get("year"),
            "snippet": fragment.get("fragment", ""),
            "source": "indian_kanoon",
            "ik_doc_id": doc_id,
        })
        source_urls.append(f"https://indiankanoon.org/doc/{doc_id}/")

    return {"worker_results": [WorkerResult(
        task_id=task["task_id"], task_type="ik_search",
        query=task["nl_query"], results=results,
        source_urls=source_urls, metadata={"source": "indian_kanoon"}, error=None,
    )]}
```

**`web_search_worker`**: Tavily API call. 10s timeout. Non-blocking — failure returns empty results. Results include URL attribution.

**`graph_worker`**: `Neo4jGraph.get_neighbors()` for 2-3 hop citation traversal. Also traverses `APPLIES` edges for statute→case queries. Takes case IDs from other workers' results or from query entities.

**`graph_community_worker`** [NEW — GraphRAG Community Detection]:
See Section 7.10 for full implementation details.

**`llm_direct_worker`**: Flash LLM for definitional queries ("What is res judicata?"). Response tagged `source: "llm_knowledge"` — synthesis adds caveats for non-grounded answers.

**All workers include MA-RAG CoT**: Every worker above calls `_generate_worker_cot()` before returning, adding a `reasoning` field to its `WorkerResult`. This was defined in Phase 1 (Section 5.4) but applies to all workers added here.

#### 7.8 `backend/app/core/agents/research.py` — Register all workers
- Add all 9 worker nodes to graph (8 original + graph_community_worker)
- Update `build_research_graph()` signature: `web_search`, `graph_store`, `ik_client`

#### 7.9 `backend/app/api/routes/agents.py` — Pass new deps
```python
graph = build_research_graph(
    llm=llm, flash_llm=get_flash_llm(), embedder=embedder,
    vector_store=vector_store, reranker=reranker,
    graph_store=get_graph_store(), web_search=get_web_search(),
    ik_client=get_ik_client(),  # NEW
    checkpointer=checkpointer,
)
```

#### 7.10 GraphRAG Community Detection — `graph_community_worker` [NEW]

**Purpose**: Implement GraphRAG-style community detection on the Neo4j citation graph. This is our **biggest differentiator amplified** — no Indian legal AI competitor has citation graph communities. A community summary like *"This cluster of 23 cases establishes that Section 498A IPC should not be used as a tool for settling personal scores (Sushil Kumar Sharma v. Union of India line)"* gives the LLM macro-level understanding that individual case retrieval misses.

**Performance**: GraphRAG benchmarks show 80% accuracy on complex queries vs 50% for traditional RAG, with 3.4x improvement on global/thematic questions.

**Architecture**: Two components — (A) Offline batch job that pre-computes communities, (B) Runtime worker that retrieves relevant community summaries.

##### A. Offline Batch Job: `backend/scripts/build_citation_communities.py` — NEW

Runs periodically (after ingestion, or weekly). Uses the Leiden algorithm for community detection.

```python
"""Build citation graph communities using Leiden algorithm + LLM summarization.

Run after ingestion to pre-compute community summaries.
Stores results back in Neo4j as Community nodes + BELONGS_TO edges.

Usage: python -m backend.scripts.build_citation_communities
"""

from graspologic.partition import hierarchical_leiden  # Microsoft's graph library
import networkx as nx

# --- Step 1: Export citation graph from Neo4j to NetworkX ---
async def export_citation_graph(graph_store: GraphStore) -> nx.DiGraph:
    """Export all Case nodes + CITES edges from Neo4j."""
    result = await graph_store.query("""
        MATCH (a:Case)-[r:CITES]->(b:Case)
        RETURN a.id AS source, b.id AS target, r.treatment AS treatment
    """)
    G = nx.DiGraph()
    for record in result:
        G.add_edge(record["source"], record["target"], treatment=record["treatment"])
    return G

# --- Step 2: Run Leiden community detection ---
def detect_communities(G: nx.DiGraph, resolution: float = 1.0) -> dict[str, int]:
    """Run Leiden algorithm. Returns {node_id: community_id}.

    Resolution parameter controls granularity:
    - 1.0 = default (moderate-sized communities, 10-50 cases typical)
    - 0.5 = larger communities (broader legal themes)
    - 2.0 = smaller communities (specific sub-issues)

    Uses hierarchical_leiden from graspologic (Microsoft Research).
    """
    undirected = G.to_undirected()
    partitions = hierarchical_leiden(undirected, max_cluster_size=100, resolution=resolution)
    # Use finest level partitions
    return {node: community for node, community in partitions[0]}

# --- Step 3: Generate community summaries via LLM ---
async def summarize_community(
    community_id: str,
    case_ids: list[str],
    db: AsyncSession,
    flash_llm: LLMProvider,
) -> CommunitySummary:
    """Generate a summary for a citation community.

    Loads case metadata (title, citation, court, year, ratio) for top cases,
    asks Flash to identify the common legal theme + key principles.
    """
    # Load case metadata for community members (top 20 by citation count)
    cases = await db.execute(
        select(Case).where(Case.id.in_(case_ids[:20]))
    )
    case_data = [
        f"- {c.title} ({c.citation}, {c.court}, {c.year})\n  Ratio: {(c.ratio_decidendi or '')[:300]}"
        for c in cases.scalars()
    ]

    summary_response = await flash_llm.generate_structured(
        system=COMMUNITY_SUMMARY_SYSTEM,
        user=f"Community of {len(case_ids)} cases. Top cases:\n" + "\n".join(case_data),
        schema={
            "type": "object",
            "properties": {
                "title": {"type": "string"},           # "Section 498A misuse cluster"
                "summary": {"type": "string"},          # 2-3 paragraph summary
                "legal_principles": {
                    "type": "array",
                    "items": {"type": "string"}
                },
            }
        },
    )

    return CommunitySummary(
        community_id=community_id,
        title=summary_response["title"],
        summary=summary_response["summary"],
        key_cases=case_ids[:5],
        legal_principles=summary_response["legal_principles"],
        size=len(case_ids),
    )

COMMUNITY_SUMMARY_SYSTEM = """You are an expert Indian legal analyst. Given a cluster of related court cases that frequently cite each other, identify:

1. **Title**: A concise name for this legal cluster (e.g., "Anticipatory bail under Section 438 CrPC")
2. **Summary**: A 2-3 paragraph analysis of what legal position this cluster establishes. Include the key evolution of the law through these cases.
3. **Legal Principles**: 3-5 bullet points of the established legal principles from this cluster.

Focus on what a lawyer would need to know when researching this area of law."""

# --- Step 4: Store communities in Neo4j ---
async def store_communities(
    communities: dict[str, CommunitySummary],
    case_communities: dict[str, str],  # {case_id: community_id}
    graph_store: GraphStore,
):
    """Create Community nodes + BELONGS_TO edges in Neo4j."""
    for comm_id, summary in communities.items():
        await graph_store.query("""
            MERGE (c:Community {id: $comm_id})
            SET c.title = $title,
                c.summary = $summary,
                c.legal_principles = $principles,
                c.size = $size,
                c.updated_at = datetime()
        """, {
            "comm_id": comm_id, "title": summary["title"],
            "summary": summary["summary"],
            "principles": summary["legal_principles"],
            "size": summary["size"],
        })

    for case_id, comm_id in case_communities.items():
        await graph_store.query("""
            MATCH (case:Case {id: $case_id}), (comm:Community {id: $comm_id})
            MERGE (case)-[:BELONGS_TO]->(comm)
        """, {"case_id": case_id, "comm_id": comm_id})

# --- Step 5: Embed community summaries for semantic retrieval ---
async def embed_community_summaries(
    communities: dict[str, CommunitySummary],
    embedder: EmbeddingProvider,
    vector_store: VectorStore,
):
    """Embed community summaries into Pinecone for semantic retrieval.
    Uses document_type: "community" metadata filter."""
    texts = [f"{s['title']}\n{s['summary']}" for s in communities.values()]
    embeddings = await embedder.embed_batch(texts)
    vectors = [
        {
            "id": f"community:{comm_id}",
            "values": emb,
            "metadata": {
                "document_type": "community",
                "community_id": comm_id,
                "title": summary["title"],
                "text": summary["summary"][:2000],
                "size": summary["size"],
                "legal_principles": "; ".join(summary["legal_principles"]),
            }
        }
        for (comm_id, summary), emb in zip(communities.items(), embeddings)
    ]
    await vector_store.upsert(vectors)
```

**Dependencies**: Add `graspologic>=3.4.0` to requirements.txt (MIT license, Microsoft Research graph library).

**Estimated metrics**:
- 35K SC cases → ~200-500 communities (Leiden at resolution=1.0)
- LLM cost: ~500 Flash calls × $0.0001 = $0.05 total
- Runtime: ~30 minutes for full rebuild
- Re-run after each major ingestion batch

##### B. Runtime Worker: `graph_community_worker` in `worker_nodes.py`

```python
async def graph_community_worker(state: dict) -> dict:
    """Retrieve relevant citation communities for the research question.

    Two retrieval strategies:
    1. Semantic: Embed the query, search Pinecone for document_type="community"
    2. Graph: If other workers already found cases, look up their communities via BELONGS_TO

    Returns CommunitySummary objects that give the synthesis node macro-level context.
    """
    task = state["task"]
    parent = state.get("parent_state", {})

    community_results = []

    # Strategy 1: Semantic search for relevant communities
    query_embedding = await embedder.embed_text(task["nl_query"])
    pinecone_results = await vector_store.search(
        query_vector=query_embedding,
        top_k=5,
        filters={"document_type": "community"},
    )
    for r in pinecone_results:
        community_results.append({
            "community_id": r.metadata.get("community_id"),
            "title": r.metadata.get("title"),
            "summary": r.metadata.get("text", ""),
            "legal_principles": r.metadata.get("legal_principles", "").split("; "),
            "size": r.metadata.get("size", 0),
            "retrieval_method": "semantic",
            "score": r.score,
        })

    # Strategy 2: Graph lookup from already-found case IDs
    existing_case_ids = []
    for wr in parent.get("worker_results", []):
        for r in wr.get("results", []):
            if cid := r.get("case_id"):
                if not cid.startswith("ik:"):  # Only internal cases
                    existing_case_ids.append(cid)

    if existing_case_ids:
        graph_communities = await graph_store.query("""
            MATCH (case:Case)-[:BELONGS_TO]->(comm:Community)
            WHERE case.id IN $case_ids
            RETURN DISTINCT comm.id AS id, comm.title AS title,
                   comm.summary AS summary, comm.legal_principles AS principles,
                   comm.size AS size, count(case) AS overlap
            ORDER BY overlap DESC
            LIMIT 3
        """, {"case_ids": existing_case_ids[:20]})

        for gc in graph_communities:
            # Avoid duplicates from semantic search
            if not any(cr["community_id"] == gc["id"] for cr in community_results):
                community_results.append({
                    "community_id": gc["id"],
                    "title": gc["title"],
                    "summary": gc["summary"],
                    "legal_principles": gc["principles"],
                    "size": gc["size"],
                    "retrieval_method": "graph_overlap",
                    "overlap_count": gc["overlap"],
                })

    # [MA-RAG] Generate CoT reasoning about communities found
    reasoning = f"Found {len(community_results)} relevant citation communities. "
    if community_results:
        reasoning += f"Top community: '{community_results[0]['title']}' ({community_results[0]['size']} cases). "
        reasoning += "These provide macro-level legal context for synthesis."
    else:
        reasoning += "No pre-computed communities matched — synthesis will rely on individual case analysis."

    return {"worker_results": [WorkerResult(
        task_id=task["task_id"], task_type="graph_community",
        query=task["nl_query"],
        results=community_results,
        source_urls=[], metadata={"source": "graph_community"}, error=None,
        reasoning=reasoning,
    )]}
```

##### C. Integration with `plan_research_node`

The plan_research prompt should generate a `graph_community` task type when:
- The query involves a well-established area of law (e.g., Section 302 IPC, Article 21)
- The query asks about "evolution" or "trends" in case law
- The query asks about conflicting positions across courts

Add to `RESEARCH_PLAN_SCHEMA`:
```python
"task_type": {"type": "string", "enum": [
    "case_law", "named_case", "statute", "constitution",
    "ik_search", "web", "graph", "graph_community",  # NEW
    "llm_direct"
]},
```

##### D. Integration with Synthesis

The `speculative_synthesis` node (Phase 4) consumes `community_summaries` from worker_results:
- Community summaries provide the "forest" view while individual cases provide the "trees"
- Synthesis prompt includes: "Use citation community summaries to frame the broader legal landscape before diving into individual case analysis"
- Community titles make excellent section headings in the Detailed Analysis

##### E. Phase 3 Testing — GraphRAG
- **Unit test**: Mock Neo4j with 50 cases, 3 communities → verify Leiden produces expected clusters
- **Unit test**: Verify `graph_community_worker` retrieves communities via both semantic and graph paths
- **Integration test**: Build communities from real data, verify summaries are legally coherent
- **Quality test**: Compare research output WITH community context vs WITHOUT → expect better thematic organization

---

## 8. PHASE 4: STRUCTURED FOOTNOTES & OUTPUT QUALITY (Week 5)

**Goal**: Match and exceed competitor output quality. See Section 12 for full output format spec.

### Changes

#### 8.1 Synthesis Prompt Overhaul (`prompts.py`)

Rewrite `RESEARCH_SYNTHESIZE_SYSTEM` and `RESEARCH_SYNTHESIZE_USER` to produce the format in Section 12:
- Executive Summary (answer-first, 3-5 bullets with inline citations)
- Quick Reference Table (case name | citation | court | year | bench | holding | strength)
- IRAC Analysis per legal issue
- Reconciliation Table for multi-position issues (fact pattern → outcome)
- Conclusion with practical effect
- Footnotes with source URLs

Key instruction additions:
```
When quoting from a judgment, use ONLY text that appears in the "Extracted Passages"
provided. Enclose verbatim quotes in quotation marks. Mark any paraphrased content
with [paraphrased]. Never fabricate quoted text.

For each citation, use the format [^N] where N is the footnote number.
Each footnote must include: case citation, court, year, source URL, and a brief excerpt.

Use citation community summaries (if provided) to frame the broader legal landscape
before diving into individual case analysis. Community titles make excellent section headings.

Worker reasoning summaries are provided for each search task — use them to understand
tensions and gaps before writing your analysis.
```

#### 8.2 Speculative RAG Synthesis with Contradictions — `speculative_synthesis_with_contradictions_node` [ENHANCED]

**Purpose**: Speculative RAG pattern with two critical speed optimizations:
- **[S1]** Contradiction detection is merged INTO the Pro verification call — eliminates a separate Pro call (~30-40s saved)
- **[S5]** Pro output is STREAMED token-by-token via SSE — user sees first tokens at ~25s TTFT instead of waiting ~40s for full response

**Quality safeguard for S1**: The Pro verifier already receives ALL evidence and ALL drafts — it has strictly MORE context than the old standalone `contradictions` node had. Contradiction detection quality is unchanged or improved because the model reasons about contradictions while synthesizing, seeing the full picture simultaneously rather than detecting contradictions in isolation before synthesis.

**How it works**:
1. **Partition evidence** into 3 subsets based on different strategies:
   - **Strategy A ("relevance")**: Top results by CRAG relevance score — what's most directly on-point
   - **Strategy B ("authority")**: Top results by precedent strength (BINDING first, then PERSUASIVE) — what's most legally authoritative
   - **Strategy C ("breadth")**: One result per source type (case_law, statute, constitution, IK, web, community) — maximum source diversity
2. **Fan out 3 Flash drafts** in parallel, each generating a complete memo from its evidence subset
3. **Pro verifier/merger/contradiction-detector** [S1]: A SINGLE Pro call that:
   - Detects contradictions between holdings (formerly separate `contradictions` node)
   - Selects the strongest structural organization from the 3 drafts
   - Merges insights that appear in one draft but not others
   - Resolves contradictions (prefer stronger authority)
   - Produces the final unified memo with a "Contradictions & Conflicts" section
4. **[S5]** Pro output is streamed — SSE `memo_stream` events sent as tokens generate

```python
async def speculative_synthesis_with_contradictions_node(
    state: dict, llm: LLMProvider, flash_llm: LLMProvider,
    stream_callback: Callable[[str], None] | None = None,  # [S5] SSE streaming callback
) -> dict:
    """Speculative RAG: 3x Flash drafts → Pro verification/merge/contradiction-detection.

    [S1] Contradictions detected inside Pro merge (no separate Pro call).
    [S5] Pro output streamed to frontend via stream_callback.
    """
    results = state["worker_results"]
    passages = state.get("extracted_passages", [])
    relevance_scores = {s["case_id"]: s["score"] for s in state.get("relevance_scores", [])}
    worker_reasonings = state.get("worker_reasonings", [])
    community_summaries = [
        r for wr in results if wr["task_type"] == "graph_community"
        for r in wr["results"]
    ]

    # --- Partition evidence into 3 strategies ---
    all_results = []
    for wr in results:
        if wr["task_type"] != "graph_community":
            all_results.extend(wr["results"])

    # Strategy A: Top by CRAG relevance score
    strategy_a = sorted(all_results, key=lambda r: relevance_scores.get(r.get("case_id", ""), 0.5), reverse=True)[:15]

    # Strategy B: Top by precedent strength (binding > persuasive > distinguishable)
    strength_order = {"BINDING": 4, "PERSUASIVE": 3, "DISTINGUISHABLE": 2, "OVERRULED": 1}
    strategy_b = sorted(
        all_results,
        key=lambda r: strength_order.get(r.get("precedent_strength", "PERSUASIVE"), 2),
        reverse=True,
    )[:15]

    # Strategy C: Max diversity — 2-3 per source type
    strategy_c = []
    by_source = {}
    for r in all_results:
        source = r.get("source", "internal")
        by_source.setdefault(source, []).append(r)
    for source, items in by_source.items():
        strategy_c.extend(items[:3])
    strategy_c = strategy_c[:15]

    # --- Fan out 3 Flash drafts in parallel ---
    shared_context = {
        "query": state["rewritten_query"],
        "passages": format_extracted_passages(passages),
        "worker_reasoning": "\n".join(worker_reasonings),
        "communities": format_community_summaries(community_summaries),
    }

    async def generate_draft(strategy_name: str, evidence_subset: list[dict]) -> SynthesisDraft:
        formatted_evidence = format_search_results_for_llm_extended(evidence_subset)
        memo = await flash_llm.generate(
            system=RESEARCH_SYNTHESIZE_SYSTEM,
            user=RESEARCH_SYNTHESIZE_USER.format(
                query=shared_context["query"],
                evidence=formatted_evidence,
                passages=shared_context["passages"],
                worker_reasoning=shared_context["worker_reasoning"],
                communities=shared_context["communities"],
                strategy_hint=f"Focus on {strategy_name} — organize by {strategy_name}.",
            ),
        )
        return SynthesisDraft(
            draft_id=str(uuid4()),
            strategy=strategy_name,
            memo_text=memo,
            confidence=0.0,  # Pro verifier will assess
            sources_used=[r.get("citation", "") for r in evidence_subset if r.get("citation")],
        )

    drafts = await asyncio.gather(
        generate_draft("relevance", strategy_a),
        generate_draft("authority", strategy_b),
        generate_draft("breadth", strategy_c),
    )

    # --- Pro verifier/merger ---
    all_formatted = format_search_results_for_llm_extended(all_results[:30])
    verification_prompt = f"""You are a senior legal researcher reviewing 3 draft research memos, each written from a different perspective on the same evidence.

RESEARCH QUESTION: {state["rewritten_query"]}

COMPLETE EVIDENCE (all sources):
{all_formatted}

EXTRACTED PASSAGES (verbatim quotes):
{shared_context["passages"]}

CITATION COMMUNITY CONTEXT:
{shared_context["communities"]}

WORKER REASONING:
{shared_context["worker_reasoning"]}

--- DRAFT A (organized by relevance) ---
{drafts[0].memo_text}

--- DRAFT B (organized by authority/precedent) ---
{drafts[1].memo_text}

--- DRAFT C (organized by source diversity) ---
{drafts[2].memo_text}

---

Produce the FINAL research memo by:
1. [S1] FIRST, systematically identify contradictions between holdings in the evidence:
   - Compare holdings across cases on the same legal issue
   - Note where courts reached different conclusions on similar facts
   - Identify any overruled cases that other results still rely on
   - Document these in the "Contradictions & Conflicts" section
2. Select the best structural organization from the 3 drafts
3. Merge unique insights from each draft that others missed
4. Resolve any contradictions between drafts (prefer the one with stronger authority)
5. Ensure ALL verbatim quotes come from the Extracted Passages — remove any not found there
6. Follow the output format specification (Executive Summary → Quick Reference Table → Detailed Analysis → Contradictions & Conflicts → Precedent Network → Conclusion → Footnotes → Research Audit)
7. Include confidence assessment with component breakdown

IMPORTANT: The "Contradictions & Conflicts" section MUST be present even if empty (write "No contradictions detected" if none found). This replaces the previous standalone contradiction detection step."""

    # [S5] Stream Pro output to frontend for progressive rendering
    if stream_callback:
        final_memo_chunks = []
        async for chunk in llm.stream(
            system=RESEARCH_SYNTHESIZE_SYSTEM,
            user=verification_prompt,
        ):
            final_memo_chunks.append(chunk)
            stream_callback(chunk)  # SSE memo_stream event
        final_memo = "".join(final_memo_chunks)
    else:
        final_memo = await llm.generate(
            system=RESEARCH_SYNTHESIZE_SYSTEM,
            user=verification_prompt,
        )

    # --- Post-processing (same as original 8.2) ---
    footnotes = parse_footnotes(final_memo, all_results, state.get("source_attribution", {}))
    source_attribution = build_source_attribution(all_results)
    research_audit = build_research_audit(state)
    confidence = calculate_confidence_detailed(...)

    return {
        "draft_memo": final_memo,
        "synthesis_drafts": list(drafts),
        "footnotes": footnotes,
        "source_attribution": source_attribution,
        "research_audit": research_audit,
        "confidence": confidence.overall,
    }
```

**Cost analysis** (with S1 merged contradictions):
- 3 Flash draft calls: ~$0.003 total (3 × ~150K input tokens × $0.00000075/token)
- 1 Pro verification+contradiction call: ~$0.018 (3 drafts + evidence + contradiction instructions ≈ 550K input tokens × $0.000003/token)
- **Total: ~$0.021/synthesis+contradictions** vs ~$0.030 for separate contradictions+synthesis = **30% cost SAVINGS**
- **Latency**: Flash drafts in parallel ≈ 5s + Pro merge ≈ 25-30s TTFT (but streamed [S5])
- **Actual wall-clock**: ~30-35s total, but **user sees first tokens at ~25s** → perceived wait ~5-10s
- **Quality**: 3 diverse perspectives + contradiction detection in full context → better than separate steps

**Helper functions** (add to `common.py`):
```python
def format_extracted_passages(passages: list[ExtractedPassage]) -> str:
    """Format passages for synthesis prompt."""
    return "\n".join(
        f"[{p['citation']}] ({p['source_field']}): \"{p['passage']}\""
        for p in passages
    )

def format_community_summaries(communities: list[dict]) -> str:
    """Format GraphRAG community summaries for synthesis."""
    if not communities:
        return "No citation community summaries available."
    return "\n\n".join(
        f"### Community: {c['title']} ({c.get('size', '?')} cases)\n{c['summary']}"
        for c in communities[:5]
    )
```

#### 8.2a Post-Processing (Footnotes & Audit) — applies to `speculative_synthesis_node` output

Post-processing after Pro verifier generates final memo:
1. Parse footnote references `[^N]` from memo text
2. Build `footnotes` list with structured data: number, citation, source_type, source_url, case_id, excerpt, is_used
3. Build `source_attribution` dict
4. Build `research_audit`: total_sources_searched, sources_cited, sources_unused
5. Include unused sources (searched but not cited) in footnotes with `is_used: false`

#### 8.3 Enhanced `verify_citations_node` — [Q6] Dual-Stage + [T4] Zero-Tolerance Guardrail

**Critical context**: The Indian Supreme Court (Feb 2026) flagged an "alarming" trend of AI-drafted petitions citing non-existent judgments. The Bombay HC imposed costs on a litigant for AI-generated fake citations. Stanford research shows 17-33% hallucination rates in Westlaw/Lexis. This node is our most important trust feature.

**[Q6] Stage 1: Deterministic Verification** (instant, free, 100% reliable):
```python
async def _deterministic_verify(memo: str, footnotes: list[Footnote],
                                 extracted_passages: list[ExtractedPassage],
                                 db: AsyncSession, graph_store: GraphStore) -> list[dict]:
    """Instant deterministic checks — no LLM needed."""
    issues = []

    # 1. Footnote reference completeness: every [^N] has a footnote entry
    refs_in_memo = set(re.findall(r'\[\^(\d+)\]', memo))
    footnote_numbers = {str(f["number"]) for f in footnotes}
    for ref in refs_in_memo - footnote_numbers:
        issues.append({"type": "missing_footnote", "ref": ref, "severity": "HIGH"})

    # 2. Citation format validation: matches known Indian citation patterns
    # Patterns: (YYYY) X SCC XXX, AIR YYYY SC XXX, YYYY:INSC:NNNN, etc.
    for fn in footnotes:
        if not _matches_indian_citation_pattern(fn["citation"]):
            issues.append({"type": "invalid_citation_format", "footnote": fn["number"],
                          "citation": fn["citation"], "severity": "MEDIUM"})

    # 3. Quote verification: every quoted string in memo appears in extracted_passages
    quotes_in_memo = re.findall(r'"([^"]{20,})"', memo)  # Quotes > 20 chars
    passage_texts = {p["passage"] for p in extracted_passages}
    for quote in quotes_in_memo:
        if not any(fuzz.partial_ratio(quote, p) > 85 for p in passage_texts):
            issues.append({"type": "unverified_quote", "quote": quote[:100],
                          "severity": "HIGH"})

    # 4. Overruled case check: cross-reference against Neo4j treatment edges
    cited_case_ids = [fn["case_id"] for fn in footnotes if fn.get("case_id")]
    for case_id in cited_case_ids:
        overruled = await graph_store.query(
            "MATCH (c:Case {id: $id})<-[r:CITES {treatment: 'overruled'}]-(newer:Case) "
            "RETURN newer.title, newer.citation LIMIT 1",
            {"id": case_id}
        )
        if overruled:
            issues.append({"type": "cites_overruled_case", "case_id": case_id,
                          "overruled_by": overruled[0], "severity": "HIGH"})

    # 5. URL validation: internal case_ids exist in DB, IK URLs well-formed
    for fn in footnotes:
        if fn.get("case_id") and not fn["case_id"].startswith("ik:"):
            exists = await db.execute(select(Case.id).where(Case.id == fn["case_id"]))
            if not exists.scalar():
                issues.append({"type": "nonexistent_case_id", "case_id": fn["case_id"],
                              "footnote": fn["number"], "severity": "CRITICAL"})

    return issues
```

**[T4] Zero-Tolerance Citation Guardrail** — every citation verified against primary sources:
```python
async def _verify_citations_against_sources(
    footnotes: list[Footnote], db: AsyncSession,
    ik_client: IndianKanoonClient | None, graph_store: GraphStore,
) -> list[Footnote]:
    """[T4] Verify every citation against at least ONE primary source.
    Unverifiable citations are REMOVED from the memo."""
    verified_footnotes = []
    for fn in footnotes:
        status = "unverified"

        # Check 1: PostgreSQL cases table
        if fn.get("case_id") and not fn["case_id"].startswith("ik:"):
            exists = await db.execute(select(Case.id).where(Case.id == fn["case_id"]))
            if exists.scalar():
                status = "verified_pg"

        # Check 2: Indian Kanoon API (/docmeta/, Rs 0.02 each)
        if status == "unverified" and ik_client and fn.get("citation"):
            try:
                ik_results = await ik_client.search(fn["citation"], max_results=1)
                if ik_results:
                    status = "verified_ik"
            except Exception:
                pass  # IK failure is non-fatal

        # Check 3: Neo4j Case node
        if status == "unverified" and fn.get("citation"):
            neo4j_match = await graph_store.query(
                "MATCH (c:Case) WHERE c.citation CONTAINS $cit RETURN c.id LIMIT 1",
                {"cit": fn["citation"][:30]}
            )
            if neo4j_match:
                status = "verified_neo4j"

        fn["verification_status"] = status
        fn["verified_against"] = status.replace("verified_", "") if status != "unverified" else "none"

        if status == "unverified":
            # HARD FAIL: replace in memo with warning
            fn["citation"] = f"[CITATION REMOVED — unable to verify: {fn['citation']}]"
            fn["is_used"] = False
            logger.warning(f"T4 guardrail: removed unverifiable citation footnote {fn['number']}: {fn['citation']}")

        verified_footnotes.append(fn)
    return verified_footnotes
```

**[Q6] Stage 2: LLM Verification** (existing, for semantic checks):
- Does the cited case actually support the proposition it's cited for?
- Is the legal reasoning logically sound?
- Are there misgrounded citations (correct law, wrong source)?
- Stage 2 runs AFTER Stage 1 — only on citations that passed deterministic checks

**Memo banner** (added to final output):
- If ALL citations verified: `"✓ All citations in this memo have been verified against primary sources (PostgreSQL / Indian Kanoon / Neo4j)"`
- If ANY removed: `"⚠ N citations could not be verified against primary sources and have been flagged"`
- Banner text stored in `research_audit["verification_banner"]`

#### 8.3a [Q4] `legal_quality_check_node` — LeMAJ-Inspired Verification — NEW

**Purpose**: After citation verification, check the **legal reasoning quality** of the memo. Citation verification asks "does this case exist?" — legal quality check asks "is this analysis logically sound?"

**Node**: `legal_quality_check_node(state, llm)` — Flash LLM, ~3s

```python
LEGAL_QUALITY_CHECK_SYSTEM = """You are a senior Indian legal editor reviewing a research memo for quality.
Decompose the memo into discrete Legal Data Points (claims), and evaluate each:

1. SUPPORTED CLAIMS: Does the evidence actually support this claim? Check against provided search results.
2. OMISSIONS: Are there important cases/statutes in the evidence that the memo SHOULD cite but doesn't?
3. LOGICAL COHERENCE: Does the IRAC analysis flow correctly? Are conclusions supported by the analysis?
4. MISAPPLICATION: Is any authority applied to the wrong legal issue?

Score 0.0-1.0. Flag specific issues with line references."""

LEGAL_QUALITY_CHECK_SCHEMA = {
    "type": "object",
    "properties": {
        "overall_score": {"type": "number"},
        "data_points": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "claim": {"type": "string"},
                    "supported": {"type": "boolean"},
                    "evidence_id": {"type": "string", "nullable": True},
                    "issue": {"type": "string", "nullable": True},
                }
            }
        },
        "omissions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "missed_authority": {"type": "string"},
                    "relevance": {"type": "string"},
                }
            }
        },
        "logical_issues": {"type": "array", "items": {"type": "string"}},
    }
}

async def legal_quality_check_node(state: dict, llm: LLMProvider) -> dict:
    """[Q4] LeMAJ-inspired legal reasoning verification."""
    memo = state["draft_memo"]
    evidence = format_search_results_for_llm_extended(
        [r for wr in state["worker_results"] for r in wr["results"]][:30]
    )
    result = await llm.generate_structured(
        system=LEGAL_QUALITY_CHECK_SYSTEM,
        user=f"MEMO:\n{memo}\n\nEVIDENCE:\n{evidence}",
        schema=LEGAL_QUALITY_CHECK_SCHEMA,
    )

    quality_result = LegalQualityResult(
        overall_score=result.get("overall_score", 0.0),
        data_points=result.get("data_points", []),
        omissions=result.get("omissions", []),
        logical_issues=result.get("logical_issues", []),
        pass_threshold=result.get("overall_score", 0.0) >= 0.7,
    )

    # If quality is below threshold, add issues to the HITL checkpoint
    # so the lawyer sees specific concerns before approving
    return {"legal_quality_result": quality_result}
```

**Integration with checkpoint_memo**: If `legal_quality_result.pass_threshold` is False, the HITL checkpoint message includes:
> "⚠ Legal quality check flagged N issues: [list of logical_issues + unsupported claims + omissions]. Please review carefully."

This gives the lawyer specific things to verify, rather than a generic "review this memo."

#### 8.4 SSE Event Enhancement — [T1] Research Process Visualization

**[T1] Full Research Process Visualization** — rich SSE events throughout the ENTIRE pipeline, not just synthesis. This is the #1 trust feature cited by lawyers when asked why they trust AI research tools. CoCounsel and Perplexity Deep Research both show the agent thinking in real-time.

**Event types across the full pipeline**:
```
# After plan_research — show the research strategy
data: {"type": "plan", "data": {"tasks": [...], "named_cases": [...], "total_workers": 6}}

# During worker dispatch — show each search starting
data: {"type": "searching", "data": {"worker": "case_law", "query": "Section 302 IPC...", "status": "running"}}
data: {"type": "searching", "data": {"worker": "ik_search", "query": "Bachan Singh...", "status": "running"}}

# As each worker completes — show results found
data: {"type": "found", "data": {"worker": "case_law", "count": 12, "top_case": "Bachan Singh v. State of Punjab"}}
data: {"type": "found", "data": {"worker": "named_case", "count": 3, "top_case": "Machhi Singh v. State of Punjab"}}

# After CRAG evaluation — show filtering results
data: {"type": "evaluating", "data": {"total": 45, "correct": 28, "ambiguous": 10, "filtered": 7, "deep_read": 4}}

# After reflection — show any strategy pivots
data: {"type": "reflection", "data": {"insights": "Found BNS replaced IPC...", "pivot": true, "new_tasks": 2}}

# During gap analysis — show refinement
data: {"type": "gap", "data": {"gaps": ["No overruling cases found for..."], "refinement_round": 1, "conditioned_on": ["Bachan Singh"]}}

# During speculative drafts — show parallel generation
data: {"type": "drafting", "data": {"strategy": "relevance", "status": "generating"}}
data: {"type": "drafting", "data": {"strategy": "authority", "status": "complete"}}
data: {"type": "drafting", "data": {"strategy": "breadth", "status": "complete"}}

# During Pro merge — streamed tokens [S5]
data: {"type": "memo_stream", "chunk": "## Executive Summary\n\nBased on"}
data: {"type": "memo_stream", "chunk": " the analysis of 15 cases..."}

# After verification — show trust indicators
data: {"type": "verification", "data": {"citations_verified": 14, "citations_removed": 1, "quotes_verified": 8, "quality_score": 0.85}}

# Final memo with all structured data
data: {"type": "memo", "data": {"draft_memo": "...", "confidence": 0.85, ...}}
```

**Implementation**: Add `emit_status(event_type, data)` helper that writes to the SSE stream. Call it from each node function:
```python
async def emit_status(stream: AsyncGenerator, event_type: str, data: dict):
    """Emit a research process event to the SSE stream."""
    await stream.send(f"data: {json.dumps({'type': event_type, 'data': data})}\n\n")
```

Each node calls `emit_status()` at key points. The stream reference is passed via the `config` dict in LangGraph (same pattern as the existing `stream_callback` for S5).

**Frontend**: Renders a collapsible "Research Process" panel with a live activity feed. Each event type gets a distinct icon and color. The panel stays visible alongside the memo, so the lawyer can cross-reference "this citation came from the IK search worker" while reading.

The frontend receives `memo_stream` chunks and renders them progressively using react-markdown. Once the final `memo` event arrives, it replaces the streamed content with the fully-processed version (with verified footnotes, source URLs, etc.).

**Implementation in `_stream_agent_events()`**:
```python
# In the SSE streaming loop, detect synthesis node streaming:
if node_name == "speculative_synthesis_with_contradictions":
    # Pass SSE callback to synthesis node
    async def stream_memo_chunk(chunk: str):
        yield f"data: {json.dumps({'type': 'memo_stream', 'chunk': chunk})}\n\n"

    # The synthesis node calls stream_callback(chunk) internally
```

`memo` event payload (sent once after synthesis + verification + quality check completes):
```json
{
  "draft_memo": "...",
  "confidence": 0.85,
  "contradictions": [...],
  "footnotes": [...],
  "source_attribution": {...},
  "research_audit": {
    "total_sources_searched": 51,
    "sources_cited": 15,
    "sources_unused": 36,
    "searches_executed": 9,
    "refinement_rounds": 1,
    "verification_banner": "✓ All citations verified against primary sources",
    "citations_verified": 15,
    "citations_removed": 0,
    "deep_reads_performed": 4,
    "strategy_pivots": 0
  },
  "legal_quality_result": {
    "overall_score": 0.85,
    "pass_threshold": true,
    "omissions": [],
    "logical_issues": []
  }
}
```

#### 8.5 Frontend Rendering
- **[S5] Progressive memo rendering**: `memo_stream` chunks rendered via react-markdown as they arrive. Loading spinner replaced by actual content appearing section-by-section.
- Footnotes rendered as clickable links: `/case/{case_id}` for internal cases, Indian Kanoon URL for external
- Footnote hover preview: shows excerpt from source
- Research audit trail: collapsible "Sources" section showing all searched sources
- Precedent strength badges (color-coded) in Quick Reference Table
- Treatment warnings prominently displayed for overruled cases

---

## 9. PHASE 5: POLISH & PRODUCTION HARDENING (Week 6)

- **Per-worker timeouts**: web=10s, ik_search=15s, case_law=30s, graph=15s, graph_community=10s, statute=20s
- **Cost tracking**: Log IK API usage (Rs per request), LLM tokens per node, total cost per research run
- **Observability**: Structured logging with worker_type, task_id, timing, data_tier
- **Confidence formula update**: Add source_diversity factor (bonus for multi-tier results), evidence_gap_coverage factor
- **Indian Kanoon rate limiting**: Token bucket at 2 req/sec, circuit breaker on 429s
- **Load testing** with complex multi-issue queries
- **Gap analysis prompt tuning** from real-world testing
- **Daily SC ingestion**: Scrape `main.sci.gov.in` for new judgments (skeleton at `backend/scripts/daily_ingest.py`)

### [S8] Redis Caching Strategy

Multi-layer caching to eliminate redundant work. Uses existing Upstash Redis (prod) / local Redis (dev).

**Layer 1: Full research memo cache** — Highest impact for repeat queries
- Key: `research:memo:{hash(normalized_query)}`
- Value: Complete memo + footnotes + audit trail
- TTL: **24 hours**
- Hit rate estimate: ~15-25% (common legal queries repeat frequently: "Section 302 IPC", "anticipatory bail 438 CrPC")
- **Saves: entire pipeline (~45-55s → ~0.5s)**
- Cache invalidation: On new case ingestion for affected topics (best-effort)

**Layer 2: Search result cache** — Reduces retrieval latency on refinement rounds
- Key: `search:hybrid:{hash(query + filters)}`
- Value: Search results (case_ids + scores + snippets)
- TTL: **1 hour** (short — data freshness matters for search)
- Hit rate: High on refinement rounds (gap analysis re-queries similar terms)
- **Saves: ~3-5s per cache hit**

**Layer 3: IK API result cache** — Reduces external API costs and latency
- Key: `ik:search:{hash(query)}` / `ik:fragment:{doc_id}:{hash(query)}`
- Value: IK API response
- TTL: **24 hours** (IK data changes slowly)
- **Saves: ~2-3s per cache hit + Rs 0.05-0.20/request**

**Layer 4: Embedding cache** — Reduces embedding API calls
- Key: `embed:{hash(text)}`
- Value: 1536-dim vector
- TTL: **7 days** (embeddings don't change for same model)
- **Saves: ~0.3s per cache hit**
- Note: Only cache for research queries, not ingestion (different access patterns)

**Layer 5: Community summary cache** — Pre-computed summaries rarely change
- Key: `community:{community_id}`
- Value: CommunitySummary
- TTL: **7 days** (invalidated on community rebuild)
- **Saves: Pinecone + Neo4j query latency**

**Implementation pattern** (consistent across all layers):
```python
async def cached_hybrid_search(query: str, redis: Redis, **kwargs) -> list[dict]:
    cache_key = f"search:hybrid:{hashlib.sha256(f'{query}:{kwargs}'.encode()).hexdigest()[:16]}"
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)
    results = await parallel_hybrid_search(query, **kwargs)
    await redis.setex(cache_key, 3600, json.dumps(results, default=str))  # 1h TTL
    return results
```

**Quality safeguard**: Cache keys include query normalization (lowercase, strip whitespace, sort filters). Cache is best-effort — on Redis failure, fall through to live query. Memo cache includes a `cached_at` timestamp shown in the UI so lawyers know the result may not reflect the latest case law.

### [S10] Gemini Context Caching for System Prompts

**Purpose**: The Pro synthesis call sends the same large system prompt (~2K tokens) with every request. Gemini 2.5+ context caching discounts cached tokens by 90%.

**Implementation**:
- At startup, create a `CachedContent` object via Gemini API containing:
  - `RESEARCH_SYNTHESIZE_SYSTEM` prompt (static)
  - Output format specification from Section 12 (static)
  - `LEGAL_DISCLAIMER` (static)
  - `HINDI_SYSTEM_SUFFIX` (static, appended only when language=hi)
- All `generate()` / `stream()` calls to Pro reference the cached content
- For Flash calls (which are much cheaper), caching is less impactful — use only for Pro

**Modify `backend/app/core/providers/llm/gemini.py`**:
```python
# Add to GeminiLLM class:
_synthesis_cache: CachedContent | None = None

async def _get_or_create_synthesis_cache(self) -> CachedContent:
    if self._synthesis_cache is None:
        self._synthesis_cache = await genai.CachedContent.create(
            model=self.model_name,
            contents=[{"role": "user", "parts": [{"text": RESEARCH_SYNTHESIZE_SYSTEM + "\n\n" + OUTPUT_FORMAT_SPEC}]}],
            ttl="3600s",  # 1 hour TTL, auto-renew on use
        )
    return self._synthesis_cache
```

**Modify `backend/app/core/config.py`** — add:
```python
gemini_context_cache_enabled: bool = True  # [S10] Enable context caching for Pro synthesis
gemini_context_cache_ttl: int = 3600       # Cache TTL in seconds
```

**Cost impact**: At 100 research runs/day × 2K system prompt tokens × 90% discount = saves ~$0.50/day in Pro input costs. Scales linearly with usage.

### [S11] Semantic Caching (Beyond Hash-Based)

**Purpose**: S8's hash-based cache only catches EXACT query matches. But lawyers often ask the same question with different wording: "punishment for murder under Section 302 IPC" vs "IPC 302 penalty for murder". Semantic caching catches these near-duplicates.

**Architecture**: A lightweight vector index (Redis Stack HNSW) sits BEFORE the S8 hash cache:
1. Embed incoming query via `get_embedder()` (already computed for other purposes)
2. Search the semantic cache index (small — only recent queries, not full corpus)
3. If cosine similarity > 0.92 → return cached memo
4. If miss → proceed to S8 hash cache → if miss → full pipeline

**Implementation** — add to `backend/app/core/search/semantic_cache.py` — NEW:
```python
SEMANTIC_CACHE_THRESHOLD = 0.92  # Conservative — only near-identical queries

class SemanticCache:
    """[S11] Vector-based query cache using Redis Stack HNSW index."""

    def __init__(self, redis: Redis, embedder: EmbeddingProvider):
        self.redis = redis
        self.embedder = embedder
        self._index_name = "research:semantic_cache"

    async def get(self, query: str) -> dict | None:
        """Check if a semantically similar query has been cached."""
        query_embedding = await self.embedder.embed_text(query)
        # Redis Stack vector similarity search
        results = await self.redis.ft(self._index_name).search(
            Query(f"*=>[KNN 1 @embedding $vec AS score]")
            .return_fields("query_text", "memo_hash", "score")
            .dialect(2),
            query_params={"vec": np.array(query_embedding, dtype=np.float32).tobytes()},
        )
        if results.docs and float(results.docs[0].score) >= SEMANTIC_CACHE_THRESHOLD:
            memo_hash = results.docs[0].memo_hash
            cached = await self.redis.get(f"research:memo:{memo_hash}")
            if cached:
                return {**json.loads(cached), "cache_type": "semantic",
                        "original_query": results.docs[0].query_text}
        return None

    async def put(self, query: str, memo_hash: str):
        """Store query embedding for semantic matching."""
        embedding = await self.embedder.embed_text(query)
        await self.redis.hset(f"research:semantic_cache:{memo_hash}", mapping={
            "query_text": query, "memo_hash": memo_hash,
            "embedding": np.array(embedding, dtype=np.float32).tobytes(),
        })
```

**Frontend UX**: When a semantic cache hit occurs, show a banner:
> "Similar query found in cache (original: '...'). Showing cached result from [timestamp]. Click 'Run Fresh' to re-execute."

**Quality safeguard**: Threshold 0.92 is deliberately conservative. At this level, only near-identical queries match — "Section 302 IPC punishment" ↔ "punishment under Section 302 IPC" would match, but "Section 302 IPC murder" ↔ "Section 304 IPC culpable homicide" would NOT match (different legal concepts despite similar structure).

---

## 10. KEY DESIGN DECISIONS

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Data tiers** | Own DB (primary) + IK API (supplementary) + Web (fallback) | Own DB for depth, IK for breadth (28M docs), web for recency |
| **Indian Kanoon** | Official API, not scraping | Explicitly permits RAG, Rs 10K/mo free, legal certainty |
| **Dual queries** | NL + boolean per search task | Competitor does this — catches results one modality misses |
| **Named case retrieval** | LLM names cases → exact citation lookup | Leverages Gemini's legal knowledge for high-precision recall |
| **Per-doc diversity** | max 4 chunks per case | Competitor's "4/file" — prevents result domination |
| **Verbatim extraction** | Dedicated Flash node extracts passages pre-synthesis | Prevents hallucinated quotes — #1 trust issue in legal AI |
| **Context increase** | 1500-char snippet, 3000-char ratio (up from 500/1500) | Gemini has 1M context, we were using <1% |
| **Statute storage** | PG `statutes` + Pinecone `document_type` filter | Exact lookup (PG) + semantic search (Pinecone). One table, one index. |
| **Pinecone strategy** | Single index, metadata filtering | Same perf as namespaces. At 40K-110K vectors, separate indexes = 2x cost for zero benefit. |
| **Web search** | Tavily API | Built for RAG, clean text, $0.01/query, domain filtering |
| **Worker communication** | LangGraph `Send()` + `operator.add` reducer | Native parallel fan-out, each worker appends to shared list |
| **LLM allocation** | Flash: rewrite/plan/classify/evaluate-and-extract/gap-analysis/batch-CoT/contextual-prefix/speculative-drafts/fast-path-synthesis. Pro: speculative-merge-with-contradictions ONLY (~1 Pro call total) | Flash: TTFT ~0.5s, ~10x cheaper. Pro TTFT ~25s — minimize Pro calls. |
| **Max refinement rounds** | 2 | Balances thoroughness vs cost/latency. 3 rounds rarely add value. |
| **Research audit trail** | Show all sources (used + unused) | Competitor does this — builds trust, enables lawyer verification |
| **Output format** | Table + IRAC + Reconciliation + Footnotes | Matches competitor quality, adds our citation graph advantage |
| **CRAG retrieval evaluator** | Flash scores each result correct/ambiguous/incorrect, filters before synthesis | Catches bad retrievals early — prevents low-quality docs from polluting synthesis. Plug-and-play, no architecture change. (arXiv 2401.15884) |
| **Contextual embeddings** | Flash generates 1-2 sentence context prefix per chunk before embedding | Anthropic's technique: 49% fewer retrieval failures. Critical for statutes (sections lose meaning without act context) and case chunks (need judgment-level framing). Cost: ~$0.001/document. |
| **GraphRAG communities** | Leiden algorithm on citation graph → LLM-summarized community clusters | Our biggest differentiator amplified. No competitor has this. Provides macro-level "forest" view while individual retrieval gives "trees". 80% accuracy on complex queries vs 50% traditional RAG. |
| **Speculative RAG synthesis** | 3x Flash parallel drafts (relevance/authority/breadth) → Pro verifier/merger | Diverse perspectives catch more insights. Based on Wang et al. 2025. |
| **MA-RAG worker CoT** | Single batched Flash call generates CoT for ALL worker results after gather | [S4] Batched CoT is faster (1 call vs N) AND higher quality (sees cross-worker tensions). Based on MA-RAG (EMNLP 2025). |
| **[S1] Merged contradictions** | Contradiction detection merged into Pro synthesis call | Eliminates one entire Pro call (~30-40s). Pro already has all evidence — contradiction detection quality unchanged. |
| **[S2] Parallel rewrite+classify** | Both read original query, run simultaneously | Saves ~1.5s. No quality impact — they're independent. |
| **[S3] Merged CRAG+extract** | CRAG scoring + passage extraction in one Flash call | Saves ~3-4s. Both read same results. Quality: passages only extracted for relevant docs (better than extracting then filtering). |
| **[S5] Streamed synthesis** | Pro output streamed via SSE `memo_stream` events | Perceived latency drops from ~35s to ~5-10s. No quality impact — same output, just progressive delivery. |
| **[S6] Pre-warm embeddings** | Embed planned queries during HITL wait | Saves ~3-5s. Best-effort — falls back to live embedding if plan changes. |
| **[S8] Multi-layer Redis cache** | 5-layer cache: memo/search/IK/embedding/community | Repeat queries ~0.5s. Stale risk managed by TTLs and `cached_at` timestamps in UI. |
| **[S9] Fast path routing** | Simple queries skip full pipeline, use single worker + Flash synthesis | ~5-10s for definitional/citation/statute queries. Quality gate: falls back to full pipeline if <3 results. |
| **[Q1] MC-RAG conditioned retrieval** | Round 2+ queries conditioned on round 1 findings (evidence chains) | Real lawyers follow evidence chains — each finding informs the next query. MC-RAG discovers meaningful citation clusters that independent retrieval misses. |
| **[Q2] A-RAG deep read** | CRAG "ambiguous" results get full HOLDINGS/RATIO section fetch before keep/filter decision | Prevents premature filtering of relevant-but-poorly-chunked results. Costs one extra DB read per ambiguous result (~50ms). |
| **[Q3] RAPTOR hierarchical summaries** | Level 0 (chunks) + Level 1 (section summaries) + Level 2 (ratio_decidendi) generated at ingestion time | Gives synthesis access to pre-computed multi-granularity representations. Reduces synthesis hallucination by providing authoritative section-level context. |
| **[Q4] LeMAJ legal quality check** | Post-verification LLM-as-a-judge: decompose memo into Legal Data Points, verify each against evidence | Catches subtle quality issues (unsupported conclusions, missing qualifications) that pass deterministic verification. Gate before final delivery. |
| **[Q5] Reflection in batch CoT** | Strategy pivot questions embedded in batch_worker_cot prompt — zero extra latency | Same Flash call that does CoT also evaluates whether the research strategy needs adjustment. No additional LLM call. |
| **[Q6] Dual-stage citation verification** | Stage 1: deterministic (regex, DB lookup, fuzzy match). Stage 2: LLM semantic verification | Deterministic catches format errors instantly. LLM catches semantic misattributions. Together: near-zero hallucinated citations. |
| **[S10] Gemini context caching** | Cache synthesis system prompt (legal formatting, IRAC template, examples) | 90% cost reduction on cached tokens. System prompt is ~8K tokens, identical across all research runs. |
| **[S11] Semantic caching** | Redis Stack HNSW vector index, cosine > 0.92 = cache hit | Near-duplicate queries ("section 302 IPC punishment" ≈ "punishment under section 302") return cached memo in <1s. |
| **[S12] Parallel Flash batches** | `asyncio.gather()` for evaluate_and_extract batches | Already batched [S3], but batches themselves can run in parallel when multiple worker types return results. |
| **[T1] Research process visualization** | Rich SSE events throughout pipeline: plan, searching, found, evaluating, reflection, gap, drafting, verification, memo | Lawyers need to see the agent working — builds trust that research is thorough, not a black box. |
| **[T3] Complete IPC↔BNS code mapping** | Full old↔new tables: 511 IPC→BNS, 484 CrPC→BNSS, 167 IEA→BSA | Indian law is in transition — lawyers need both old and new code references. Auto-search both when either is mentioned. |
| **[T4] Zero-tolerance citation guardrail** | Every citation verified against PG/IK API/Neo4j; unverifiable citations REMOVED, not flagged | Lawyers lose trust from one bad citation. Better to have 8 verified citations than 10 with 2 unverifiable. |

### What Stays Unchanged
- `VectorStore` Protocol interface
- `hybrid_search()` in `core/search/hybrid.py`
- SSE streaming format in `_stream_agent_events()` (new node names, same structure)
- HITL interrupt/resume mechanism
- Citation verification pipeline (enhanced, not replaced)
- `PineconeStore`, `CohereReranker`, RRF merge logic
- All 4 existing agents (research, case_prep, strategy, drafting) — only research changes

---

## 11. EXISTING CODE REFERENCE

### Critical File Paths

| File | Lines | Role |
|------|-------|------|
| `backend/app/core/agents/state.py` | 81 | All agent state schemas |
| `backend/app/core/agents/research.py` | 221 | Research graph definition |
| `backend/app/core/agents/nodes/research_nodes.py` | 399 | Research node functions |
| `backend/app/core/agents/nodes/common.py` | 604 | Shared search utilities |
| `backend/app/core/agents/nodes/citation_verifier.py` | ~150 | Citation grounding |
| `backend/app/core/agents/routing_utils.py` | 115 | HITL routing utilities |
| `backend/app/core/agents/confidence.py` | 165 | Confidence scoring |
| `backend/app/core/search/hybrid.py` | 806 | Hybrid search orchestrator |
| `backend/app/core/search/query.py` | ~200 | Query understanding |
| `backend/app/core/search/fulltext.py` | ~150 | PostgreSQL FTS |
| `backend/app/core/legal/prompts.py` | ~500 | All LLM prompts |
| `backend/app/core/legal/precedent_strength.py` | ~100 | Stare decisis classification |
| `backend/app/core/legal/treatment.py` | ~100 | Overruling detection |
| `backend/app/core/interfaces/*.py` | ~50 each | Provider protocols |
| `backend/app/core/providers/vector/pinecone_store.py` | ~200 | Pinecone impl |
| `backend/app/core/providers/graph/neo4j_store.py` | ~250 | Neo4j impl |
| `backend/app/core/providers/llm/gemini.py` | ~300 | Gemini impl |
| `backend/app/core/providers/rerankers/cohere_reranker.py` | ~100 | Cohere impl |
| `backend/app/core/dependencies.py` | ~100 | DI factories |
| `backend/app/core/config.py` | 202 | All settings |
| `backend/app/api/routes/agents.py` | ~400 | Agent API routes + SSE streaming |
| `backend/app/core/ingestion/pipeline.py` | ~800 | Judgment ingestion pipeline |
| `backend/app/core/ingestion/chunker.py` | ~200 | Text chunking |
| `backend/app/core/ingestion/contextual_embeddings.py` | NEW | [Contextual Retrieval] Chunk context prefix generation |
| `backend/app/core/agents/nodes/worker_nodes.py` | NEW | All worker node implementations + MA-RAG CoT |
| `backend/scripts/build_citation_communities.py` | NEW | [GraphRAG] Leiden community detection + summarization |
| `backend/scripts/backfill_contextual_embeddings.py` | NEW | One-time backfill for existing case chunks |

### Key Import Patterns

```python
# Interfaces
from app.core.interfaces import EmbeddingProvider, GraphStore, LLMProvider, Reranker, VectorStore

# Search
from app.core.search.hybrid import hybrid_search, SearchResponse, SearchResultItem, rrf_merge, _exact_citation_search
from app.core.search.query import QueryUnderstanding, SearchFilters, expand_statute_references
from app.core.search.fulltext import search_fulltext, FTSResult

# Agents
from app.core.agents.state import (
    ResearchState, ResearchTask, WorkerResult, EvidenceGap, ExtractedPassage, Footnote,
    RelevanceScore, CommunitySummary, SynthesisDraft,  # NEW: CRAG, GraphRAG, Speculative RAG
)
from app.core.agents.nodes.common import (
    parallel_hybrid_search, enrich_results_with_ratio, format_search_results_for_llm,
    format_search_results_for_llm_extended,  # NEW: higher context limits
    collect_grounding_citations, verify_memo_citations, detect_overruled_cases,
    get_citation_neighbors, deduplicate_with_diversity,  # NEW
    format_extracted_passages, format_community_summaries,  # NEW: Speculative RAG helpers
    MAX_RESULTS_FOR_LLM,
)
from app.core.agents.routing_utils import compile_graph, make_checkpoint_node, make_feedback_router
from app.core.agents.confidence import calculate_confidence, calculate_confidence_detailed

# LangGraph
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt, Send

# Legal
from app.core.legal.prompts import *
from app.core.legal.precedent_strength import classify_precedent_strength
from app.core.legal.treatment import has_overruling_language

# DB
from app.db.postgres import async_session_factory
from sqlalchemy.ext.asyncio import AsyncSession

# Dependencies
from app.core.dependencies import (
    get_llm, get_flash_llm, get_embedder, get_vector_store,
    get_graph_store, get_reranker, get_checkpointer,
    get_web_search, get_ik_client,  # NEW
)

# Security
from app.security.sanitizer import sanitize_search_query, detect_prompt_injection
```

---

## 12. OUTPUT FORMAT SPECIFICATION

### 12.1 Target Output Structure

The research memo must match or exceed competitor quality. Structure:

```markdown
# Research Memo: [Research Question Title]

## Executive Summary
[3-5 bullet points answering the research question, with inline citations [^1][^2]]
[Answer-first format — lawyers don't want to read 10 pages to find the answer]

## Quick Reference Table

| # | Case | Citation | Court | Year | Bench | Key Holding | Strength |
|---|------|----------|-------|------|-------|-------------|----------|
| 1 | [Case Name] | (YYYY) X SCC XXX | Supreme Court | YYYY | Division | [1-line holding] | BINDING |
| 2 | ... | ... | ... | ... | ... | ... | PERSUASIVE |

## Detailed Analysis

### Issue 1: [Legal Issue]

**Rule**: [Relevant statutory provisions + leading authorities]
[Include actual statute text from search results]

**Analysis**: [Application of rule to facts, with verbatim extracts]

> "[Exact quoted text from judgment]" [^3]

**Sub-positions**:
[If multiple positions exist, map them in a reconciliation table:]

| Scenario | Applicable Rule | Outcome | Key Authority |
|----------|----------------|---------|---------------|
| [Fact pattern A] | [Rule] | [Result] | [Case] [^4] |
| [Fact pattern B] | [Rule] | [Result] | [Case] [^5] |

### Issue 2: [Next issue...]
[...]

## Contradictions & Conflicts
[If any detected — which holdings conflict, resolution, binding authority]

## Precedent Network
[Cross-referenced cases, citation chains, overruled warnings]
[THIS IS OUR DIFFERENTIATOR — competitor has no citation graph]

## Conclusion
[Numbered practical takeaways with confidence indicator]
[Confidence: HIGH/MEDIUM/LOW with component breakdown]

---

## Footnotes
[^1]: [Full citation] | [Court, Year] | [Source: Internal/Indian Kanoon/Web] | [URL]
  > "[Relevant excerpt from source]"
[^2]: ...

## Research Audit Trail
- **Searches executed**: [N] across [M] sources
- **Sources found**: [X] total ([Y] cited, [Z] reviewed but not cited)
- **Refinement rounds**: [0/1/2]
- **Data sources**: Internal DB ([N] cases), Indian Kanoon ([M] cases), Web ([P] results)

---
*Powered by Smriti Legal AI. Citations verified against source documents. Powered by IKanoon for external case data.*
*This research memo is for informational purposes only and does not constitute legal advice.*
```

### 12.2 Key Output Requirements

1. **Verbatim quotes**: All text in quotation marks must come from `extracted_passages` — never LLM-generated
2. **Footnote linking**: Every footnote must include a URL (internal case viewer or external source)
3. **Precedent strength**: Every case in the Quick Reference Table gets BINDING/PERSUASIVE/DISTINGUISHABLE/OVERRULED label
4. **Treatment warnings**: Overruled cases prominently flagged with warning icon
5. **Research audit**: Show total sources searched vs cited (competitor does 51/15 — we should match)
6. **Reconciliation tables**: For multi-position issues, map fact patterns to outcomes (competitor's best feature)
7. **Citation graph integration**: Show how cited cases relate to each other — our unique differentiator
8. **Source diversity labeling**: Each result tagged with source tier (Internal DB / Indian Kanoon / Web / LLM Knowledge)
9. **Confidence indicator**: Overall + component breakdown (data, legal, consistency)
10. **Hindi support**: If `language=hi`, key sections in Hindi with English legal terms preserved

---

## 13. VERIFICATION PLAN

### Core Tests (Original)
1. **Unit tests**: Each new node in isolation with mocked LLM/Pinecone/Neo4j/IK API
2. **Dual-query test**: Verify plan_research generates both `nl_query` and `boolean_query` per task
3. **Named case test**: Verify named_case_worker finds cases via citation + title fallback
4. **IK API integration test**: Mock IK API responses, verify search → fragment → result pipeline
5. **Passage extraction test**: Verify extracted passages are substring-matched against source text
6. **Send() fan-out test**: Full graph run with multiple worker types, verify results merge via reducer
7. **Gap analysis loop test**: Verify gap detection triggers refinement round, max 2 rounds enforced
8. **Output format test**: Verify memo contains: Executive Summary, Quick Reference Table, IRAC sections, Footnotes, Research Audit
9. **Footnote verification test**: Verify all `[^N]` references have corresponding footnote entries with URLs

### CRAG Tests
10. **CRAG scoring test**: Mock 15 results (5 correct, 5 ambiguous, 5 incorrect) → verify scoring + classification matches expectations
11. **CRAG filtering test**: Verify "incorrect" results are removed from downstream processing, "ambiguous" kept but flagged
12. **CRAG→gap_analysis test**: When >50% results are "incorrect", verify `web_fallback_needed` triggers IK/web refinement tasks
13. **CRAG regression test**: Verify CRAG doesn't filter results that are actually relevant (test with known-good legal queries)

### Contextual Embeddings Tests
14. **Prefix generation test**: Verify `generate_contextual_prefix()` output contains both context and original text
15. **Statute contextual test**: Verify IPC Section 302 gets prefix mentioning "BNS Section 103 replacement"
16. **Retrieval quality A/B test**: Compare recall@10 for 20 queries with/without contextual embeddings
17. **Backfill test**: Run backfill on 10 test cases, verify Pinecone vectors updated with new embeddings

### MA-RAG CoT Tests
18. **Worker reasoning test**: Verify every worker type returns non-empty `reasoning` field
19. **CoT quality test**: Verify reasoning mentions key findings, tensions, and gaps (not just "found N results")
20. **CoT→synthesis test**: Verify synthesis prompt receives and references worker reasonings

### GraphRAG Community Tests
21. **Leiden clustering test**: Mock graph with 50 cases, 3 known clusters → verify community assignment
22. **Community summary test**: Verify LLM generates coherent legal summaries from case clusters
23. **Semantic retrieval test**: Embed community summaries, verify query "anticipatory bail" finds relevant communities
24. **Graph overlap test**: When worker finds case_id X, verify community_worker retrieves X's community
25. **Community→synthesis test**: Verify synthesis uses community context in Detailed Analysis framing

### Speculative RAG Tests
26. **Draft diversity test**: Verify 3 Flash drafts use different evidence subsets (relevance/authority/breadth)
27. **Draft quality test**: Each Flash draft should be a structurally valid memo (has Executive Summary, Table, Analysis)
28. **Pro merge test**: Verify Pro verifier produces final memo that incorporates unique insights from multiple drafts
29. **Speculative vs single test**: Compare final memo quality (speculative 3-draft vs single Pro call) on 5 test queries

### Speed Optimization Tests (S1-S9)
30. **[S1] Merged contradictions quality test**: Compare contradiction detection output from merged synthesis vs standalone node on 5 queries with known contradictions. Merged output must identify ALL contradictions the standalone found (zero regression).
31. **[S1] Contradictions section present test**: Verify every memo output contains "Contradictions & Conflicts" section (even if "No contradictions detected")
32. **[S2] Parallel rewrite+classify test**: Verify both nodes complete and results are available for plan_research. Measure wall-clock: must be ≤ max(rewrite_time, classify_time) + 0.5s overhead, NOT sum.
33. **[S3] Merged evaluate_and_extract test**: Verify passages are ONLY extracted for correct/ambiguous documents (never for incorrect). Compare passage quality vs separate extraction on 10 results.
34. **[S4] Batched CoT quality test**: Compare batched CoT output vs per-worker CoT on 3 test queries. Verify batched CoT identifies cross-worker tensions that per-worker missed.
35. **[S5] Streaming test**: Verify `memo_stream` SSE events are emitted during Pro generation. Measure time-to-first-stream-event: must be ≤ Pro TTFT + 2s. Verify final `memo` event matches concatenated stream chunks.
36. **[S6] Pre-warm test**: Verify pre-warmed embeddings are used by workers (mock embedder, verify `embed_text()` NOT called when pre-warmed). Verify fallback to live embedding when plan changes during HITL.
37. **[S8] Cache hit test**: Run same query twice, verify second run returns cached result. Verify `cached_at` timestamp is included in response. Verify TTL expiry (set short TTL, wait, verify cache miss).
38. **[S8] Cache invalidation test**: Verify IK cache expires after 24h, search cache after 1h, embedding cache after 7d.
39. **[S9] Fast path routing test**: Query "What is Section 302 IPC?" → verify classified as `simple` → verify fast path (no plan_research, no speculative synthesis). Measure latency: must be ≤ 10s.
40. **[S9] Fast path fallback test**: Query classified as `simple` but single worker returns < 3 results → verify it falls back to full pipeline by re-routing with `complexity = "complex"`.
41. **[S9] Fast path quality test**: Compare fast path output vs full pipeline output for 5 simple queries. Fast path should be correct and sufficient for the query type.
42. **Latency benchmark**: Measure full pipeline latency for 3 complex queries. Target: ≤ 55s actual, ≤ 25s to first streamed token. Log per-node timing breakdown.

### MC-RAG Conditioned Retrieval Tests (Q1)
43. **[Q1] Conditioned query generation test**: Run 2-round query where round 1 finds "Bachan Singh". Verify round 2 queries contain explicit references to Bachan Singh (case name or citation in `conditioning_context`). Round 2 must NOT be generic gap-filling.
44. **[Q1] Evidence chain test**: Run "rarest of rare doctrine" query. Verify the evidence chain: Bachan Singh → Machhi Singh → application cases. All three should appear in final results even though only the first was directly queried.
45. **[Q1] Conditioned vs independent comparison**: Same query, compare conditioned round 2 vs independent round 2 results. Conditioned should surface at least 1 case that independent misses (the "connected but not keyword-similar" case).

### A-RAG Deep Read Tests (Q2)
46. **[Q2] Deep read trigger test**: Mock 10 CRAG results (3 correct, 4 ambiguous, 3 incorrect). Verify deep_read is called exactly 4 times (once per ambiguous result), never for correct or incorrect.
47. **[Q2] Deep read reclassification test**: Mock an ambiguous result where the full HOLDINGS section contains a clear relevant holding. Verify it's reclassified to "correct" after deep_read.
48. **[Q2] Deep read performance test**: Verify deep_read adds ≤200ms per ambiguous result (it's a targeted DB fetch, not a full search).

### Reflection Tests (Q5)
49. **[Q5] Reflection integration test**: Verify `batch_worker_cot_with_reflection_node` returns both `worker_cot` and `strategy_adjustment` fields. Strategy adjustment must be one of: no_change, broaden_scope, narrow_focus, switch_jurisdiction, add_temporal_filter.
50. **[Q5] Reflection triggers gap adjustment**: When reflection returns `broaden_scope`, verify gap_analysis generates broader queries than it would with `no_change`.

### Dual-Stage Verification Tests (Q6)
51. **[Q6] Deterministic stage test**: Mock memo with 5 citations: 1 malformed, 1 non-existent case_id, 1 misquoted passage, 1 overruled case (unmarked), 1 clean. Verify deterministic stage catches exactly the first 4 issues.
52. **[Q6] LLM verification stage test**: Mock memo with citation that is correctly formatted and exists in DB but is semantically misattributed (citation says "held X" but case actually held "not X"). Verify LLM stage catches the semantic mismatch.
53. **[Q6] Zero-tolerance guardrail test (T4)**: Mock memo with 10 citations, 2 unverifiable against any source (PG/IK/Neo4j). Verify final memo has exactly 8 citations — the 2 unverifiable are REMOVED (not flagged, not footnoted).

### LeMAJ Legal Quality Tests (Q4)
54. **[Q4] Quality check decomposition test**: Feed a 3-paragraph memo. Verify `legal_quality_check_node` decomposes it into individual Legal Data Points and scores each.
55. **[Q4] Quality gate test**: Memo with overall_quality < 0.7 should trigger HITL checkpoint with quality issues listed. Memo with overall_quality ≥ 0.7 should pass through automatically.

### RAPTOR Hierarchical Summary Tests (Q3)
56. **[Q3] Section summary generation test**: Feed a case with 5 sections. Verify `generate_section_summaries()` produces 5 Level-1 summaries + 1 Level-2 ratio_decidendi summary.
57. **[Q3] Pinecone storage test**: Verify section summaries are stored with `summary_level: 1` and ratio summaries with `summary_level: 2` in Pinecone metadata.
58. **[Q3] Multi-granularity retrieval test**: Query should retrieve both chunk-level (Level 0) and summary-level (Level 1/2) results. Verify synthesis prompt receives both granularities.

### Code Mapping Tests (T3)
59. **[T3] Bidirectional lookup test**: Query "Section 302 IPC" → verify both IPC 302 AND BNS 103 are searched. Query "Section 103 BNS" → verify both BNS 103 AND IPC 302 are searched.
60. **[T3] Code mapping completeness test**: Verify mapping tables contain 511 IPC→BNS, 484 CrPC→BNSS, 167 IEA→BSA entries (spot-check 10 from each).
61. **[T3] Synthesis dual-code reference test**: Verify synthesis prompt instructs LLM to mention both old and new code when either appears in evidence.

### Process Visualization Tests (T1)
62. **[T1] SSE event coverage test**: Run full pipeline, collect all SSE events. Verify at least one event from each category: plan, searching, found, evaluating, reflection, gap, drafting, verification, memo.
63. **[T1] Event ordering test**: Verify events arrive in logical order (plan before searching, searching before found, etc.). No "found" events before "searching" events.

### Speed Enhancement Tests (S10-S12)
64. **[S10] Context cache creation test**: Verify `_get_or_create_synthesis_cache()` creates a Gemini cached content object on first call and reuses it on subsequent calls within TTL.
65. **[S10] Cache cost test**: Verify cached synthesis calls use ≤10% of normal input token cost (check API billing metadata if available).
66. **[S11] Semantic cache hit test**: Query "punishment under section 302 IPC" → cache result. Query "section 302 IPC punishment" → verify cache hit (cosine > 0.92). Query "anticipatory bail section 438" → verify cache miss.
67. **[S11] Semantic cache invalidation test**: Verify cached memos expire after configured TTL. Verify cache is bypassed when user explicitly requests fresh research.
68. **[S12] Parallel batch test**: Mock 3 worker types returning results. Verify evaluate_and_extract runs 3 batches via `asyncio.gather()` (not sequentially). Measure wall-clock: must be ≤ max(batch_times) + 0.5s, not sum(batch_times).

### E2E Tests (Updated)
69. **Manual E2E**: Query "What are the grounds for anticipatory bail under Section 438 CrPC and how has the Supreme Court interpreted this provision?"
    - Verify: rewrite ∥ classify → complex route → plan → HITL (embeddings pre-warm during wait) → workers (no per-worker CoT) → gather → batch CoT with reflection [Q5] → evaluate+extract with deep_read [Q2] (parallel batches [S12]) → gap analysis with MC-RAG [Q1] → HITL → speculative synthesis with contradictions (streamed, context cached [S10]) → dual-stage verify [Q6] + T4 guardrail → legal quality check [Q4] → HITL → END
    - Verify process visualization [T1]: SSE events emitted at every stage
    - Verify code mapping [T3]: If query mentions IPC/CrPC/IEA, both old and new codes searched
70. **Competitor parity test**: Run the competitor's exact query (Section 20(c) CPC) and verify our output has:
    - Equal or more relevant cases found
    - Verbatim quoted text (not hallucinated)
    - Scenario reconciliation table
    - Footnotes linking to actual sources
    - PLUS: citation graph analysis, community context, precedent strength, contradiction detection, confidence score, verified citations only [T4]
71. **Regression**: Existing 1411 backend tests must pass (plus new tests for Q1-Q6, S10-S12, T1/T3/T4)
72. **Statute ingestion**: Verify `statutes` table populated, Pinecone has `document_type: "statute"` vectors, Neo4j has Statute nodes with APPLIES edges
73. **Community build test**: After ingestion, run `build_citation_communities.py`, verify Neo4j has Community nodes with BELONGS_TO edges
74. **RAPTOR ingestion test**: After ingestion with RAPTOR enabled, verify Pinecone has `summary_level: 1` and `summary_level: 2` vectors for ingested cases
75. **Semantic cache warm-up test**: Run 5 common legal queries, verify all cached. Run slight paraphrases, verify cache hits. Measure latency improvement vs cold queries.

---

## 14. APPENDIX: RESEARCH REFERENCES

### Academic — Original
- **FAIR-RAG** (arXiv 2510.22344): Iterative refinement with Structured Evidence Assessment
- **A-RAG** (arXiv 2602.03442): Hierarchical retrieval interfaces
- **HalluGraph** (arXiv 2512.01659): Graph-theoretic hallucination detection
- **Stanford Legal RAG** (Magesh et al., JELS 2025): 17-33% hallucination rate in legal AI tools. Citation verification non-negotiable.

### Academic — New Additions (Informing V2 Upgrades)
- **CRAG — Corrective RAG** (arXiv 2401.15884, Yan et al. 2024): Lightweight retrieval evaluator scoring documents as correct/ambiguous/incorrect. Triggers adaptive fallback actions. Plug-and-play with any RAG pipeline. Informs our `evaluate_relevance_node`.
- **Contextual Retrieval** (Anthropic Blog, Sept 2024): Prepend chunk-specific context before embedding. 49% fewer retrieval failures, 67% with BM25+reranking. Informs our `contextual_embeddings.py`.
- **GraphRAG** (arXiv 2501.00309, Microsoft): Community detection on knowledge graphs + LLM summarization. 80% accuracy on complex queries vs 50% traditional RAG. 3.4x improvement on enterprise benchmarks. Informs our `graph_community_worker`.
- **Speculative RAG** (Wang et al. 2025, OpenReview): Parallel drafts from specialist LMs, verified by generalist LM. Reduces latency while improving quality through diverse perspectives. Informs our `speculative_synthesis_node`.
- **MA-RAG** (arXiv 2505.20096, EMNLP 2025): Multi-agent RAG via collaborative chain-of-thought reasoning. Worker-level CoT significantly improves final answer quality. Informs our worker `reasoning` field.
- **Agentic RAG Survey** (arXiv 2501.09136): Comprehensive taxonomy of agentic RAG patterns: reflection, planning, tool use, multi-agent collaboration. Validates our overall architecture.
- **Deep Research Agent Survey** (arXiv 2508.12752): Survey of autonomous research agents. Reasoning-searching-synthesizing closed loop. Validates our iterative gap analysis approach.
- **When to Use Graphs in RAG** (arXiv 2506.05690): Comprehensive analysis of when graph structures provide measurable benefits. Validates citation graph usage for legal precedent.
- **Late Chunking** (arXiv 2409.04701): Contextual chunk embeddings using long-context models. We chose Contextual Retrieval instead (more practical with Gemini API), but Late Chunking is a valid alternative.
- **Search-R1** (PeterGriffinJin/Search-R1): RL-trained search agents. Interesting but requires training infrastructure beyond our current scope.

### Academic — Enhancement Round (Q1-Q6, S10-S12, T1-T4)
- **MC-RAG — Multiply-Conditioned Retrieval** (IJSAT 2025): Conditioned retrieval where subsequent rounds use prior findings as context. Discovers meaningful citation clusters that independent retrieval misses. Informs [Q1] conditioned gap analysis.
- **RAPTOR** (arXiv 2401.18059, Sarthi et al. 2024): Recursive Abstractive Processing for Tree-Organized Retrieval. Hierarchical summarization at ingestion time creates multi-granularity document representations. Informs [Q3] section summaries.
- **LeMAJ — Legal LLM-as-a-Judge** (arXiv 2403.XXXXX, 2024): Decompose legal text into Legal Data Points, verify each against source evidence. More rigorous than holistic quality scoring. Informs [Q4] legal quality check.
- **HiPRAG — Hierarchical Prompted RAG** (2025): Progressive retrieval with increasing specificity. Validates our multi-round refinement approach with conditioned queries [Q1].
- **Perplexity Deep Research Architecture** (2025-2026): Iterative search-reason-search loop with real-time process visualization. Users see every step the agent takes. Directly validates [T1] research process visualization.
- **Google Gemini Context Caching** (Gemini API, 2025): Cache frequently-reused prompt content for 90% input token cost reduction. Minimum 32K tokens cached. Informs [S10].
- **Stanford Legal AI Hallucination Study** (Magesh et al., JELS 2025): 17-33% hallucination rate across commercial legal AI tools. Citation verification is non-negotiable for production legal AI. Validates [Q6] dual-stage verification and [T4] zero-tolerance guardrail.

### Industry
- **Thomson Reuters Deep Research**: Research plan → user review → iterative execution → citation-grounded reports
- **Jhana AI**: 16M+ docs, 10K+ users, 150+ judges, paragraph classification, citation graph (competitor benchmark)
- **BharatLaw AI**: 1M+ docs, free tier, SC + all HCs, audio digests, AI summaries
- **CaseMine**: CaseIQ dynamic case maps, AMICUS generative AI assistant, precedent visualization
- **LexisNexis Protégé** (launched Aug 2025): Agentic AI that autonomously completes tasks and reviews its own work
- **CoCounsel Legal** (early 2026): Agentic workflows for multi-step legal research

### Technical
- **LangGraph Send() API**: Dynamic fan-out for parallel execution. Results merge via state reducers.
- **Pinecone metadata filtering**: Same performance as namespaces. Recommended for flexibility.
- **Indian Kanoon API**: `api.indiankanoon.org` — 28M docs, structural analysis, citation graph, Rs 0.05/fragment
- **graspologic** (Microsoft Research): Python library for graph statistics including Leiden community detection. MIT license. Required for GraphRAG communities.
- **Gemini Context Caching API**: `caching.CachedContent.create()` — cache system prompts for 90% cost reduction. TTL-based expiry. Minimum 32K tokens. Informs [S10].
- **Redis Stack / RediSearch**: HNSW vector index for semantic similarity search. `FT.CREATE` with VECTOR field type, `FT.SEARCH` with KNN. Used for [S11] semantic caching.
- **MTEB Benchmark (March 2026)**: Gemini embedding-001 remains #1 (score 68.32, +5.09 gap over #2). No model change needed.
- **Cohere rerank-v4.0-pro**: Still industry standard for reranking. No better alternative identified as of March 2026.

### Data Sources
- AWS Open Data: SC judgments (`s3://indian-supreme-court-judgments/`), HC judgments (`s3://indian-high-court-judgments/`)
- Indian Kanoon API: `api.indiankanoon.org` (commercial, Rs 10K/mo free for non-commercial)
- Tavily: `tavily.com` (web search for RAG, $0.01/query)
- civictech-India: Constitution + IPC/CrPC/IEA/CPC (GitHub, free)
- Kaggle: BNS dataset (free)
