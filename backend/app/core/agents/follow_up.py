"""Follow-up conversation LangGraph sub-graph.

A lightweight 3-node graph for follow-up questions on completed research memos.
Takes 10-30 seconds (vs 1-3 minutes for the full research pipeline).

Graph: START -> reformulate_with_context -> targeted_search -> synthesize_follow_up -> END

No HITL checkpoints — follow-ups are quick refinements, not full research cycles.
"""

from __future__ import annotations

import logging
import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

from app.core.agents.nodes.follow_up_nodes import (
    reformulate_with_context_node,
    synthesize_follow_up_node,
    targeted_search_node,
)
from app.core.agents.routing_utils import compile_graph
from app.db.postgres import async_session_factory

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# State schema
# ---------------------------------------------------------------------------


class FollowUpState(TypedDict):
    """State for the follow-up conversation sub-graph."""

    # Input
    follow_up_query: str
    prior_memo: str
    prior_footnotes: list[dict]
    conversation_history: list[dict]

    # Intermediate
    reformulated_query: str
    search_results: list[dict]

    # Output
    response: str
    footnotes: list[dict]
    confidence: float

    # SSE progress events (reducer: append)
    process_events: Annotated[list[dict], operator.add]
    messages: Annotated[list[dict], operator.add]

    # Error
    error: str


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------


def build_follow_up_graph(
    *,
    llm: Any,
    flash_llm: Any,
    embedder: Any,
    vector_store: Any,
    reranker: Any,
    graph_store: Any = None,
    redis_client: Any = None,
    checkpointer: Any | None = None,
    memo_stream_callback: Any | None = None,
) -> Any:
    """Build and compile the follow-up conversation LangGraph graph.

    Parameters
    ----------
    llm : LLMProvider
        Primary LLM (Gemini Pro) for synthesis.
    flash_llm : LLMProvider
        Fast LLM (Gemini Flash) for reformulation.
    embedder : EmbeddingProvider
        For vector search.
    vector_store : VectorStore
        Pinecone vector store.
    reranker : Reranker
        Cohere reranker.
    graph_store : GraphStore, optional
        Neo4j graph store (unused in follow-up, reserved for future).
    redis_client : optional
        Redis for search caching.
    checkpointer : optional
        LangGraph checkpointer for state persistence.
    memo_stream_callback : callable, optional
        Async callback for streaming memo chunks via SSE.
    """

    # -- Node wrappers (closures capture dependencies) -----------------------

    async def reformulate(state: FollowUpState) -> dict:
        return await reformulate_with_context_node(state, flash_llm)

    async def search(state: FollowUpState) -> dict:
        return await targeted_search_node(
            state,
            embedder=embedder,
            vector_store=vector_store,
            reranker=reranker,
            db_session_factory=async_session_factory,
            redis_client=redis_client,
            llm=flash_llm,
        )

    async def synthesize(state: FollowUpState) -> dict:
        return await synthesize_follow_up_node(
            state,
            llm,
            memo_stream_callback=memo_stream_callback,
        )

    # -- Graph construction --------------------------------------------------

    graph = StateGraph(FollowUpState)

    graph.add_node("reformulate_with_context", reformulate)
    graph.add_node("targeted_search", search)
    graph.add_node("synthesize_follow_up", synthesize)

    graph.add_edge(START, "reformulate_with_context")
    graph.add_edge("reformulate_with_context", "targeted_search")
    graph.add_edge("targeted_search", "synthesize_follow_up")
    graph.add_edge("synthesize_follow_up", END)

    return compile_graph(graph, checkpointer)
