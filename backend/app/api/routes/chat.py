"""Chat API endpoints — RAG-powered legal research assistant with streaming."""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from app.security.rate_limiter import rate_limit_dependency
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.chat.rag import rag_respond
from app.core.dependencies import get_embedder, get_graph_store, get_llm, get_reranker, get_vector_store
from app.db.postgres import async_session_factory, get_db
from app.db.redis_client import get_redis
from app.security.auth import TokenPayload
from app.security.audit import create_audit_log
from app.security.encryption import safe_decrypt
from app.security.rbac import get_current_user
from app.security.sanitizer import sanitize_search_query, detect_prompt_injection

logger = logging.getLogger(__name__)

router = APIRouter()


def _validate_uuid(value: str, name: str = "ID") -> None:
    """Validate that a string is a valid UUID format."""
    import uuid
    try:
        uuid.UUID(value)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid {name} format")


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=5000)


# ---------------------------------------------------------------------------
# POST /chat — New session + first message (SSE stream)
# ---------------------------------------------------------------------------


@router.post("", dependencies=[Depends(rate_limit_dependency("20/minute"))])
async def create_chat(
    body: ChatRequest,
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Start a new chat session and stream the first response."""
    if detect_prompt_injection(body.message):
        raise HTTPException(status_code=400, detail="Input contains potentially harmful content")
    body.message = sanitize_search_query(body.message)

    llm = get_llm()
    embedder = get_embedder()
    vector_store = get_vector_store()
    reranker = get_reranker()
    redis_client = await get_redis()
    graph_store = get_graph_store()

    logger.info("Creating new chat session for user %s", user.sub)

    async def event_stream():
        # Use an independent DB session for the SSE generator lifetime.
        # The request-scoped session (from Depends(get_db)) may be closed
        # before this generator finishes yielding events.
        async with async_session_factory() as stream_db:
            try:
                async with asyncio.timeout(300):  # 5-minute max SSE duration
                    async for event in rag_respond(
                        question=body.message,
                        session_id=None,
                        user_id=user.sub,
                        llm=llm,
                        embedder=embedder,
                        vector_store=vector_store,
                        reranker=reranker,
                        db=stream_db,
                        redis_client=redis_client,
                        graph_store=graph_store,
                    ):
                        yield f"data: {json.dumps(event.data | {'type': event.type})}\n\n"
            except TimeoutError:
                logger.warning("Chat SSE stream timed out after 5 minutes")
                yield f"data: {json.dumps({'type': 'error', 'message': 'Stream timed out after 5 minutes'})}\n\n"
            except Exception:
                logger.exception("SSE stream error in create_chat for user %s", user.sub)
                yield f"data: {json.dumps({'type': 'error', 'message': 'An internal error occurred'})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# POST /chat/{session_id}/message — Continue conversation (SSE stream)
# ---------------------------------------------------------------------------


@router.post("/{session_id}/message", dependencies=[Depends(rate_limit_dependency("20/minute"))])
async def send_message(
    session_id: str,
    body: ChatRequest,
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Send a message in an existing chat session and stream the response."""
    _validate_uuid(session_id, "session_id")

    # Verify session ownership (IDOR protection)
    session_check = await db.execute(
        text("SELECT user_id FROM chat_sessions WHERE id = :id"),
        {"id": session_id},
    )
    session_row = session_check.mappings().one_or_none()
    if session_row is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if str(session_row["user_id"]) != user.sub:
        raise HTTPException(status_code=403, detail="Access denied")

    if detect_prompt_injection(body.message):
        raise HTTPException(status_code=400, detail="Input contains potentially harmful content")
    body.message = sanitize_search_query(body.message)

    llm = get_llm()
    embedder = get_embedder()
    vector_store = get_vector_store()
    reranker = get_reranker()
    redis_client = await get_redis()
    graph_store = get_graph_store()

    logger.info("Continuing chat session %s for user %s", session_id, user.sub)

    async def event_stream():
        # Use an independent DB session for the SSE generator lifetime.
        # The request-scoped session (from Depends(get_db)) may be closed
        # before this generator finishes yielding events.
        async with async_session_factory() as stream_db:
            try:
                async with asyncio.timeout(300):  # 5-minute max SSE duration
                    async for event in rag_respond(
                        question=body.message,
                        session_id=session_id,
                        user_id=user.sub,
                        llm=llm,
                        embedder=embedder,
                        vector_store=vector_store,
                        reranker=reranker,
                        db=stream_db,
                        redis_client=redis_client,
                        graph_store=graph_store,
                    ):
                        yield f"data: {json.dumps(event.data | {'type': event.type})}\n\n"
            except TimeoutError:
                logger.warning("Chat SSE stream timed out after 5 minutes")
                yield f"data: {json.dumps({'type': 'error', 'message': 'Stream timed out after 5 minutes'})}\n\n"
            except Exception:
                logger.exception("SSE stream error in send_message for session %s, user %s", session_id, user.sub)
                yield f"data: {json.dumps({'type': 'error', 'message': 'An internal error occurred'})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# GET /chat/sessions — List user's sessions
# ---------------------------------------------------------------------------


@router.get("/sessions", dependencies=[Depends(rate_limit_dependency("60/minute"))])
async def list_sessions(
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict:
    """List all chat sessions for the current user (paginated)."""
    # Total count
    count_result = await db.execute(
        text("SELECT COUNT(*) FROM chat_sessions WHERE user_id = :user_id"),
        {"user_id": user.sub},
    )
    total = count_result.scalar_one()

    # Paginated results
    offset = (page - 1) * page_size
    result = await db.execute(
        text(
            "SELECT s.id, s.title, s.created_at, s.updated_at, "
            "COUNT(m.id) AS message_count "
            "FROM chat_sessions s "
            "LEFT JOIN chat_messages m ON m.session_id = s.id "
            "WHERE s.user_id = :user_id "
            "GROUP BY s.id "
            "ORDER BY s.updated_at DESC "
            "LIMIT :limit OFFSET :offset"
        ),
        {"user_id": user.sub, "limit": page_size, "offset": offset},
    )
    rows = result.mappings().all()

    sessions = [
        {
            "id": str(r["id"]),
            "title": r["title"],
            "created_at": str(r["created_at"]),
            "updated_at": str(r["updated_at"]),
            "message_count": r["message_count"],
        }
        for r in rows
    ]

    return {"sessions": sessions, "total": total, "page": page, "page_size": page_size}


# ---------------------------------------------------------------------------
# GET /chat/{session_id}/history — Full message history
# ---------------------------------------------------------------------------


@router.get("/{session_id}/history", dependencies=[Depends(rate_limit_dependency("60/minute"))])
async def get_history(
    session_id: str,
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get the full message history for a chat session."""
    _validate_uuid(session_id, "session_id")

    # Verify session ownership
    session_result = await db.execute(
        text("SELECT user_id, title FROM chat_sessions WHERE id = :id"),
        {"id": session_id},
    )
    session = session_result.mappings().one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Chat session not found")
    if str(session["user_id"]) != user.sub:
        raise HTTPException(status_code=403, detail="Access denied to this chat session")

    result = await db.execute(
        text(
            "SELECT id, role, content, sources, created_at "
            "FROM chat_messages "
            "WHERE session_id = :session_id "
            "ORDER BY created_at ASC"
        ),
        {"session_id": session_id},
    )
    rows = result.mappings().all()

    messages = [
        {
            "id": str(r["id"]),
            "role": r["role"],
            "content": safe_decrypt(r["content"]),
            "sources": r["sources"] if r["sources"] else [],
            "created_at": str(r["created_at"]),
        }
        for r in rows
    ]
    return {"messages": messages, "total": len(messages)}


# ---------------------------------------------------------------------------
# DELETE /chat/{session_id} — Delete session + all messages
# ---------------------------------------------------------------------------


@router.delete("/{session_id}", dependencies=[Depends(rate_limit_dependency("30/minute"))])
async def delete_session(
    session_id: str,
    request: Request,
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Delete a chat session and all its messages."""
    _validate_uuid(session_id, "session_id")

    # Verify session ownership
    session_result = await db.execute(
        text("SELECT user_id FROM chat_sessions WHERE id = :id"),
        {"id": session_id},
    )
    session = session_result.mappings().one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Chat session not found")
    if str(session["user_id"]) != user.sub:
        raise HTTPException(status_code=403, detail="Access denied to this chat session")

    # CASCADE delete will remove messages too
    await db.execute(
        text("DELETE FROM chat_sessions WHERE id = :id"),
        {"id": session_id},
    )
    await db.commit()

    await create_audit_log(
        db=db,
        action="session.delete",
        user_id=user.sub,
        resource_type="chat_session",
        resource_id=session_id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return {"status": "deleted"}
