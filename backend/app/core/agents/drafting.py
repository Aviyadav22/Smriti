"""Drafting Agent LangGraph graph.

Builds a compiled LangGraph state graph that resolves a document template,
gathers statutory provisions, verifies precedents, drafts sections, assembles
the full document, and supports iterative revision -- with HITL checkpoints
at key decision points.

Graph flow:
  START -> [parse_opposing_doc (if opposing text)] -> resolve_template ->
  gather_provisions -> verify_precedents -> checkpoint_sources ->
  draft_sections -> assemble -> checkpoint_draft ->
  verify_final -> checkpoint_final -> END

With a conditional revise branch from checkpoint_draft:
  checkpoint_draft --(feedback)--> revise_section -> assemble -> checkpoint_draft
  checkpoint_draft --(approved)--> verify_final
"""
from __future__ import annotations

import logging
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.core.agents.nodes.drafting_nodes import (
    assemble_document_node,
    draft_sections_node,
    gather_provisions_node,
    generate_affidavit_node,
    parse_opposing_document_node,
    resolve_template_node,
    revise_section_node,
    verify_final_node,
    verify_precedents_node,
)
from app.core.agents.routing_utils import compile_graph, make_checkpoint_node, make_feedback_router
from app.core.agents.state import DraftingState
from app.db.postgres import async_session_factory

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Router functions (module-level for testability)
# ---------------------------------------------------------------------------


def route_after_start(state: DraftingState) -> str:
    """Route: if opposing_document_text is present, parse it first."""
    if state.get("opposing_document_text"):
        return "parse_opposing_doc"
    return "resolve_template"


def route_after_template(state: DraftingState) -> str:
    """Route after template resolution.

    If an error was set (e.g. unknown doc_type), skip straight to END
    so the user sees the error message instead of empty results.
    """
    if state.get("error"):
        return END
    return "gather_provisions"


route_after_sources = make_feedback_router("sources", "gather_provisions", "draft_sections", check_error=True)
route_after_draft = make_feedback_router("draft", "revise_section", "verify_final", check_error=True)
route_after_final = make_feedback_router("final", "revise_section", check_error=True)


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------


def build_drafting_graph(
    *,
    llm: Any,
    flash_llm: Any,
    embedder: Any,
    vector_store: Any,
    reranker: Any,
    checkpointer: Any | None = None,
    graph_store: Any | None = None,
) -> Any:
    """Build and compile the Drafting Agent LangGraph graph.

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
    checkpointer:
        LangGraph checkpointer for persistence.  Can be ``None`` for
        unit testing (graph compiles without a checkpointer).

    Returns
    -------
    Compiled LangGraph state graph.
    """
    graph = StateGraph(DraftingState)

    # -- Node wrappers (closures capturing dependencies) --------------------
    # DB-accessing nodes create fresh sessions via async_session_factory()
    # because the FastAPI Depends(get_db) session closes before the
    # StreamingResponse generator runs.

    async def parse_opposing_doc(state: DraftingState) -> dict:
        return await parse_opposing_document_node(state, llm)

    async def resolve_template(state: DraftingState) -> dict:
        return await resolve_template_node(state)

    async def gather_provisions(state: DraftingState) -> dict:
        async with async_session_factory() as session:
            result = await gather_provisions_node(state, llm, session, graph_store)
        # Count feedback messages for THIS step only (not shared across checkpoints)
        step_feedback_count = sum(
            1 for m in state.get("messages", [])
            if isinstance(m, dict) and m.get("type") == "user_feedback" and m.get("step") == "sources"
        )
        result["iteration"] = step_feedback_count
        return result

    async def verify_precedents(state: DraftingState) -> dict:
        async with async_session_factory() as session:
            return await verify_precedents_node(state, session, graph_store)

    async def draft_sections(state: DraftingState) -> dict:
        return await draft_sections_node(state, llm, vector_store, embedder)

    async def assemble(state: DraftingState) -> dict:
        result = await assemble_document_node(state, llm)
        # V2: Generate companion affidavit if required
        merged_state = {**state, **result}
        affidavit_result = await generate_affidavit_node(merged_state, llm)
        result.update(affidavit_result)
        return result

    async def revise_section(state: DraftingState) -> dict:
        result = await revise_section_node(state, llm)
        # Count feedback messages for THIS step only (not shared across checkpoints)
        step_feedback_count = sum(
            1 for m in state.get("messages", [])
            if isinstance(m, dict) and m.get("type") == "user_feedback" and m.get("step") == "draft"
        )
        result["iteration"] = step_feedback_count
        return result

    async def verify_final(state: DraftingState) -> dict:
        async with async_session_factory() as session:
            return await verify_final_node(state, session)

    # -- Checkpoint nodes (HITL via interrupt) ------------------------------

    checkpoint_sources = make_checkpoint_node(
        "sources",
        "Here are the verified precedents and statutory provisions. Would you like to adjust?",
        {"verified_precedents": ("verified_precedents", []), "statutory_provisions": ("statutory_provisions", [])},
    )

    checkpoint_draft = make_checkpoint_node(
        "draft",
        "Here is the draft document. Would you like to revise any section?",
        {"full_draft": ("full_draft", ""), "section_drafts": ("section_drafts", {})},
        extra_return=lambda response: {"revision_feedback": response},
    )

    checkpoint_final = make_checkpoint_node(
        "final",
        "Final review. Ready to export?",
        {"full_draft": ("full_draft", "")},
    )

    # -- Register nodes -----------------------------------------------------

    graph.add_node("parse_opposing_doc", parse_opposing_doc)
    graph.add_node("resolve_template", resolve_template)
    graph.add_node("gather_provisions", gather_provisions)
    graph.add_node("verify_precedents", verify_precedents)
    graph.add_node("checkpoint_sources", checkpoint_sources)
    graph.add_node("draft_sections", draft_sections)
    graph.add_node("assemble", assemble)
    graph.add_node("checkpoint_draft", checkpoint_draft)
    graph.add_node("revise_section", revise_section)
    graph.add_node("verify_final", verify_final)
    graph.add_node("checkpoint_final", checkpoint_final)

    # -- Edges --------------------------------------------------------------

    graph.add_conditional_edges(
        START,
        route_after_start,
        {"parse_opposing_doc": "parse_opposing_doc", "resolve_template": "resolve_template"},
    )
    graph.add_edge("parse_opposing_doc", "resolve_template")

    graph.add_conditional_edges(
        "resolve_template",
        route_after_template,
        {"gather_provisions": "gather_provisions", END: END},
    )

    graph.add_edge("gather_provisions", "verify_precedents")
    graph.add_edge("verify_precedents", "checkpoint_sources")

    graph.add_conditional_edges(
        "checkpoint_sources",
        route_after_sources,
        {
            "gather_provisions": "gather_provisions",
            "draft_sections": "draft_sections",
            END: END,
        },
    )

    graph.add_edge("draft_sections", "assemble")
    graph.add_edge("assemble", "checkpoint_draft")

    graph.add_conditional_edges(
        "checkpoint_draft",
        route_after_draft,
        {"revise_section": "revise_section", "verify_final": "verify_final", END: END},
    )

    graph.add_edge("revise_section", "assemble")

    graph.add_edge("verify_final", "checkpoint_final")

    graph.add_conditional_edges(
        "checkpoint_final",
        route_after_final,
        {"revise_section": "revise_section", END: END},
    )

    # -- Compile ------------------------------------------------------------

    return compile_graph(graph, checkpointer)
