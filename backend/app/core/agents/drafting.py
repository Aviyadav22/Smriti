"""Drafting Agent LangGraph graph.

Builds a compiled LangGraph state graph that resolves a document template,
gathers statutory provisions, verifies precedents, drafts sections, assembles
the full document, and supports iterative revision -- with HITL checkpoints
at key decision points.

Graph flow:
  START -> resolve_template -> gather_provisions -> verify_precedents ->
  checkpoint_sources -> draft_sections -> assemble -> checkpoint_draft ->
  verify_final -> checkpoint_final -> END

With a conditional revise branch from checkpoint_draft:
  checkpoint_draft --(feedback)--> revise_section -> assemble -> checkpoint_draft
  checkpoint_draft --(approved)--> verify_final
"""
from __future__ import annotations

import logging
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from app.core.agents.nodes.drafting_nodes import (
    assemble_document_node,
    draft_sections_node,
    gather_provisions_node,
    resolve_template_node,
    revise_section_node,
    verify_final_node,
    verify_precedents_node,
)
from app.core.agents.state import DraftingState

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Router functions (module-level for testability)
# ---------------------------------------------------------------------------


def route_after_template(state: DraftingState) -> str:
    """Route after template resolution.

    If an error was set (e.g. unknown doc_type), skip straight to END
    so the user sees the error message instead of empty results.
    """
    if state.get("error"):
        return END
    return "gather_provisions"


def route_after_sources(state: DraftingState) -> str:
    """Route after sources checkpoint.

    If the user provided feedback and we haven't exceeded the max iteration
    count, loop back to gather_provisions. Otherwise proceed to draft_sections.
    """
    messages = state.get("messages", [])
    last_feedback = next(
        (
            m
            for m in reversed(messages)
            if m.get("type") == "user_feedback" and m.get("step") == "sources"
        ),
        None,
    )
    if (
        last_feedback
        and last_feedback.get("content")
        and state.get("iteration", 0) < 3
    ):
        return "gather_provisions"
    return "draft_sections"


def route_after_draft(state: DraftingState) -> str:
    """Route after draft checkpoint.

    If the user provided feedback (revision instructions), route to
    revise_section. Otherwise proceed to verify_final.
    """
    messages = state.get("messages", [])
    last_feedback = next(
        (
            m
            for m in reversed(messages)
            if m.get("type") == "user_feedback" and m.get("step") == "draft"
        ),
        None,
    )
    if (
        last_feedback
        and last_feedback.get("content")
        and state.get("iteration", 0) < 3
    ):
        return "revise_section"
    return "verify_final"


def route_after_final(state: DraftingState) -> str:
    """Route after final checkpoint.

    If the user provided feedback and we haven't exceeded the max iteration
    count, loop back to revise_section for another round. Otherwise END.
    """
    messages = state.get("messages", [])
    last_feedback = next(
        (
            m
            for m in reversed(messages)
            if m.get("type") == "user_feedback" and m.get("step") == "final"
        ),
        None,
    )
    if (
        last_feedback
        and last_feedback.get("content")
        and state.get("iteration", 0) < 3
    ):
        return "revise_section"
    return END


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
    db: Any,
    checkpointer: Any | None = None,
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
    db:
        Async database session for SQL queries.
    checkpointer:
        LangGraph checkpointer for persistence.  Can be ``None`` for
        unit testing (graph compiles without a checkpointer).

    Returns
    -------
    Compiled LangGraph state graph.
    """
    graph = StateGraph(DraftingState)

    # -- Node wrappers (closures capturing dependencies) --------------------

    async def resolve_template(state: DraftingState) -> dict:
        return await resolve_template_node(state)

    async def gather_provisions(state: DraftingState) -> dict:
        result = await gather_provisions_node(state, llm, db)
        # Always increment iteration counter
        result["iteration"] = state.get("iteration", 0) + 1
        return result

    async def verify_precedents(state: DraftingState) -> dict:
        return await verify_precedents_node(state, db)

    async def draft_sections(state: DraftingState) -> dict:
        return await draft_sections_node(state, llm)

    async def assemble(state: DraftingState) -> dict:
        return await assemble_document_node(state, llm)

    async def revise_section(state: DraftingState) -> dict:
        result = await revise_section_node(state, llm)
        result["iteration"] = state.get("iteration", 0) + 1
        return result

    async def verify_final(state: DraftingState) -> dict:
        return await verify_final_node(state, db)

    # -- Checkpoint nodes (HITL via interrupt) ------------------------------

    async def checkpoint_sources(state: DraftingState) -> dict:
        """Pause for user review of verified precedents and provisions."""
        response = interrupt({
            "question": (
                "Here are the verified precedents and statutory provisions. "
                "Would you like to adjust?"
            ),
            "verified_precedents": state.get("verified_precedents", []),
            "statutory_provisions": state.get("statutory_provisions", []),
        })
        return {
            "messages": [
                {
                    "type": "user_feedback",
                    "step": "sources",
                    "content": response,
                }
            ],
        }

    async def checkpoint_draft(state: DraftingState) -> dict:
        """Pause for user review of the assembled draft document."""
        response = interrupt({
            "question": (
                "Here is the draft document. "
                "Would you like to revise any section?"
            ),
            "full_draft": state.get("full_draft", ""),
            "section_drafts": state.get("section_drafts", {}),
        })
        return {
            "messages": [
                {
                    "type": "user_feedback",
                    "step": "draft",
                    "content": response,
                }
            ],
            "revision_feedback": response,
        }

    async def checkpoint_final(state: DraftingState) -> dict:
        """Pause for final review before export."""
        response = interrupt({
            "question": "Final review. Ready to export?",
            "full_draft": state.get("full_draft", ""),
        })
        return {
            "messages": [
                {"type": "user_feedback", "step": "final", "content": response}
            ],
        }

    # -- Register nodes -----------------------------------------------------

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

    graph.add_edge(START, "resolve_template")

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
        },
    )

    graph.add_edge("draft_sections", "assemble")
    graph.add_edge("assemble", "checkpoint_draft")

    graph.add_conditional_edges(
        "checkpoint_draft",
        route_after_draft,
        {"revise_section": "revise_section", "verify_final": "verify_final"},
    )

    graph.add_edge("revise_section", "assemble")

    graph.add_edge("verify_final", "checkpoint_final")

    graph.add_conditional_edges(
        "checkpoint_final",
        route_after_final,
        {"revise_section": "revise_section", END: END},
    )

    # -- Compile ------------------------------------------------------------

    compile_kwargs: dict[str, Any] = {}
    if checkpointer is not None:
        compile_kwargs["checkpointer"] = checkpointer

    return graph.compile(**compile_kwargs)
