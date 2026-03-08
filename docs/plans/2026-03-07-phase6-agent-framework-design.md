# Phase 6: Agent Framework + Research & Case Prep Agents — Design

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the agent infrastructure on LangGraph and ship two fully interactive agents (Research Agent, Case Prep Agent) that transition Smriti from "search tool" to "AI legal assistant."

**Architecture:** Hybrid approach — LangGraph `StateGraph` for agent orchestration with `AsyncPostgresSaver` for checkpoint persistence and `interrupt()` for fully interactive human-in-the-loop. Celery stays untouched for existing background tasks (document processing, audio generation). Existing services (`hybrid_search`, `DocumentAnalyzer`, `PrecedentMapper`, `GraphStore`) become node functions inside the agent graphs.

**Tech Stack:** LangGraph, langgraph-checkpoint-postgres, psycopg-pool, Gemini Pro (reasoning nodes), Gemini Flash (classification nodes), FastAPI SSE streaming, React (agent workspace UI)

---

## Design Decisions

| Decision | Choice | Reasoning |
|----------|--------|-----------|
| Agent runtime | LangGraph StateGraph | Built-in checkpointing for HITL, streaming, conditional routing, parallel nodes |
| Orchestration for existing tasks | Celery (unchanged) | Document processing and audio generation are non-interactive background tasks |
| Checkpoint storage | AsyncPostgresSaver (existing PostgreSQL) | No new database, thread-based isolation, fault tolerance |
| HITL approach | Fully interactive (interrupt at every key step) | User chose maximum interactivity — lawyers want to steer research direction |
| Research Agent vs Chat | Separate tools | Chat stays for quick Q&A; Research Agent is deep structured research |
| Case Prep Agent vs Doc Analysis | Enhanced layer | Builds on existing DocumentAnalysis results, adds prioritization + strategy |
| Agent UI | Dedicated hub + per-agent workspaces | Clean separation, each agent gets full workspace with step visualization |
| Multi-model routing | Flash for classification, Pro for reasoning | Cost optimization — Flash is cheaper for simple tasks, Pro for complex analysis |

---

## 1. Architecture Overview

```
User Request
    |
FastAPI Route (/agents/{type}/run)
    |
Orchestrator (intent classification -> route to agent)
    |
+-------------------------------------+
|  LangGraph StateGraph               |
|                                     |
|  Nodes: plan -> search -> analyze ->|
|         synthesize -> checkpoint -> |
|         respond                     |
|                                     |
|  Checkpointer: AsyncPostgresSaver   |
|  Streaming: astream() -> SSE        |
|  HITL: interrupt() -> resume via    |
|        Command(resume=...)          |
+-------------------------------------+
    |
SSE stream to frontend (progress, results, checkpoints)
```

Key points:
- Each agent is a compiled `StateGraph` (Research Agent graph, Case Prep Agent graph)
- `AsyncPostgresSaver` uses existing PostgreSQL for checkpoint persistence (no new DB)
- Agent state is thread-based — each execution gets a `thread_id` for isolation
- Existing services become node functions inside the graphs
- Multi-model: Gemini Flash for classification/extraction nodes, Gemini Pro for reasoning/synthesis nodes
- Celery stays untouched for document upload processing and audio generation

---

## 2. Data Model

### New Table: `agent_executions`

```
agent_executions
  id              UUID PK
  user_id         FK -> users
  agent_type      ENUM('research', 'case_prep')
  status          ENUM('running', 'waiting_input', 'completed', 'failed', 'cancelled')
  input_data      JSONB           -- original query or document reference
  result_data     JSONB           -- final structured output (memo, citations, etc.)
  thread_id       UUID            -- LangGraph checkpoint thread
  current_step    VARCHAR         -- which node is currently active
  steps_completed INT DEFAULT 0
  total_steps     INT NULL        -- estimated, updated as plan evolves
  created_at      TIMESTAMPTZ
  updated_at      TIMESTAMPTZ
  completed_at    TIMESTAMPTZ NULL
  error_message   TEXT NULL
```

### LangGraph Checkpoint Tables

Managed automatically by `AsyncPostgresSaver.setup()`. We don't touch these directly.

### LangGraph State Schemas

```python
# Research Agent
class ResearchState(TypedDict):
    query: str                                      # original legal question
    sub_queries: list[str]                           # decomposed sub-questions
    search_results: Annotated[list, operator.add]    # accumulated results (reducer)
    cross_references: list[dict]                     # cases in multiple sub-queries
    contradictions: list[dict]                       # conflicting holdings
    draft_memo: str                                  # structured research memo
    confidence: float                                # overall confidence score
    messages: list[dict]                             # HITL conversation history
    iteration: int                                   # loop counter (max 3)

# Case Prep Agent
class CasePrepState(TypedDict):
    document_id: str                                 # uploaded document reference
    analysis: dict                                   # existing DocumentAnalysis results
    prioritized_issues: list[dict]                   # issues ranked by strength
    argument_order: list[dict]                       # recommended argument sequence
    strategy_points: list[str]                       # tactical recommendations
    enhanced_memo: str                               # final enhanced research memo
    messages: list[dict]                             # HITL conversation
    iteration: int                                   # loop counter (max 3)
```

---

## 3. Research Agent Graph

```
START
  |
[classify_query] (Flash) -- legal topic, complexity, jurisdiction
  |
[decompose] (Pro) -- break into 3-7 sub-queries
  |
[interrupt: "I plan to research these sub-questions. Adjust?"]
  |
[parallel_search] -- scatter: hybrid_search per sub-query (parallel nodes)
  |
[gather_results] -- merge, deduplicate, cross-reference
  |
[detect_contradictions] (Pro) -- flag conflicting holdings
  |
[interrupt: "Here's what I found. Focus on any specific area?"]
  |
[synthesize_memo] (Pro) -- structured research memo:
  - Executive summary
  - Key findings per sub-query
  - Supporting precedents (with confidence scores)
  - Opposing/distinguishing precedents
  - Statutory provisions
  - Contradictions flagged
  - Recommended further research
  |
[verify_citations] -- check every cited case_id exists in DB
  |
[interrupt: "Draft memo ready. Any revisions?"]
  |
END -> return final memo
```

Key behaviors:
- Each `interrupt()` pauses execution and streams checkpoint to frontend
- If user provides feedback at a checkpoint, agent can loop back (max 3 iterations)
- All search nodes reuse existing `hybrid_search()` -- no new search logic
- Citation verification ensures zero hallucinated case references
- Flash for classification, Pro for decomposition/contradiction/synthesis

---

## 4. Case Prep Agent Graph

```
START
  |
[load_analysis] -- fetch existing DocumentAnalysis from DB
  |
[prioritize_issues] (Pro) -- rank by legal strength, relevance, trends
  |
[interrupt: "I've ranked the issues. Reorder or drop any?"]
  |
[deep_precedent_search] -- per top issue:
  - Citation graph traversal (Neo4j 2-hop neighbors)
  - Similar fact-pattern search (vector similarity)
  - Statute cross-referencing
  |
[build_argument_order] (Pro) -- recommend sequence:
  - Strongest arguments first vs. logical narrative
  - Which precedents to lead with
  - Which counter-arguments to preempt
  |
[interrupt: "Proposed argument structure. Adjust strategy?"]
  |
[generate_strategy_memo] (Pro) -- enhanced memo:
  - Case overview + parties
  - Prioritized issues with strength ratings
  - Per-issue: lead precedent, supporting chain, distinguishing cases
  - Counter-argument matrix with suggested rebuttals
  - Recommended argument order with reasoning
  - Strategic notes (bench composition, recent trends)
  |
[verify_citations] -- same as Research Agent
  |
[interrupt: "Strategy memo ready. Revisions?"]
  |
END -> return enhanced memo
```

Key behaviors:
- Requires a previously analyzed document (document_id -> existing DocumentAnalysis)
- Builds on Phase 5's analysis -- doesn't redo extraction or basic precedent search
- Uses Neo4j citation graph for deeper precedent chain discovery
- Each interrupt lets user steer direction
- Max 3 iterations per loop

---

## 5. API Endpoints

New route file: `api/routes/agents.py`

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/agents/{type}/run` | Start agent execution -> SSE stream |
| `GET` | `/agents/executions` | List user's executions (paginated) |
| `GET` | `/agents/executions/{id}` | Execution status + results |
| `POST` | `/agents/executions/{id}/resume` | Provide HITL input, resume agent |
| `DELETE` | `/agents/executions/{id}` | Cancel running execution |

### SSE Event Types

```
event: status      -> {"step": "decompose", "message": "Breaking question into sub-queries..."}
event: progress    -> {"steps_completed": 2, "total_steps": 7}
event: result      -> {"type": "sub_queries", "data": ["query1", "query2", ...]}
event: checkpoint  -> {"type": "interrupt", "question": "...", "options": [...], "context": {...}}
event: memo        -> {"type": "draft_memo", "content": "..."}
event: done        -> {"execution_id": "...", "status": "completed"}
event: error       -> {"message": "...", "recoverable": true/false}
```

### HITL Flow

1. Agent hits `interrupt()` -> LangGraph pauses, checkpoint saved
2. SSE sends `checkpoint` event with question + context to frontend
3. Execution status becomes `waiting_input`
4. User responds via `POST /agents/executions/{id}/resume` with their input
5. LangGraph resumes with `Command(resume=user_input)`
6. SSE stream continues from where it paused

All endpoints require JWT auth. Executions are private per-user.

---

## 6. Frontend

### New Pages

| Page | Route | Purpose |
|------|-------|---------|
| Agent Hub | `/agents` | Card grid: Research Agent + Case Prep Agent |
| Research Workspace | `/agents/research` | Text input + step viz + memo output |
| Case Prep Workspace | `/agents/case-prep` | Document selector + step viz + strategy memo |
| Execution History | `/agents/history` | Past executions list |

### Workspace Layout

```
+---------------------------------------------+
|  Agent Name                    [Cancel]      |
+----------------------+----------------------+
|                      |                      |
|  Step Timeline       |  Main Content        |
|                      |                      |
|  [checkmark] Classify|  [Current step       |
|  [checkmark] Decomp  |   output renders     |
|  [spinner] Search... |   here]              |
|  [ ] Analyze         |                      |
|  [ ] Synthesize      |  +----------------+  |
|                      |  | HITL Prompt    |  |
|                      |  | "Focus on any  |  |
|                      |  |  specific area?"|  |
|                      |  | [text input]   |  |
|                      |  | [Submit]       |  |
|                      |  +----------------+  |
|                      |                      |
+----------------------+----------------------+
|  Sources: [case cards with citations]        |
+---------------------------------------------+
```

### New Components

- `AgentStepTimeline` -- vertical step list with status icons (checkmark/spinner/circle)
- `AgentCheckpointPrompt` -- HITL interaction card with text input
- `AgentMemoViewer` -- rich markdown renderer for research/strategy memos
- `AgentHubCard` -- agent description card with start button

---

## 7. Testing & Error Handling

### Testing Strategy

| Layer | What | How |
|-------|------|-----|
| Agent nodes | Each node in isolation | Mock LLM + search, assert state transforms |
| Graph flow | Full execution with mocks | Compile graph, invoke, verify final output |
| HITL | Interrupt/resume cycle | Invoke, catch interrupt, resume with Command |
| State persistence | Checkpoint save/load | Run partway, reload, verify state |
| API routes | SSE streaming, auth, errors | TestClient with SSE parsing |
| Frontend | Workspace, SSE, HITL prompts | React Testing Library |

### Error Handling

- **Node failures:** catch in node, set error in state, route to error handler
- **LLM timeout:** 60s per call, retry once, then fail with partial results
- **Search failures:** individual sub-query failures skip and note in memo
- **HITL timeout:** stays `waiting_input` indefinitely (no auto-cancel)
- **Max iterations:** hard cap of 3 loops on any cycle
- **Cancellation:** DELETE sets cancel flag, nodes check before proceeding

### Estimated Test Counts

- ~40 new backend tests
- ~15 new frontend tests

---

## 8. New Dependencies

```
langgraph>=0.3
langgraph-checkpoint-postgres>=2.0
psycopg[binary]>=3.2
psycopg-pool>=3.2
```

---

## 9. File Structure (New)

```
backend/app/
  core/
    agents/
      __init__.py
      state.py              # State schemas (ResearchState, CasePrepState)
      research.py            # Research Agent graph definition
      case_prep.py           # Case Prep Agent graph definition
      nodes/
        __init__.py
        classify.py          # classify_query node (Flash)
        decompose.py         # decompose node (Pro)
        search.py            # parallel_search + gather_results nodes
        analyze.py           # detect_contradictions, prioritize_issues nodes
        synthesize.py        # synthesize_memo, generate_strategy_memo nodes
        verify.py            # verify_citations node
        common.py            # shared node utilities
      checkpointer.py       # AsyncPostgresSaver setup
  api/routes/
    agents.py               # Agent API endpoints
  models/
    agent_execution.py       # AgentExecution SQLAlchemy model

backend/tests/unit/
  test_agent_nodes.py        # Individual node tests
  test_research_agent.py     # Research Agent graph tests
  test_case_prep_agent.py    # Case Prep Agent graph tests
  test_agent_routes.py       # API route tests

frontend/src/app/
  agents/
    page.tsx                 # Agent hub
    research/page.tsx        # Research workspace
    case-prep/page.tsx       # Case Prep workspace
    history/page.tsx         # Execution history

frontend/src/components/
  agent-step-timeline.tsx
  agent-checkpoint-prompt.tsx
  agent-memo-viewer.tsx
  agent-hub-card.tsx

frontend/src/__tests__/
  agents-page.test.tsx
  research-workspace.test.tsx
  case-prep-workspace.test.tsx
```
