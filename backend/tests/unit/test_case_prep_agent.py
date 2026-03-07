"""Tests for the Case Prep Agent LangGraph graph."""
from __future__ import annotations

import pytest

from app.core.agents.case_prep import (
    build_case_prep_graph,
    route_after_issues,
    route_after_memo,
    route_after_strategy,
)
from app.core.agents.state import CasePrepState
from langgraph.graph import END


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _base_state(**overrides: object) -> CasePrepState:
    """Return a minimal valid CasePrepState with optional overrides."""
    state: dict = {
        "document_id": "doc-001",
        "analysis": {},
        "prioritized_issues": [],
        "argument_order": [],
        "strategy_points": [],
        "enhanced_memo": "",
        "messages": [],
        "iteration": 0,
    }
    state.update(overrides)
    return state  # type: ignore[return-value]


def _build_graph():
    """Build a graph with dummy dependencies (no checkpointer)."""
    return build_case_prep_graph(
        llm=object(),
        flash_llm=object(),
        embedder=object(),
        vector_store=object(),
        reranker=object(),
        graph_store=object(),
        db=object(),
        checkpointer=None,
    )


# ---------------------------------------------------------------------------
# Graph construction tests
# ---------------------------------------------------------------------------

EXPECTED_NODES = {
    "load_analysis",
    "prioritize",
    "checkpoint_issues",
    "deep_search",
    "argument_order",
    "checkpoint_strategy",
    "strategy_memo",
    "verify",
    "checkpoint_memo",
}


class TestBuildCasePrepGraph:
    def test_build_case_prep_graph_returns_compiled(self) -> None:
        compiled = _build_graph()
        assert hasattr(compiled, "invoke")
        assert callable(compiled.invoke)

    def test_graph_has_expected_nodes(self) -> None:
        compiled = _build_graph()
        graph_nodes = set(compiled.get_graph().nodes.keys())
        for node_name in EXPECTED_NODES:
            assert node_name in graph_nodes, f"Missing node: {node_name}"

    def test_initial_state_structure(self) -> None:
        """Verify that a valid initial state can be constructed."""
        state = _base_state()
        assert state["document_id"] == "doc-001"
        assert state["iteration"] == 0
        assert state["messages"] == []


# ---------------------------------------------------------------------------
# route_after_issues tests
# ---------------------------------------------------------------------------


class TestRouteAfterIssues:
    def test_continues_without_feedback(self) -> None:
        state = _base_state()
        assert route_after_issues(state) == "deep_search"

    def test_continues_with_empty_feedback(self) -> None:
        state = _base_state(
            messages=[{"type": "user_feedback", "step": "issues", "content": ""}],
        )
        assert route_after_issues(state) == "deep_search"

    def test_loops_with_feedback(self) -> None:
        state = _base_state(
            messages=[
                {"type": "user_feedback", "step": "issues", "content": "Reorder"},
            ],
            iteration=0,
        )
        assert route_after_issues(state) == "prioritize"

    def test_loops_with_feedback_iteration_2(self) -> None:
        state = _base_state(
            messages=[
                {"type": "user_feedback", "step": "issues", "content": "Drop issue 3"},
            ],
            iteration=2,
        )
        assert route_after_issues(state) == "prioritize"

    def test_stops_at_max_iterations(self) -> None:
        state = _base_state(
            messages=[
                {"type": "user_feedback", "step": "issues", "content": "More"},
            ],
            iteration=3,
        )
        assert route_after_issues(state) == "deep_search"

    def test_ignores_feedback_for_other_steps(self) -> None:
        state = _base_state(
            messages=[
                {"type": "user_feedback", "step": "strategy", "content": "Change"},
            ],
            iteration=0,
        )
        assert route_after_issues(state) == "deep_search"


# ---------------------------------------------------------------------------
# route_after_strategy tests
# ---------------------------------------------------------------------------


class TestRouteAfterStrategy:
    def test_continues_without_feedback(self) -> None:
        state = _base_state()
        assert route_after_strategy(state) == "strategy_memo"

    def test_continues_with_empty_feedback(self) -> None:
        state = _base_state(
            messages=[
                {"type": "user_feedback", "step": "strategy", "content": ""},
            ],
        )
        assert route_after_strategy(state) == "strategy_memo"

    def test_loops_with_feedback(self) -> None:
        state = _base_state(
            messages=[
                {
                    "type": "user_feedback",
                    "step": "strategy",
                    "content": "Lead with jurisdiction",
                },
            ],
            iteration=0,
        )
        assert route_after_strategy(state) == "argument_order"

    def test_stops_at_max_iterations(self) -> None:
        state = _base_state(
            messages=[
                {"type": "user_feedback", "step": "strategy", "content": "Adjust"},
            ],
            iteration=3,
        )
        assert route_after_strategy(state) == "strategy_memo"

    def test_ignores_feedback_for_other_steps(self) -> None:
        state = _base_state(
            messages=[
                {"type": "user_feedback", "step": "issues", "content": "Change"},
            ],
            iteration=0,
        )
        assert route_after_strategy(state) == "strategy_memo"


# ---------------------------------------------------------------------------
# route_after_memo tests
# ---------------------------------------------------------------------------


class TestRouteAfterMemo:
    def test_continues_without_feedback(self) -> None:
        state = _base_state()
        assert route_after_memo(state) == END

    def test_continues_with_empty_feedback(self) -> None:
        state = _base_state(
            messages=[
                {"type": "user_feedback", "step": "memo", "content": ""},
            ],
        )
        assert route_after_memo(state) == END

    def test_loops_with_feedback(self) -> None:
        state = _base_state(
            messages=[
                {
                    "type": "user_feedback",
                    "step": "memo",
                    "content": "Add more citations",
                },
            ],
            iteration=0,
        )
        assert route_after_memo(state) == "strategy_memo"

    def test_stops_at_max_iterations(self) -> None:
        state = _base_state(
            messages=[
                {"type": "user_feedback", "step": "memo", "content": "Revise"},
            ],
            iteration=3,
        )
        assert route_after_memo(state) == END

    def test_ignores_feedback_for_other_steps(self) -> None:
        state = _base_state(
            messages=[
                {"type": "user_feedback", "step": "strategy", "content": "Focus"},
            ],
            iteration=0,
        )
        assert route_after_memo(state) == END
