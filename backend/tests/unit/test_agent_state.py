"""Tests for agent state schemas."""
from app.core.agents.state import (
    ResearchState,
    CasePrepState,
    StatuteContext,
    LegalElement,
    TemporalWarning,
)


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


class TestStatuteContext:
    def test_has_required_fields(self) -> None:
        ctx = StatuteContext(
            act_short_name="IPC",
            section_number="302",
            section_title="Punishment for murder",
            section_text="Whoever commits murder shall be punished...",
            is_repealed=True,
            replaced_by="BNS, Section 103",
            new_code_text="Whoever commits murder shall be punished...",
        )
        assert ctx["act_short_name"] == "IPC"
        assert ctx["is_repealed"] is True
        assert ctx["new_code_text"] != ""


class TestLegalElement:
    def test_has_required_fields(self) -> None:
        elem = LegalElement(
            element_id="mens_rea",
            description="Intention to cause death or knowledge of likelihood",
            statute_basis="IPC Section 300",
            search_query="intention to cause death Section 300 IPC murder",
            is_contested=True,
        )
        assert elem["element_id"] == "mens_rea"
        assert elem["is_contested"] is True


class TestTemporalWarning:
    def test_has_required_fields(self) -> None:
        w = TemporalWarning(
            case_id="abc-123",
            case_citation="(2020) 5 SCC 100",
            old_section="IPC 302",
            new_section="BNS 103",
            similarity=0.75,
            warning="Section wording changed (75% similar).",
        )
        assert w["similarity"] == 0.75


class TestResearchStateV3Fields:
    def test_research_state_has_v3_fields(self) -> None:
        """ResearchState must include V3 fields."""
        annotations = ResearchState.__annotations__
        assert "statute_context" in annotations
        assert "legal_elements" in annotations
        assert "procedural_context" in annotations
        assert "client_position" in annotations
        assert "include_adversarial" in annotations
        assert "temporal_warnings" in annotations


class TestCasePrepState:
    def test_can_create_state(self) -> None:
        state: CasePrepState = {
            "document_id": "abc",
            "analysis": {},
            "prioritized_issues": [],
            "argument_order": [],
            "enhanced_memo": "",
            "messages": [],
            "iteration": 0,
        }
        assert state["document_id"] == "abc"
        assert state["argument_order"] == []
