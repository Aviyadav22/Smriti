# Phase 6: Agent Framework Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build LangGraph-based agent infrastructure and ship Research Agent + Case Prep Agent with fully interactive HITL.

**Architecture:** LangGraph StateGraph for agent orchestration, AsyncPostgresSaver for checkpointing (existing PostgreSQL), interrupt() for HITL pauses, SSE streaming to frontend. Celery stays for existing background tasks.

**Tech Stack:** langgraph, langgraph-checkpoint-postgres, psycopg-pool, Gemini Pro/Flash, FastAPI SSE, React

**Design doc:** `docs/plans/2026-03-07-phase6-agent-framework-design.md`

---

### Task 1: Install LangGraph Dependencies

**Files:**
- Modify: `backend/requirements.txt`

**Step 1:** Add dependencies to requirements.txt:
```
langgraph>=0.3
langgraph-checkpoint-postgres>=2.0
psycopg[binary]>=3.2
psycopg-pool>=3.2
```

**Step 2:** Install:
```bash
cd backend && pip install -r requirements.txt
```

**Step 3:** Verify import works:
```bash
cd backend && python -c "import langgraph; print(langgraph.__version__)"
```

**Step 4:** Commit:
```bash
git add backend/requirements.txt
git commit -m "feat: add LangGraph dependencies for agent framework"
```

---

### Task 2: AgentExecution Model + Migration

**Files:**
- Create: `backend/app/models/agent_execution.py`
- Modify: `backend/app/models/__init__.py`
- Create: Alembic migration

**Step 1:** Write test for the model:

Create `backend/tests/unit/test_agent_execution_model.py`:
```python
"""Tests for AgentExecution model."""
import uuid
from app.models.agent_execution import AgentExecution, AgentType, AgentStatus


class TestAgentExecutionModel:
    def test_tablename(self) -> None:
        assert AgentExecution.__tablename__ == "agent_executions"

    def test_agent_type_enum(self) -> None:
        assert AgentType.RESEARCH.value == "research"
        assert AgentType.CASE_PREP.value == "case_prep"

    def test_agent_status_enum(self) -> None:
        assert AgentStatus.RUNNING.value == "running"
        assert AgentStatus.WAITING_INPUT.value == "waiting_input"
        assert AgentStatus.COMPLETED.value == "completed"
        assert AgentStatus.FAILED.value == "failed"
        assert AgentStatus.CANCELLED.value == "cancelled"
```

**Step 2:** Run test, verify it fails:
```bash
cd backend && python -m pytest tests/unit/test_agent_execution_model.py -v
```

**Step 3:** Create `backend/app/models/agent_execution.py`:
```python
"""AgentExecution model for tracking agent runs."""
import enum
import uuid

import sqlalchemy as sa
from sqlalchemy import CheckConstraint, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AgentType(str, enum.Enum):
    RESEARCH = "research"
    CASE_PREP = "case_prep"


class AgentStatus(str, enum.Enum):
    RUNNING = "running"
    WAITING_INPUT = "waiting_input"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentExecution(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "agent_executions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    agent_type: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(20), nullable=False, server_default="running")
    input_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    result_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    thread_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, default=uuid.uuid4
    )
    current_step: Mapped[str | None] = mapped_column(sa.String(100), nullable=True)
    steps_completed: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default="0")
    total_steps: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    completed_at: Mapped[sa.DateTime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "agent_type IN ('research', 'case_prep')",
            name="ck_agent_executions_type",
        ),
        CheckConstraint(
            "status IN ('running', 'waiting_input', 'completed', 'failed', 'cancelled')",
            name="ck_agent_executions_status",
        ),
    )
```

**Step 4:** Add to `backend/app/models/__init__.py` — import `AgentExecution`.

**Step 5:** Run test, verify it passes:
```bash
cd backend && python -m pytest tests/unit/test_agent_execution_model.py -v
```

**Step 6:** Generate and run migration:
```bash
cd backend && alembic revision --autogenerate -m "add agent_executions table"
cd backend && alembic upgrade head
```

**Step 7:** Commit:
```bash
git add backend/app/models/agent_execution.py backend/tests/unit/test_agent_execution_model.py backend/app/models/__init__.py backend/migrations/
git commit -m "feat: add AgentExecution model and migration"
```

---

### Task 3: Agent State Schemas

**Files:**
- Create: `backend/app/core/agents/__init__.py`
- Create: `backend/app/core/agents/state.py`
- Create: `backend/tests/unit/test_agent_state.py`

**Step 1:** Write tests for state schemas:

```python
"""Tests for agent state schemas."""
from app.core.agents.state import ResearchState, CasePrepState


class TestResearchState:
    def test_has_required_keys(self) -> None:
        state: ResearchState = {
            "query": "test",
            "sub_queries": [],
            "search_results": [],
            "cross_references": [],
            "contradictions": [],
            "draft_memo": "",
            "confidence": 0.0,
            "messages": [],
            "iteration": 0,
        }
        assert state["query"] == "test"
        assert state["iteration"] == 0

class TestCasePrepState:
    def test_has_required_keys(self) -> None:
        state: CasePrepState = {
            "document_id": "abc",
            "analysis": {},
            "prioritized_issues": [],
            "argument_order": [],
            "strategy_points": [],
            "enhanced_memo": "",
            "messages": [],
            "iteration": 0,
        }
        assert state["document_id"] == "abc"
```

**Step 2:** Run test, verify fail.

**Step 3:** Create `backend/app/core/agents/__init__.py` (empty) and `backend/app/core/agents/state.py`:

```python
"""Agent state schemas for LangGraph."""
from __future__ import annotations

import operator
from typing import Annotated, TypedDict


class ResearchState(TypedDict):
    """State for the Research Agent graph."""
    query: str
    sub_queries: list[str]
    search_results: Annotated[list[dict], operator.add]
    cross_references: list[dict]
    contradictions: list[dict]
    draft_memo: str
    confidence: float
    messages: list[dict]
    iteration: int


class CasePrepState(TypedDict):
    """State for the Case Prep Agent graph."""
    document_id: str
    analysis: dict
    prioritized_issues: list[dict]
    argument_order: list[dict]
    strategy_points: list[str]
    enhanced_memo: str
    messages: list[dict]
    iteration: int
```

**Step 4:** Run test, verify pass.

**Step 5:** Commit:
```bash
git commit -m "feat: add agent state schemas for Research and Case Prep agents"
```

---

### Task 4: Agent Prompts

**Files:**
- Modify: `backend/app/core/legal/prompts.py`
- Create: `backend/tests/unit/test_agent_prompts.py`

**Step 1:** Write test that prompts exist and have placeholders:
```python
"""Tests for agent prompts."""
from app.core.legal.prompts import (
    RESEARCH_CLASSIFY_SYSTEM,
    RESEARCH_DECOMPOSE_SYSTEM,
    RESEARCH_DECOMPOSE_USER,
    RESEARCH_CONTRADICTIONS_SYSTEM,
    RESEARCH_SYNTHESIZE_SYSTEM,
    RESEARCH_SYNTHESIZE_USER,
    CASE_PREP_PRIORITIZE_SYSTEM,
    CASE_PREP_PRIORITIZE_USER,
    CASE_PREP_ARGUMENT_ORDER_SYSTEM,
    CASE_PREP_STRATEGY_SYSTEM,
    CASE_PREP_STRATEGY_USER,
    RESEARCH_CLASSIFY_SCHEMA,
    RESEARCH_DECOMPOSE_SCHEMA,
)


class TestResearchPrompts:
    def test_classify_system_exists(self) -> None:
        assert len(RESEARCH_CLASSIFY_SYSTEM) > 50

    def test_decompose_has_placeholder(self) -> None:
        assert "{query}" in RESEARCH_DECOMPOSE_USER

    def test_synthesize_has_placeholders(self) -> None:
        assert "{query}" in RESEARCH_SYNTHESIZE_USER
        assert "{findings}" in RESEARCH_SYNTHESIZE_USER

    def test_classify_schema_is_valid(self) -> None:
        assert RESEARCH_CLASSIFY_SCHEMA["type"] == "object"
        assert "topic" in RESEARCH_CLASSIFY_SCHEMA["properties"]

    def test_decompose_schema_is_valid(self) -> None:
        assert RESEARCH_DECOMPOSE_SCHEMA["type"] == "object"
        assert "sub_queries" in RESEARCH_DECOMPOSE_SCHEMA["properties"]


class TestCasePrepPrompts:
    def test_prioritize_has_placeholder(self) -> None:
        assert "{issues}" in CASE_PREP_PRIORITIZE_USER

    def test_strategy_has_placeholders(self) -> None:
        assert "{issues_analysis}" in CASE_PREP_STRATEGY_USER
```

**Step 2:** Run test, verify fail.

**Step 3:** Add agent prompts to `backend/app/core/legal/prompts.py`. These are the key prompts needed:

- `RESEARCH_CLASSIFY_SYSTEM` / `RESEARCH_CLASSIFY_SCHEMA` — classify legal query topic, complexity, jurisdiction
- `RESEARCH_DECOMPOSE_SYSTEM` / `RESEARCH_DECOMPOSE_USER` / `RESEARCH_DECOMPOSE_SCHEMA` — break query into 3-7 sub-queries
- `RESEARCH_CONTRADICTIONS_SYSTEM` — detect contradictions between case holdings
- `RESEARCH_SYNTHESIZE_SYSTEM` / `RESEARCH_SYNTHESIZE_USER` — generate structured research memo
- `CASE_PREP_PRIORITIZE_SYSTEM` / `CASE_PREP_PRIORITIZE_USER` — rank issues by legal strength
- `CASE_PREP_ARGUMENT_ORDER_SYSTEM` — recommend argument sequence
- `CASE_PREP_STRATEGY_SYSTEM` / `CASE_PREP_STRATEGY_USER` — generate strategy memo

Each prompt should follow existing patterns in the file (Final[str] constants, clear system instructions for Indian legal domain, Gemini-compatible schemas with `"nullable": true`).

**Step 4:** Run test, verify pass.

**Step 5:** Commit:
```bash
git commit -m "feat: add agent prompts for Research and Case Prep agents"
```

---

### Task 5: Checkpointer Setup

**Files:**
- Create: `backend/app/core/agents/checkpointer.py`
- Create: `backend/tests/unit/test_checkpointer.py`

**Step 1:** Write test:
```python
"""Tests for checkpointer factory."""
from unittest.mock import patch, AsyncMock
from app.core.agents.checkpointer import get_checkpointer_connection_string


class TestCheckpointer:
    def test_connection_string_uses_settings(self) -> None:
        conn_str = get_checkpointer_connection_string()
        assert conn_str.startswith("postgresql://") or conn_str.startswith("postgres://")
```

**Step 2:** Run test, verify fail.

**Step 3:** Create `backend/app/core/agents/checkpointer.py`:
```python
"""LangGraph checkpointer setup using existing PostgreSQL."""
from __future__ import annotations

from app.core.config import settings


def get_checkpointer_connection_string() -> str:
    """Build psycopg3-compatible connection string from settings."""
    db_url = str(settings.database_url)
    # langgraph-checkpoint-postgres uses psycopg3, needs postgresql:// prefix
    if db_url.startswith("postgresql+asyncpg://"):
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return db_url
```

Note: The actual `AsyncPostgresSaver` is instantiated at graph compile time in each agent module, using `psycopg_pool.AsyncConnectionPool` with this connection string. Setup tables via a one-time migration script or `checkpointer.setup()` call during app startup.

**Step 4:** Run test, verify pass.

**Step 5:** Commit:
```bash
git commit -m "feat: add LangGraph checkpointer connection setup"
```

---

### Task 6: Agent Node Functions — Common Utilities

**Files:**
- Create: `backend/app/core/agents/nodes/__init__.py`
- Create: `backend/app/core/agents/nodes/common.py`
- Create: `backend/tests/unit/test_agent_nodes_common.py`

**Step 1:** Write tests for shared node utilities:
```python
"""Tests for common agent node utilities."""
import pytest
from app.core.agents.nodes.common import format_search_results_for_llm, verify_case_ids


class TestFormatSearchResults:
    def test_formats_results_with_citations(self) -> None:
        results = [
            {"case_id": "1", "title": "State v. Rao", "citation": "2020 SCC 1", "snippet": "key holding"},
        ]
        formatted = format_search_results_for_llm(results)
        assert "State v. Rao" in formatted
        assert "2020 SCC 1" in formatted

    def test_empty_results(self) -> None:
        assert format_search_results_for_llm([]) == "No results found."

    def test_truncates_long_snippets(self) -> None:
        results = [{"case_id": "1", "title": "T", "citation": "C", "snippet": "x" * 2000}]
        formatted = format_search_results_for_llm(results)
        assert len(formatted) < 2000


class TestVerifyCaseIds:
    @pytest.mark.asyncio
    async def test_returns_valid_ids(self) -> None:
        # Mock db session that returns existing case IDs
        from unittest.mock import AsyncMock, MagicMock
        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = ["id1", "id2"]
        db.execute.return_value = result_mock

        valid = await verify_case_ids(["id1", "id2", "id3"], db)
        assert "id1" in valid
        assert "id2" in valid
        assert "id3" not in valid
```

**Step 2:** Run test, verify fail.

**Step 3:** Create `backend/app/core/agents/nodes/common.py`:
```python
"""Shared utilities for agent node functions."""
from __future__ import annotations

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession


def format_search_results_for_llm(results: list[dict], max_snippet_len: int = 500) -> str:
    """Format search results into a string for LLM context."""
    if not results:
        return "No results found."

    parts = []
    for i, r in enumerate(results, 1):
        snippet = (r.get("snippet") or "")[:max_snippet_len]
        parts.append(
            f"[{i}] {r.get('title', 'Untitled')} ({r.get('citation', 'No citation')})\n"
            f"    Court: {r.get('court', 'Unknown')} | Year: {r.get('year', 'Unknown')}\n"
            f"    {snippet}"
        )
    return "\n\n".join(parts)


async def verify_case_ids(case_ids: list[str], db: AsyncSession) -> set[str]:
    """Check which case_ids actually exist in the database."""
    if not case_ids:
        return set()
    result = await db.execute(
        text("SELECT id::text FROM cases WHERE id::text = ANY(:ids)"),
        {"ids": case_ids},
    )
    return {row[0] for row in result.fetchall()}
```

**Step 4:** Run test, verify pass.

**Step 5:** Commit:
```bash
git commit -m "feat: add common agent node utilities"
```

---

### Task 7: Research Agent Nodes

**Files:**
- Create: `backend/app/core/agents/nodes/research_nodes.py`
- Create: `backend/tests/unit/test_research_nodes.py`

**Step 1:** Write tests for each node function. Key tests:
- `test_classify_query_returns_structured_output` — mock LLM generate_structured, verify topic/complexity/jurisdiction
- `test_decompose_returns_sub_queries` — mock LLM, verify list of 3-7 sub-queries
- `test_parallel_search_accumulates_results` — mock hybrid_search, verify results accumulated
- `test_gather_results_deduplicates` — pass duplicates, verify deduplication + cross-reference detection
- `test_detect_contradictions_flags_conflicts` — mock LLM, verify contradiction list
- `test_synthesize_memo_produces_markdown` — mock LLM, verify memo string
- `test_verify_citations_removes_invalid` — mock DB, verify invalid case_ids removed from memo

**Step 2:** Run tests, verify fail.

**Step 3:** Create `backend/app/core/agents/nodes/research_nodes.py` with these async node functions:

- `classify_query(state, *, llm)` — uses Flash model, `generate_structured` with `RESEARCH_CLASSIFY_SCHEMA`
- `decompose_query(state, *, llm)` — uses Pro model, `generate_structured` with `RESEARCH_DECOMPOSE_SCHEMA`
- `parallel_search(state, *, llm, embedder, vector_store, reranker, db)` — runs `hybrid_search()` per sub-query via `asyncio.gather`, returns accumulated results
- `gather_results(state)` — pure function: dedup by case_id, identify cross-references (cases in 2+ sub-queries)
- `detect_contradictions(state, *, llm)` — Pro model, pass search results, return contradictions list
- `synthesize_memo(state, *, llm)` — Pro model, generate structured research memo from all findings
- `verify_citations(state, *, db)` — check all case_ids in memo exist in DB, flag invalid ones

Each node function takes state as first arg, returns partial state dict. Follow LangGraph convention: nodes are pure-ish functions that read state and return state updates.

**Step 4:** Run tests, verify pass.

**Step 5:** Commit:
```bash
git commit -m "feat: add Research Agent node functions"
```

---

### Task 8: Research Agent Graph

**Files:**
- Create: `backend/app/core/agents/research.py`
- Create: `backend/tests/unit/test_research_agent.py`

**Step 1:** Write tests:
- `test_graph_compiles` — verify `build_research_graph()` returns a compiled graph
- `test_graph_with_mocked_nodes_produces_memo` — mock all node functions, invoke graph, verify final state has `draft_memo`
- `test_interrupt_pauses_execution` — invoke graph, verify it pauses at first interrupt with checkpoint data
- `test_resume_after_interrupt` — invoke, interrupt, resume with Command, verify continuation
- `test_max_iterations_prevents_runaway` — set iteration=3, verify graph routes to END

**Step 2:** Run tests, verify fail.

**Step 3:** Create `backend/app/core/agents/research.py`:

```python
"""Research Agent — LangGraph graph definition."""
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt, Command

from app.core.agents.state import ResearchState

def build_research_graph(*, llm, flash_llm, embedder, vector_store, reranker, db):
    """Build and compile the Research Agent graph."""
    graph = StateGraph(ResearchState)

    # Add nodes (each wraps the node function with injected deps)
    graph.add_node("classify", ...)
    graph.add_node("decompose", ...)
    graph.add_node("checkpoint_plan", ...)      # interrupt: show sub-queries
    graph.add_node("search", ...)
    graph.add_node("gather", ...)
    graph.add_node("contradictions", ...)
    graph.add_node("checkpoint_findings", ...)   # interrupt: show findings
    graph.add_node("synthesize", ...)
    graph.add_node("verify", ...)
    graph.add_node("checkpoint_memo", ...)       # interrupt: show draft memo

    # Edges
    graph.add_edge(START, "classify")
    graph.add_edge("classify", "decompose")
    graph.add_edge("decompose", "checkpoint_plan")
    # checkpoint_plan: conditional — if user says "adjust", loop back to decompose (max 3)
    graph.add_conditional_edges("checkpoint_plan", route_after_plan, {...})
    graph.add_edge("search", "gather")
    graph.add_edge("gather", "contradictions")
    graph.add_edge("contradictions", "checkpoint_findings")
    graph.add_conditional_edges("checkpoint_findings", route_after_findings, {...})
    graph.add_edge("synthesize", "verify")
    graph.add_edge("verify", "checkpoint_memo")
    graph.add_conditional_edges("checkpoint_memo", route_after_memo, {...})

    return graph.compile(checkpointer=checkpointer)
```

Each checkpoint node calls `interrupt()` with context data. Router functions check `iteration < 3` and user feedback to decide next node.

**Step 4:** Run tests, verify pass.

**Step 5:** Commit:
```bash
git commit -m "feat: build Research Agent LangGraph graph"
```

---

### Task 9: Case Prep Agent Nodes

**Files:**
- Create: `backend/app/core/agents/nodes/case_prep_nodes.py`
- Create: `backend/tests/unit/test_case_prep_nodes.py`

**Step 1:** Write tests for each node:
- `test_load_analysis_fetches_from_db` — mock DB, verify analysis dict populated
- `test_prioritize_issues_returns_ranked_list` — mock LLM, verify issues sorted by strength
- `test_deep_precedent_search_uses_graph` — mock graph_store + hybrid_search, verify deeper results
- `test_build_argument_order_returns_sequence` — mock LLM, verify ordered argument list
- `test_generate_strategy_memo_produces_output` — mock LLM, verify memo string

**Step 2:** Run tests, verify fail.

**Step 3:** Create `backend/app/core/agents/nodes/case_prep_nodes.py`:

- `load_analysis(state, *, db)` — fetch DocumentAnalysis by document_id, populate state.analysis
- `prioritize_issues(state, *, llm)` — Pro model, rank issues from analysis by legal strength
- `deep_precedent_search(state, *, llm, embedder, vector_store, reranker, graph_store, db)` — for top issues: Neo4j 2-hop citation traversal + vector similarity search
- `build_argument_order(state, *, llm)` — Pro model, recommend argument sequence
- `generate_strategy_memo(state, *, llm)` — Pro model, generate enhanced strategy memo
- `verify_citations(state, *, db)` — reuse from research nodes

**Step 4:** Run tests, verify pass.

**Step 5:** Commit:
```bash
git commit -m "feat: add Case Prep Agent node functions"
```

---

### Task 10: Case Prep Agent Graph

**Files:**
- Create: `backend/app/core/agents/case_prep.py`
- Create: `backend/tests/unit/test_case_prep_agent.py`

**Step 1:** Write tests (same pattern as Task 8):
- `test_graph_compiles`
- `test_graph_produces_strategy_memo`
- `test_interrupt_at_issue_prioritization`
- `test_interrupt_at_argument_order`
- `test_max_iterations`

**Step 2:** Run tests, verify fail.

**Step 3:** Create `backend/app/core/agents/case_prep.py`:

Same pattern as research.py but with CasePrepState and case prep nodes:
```
START → load_analysis → prioritize → checkpoint_issues → deep_search →
argument_order → checkpoint_strategy → strategy_memo → verify → checkpoint_memo → END
```

**Step 4:** Run tests, verify pass.

**Step 5:** Commit:
```bash
git commit -m "feat: build Case Prep Agent LangGraph graph"
```

---

### Task 11: Agent API Routes

**Files:**
- Create: `backend/app/api/routes/agents.py`
- Modify: `backend/app/main.py` (register router)
- Create: `backend/tests/unit/test_agent_routes.py`

**Step 1:** Write tests:
- `test_run_research_agent_returns_sse_stream` — POST /agents/research/run, verify SSE content-type
- `test_run_requires_auth` — POST without JWT returns 401
- `test_list_executions_returns_user_only` — GET /agents/executions filtered by user_id
- `test_get_execution_returns_detail` — GET /agents/executions/{id}
- `test_resume_execution_with_input` — POST /agents/executions/{id}/resume
- `test_cancel_execution` — DELETE /agents/executions/{id}
- `test_invalid_agent_type_returns_422` — POST /agents/invalid/run

**Step 2:** Run tests, verify fail.

**Step 3:** Create `backend/app/api/routes/agents.py`:

```python
"""Agent execution API routes."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()

class ResearchRequest(BaseModel):
    query: str = Field(..., min_length=5, max_length=5000)

class CasePrepRequest(BaseModel):
    document_id: str = Field(...)

class ResumeRequest(BaseModel):
    input: str = Field(..., min_length=1, max_length=5000)

@router.post("/{agent_type}/run")
async def run_agent(agent_type: str, ...) -> StreamingResponse:
    """Start agent execution, return SSE stream."""
    # 1. Validate agent_type (research or case_prep)
    # 2. Create AgentExecution record
    # 3. Build graph with injected dependencies
    # 4. Stream via astream() with stream_mode=["custom", "updates"]
    # 5. Yield SSE events: status, progress, result, checkpoint, memo, done, error
    # 6. On interrupt: update status to waiting_input, yield checkpoint event, return
    # Headers: Cache-Control: no-cache, X-Accel-Buffering: no

@router.get("/executions")
async def list_executions(...) -> dict:
    """List user's agent executions (paginated)."""

@router.get("/executions/{execution_id}")
async def get_execution(...) -> dict:
    """Get execution detail + results."""

@router.post("/executions/{execution_id}/resume")
async def resume_execution(...) -> StreamingResponse:
    """Resume agent with user input at checkpoint."""
    # 1. Verify ownership
    # 2. Verify status == waiting_input
    # 3. Resume graph with Command(resume=user_input)
    # 4. Continue streaming SSE events

@router.delete("/executions/{execution_id}")
async def cancel_execution(...) -> dict:
    """Cancel running execution."""
```

**Step 4:** Register in `backend/app/main.py`:
```python
app.include_router(agents_router, prefix="/api/v1/agents", tags=["agents"])
```

**Step 5:** Run tests, verify pass.

**Step 6:** Commit:
```bash
git commit -m "feat: add agent API routes with SSE streaming"
```

---

### Task 12: Frontend — Agent Types + API Functions

**Files:**
- Modify: `frontend/src/lib/types.ts`
- Modify: `frontend/src/lib/api.ts`

**Step 1:** Add agent types to `types.ts`:
```typescript
// Agent types
export interface AgentExecution {
    id: string;
    agent_type: "research" | "case_prep";
    status: "running" | "waiting_input" | "completed" | "failed" | "cancelled";
    input_data: Record<string, unknown>;
    result_data: Record<string, unknown> | null;
    current_step: string | null;
    steps_completed: number;
    total_steps: number | null;
    created_at: string;
    updated_at: string;
    completed_at: string | null;
    error_message: string | null;
}

export interface AgentStreamEvent {
    type: "status" | "progress" | "result" | "checkpoint" | "memo" | "done" | "error";
    step?: string;
    message?: string;
    steps_completed?: number;
    total_steps?: number;
    data?: unknown;
    question?: string;
    options?: string[];
    context?: Record<string, unknown>;
    content?: string;
    execution_id?: string;
    status?: string;
    recoverable?: boolean;
}

export interface AgentCheckpoint {
    question: string;
    context: Record<string, unknown>;
}
```

**Step 2:** Add API functions to `api.ts`:
```typescript
export function runResearchAgent(
    query: string,
    onEvent: (event: AgentStreamEvent) => void,
    onError?: (error: Error) => void,
): AbortController { ... }

export function runCasePrepAgent(
    documentId: string,
    onEvent: (event: AgentStreamEvent) => void,
    onError?: (error: Error) => void,
): AbortController { ... }

export function resumeAgentExecution(
    executionId: string,
    input: string,
    onEvent: (event: AgentStreamEvent) => void,
    onError?: (error: Error) => void,
): AbortController { ... }

export async function getAgentExecutions(page?: number): Promise<{executions: AgentExecution[], total: number}> { ... }

export async function getAgentExecution(id: string): Promise<AgentExecution> { ... }

export async function cancelAgentExecution(id: string): Promise<void> { ... }
```

The SSE streaming functions follow the same `_streamChat` pattern: fetch with ReadableStream reader, parse `data: ` lines, call onEvent callback.

**Step 3:** Commit:
```bash
git commit -m "feat: add agent types and API functions to frontend"
```

---

### Task 13: Frontend — Shared Agent Components

**Files:**
- Create: `frontend/src/components/agent-step-timeline.tsx`
- Create: `frontend/src/components/agent-checkpoint-prompt.tsx`
- Create: `frontend/src/components/agent-memo-viewer.tsx`
- Create: `frontend/src/components/agent-hub-card.tsx`

**Step 1:** Create `agent-step-timeline.tsx`:
- Props: `steps: {name: string, status: "pending" | "active" | "completed"}[]`
- Vertical list with status icons (checkmark/spinner/circle)
- Highlight active step

**Step 2:** Create `agent-checkpoint-prompt.tsx`:
- Props: `question: string, context: Record<string, unknown>, onSubmit: (input: string) => void, disabled: boolean`
- Card with question text, optional context display, text input, submit button

**Step 3:** Create `agent-memo-viewer.tsx`:
- Props: `content: string, citations: {case_id: string, title: string}[]`
- Render markdown content with clickable case citation links (Link to /case/[id])

**Step 4:** Create `agent-hub-card.tsx`:
- Props: `title: string, description: string, icon: ReactNode, href: string`
- Card component with icon, title, description, "Start" button linking to workspace

**Step 5:** Commit:
```bash
git commit -m "feat: add shared agent UI components"
```

---

### Task 14: Frontend — Agent Hub Page

**Files:**
- Create: `frontend/src/app/agents/page.tsx`
- Create: `frontend/src/__tests__/agents-hub.test.tsx`

**Step 1:** Write test:
```typescript
describe("AgentsPage", () => {
    it("renders research agent card", () => { ... });
    it("renders case prep agent card", () => { ... });
    it("links to correct workspaces", () => { ... });
});
```

**Step 2:** Create `agents/page.tsx`:
- Two `AgentHubCard` components: Research Agent + Case Prep Agent
- Each links to `/agents/research` and `/agents/case-prep`
- Brief descriptions of what each agent does
- Auth-protected (redirect to /login if not authenticated)

**Step 3:** Run test, verify pass.

**Step 4:** Commit:
```bash
git commit -m "feat: add Agent Hub page"
```

---

### Task 15: Frontend — Research Agent Workspace

**Files:**
- Create: `frontend/src/app/agents/research/page.tsx`
- Create: `frontend/src/__tests__/research-workspace.test.tsx`

**Step 1:** Write tests:
- `test_renders_input_form`
- `test_submitting_query_starts_stream`
- `test_displays_step_timeline_during_execution`
- `test_renders_checkpoint_prompt_on_interrupt`
- `test_displays_final_memo`

**Step 2:** Create `agents/research/page.tsx`:

Layout: Left sidebar (AgentStepTimeline) + Main area (input → streaming output → checkpoint prompts → final memo)

Key state:
```typescript
const [query, setQuery] = useState("")
const [isRunning, setIsRunning] = useState(false)
const [executionId, setExecutionId] = useState<string | null>(null)
const [steps, setSteps] = useState<Step[]>([])
const [checkpoint, setCheckpoint] = useState<AgentCheckpoint | null>(null)
const [memo, setMemo] = useState<string>("")
const [sources, setSources] = useState<SearchResultItem[]>([])
const abortRef = useRef<AbortController | null>(null)
```

SSE event handling (same pattern as chat page):
- `status` → update steps timeline
- `progress` → update step counts
- `result` → display intermediate results
- `checkpoint` → show AgentCheckpointPrompt, pause
- `memo` → set memo content
- `done` → finalize, show AgentMemoViewer

Resume flow: when user submits at checkpoint → call `resumeAgentExecution()` → continue SSE stream.

**Step 3:** Run tests, verify pass.

**Step 4:** Commit:
```bash
git commit -m "feat: add Research Agent workspace page"
```

---

### Task 16: Frontend — Case Prep Agent Workspace

**Files:**
- Create: `frontend/src/app/agents/case-prep/page.tsx`
- Create: `frontend/src/__tests__/case-prep-workspace.test.tsx`

**Step 1:** Write tests (same pattern as Task 15).

**Step 2:** Create `agents/case-prep/page.tsx`:

Same layout as Research workspace but:
- Input: document selector dropdown (fetches from `getDocuments()`, filters to `status === "completed"`)
- Shows existing analysis summary before starting
- Strategy memo output instead of research memo

**Step 3:** Run tests, verify pass.

**Step 4:** Commit:
```bash
git commit -m "feat: add Case Prep Agent workspace page"
```

---

### Task 17: Frontend — Execution History Page

**Files:**
- Create: `frontend/src/app/agents/history/page.tsx`

**Step 1:** Create `agents/history/page.tsx`:
- Paginated list of past executions from `getAgentExecutions()`
- Each row: agent type badge, input summary, status badge, created_at, click to view results
- Completed executions: click shows result in AgentMemoViewer
- Running/waiting: link to resume in workspace

**Step 2:** Commit:
```bash
git commit -m "feat: add agent execution history page"
```

---

### Task 18: Header Navigation + Integration

**Files:**
- Modify: `frontend/src/components/header.tsx`

**Step 1:** Add Agents link to header nav (both desktop and mobile):
- Import `Bot` icon from lucide-react
- Add nav button between Graph and Judges:
  ```tsx
  <Button variant="ghost" size="sm" className="text-xs uppercase tracking-wider font-medium h-8 px-3" asChild>
      <Link href="/agents"><Bot className="h-3.5 w-3.5 mr-1" /> Agents</Link>
  </Button>
  ```
- Same for mobile dropdown

**Step 2:** Commit:
```bash
git commit -m "feat: add Agents link to header navigation"
```

---

### Task 19: Run All Tests + Final Verification

**Step 1:** Run all backend tests:
```bash
cd backend && python -m pytest -v
```
Expected: ~290+ tests pass (250 existing + ~40 new)

**Step 2:** Run all frontend tests:
```bash
cd frontend && pnpm test
```
Expected: ~142+ tests pass (127 existing + ~15 new)

**Step 3:** Run frontend build:
```bash
cd frontend && pnpm build
```
Expected: clean build

**Step 4:** Commit any fixes needed.

---

### Task 20: Update PHASE_PLAN.md + Documentation

**Files:**
- Modify: `docs/PHASE_PLAN.md` — check all Phase 6 boxes
- Modify: `docs/CLAUDE.md` — update current phase to "Phase 7"
- Modify: `C:\Users\yadav\.claude\projects\d--Startup-Smriti\memory\MEMORY.md` — update phase status

**Step 1:** Update docs.

**Step 2:** Commit:
```bash
git commit -m "docs: mark Phase 6 complete, update project docs"
```

---

## Task Dependency Graph

```
Task 1 (deps) → Task 2 (model) → Task 3 (state)
                                      ↓
Task 4 (prompts) ──────────────→ Task 5 (checkpointer)
                                      ↓
                                 Task 6 (common nodes)
                                   ↓           ↓
                            Task 7 (research)  Task 9 (case prep)
                            Task 8 (graph)     Task 10 (graph)
                                   ↓           ↓
                                 Task 11 (API routes)
                                      ↓
                                 Task 12 (FE types+api)
                                      ↓
                                 Task 13 (FE components)
                                   ↓     ↓       ↓
                            Task 14  Task 15  Task 16  Task 17
                              (hub)  (research) (case-prep) (history)
                                   ↓
                                 Task 18 (header nav)
                                      ↓
                                 Task 19 (final tests)
                                      ↓
                                 Task 20 (docs update)
```

**Total: 20 tasks, ~40 new backend tests, ~15 new frontend tests**
