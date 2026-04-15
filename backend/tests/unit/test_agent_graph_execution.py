"""Tests for agent graph structure and routing logic."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.agents.case_prep import (
    build_case_prep_graph,
    route_after_issues,
    route_after_load,
    route_after_strategy,
)
from app.core.agents.case_prep import (
    route_after_memo as cp_route_after_memo,
)
from app.core.agents.research import (
    build_research_graph,
    route_after_findings,
    route_after_memo,
    route_after_plan,
)

if TYPE_CHECKING:
    from app.core.agents.state import CasePrepState, ResearchState

# ---------------------------------------------------------------------------
# Research Agent — Router tests
# ---------------------------------------------------------------------------


class TestResearchRouters:
    """Tests for research agent conditional routing functions."""

    def test_route_after_plan_no_feedback_goes_to_search(self) -> None:
        state: ResearchState = {
            "query": "test",
            "target_court": "",
            "target_bench": "",
            "sub_queries": [],
            "search_results": [],
            "cross_references": [],
            "contradictions": [],
            "draft_memo": "",
            "confidence": 0.0,
            "messages": [],
            "iteration": 0,
        }
        assert route_after_plan(state) == "dispatch_workers"

    def test_route_after_plan_with_feedback_loops_back(self) -> None:
        state: ResearchState = {
            "query": "test",
            "target_court": "",
            "target_bench": "",
            "sub_queries": [],
            "search_results": [],
            "cross_references": [],
            "contradictions": [],
            "draft_memo": "",
            "confidence": 0.0,
            "messages": [
                {"type": "user_feedback", "step": "plan", "content": "refine this"}
            ],
            "iteration": 1,
        }
        assert route_after_plan(state) == "plan_research"

    def test_route_after_plan_max_iterations_goes_to_dispatch(self) -> None:
        state: ResearchState = {
            "query": "test",
            "target_court": "",
            "target_bench": "",
            "sub_queries": [],
            "search_results": [],
            "cross_references": [],
            "contradictions": [],
            "draft_memo": "",
            "confidence": 0.0,
            "messages": [
                {"type": "user_feedback", "step": "plan", "content": "refine this"},
                {"type": "user_feedback", "step": "plan", "content": "more changes"},
                {"type": "user_feedback", "step": "plan", "content": "still not right"},
            ],
            "iteration": 3,
        }
        assert route_after_plan(state) == "dispatch_workers"

    def test_route_after_findings_no_feedback_goes_to_synthesize(self) -> None:
        state: ResearchState = {
            "query": "test",
            "target_court": "",
            "target_bench": "",
            "sub_queries": [],
            "search_results": [],
            "cross_references": [],
            "contradictions": [],
            "draft_memo": "",
            "confidence": 0.0,
            "messages": [],
            "iteration": 0,
        }
        assert route_after_findings(state) == "synthesize"

    def test_route_after_memo_no_feedback_goes_to_end(self) -> None:
        state: ResearchState = {
            "query": "test",
            "target_court": "",
            "target_bench": "",
            "sub_queries": [],
            "search_results": [],
            "cross_references": [],
            "contradictions": [],
            "draft_memo": "",
            "confidence": 0.0,
            "messages": [],
            "iteration": 0,
        }
        assert route_after_memo(state) == "__end__"

    def test_route_after_memo_with_feedback_loops(self) -> None:
        state: ResearchState = {
            "query": "test",
            "target_court": "",
            "target_bench": "",
            "sub_queries": [],
            "search_results": [],
            "cross_references": [],
            "contradictions": [],
            "draft_memo": "",
            "confidence": 0.0,
            "messages": [
                {"type": "user_feedback", "step": "memo", "content": "add more"}
            ],
            "iteration": 1,
        }
        assert route_after_memo(state) == "synthesize"


# ---------------------------------------------------------------------------
# Case Prep Agent — Router tests
# ---------------------------------------------------------------------------


class TestCasePrepRouters:
    """Tests for case prep agent conditional routing functions."""

    def _base_state(self, **overrides) -> CasePrepState:
        defaults: CasePrepState = {
            "document_id": "doc-1",
            "analysis": {},
            "prioritized_issues": [],
            "argument_order": [],
            "enhanced_memo": "",
            "messages": [],
            "iteration": 0,
            "error": "",
        }
        defaults.update(overrides)
        return defaults

    def test_route_after_load_no_error_goes_to_prioritize(self) -> None:
        state = self._base_state()
        assert route_after_load(state) == "prioritize"

    def test_route_after_load_with_error_goes_to_end(self) -> None:
        state = self._base_state(error="Document not found")
        assert route_after_load(state) == "__end__"

    def test_route_after_issues_no_feedback_goes_to_deep_search(self) -> None:
        state = self._base_state()
        assert route_after_issues(state) == "deep_search"

    def test_route_after_issues_with_feedback_loops(self) -> None:
        state = self._base_state(
            messages=[
                {"type": "user_feedback", "step": "issues", "content": "reorder"}
            ],
            iteration=1,
        )
        assert route_after_issues(state) == "prioritize"

    def test_route_after_strategy_no_feedback(self) -> None:
        state = self._base_state()
        assert route_after_strategy(state) == "strategy_memo"

    def test_cp_route_after_memo_no_feedback(self) -> None:
        state = self._base_state()
        assert cp_route_after_memo(state) == "__end__"


# ---------------------------------------------------------------------------
# Graph build tests (compile without checkpointer)
# ---------------------------------------------------------------------------


class TestGraphCompilation:
    """Tests that agent graphs compile successfully."""

    def test_research_graph_compiles(self) -> None:
        """Research graph compiles with mock dependencies."""

        class MockDep:
            pass

        graph = build_research_graph(
            llm=MockDep(),
            flash_llm=MockDep(),
            embedder=MockDep(),
            vector_store=MockDep(),
            reranker=MockDep(),
            checkpointer=None,
        )
        # Compiled graph should have an invoke method
        assert hasattr(graph, "invoke") or hasattr(graph, "ainvoke")

    def test_case_prep_graph_compiles(self) -> None:
        """Case prep graph compiles with mock dependencies."""

        class MockDep:
            pass

        graph = build_case_prep_graph(
            llm=MockDep(),
            embedder=MockDep(),
            vector_store=MockDep(),
            reranker=MockDep(),
            graph_store=MockDep(),
            checkpointer=None,
        )
        assert hasattr(graph, "invoke") or hasattr(graph, "ainvoke")
