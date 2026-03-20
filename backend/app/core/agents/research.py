"""Research Agent V2 LangGraph graph.

Builds a compiled LangGraph state graph with orchestrated multi-agent
research: classify → plan → dispatch workers (Send fan-out) → gather →
evaluate → gap analysis → synthesis → verify → HITL checkpoints.

Graph flow (complex queries):
  START → [rewrite_query ∥ classify] → route_by_complexity
    → plan_research → checkpoint_plan → dispatch_workers → [Send() fan-out]
    → gather_results → batch_cot_with_reflection → evaluate_and_extract
    → gap_analysis → [should_refine] → dispatch_workers | checkpoint_findings
    → synthesize → verify → checkpoint_memo → END

Fast path (simple queries):
  START → [rewrite_query ∥ classify] → route_by_complexity
    → fast_path_search → fast_path_synthesis → verify → checkpoint_memo → END
"""
from __future__ import annotations

import logging
from typing import Any

from langgraph.graph import StateGraph, START, END
from langgraph.types import Send, interrupt

from app.core.agents.nodes.research_nodes import (
    # V1 nodes (kept for backward compat in V2 pipeline)
    classify_query_node,
    synthesize_memo_node,
    verify_citations_node,
    # V2 nodes
    batch_worker_cot_with_reflection_node,
    evaluate_and_extract_node,
    fast_path_search_node,
    fast_path_synthesis_node,
    format_footnotes_node,
    gap_analysis_node,
    gather_worker_results_node,
    legal_quality_check_node,
    plan_research_node,
    pre_warm_embeddings_node,
    rewrite_query_node,
    speculative_synthesis_with_contradictions_node,
    verify_citations_v2_node,
)
from app.core.agents.nodes.worker_nodes import (
    case_law_worker,
    graph_community_worker,
    graph_worker,
    ik_search_worker,
    named_case_worker,
    statute_worker,
    web_search_worker,
)
from app.core.agents.routing_utils import (
    compile_graph,
    make_checkpoint_node,
    make_feedback_router,
)
from app.core.agents.state import ResearchState
from app.db.postgres import async_session_factory

logger = logging.getLogger(__name__)


# -- HITL feedback routers --------------------------------------------------

route_after_plan = make_feedback_router(
    "plan", "plan_research", "dispatch_workers", check_error=True,
)
route_after_findings = make_feedback_router(
    "findings", "dispatch_workers", "synthesize", check_error=True,
)
route_after_memo = make_feedback_router("memo", "synthesize", check_error=True)


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
    graph_store: Any = None,
    web_search: Any = None,
    ik_client: Any = None,
    checkpointer: Any | None = None,
) -> Any:
    """Build and compile the Research Agent V2 LangGraph graph.

    Parameters
    ----------
    llm:
        Primary LLM provider (Gemini Pro) for reasoning/synthesis.
    flash_llm:
        Fast LLM provider (Gemini Flash) for classification/planning.
    embedder:
        Embedding provider for vector search.
    vector_store:
        Vector store (Pinecone) for semantic search.
    reranker:
        Reranker (Cohere) for result re-ranking.
    graph_store:
        Graph store (Neo4j) for citation graph traversal.
    web_search:
        Web search provider (Tavily) for recent developments.
    ik_client:
        External doc provider (Indian Kanoon) for case retrieval.
    checkpointer:
        LangGraph checkpointer for persistence.
    """
    graph = StateGraph(ResearchState)

    # -- Node wrappers (closures capturing dependencies) --------------------

    # [S2] Parallel: rewrite + classify both read original query
    async def rewrite(state: ResearchState) -> dict:
        return await rewrite_query_node(state, flash_llm)

    async def classify(state: ResearchState) -> dict:
        result = await classify_query_node(state, flash_llm)
        # Extract complexity for routing [S9]
        for msg in result.get("messages", []):
            if isinstance(msg, dict) and msg.get("type") == "classification":
                data = msg.get("data", {})
                complexity = data.get("complexity", "complex")
                # Map V2 complexity to routing values
                result["complexity"] = complexity
        return result

    async def plan(state: ResearchState) -> dict:
        result = await plan_research_node(state, flash_llm)
        step_feedback_count = sum(
            1 for m in state.get("messages", [])
            if isinstance(m, dict)
            and m.get("type") == "user_feedback"
            and m.get("step") == "plan"
        )
        result["iteration"] = step_feedback_count
        return result

    # [S9] Fast path nodes
    async def fast_path_search(state: ResearchState) -> dict:
        async with async_session_factory() as session:
            return await fast_path_search_node(
                state, llm, flash_llm, embedder, vector_store, reranker, session,
            )

    async def fast_path_synthesis(state: ResearchState) -> dict:
        return await fast_path_synthesis_node(state, flash_llm)

    # Worker dispatch via Send()
    # Map task_type → worker node name
    _WORKER_MAP = {
        "case_law": "case_law_worker",
        "named_case": "named_case_worker",
        "statute": "statute_worker",
        "constitution": "statute_worker",  # constitution uses same worker
        "ik_search": "ik_search_worker",
        "web": "web_search_worker",
        "graph": "graph_worker",
        "graph_community": "graph_community_worker",
    }

    def dispatch_workers(state: ResearchState) -> list[Send]:
        """Fan out to appropriate worker for each research task."""
        sends: list[Send] = []
        plan = state.get("research_plan", [])
        precomputed = state.get("precomputed_embeddings", {})

        for task in plan:
            task_type = task.get("task_type", "case_law")
            worker_name = _WORKER_MAP.get(task_type, "case_law_worker")

            # Check if required provider is available
            if worker_name == "ik_search_worker" and ik_client is None:
                worker_name = "case_law_worker"  # Fallback
            elif worker_name == "web_search_worker" and web_search is None:
                continue  # Skip web search if no provider
            elif worker_name in ("graph_worker", "graph_community_worker") and graph_store is None:
                continue  # Skip graph workers if no graph store

            payload = {
                "task": task,
                "precomputed_embeddings": precomputed,
            }

            # graph_community_worker needs parent state for case ID lookup
            if worker_name == "graph_community_worker":
                payload["parent_state"] = {
                    "worker_results": state.get("worker_results", []),
                }

            sends.append(Send(worker_name, payload))

        if not sends:
            # Fallback: at least one search with the original query
            sends.append(Send("case_law_worker", {
                "task": {
                    "task_id": "fallback",
                    "task_type": "case_law",
                    "nl_query": state.get("rewritten_query") or state["query"],
                    "boolean_query": "",
                    "named_cases": [],
                    "rationale": "Fallback search",
                    "filters": {},
                    "priority": 1,
                },
                "precomputed_embeddings": {},
            }))

        return sends

    async def gather(state: ResearchState) -> dict:
        return await gather_worker_results_node(state)

    async def batch_cot(state: ResearchState) -> dict:
        return await batch_worker_cot_with_reflection_node(state, flash_llm)

    async def evaluate_extract(state: ResearchState) -> dict:
        async with async_session_factory() as session:
            return await evaluate_and_extract_node(state, flash_llm, session)

    async def gap_analysis(state: ResearchState) -> dict:
        return await gap_analysis_node(state, flash_llm)

    async def synthesize(state: ResearchState) -> dict:
        return await synthesize_memo_node(state, llm)

    async def verify(state: ResearchState) -> dict:
        async with async_session_factory() as session:
            return await verify_citations_node(state, session)

    # Phase 4 nodes: speculative synthesis → format footnotes → verify v2 → quality check
    async def speculative_synthesis(state: ResearchState) -> dict:
        return await speculative_synthesis_with_contradictions_node(
            state, llm, flash_llm,
            stream_callback=None,  # Stream callback set by SSE layer
        )

    async def format_footnotes(state: ResearchState) -> dict:
        return await format_footnotes_node(state)

    async def verify_v2(state: ResearchState) -> dict:
        async with async_session_factory() as session:
            return await verify_citations_v2_node(
                state, session,
                graph_store=graph_store,
                ik_client=ik_client,
            )

    async def quality_check(state: ResearchState) -> dict:
        return await legal_quality_check_node(state, flash_llm)

    # -- Worker node wrappers (closures for Send) ---------------------------

    async def _case_law_worker(state: dict) -> dict:
        return await case_law_worker(state, llm, embedder, vector_store, reranker)

    async def _named_case_worker(state: dict) -> dict:
        return await named_case_worker(state, llm, embedder, vector_store, reranker)

    async def _statute_worker(state: dict) -> dict:
        return await statute_worker(state, embedder, vector_store)

    async def _ik_search_worker(state: dict) -> dict:
        return await ik_search_worker(state, ik_client)

    async def _web_search_worker(state: dict) -> dict:
        return await web_search_worker(state, web_search)

    async def _graph_worker(state: dict) -> dict:
        return await graph_worker(state, graph_store)

    async def _graph_community_worker(state: dict) -> dict:
        return await graph_community_worker(state, embedder, vector_store, graph_store)

    # -- Checkpoint nodes (HITL via interrupt) ------------------------------

    async def checkpoint_plan(state: ResearchState) -> dict:
        """Pause for user review of research plan."""
        research_plan = state.get("research_plan", [])
        response = interrupt({
            "question": (
                "I've created a research plan with "
                f"{len(research_plan)} tasks. "
                "Would you like to adjust it?"
            ),
            "sub_queries": state.get("sub_queries", []),
            "research_plan": [
                {
                    "task_type": t.get("task_type"),
                    "nl_query": t.get("nl_query"),
                    "rationale": t.get("rationale"),
                    "named_cases": t.get("named_cases", []),
                    "priority": t.get("priority"),
                }
                for t in research_plan
            ],
            "classification": next(
                (
                    m["data"]
                    for m in state.get("messages", [])
                    if isinstance(m, dict) and m.get("type") == "classification"
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
        worker_count = len(state.get("worker_results", []))
        gaps = state.get("evidence_gaps", [])

        response = interrupt({
            "question": (
                "Here are the search findings. "
                "Would you like to focus on any specific area?"
            ),
            "result_count": result_count,
            "worker_count": worker_count,
            "cross_references": state.get("cross_references", []),
            "evidence_gaps": [
                {"description": g.get("description"), "priority": g.get("priority")}
                for g in gaps
            ],
            "refinement_round": state.get("refinement_round", 0),
            "summary": (
                f"Found {result_count} results from {worker_count} workers, "
                f"{cross_ref_count} cross-references."
            ),
        })
        return {
            "messages": [
                {"type": "user_feedback", "step": "findings", "content": response}
            ],
        }

    checkpoint_memo = make_checkpoint_node(
        "memo",
        "Here is the draft research memo. Any revisions?",
        {"draft_memo": ("draft_memo", ""), "confidence": ("confidence", 0.0)},
    )

    # -- Routing functions --------------------------------------------------

    def route_by_complexity(state: ResearchState) -> str:
        """[S9] Route simple queries to fast path, complex to full pipeline."""
        complexity = state.get("complexity", "complex")
        if complexity == "simple":
            return "fast_path_search"
        return "plan_research"

    def should_refine(state: ResearchState) -> str:
        """Route after gap analysis: refine or proceed to findings."""
        if (
            state.get("evidence_gaps")
            and state.get("refinement_round", 0) < 2
        ):
            return "dispatch_workers"
        return "checkpoint_findings"

    def route_after_fast_path(state: ResearchState) -> str:
        """Handle fast path fallback to full pipeline."""
        if state.get("complexity") == "complex":
            return "plan_research"  # Fallback triggered
        return "fast_path_synthesis"

    # -- Register nodes -----------------------------------------------------

    # Parallel entry nodes [S2]
    graph.add_node("rewrite_query", rewrite)
    graph.add_node("classify", classify)

    # Full pipeline nodes
    graph.add_node("plan_research", plan)
    graph.add_node("checkpoint_plan", checkpoint_plan)
    graph.add_node("dispatch_workers", dispatch_workers)
    graph.add_node("case_law_worker", _case_law_worker)
    graph.add_node("named_case_worker", _named_case_worker)
    graph.add_node("statute_worker", _statute_worker)
    graph.add_node("ik_search_worker", _ik_search_worker)
    graph.add_node("web_search_worker", _web_search_worker)
    graph.add_node("graph_worker", _graph_worker)
    graph.add_node("graph_community_worker", _graph_community_worker)
    graph.add_node("gather_results", gather)
    graph.add_node("batch_cot_with_reflection", batch_cot)
    graph.add_node("evaluate_and_extract", evaluate_extract)
    graph.add_node("gap_analysis", gap_analysis)
    graph.add_node("checkpoint_findings", checkpoint_findings)
    graph.add_node("synthesize", synthesize)
    graph.add_node("verify", verify)
    # Phase 4 nodes
    graph.add_node("speculative_synthesis", speculative_synthesis)
    graph.add_node("format_footnotes", format_footnotes)
    graph.add_node("verify_v2", verify_v2)
    graph.add_node("quality_check", quality_check)
    graph.add_node("checkpoint_memo", checkpoint_memo)

    # Fast path nodes [S9]
    graph.add_node("fast_path_search", fast_path_search)
    graph.add_node("fast_path_synthesis", fast_path_synthesis)

    # -- Edges --------------------------------------------------------------

    # [S2] Parallel rewrite + classify from START
    graph.add_edge(START, "rewrite_query")
    graph.add_edge(START, "classify")

    # Both rewrite and classify feed into route_by_complexity
    # We need a join point — use classify as the routing node since
    # rewrite_query writes to rewritten_query (independent state key)
    graph.add_edge("rewrite_query", "classify")

    # [S9] Route by complexity
    graph.add_conditional_edges(
        "classify",
        route_by_complexity,
        {"fast_path_search": "fast_path_search", "plan_research": "plan_research"},
    )

    # Fast path [S9]
    graph.add_conditional_edges(
        "fast_path_search",
        route_after_fast_path,
        {"fast_path_synthesis": "fast_path_synthesis", "plan_research": "plan_research"},
    )
    graph.add_edge("fast_path_synthesis", "checkpoint_memo")

    # Full pipeline
    graph.add_edge("plan_research", "checkpoint_plan")
    graph.add_conditional_edges(
        "checkpoint_plan",
        route_after_plan,
        {
            "plan_research": "plan_research",
            "dispatch_workers": "dispatch_workers",
            END: END,
        },
    )

    # Workers fan out via Send(), results merge at gather_results
    graph.add_edge("case_law_worker", "gather_results")
    graph.add_edge("named_case_worker", "gather_results")
    graph.add_edge("statute_worker", "gather_results")
    graph.add_edge("ik_search_worker", "gather_results")
    graph.add_edge("web_search_worker", "gather_results")
    graph.add_edge("graph_worker", "gather_results")
    graph.add_edge("graph_community_worker", "gather_results")

    # Post-gather pipeline
    graph.add_edge("gather_results", "batch_cot_with_reflection")
    graph.add_edge("batch_cot_with_reflection", "evaluate_and_extract")
    graph.add_edge("evaluate_and_extract", "gap_analysis")

    # Gap analysis loop (max 2 rounds)
    graph.add_conditional_edges(
        "gap_analysis",
        should_refine,
        {
            "dispatch_workers": "dispatch_workers",
            "checkpoint_findings": "checkpoint_findings",
        },
    )

    # Post-findings — route to speculative synthesis (Phase 4) instead of old synthesize
    graph.add_conditional_edges(
        "checkpoint_findings",
        route_after_findings,
        {
            "dispatch_workers": "dispatch_workers",
            "synthesize": "speculative_synthesis",
            END: END,
        },
    )

    # Phase 4 pipeline: speculative synthesis → format footnotes → verify → quality → memo
    graph.add_edge("speculative_synthesis", "format_footnotes")
    graph.add_edge("format_footnotes", "verify_v2")
    graph.add_edge("verify_v2", "quality_check")
    graph.add_edge("quality_check", "checkpoint_memo")

    graph.add_conditional_edges(
        "checkpoint_memo",
        route_after_memo,
        {"synthesize": "speculative_synthesis", END: END},
    )

    # -- Compile ------------------------------------------------------------

    return compile_graph(graph, checkpointer)
