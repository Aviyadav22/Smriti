"""Research Agent LangGraph graph.

Builds a compiled LangGraph state graph that decomposes legal research
questions into sub-queries, searches in parallel, detects contradictions,
and synthesizes a research memo — with fully interactive HITL checkpoints.

Graph flow:
  START -> classify -> decompose -> checkpoint_plan -> search -> gather ->
  contradictions -> checkpoint_findings -> synthesize -> verify ->
  checkpoint_memo -> END
"""
from __future__ import annotations

import logging
from typing import Any

from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt

from app.core.agents.nodes.research_nodes import (
    classify_query_node,
    decompose_query_node,
    detect_contradictions_node,
    gather_results_node,
    parallel_search_node,
    synthesize_memo_node,
    verify_citations_node,
)
from app.core.agents.state import ResearchState

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Router functions (module-level for testability)
# ---------------------------------------------------------------------------


def route_after_plan(state: ResearchState) -> str:
    """Route after plan checkpoint.

    If the user provided feedback and we haven't exceeded the max iteration
    count, loop back to decompose. Otherwise proceed to search.
    """
    messages = state.get("messages", [])
    last_feedback = next(
        (
            m
            for m in reversed(messages)
            if m.get("type") == "user_feedback" and m.get("step") == "plan"
        ),
        None,
    )
    if (
        last_feedback
        and last_feedback.get("content")
        and state.get("iteration", 0) < 3
    ):
        return "decompose"
    return "search"


def route_after_findings(state: ResearchState) -> str:
    """Route after findings checkpoint.

    If the user provided feedback and we haven't exceeded the max iteration
    count, loop back to search. Otherwise proceed to synthesize.
    """
    messages = state.get("messages", [])
    last_feedback = next(
        (
            m
            for m in reversed(messages)
            if m.get("type") == "user_feedback" and m.get("step") == "findings"
        ),
        None,
    )
    if (
        last_feedback
        and last_feedback.get("content")
        and state.get("iteration", 0) < 3
    ):
        return "search"
    return "synthesize"


def route_after_memo(state: ResearchState) -> str:
    """Route after memo checkpoint.

    If the user provided feedback and we haven't exceeded the max iteration
    count, loop back to synthesize. Otherwise proceed to END.
    """
    messages = state.get("messages", [])
    last_feedback = next(
        (
            m
            for m in reversed(messages)
            if m.get("type") == "user_feedback" and m.get("step") == "memo"
        ),
        None,
    )
    if (
        last_feedback
        and last_feedback.get("content")
        and state.get("iteration", 0) < 3
    ):
        return "synthesize"
    return END


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------


def build_research_graph(
    *,
    llm: Any,
    flash_llm: Any,
    embedder: Any,
    vector_store: Any,
    reranker: Any,
    db: Any,
    checkpointer: Any | None = None,
) -> Any:
    """Build and compile the Research Agent LangGraph graph.

    Parameters
    ----------
    llm:
        Primary LLM provider (Gemini Pro) for reasoning-heavy tasks.
    flash_llm:
        Fast LLM provider (Gemini Flash) for classification.
    embedder:
        Embedding provider for vector search.
    vector_store:
        Vector store (Pinecone) for semantic search.
    reranker:
        Reranker (Cohere) for result re-ranking.
    db:
        Async database session for SQL queries.
    checkpointer:
        LangGraph checkpointer for persistence.  Can be ``None`` for
        unit testing (graph compiles without a checkpointer).

    Returns
    -------
    Compiled LangGraph state graph.
    """
    graph = StateGraph(ResearchState)

    # -- Node wrappers (closures capturing dependencies) --------------------

    async def classify(state: ResearchState) -> dict:
        return await classify_query_node(state, flash_llm)

    async def decompose(state: ResearchState) -> dict:
        result = await decompose_query_node(state, llm)
        # Increment iteration when looping back through decompose
        iteration = state.get("iteration", 0)
        if iteration > 0:
            result["iteration"] = iteration + 1
        return result

    async def search(state: ResearchState) -> dict:
        return await parallel_search_node(
            state, llm, embedder, vector_store, reranker, db
        )

    async def gather(state: ResearchState) -> dict:
        return await gather_results_node(state)

    async def contradictions(state: ResearchState) -> dict:
        return await detect_contradictions_node(state, llm)

    async def synthesize(state: ResearchState) -> dict:
        return await synthesize_memo_node(state, llm)

    async def verify(state: ResearchState) -> dict:
        return await verify_citations_node(state, db)

    # -- Checkpoint nodes (HITL via interrupt) ------------------------------

    async def checkpoint_plan(state: ResearchState) -> dict:
        """Pause for user review of sub-queries."""
        response = interrupt({
            "question": (
                "I plan to research these sub-questions. "
                "Would you like to adjust them?"
            ),
            "sub_queries": state["sub_queries"],
            "classification": next(
                (
                    m["data"]
                    for m in state.get("messages", [])
                    if m.get("type") == "classification"
                ),
                None,
            ),
        })
        return {
            "messages": [
                {"type": "user_feedback", "step": "plan", "content": response}
            ],
        }

    async def checkpoint_findings(state: ResearchState) -> dict:
        """Pause for user review of search findings."""
        result_count = len(state.get("search_results", []))
        cross_ref_count = len(state.get("cross_references", []))
        contradiction_count = len(state.get("contradictions", []))

        response = interrupt({
            "question": (
                "Here are the search findings. "
                "Would you like to focus on any specific area?"
            ),
            "result_count": result_count,
            "cross_references": state.get("cross_references", []),
            "contradictions": state.get("contradictions", []),
            "summary": (
                f"Found {result_count} results, "
                f"{cross_ref_count} cross-references, "
                f"{contradiction_count} contradictions."
            ),
        })
        return {
            "messages": [
                {
                    "type": "user_feedback",
                    "step": "findings",
                    "content": response,
                }
            ],
        }

    async def checkpoint_memo(state: ResearchState) -> dict:
        """Pause for user review of draft memo."""
        response = interrupt({
            "question": "Here is the draft research memo. Any revisions?",
            "draft_memo": state.get("draft_memo", ""),
            "confidence": state.get("confidence", 0.0),
        })
        return {
            "messages": [
                {"type": "user_feedback", "step": "memo", "content": response}
            ],
        }

    # -- Register nodes -----------------------------------------------------

    graph.add_node("classify", classify)
    graph.add_node("decompose", decompose)
    graph.add_node("checkpoint_plan", checkpoint_plan)
    graph.add_node("search", search)
    graph.add_node("gather", gather)
    graph.add_node("contradictions", contradictions)
    graph.add_node("checkpoint_findings", checkpoint_findings)
    graph.add_node("synthesize", synthesize)
    graph.add_node("verify", verify)
    graph.add_node("checkpoint_memo", checkpoint_memo)

    # -- Edges --------------------------------------------------------------

    graph.add_edge(START, "classify")
    graph.add_edge("classify", "decompose")
    graph.add_edge("decompose", "checkpoint_plan")

    graph.add_conditional_edges(
        "checkpoint_plan",
        route_after_plan,
        {"decompose": "decompose", "search": "search"},
    )

    graph.add_edge("search", "gather")
    graph.add_edge("gather", "contradictions")
    graph.add_edge("contradictions", "checkpoint_findings")

    graph.add_conditional_edges(
        "checkpoint_findings",
        route_after_findings,
        {"search": "search", "synthesize": "synthesize"},
    )

    graph.add_edge("synthesize", "verify")
    graph.add_edge("verify", "checkpoint_memo")

    graph.add_conditional_edges(
        "checkpoint_memo",
        route_after_memo,
        {"synthesize": "synthesize", END: END},
    )

    # -- Compile ------------------------------------------------------------

    compile_kwargs: dict[str, Any] = {}
    if checkpointer is not None:
        compile_kwargs["checkpointer"] = checkpointer

    return graph.compile(**compile_kwargs)
