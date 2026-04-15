"""Follow-up conversation nodes for the lightweight follow-up LangGraph sub-graph.

Three nodes:
1. reformulate_with_context_node — rewrite follow-up using prior memo context
2. targeted_search_node — hybrid search with narrower scope
3. synthesize_follow_up_node — generate response grounded in prior memo + new results
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.config import settings
from app.core.legal.prompts import (
    FOLLOW_UP_REFORMULATE_PROMPT,
    FOLLOW_UP_SYSTEM_PROMPT,
    FOLLOW_UP_USER_PROMPT,
)
from app.core.search.hybrid import hybrid_search

logger = logging.getLogger(__name__)


async def reformulate_with_context_node(
    state: dict,
    flash_llm: Any,
) -> dict:
    """Reformulate the follow-up query using prior memo context.

    Uses Flash LLM for speed — this is a simple query rewriting task.
    """
    follow_up = state["follow_up_query"]
    prior_memo = state.get("prior_memo", "")
    conversation_history = state.get("conversation_history", [])

    # Truncate prior memo to first 3000 chars for reformulation (just need gist)
    memo_summary = prior_memo[:3000]
    if len(prior_memo) > 3000:
        memo_summary += "\n... [truncated]"

    history_text = _format_conversation_history(conversation_history, max_messages=5)

    prompt = FOLLOW_UP_REFORMULATE_PROMPT.format(
        prior_memo_summary=memo_summary,
        conversation_history=history_text,
        follow_up_query=follow_up,
    )

    reformulated = await flash_llm.generate(
        prompt=prompt,
        temperature=0.0,
        max_tokens=200,
    )

    reformulated = reformulated.strip().strip('"').strip("'")
    logger.info("Follow-up reformulated: %r -> %r", follow_up, reformulated)

    return {
        "reformulated_query": reformulated,
        "process_events": [
            {
                "type": "progress",
                "stage": "Reformulating",
                "progress": 0.2,
                "detail": f"Reformulated query: {reformulated[:100]}",
            }
        ],
    }


async def targeted_search_node(
    state: dict,
    *,
    embedder: Any,
    vector_store: Any,
    reranker: Any,
    db_session_factory: Any,
    redis_client: Any = None,
    llm: Any,
) -> dict:
    """Run a focused hybrid search for the follow-up question.

    Uses fewer results than the full pipeline (configurable via settings).
    """
    query = state.get("reformulated_query") or state["follow_up_query"]
    max_results = settings.agent_followup_max_results

    async with db_session_factory() as db:
        search_response = await hybrid_search(
            query=query,
            page=1,
            page_size=max_results,
            llm=llm,
            embedder=embedder,
            vector_store=vector_store,
            reranker=reranker,
            db=db,
            redis_client=redis_client,
        )

    results = []
    for r in search_response.results:
        results.append(
            {
                "case_id": r.case_id,
                "title": r.title,
                "citation": r.citation,
                "court": getattr(r, "court", None),
                "year": getattr(r, "year", None),
                "snippet": getattr(r, "snippet", ""),
                "score": getattr(r, "score", 0.0),
            }
        )

    logger.info("Follow-up search returned %d results for query: %r", len(results), query)

    return {
        "search_results": results,
        "process_events": [
            {
                "type": "progress",
                "stage": "Searching",
                "progress": 0.5,
                "detail": f"Found {len(results)} results",
            }
        ],
    }


async def synthesize_follow_up_node(
    state: dict,
    llm: Any,
    memo_stream_callback: Any | None = None,
) -> dict:
    """Synthesize a follow-up response using prior memo + new search results.

    Uses the Pro LLM for quality synthesis with streaming support.
    """
    follow_up = state["follow_up_query"]
    prior_memo = state.get("prior_memo", "")
    prior_footnotes = state.get("prior_footnotes", [])
    search_results = state.get("search_results", [])
    conversation_history = state.get("conversation_history", [])

    # Truncate prior memo to configured limit
    max_memo_chars = settings.agent_followup_memo_chars
    truncated_memo = prior_memo[:max_memo_chars]
    if len(prior_memo) > max_memo_chars:
        truncated_memo += "\n\n... [memo truncated for context]"

    # Format prior footnotes
    footnotes_text = _format_footnotes(prior_footnotes, max_footnotes=20)

    # Format new search results
    new_results_text = _format_search_results(search_results)

    # Format conversation history
    history_text = _format_conversation_history(conversation_history, max_messages=5)

    user_prompt = FOLLOW_UP_USER_PROMPT.format(
        prior_memo=truncated_memo,
        prior_footnotes=footnotes_text,
        new_search_results=new_results_text,
        conversation_history=history_text,
        follow_up_query=follow_up,
    )

    # Stream or generate
    if memo_stream_callback:
        full_response: list[str] = []
        async for chunk in llm.stream(
            prompt=user_prompt,
            system=FOLLOW_UP_SYSTEM_PROMPT,
            temperature=0.2,
        ):
            full_response.append(chunk)
            await memo_stream_callback(chunk)
        response = "".join(full_response)
    else:
        response = await llm.generate(
            prompt=user_prompt,
            system=FOLLOW_UP_SYSTEM_PROMPT,
            temperature=0.2,
            max_tokens=4096,
        )

    # Build footnotes from new search results
    new_footnotes = []
    for i, r in enumerate(search_results, 1):
        new_footnotes.append(
            {
                "number": i,
                "citation": r.get("citation", ""),
                "source_type": "case",
                "case_id": r.get("case_id"),
                "title": r.get("title", ""),
                "court": r.get("court", ""),
                "year": r.get("year"),
                "excerpt": (r.get("snippet", ""))[:300],
                "is_used": True,
                "verification_status": "unverified",
            }
        )

    logger.info("Follow-up synthesis complete, %d chars", len(response))

    return {
        "response": response,
        "footnotes": new_footnotes,
        "confidence": 0.7,  # Default for follow-ups; could be refined
        "process_events": [
            {
                "type": "progress",
                "stage": "Synthesizing",
                "progress": 1.0,
                "detail": "Follow-up response complete",
            }
        ],
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _format_conversation_history(history: list[dict], max_messages: int = 5) -> str:
    """Format conversation history for prompt inclusion."""
    if not history:
        return "(No prior conversation)"

    recent = history[-max_messages:]
    lines = []
    for msg in recent:
        role = msg.get("role", "user").title()
        content = msg.get("content", "")[:500]
        lines.append(f"{role}: {content}")
    return "\n\n".join(lines)


def _format_footnotes(footnotes: list[dict], max_footnotes: int = 20) -> str:
    """Format prior footnotes for prompt inclusion."""
    if not footnotes:
        return "(No prior footnotes)"

    lines = []
    for fn in footnotes[:max_footnotes]:
        citation = fn.get("citation", "Unknown")
        title = fn.get("title", "")
        court = fn.get("court", "")
        year = fn.get("year", "")
        lines.append(f"[^{fn.get('number', '?')}] {citation} — {title} ({court}, {year})")
    return "\n".join(lines)


def _format_search_results(results: list[dict]) -> str:
    """Format search results for prompt inclusion."""
    if not results:
        return "(No new search results found)"

    lines = []
    for i, r in enumerate(results, 1):
        title = r.get("title", "Unknown")
        citation = r.get("citation", "")
        court = r.get("court", "")
        year = r.get("year", "")
        snippet = r.get("snippet", "")[:500]
        lines.append(
            f"[{i}] {title}\n"
            f"    Citation: {citation}\n"
            f"    Court: {court}, Year: {year}\n"
            f"    Excerpt: {snippet}"
        )
    return "\n\n".join(lines)
