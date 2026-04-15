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

import logging
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.core.agents.nodes.case_prep_nodes import (
    build_argument_order_node,
    deep_precedent_search_node,
    generate_strategy_memo_node,
    load_analysis_node,
    prioritize_issues_node,
    verify_citations_node,
)
from app.core.agents.routing_utils import compile_graph, make_checkpoint_node, make_feedback_router
from app.core.agents.state import CasePrepState
from app.db.postgres import async_session_factory

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


route_after_issues = make_feedback_router("issues", "prioritize", "deep_search", check_error=True)
route_after_strategy = make_feedback_router(
    "strategy", "argument_order", "strategy_memo", check_error=True
)
route_after_memo = make_feedback_router("memo", "strategy_memo", check_error=True)


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------


def build_case_prep_graph(
    *,
    llm: Any,
    embedder: Any,
    vector_store: Any,
    reranker: Any,
    graph_store: Any,
    checkpointer: Any | None = None,
) -> Any:
    """Build and compile the Case Prep Agent LangGraph graph.

    Parameters
    ----------
    llm:
        Primary LLM provider (Gemini Pro) for reasoning-heavy tasks.
    embedder:
        Embedding provider for vector search.
    vector_store:
        Vector store (Pinecone) for semantic search.
    reranker:
        Reranker (Cohere) for result re-ranking.
    graph_store:
        Graph store (Neo4j) for citation graph queries.
    checkpointer:
        LangGraph checkpointer for persistence.  Can be ``None`` for
        unit testing (graph compiles without a checkpointer).

    Returns
    -------
    Compiled LangGraph state graph.
    """
    graph = StateGraph(CasePrepState)

    # -- Node wrappers (closures capturing dependencies) --------------------
    # DB-accessing nodes create fresh sessions via async_session_factory()
    # because the FastAPI Depends(get_db) session closes before the
    # StreamingResponse generator runs.

    async def load_analysis(state: CasePrepState) -> dict:
        async with async_session_factory() as session:
            return await load_analysis_node(state, session)

    async def prioritize(state: CasePrepState) -> dict:
        result = await prioritize_issues_node(state, llm)
        # Count feedback messages for THIS step only (not shared across checkpoints)
        step_feedback_count = sum(
            1
            for m in state.get("messages", [])
            if isinstance(m, dict)
            and m.get("type") == "user_feedback"
            and m.get("step") == "issues"
        )
        result["iteration"] = step_feedback_count
        return result

    async def deep_search(state: CasePrepState) -> dict:
        async with async_session_factory() as session:
            return await deep_precedent_search_node(
                state, llm, embedder, vector_store, reranker, graph_store, session
            )

    async def argument_order(state: CasePrepState) -> dict:
        return await build_argument_order_node(state, llm)

    async def strategy_memo(state: CasePrepState) -> dict:
        return await generate_strategy_memo_node(state, llm)

    async def verify(state: CasePrepState) -> dict:
        async with async_session_factory() as session:
            return await verify_citations_node(state, session)

    # -- Checkpoint nodes (HITL via interrupt) ------------------------------

    checkpoint_issues = make_checkpoint_node(
        "issues",
        "Here are the prioritized legal issues. Reorder or drop any?",
        {"prioritized_issues": ("prioritized_issues", [])},
    )

    checkpoint_strategy = make_checkpoint_node(
        "strategy",
        "Here is the recommended argument order. Adjust strategy?",
        {"argument_order": ("argument_order", [])},
    )

    checkpoint_memo = make_checkpoint_node(
        "memo",
        "Here is the strategy memo. Any revisions?",
        {"enhanced_memo": ("enhanced_memo", "")},
    )

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
        {"prioritize": "prioritize", "deep_search": "deep_search", END: END},
    )

    graph.add_edge("deep_search", "argument_order")
    graph.add_edge("argument_order", "checkpoint_strategy")

    graph.add_conditional_edges(
        "checkpoint_strategy",
        route_after_strategy,
        {"argument_order": "argument_order", "strategy_memo": "strategy_memo", END: END},
    )

    graph.add_edge("strategy_memo", "verify")
    graph.add_edge("verify", "checkpoint_memo")

    graph.add_conditional_edges(
        "checkpoint_memo",
        route_after_memo,
        {"strategy_memo": "strategy_memo", END: END},
    )

    # -- Compile ------------------------------------------------------------

    return compile_graph(graph, checkpointer)
