# Chapter 7: The Research Agent

---

Everything so far — reading PDFs, extracting metadata, embedding text, building search, mapping citations — was preparation for this.

The research agent is Smriti's crown jewel. It doesn't just *find* cases. It **researches like a lawyer** — reading statute text, breaking down legal questions, searching for supporting and opposing precedents, evaluating evidence, and writing a research memo with citations and confidence scores.

This chapter tells the story of how the agent evolved through three versions, each one dramatically smarter than the last.

---

## Version 1: The Simple Search (March 6)

V1 was barely an "agent." More like a fancy search wrapper:

1. Take the user's question
2. Search for relevant cases
3. Feed the cases to Gemini
4. Ask Gemini to write a memo

It worked... sort of. But the memos were shallow. The agent had no understanding of *what* it was searching for. It couldn't distinguish between strong and weak precedent. And it definitely couldn't handle complex multi-part legal questions.

---

## Version 2: The Orchestrator (March 20)

V2 was a quantum leap. Built on **LangGraph** — a framework that lets you build AI workflows as *graphs* of nodes, where each node does one thing and passes its output to the next.

### The LangGraph Mental Model

Think of it as a flowchart, but one that an AI can walk through:

```
Start → Node A → Node B → [Decision] → Node C (if yes)
                                      → Node D (if no)
                          ↓
                      Node E → End
```

Each node is a Python function that:
- Receives the current **state** (all accumulated knowledge)
- Does one thing (call an LLM, run a search, validate citations)
- Returns a **partial state update** (new information to add)

The state grows as the agent progresses through the graph.

### V2's Pipeline (5 Phases)

**Phase 1: Understand**
```
User Question → Rewrite Query → Classify Query
                                     ↓
                              Topic? Complexity?
                              Key entities?
                              Target court?
```

**Phase 2: Plan**
```
Classification → Generate Research Plan → [CHECKPOINT: User approval]
                     ↓
              "I plan to search for:
               1. Case law on bail under NDPS
               2. The landmark case Union of India v. Ram Samujh
               3. Section 37 NDPS Act text
               4. Recent web articles on NDPS bail"
```

**Phase 3: Execute** (Workers in Parallel!)
```
Plan approved →  ┌─ case_law_worker (search database)
                 ├─ named_case_worker (find specific landmark cases)
                 ├─ statute_worker (find statute text)
                 ├─ ik_search_worker (search Indian Kanoon)
                 ├─ web_search_worker (search recent news via Tavily)
                 ├─ graph_worker (traverse citation network)
                 └─ graph_community_worker (find citation clusters)

                 All running simultaneously!
```

**Phase 4: Evaluate**
```
Worker results → Evaluate & Extract → Gap Analysis → [CHECKPOINT]
                      ↓                    ↓
              "Found 23 cases,         "Missing: cases on
               3 contradictions,        bail after 2023
               key holding: ..."        BNSS amendments"
```

**Phase 5: Synthesize**
```
Findings → Write Memo → Format Footnotes → Verify Citations → Quality Check
                ↓              ↓                 ↓               ↓
          "Research Memo:    [1] case ref     "Citation #3     "Confidence:
           The law on bail    [2] case ref     not found in      0.82
           under NDPS..."     [3] statute      search results    Coverage: good
                                               - FLAGGED"        Gaps: 1"
```

### Human-in-the-Loop (HITL)

V2 introduced a critical feature: **checkpoints**. At key moments, the agent pauses and asks the user:

"Here's my research plan. Do you want me to proceed, or would you like to modify it?"

This uses LangGraph's `interrupt()` mechanism — the graph literally pauses, saves its state, sends the plan to the user's browser, and waits. When the user responds, the graph resumes exactly where it left off.

This is crucial for legal research. A lawyer doesn't want a black box that spits out a memo. They want to guide the research direction.

---

## Version 3: The Legal Mind (March 22)

V3 addressed nine specific gaps in V2. The result is an agent that thinks more like an actual lawyer.

### Gap 1: "Read the statute BEFORE planning"

In V2, the agent planned its research without reading the actual statute text. That's like a lawyer planning research without reading the law.

**V3 fix: `statute_lookup_node`** — Runs in Stage 1 (Understand), before any planning:
- Extracts statute references from the query
- Auto-expands old↔new code mappings (IPC 302 → BNS 103)
- Batch-fetches statute text from PostgreSQL
- Does semantic search in Pinecone for related statutes
- Returns full context: section text, replacement info, equivalents

Now when the agent plans research on "Section 302 IPC," it already knows the section says "Whoever commits murder shall be punished with death, or imprisonment for life, and shall also be liable to fine."

### Gap 2: "Break down the legal question"

In V2, "Is the accused liable under Section 302 IPC?" went to search as a single query. But a lawyer would decompose this:
- Was there a death? (actus reus)
- Was there intention to kill? (mens rea)
- Do any exceptions apply? (self-defense, sudden provocation?)
- What's the standard of proof?

**V3 fix: `element_decomposition_node`** — Breaks the legal question into constituent elements:
```json
{
  "elements": [
    {"element": "actus reus", "description": "Was there an act causing death?"},
    {"element": "mens rea", "description": "Was there intention or knowledge?"},
    {"element": "exceptions", "description": "Does Exception 1-5 of S.300 apply?"},
    {"element": "standard_of_proof", "description": "Beyond reasonable doubt"}
  ]
}
```

Each element becomes a separate research task. Much more thorough than searching for one big question.

### Gap 3: "Find the counter-arguments"

A good lawyer doesn't just find cases that support their position. They anticipate the other side's arguments.

**V3 fix: `adversarial_search_node`** — After finding supporting cases, this node flips the argument:
- If you found cases *granting* bail under NDPS, search for cases *denying* bail
- If you found cases *upholding* Section 302, search for cases *reducing* to Section 304

The user can toggle this on/off. It's optional but powerful.

### Gap 4: "Check if the law changed"

A 2022 IPC case might cite Section 302. But in 2024, IPC was replaced by BNS. Is the holding still valid? Under which section?

**V3 fix: `temporal_validation_node`** — Deterministic (no LLM, just logic):
- Checks each cited case against the new/old code timeline
- Flags cases that cite repealed provisions
- Notes equivalent new provisions
- Produces warnings: "This case cites IPC 302, now replaced by BNS 103"

---

## The V3 Pipeline: 5 Stages

```
┌─────────────────────────────────────────────────────────┐
│ STAGE 1: UNDERSTAND                                     │
│   rewrite_query → classify → statute_lookup (NEW)       │
│   "Read the law before you plan"                        │
├─────────────────────────────────────────────────────────┤
│ STAGE 2: DECOMPOSE                                      │
│   element_decomposition (NEW) → plan_research            │
│   "Break the question into legal elements"               │
│   [CHECKPOINT: User approves plan]                       │
├─────────────────────────────────────────────────────────┤
│ STAGE 3: INVESTIGATE                                    │
│   Workers in parallel (7 types, up to 30 workers)        │
│   case_law, named_case, statute, IK, web, graph, comm.  │
├─────────────────────────────────────────────────────────┤
│ STAGE 4: CHALLENGE                                      │
│   evaluate → adversarial_search (NEW) →                  │
│   temporal_validation (NEW) → gap_analysis               │
│   "Find the counter-arguments, check the timeline"       │
├─────────────────────────────────────────────────────────┤
│ STAGE 5: SYNTHESIZE                                     │
│   draft_memo → format_footnotes → verify_citations →     │
│   quality_check → confidence_score                       │
│   "Write the memo, verify every citation"                │
└─────────────────────────────────────────────────────────┘
```

### Fast Path

Simple questions ("What does Section 302 IPC say?") skip the full pipeline:

```
statute_lookup → element_decomposition → fast_search → fast_synthesis → verify → done
```

No planning step, no workers, no gap analysis. Quick and efficient.

---

## The Workers: Specialized Searchers

Each worker type has a specific skill:

| Worker | What It Does | Data Source |
|--------|-------------|-------------|
| `case_law_worker` | Dual-query hybrid search (natural language + boolean) | PostgreSQL + Pinecone |
| `named_case_worker` | Find a specific landmark case by name/citation | PostgreSQL (exact match) |
| `statute_worker` | Find statute section text | PostgreSQL statutes table + Pinecone |
| `ik_search_worker` | Search Indian Kanoon (external legal database) | Indian Kanoon API |
| `web_search_worker` | Find recent developments, news, articles | Tavily web search |
| `graph_worker` | Traverse the citation network | Neo4j |
| `graph_community_worker` | Find citation clusters on a topic | Neo4j + NetworkX |

Workers run in parallel (up to 30 at a time) using LangGraph's `Send()` fan-out. This means Stage 3 takes as long as the slowest worker, not the sum of all workers.

---

## Confidence Scoring: How Sure Is Smriti?

At the end of every research, Smriti computes a confidence score:

```
confidence = weighted_average(
    0.25 × relevance       — how well do results match the query?
    0.10 × coverage         — what fraction of elements have evidence?
    0.15 × authority        — how strong are the cited precedents?
    0.10 × consistency      — any contradictions between findings?
    0.10 × source_diversity — evidence from multiple sources? (DB, IK, web, graph)
    0.10 × gap_coverage     — were evidence gaps filled?
    0.20 × synthesis_quality — how good is the memo itself?
)
```

The confidence breakdown is shown to the user:

```
Overall Confidence: 0.82 (Good)
├── Relevance: 0.89 (search results highly relevant)
├── Coverage: 0.75 (3 of 4 elements covered)
├── Authority: 0.85 (includes Constitution Bench decisions)
├── Consistency: 0.90 (minor contradiction on one point)
├── Source Diversity: 0.80 (DB + IK + graph, no web results)
├── Gap Coverage: 0.70 (1 gap partially addressed)
└── Synthesis Quality: 0.85 (coherent, well-structured)
```

---

## Streaming: Watching the Agent Think

The research agent doesn't just produce a final result. It *streams* its progress to the user's browser in real-time via **Server-Sent Events (SSE)**:

```
[0s]   status: "Understanding your question..."
[2s]   status: "Reading Section 302 IPC text..."
[3s]   progress: Stage 1 complete (20%)
[5s]   status: "Breaking down legal elements..."
[7s]   checkpoint: "Here's my research plan. Approve?"
[user approves]
[8s]   status: "Dispatching 12 research workers..."
[10s]  progress: Stage 3 in progress (45%)
[15s]  status: "Worker 'case_law_bail' found 8 cases"
[18s]  status: "Worker 'ik_search' found 5 cases"
[25s]  progress: Stage 3 complete (60%)
[30s]  status: "Evaluating evidence, checking for gaps..."
[35s]  progress: Stage 4 complete (80%)
[40s]  memo_stream: "## Research Memo\n\nThe question of bail under..."
[41s]  memo_stream: "...Section 37 of the NDPS Act imposes..."
[50s]  done: { confidence: 0.82, citation_count: 15 }
```

The memo itself streams chunk by chunk, so the user sees it being written in real-time — like watching a lawyer draft.

---

## Performance: V2 vs V3

| Metric | V2 | V3 | Change |
|--------|----|----|--------|
| Wall-clock time | ~47 seconds | ~56 seconds | +19% |
| Statute awareness | None | Full context | Major improvement |
| Element decomposition | None | 3-5 elements | Much more thorough |
| Adversarial search | None | Optional | Finds counter-arguments |
| Temporal validation | None | Automatic | Catches outdated law |

The extra 9 seconds are worth it. V3 produces dramatically better research memos — more thorough, more nuanced, and more trustworthy.

---

> **Next: [Chapter 8 — The Face of Smriti →](./08-the-face-of-smriti.md)**
>
> *Where all this backend magic gets wrapped in a beautiful, usable interface.*

---

### In the Code

| What | Where |
|------|-------|
| Research graph builder | [backend/app/core/agents/research.py](../../backend/app/core/agents/research.py) |
| Worker nodes | [backend/app/core/agents/nodes/worker_nodes.py](../../backend/app/core/agents/nodes/worker_nodes.py) |
| Research nodes | [backend/app/core/agents/nodes/research_nodes.py](../../backend/app/core/agents/nodes/research_nodes.py) |
| Common nodes | [backend/app/core/agents/nodes/common.py](../../backend/app/core/agents/nodes/common.py) |
| Confidence scoring | [backend/app/core/agents/confidence.py](../../backend/app/core/agents/confidence.py) |
| Agent state schema | `backend/app/core/agents/state.py` |
| Agent API routes | [backend/app/api/routes/agents.py](../../backend/app/api/routes/agents.py) |
| V3 design doc | [docs/plans/2026-03-20-research-agent-v3-design.md](../plans/2026-03-20-research-agent-v3-design.md) |
| V3 implementation plan | [docs/plans/2026-03-20-research-agent-v3-plan.md](../plans/2026-03-20-research-agent-v3-plan.md) |
| All agent prompts | [docs/PROMPT_LIBRARY.md](../PROMPT_LIBRARY.md) |
| Follow-up agent | [backend/app/core/agents/follow_up.py](../../backend/app/core/agents/follow_up.py) |
