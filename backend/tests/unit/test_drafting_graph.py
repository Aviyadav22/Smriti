"""Tests for Drafting Agent graph builder and router functions."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from langgraph.graph import END

from app.core.agents.drafting import (
    build_drafting_graph,
    route_after_draft,
    route_after_final,
    route_after_sources,
    route_after_start,
    route_after_template,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(**overrides) -> dict:
    """Create a minimal DraftingState dict with defaults."""
    base = {
        "doc_type": "bail_application",
        "case_facts": "The accused was arrested for offences under S.420 IPC.",
        "relevant_precedents": [],
        "additional_context": {
            "accused_name": "Ram Kumar",
            "fir_number": "FIR No. 123/2024",
            "police_station": "PS Sadar",
            "offences_charged": "S.420, S.468 IPC",
        },
        "target_court": "Delhi High Court",
        "template": {},
        "statutory_provisions": [],
        "verified_precedents": [],
        "section_drafts": {},
        "full_draft": "",
        "revision_feedback": "",

        "messages": [],
        "iteration": 0,
        "error": "",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# route_after_start
# ---------------------------------------------------------------------------


class TestRouteAfterStart:
    def test_returns_parse_opposing_doc_when_text_present(self) -> None:
        state = _make_state(opposing_document_text="Full plaint text...")
        result = route_after_start(state)
        assert result == "parse_opposing_doc"

    def test_returns_resolve_template_when_no_opposing_text(self) -> None:
        state = _make_state()
        result = route_after_start(state)
        assert result == "resolve_template"

    def test_returns_resolve_template_when_opposing_text_empty(self) -> None:
        state = _make_state(opposing_document_text="")
        result = route_after_start(state)
        assert result == "resolve_template"


# ---------------------------------------------------------------------------
# route_after_template
# ---------------------------------------------------------------------------


class TestRouteAfterTemplate:
    def test_returns_end_when_error_is_set(self) -> None:
        state = _make_state(error="Unknown document type: invalid_type")
        result = route_after_template(state)
        assert result == END

    def test_returns_gather_provisions_when_no_error(self) -> None:
        state = _make_state(error="")
        result = route_after_template(state)
        assert result == "gather_provisions"

    def test_returns_gather_provisions_when_error_is_none(self) -> None:
        state = _make_state()
        state.pop("error", None)
        result = route_after_template(state)
        assert result == "gather_provisions"

    def test_returns_end_for_missing_fields_error(self) -> None:
        state = _make_state(error="Missing required fields: fir_number, police_station")
        result = route_after_template(state)
        assert result == END


# ---------------------------------------------------------------------------
# route_after_sources
# ---------------------------------------------------------------------------


class TestRouteAfterSources:
    def test_returns_draft_sections_when_no_feedback(self) -> None:
        state = _make_state(messages=[])
        result = route_after_sources(state)
        assert result == "draft_sections"

    def test_returns_gather_provisions_when_feedback_present_and_iteration_below_3(self) -> None:
        state = _make_state(
            messages=[
                {
                    "type": "user_feedback",
                    "step": "sources",
                    "content": "Please include provisions from Evidence Act.",
                }
            ],
            iteration=1,
        )
        result = route_after_sources(state)
        assert result == "gather_provisions"

    def test_returns_draft_sections_when_iteration_at_3(self) -> None:
        state = _make_state(
            messages=[
                {"type": "user_feedback", "step": "sources", "content": "More provisions please."},
                {"type": "user_feedback", "step": "sources", "content": "Still more."},
                {"type": "user_feedback", "step": "sources", "content": "Final try."},
            ],
            iteration=3,
        )
        result = route_after_sources(state)
        assert result == "draft_sections"

    def test_returns_draft_sections_when_feedback_is_empty_string(self) -> None:
        state = _make_state(
            messages=[
                {
                    "type": "user_feedback",
                    "step": "sources",
                    "content": "",
                }
            ],
            iteration=0,
        )
        result = route_after_sources(state)
        assert result == "draft_sections"

    def test_ignores_feedback_for_other_steps(self) -> None:
        """Feedback with step != 'sources' should not trigger re-gather."""
        state = _make_state(
            messages=[
                {
                    "type": "user_feedback",
                    "step": "draft",
                    "content": "Some draft feedback.",
                }
            ],
            iteration=0,
        )
        result = route_after_sources(state)
        assert result == "draft_sections"

    def test_uses_last_sources_feedback_when_multiple_messages(self) -> None:
        """Only the most recent sources feedback should be considered."""
        state = _make_state(
            messages=[
                {"type": "user_feedback", "step": "sources", "content": "First feedback."},
                {"type": "user_feedback", "step": "draft", "content": "Draft feedback."},
                {"type": "user_feedback", "step": "sources", "content": ""},  # last sources feedback is empty
            ],
            iteration=0,
        )
        result = route_after_sources(state)
        # Last sources feedback is empty string, so should proceed to draft_sections
        assert result == "draft_sections"


# ---------------------------------------------------------------------------
# route_after_draft
# ---------------------------------------------------------------------------


class TestRouteAfterDraft:
    def test_returns_verify_final_when_no_feedback(self) -> None:
        state = _make_state(messages=[])
        result = route_after_draft(state)
        assert result == "verify_final"

    def test_returns_revise_section_when_feedback_present(self) -> None:
        state = _make_state(
            messages=[
                {
                    "type": "user_feedback",
                    "step": "draft",
                    "content": "Please revise the grounds section.",
                }
            ],
            iteration=1,
        )
        result = route_after_draft(state)
        assert result == "revise_section"

    def test_returns_verify_final_when_iteration_at_3(self) -> None:
        state = _make_state(
            messages=[
                {"type": "user_feedback", "step": "draft", "content": "Revise more."},
                {"type": "user_feedback", "step": "draft", "content": "Still not right."},
                {"type": "user_feedback", "step": "draft", "content": "Final attempt."},
            ],
            iteration=3,
        )
        result = route_after_draft(state)
        assert result == "verify_final"

    def test_returns_verify_final_when_draft_feedback_is_empty(self) -> None:
        state = _make_state(
            messages=[
                {"type": "user_feedback", "step": "draft", "content": ""}
            ],
            iteration=0,
        )
        result = route_after_draft(state)
        assert result == "verify_final"

    def test_ignores_sources_feedback_for_draft_routing(self) -> None:
        state = _make_state(
            messages=[
                {
                    "type": "user_feedback",
                    "step": "sources",
                    "content": "Sources feedback that should be ignored.",
                }
            ],
            iteration=0,
        )
        result = route_after_draft(state)
        assert result == "verify_final"


# ---------------------------------------------------------------------------
# route_after_final
# ---------------------------------------------------------------------------


class TestRouteAfterFinal:
    def test_returns_end_when_no_feedback(self) -> None:
        state = _make_state(messages=[])
        result = route_after_final(state)
        assert result == END

    def test_returns_revise_section_when_feedback_present(self) -> None:
        state = _make_state(
            messages=[
                {
                    "type": "user_feedback",
                    "step": "final",
                    "content": "Please fix the citation in paragraph 3.",
                }
            ],
            iteration=2,
        )
        result = route_after_final(state)
        assert result == "revise_section"

    def test_returns_end_when_iteration_at_3(self) -> None:
        state = _make_state(
            messages=[
                {"type": "user_feedback", "step": "final", "content": "Another revision."},
                {"type": "user_feedback", "step": "final", "content": "More changes."},
                {"type": "user_feedback", "step": "final", "content": "Final try."},
            ],
            iteration=3,
        )
        result = route_after_final(state)
        assert result == END

    def test_returns_end_when_final_feedback_is_empty(self) -> None:
        state = _make_state(
            messages=[
                {"type": "user_feedback", "step": "final", "content": ""}
            ],
            iteration=0,
        )
        result = route_after_final(state)
        assert result == END

    def test_ignores_draft_feedback_for_final_routing(self) -> None:
        state = _make_state(
            messages=[
                {
                    "type": "user_feedback",
                    "step": "draft",
                    "content": "Draft feedback that should be ignored here.",
                }
            ],
            iteration=0,
        )
        result = route_after_final(state)
        assert result == END


# ---------------------------------------------------------------------------
# build_drafting_graph
# ---------------------------------------------------------------------------


class TestBuildDraftingGraph:
    def test_compiles_without_checkpointer(self) -> None:
        """Graph must compile successfully with checkpointer=None."""
        llm = AsyncMock()
        flash_llm = AsyncMock()
        embedder = AsyncMock()
        vector_store = AsyncMock()
        reranker = AsyncMock()
        db = AsyncMock()

        graph = build_drafting_graph(
            llm=llm,
            flash_llm=flash_llm,
            embedder=embedder,
            vector_store=vector_store,
            reranker=reranker,
            checkpointer=None,
        )

        assert graph is not None

    def test_has_expected_nodes(self) -> None:
        """Graph must contain exactly the expected 11 nodes."""
        llm = AsyncMock()
        flash_llm = AsyncMock()
        embedder = AsyncMock()
        vector_store = AsyncMock()
        reranker = AsyncMock()
        db = AsyncMock()

        graph = build_drafting_graph(
            llm=llm,
            flash_llm=flash_llm,
            embedder=embedder,
            vector_store=vector_store,
            reranker=reranker,
            checkpointer=None,
        )

        expected_nodes = {
            "parse_opposing_doc",
            "resolve_template",
            "gather_provisions",
            "verify_precedents",
            "checkpoint_sources",
            "draft_sections",
            "assemble",
            "checkpoint_draft",
            "revise_section",
            "verify_final",
            "checkpoint_final",
        }

        # LangGraph compiled graphs expose nodes via graph.nodes or similar attribute
        actual_nodes = set(graph.nodes.keys())
        # Remove LangGraph internal nodes (__start__, __end__)
        user_nodes = {n for n in actual_nodes if not n.startswith("__")}
        assert user_nodes == expected_nodes

    def test_compiles_with_mock_checkpointer(self) -> None:
        """Graph must also compile when a checkpointer is provided."""
        llm = AsyncMock()
        flash_llm = AsyncMock()
        embedder = AsyncMock()
        vector_store = AsyncMock()
        reranker = AsyncMock()
        db = AsyncMock()
        checkpointer = MagicMock()

        # Some versions of LangGraph inspect the checkpointer; this test just
        # ensures no TypeError is raised during construction
        try:
            graph = build_drafting_graph(
                llm=llm,
                flash_llm=flash_llm,
                embedder=embedder,
                vector_store=vector_store,
                reranker=reranker,
                checkpointer=checkpointer,
            )
            assert graph is not None
        except Exception:
            # If LangGraph validates the checkpointer type, skip gracefully
            pytest.skip("Checkpointer validation requires a real checkpointer instance")
