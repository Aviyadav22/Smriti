"""Strategy Agent LangGraph graph.

Builds a compiled LangGraph state graph that analyzes case facts, fetches
judge profiles, searches for precedents, assesses argument strength,
generates arguments with counter-arguments and judge-specific considerations,
and synthesizes a litigation strategy memo -- with HITL checkpoints at key
decision points.

Graph flow:
  START -> analyze_facts -> fetch_judge -> checkpoint_analysis ->
  search_precedents -> assess_strength -> generate_arguments ->
  checkpoint_arguments -> counter_arguments -> judge_considerations ->
  synthesize_strategy -> verify -> checkpoint_memo -> END
"""
from __future__ import annotations

import logging
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import interrupt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.interfaces import (
    EmbeddingProvider,
    GraphStore,
    LLMProvider,
    Reranker,
    VectorStore,
)
from app.core.agents.nodes.strategy_nodes import (
    analyze_facts_node,
    assess_strength_node,
    counter_arguments_node,
    fetch_judge_profile_node,
    generate_arguments_node,
    judge_considerations_node,
    search_precedents_node,
    synthesize_strategy_node,
    verify_citations_node,
)
from app.core.agents.state import StrategyState

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Router functions (module-level for testability)
# ---------------------------------------------------------------------------


def route_after_analysis(state: StrategyState) -> str:
    """Route after analysis checkpoint.

    If the user provided feedback and we haven't exceeded the max iteration
    count, loop back to analyze_facts. Otherwise proceed to search_precedents.
    """
    if state.get("error"):
        return END
    messages = state.get("messages", [])
    last_feedback = next(
        (
            m
            for m in reversed(messages)
            if m.get("type") == "user_feedback" and m.get("step") == "analysis"
        ),
        None,
    )
    if (
        last_feedback
        and last_feedback.get("content")
        and state.get("iteration", 0) < 3
    ):
        return "analyze_facts"
    return "search_precedents"


def route_after_arguments(state: StrategyState) -> str:
    """Route after arguments checkpoint.

    If the user provided feedback and we haven't exceeded the max iteration
    count, loop back to generate_arguments. Otherwise proceed to
    counter_arguments.
    """
    if state.get("error"):
        return END
    messages = state.get("messages", [])
    last_feedback = next(
        (
            m
            for m in reversed(messages)
            if m.get("type") == "user_feedback" and m.get("step") == "arguments"
        ),
        None,
    )
    if (
        last_feedback
        and last_feedback.get("content")
        and state.get("iteration", 0) < 3
    ):
        return "generate_arguments"
    return "counter_arguments"


def route_after_memo(state: StrategyState) -> str:
    """Route after memo checkpoint.

    If the user provided feedback and we haven't exceeded the max iteration
    count, loop back to synthesize_strategy. Otherwise proceed to END.
    """
    if state.get("error"):
        return END
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
        return "synthesize_strategy"
    return END


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
    db: AsyncSession,
    checkpointer: BaseCheckpointSaver | None = None,
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
    db:
        Async database session for SQL queries.
    checkpointer:
        LangGraph checkpointer for persistence.  Can be ``None`` for
        unit testing (graph compiles without a checkpointer).

    Returns
    -------
    Compiled LangGraph state graph.
    """
    graph = StateGraph(StrategyState)

    # -- Node wrappers (closures capturing dependencies) --------------------

    async def analyze_facts(state: StrategyState) -> dict:
        result = await analyze_facts_node(state, flash_llm)
        # Always increment iteration counter
        result["iteration"] = state.get("iteration", 0) + 1
        return result

    async def fetch_judge(state: StrategyState) -> dict:
        return await fetch_judge_profile_node(state, db)

    async def search_precedents(state: StrategyState) -> dict:
        return await search_precedents_node(
            state, llm, embedder, vector_store, reranker, graph_store, db
        )

    async def assess_strength(state: StrategyState) -> dict:
        return await assess_strength_node(state, llm)

    async def generate_arguments(state: StrategyState) -> dict:
        result = await generate_arguments_node(state, llm)
        result["iteration"] = state.get("iteration", 0) + 1
        return result

    async def counter_args(state: StrategyState) -> dict:
        return await counter_arguments_node(state, llm)

    async def judge_consider(state: StrategyState) -> dict:
        return await judge_considerations_node(state, llm)

    async def synthesize_strategy(state: StrategyState) -> dict:
        result = await synthesize_strategy_node(state, llm)
        result["iteration"] = state.get("iteration", 0) + 1
        return result

    async def verify(state: StrategyState) -> dict:
        return await verify_citations_node(state, db)

    # -- Checkpoint nodes (HITL via interrupt) ------------------------------

    async def checkpoint_analysis(state: StrategyState) -> dict:
        """Pause for user review of parsed facts and judge profile."""
        response = interrupt({
            "question": (
                "Here is the fact analysis and judge profile. "
                "Would you like to adjust?"
            ),
            "fact_analysis": state.get("fact_analysis", {}),
            "judge_profile": state.get("judge_profile", {}),
        })
        return {
            "messages": [
                {
                    "type": "user_feedback",
                    "step": "analysis",
                    "content": response,
                }
            ],
        }

    async def checkpoint_arguments(state: StrategyState) -> dict:
        """Pause for user review of arguments and strength assessment."""
        response = interrupt({
            "question": (
                "Here are the legal arguments and strength assessment. "
                "Would you like to adjust?"
            ),
            "legal_arguments": state.get("legal_arguments", []),
            "strength_assessment": state.get("strength_assessment", {}),
        })
        return {
            "messages": [
                {
                    "type": "user_feedback",
                    "step": "arguments",
                    "content": response,
                }
            ],
        }

    async def checkpoint_memo(state: StrategyState) -> dict:
        """Pause for user review of final strategy memo."""
        response = interrupt({
            "question": "Here is the strategy memo. Any revisions?",
            "strategy_memo": state.get("strategy_memo", ""),
            "confidence": state.get("confidence", 0.0),
        })
        return {
            "messages": [
                {"type": "user_feedback", "step": "memo", "content": response}
            ],
        }

    # -- Register nodes -----------------------------------------------------

    graph.add_node("analyze_facts", analyze_facts)
    graph.add_node("fetch_judge", fetch_judge)
    graph.add_node("checkpoint_analysis", checkpoint_analysis)
    graph.add_node("search_precedents", search_precedents)
    graph.add_node("assess_strength", assess_strength)
    graph.add_node("generate_arguments", generate_arguments)
    graph.add_node("checkpoint_arguments", checkpoint_arguments)
    graph.add_node("counter_arguments", counter_args)
    graph.add_node("judge_considerations", judge_consider)
    graph.add_node("synthesize_strategy", synthesize_strategy)
    graph.add_node("verify", verify)
    graph.add_node("checkpoint_memo", checkpoint_memo)

    # -- Edges --------------------------------------------------------------

    graph.add_edge(START, "analyze_facts")
    graph.add_edge("analyze_facts", "fetch_judge")
    graph.add_edge("fetch_judge", "checkpoint_analysis")

    graph.add_conditional_edges(
        "checkpoint_analysis",
        route_after_analysis,
        {"analyze_facts": "analyze_facts", "search_precedents": "search_precedents", END: END},
    )

    graph.add_edge("search_precedents", "assess_strength")
    graph.add_edge("assess_strength", "generate_arguments")
    graph.add_edge("generate_arguments", "checkpoint_arguments")

    graph.add_conditional_edges(
        "checkpoint_arguments",
        route_after_arguments,
        {
            "generate_arguments": "generate_arguments",
            "counter_arguments": "counter_arguments",
            END: END,
        },
    )

    graph.add_edge("counter_arguments", "judge_considerations")
    graph.add_edge("judge_considerations", "synthesize_strategy")
    graph.add_edge("synthesize_strategy", "verify")
    graph.add_edge("verify", "checkpoint_memo")

    graph.add_conditional_edges(
        "checkpoint_memo",
        route_after_memo,
        {"synthesize_strategy": "synthesize_strategy", END: END},
    )

    # -- Compile ------------------------------------------------------------

    compile_kwargs: dict[str, Any] = {}
    if checkpointer is not None:
        compile_kwargs["checkpointer"] = checkpointer

    return graph.compile(**compile_kwargs)
