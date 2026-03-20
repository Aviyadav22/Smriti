"""Tests for the Research Agent LangGraph graph."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

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
        checkpointer=None,
    )


# ---------------------------------------------------------------------------
# Graph construction tests
# ---------------------------------------------------------------------------

EXPECTED_NODES = {
    "rewrite_query",
    "classify",
    "statute_lookup",           # [V3]
    "element_decomposition",    # [V3]
    "plan_research",
    "checkpoint_plan",
    "dispatch_workers",
    "case_law_worker",
    "named_case_worker",
    "gather_results",
    "batch_cot_with_reflection",
    "evaluate_and_extract",
    "gap_analysis",
    "checkpoint_findings",
    "adversarial_search",       # [V3]
    "temporal_validation",      # [V3]
    "speculative_synthesis",
    "format_footnotes",
    "verify_v2",
    "quality_check",
    "checkpoint_memo",
    "fast_path_search",
    "fast_path_synthesis",
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
        assert route_after_plan(state) == "dispatch_workers"

    def test_continues_with_empty_feedback(self) -> None:
        state = _base_state(
            messages=[{"type": "user_feedback", "step": "plan", "content": ""}],
        )
        assert route_after_plan(state) == "dispatch_workers"

    def test_loops_with_feedback(self) -> None:
        state = _base_state(
            messages=[
                {"type": "user_feedback", "step": "plan", "content": "Add more"},
            ],
            iteration=0,
        )
        assert route_after_plan(state) == "plan_research"

    def test_loops_with_feedback_iteration_2(self) -> None:
        state = _base_state(
            messages=[
                {"type": "user_feedback", "step": "plan", "content": "Refine"},
            ],
            iteration=2,
        )
        assert route_after_plan(state) == "plan_research"

    def test_stops_at_max_iterations(self) -> None:
        state = _base_state(
            messages=[
                {"type": "user_feedback", "step": "plan", "content": "More"},
                {"type": "user_feedback", "step": "plan", "content": "Still more"},
                {"type": "user_feedback", "step": "plan", "content": "Again"},
            ],
            iteration=3,
        )
        assert route_after_plan(state) == "dispatch_workers"

    def test_ignores_feedback_for_other_steps(self) -> None:
        state = _base_state(
            messages=[
                {"type": "user_feedback", "step": "findings", "content": "Focus"},
            ],
            iteration=0,
        )
        assert route_after_plan(state) == "dispatch_workers"


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
        assert route_after_findings(state) == "dispatch_workers"

    def test_stops_at_max_iterations(self) -> None:
        state = _base_state(
            messages=[
                {"type": "user_feedback", "step": "findings", "content": "More"},
                {"type": "user_feedback", "step": "findings", "content": "Still more"},
                {"type": "user_feedback", "step": "findings", "content": "Again"},
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
                {"type": "user_feedback", "step": "memo", "content": "More revisions"},
                {"type": "user_feedback", "step": "memo", "content": "Final attempt"},
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


# ---------------------------------------------------------------------------
# [V3] adversarial_search_node
# ---------------------------------------------------------------------------


class TestAdversarialSearchNode:
    @pytest.mark.asyncio
    async def test_skips_when_disabled(self) -> None:
        from app.core.agents.nodes.research_nodes import adversarial_search_node

        state = {
            "include_adversarial": False,
            "worker_results": [],
            "legal_elements": [],
            "worker_reasonings": [],
        }
        result = await adversarial_search_node(
            state, AsyncMock(), AsyncMock(), AsyncMock(), AsyncMock()
        )
        assert result == {}

    @pytest.mark.asyncio
    async def test_generates_counter_queries(self) -> None:
        from app.core.agents.nodes.research_nodes import adversarial_search_node

        mock_llm = AsyncMock()
        mock_llm.generate_structured.return_value = {
            "counter_arguments": [
                {
                    "counter_thesis": "The accused acted under provocation",
                    "search_query": "sudden provocation Exception 1 Section 300 IPC",
                    "boolean_query": "provocation AND Section 300 AND exception",
                    "target_source": "case_law",
                    "priority": 1,
                },
            ],
        }

        state = {
            "include_adversarial": True,
            "worker_results": [
                {"task_type": "case_law", "results": [{"title": "State v Ram"}]}
            ],
            "legal_elements": [{"element_id": "mens_rea", "description": "intent"}],
            "worker_reasonings": ["Cases point toward murder conviction"],
            "rewritten_query": "Is this murder?",
        }

        with patch(
            "app.core.agents.nodes.research_nodes._run_adversarial_search",
            new_callable=AsyncMock,
            return_value=[{
                "task_id": "adv_1",
                "task_type": "case_law",
                "query": "provocation",
                "results": [{"title": "Nanavati v State"}],
                "source_urls": [],
                "metadata": {"adversarial": True},
                "error": None,
                "reasoning": "",
            }],
        ):
            result = await adversarial_search_node(
                state, mock_llm, AsyncMock(), AsyncMock(), AsyncMock(),
            )

        assert "worker_results" in result
        assert len(result["worker_results"]) >= 1
        assert result["worker_results"][0]["metadata"].get("adversarial") is True

    @pytest.mark.asyncio
    async def test_returns_empty_on_llm_failure(self) -> None:
        from app.core.agents.nodes.research_nodes import adversarial_search_node

        mock_llm = AsyncMock()
        mock_llm.generate_structured.side_effect = RuntimeError("LLM down")

        state = {
            "include_adversarial": True,
            "worker_results": [],
            "legal_elements": [],
            "worker_reasonings": [],
            "rewritten_query": "test",
        }

        result = await adversarial_search_node(
            state, mock_llm, AsyncMock(), AsyncMock(), AsyncMock(),
        )
        assert result == {}


# ---------------------------------------------------------------------------
# [V3] temporal_validation_node
# ---------------------------------------------------------------------------


class TestTemporalValidationNode:
    @pytest.mark.asyncio
    async def test_flags_changed_sections(self) -> None:
        from app.core.agents.nodes.research_nodes import temporal_validation_node

        state = {
            "statute_context": [{
                "act_short_name": "IPC",
                "section_number": "302",
                "section_text": "Whoever commits murder shall be punished with death.",
                "is_repealed": True,
                "replaced_by": "BNS, Section 103",
                "new_code_text": "Whoever commits murder shall be punished with death plus community service and rehabilitation.",
            }],
        }

        result = await temporal_validation_node(state)
        assert "temporal_warnings" in result
        # Texts differ significantly, should produce a warning
        assert len(result["temporal_warnings"]) >= 1
        assert "IPC" in result["temporal_warnings"][0]["old_section"]

    @pytest.mark.asyncio
    async def test_no_warning_for_identical_text(self) -> None:
        from app.core.agents.nodes.research_nodes import temporal_validation_node

        same_text = "Whoever commits murder shall be punished with death or imprisonment for life."
        state = {
            "statute_context": [{
                "act_short_name": "IPC",
                "section_number": "302",
                "section_text": same_text,
                "is_repealed": True,
                "replaced_by": "BNS, Section 103",
                "new_code_text": same_text,
            }],
        }

        result = await temporal_validation_node(state)
        assert result["temporal_warnings"] == []

    @pytest.mark.asyncio
    async def test_skips_non_repealed(self) -> None:
        from app.core.agents.nodes.research_nodes import temporal_validation_node

        state = {
            "statute_context": [{
                "act_short_name": "CPC",
                "section_number": "9",
                "section_text": "Courts shall try all civil suits.",
                "is_repealed": False,
                "replaced_by": "",
                "new_code_text": "",
            }],
        }

        result = await temporal_validation_node(state)
        assert result["temporal_warnings"] == []


# ---------------------------------------------------------------------------
# [V3] classify_query_node V3 fields
# ---------------------------------------------------------------------------


class TestClassifyV3Fields:
    @pytest.mark.asyncio
    async def test_extracts_procedural_context(self) -> None:
        from app.core.agents.nodes.research_nodes import classify_query_node

        mock_llm = AsyncMock()
        mock_llm.generate_structured.return_value = {
            "topic": "criminal",
            "complexity": "complex",
            "jurisdiction": None,
            "target_court": "Supreme Court of India",
            "target_bench": None,
            "key_entities": ["Section 302 IPC"],
            "search_hints": ["murder punishment"],
            "procedural_context": "appeal",
            "client_position": "accused",
        }

        state = _base_state(
            query="My client is accused of murder, appealing against conviction"
        )
        result = await classify_query_node(state, mock_llm)

        assert result.get("procedural_context") == "appeal"
        assert result.get("client_position") == "accused"

    @pytest.mark.asyncio
    async def test_defaults_to_empty_string(self) -> None:
        from app.core.agents.nodes.research_nodes import classify_query_node

        mock_llm = AsyncMock()
        mock_llm.generate_structured.return_value = {
            "topic": "civil",
            "complexity": "simple",
            "jurisdiction": None,
            "key_entities": [],
            "search_hints": [],
        }

        state = _base_state(query="What is natural justice?")
        result = await classify_query_node(state, mock_llm)

        assert result.get("procedural_context", "") == ""
        assert result.get("client_position", "") == ""


# ---------------------------------------------------------------------------
# [V3] plan_research_node with statute/element context
# ---------------------------------------------------------------------------


class TestCaseLawWorkerV3:
    @pytest.mark.asyncio
    async def test_element_context_enriches_query(self) -> None:
        """case_law_worker should prepend element context to query."""
        from app.core.agents.nodes.worker_nodes import case_law_worker

        state = {
            "task": {
                "task_id": "t1",
                "task_type": "case_law",
                "nl_query": "murder conviction",
                "boolean_query": "",
                "named_cases": [],
                "rationale": "test",
                "filters": {"element_context": "Intent to cause death under Section 300"},
                "priority": 1,
            },
            "precomputed_embeddings": {},
        }

        with patch(
            "app.core.agents.nodes.worker_nodes.parallel_hybrid_search",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_search, patch(
            "app.core.agents.nodes.worker_nodes.async_session_factory",
        ) as mock_factory:
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

            await case_law_worker(
                state, AsyncMock(), AsyncMock(), AsyncMock(), AsyncMock()
            )

            # The first query should have element context prepended
            call_args = mock_search.call_args
            queries = call_args[0][0]  # first positional arg
            assert "Intent to cause death" in queries[0]
            assert "murder conviction" in queries[0]

    @pytest.mark.asyncio
    async def test_bench_filter_passed_to_search(self) -> None:
        """case_law_worker should pass bench_type filter when target_bench specified."""
        from app.core.agents.nodes.worker_nodes import case_law_worker

        state = {
            "task": {
                "task_id": "t1",
                "task_type": "case_law",
                "nl_query": "right to privacy",
                "boolean_query": "",
                "named_cases": [],
                "rationale": "test",
                "filters": {"target_bench": "constitutional"},
                "priority": 1,
            },
            "precomputed_embeddings": {},
        }

        with patch(
            "app.core.agents.nodes.worker_nodes.parallel_hybrid_search",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_search, patch(
            "app.core.agents.nodes.worker_nodes.async_session_factory",
        ) as mock_factory:
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

            await case_law_worker(
                state, AsyncMock(), AsyncMock(), AsyncMock(), AsyncMock()
            )

            # Check that filters were passed
            call_kwargs = mock_search.call_args.kwargs
            filters = call_kwargs.get("filters")
            assert filters is not None
            assert filters.bench_type == "constitutional"


class TestPlanResearchV3:
    @pytest.mark.asyncio
    async def test_plan_receives_statute_and_elements(self) -> None:
        from app.core.agents.nodes.research_nodes import plan_research_node

        mock_llm = AsyncMock()
        mock_llm.generate_structured.return_value = {
            "research_tasks": [{
                "task_type": "case_law",
                "nl_query": "cases interpreting Section 300 Exception 1",
                "boolean_query": "Section 300 exception provocation",
                "named_cases": [],
                "rationale": "Need case law on provocation defense",
                "filters": {"element_id": "provocation_defense"},
                "priority": 1,
            }],
        }

        state = _base_state(
            rewritten_query="Is this murder or culpable homicide under Section 302/300 IPC?",
            complexity="complex",
            messages=[{"type": "classification", "data": {"topic": "criminal"}}],
            statute_context=[{
                "act_short_name": "IPC",
                "section_number": "300",
                "section_text": "Murder definition...",
                "is_repealed": True,
                "replaced_by": "BNS 101",
                "new_code_text": "",
                "section_title": "Murder",
            }],
            legal_elements=[{
                "element_id": "provocation_defense",
                "description": "Whether Exception 1 applies",
                "statute_basis": "IPC Section 300, Exception 1",
                "search_query": "sudden provocation",
                "is_contested": True,
            }],
            procedural_context="trial",
            client_position="accused",
        )

        result = await plan_research_node(state, mock_llm)
        assert "research_plan" in result

        # Verify LLM was called with V3 context in the prompt
        call_args = mock_llm.generate_structured.call_args
        prompt = call_args.kwargs.get("prompt", "")
        assert "Statute" in prompt or "statute" in prompt.lower()
        assert "Element" in prompt or "element" in prompt.lower()
        assert "provocation_defense" in prompt
        assert "trial" in prompt
        assert "accused" in prompt
