"""Tests for the Research Agent LangGraph graph."""
from __future__ import annotations

import pytest

from app.core.agents.research import (
    build_research_graph,
    route_after_findings,
    route_after_memo,
    route_after_plan,
)
from app.core.agents.state import ResearchState
from langgraph.graph import END


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _base_state(**overrides: object) -> ResearchState:
    """Return a minimal valid ResearchState with optional overrides."""
    state: dict = {
        "query": "test query",
        "sub_queries": [],
        "search_results": [],
        "cross_references": [],
        "contradictions": [],
        "draft_memo": "",
        "confidence": 0.0,
        "messages": [],
        "iteration": 0,
    }
    state.update(overrides)
    return state  # type: ignore[return-value]


def _build_graph():
    """Build a graph with dummy dependencies (no checkpointer)."""
    return build_research_graph(
        llm=object(),
        flash_llm=object(),
        embedder=object(),
        vector_store=object(),
        reranker=object(),
        db=object(),
        checkpointer=None,
    )


# ---------------------------------------------------------------------------
# Graph construction tests
# ---------------------------------------------------------------------------

EXPECTED_NODES = {
    "classify",
    "decompose",
    "checkpoint_plan",
    "search",
    "gather",
    "contradictions",
    "checkpoint_findings",
    "synthesize",
    "verify",
    "checkpoint_memo",
}


class TestBuildResearchGraph:
    def test_build_research_graph_returns_compiled(self) -> None:
        compiled = _build_graph()
        # A compiled graph has an invoke method
        assert hasattr(compiled, "invoke")
        assert callable(compiled.invoke)

    def test_graph_has_expected_nodes(self) -> None:
        compiled = _build_graph()
        # The compiled graph exposes node names via .get_graph().nodes
        graph_nodes = set(compiled.get_graph().nodes.keys())
        # LangGraph adds __start__ and __end__ nodes
        for node_name in EXPECTED_NODES:
            assert node_name in graph_nodes, f"Missing node: {node_name}"

    def test_initial_state_structure(self) -> None:
        """Verify that a valid initial state can be constructed."""
        state = _base_state()
        assert state["query"] == "test query"
        assert state["iteration"] == 0
        assert state["messages"] == []


# ---------------------------------------------------------------------------
# route_after_plan tests
# ---------------------------------------------------------------------------


class TestRouteAfterPlan:
    def test_continues_without_feedback(self) -> None:
        state = _base_state()
        assert route_after_plan(state) == "search"

    def test_continues_with_empty_feedback(self) -> None:
        state = _base_state(
            messages=[{"type": "user_feedback", "step": "plan", "content": ""}],
        )
        assert route_after_plan(state) == "search"

    def test_loops_with_feedback(self) -> None:
        state = _base_state(
            messages=[
                {"type": "user_feedback", "step": "plan", "content": "Add more"},
            ],
            iteration=0,
        )
        assert route_after_plan(state) == "decompose"

    def test_loops_with_feedback_iteration_2(self) -> None:
        state = _base_state(
            messages=[
                {"type": "user_feedback", "step": "plan", "content": "Refine"},
            ],
            iteration=2,
        )
        assert route_after_plan(state) == "decompose"

    def test_stops_at_max_iterations(self) -> None:
        state = _base_state(
            messages=[
                {"type": "user_feedback", "step": "plan", "content": "More"},
            ],
            iteration=3,
        )
        assert route_after_plan(state) == "search"

    def test_ignores_feedback_for_other_steps(self) -> None:
        state = _base_state(
            messages=[
                {"type": "user_feedback", "step": "findings", "content": "Focus"},
            ],
            iteration=0,
        )
        assert route_after_plan(state) == "search"


# ---------------------------------------------------------------------------
# route_after_findings tests
# ---------------------------------------------------------------------------


class TestRouteAfterFindings:
    def test_continues_without_feedback(self) -> None:
        state = _base_state()
        assert route_after_findings(state) == "synthesize"

    def test_continues_with_empty_feedback(self) -> None:
        state = _base_state(
            messages=[
                {"type": "user_feedback", "step": "findings", "content": ""},
            ],
        )
        assert route_after_findings(state) == "synthesize"

    def test_loops_with_feedback(self) -> None:
        state = _base_state(
            messages=[
                {
                    "type": "user_feedback",
                    "step": "findings",
                    "content": "Focus on Art 21",
                },
            ],
            iteration=0,
        )
        assert route_after_findings(state) == "search"

    def test_stops_at_max_iterations(self) -> None:
        state = _base_state(
            messages=[
                {"type": "user_feedback", "step": "findings", "content": "More"},
            ],
            iteration=3,
        )
        assert route_after_findings(state) == "synthesize"

    def test_ignores_feedback_for_other_steps(self) -> None:
        state = _base_state(
            messages=[
                {"type": "user_feedback", "step": "plan", "content": "Change"},
            ],
            iteration=0,
        )
        assert route_after_findings(state) == "synthesize"


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
        assert route_after_memo(state) == "synthesize"

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
                {"type": "user_feedback", "step": "findings", "content": "Focus"},
            ],
            iteration=0,
        )
        assert route_after_memo(state) == END
