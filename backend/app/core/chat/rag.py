"""RAG (Retrieval-Augmented Generation) pipeline for legal research chat.

Retrieves relevant case law via hybrid search, constructs a grounded prompt,
and streams the response from Gemini with inline citations.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy import text

from app.core.config import settings
from app.core.legal.prompts import CHAT_SYSTEM_PROMPT, CHAT_USER_WITH_CONTEXT
from app.core.legal.treatment import (
    classify_treatment_llm,
    detect_treatment_in_text,
    has_overruling_language,
)
from app.core.search.hybrid import hybrid_search
from app.security.encryption import encrypt_field, safe_decrypt
from app.security.sanitizer import sanitize_search_query

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.core.interfaces import EmbeddingProvider, LLMProvider, Reranker, VectorStore
    from app.core.interfaces.graph_store import GraphStore

logger = logging.getLogger(__name__)

MAX_HISTORY_MESSAGES = settings.chat_max_history
MAX_CONTEXT_RESULTS = settings.chat_max_context_results
MAX_SNIPPET_CHARS = settings.chat_max_snippet_chars
MAX_RATIO_CHARS = 2000
MAX_CHUNK_CHARS = 1000
MAX_PROMPT_CHARS = 100_000  # ~25K tokens, safe for Gemini 2.5 Pro

BENCH_LABELS: dict[str, str] = {
    "single": "Single Judge",
    "division": "Division Bench",
    "full": "Full Bench",
    "constitutional": "Constitution Bench",
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ChatSource:
    """A source case referenced in the RAG response."""

    case_id: str
    title: str | None = None
    citation: str | None = None
    court: str | None = None
    year: int | None = None
    score: float = 0.0
    ratio: str | None = None
    bench_type: str | None = None
    judge_names: list[str] | None = None
    chunk_text: str | None = None


@dataclass(slots=True)
class RAGEvent:
    """A single event in the RAG streaming response."""

    type: str  # "session", "chunk", "source", "done"
    data: dict


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def check_treatment_from_graph(
    case_ids: list[str],
    graph_store: GraphStore,
) -> dict[str, str]:
    """Query Neo4j for cases that have been overruled.

    Returns:
        Mapping of case_id -> overruling citation for cases found to be overruled.
        Returns empty dict on error (graph unavailability should not break RAG).
    """
    if not case_ids:
        return {}
    try:
        results = await graph_store.query(
            "MATCH (c:Case)-[r:CITES]->(cited:Case) "
            "WHERE cited.id IN $case_ids AND r.treatment = 'overruled' "
            "RETURN cited.id AS case_id, c.citation AS overruled_by",
            params={"case_ids": case_ids},
        )
        return {r["case_id"]: r["overruled_by"] for r in results}
    except Exception:
        logger.warning("Failed to check treatment from graph, falling back to heuristic", exc_info=True)
        return {}


async def rag_respond(
    question: str,
    *,
    session_id: str | None = None,
    user_id: str,
    llm: LLMProvider,
    embedder: EmbeddingProvider,
    vector_store: VectorStore,
    reranker: Reranker,
    db: AsyncSession,
    redis_client=None,
    graph_store: GraphStore | None = None,
) -> AsyncIterator[RAGEvent]:
    """Execute the RAG pipeline and yield streaming events.

    Yields RAGEvent objects:
    - type="session": {session_id, title} (only for new sessions)
    - type="chunk": {content} (streamed text tokens)
    - type="source": {case_id, title, citation, ...} (per source)
    - type="done": {tokens_used, source_count}
    """

    # 1. Create or validate session
    is_new_session = session_id is None
    if is_new_session:
        session_id = str(uuid.uuid4())
        title = _generate_title(question)
        await _create_session(db, session_id, user_id, title)
        yield RAGEvent(type="session", data={"session_id": session_id, "title": title})
    else:
        await _verify_session_ownership(db, session_id, user_id)

    try:
        # 2. Load chat history
        chat_history = await _load_chat_history(db, session_id)

        # 2.5 Reformulate follow-up queries with conversation context
        search_query = question
        if chat_history:
            search_query = await _reformulate_query(question, chat_history, llm)

        # 3. Retrieve relevant cases via hybrid search
        search_response = await hybrid_search(
            query=search_query,
            page=1,
            page_size=MAX_CONTEXT_RESULTS,
            llm=llm,
            embedder=embedder,
            vector_store=vector_store,
            reranker=reranker,
            db=db,
            redis_client=redis_client,
        )

        # 4. Fetch text snippets for context
        sources = await _build_sources(search_response.results, db)

        # 5. Build prompt
        context_text = _format_context(sources)
        history_text = _format_history(chat_history)
        user_prompt = CHAT_USER_WITH_CONTEXT.format(
            retrieved_context=context_text,
            chat_history=history_text,
            question=question,
        )

        # 5.5 Context size guard -- truncate if prompt exceeds safe limit.
        # IMPORTANT: `sources` is reassigned here so that downstream steps
        # (source event yielding in step 7, DB persistence in step 8) only
        # reference the sources that were actually sent to the LLM.
        original_source_count = len(sources)
        if len(user_prompt) > MAX_PROMPT_CHARS:
            original_len = len(user_prompt)
            sources = sources[:3]
            context_text = _format_context(sources)
            history_text = _format_history(chat_history[-4:])
            user_prompt = CHAT_USER_WITH_CONTEXT.format(
                retrieved_context=context_text,
                chat_history=history_text,
                question=question,
            )
            logger.warning(
                "Prompt truncated from %d to %d chars; sources reduced from %d to %d",
                original_len,
                len(user_prompt),
                original_source_count,
                len(sources),
            )
        truncated_source_count = len(sources)

        # 5.6 Notify client if sources were dropped due to context limits
        if truncated_source_count < original_source_count:
            yield RAGEvent(
                type="context_notice",
                data={
                    "sources_used": truncated_source_count,
                    "sources_available": original_source_count,
                    "message": (
                        f"Showing {truncated_source_count} of "
                        f"{original_source_count} relevant sources "
                        f"due to context limits."
                    ),
                },
            )

        # 6. Stream response from LLM
        full_response: list[str] = []
        async for chunk in llm.stream(
            prompt=user_prompt,
            system=CHAT_SYSTEM_PROMPT,
            temperature=0.2,
        ):
            full_response.append(chunk)
            yield RAGEvent(type="chunk", data={"content": chunk})

        response_text = "".join(full_response)

        # 7. Yield source events (with treatment warnings where applicable)
        # NOTE: Only sources actually included in the LLM context are yielded
        # (the `sources` list may have been truncated in step 5.5).
        graph_overruled: dict[str, str] = {}
        if graph_store and sources:
            graph_overruled = await check_treatment_from_graph(
                [s.case_id for s in sources], graph_store
            )
        for i, source in enumerate(sources):
            source_data: dict = {
                "index": i + 1,
                "case_id": source.case_id,
                "title": source.title,
                "citation": source.citation,
                "court": source.court,
                "year": source.year,
                "score": round(source.score, 4),
            }
            # Check treatment status: three-stage pipeline:
            # 1. Graph (authoritative) — Neo4j CITES edges with treatment metadata
            # 2. Regex heuristic — pattern matching on ratio/chunk text
            # 3. LLM fallback — Gemini Flash for ambiguous cases (config-gated)
            # WIRED_BY_REFACTOR: Stage 3 uses classify_treatment_llm() which was
            # previously defined but never called. Activated when regex confidence
            # is below threshold and enable_treatment_llm_fallback is True.
            if source.case_id in graph_overruled:
                source_data["treatment_warning"] = (
                    f"This case has been overruled by {graph_overruled[source.case_id]}. "
                    "Verify its current status before relying on it."
                )
            else:
                check_text = (source.ratio or "") + " " + (source.chunk_text or "")
                if check_text.strip() and has_overruling_language(check_text):
                    source_data["treatment_warning"] = (
                        "This case may have been overruled or distinguished. "
                        "Verify its current status before relying on it."
                    )
                elif (
                    check_text.strip()
                    and settings.enable_treatment_llm_fallback
                ):
                    # Stage 3: LLM fallback — try regex first, if low confidence,
                    # escalate to LLM for more accurate classification.
                    regex_results = detect_treatment_in_text(check_text)
                    low_confidence = any(
                        r.confidence < settings.treatment_llm_confidence_threshold
                        for r in regex_results
                    )
                    if regex_results and low_confidence:
                        llm_result = await classify_treatment_llm(check_text, llm)
                        if llm_result and llm_result.treatment.value in (
                            "overruled", "distinguished", "not_followed", "doubted",
                        ):
                            source_data["treatment_warning"] = (
                                f"AI analysis suggests this case may have been "
                                f"{llm_result.treatment.value} "
                                f"(confidence: {llm_result.confidence:.0%}). "
                                "Verify its current status before relying on it."
                            )
            yield RAGEvent(type="source", data=source_data)

        # 8. Save messages to DB
        await _save_user_message(db, session_id, question)
        source_json = [
            {
                "case_id": s.case_id,
                "title": s.title,
                "citation": s.citation,
                "court": s.court,
                "year": s.year,
                "score": round(s.score, 4),
            }
            for s in sources
        ]
        await _save_assistant_message(db, session_id, response_text, source_json)

        # 8.5 Yield disclaimer event for UI to display
        yield RAGEvent(
            type="disclaimer",
            data={
                "message": (
                    "This is AI-generated legal analysis by Smriti AI. "
                    "It does not constitute legal advice. Verify all citations "
                    "and holdings independently before reliance."
                ),
            },
        )

        yield RAGEvent(
            type="done",
            data={"source_count": len(sources)},
        )

    except Exception:
        logger.exception("RAG pipeline error for session %s", session_id)
        yield RAGEvent(
            type="error",
            data={"message": "An error occurred while processing your request. Please try again."},
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _reformulate_query(
    question: str,
    chat_history: list[dict],
    llm: LLMProvider,
) -> str:
    """Reformulate a follow-up question using conversation context."""
    # Take last few messages for context
    recent = chat_history[-4:]
    history_summary = "\n".join(
        f"{m['role'].title()}: {m['content'][:200]}" for m in recent
    )

    prompt = (
        "You are reformulating a legal research query. Given this conversation context:\n"
        f"{history_summary}\n\n"
        f"The user now asks: \"{question}\"\n\n"
        "Rewrite the user's question as a self-contained legal search query that:\n"
        "1. Preserves ALL legal terminology (section numbers, act names, case names, legal concepts)\n"
        "2. Resolves pronouns and references to specific legal entities from the conversation\n"
        "3. Maintains the Indian legal context (IPC/BNS, CrPC/BNSS, specific courts mentioned)\n"
        "4. Is suitable for searching a database of Indian court judgments\n"
        "Return ONLY the reformulated query, nothing else."
    )

    try:
        reformulated = await llm.generate(
            prompt=prompt,
            system="You are a query reformulation assistant. Output only the reformulated search query.",
            temperature=0.0,
            max_tokens=200,
        )
        reformulated = reformulated.strip().strip('"').strip("'")
        if reformulated:
            return reformulated
    except (ConnectionError, TimeoutError, ValueError):
        logger.warning("Query reformulation failed, using original query")

    return question


def _generate_title(question: str) -> str:
    """Generate a short session title from the first question."""
    title = question.strip()[:80]
    if len(question) > 80:
        title += "..."
    return title


async def _create_session(
    db: AsyncSession, session_id: str, user_id: str, title: str
) -> None:
    """Insert a new chat session row."""
    await db.execute(
        text(
            "INSERT INTO chat_sessions (id, user_id, title) "
            "VALUES (:id, :user_id, :title)"
        ),
        {"id": session_id, "user_id": user_id, "title": title},
    )
    await db.commit()


async def _verify_session_ownership(
    db: AsyncSession, session_id: str, user_id: str
) -> None:
    """Verify that the session belongs to the user."""
    from fastapi import HTTPException

    result = await db.execute(
        text("SELECT user_id FROM chat_sessions WHERE id = :id"),
        {"id": session_id},
    )
    row = result.mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Chat session not found")
    if str(row["user_id"]) != user_id:
        raise HTTPException(status_code=403, detail="Access denied to this chat session")


async def _load_chat_history(
    db: AsyncSession, session_id: str
) -> list[dict]:
    """Load recent chat messages for context."""
    result = await db.execute(
        text(
            "SELECT role, content FROM chat_messages "
            "WHERE session_id = :session_id "
            "ORDER BY created_at DESC "
            "LIMIT :limit"
        ),
        {"session_id": session_id, "limit": MAX_HISTORY_MESSAGES},
    )
    rows = result.mappings().all()
    return [{"role": r["role"], "content": safe_decrypt(r["content"])} for r in reversed(rows)]


async def _build_sources(
    search_results: list,
    db: AsyncSession,
) -> list[ChatSource]:
    """Build ChatSource objects from search results, fetching snippets."""
    if not search_results:
        return []

    case_ids = [r.case_id for r in search_results]
    placeholders = ", ".join(f":id_{i}" for i in range(len(case_ids)))
    params = {f"id_{i}": cid for i, cid in enumerate(case_ids)}

    result = await db.execute(
        text(
            f"SELECT id, title, citation, court, year, "
            f"LEFT(ratio_decidendi, {MAX_SNIPPET_CHARS}) AS ratio, "
            f"LEFT(description, {MAX_SNIPPET_CHARS}) AS description, "
            f"bench_type, judge "
            f"FROM cases WHERE id IN ({placeholders})"
        ),
        params,
    )
    rows = {str(r["id"]): r for r in result.mappings().all()}

    sources: list[ChatSource] = []
    for sr in search_results:
        row = rows.get(sr.case_id)
        if row is None:
            continue

        # Parse judge names: could be a list or a string
        raw_judge = row.get("judge")
        if isinstance(raw_judge, list):
            judge_names = raw_judge
        elif isinstance(raw_judge, str) and raw_judge:
            judge_names = [raw_judge]
        else:
            judge_names = None

        # Chunk text: prefer vector chunk (semantic match), then FTS snippet, then description
        chunk_text = (
            getattr(sr, "chunk_text", None)
            or getattr(sr, "snippet", None)
            or row.get("description")
        )

        sources.append(
            ChatSource(
                case_id=sr.case_id,
                title=row.get("title") or sr.title,
                citation=row.get("citation") or sr.citation,
                court=row.get("court") or sr.court,
                year=row.get("year") or sr.year,
                score=sr.score,
                ratio=row.get("ratio"),
                bench_type=row.get("bench_type"),
                judge_names=judge_names,
                chunk_text=chunk_text,
            )
        )

    return sources


def _format_context(sources: list[ChatSource]) -> str:
    """Format retrieved sources into a context block for the prompt."""
    if not sources:
        return "No relevant cases were found in the database."

    parts: list[str] = []
    for i, s in enumerate(sources, 1):
        citation_str = s.citation or "No citation"
        court_str = s.court or "Unknown court"
        year_str = str(s.year) if s.year else "Unknown year"

        # Build court string with bench type
        bench_label = BENCH_LABELS.get(s.bench_type or "", "")
        if bench_label:
            court_str = f"{court_str} ({bench_label})"

        lines = [
            f"[{i}] {s.title or 'Untitled'}",
            f"    Citation: {citation_str}",
            f"    Court: {court_str}, Year: {year_str}",
        ]

        # Add bench (judge names)
        if s.judge_names:
            lines.append(f"    Bench: {', '.join(s.judge_names)}")

        # Add ratio decidendi
        if s.ratio:
            ratio_text = s.ratio[:MAX_RATIO_CHARS]
            if len(s.ratio) > MAX_RATIO_CHARS:
                ratio_text += "..."
            lines.append(f"\n    Ratio Decidendi:\n    {ratio_text}")

        # Add relevant passage (chunk text)
        if s.chunk_text:
            chunk = s.chunk_text[:MAX_CHUNK_CHARS]
            if len(s.chunk_text) > MAX_CHUNK_CHARS:
                chunk += "..."
            lines.append(f"\n    Relevant Passage:\n    \"{chunk}\"")

        # Check for overruling language and add treatment warning
        check_text = (s.ratio or "") + " " + (s.chunk_text or "")
        if check_text.strip() and has_overruling_language(check_text):
            lines.append(
                "\n    WARNING: This case contains language suggesting it may have "
                "been overruled or distinguished. Verify current status."
            )

        parts.append("\n".join(lines))

    return "\n\n".join(parts)


def _format_history(messages: list[dict]) -> str:
    """Format chat history for the prompt, sanitizing user messages."""
    if not messages:
        return ""

    parts = []
    for msg in messages:
        role = "User" if msg["role"] == "user" else "Assistant"
        content = msg["content"]
        # Sanitize user messages to prevent prompt injection via history
        if msg["role"] == "user":
            content = sanitize_search_query(content)
        parts.append(f"{role}: {content}")

    return "Previous conversation:\n" + "\n\n".join(parts) + "\n\n"


async def _save_user_message(
    db: AsyncSession, session_id: str, content: str
) -> None:
    """Save the user's message to the database (encrypted)."""
    msg_id = str(uuid.uuid4())
    await db.execute(
        text(
            "INSERT INTO chat_messages (id, session_id, role, content) "
            "VALUES (:id, :session_id, 'user', :content)"
        ),
        {"id": msg_id, "session_id": session_id, "content": encrypt_field(content)},
    )


async def _save_assistant_message(
    db: AsyncSession,
    session_id: str,
    content: str,
    sources: list[dict],
) -> None:
    """Save the assistant's response and sources to the database (encrypted).

    Also updates the session timestamp. All writes are batched into a
    single commit to avoid partial persistence.
    """
    msg_id = str(uuid.uuid4())
    await db.execute(
        text(
            "INSERT INTO chat_messages (id, session_id, role, content, sources) "
            "VALUES (:id, :session_id, 'assistant', :content, :sources)"
        ),
        {
            "id": msg_id,
            "session_id": session_id,
            "content": encrypt_field(content),
            "sources": json.dumps(sources),
        },
    )

    # Update session timestamp
    await db.execute(
        text("UPDATE chat_sessions SET updated_at = NOW() WHERE id = :id"),
        {"id": session_id},
    )
    await db.commit()
