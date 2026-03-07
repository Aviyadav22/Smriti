"""Tests for agent state schemas."""
from app.core.agents.state import ResearchState, CasePrepState


class TestResearchState:
    def test_can_create_state(self) -> None:
        state: ResearchState = {
            "query": "test",
            "sub_queries": [],
            "search_results": [],
            "cross_references": [],
            "contradictions": [],
            "draft_memo": "",
            "confidence": 0.0,
            "messages": [],
            "iteration": 0,
        }
        assert state["query"] == "test"
        assert state["iteration"] == 0

    def test_search_results_uses_replace_semantics(self) -> None:
        """Verify search_results uses plain list (replace, not accumulate)."""
        import typing
        hints = typing.get_type_hints(ResearchState, include_extras=True)
        sr_hint = hints["search_results"]
        # search_results should be a plain list[dict], not Annotated
        assert not hasattr(sr_hint, "__metadata__")


class TestCasePrepState:
    def test_can_create_state(self) -> None:
        state: CasePrepState = {
            "document_id": "abc",
            "analysis": {},
            "prioritized_issues": [],
            "argument_order": [],
            "strategy_points": [],
            "enhanced_memo": "",
            "messages": [],
            "iteration": 0,
        }
        assert state["document_id"] == "abc"
        assert state["strategy_points"] == []
