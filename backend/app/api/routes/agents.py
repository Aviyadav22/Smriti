"""Agent execution API routes with SSE streaming and HITL checkpoints."""

from __future__ import annotations

import json
import logging
import re
import uuid
from typing import AsyncIterator

from cachetools import TTLCache

from fastapi import APIRouter, Depends, HTTPException, Query
from app.security.rate_limiter import rate_limit_dependency
from fastapi.responses import StreamingResponse
from langgraph.types import Command
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.agents.case_prep import build_case_prep_graph
from app.core.agents.drafting import build_drafting_graph
from app.core.agents.research import build_research_graph
from app.core.agents.strategy import build_strategy_graph
from app.core.dependencies import (
    get_checkpointer,
    get_embedder,
    get_flash_llm,
    get_graph_store,
    get_llm,
    get_reranker,
    get_vector_store,
)
from app.core.drafting.export import export_to_docx, export_to_pdf
from app.core.drafting.templates import TEMPLATES, get_template
from app.db.postgres import async_session_factory, get_db
from app.models.agent_execution import AgentExecution, AgentStatus, AgentType
from app.security.audit import create_audit_log
from app.security.auth import TokenPayload
from app.security.rbac import get_current_user
from app.security.sanitizer import sanitize_search_query, detect_prompt_injection

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Module-level store for active graph checkpointers (MVP: single-server)
# Uses TTLCache to automatically evict entries after 1 hour, preventing
# memory leaks from abandoned SSE connections. In production, use
# AsyncPostgresSaver checkpointing (no in-memory map needed).
# ---------------------------------------------------------------------------

_CHECKPOINTER_TTL_SECONDS = 3600  # 1 hour

_active_checkpointers: TTLCache[str, object] = TTLCache(
    maxsize=1024, ttl=_CHECKPOINTER_TTL_SECONDS
)

# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class ResearchRequest(BaseModel):
    query: str = Field(..., min_length=5, max_length=5000)
    language: str = Field(default="en", pattern="^(en|hi)$")


class CasePrepRequest(BaseModel):
    document_id: str = Field(...)
    language: str = Field(default="en", pattern="^(en|hi)$")

    @field_validator("document_id")
    @classmethod
    def validate_document_id_as_uuid(cls, v: str) -> str:
        """Ensure document_id is a valid UUID."""
        try:
            uuid.UUID(v)
        except ValueError:
            raise ValueError("document_id must be a valid UUID")
        return v


class StrategyRequest(BaseModel):
    case_facts: str = Field(..., min_length=20, max_length=20000)
    desired_relief: str = Field(..., min_length=5, max_length=2000)
    target_judge: str = Field(default="", max_length=200)
    target_bench: str = Field(default="", max_length=50)
    language: str = Field(default="en", pattern="^(en|hi)$")


class PrecedentRef(BaseModel):
    citation: str = Field(..., max_length=500)
    title: str = Field(default="", max_length=500)


class DraftingRequest(BaseModel):
    doc_type: str = Field(..., min_length=1, max_length=50)
    case_facts: str = Field(..., min_length=20, max_length=20000)
    target_court: str = Field(default="", max_length=200)
    relevant_precedents: list[PrecedentRef] = Field(default_factory=list)
    additional_context: dict[str, str] = Field(default_factory=dict)
    language: str = Field(default="en", pattern="^(en|hi)$")

    @field_validator("relevant_precedents")
    @classmethod
    def validate_precedents_length(cls, v: list[PrecedentRef]) -> list[PrecedentRef]:
        if len(v) > 20:
            raise ValueError("Maximum 20 precedent references allowed")
        return v

    @field_validator("additional_context")
    @classmethod
    def validate_additional_context(cls, v: dict[str, str]) -> dict[str, str]:
        if len(v) > 10:
            raise ValueError("Maximum 10 additional_context keys allowed")
        for key, val in v.items():
            if len(val) > 2000:
                raise ValueError(f"additional_context value for '{key}' exceeds 2000 characters")
        return v


class ResumeRequest(BaseModel):
    input: str = Field(..., min_length=1, max_length=5000)


# ---------------------------------------------------------------------------
# SSE streaming helper
# ---------------------------------------------------------------------------


async def _stream_agent_events(
    graph,  # noqa: ANN001
    initial_input: dict,
    config: dict,
    exec_id: uuid.UUID,
) -> AsyncIterator[str]:
    """Stream SSE events from agent graph execution.

    IMPORTANT: This generator runs AFTER the FastAPI endpoint returns, so the
    Depends(get_db) session is already closed. All DB updates use independent
    sessions created via async_session_factory().

    Uses an async queue + background task pattern so we can send SSE keepalive
    heartbeats every 15 seconds while waiting for long-running graph nodes
    (e.g. LLM calls that take 30-60s).
    """
    import asyncio

    _KEEPALIVE_INTERVAL = 15  # seconds between heartbeat comments
    _GRAPH_TIMEOUT = 600  # 10 minutes max for entire graph execution
    _SENTINEL = object()  # signals the producer is done

    queue: asyncio.Queue[str | object] = asyncio.Queue()
    is_checkpoint = False

    async def _run_graph() -> None:
        """Producer: iterate graph events and push SSE strings into queue."""
        nonlocal is_checkpoint
        try:
            async for event in graph.astream(
                initial_input, config=config, stream_mode="updates"
            ):
                for node_name, node_output in event.items():
                    sse_event = {
                        "type": "status",
                        "execution_id": str(exec_id),
                        "step": node_name,
                        "message": f"Completed: {node_name}",
                    }
                    await queue.put(f"data: {json.dumps(sse_event)}\n\n")

            # Check if we are at an interrupt (HITL checkpoint)
            state = await graph.aget_state(config)

            if state.next:
                is_checkpoint = True
                interrupt_value = None
                if hasattr(state, "tasks") and state.tasks:
                    for task in state.tasks:
                        if hasattr(task, "interrupts") and task.interrupts:
                            interrupt_value = task.interrupts[0].value
                            break

                current_step = state.next[0] if state.next else None
                async with async_session_factory() as db:
                    await db.execute(
                        text(
                            "UPDATE agent_executions SET status = 'waiting_input', "
                            "current_step = :step WHERE id = :id"
                        ),
                        {"id": exec_id, "step": current_step},
                    )
                    await db.commit()

                checkpoint_data = {
                    "type": "checkpoint",
                    "execution_id": str(exec_id),
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
                await queue.put(f"data: {json.dumps(checkpoint_data)}\n\n")
            else:
                # Graph completed normally
                final_state = state.values
                result_data = {
                    "memo": (
                        final_state.get("draft_memo")
                        or final_state.get("enhanced_memo")
                        or final_state.get("strategy_memo")
                        or final_state.get("full_draft")
                        or ""
                    ),
                    "confidence": final_state.get("confidence", 0),
                }
                async with async_session_factory() as db:
                    await db.execute(
                        text(
                            "UPDATE agent_executions SET status = 'completed', "
                            "result_data = :data, completed_at = now() WHERE id = :id"
                        ),
                        {"id": exec_id, "data": json.dumps(result_data)},
                    )
                    await db.commit()

                await queue.put(f"data: {json.dumps({'type': 'memo', 'execution_id': str(exec_id), 'content': result_data['memo'], 'data': {'confidence': result_data['confidence']}})}\n\n")
                await queue.put(f"data: {json.dumps({'type': 'done', 'execution_id': str(exec_id), 'status': 'completed'})}\n\n")

        except Exception as exc:
            logger.exception("Agent execution %s failed", exec_id)
            try:
                async with async_session_factory() as db:
                    await db.execute(
                        text(
                            "UPDATE agent_executions SET status = 'failed', "
                            "error_message = :msg WHERE id = :id"
                        ),
                        {"id": exec_id, "msg": str(exc)[:2000]},
                    )
                    await db.commit()
            except Exception:
                logger.exception("Failed to update execution %s status to failed", exec_id)
            await queue.put(f"data: {json.dumps({'type': 'error', 'message': 'Agent execution failed. Please try again.', 'recoverable': False})}\n\n")
            _active_checkpointers.pop(str(exec_id), None)
        finally:
            await queue.put(_SENTINEL)

    async def _run_graph_with_timeout() -> None:
        """Wrap _run_graph with an overall execution timeout."""
        try:
            await asyncio.wait_for(_run_graph(), timeout=_GRAPH_TIMEOUT)
        except asyncio.TimeoutError:
            logger.error("Agent execution %s timed out after %d seconds", exec_id, _GRAPH_TIMEOUT)
            # Update DB status to failed
            try:
                async with async_session_factory() as db:
                    await db.execute(
                        text(
                            "UPDATE agent_executions SET status = 'failed', "
                            "error_message = :msg WHERE id = :id"
                        ),
                        {"id": exec_id, "msg": f"Agent execution timed out after {_GRAPH_TIMEOUT // 60} minutes"},
                    )
                    await db.commit()
            except Exception:
                logger.exception("Failed to update execution %s status after timeout", exec_id)
            # Send timeout error event to client
            await queue.put(
                f"data: {json.dumps({'type': 'error', 'message': 'Agent execution timed out after 10 minutes', 'recoverable': False})}\n\n"
            )
            _active_checkpointers.pop(str(exec_id), None)
            await queue.put(_SENTINEL)

    # Launch the graph producer as a background task (with timeout guard)
    task = asyncio.create_task(_run_graph_with_timeout())

    try:
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=_KEEPALIVE_INTERVAL)
            except asyncio.TimeoutError:
                # No event within interval — send SSE keepalive comment
                yield ": keepalive\n\n"
                continue

            if item is _SENTINEL:
                break
            yield item  # type: ignore[misc]
    finally:
        # Clean up checkpointer if graph completed (not paused at checkpoint)
        if not is_checkpoint:
            _active_checkpointers.pop(str(exec_id), None)
        if not task.done():
            task.cancel()


# ---------------------------------------------------------------------------
# POST /{agent_type}/run -- Start agent execution, return SSE stream
# ---------------------------------------------------------------------------


@router.post("/{agent_type}/run", dependencies=[Depends(rate_limit_dependency("10/minute"))])
async def run_agent(
    agent_type: str,
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    request_body: ResearchRequest | CasePrepRequest | StrategyRequest | DraftingRequest | None = None,
) -> StreamingResponse:
    """Start an agent execution and stream SSE events."""
    # Validate agent_type
    if agent_type not in ("research", "case_prep", "strategy", "drafting"):
        raise HTTPException(
            status_code=422,
            detail=f"Invalid agent_type '{agent_type}'. Must be 'research', 'case_prep', 'strategy', or 'drafting'.",
        )

    # Parse request body based on agent_type
    if request_body is None:
        raise HTTPException(status_code=422, detail="Request body is required.")

    # Sanitize user input for research queries
    if isinstance(request_body, ResearchRequest):
        if detect_prompt_injection(request_body.query):
            raise HTTPException(status_code=400, detail="Input contains potentially harmful content")
        request_body.query = sanitize_search_query(request_body.query)

    if isinstance(request_body, StrategyRequest):
        for field_name in ("case_facts", "desired_relief", "target_judge", "target_bench"):
            value = getattr(request_body, field_name)
            if value and detect_prompt_injection(value):
                raise HTTPException(status_code=400, detail="Input contains potentially harmful content")
            if value:
                setattr(request_body, field_name, sanitize_search_query(value))

    if isinstance(request_body, DraftingRequest):
        for field_name in ("case_facts", "target_court"):
            value = getattr(request_body, field_name)
            if value and detect_prompt_injection(value):
                raise HTTPException(status_code=400, detail="Input contains potentially harmful content")
            if value:
                setattr(request_body, field_name, sanitize_search_query(value))

        # Validate doc_type against known templates at submission time
        if request_body.doc_type not in TEMPLATES:
            raise HTTPException(
                status_code=422,
                detail=f"Unknown doc_type. Valid types: {list(TEMPLATES.keys())}",
            )

    # Create checkpointer
    checkpointer = get_checkpointer()
    thread_id = str(uuid.uuid4())

    # Extract language from request body (defaults to "en")
    request_language = getattr(request_body, "language", "en") or "en"

    # Create execution record
    if isinstance(request_body, ResearchRequest):
        input_data = {"query": request_body.query}
    elif isinstance(request_body, CasePrepRequest):
        input_data = {"document_id": request_body.document_id}
    elif isinstance(request_body, StrategyRequest):
        input_data = {
            "case_facts": request_body.case_facts,
            "desired_relief": request_body.desired_relief,
            "target_judge": request_body.target_judge,
            "target_bench": request_body.target_bench,
        }
    else:
        input_data = {
            "doc_type": request_body.doc_type,
            "case_facts": request_body.case_facts,
            "target_court": request_body.target_court,
            "relevant_precedents": [p.model_dump() for p in request_body.relevant_precedents],
            "additional_context": request_body.additional_context,
        }
    # Store language in input_data for downstream use
    input_data["language"] = request_language

    execution = AgentExecution(
        user_id=uuid.UUID(user.sub),
        agent_type=agent_type,
        status=AgentStatus.running.value,
        thread_id=uuid.UUID(thread_id),
        input_data=input_data,
    )
    db.add(execution)
    await db.commit()
    await db.refresh(execution)

    # Store checkpointer for potential resume (TTLCache auto-evicts after 1 hour)
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
            flash_llm=get_flash_llm(),
            embedder=embedder,
            vector_store=vector_store,
            reranker=reranker,
            checkpointer=checkpointer,
        )
        initial_input = {"query": request_body.query, "language": request_language}
    elif agent_type == "case_prep":
        graph_store = get_graph_store()
        graph = build_case_prep_graph(
            llm=llm,
            embedder=embedder,
            vector_store=vector_store,
            reranker=reranker,
            graph_store=graph_store,
            checkpointer=checkpointer,
        )
        initial_input = {"document_id": request_body.document_id, "language": request_language}
    elif agent_type == "strategy":
        graph_store = get_graph_store()
        graph = build_strategy_graph(
            llm=llm,
            flash_llm=get_flash_llm(),
            embedder=embedder,
            vector_store=vector_store,
            reranker=reranker,
            graph_store=graph_store,
            checkpointer=checkpointer,
        )
        initial_input = {
            "case_facts": request_body.case_facts,
            "desired_relief": request_body.desired_relief,
            "target_judge": request_body.target_judge,
            "target_bench": request_body.target_bench,
            "language": request_language,
        }
    elif agent_type == "drafting":
        graph = build_drafting_graph(
            llm=llm,
            flash_llm=get_flash_llm(),
            embedder=embedder,
            vector_store=vector_store,
            reranker=reranker,
            checkpointer=checkpointer,
        )
        initial_input = {
            "doc_type": request_body.doc_type,
            "case_facts": request_body.case_facts,
            "target_court": request_body.target_court,
            "relevant_precedents": [p.model_dump() for p in request_body.relevant_precedents],
            "additional_context": request_body.additional_context,
            "language": request_language,
        }
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported agent type: {agent_type}",
        )

    # Audit log: agent invocation
    await create_audit_log(
        db=db,
        action="agent.run",
        user_id=user.sub,
        resource_type="agent_execution",
        resource_id=str(execution.id),
        metadata={"agent_type": agent_type, "thread_id": thread_id},
    )

    return StreamingResponse(
        _stream_agent_events(graph, initial_input, config, execution.id),
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
                "result_data": e.result_data,
                "current_step": e.current_step,
                "steps_completed": e.steps_completed,
                "total_steps": e.total_steps,
                "error_message": e.error_message,
                "created_at": str(e.created_at),
                "updated_at": str(e.updated_at),
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


@router.post("/executions/{execution_id}/resume", dependencies=[Depends(rate_limit_dependency("10/minute"))])
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
        # In production (AsyncPostgresSaver), state is persisted to DB — recreate checkpointer
        checkpointer = get_checkpointer()
        _active_checkpointers[execution_id] = checkpointer

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
            flash_llm=get_flash_llm(),
            embedder=embedder,
            vector_store=vector_store,
            reranker=reranker,
            checkpointer=checkpointer,
        )
    elif execution.agent_type == AgentType.case_prep.value:
        graph_store = get_graph_store()
        graph = build_case_prep_graph(
            llm=llm,
            embedder=embedder,
            vector_store=vector_store,
            reranker=reranker,
            graph_store=graph_store,
            checkpointer=checkpointer,
        )
    elif execution.agent_type == AgentType.strategy.value:
        graph_store = get_graph_store()
        graph = build_strategy_graph(
            llm=llm,
            flash_llm=get_flash_llm(),
            embedder=embedder,
            vector_store=vector_store,
            reranker=reranker,
            graph_store=graph_store,
            checkpointer=checkpointer,
        )
    elif execution.agent_type == AgentType.drafting.value:
        graph = build_drafting_graph(
            llm=llm,
            flash_llm=get_flash_llm(),
            embedder=embedder,
            vector_store=vector_store,
            reranker=reranker,
            checkpointer=checkpointer,
        )
    else:
        # Should not happen due to DB constraint, but guard against it
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported agent type: {execution.agent_type}",
        )

    # Resume with Command
    resume_input = Command(resume=body.input)

    # Audit log: agent resume
    await create_audit_log(
        db=db,
        action="agent.resume",
        user_id=user.sub,
        resource_type="agent_execution",
        resource_id=execution_id,
        metadata={"agent_type": execution.agent_type},
    )

    return StreamingResponse(
        _stream_agent_events(graph, resume_input, config, exec_uuid),
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

    # Audit log: agent cancellation
    await create_audit_log(
        db=db,
        action="agent.cancel",
        user_id=user.sub,
        resource_type="agent_execution",
        resource_id=execution_id,
        metadata={"agent_type": execution.agent_type},
    )

    return {"status": "cancelled", "execution_id": execution_id}


# ---------------------------------------------------------------------------
# GET /drafting/templates -- List available document templates
# ---------------------------------------------------------------------------


@router.get("/drafting/templates")
async def get_drafting_templates(
    user: TokenPayload = Depends(get_current_user),
) -> dict:
    """Return available document templates for the Drafting Agent."""
    return {
        "templates": [
            {
                "doc_type": t.doc_type,
                "display_name": t.display_name,
                "sections": t.sections,
                "required_fields": t.required_fields,
                "statutory_basis": t.statutory_basis,
            }
            for t in TEMPLATES.values()
        ]
    }


# ---------------------------------------------------------------------------
# POST /drafting/export/{execution_id} -- Export draft as DOCX or PDF
# ---------------------------------------------------------------------------


@router.post("/drafting/export/{execution_id}", dependencies=[Depends(rate_limit_dependency("20/minute"))])
async def export_draft(
    execution_id: str,
    format: str = Query("docx", pattern="^(docx|pdf)$"),
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Export a completed draft as Word or PDF."""
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
    if execution.agent_type != AgentType.drafting.value:
        raise HTTPException(status_code=400, detail="Export is only available for drafting executions.")
    if execution.status != AgentStatus.completed.value:
        raise HTTPException(status_code=400, detail="Execution is not completed.")

    content = (execution.result_data or {}).get("memo", "")
    doc_type = (execution.input_data or {}).get("doc_type", "")

    try:
        template = get_template(doc_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown document type: {doc_type}")

    # Sanitize doc_type for use in Content-Disposition filename
    safe_doc_type = re.sub(r"[^a-zA-Z0-9_-]", "", doc_type)
    fmt = format  # already validated by Query pattern

    if fmt == "docx":
        file_bytes = await export_to_docx(content, template)
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        filename = f"draft_{safe_doc_type}.docx"
    else:
        file_bytes = await export_to_pdf(content, template)
        media_type = "application/pdf"
        filename = f"draft_{safe_doc_type}.pdf"

    # Audit log: document export
    await create_audit_log(
        db=db,
        action="agent.export",
        user_id=user.sub,
        resource_type="agent_execution",
        resource_id=execution_id,
        metadata={"format": fmt, "doc_type": doc_type},
    )

    from io import BytesIO
    return StreamingResponse(
        BytesIO(file_bytes),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
