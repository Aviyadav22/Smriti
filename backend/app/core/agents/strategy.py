"""Strategy / Argument Builder Agent LangGraph graph.

Builds a compiled LangGraph state graph that analyzes case facts, decomposes
legal elements, fetches judge profiles, searches for precedents, assesses
argument strength, generates IRAC-structured arguments, runs adversarial
searches, determines optimal argument ordering, generates counter-arguments
with judge-specific considerations, and synthesizes an argument memo -- with
HITL checkpoints at key decision points.

Graph flow:
  START -> analyze_facts -> element_decomposition -> fetch_judge ->
  checkpoint_analysis -> search_precedents -> evaluate_relevance ->
  assess_strength -> generate_arguments_irac -> checkpoint_arguments ->
  adversarial_search -> counter_and_judge -> argument_ordering ->
  synthesize_strategy -> format_footnotes -> verify ->
  quality_check -> [route: pass->checkpoint_memo, fail->synthesize_strategy] ->
  checkpoint_memo -> END
"""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from langgraph.graph import END, START, StateGraph

from app.core.agents.nodes.common import element_decomposition_node
from app.core.agents.nodes.strategy_nodes import (
    adversarial_search_strategy_node,
    analyze_facts_node,
    argument_ordering_node,
    assess_strength_node,
    counter_arguments_node,
    evaluate_relevance_node,
    fetch_judge_profile_node,
    format_strategy_footnotes_node,
    generate_arguments_irac_node,
    judge_considerations_node,
    quality_check_node,
    search_precedents_node,
    synthesize_strategy_node,
    verify_citations_node,
)
from app.core.agents.routing_utils import compile_graph, make_checkpoint_node, make_feedback_router
from app.core.agents.state import StrategyState
from app.db.postgres import async_session_factory

if TYPE_CHECKING:
    from langgraph.checkpoint.base import BaseCheckpointSaver
    from langgraph.graph.state import CompiledStateGraph

    from app.core.interfaces import (
        EmbeddingProvider,
        GraphStore,
        LLMProvider,
        Reranker,
        VectorStore,
    )

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Router functions (module-level for testability)
# ---------------------------------------------------------------------------

route_after_analysis = make_feedback_router("analysis", "analyze_facts", "search_precedents", check_error=True)
route_after_arguments = make_feedback_router("arguments", "generate_arguments_irac", "adversarial_search", check_error=True)
route_after_memo = make_feedback_router("memo", "synthesize_strategy", proceed=None, check_error=True)


def route_after_quality(state: dict) -> str:
    """Route after quality check: retry synthesis or proceed to checkpoint."""
    error = state.get("error", "")
    if error and "[QUALITY_RETRY]" in error and state.get("quality_attempts", 0) < 3:
        return "synthesize_strategy"
    return "checkpoint_memo"


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------


def build_strategy_graph(
    *,
    llm: LLMProvider,
    flash_llm: LLMProvider,
    embedder: EmbeddingProvider,
    vector_store: VectorStore,
    reranker: Reranker,
    graph_store: GraphStore,
    checkpointer: BaseCheckpointSaver | None = None,
    memo_stream_callback: Any | None = None,
) -> CompiledStateGraph:
    """Build and compile the Strategy Agent LangGraph graph.

    Parameters
    ----------
    llm:
        Primary LLM provider (Gemini Pro) for reasoning-heavy tasks.
    flash_llm:
        Fast LLM provider (Gemini Flash) for fact analysis.
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
    graph = StateGraph(StrategyState)

    # -- Node wrappers (closures capturing dependencies) --------------------
    # DB-accessing nodes create fresh sessions via async_session_factory()
    # because the FastAPI Depends(get_db) session closes before the
    # StreamingResponse generator runs.

    async def analyze_facts(state: StrategyState) -> dict:
        result = await analyze_facts_node(state, flash_llm)
        # Count feedback messages for THIS step only (not shared across checkpoints)
        step_feedback_count = sum(
            1 for m in state.get("messages", [])
            if isinstance(m, dict) and m.get("type") == "user_feedback" and m.get("step") == "analysis"
        )
        result["iteration"] = step_feedback_count
        return result

    async def fetch_judge(state: StrategyState) -> dict:
        async with async_session_factory() as session:
            return await fetch_judge_profile_node(state, session)

    async def search_precedents(state: StrategyState) -> dict:
        async with async_session_factory() as session:
            return await search_precedents_node(
                state, llm, embedder, vector_store, reranker, graph_store, session
            )

    async def evaluate_relevance(state: StrategyState) -> dict:
        return await evaluate_relevance_node(state, flash_llm)

    async def assess_strength(state: StrategyState) -> dict:
        return await assess_strength_node(state, llm)

    async def element_decomposition(state: StrategyState) -> dict:
        # Adapt StrategyState to the dict shape element_decomposition_node expects.
        # Extract minimal statute context from fact_analysis causes_of_action
        # (the full statute_lookup_node is not available in the strategy graph).
        fact_analysis = state.get("fact_analysis", {})
        statute_refs: list[dict] = []
        if isinstance(fact_analysis, dict):
            for cause in fact_analysis.get("causes_of_action", []):
                if isinstance(cause, dict) and cause.get("statutory_basis"):
                    statute_refs.append({
                        "act_short_name": cause["statutory_basis"],
                        "section_number": "",
                        "section_title": "",
                        "section_text": "",
                        "is_repealed": False,
                    })
        adapted = {
            "query": state.get("case_facts", ""),
            "rewritten_query": "",
            "statute_context": statute_refs,
            "complexity": "complex",
        }
        return await element_decomposition_node(adapted, flash_llm)

    async def generate_arguments_irac(state: StrategyState) -> dict:
        result = await generate_arguments_irac_node(state, llm)
        step_feedback_count = sum(
            1 for m in state.get("messages", [])
            if isinstance(m, dict) and m.get("type") == "user_feedback" and m.get("step") == "arguments"
        )
        result["iteration"] = step_feedback_count
        return result

    async def adversarial_search(state: StrategyState) -> dict:
        return await adversarial_search_strategy_node(
            state, llm, embedder, vector_store, reranker
        )

    async def argument_ordering(state: StrategyState) -> dict:
        return await argument_ordering_node(state, llm)

    async def counter_and_judge(state: StrategyState) -> dict:
        counter_result, judge_result = await asyncio.gather(
            counter_arguments_node(state, llm),
            judge_considerations_node(state, llm),
        )
        return {**counter_result, **judge_result}

    async def synthesize_strategy(state: StrategyState) -> dict:
        result = await synthesize_strategy_node(state, llm, stream_callback=memo_stream_callback)
        # Count feedback messages for THIS step only (not shared across checkpoints)
        step_feedback_count = sum(
            1 for m in state.get("messages", [])
            if isinstance(m, dict) and m.get("type") == "user_feedback" and m.get("step") == "memo"
        )
        result["iteration"] = step_feedback_count
        return result

    async def verify(state: StrategyState) -> dict:
        async with async_session_factory() as session:
            return await verify_citations_node(state, session)

    async def format_footnotes(state: StrategyState) -> dict:
        return await format_strategy_footnotes_node(state)

    async def quality_check(state: StrategyState) -> dict:
        return await quality_check_node(state, llm)

    # -- Checkpoint nodes (HITL via interrupt) ------------------------------

    checkpoint_analysis = make_checkpoint_node(
        "analysis",
        "Here is the fact analysis and judge profile. Would you like to adjust?",
        {"fact_analysis": ("fact_analysis", {}), "judge_profile": ("judge_profile", {})},
    )

    checkpoint_arguments = make_checkpoint_node(
        "arguments",
        "Here are the IRAC-structured arguments and strength assessment. Would you like to adjust?",
        {"irac_arguments": ("irac_arguments", []), "strength_assessment": ("strength_assessment", {})},
    )

    checkpoint_memo = make_checkpoint_node(
        "memo",
        "Here is the argument memo with footnotes and quality assessment. Any revisions?",
        {
            "strategy_memo": ("strategy_memo", ""),
            "confidence": ("confidence", 0.0),
            "footnotes": ("footnotes", []),
            "legal_quality_result": ("legal_quality_result", {}),
            "contradictions": ("contradictions", []),
        },
    )

    # -- Register nodes -----------------------------------------------------

    graph.add_node("analyze_facts", analyze_facts)
    graph.add_node("element_decomposition", element_decomposition)
    graph.add_node("fetch_judge", fetch_judge)
    graph.add_node("checkpoint_analysis", checkpoint_analysis)
    graph.add_node("search_precedents", search_precedents)
    graph.add_node("evaluate_relevance", evaluate_relevance)
    graph.add_node("assess_strength", assess_strength)
    graph.add_node("generate_arguments_irac", generate_arguments_irac)
    graph.add_node("checkpoint_arguments", checkpoint_arguments)
    graph.add_node("adversarial_search", adversarial_search)
    graph.add_node("counter_and_judge", counter_and_judge)
    graph.add_node("argument_ordering", argument_ordering)
    graph.add_node("synthesize_strategy", synthesize_strategy)
    graph.add_node("format_footnotes", format_footnotes)
    graph.add_node("verify", verify)
    graph.add_node("quality_check", quality_check)
    graph.add_node("checkpoint_memo", checkpoint_memo)

    # -- Edges --------------------------------------------------------------

    graph.add_edge(START, "analyze_facts")
    graph.add_edge("analyze_facts", "element_decomposition")
    graph.add_edge("element_decomposition", "fetch_judge")
    graph.add_edge("fetch_judge", "checkpoint_analysis")

    graph.add_conditional_edges(
        "checkpoint_analysis",
        route_after_analysis,
        {"analyze_facts": "analyze_facts", "search_precedents": "search_precedents", END: END},
    )

    graph.add_edge("search_precedents", "evaluate_relevance")
    graph.add_edge("evaluate_relevance", "assess_strength")
    graph.add_edge("assess_strength", "generate_arguments_irac")
    graph.add_edge("generate_arguments_irac", "checkpoint_arguments")

    graph.add_conditional_edges(
        "checkpoint_arguments",
        route_after_arguments,
        {
            "generate_arguments_irac": "generate_arguments_irac",
            "adversarial_search": "adversarial_search",
            END: END,
        },
    )

    graph.add_edge("adversarial_search", "counter_and_judge")
    graph.add_edge("counter_and_judge", "argument_ordering")
    graph.add_edge("argument_ordering", "synthesize_strategy")
    graph.add_edge("synthesize_strategy", "format_footnotes")
    graph.add_edge("format_footnotes", "verify")
    graph.add_edge("verify", "quality_check")
    graph.add_conditional_edges(
        "quality_check",
        route_after_quality,
        {"synthesize_strategy": "synthesize_strategy", "checkpoint_memo": "checkpoint_memo"},
    )
    graph.add_conditional_edges(
        "checkpoint_memo",
        route_after_memo,
        {"synthesize_strategy": "synthesize_strategy", END: END},
    )

    # -- Compile ------------------------------------------------------------

    return compile_graph(graph, checkpointer)
