"""Agent execution API routes with SSE streaming and HITL checkpoints."""

from __future__ import annotations

import json
import logging
import uuid
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Query
from app.security.rate_limiter import rate_limit_dependency
from fastapi.responses import StreamingResponse
from langgraph.types import Command
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.agents.case_prep import build_case_prep_graph
from app.core.agents.research import build_research_graph
from app.core.dependencies import (
    get_checkpointer,
    get_embedder,
    get_graph_store,
    get_llm,
    get_reranker,
    get_vector_store,
)
from app.db.postgres import get_db
from app.models.agent_execution import AgentExecution, AgentStatus, AgentType
from app.security.auth import TokenPayload
from app.security.rbac import get_current_user
from app.security.sanitizer import sanitize_search_query, detect_prompt_injection

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Module-level store for active graph checkpointers (MVP: single-server)
# ---------------------------------------------------------------------------

_active_checkpointers: dict[str, object] = {}

# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class ResearchRequest(BaseModel):
    query: str = Field(..., min_length=5, max_length=5000)


class CasePrepRequest(BaseModel):
    document_id: str = Field(...)


class ResumeRequest(BaseModel):
    input: str = Field(..., min_length=1, max_length=5000)


# ---------------------------------------------------------------------------
# SSE streaming helper
# ---------------------------------------------------------------------------


async def _stream_agent_events(
    graph,  # noqa: ANN001
    initial_input: dict,
    config: dict,
    execution: AgentExecution,
    db: AsyncSession,
) -> AsyncIterator[str]:
    """Stream SSE events from agent graph execution."""
    try:
        async for event in graph.astream(
            initial_input, config=config, stream_mode="updates"
        ):
            for node_name, node_output in event.items():
                sse_event = {
                    "type": "status",
                    "step": node_name,
                    "message": f"Completed: {node_name}",
                }
                yield f"data: {json.dumps(sse_event)}\n\n"

        # Check if we are at an interrupt (HITL checkpoint)
        state = await graph.aget_state(config)
        if state.next:
            # There are pending nodes -- graph paused at an interrupt
            interrupt_value = None
            if hasattr(state, "tasks") and state.tasks:
                for task in state.tasks:
                    if hasattr(task, "interrupts") and task.interrupts:
                        interrupt_value = task.interrupts[0].value
                        break

            execution.status = AgentStatus.waiting_input.value
            execution.current_step = state.next[0] if state.next else None
            await db.commit()

            checkpoint_data = {
                "type": "checkpoint",
                "question": (
                    interrupt_value.get("question", "")
                    if isinstance(interrupt_value, dict)
                    else str(interrupt_value or "")
                ),
                "context": (
                    interrupt_value
                    if isinstance(interrupt_value, dict)
                    else {"value": interrupt_value}
                ),
            }
            yield f"data: {json.dumps(checkpoint_data)}\n\n"
        else:
            # Graph completed normally
            final_state = state.values
            execution.status = AgentStatus.completed.value
            execution.result_data = {
                "memo": (
                    final_state.get("draft_memo")
                    or final_state.get("enhanced_memo", "")
                ),
                "confidence": final_state.get("confidence", 0),
            }
            execution.completed_at = func.now()
            await db.commit()

            yield f"data: {json.dumps({'type': 'memo', 'content': execution.result_data['memo']})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'execution_id': str(execution.id), 'status': 'completed'})}\n\n"

    except Exception as exc:
        logger.exception("Agent execution %s failed", execution.id)
        execution.status = AgentStatus.failed.value
        execution.error_message = str(exc)[:2000]
        await db.commit()
        yield f"data: {json.dumps({'type': 'error', 'message': 'Agent execution failed. Please try again.', 'recoverable': False})}\n\n"
    finally:
        # Clean up checkpointer to prevent memory leak
        _active_checkpointers.pop(str(execution.id), None)


# ---------------------------------------------------------------------------
# POST /{agent_type}/run -- Start agent execution, return SSE stream
# ---------------------------------------------------------------------------


@router.post("/{agent_type}/run", dependencies=[Depends(rate_limit_dependency("10/minute"))])
async def run_agent(
    agent_type: str,
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    request_body: ResearchRequest | CasePrepRequest | None = None,
) -> StreamingResponse:
    """Start an agent execution and stream SSE events."""
    # Validate agent_type
    if agent_type not in ("research", "case_prep"):
        raise HTTPException(
            status_code=422,
            detail=f"Invalid agent_type '{agent_type}'. Must be 'research' or 'case_prep'.",
        )

    # Parse request body based on agent_type
    if request_body is None:
        raise HTTPException(status_code=422, detail="Request body is required.")

    # Sanitize user input for research queries
    if isinstance(request_body, ResearchRequest):
        if detect_prompt_injection(request_body.query):
            raise HTTPException(status_code=400, detail="Input contains potentially harmful content")
        request_body.query = sanitize_search_query(request_body.query)

    # Create checkpointer
    checkpointer = get_checkpointer()
    thread_id = str(uuid.uuid4())

    # Create execution record
    execution = AgentExecution(
        user_id=uuid.UUID(user.sub),
        agent_type=agent_type,
        status=AgentStatus.running.value,
        thread_id=uuid.UUID(thread_id),
        input_data=(
            {"query": request_body.query}
            if isinstance(request_body, ResearchRequest)
            else {"document_id": request_body.document_id}
        ),
    )
    db.add(execution)
    await db.commit()
    await db.refresh(execution)

    # Store checkpointer for potential resume
    _active_checkpointers[str(execution.id)] = checkpointer

    # Build graph and initial state
    llm = get_llm()
    embedder = get_embedder()
    vector_store = get_vector_store()
    reranker = get_reranker()

    config = {"configurable": {"thread_id": thread_id}}

    if agent_type == "research":
        graph = build_research_graph(
            llm=llm,
            flash_llm=llm,  # Use same LLM for flash in MVP
            embedder=embedder,
            vector_store=vector_store,
            reranker=reranker,
            db=db,
            checkpointer=checkpointer,
        )
        initial_input = {"query": request_body.query}
    else:
        graph_store = get_graph_store()
        graph = build_case_prep_graph(
            llm=llm,
            flash_llm=llm,
            embedder=embedder,
            vector_store=vector_store,
            reranker=reranker,
            graph_store=graph_store,
            db=db,
            checkpointer=checkpointer,
        )
        initial_input = {"document_id": request_body.document_id}

    return StreamingResponse(
        _stream_agent_events(graph, initial_input, config, execution, db),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# GET /executions -- List user's executions (paginated)
# ---------------------------------------------------------------------------


@router.get("/executions")
async def list_executions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List agent executions for the current user."""
    user_uuid = uuid.UUID(user.sub)

    count_stmt = (
        select(func.count())
        .select_from(AgentExecution)
        .where(AgentExecution.user_id == user_uuid)
    )
    total = (await db.execute(count_stmt)).scalar_one()

    offset = (page - 1) * page_size
    stmt = (
        select(AgentExecution)
        .where(AgentExecution.user_id == user_uuid)
        .order_by(AgentExecution.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    executions = result.scalars().all()

    return {
        "executions": [
            {
                "id": str(e.id),
                "agent_type": e.agent_type,
                "status": e.status,
                "input_data": e.input_data,
                "current_step": e.current_step,
                "steps_completed": e.steps_completed,
                "total_steps": e.total_steps,
                "created_at": str(e.created_at),
                "completed_at": str(e.completed_at) if e.completed_at else None,
            }
            for e in executions
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ---------------------------------------------------------------------------
# GET /executions/{execution_id} -- Get execution detail
# ---------------------------------------------------------------------------


@router.get("/executions/{execution_id}")
async def get_execution(
    execution_id: str,
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get details of a specific agent execution."""
    try:
        exec_uuid = uuid.UUID(execution_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid execution_id format.")

    stmt = select(AgentExecution).where(AgentExecution.id == exec_uuid)
    result = await db.execute(stmt)
    execution = result.scalar_one_or_none()

    if execution is None:
        raise HTTPException(status_code=404, detail="Execution not found.")

    if str(execution.user_id) != user.sub:
        raise HTTPException(status_code=403, detail="Access denied.")

    return {
        "id": str(execution.id),
        "agent_type": execution.agent_type,
        "status": execution.status,
        "input_data": execution.input_data,
        "result_data": execution.result_data,
        "thread_id": str(execution.thread_id),
        "current_step": execution.current_step,
        "steps_completed": execution.steps_completed,
        "total_steps": execution.total_steps,
        "error_message": execution.error_message,
        "created_at": str(execution.created_at),
        "updated_at": str(execution.updated_at),
        "completed_at": str(execution.completed_at) if execution.completed_at else None,
    }


# ---------------------------------------------------------------------------
# POST /executions/{execution_id}/resume -- Resume with user input
# ---------------------------------------------------------------------------


@router.post("/executions/{execution_id}/resume")
async def resume_execution(
    execution_id: str,
    body: ResumeRequest,
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Resume a paused agent execution with user input."""
    try:
        exec_uuid = uuid.UUID(execution_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid execution_id format.")

    stmt = select(AgentExecution).where(AgentExecution.id == exec_uuid)
    result = await db.execute(stmt)
    execution = result.scalar_one_or_none()

    if execution is None:
        raise HTTPException(status_code=404, detail="Execution not found.")

    if str(execution.user_id) != user.sub:
        raise HTTPException(status_code=403, detail="Access denied.")

    # Sanitize resume input
    if detect_prompt_injection(body.input):
        raise HTTPException(status_code=400, detail="Input contains potentially harmful content")
    body.input = sanitize_search_query(body.input)

    if execution.status != AgentStatus.waiting_input.value:
        raise HTTPException(
            status_code=400,
            detail=f"Execution is not awaiting input (status: {execution.status}).",
        )

    checkpointer = _active_checkpointers.get(execution_id)
    if checkpointer is None:
        raise HTTPException(
            status_code=410,
            detail="Checkpoint expired. Please start a new execution.",
        )

    # Atomically transition status to prevent concurrent resume race condition
    result = await db.execute(
        text(
            "UPDATE agent_executions SET status = 'running' "
            "WHERE id = :id AND status = 'waiting_input' RETURNING id"
        ),
        {"id": exec_uuid},
    )
    if not result.fetchone():
        raise HTTPException(
            status_code=409,
            detail="Execution is not in waiting_input state",
        )
    await db.commit()

    # Rebuild graph with same checkpointer
    llm = get_llm()
    embedder = get_embedder()
    vector_store = get_vector_store()
    reranker = get_reranker()

    config = {"configurable": {"thread_id": str(execution.thread_id)}}

    if execution.agent_type == AgentType.research.value:
        graph = build_research_graph(
            llm=llm,
            flash_llm=llm,
            embedder=embedder,
            vector_store=vector_store,
            reranker=reranker,
            db=db,
            checkpointer=checkpointer,
        )
    else:
        graph_store = get_graph_store()
        graph = build_case_prep_graph(
            llm=llm,
            flash_llm=llm,
            embedder=embedder,
            vector_store=vector_store,
            reranker=reranker,
            graph_store=graph_store,
            db=db,
            checkpointer=checkpointer,
        )

    # Resume with Command
    resume_input = Command(resume=body.input)

    return StreamingResponse(
        _stream_agent_events(graph, resume_input, config, execution, db),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# DELETE /executions/{execution_id} -- Cancel execution
# ---------------------------------------------------------------------------


@router.delete("/executions/{execution_id}")
async def cancel_execution(
    execution_id: str,
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Cancel an agent execution."""
    try:
        exec_uuid = uuid.UUID(execution_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid execution_id format.")

    stmt = select(AgentExecution).where(AgentExecution.id == exec_uuid)
    result = await db.execute(stmt)
    execution = result.scalar_one_or_none()

    if execution is None:
        raise HTTPException(status_code=404, detail="Execution not found.")

    if str(execution.user_id) != user.sub:
        raise HTTPException(status_code=403, detail="Access denied.")

    if execution.status in (
        AgentStatus.completed.value,
        AgentStatus.failed.value,
        AgentStatus.cancelled.value,
    ):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel execution with status '{execution.status}'.",
        )

    execution.status = AgentStatus.cancelled.value
    await db.commit()

    # Clean up checkpointer
    _active_checkpointers.pop(execution_id, None)

    return {"status": "cancelled", "execution_id": execution_id}
