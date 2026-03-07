"""Case Prep Agent LangGraph graph.

Builds a compiled LangGraph state graph that takes a previously analyzed
document, prioritizes issues, performs deep precedent search via citation
graph, orders arguments, and generates a strategy memo -- with HITL
checkpoints at key decision points.

Graph flow:
  START -> load_analysis -> prioritize -> checkpoint_issues -> deep_search ->
  argument_order -> checkpoint_strategy -> strategy_memo -> verify ->
  checkpoint_memo -> END
"""
from __future__ import annotations

import json
import logging
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from app.core.agents.nodes.case_prep_nodes import (
    build_argument_order_node,
    deep_precedent_search_node,
    generate_strategy_memo_node,
    load_analysis_node,
    prioritize_issues_node,
    verify_citations_node,
)
from app.core.agents.state import CasePrepState

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Router functions (module-level for testability)
# ---------------------------------------------------------------------------


def route_after_load(state: CasePrepState) -> str:
    """Route after load_analysis.

    If an error was set (e.g. no DocumentAnalysis found), skip straight to END
    so the user sees the error message instead of empty results.
    """
    if state.get("error"):
        return END
    return "prioritize"


def route_after_issues(state: CasePrepState) -> str:
    """Route after issues checkpoint.

    If the user provided feedback and we haven't exceeded the max iteration
    count, loop back to prioritize. Otherwise proceed to deep_search.
    """
    messages = state.get("messages", [])
    last_feedback = next(
        (
            m
            for m in reversed(messages)
            if m.get("type") == "user_feedback" and m.get("step") == "issues"
        ),
        None,
    )
    if (
        last_feedback
        and last_feedback.get("content")
        and state.get("iteration", 0) < 3
    ):
        return "prioritize"
    return "deep_search"


def route_after_strategy(state: CasePrepState) -> str:
    """Route after strategy checkpoint.

    If the user provided feedback and we haven't exceeded the max iteration
    count, loop back to argument_order. Otherwise proceed to strategy_memo.
    """
    messages = state.get("messages", [])
    last_feedback = next(
        (
            m
            for m in reversed(messages)
            if m.get("type") == "user_feedback" and m.get("step") == "strategy"
        ),
        None,
    )
    if (
        last_feedback
        and last_feedback.get("content")
        and state.get("iteration", 0) < 3
    ):
        return "argument_order"
    return "strategy_memo"


def route_after_memo(state: CasePrepState) -> str:
    """Route after memo checkpoint.

    If the user provided feedback and we haven't exceeded the max iteration
    count, loop back to strategy_memo. Otherwise proceed to END.
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
        return "strategy_memo"
    return END


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------


def build_case_prep_graph(
    *,
    llm: Any,
    flash_llm: Any,
    embedder: Any,
    vector_store: Any,
    reranker: Any,
    graph_store: Any,
    db: Any,
    checkpointer: Any | None = None,
) -> Any:
    """Build and compile the Case Prep Agent LangGraph graph.

    Parameters
    ----------
    llm:
        Primary LLM provider (Gemini Pro) for reasoning-heavy tasks.
    flash_llm:
        Fast LLM provider (Gemini Flash) for lighter tasks.
    embedder:
        Embedding provider for vector search.
    vector_store:
        Vector store (Pinecone) for semantic search.
    reranker:
        Reranker (Cohere) for result re-ranking.
    graph_store:
        Graph store (Neo4j) for citation graph queries.
    db:
        Async database session for SQL queries.
    checkpointer:
        LangGraph checkpointer for persistence.  Can be ``None`` for
        unit testing (graph compiles without a checkpointer).

    Returns
    -------
    Compiled LangGraph state graph.
    """
    graph = StateGraph(CasePrepState)

    # -- Node wrappers (closures capturing dependencies) --------------------

    async def load_analysis(state: CasePrepState) -> dict:
        return await load_analysis_node(state, db)

    async def prioritize(state: CasePrepState) -> dict:
        result = await prioritize_issues_node(state, llm)
        # Increment iteration when looping back through prioritize
        iteration = state.get("iteration", 0)
        if iteration > 0:
            result["iteration"] = iteration + 1
        return result

    async def deep_search(state: CasePrepState) -> dict:
        return await deep_precedent_search_node(
            state, llm, embedder, vector_store, reranker, graph_store, db
        )

    async def argument_order(state: CasePrepState) -> dict:
        return await build_argument_order_node(state, llm)

    async def strategy_memo(state: CasePrepState) -> dict:
        return await generate_strategy_memo_node(state, llm)

    async def verify(state: CasePrepState) -> dict:
        return await verify_citations_node(state, db)

    # -- Checkpoint nodes (HITL via interrupt) ------------------------------

    async def checkpoint_issues(state: CasePrepState) -> dict:
        """Pause for user review of prioritized issues."""
        response = interrupt({
            "question": (
                "Here are the prioritized legal issues. "
                "Reorder or drop any?"
            ),
            "prioritized_issues": state.get("prioritized_issues", []),
        })
        return {
            "messages": [
                {"type": "user_feedback", "step": "issues", "content": response}
            ],
        }

    async def checkpoint_strategy(state: CasePrepState) -> dict:
        """Pause for user review of argument order."""
        response = interrupt({
            "question": (
                "Here is the recommended argument order. "
                "Adjust strategy?"
            ),
            "argument_order": state.get("argument_order", []),
        })
        return {
            "messages": [
                {
                    "type": "user_feedback",
                    "step": "strategy",
                    "content": response,
                }
            ],
        }

    async def checkpoint_memo(state: CasePrepState) -> dict:
        """Pause for user review of strategy memo."""
        response = interrupt({
            "question": "Here is the strategy memo. Any revisions?",
            "enhanced_memo": state.get("enhanced_memo", ""),
        })
        return {
            "messages": [
                {"type": "user_feedback", "step": "memo", "content": response}
            ],
        }

    # -- Register nodes -----------------------------------------------------

    graph.add_node("load_analysis", load_analysis)
    graph.add_node("prioritize", prioritize)
    graph.add_node("checkpoint_issues", checkpoint_issues)
    graph.add_node("deep_search", deep_search)
    graph.add_node("argument_order", argument_order)
    graph.add_node("checkpoint_strategy", checkpoint_strategy)
    graph.add_node("strategy_memo", strategy_memo)
    graph.add_node("verify", verify)
    graph.add_node("checkpoint_memo", checkpoint_memo)

    # -- Edges --------------------------------------------------------------

    graph.add_edge(START, "load_analysis")

    graph.add_conditional_edges(
        "load_analysis",
        route_after_load,
        {"prioritize": "prioritize", END: END},
    )

    graph.add_edge("prioritize", "checkpoint_issues")

    graph.add_conditional_edges(
        "checkpoint_issues",
        route_after_issues,
        {"prioritize": "prioritize", "deep_search": "deep_search"},
    )

    graph.add_edge("deep_search", "argument_order")
    graph.add_edge("argument_order", "checkpoint_strategy")

    graph.add_conditional_edges(
        "checkpoint_strategy",
        route_after_strategy,
        {"argument_order": "argument_order", "strategy_memo": "strategy_memo"},
    )

    graph.add_edge("strategy_memo", "verify")
    graph.add_edge("verify", "checkpoint_memo")

    graph.add_conditional_edges(
        "checkpoint_memo",
        route_after_memo,
        {"strategy_memo": "strategy_memo", END: END},
    )

    # -- Compile ------------------------------------------------------------

    compile_kwargs: dict[str, Any] = {}
    if checkpointer is not None:
        compile_kwargs["checkpointer"] = checkpointer

    return graph.compile(**compile_kwargs)
