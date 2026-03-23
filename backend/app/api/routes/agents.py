"""Agent execution API routes with SSE streaming and HITL checkpoints."""

from __future__ import annotations

import json
import logging
import re
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from langgraph.types import Command
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.agents.case_prep import build_case_prep_graph
from app.core.agents.drafting import build_drafting_graph
from app.core.agents.research import build_research_graph
from app.core.agents.research_cache import get_cached_memo
from app.core.agents.strategy import build_strategy_graph
from app.core.dependencies import (
    get_checkpointer,
    get_embedder,
    get_flash_llm,
    get_graph_store,
    get_ik_client,
    get_llm,
    get_reranker,
    get_vector_store,
    get_web_search,
)
from app.core.drafting.export import (
    export_research_memo_docx,
    export_research_memo_pdf,
    export_to_docx,
    export_to_pdf,
)
from app.core.drafting.templates import TEMPLATES, get_template
from app.db.postgres import async_session_factory, get_db
from app.db.redis_client import get_redis
from app.models.agent_execution import AgentExecution, AgentStatus, AgentType
from app.security.audit import create_audit_log
from app.security.auth import TokenPayload
from app.security.rate_limiter import rate_limit_dependency
from app.security.rbac import get_current_user
from app.security.sanitizer import detect_prompt_injection, sanitize_search_query

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# [D9] Error categorization for SSE error events
# ---------------------------------------------------------------------------

def _categorize_error(exc: Exception) -> dict:
    """Categorize an exception into an SSE error event payload."""
    msg = str(exc)
    lower = msg.lower()

    if ("rate" in lower and "limit" in lower) or "429" in lower or "quota" in lower:
        return {
            "type": "error",
            "category": "rate_limit",
            "message": "API rate limit reached. Please wait a moment and try again.",
            "recoverable": True,
        }
    if "timeout" in lower or "timed out" in lower:
        return {
            "type": "error",
            "category": "timeout",
            "message": "A search operation timed out. Results may be incomplete.",
            "recoverable": True,
        }
    if "auth" in lower or "401" in lower or "403" in lower or "permission" in lower:
        return {
            "type": "error",
            "category": "auth_error",
            "message": "Authentication error. Please sign in again.",
            "recoverable": False,
        }
    if "no results" in lower or "not found" in lower:
        return {
            "type": "error",
            "category": "no_results",
            "message": "No matching cases found. Try rephrasing your query.",
            "recoverable": True,
        }
    # Default: LLM or infrastructure error
    return {
        "type": "error",
        "category": "llm_error",
        "message": "Agent execution failed. Please try again.",
        "recoverable": False,
    }

# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class ResearchRequest(BaseModel):
    query: str = Field(..., min_length=5, max_length=5000)
    language: str = Field(default="en", pattern="^(en|hi)$")
    auto_approve: bool = Field(default=False, description="Skip HITL checkpoints, auto-approve all")


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
    graph,
    initial_input: dict,
    config: dict,
    exec_id: uuid.UUID,
    graph_kwargs: dict | None = None,
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
        nonlocal is_checkpoint, graph

        # Build graph lazily if kwargs provided (enables memo streaming)
        if graph_kwargs is not None:
            _memo_chunk_count = 0

            async def _memo_stream_cb(chunk: str) -> None:
                nonlocal _memo_chunk_count
                _memo_chunk_count += 1
                if _memo_chunk_count <= 3 or _memo_chunk_count % 20 == 0:
                    logger.info("memo_stream chunk #%d (%d chars)", _memo_chunk_count, len(chunk))
                await queue.put(
                    f'data: {json.dumps({"type": "memo_stream", "execution_id": str(exec_id), "chunk": chunk})}\n\n'
                )
            graph = build_research_graph(**graph_kwargs, memo_stream_callback=_memo_stream_cb)

        try:
            async for event in graph.astream(
                initial_input, config=config, stream_mode="updates"
            ):
                for node_name, node_output in event.items():
                    # [T1] Forward process_events as rich SSE events
                    if isinstance(node_output, dict):
                        for pe in node_output.get("process_events", []):
                            await queue.put(
                                f"data: {json.dumps({**pe, 'execution_id': str(exec_id)})}\n\n"
                            )

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
                logger.info(
                    "Agent %s completed. State keys: %s, footnotes count: %d",
                    exec_id,
                    list(final_state.keys()),
                    len(final_state.get("footnotes") or []),
                )
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
                # [T1] Enrich with Phase 4 structured data
                if final_state.get("footnotes"):
                    result_data["footnotes"] = final_state["footnotes"]
                if final_state.get("source_attribution"):
                    result_data["source_attribution"] = final_state["source_attribution"]
                if final_state.get("research_audit"):
                    result_data["research_audit"] = final_state["research_audit"]
                if final_state.get("legal_quality_result"):
                    result_data["legal_quality_result"] = final_state["legal_quality_result"]
                if final_state.get("contradictions"):
                    result_data["contradictions"] = final_state["contradictions"]
                if final_state.get("confidence_breakdown"):
                    result_data["confidence_breakdown"] = final_state["confidence_breakdown"]
                async with async_session_factory() as db:
                    await db.execute(
                        text(
                            "UPDATE agent_executions SET status = 'completed', "
                            "result_data = :data, completed_at = now() WHERE id = :id"
                        ),
                        {"id": exec_id, "data": json.dumps(result_data)},
                    )
                    await db.commit()

                memo_event_data: dict = {"confidence": result_data["confidence"]}
                if result_data.get("footnotes"):
                    memo_event_data["footnotes"] = result_data["footnotes"]
                if result_data.get("research_audit"):
                    memo_event_data["research_audit"] = result_data["research_audit"]
                if result_data.get("source_attribution"):
                    memo_event_data["source_attribution"] = result_data["source_attribution"]
                if result_data.get("legal_quality_result"):
                    memo_event_data["legal_quality_result"] = result_data["legal_quality_result"]
                if result_data.get("contradictions"):
                    memo_event_data["contradictions"] = result_data["contradictions"]
                await queue.put(f"data: {json.dumps({'type': 'memo', 'execution_id': str(exec_id), 'content': result_data['memo'], 'data': memo_event_data})}\n\n")
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
                        {"id": exec_id, "msg": re.sub(
                            r'(postgresql|redis|neo4j|https?)://[^\s]+',
                            '[REDACTED_URL]',
                            str(exc)[:2000],
                        )},
                    )
                    await db.commit()
            except Exception:
                logger.exception("Failed to update execution %s status to failed", exec_id)
            await queue.put(f"data: {json.dumps(_categorize_error(exc))}\n\n")
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

    # Build graph and initial state
    llm = get_llm()
    embedder = get_embedder()
    vector_store = get_vector_store()
    reranker = get_reranker()

    config = {"configurable": {"thread_id": thread_id}}
    graph_kwargs: dict | None = None  # Only set for research agent (memo streaming)

    if agent_type == "research":
        # Inject IK/Tavily providers — gracefully handle missing API keys
        try:
            _ik_client = get_ik_client()
        except (ValueError, Exception):
            _ik_client = None
        try:
            _web_search = get_web_search()
        except (ValueError, Exception):
            _web_search = None

        # [S8-L1 + S11] Check memo cache before running graph
        try:
            _redis = await get_redis()
        except Exception:
            _redis = None

        # [S11] Semantic cache check (before hash cache)
        try:
            from app.core.search.semantic_cache import SemanticCache
            _sem_cache = SemanticCache(_redis, embedder) if _redis else None
            if _sem_cache:
                cached_semantic = await _sem_cache.get(request_body.query)
                if cached_semantic:
                    cached_semantic["cache_type"] = "semantic"
                    async def _cached_stream_semantic():
                        exec_str = str(execution.id)
                        yield f"data: {json.dumps({'type': 'status', 'execution_id': exec_str, 'step': 'cache_hit', 'message': 'Found cached result (semantic)'})}\n\n"
                        memo_data: dict = {"confidence": cached_semantic.get("confidence", 0)}
                        if cached_semantic.get("footnotes"):
                            memo_data["footnotes"] = cached_semantic["footnotes"]
                        if cached_semantic.get("research_audit"):
                            memo_data["research_audit"] = cached_semantic["research_audit"]
                        yield f"data: {json.dumps({'type': 'memo', 'execution_id': exec_str, 'content': cached_semantic.get('memo', ''), 'data': memo_data})}\n\n"
                        yield f"data: {json.dumps({'type': 'done', 'execution_id': exec_str, 'status': 'completed'})}\n\n"
                    return StreamingResponse(
                        _cached_stream_semantic(),
                        media_type="text/event-stream",
                        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
                    )
        except Exception:
            pass  # Best-effort — fall through

        # [S8-L1] Hash cache check
        cached_memo = await get_cached_memo(_redis, request_body.query)
        if cached_memo:
            async def _cached_stream():
                exec_str = str(execution.id)
                yield f"data: {json.dumps({'type': 'status', 'execution_id': exec_str, 'step': 'cache_hit', 'message': 'Found cached result'})}\n\n"
                memo_data_h: dict = {"confidence": cached_memo.get("confidence", 0)}
                if cached_memo.get("footnotes"):
                    memo_data_h["footnotes"] = cached_memo["footnotes"]
                if cached_memo.get("research_audit"):
                    memo_data_h["research_audit"] = cached_memo["research_audit"]
                yield f"data: {json.dumps({'type': 'memo', 'execution_id': exec_str, 'content': cached_memo.get('memo', ''), 'data': memo_data_h})}\n\n"
                yield f"data: {json.dumps({'type': 'done', 'execution_id': exec_str, 'status': 'completed'})}\n\n"
            return StreamingResponse(
                _cached_stream(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
            )

        graph_kwargs = dict(
            llm=llm,
            flash_llm=get_flash_llm(),
            embedder=embedder,
            vector_store=vector_store,
            reranker=reranker,
            graph_store=get_graph_store(),
            web_search=_web_search,
            ik_client=_ik_client,
            checkpointer=checkpointer,
        )
        graph = None  # Built lazily inside _run_graph for memo streaming
        initial_input = {"query": request_body.query, "language": request_language}
        # [D10] Pass auto_approve if set
        if hasattr(request_body, "auto_approve") and request_body.auto_approve:
            initial_input["auto_approve"] = True
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
        _stream_agent_events(graph, initial_input, config, execution.id, graph_kwargs=graph_kwargs),
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


@router.get("/executions", dependencies=[Depends(rate_limit_dependency("60/minute"))])
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


@router.get("/executions/{execution_id}", dependencies=[Depends(rate_limit_dependency("60/minute"))])
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

    checkpointer = get_checkpointer()

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
    resume_graph_kwargs: dict | None = None  # Only set for research agent (memo streaming)

    if execution.agent_type == AgentType.research.value:
        try:
            _ik_client = get_ik_client()
        except (ValueError, Exception):
            _ik_client = None
        try:
            _web_search = get_web_search()
        except (ValueError, Exception):
            _web_search = None

        resume_graph_kwargs = dict(
            llm=llm,
            flash_llm=get_flash_llm(),
            embedder=embedder,
            vector_store=vector_store,
            reranker=reranker,
            graph_store=get_graph_store(),
            web_search=_web_search,
            ik_client=_ik_client,
            checkpointer=checkpointer,
        )
        # Build graph eagerly for checkpoint state check; rebuilt with memo
        # streaming callback inside _run_graph.
        graph = build_research_graph(**resume_graph_kwargs)
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

    # [DEBUG] Log resume details to diagnose checkpoint loop bug
    logger.warning(
        "RESUME_DEBUG: exec_id=%s thread_id=%s agent_type=%s body_input=%r resume_input=%r",
        exec_uuid, execution.thread_id, execution.agent_type,
        body.input[:200], resume_input,
    )

    # Verify checkpoint state exists before resuming
    try:
        pre_state = await graph.aget_state(config)
        if not pre_state.values:
            # Checkpoint state was lost (e.g. server restart with InMemorySaver)
            async with async_session_factory() as err_db:
                await err_db.execute(
                    text("UPDATE agent_executions SET status = 'failed', error_message = 'Checkpoint state lost (server was restarted). Please start a new research query.' WHERE id = :id"),
                    {"id": exec_uuid},
                )
                await err_db.commit()
            raise HTTPException(
                status_code=410,
                detail="Checkpoint state was lost due to server restart. Please start a new research query.",
            )
        logger.warning(
            "RESUME_DEBUG: pre_resume_state next=%s values_keys=%s msg_count=%d plan_len=%d",
            pre_state.next,
            list(pre_state.values.keys())[:10] if pre_state.values else [],
            len(pre_state.values.get("messages", [])) if pre_state.values else 0,
            len(pre_state.values.get("research_plan", [])) if pre_state.values else 0,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("RESUME_DEBUG: failed to get pre-state: %s", e)

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
        _stream_agent_events(graph, resume_input, config, exec_uuid, graph_kwargs=resume_graph_kwargs),
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


@router.delete("/executions/{execution_id}", dependencies=[Depends(rate_limit_dependency("30/minute"))])
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


@router.get("/drafting/templates", dependencies=[Depends(rate_limit_dependency("60/minute"))])
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


# ---------------------------------------------------------------------------
# POST /research/revise-section/{execution_id} -- Revise a single memo section
# ---------------------------------------------------------------------------


class ReviseSectionRequest(BaseModel):
    """Request body for section-level revision."""
    section_heading: str = Field(..., min_length=1, max_length=200)
    feedback: str = Field(..., min_length=1, max_length=2000)


@router.post("/research/revise-section/{execution_id}", dependencies=[Depends(rate_limit_dependency("10/minute"))])
async def revise_research_section(
    execution_id: str,
    body: ReviseSectionRequest,
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Revise a single section of a completed research memo.

    Streams SSE events: ``section_start``, ``section_delta``, ``section_done``.
    """
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
    if execution.agent_type != AgentType.research.value:
        raise HTTPException(status_code=400, detail="Revision is only available for research executions.")
    if execution.status != AgentStatus.completed.value:
        raise HTTPException(status_code=400, detail="Execution is not completed.")

    result_data = execution.result_data or {}
    memo_content = result_data.get("memo", "")
    if not memo_content:
        raise HTTPException(status_code=400, detail="No memo content available.")

    # Extract the target section
    section_heading = body.section_heading
    feedback = body.feedback

    # Parse memo into sections, find the target
    lines = memo_content.split("\n")
    section_start_idx: int | None = None
    section_end_idx: int | None = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("##") and not stripped.startswith("###"):
            heading_text = stripped.lstrip("#").strip()
            if heading_text.lower() == section_heading.lower():
                section_start_idx = i
            elif section_start_idx is not None and section_end_idx is None:
                section_end_idx = i
    if section_start_idx is None:
        raise HTTPException(status_code=404, detail=f"Section '{section_heading}' not found in memo.")
    if section_end_idx is None:
        section_end_idx = len(lines)

    original_section = "\n".join(lines[section_start_idx:section_end_idx]).strip()

    # Build revision prompt
    revision_prompt = (
        f"You are revising ONE section of a legal research memo.\n\n"
        f"## Original Section\n{original_section}\n\n"
        f"## User Feedback\n{feedback}\n\n"
        f"## Instructions\n"
        f"Rewrite ONLY this section incorporating the user's feedback. "
        f"Keep the same heading (## {section_heading}). "
        f"Maintain existing footnote references [^N]. "
        f"Do not change other sections. Return ONLY the revised section."
    )

    llm = get_llm()

    async def _stream_revision() -> AsyncIterator[str]:
        yield f"data: {json.dumps({'type': 'section_start', 'heading': section_heading})}\n\n"

        try:
            revised_text = await llm.generate(revision_prompt)

            # Update memo content in-place
            new_lines = lines[:section_start_idx] + revised_text.split("\n") + lines[section_end_idx:]
            new_memo = "\n".join(new_lines)

            # Persist updated memo
            async with async_session_factory() as session:
                upd_stmt = select(AgentExecution).where(AgentExecution.id == exec_uuid)
                upd_result = await session.execute(upd_stmt)
                upd_exec = upd_result.scalar_one_or_none()
                if upd_exec and upd_exec.result_data:
                    upd_exec.result_data = {**upd_exec.result_data, "memo": new_memo}
                    await session.commit()

            yield f"data: {json.dumps({'type': 'section_delta', 'heading': section_heading, 'content': revised_text})}\n\n"
            yield f"data: {json.dumps({'type': 'section_done', 'heading': section_heading})}\n\n"
        except Exception as exc:
            logger.exception("Section revision failed for %s", execution_id)
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

    return StreamingResponse(
        _stream_revision(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

# ---------------------------------------------------------------------------
# GET /research/export/{execution_id} -- Export research memo as DOCX, PDF, or MD
# ---------------------------------------------------------------------------


@router.get("/research/export/{execution_id}", dependencies=[Depends(rate_limit_dependency("20/minute"))])
async def export_research_memo(
    execution_id: str,
    format: str = Query("docx", pattern="^(docx|pdf|md)$"),
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Export a completed research memo as Word, PDF, or Markdown."""
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
    if execution.agent_type != AgentType.research.value:
        raise HTTPException(status_code=400, detail="Export is only available for research executions.")
    if execution.status != AgentStatus.completed.value:
        raise HTTPException(status_code=400, detail="Execution is not completed.")

    result_data = execution.result_data or {}
    memo_content = result_data.get("memo", "")
    footnotes = result_data.get("footnotes", [])
    memo_title = result_data.get("title", "Research Memo")

    if not memo_content:
        raise HTTPException(status_code=400, detail="No memo content available for export.")

    fmt = format
    from io import BytesIO

    if fmt == "md":
        file_bytes = memo_content.encode("utf-8")
        media_type = "text/markdown; charset=utf-8"
        filename = "research_memo.md"
    elif fmt == "docx":
        file_bytes = await export_research_memo_docx(
            memo_content, title=memo_title, footnotes=footnotes,
        )
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        filename = "research_memo.docx"
    else:
        file_bytes = await export_research_memo_pdf(
            memo_content, title=memo_title, footnotes=footnotes,
        )
        media_type = "application/pdf"
        filename = "research_memo.pdf"

    await create_audit_log(
        db=db,
        action="agent.export",
        user_id=user.sub,
        resource_type="agent_execution",
        resource_id=execution_id,
        metadata={"format": fmt, "agent_type": "research"},
    )

    return StreamingResponse(
        BytesIO(file_bytes),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
