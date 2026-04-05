"""Tests for Strategy Agent graph builder and router functions."""
from __future__ import annotations

import pytest

from langgraph.graph import END

from app.core.agents.strategy import (
    build_strategy_graph,
    route_after_analysis,
    route_after_arguments,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(**overrides) -> dict:
    """Create a minimal StrategyState dict with defaults."""
    base = {
        "case_facts": "A filed suit against B for breach of contract.",
        "target_judge": "",
        "target_bench": "division",
        "target_court": "Supreme Court of India",
        "desired_relief": "Specific performance",
        "fact_analysis": {},
        "judge_profile": {},
        "search_results": [],
        "precedent_map": [],
        "strength_assessment": {},
        "legal_arguments": [],
        "counter_arguments": [],
        "judge_considerations": [],
        "procedural_suggestions": [],
        "strategy_memo": "",
        "confidence": 0.0,
        "messages": [],
        "iteration": 0,
        "error": "",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# route_after_analysis
# ---------------------------------------------------------------------------


class TestRouteAfterAnalysis:
    def test_returns_search_precedents_when_no_feedback(self) -> None:
        state = _make_state(messages=[], iteration=0)
        assert route_after_analysis(state) == "search_precedents"

    def test_returns_analyze_facts_when_feedback_present_and_iteration_under_3(self) -> None:
        state = _make_state(
            messages=[
                {
                    "type": "user_feedback",
                    "step": "analysis",
                    "content": "Please re-analyse focusing on criminal law.",
                }
            ],
            iteration=1,
        )
        assert route_after_analysis(state) == "analyze_facts"

    def test_returns_search_precedents_when_iteration_equals_3(self) -> None:
        state = _make_state(
            messages=[
                {"type": "user_feedback", "step": "analysis", "content": "Still not right."},
                {"type": "user_feedback", "step": "analysis", "content": "More changes."},
                {"type": "user_feedback", "step": "analysis", "content": "Final try."},
            ],
            iteration=3,
        )
        assert route_after_analysis(state) == "search_precedents"

    def test_returns_search_precedents_when_iteration_exceeds_3(self) -> None:
        state = _make_state(
            messages=[
                {"type": "user_feedback", "step": "analysis", "content": "Keep revising."},
                {"type": "user_feedback", "step": "analysis", "content": "More changes."},
                {"type": "user_feedback", "step": "analysis", "content": "Still more."},
                {"type": "user_feedback", "step": "analysis", "content": "Final try."},
                {"type": "user_feedback", "step": "analysis", "content": "One more."},
            ],
            iteration=5,
        )
        assert route_after_analysis(state) == "search_precedents"

    def test_ignores_feedback_for_other_steps(self) -> None:
        # Feedback with step != "analysis" must not trigger the loop
        state = _make_state(
            messages=[
                {
                    "type": "user_feedback",
                    "step": "arguments",
                    "content": "Should be ignored by analysis router.",
                }
            ],
            iteration=1,
        )
        assert route_after_analysis(state) == "search_precedents"

    def test_empty_feedback_content_does_not_loop(self) -> None:
        state = _make_state(
            messages=[
                {
                    "type": "user_feedback",
                    "step": "analysis",
                    "content": "",
                }
            ],
            iteration=1,
        )
        assert route_after_analysis(state) == "search_precedents"

    def test_returns_end_when_error_is_set(self) -> None:
        state = _make_state(error="LLM error in analyze_facts_node: timeout")
        assert route_after_analysis(state) == END

    def test_uses_most_recent_feedback(self) -> None:
        # Latest feedback has empty content — should NOT loop
        state = _make_state(
            messages=[
                {"type": "user_feedback", "step": "analysis", "content": "First revision"},
                {"type": "user_feedback", "step": "analysis", "content": ""},
            ],
            iteration=1,
        )
        assert route_after_analysis(state) == "search_precedents"


# ---------------------------------------------------------------------------
# route_after_arguments
# ---------------------------------------------------------------------------


class TestRouteAfterArguments:
    def test_returns_counter_and_judge_when_no_feedback(self) -> None:
        state = _make_state(messages=[], iteration=0)
        assert route_after_arguments(state) == "adversarial_search"

    def test_returns_generate_arguments_when_feedback_present_and_iteration_under_3(self) -> None:
        state = _make_state(
            messages=[
                {
                    "type": "user_feedback",
                    "step": "arguments",
                    "content": "Add more constitutional arguments.",
                }
            ],
            iteration=2,
        )
        assert route_after_arguments(state) == "generate_arguments_irac"

    def test_returns_counter_and_judge_when_iteration_equals_3(self) -> None:
        state = _make_state(
            messages=[
                {"type": "user_feedback", "step": "arguments", "content": "Refine once more."},
                {"type": "user_feedback", "step": "arguments", "content": "More changes."},
                {"type": "user_feedback", "step": "arguments", "content": "Final try."},
            ],
            iteration=3,
        )
        assert route_after_arguments(state) == "adversarial_search"

    def test_returns_counter_and_judge_when_iteration_exceeds_3(self) -> None:
        state = _make_state(
            messages=[
                {"type": "user_feedback", "step": "arguments", "content": "Keep trying."},
                {"type": "user_feedback", "step": "arguments", "content": "More."},
                {"type": "user_feedback", "step": "arguments", "content": "Again."},
                {"type": "user_feedback", "step": "arguments", "content": "Still more."},
            ],
            iteration=10,
        )
        assert route_after_arguments(state) == "adversarial_search"

    def test_ignores_feedback_for_other_steps(self) -> None:
        state = _make_state(
            messages=[
                {
                    "type": "user_feedback",
                    "step": "analysis",
                    "content": "Should be ignored.",
                }
            ],
            iteration=1,
        )
        assert route_after_arguments(state) == "adversarial_search"

    def test_empty_feedback_content_does_not_loop(self) -> None:
        state = _make_state(
            messages=[
                {
                    "type": "user_feedback",
                    "step": "arguments",
                    "content": "",
                }
            ],
            iteration=1,
        )
        assert route_after_arguments(state) == "adversarial_search"

    def test_returns_end_when_error_is_set(self) -> None:
        state = _make_state(error="LLM error in generate_arguments_node: timeout")
        assert route_after_arguments(state) == END


# ---------------------------------------------------------------------------
# build_strategy_graph
# ---------------------------------------------------------------------------


class TestBuildStrategyGraph:
    """Tests for the graph builder itself."""

    class _MockDep:
        """Generic stand-in for any dependency."""

    def _build(self, checkpointer=None):
        return build_strategy_graph(
            llm=self._MockDep(),
            flash_llm=self._MockDep(),
            embedder=self._MockDep(),
            vector_store=self._MockDep(),
            reranker=self._MockDep(),
            graph_store=self._MockDep(),
            checkpointer=checkpointer,
        )

    def test_graph_compiles_without_checkpointer(self) -> None:
        graph = self._build(checkpointer=None)
        assert hasattr(graph, "invoke") or hasattr(graph, "ainvoke")

    def test_graph_has_expected_node_count(self) -> None:
        """Graph must have exactly 14 registered nodes (+ __start__ = 15)."""
        graph = self._build()
        # LangGraph exposes the graph structure via .graph attribute on compiled graphs
        # The underlying StateGraph nodes are accessible via graph.nodes or the builder
        node_count = len(graph.nodes)
        # 14 user nodes + __start__ = 15
        assert node_count == 15, (
            f"Expected 15 nodes, got {node_count}. "
            f"Nodes: {sorted(graph.nodes)}"
        )

    def test_graph_has_expected_nodes(self) -> None:
        """Compiled graph must include all 14 named nodes."""
        graph = self._build()
        expected_nodes = {
            "analyze_facts",
            "element_decomposition",
            "fetch_judge",
            "checkpoint_analysis",
            "search_precedents",
            "evaluate_relevance",
            "assess_strength",
            "generate_arguments_irac",
            "checkpoint_arguments",
            "adversarial_search",
            "counter_and_judge",
            "argument_ordering",
            "synthesize_strategy",
            "verify",
        }
        actual_nodes = {n for n in graph.nodes if not n.startswith("__")}
        assert expected_nodes == actual_nodes, (
            f"Missing: {expected_nodes - actual_nodes}, "
            f"Extra: {actual_nodes - expected_nodes}"
        )

    def test_graph_starts_at_analyze_facts(self) -> None:
        """The graph must contain both __start__ and analyze_facts nodes."""
        graph = self._build()
        # Compiled LangGraph has __start__ and all user nodes
        assert "__start__" in graph.nodes
        assert "analyze_facts" in graph.nodes

    def test_graph_returns_compiled_object_with_ainvoke(self) -> None:
        """The compiled graph must expose an ainvoke coroutine method."""
        graph = self._build()
        assert callable(getattr(graph, "ainvoke", None))

    def test_graph_compiles_with_none_checkpointer_does_not_raise(self) -> None:
        """Passing checkpointer=None is the documented unit-test mode."""
        try:
            graph = self._build(checkpointer=None)
            assert graph is not None
        except Exception as exc:  # noqa: BLE001
            pytest.fail(f"build_strategy_graph raised unexpectedly: {exc}")
