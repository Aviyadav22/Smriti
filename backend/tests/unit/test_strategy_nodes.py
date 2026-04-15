"""Tests for Strategy Agent node functions."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.agents.nodes.strategy_nodes import (
    analyze_facts_node,
    assess_strength_node,
    counter_arguments_node,
    fetch_judge_profile_node,
    generate_arguments_node,
    judge_considerations_node,
    search_precedents_node,
    synthesize_strategy_node,
    verify_citations_node,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(**overrides) -> dict:
    """Create a minimal StrategyState dict with defaults."""
    base = {
        "case_facts": "A filed suit against B for breach of contract under Indian Contract Act, 1872.",
        "target_judge": "",
        "target_bench": "division",
        "target_court": "Supreme Court of India",
        "desired_relief": "Specific performance of contract",
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


def _make_llm(**overrides) -> AsyncMock:
    """Create a mock LLMProvider."""
    llm = AsyncMock()
    llm.generate = AsyncMock(return_value="")
    llm.generate_structured = AsyncMock(return_value={})
    for k, v in overrides.items():
        setattr(llm, k, v)
    return llm


# ---------------------------------------------------------------------------
# analyze_facts_node
# ---------------------------------------------------------------------------


class TestAnalyzeFactsNode:
    @pytest.mark.asyncio
    async def test_returns_fact_analysis_from_llm(self) -> None:
        fact_analysis = {
            "parties": {"plaintiff": "A", "defendant": "B"},
            "causes_of_action": [
                {"title": "Breach of Contract", "statutory_basis": "Indian Contract Act, 1872"}
            ],
            "relief_sought": "Specific performance",
        }
        llm = _make_llm()
        llm.generate_structured.return_value = fact_analysis

        state = _make_state()
        result = await analyze_facts_node(state, llm)

        assert "fact_analysis" in result
        assert result["fact_analysis"] == fact_analysis

    @pytest.mark.asyncio
    async def test_passes_case_facts_as_prompt(self) -> None:
        llm = _make_llm()
        llm.generate_structured.return_value = {"causes_of_action": []}

        state = _make_state(case_facts="Plaintiff sued for wrongful termination of employment.")
        await analyze_facts_node(state, llm)

        call_kwargs = llm.generate_structured.call_args
        prompt_sent = call_kwargs.kwargs.get(
            "prompt", call_kwargs.args[0] if call_kwargs.args else ""
        )
        assert "wrongful termination" in prompt_sent

    @pytest.mark.asyncio
    async def test_empty_facts_returns_empty_analysis(self) -> None:
        llm = _make_llm()
        llm.generate_structured.return_value = {}

        state = _make_state(case_facts="")
        result = await analyze_facts_node(state, llm)

        assert result["fact_analysis"] == {}

    @pytest.mark.asyncio
    async def test_error_handling_returns_error_dict(self) -> None:
        llm = _make_llm()
        llm.generate_structured.side_effect = RuntimeError("LLM service unavailable")

        state = _make_state()
        result = await analyze_facts_node(state, llm)

        assert "error" in result
        assert "LLM error in analyze_facts_node" in result["error"]


# ---------------------------------------------------------------------------
# fetch_judge_profile_node
# ---------------------------------------------------------------------------


class TestFetchJudgeProfileNode:
    @pytest.mark.asyncio
    async def test_returns_empty_profile_when_no_target_judge(self) -> None:
        db = AsyncMock()
        state = _make_state(target_judge="")
        result = await fetch_judge_profile_node(state, db)

        assert result == {"judge_profile": {}}
        db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_profile_with_disposal_and_acts_when_judge_set(self) -> None:
        # Mock disposal breakdown query
        disposal_mock = MagicMock()
        disposal_mock.fetchall.return_value = [
            ("Allowed", 42),
            ("Dismissed", 30),
        ]

        # Mock top acts query
        acts_mock = MagicMock()
        acts_mock.fetchall.return_value = [
            ("Indian Contract Act, 1872", 20),
            ("Code of Civil Procedure, 1908", 15),
        ]

        # Mock counts query
        counts_mock = MagicMock()
        counts_mock.fetchone.return_value = (72, 18)

        db = AsyncMock()
        db.execute.side_effect = [disposal_mock, acts_mock, counts_mock]

        state = _make_state(target_judge="Justice D.Y. Chandrachud")
        result = await fetch_judge_profile_node(state, db)

        assert "judge_profile" in result
        profile = result["judge_profile"]
        assert profile["name"] == "Justice D.Y. Chandrachud"
        assert len(profile["disposal_breakdown"]) == 2
        assert profile["disposal_breakdown"][0]["disposal_nature"] == "Allowed"
        assert profile["disposal_breakdown"][0]["count"] == 42
        assert len(profile["top_acts"]) == 2
        assert profile["top_acts"][0]["act"] == "Indian Contract Act, 1872"
        assert profile["total_cases"] == 72
        assert profile["recent_cases"] == 18

    @pytest.mark.asyncio
    async def test_handles_db_exception_gracefully(self) -> None:
        db = AsyncMock()
        db.execute.side_effect = RuntimeError("DB connection failed")

        state = _make_state(target_judge="Justice A.B. Singh")
        result = await fetch_judge_profile_node(state, db)

        # Should return empty profile, not raise
        assert result == {"judge_profile": {}}

    @pytest.mark.asyncio
    async def test_returns_empty_profile_when_counts_row_is_none(self) -> None:
        disposal_mock = MagicMock()
        disposal_mock.fetchall.return_value = []

        acts_mock = MagicMock()
        acts_mock.fetchall.return_value = []

        counts_mock = MagicMock()
        counts_mock.fetchone.return_value = None

        db = AsyncMock()
        db.execute.side_effect = [disposal_mock, acts_mock, counts_mock]

        state = _make_state(target_judge="Justice Unknown")
        result = await fetch_judge_profile_node(state, db)

        assert result["judge_profile"]["total_cases"] == 0
        assert result["judge_profile"]["recent_cases"] == 0


# ---------------------------------------------------------------------------
# search_precedents_node
# ---------------------------------------------------------------------------


class TestSearchPrecedentsNode:
    @pytest.mark.asyncio
    async def test_returns_search_results_and_precedent_map(self) -> None:
        from dataclasses import dataclass

        @dataclass(frozen=True, slots=True)
        class FakeItem:
            case_id: str
            score: float
            title: str | None = None
            citation: str | None = None
            court: str | None = None
            year: int | None = None
            date: str | None = None
            case_type: str | None = None
            judge: str | None = None
            snippet: str | None = None
            relevance_sources: list[str] | None = None

        mock_response = MagicMock()
        mock_response.results = [
            FakeItem(
                case_id="c1",
                score=0.85,
                title="Hadley v Baxendale",
                citation="(2020) 1 SCC 100",
                court="Supreme Court of India",
                snippet="remoteness of damage",
            ),
        ]

        graph_store = AsyncMock()
        graph_store.get_neighbors.return_value = {"neighbors": []}

        with (
            patch(
                "app.core.agents.nodes.common.hybrid_search",
                new_callable=AsyncMock,
            ) as mock_search,
            patch(
                "app.core.agents.nodes.strategy_nodes.enrich_results_with_ratio",
                new_callable=AsyncMock,
            ) as mock_enrich,
        ):
            mock_search.return_value = mock_response
            mock_enrich.side_effect = lambda results, db: results

            state = _make_state(
                fact_analysis={
                    "causes_of_action": [
                        {
                            "title": "Breach of Contract",
                            "statutory_basis": "Indian Contract Act, 1872",
                        }
                    ]
                },
                desired_relief="Specific performance",
            )
            llm = _make_llm()
            embedder = AsyncMock()
            vector_store = AsyncMock()
            reranker = AsyncMock()
            db = AsyncMock()

            result = await search_precedents_node(
                state, llm, embedder, vector_store, reranker, graph_store, db
            )

            assert "search_results" in result
            assert "precedent_map" in result
            assert len(result["search_results"]) >= 1
            assert len(result["precedent_map"]) >= 1
            # Each precedent map entry has required fields
            entry = result["precedent_map"][0]
            assert "case_id" in entry
            assert "strength" in entry

    @pytest.mark.asyncio
    async def test_handles_empty_causes_of_action(self) -> None:
        from dataclasses import dataclass

        @dataclass(frozen=True, slots=True)
        class FakeItem:
            case_id: str
            score: float
            title: str | None = None
            citation: str | None = None
            court: str | None = None
            year: int | None = None
            date: str | None = None
            case_type: str | None = None
            judge: str | None = None
            snippet: str | None = None
            relevance_sources: list[str] | None = None

        mock_response = MagicMock()
        mock_response.results = [
            FakeItem(case_id="c2", score=0.70, title="General Case"),
        ]

        graph_store = AsyncMock()
        graph_store.get_neighbors.return_value = {"neighbors": []}

        with (
            patch(
                "app.core.agents.nodes.common.hybrid_search",
                new_callable=AsyncMock,
            ) as mock_search,
            patch(
                "app.core.agents.nodes.strategy_nodes.enrich_results_with_ratio",
                new_callable=AsyncMock,
            ) as mock_enrich,
        ):
            mock_search.return_value = mock_response
            mock_enrich.side_effect = lambda results, db: results

            # No causes_of_action — still runs on case_facts + desired_relief
            state = _make_state(fact_analysis={"causes_of_action": []})
            result = await search_precedents_node(
                state,
                _make_llm(),
                AsyncMock(),
                AsyncMock(),
                AsyncMock(),
                graph_store,
                AsyncMock(),
            )

            assert "search_results" in result
            assert "precedent_map" in result

    @pytest.mark.asyncio
    async def test_no_queries_returns_empty(self) -> None:
        # If no case_facts and no causes_of_action and no desired_relief
        state = _make_state(
            case_facts="",
            desired_relief="",
            fact_analysis={"causes_of_action": []},
        )
        graph_store = AsyncMock()

        result = await search_precedents_node(
            state,
            _make_llm(),
            AsyncMock(),
            AsyncMock(),
            AsyncMock(),
            graph_store,
            AsyncMock(),
        )

        assert result == {"search_results": [], "precedent_map": []}

    @pytest.mark.asyncio
    async def test_graph_neighbors_added_to_results(self) -> None:
        from dataclasses import dataclass

        @dataclass(frozen=True, slots=True)
        class FakeItem:
            case_id: str
            score: float
            title: str | None = None
            citation: str | None = None
            court: str | None = None
            year: int | None = None
            date: str | None = None
            case_type: str | None = None
            judge: str | None = None
            snippet: str | None = None
            relevance_sources: list[str] | None = None

        mock_response = MagicMock()
        mock_response.results = [
            FakeItem(case_id="c1", score=0.9, title="Main Case"),
        ]

        neighbor_data = {
            "neighbors": [
                {
                    "node": {
                        "id": "c_neighbor",
                        "title": "Neighbor Case",
                        "citation": "(2019) 3 SCC 50",
                        "court": "Supreme Court of India",
                        "year": 2019,
                    }
                }
            ]
        }

        graph_store = AsyncMock()
        graph_store.get_neighbors.return_value = neighbor_data

        with (
            patch(
                "app.core.agents.nodes.common.hybrid_search",
                new_callable=AsyncMock,
            ) as mock_search,
            patch(
                "app.core.agents.nodes.strategy_nodes.enrich_results_with_ratio",
                new_callable=AsyncMock,
            ) as mock_enrich,
        ):
            mock_search.return_value = mock_response
            mock_enrich.side_effect = lambda results, db: results

            state = _make_state(
                fact_analysis={
                    "causes_of_action": [{"title": "Tort", "statutory_basis": "Tort Law"}]
                }
            )
            result = await search_precedents_node(
                state,
                _make_llm(),
                AsyncMock(),
                AsyncMock(),
                AsyncMock(),
                graph_store,
                AsyncMock(),
            )

            case_ids = [r.get("case_id") for r in result["search_results"]]
            assert "c_neighbor" in case_ids


# ---------------------------------------------------------------------------
# assess_strength_node
# ---------------------------------------------------------------------------


class TestAssessStrengthNode:
    @pytest.mark.asyncio
    async def test_returns_strength_assessment_from_llm(self) -> None:
        assessment = {
            "overall_score": 7,
            "legal_strength": "strong",
            "factual_strength": "moderate",
            "summary": "Case has strong legal footing.",
        }
        llm = _make_llm()
        llm.generate_structured.return_value = assessment

        state = _make_state(
            fact_analysis={"parties": {"plaintiff": "A", "defendant": "B"}},
            precedent_map=[{"case_id": "c1", "strength": "BINDING"}],
        )
        result = await assess_strength_node(state, llm)

        assert "strength_assessment" in result
        assert result["strength_assessment"] == assessment

    @pytest.mark.asyncio
    async def test_includes_judge_profile_in_prompt_when_present(self) -> None:
        llm = _make_llm()
        llm.generate_structured.return_value = {"overall_score": 5}

        judge_profile = {
            "name": "Justice X",
            "disposal_breakdown": [{"disposal_nature": "Dismissed", "count": 60}],
        }
        state = _make_state(judge_profile=judge_profile)
        await assess_strength_node(state, llm)

        call_kwargs = llm.generate_structured.call_args
        prompt_sent = call_kwargs.kwargs.get(
            "prompt", call_kwargs.args[0] if call_kwargs.args else ""
        )
        assert "Justice X" in prompt_sent

    @pytest.mark.asyncio
    async def test_empty_state_returns_empty_assessment(self) -> None:
        llm = _make_llm()
        llm.generate_structured.return_value = {}

        state = _make_state()
        result = await assess_strength_node(state, llm)

        assert result["strength_assessment"] == {}

    @pytest.mark.asyncio
    async def test_error_handling_returns_error_dict(self) -> None:
        llm = _make_llm()
        llm.generate_structured.side_effect = RuntimeError("LLM service unavailable")

        state = _make_state()
        result = await assess_strength_node(state, llm)

        assert "error" in result
        assert "LLM error in assess_strength_node" in result["error"]


# ---------------------------------------------------------------------------
# generate_arguments_node
# ---------------------------------------------------------------------------


class TestGenerateArgumentsNode:
    @pytest.mark.asyncio
    async def test_returns_legal_arguments_from_structured_llm(self) -> None:
        arguments = [
            {
                "title": "Breach of Section 73 ICA",
                "legal_basis": "Indian Contract Act, 1872, s.73",
                "precedents": ["(2020) 1 SCC 100"],
                "strength": "strong",
            }
        ]
        llm = _make_llm()
        llm.generate_structured.return_value = {"arguments": arguments}

        state = _make_state(
            fact_analysis={"causes_of_action": [{"title": "Breach", "statutory_basis": "ICA"}]},
            precedent_map=[
                {"case_id": "c1", "strength": "BINDING", "citation": "(2020) 1 SCC 100"}
            ],
            strength_assessment={"overall_score": 7},
        )
        result = await generate_arguments_node(state, llm)

        assert "legal_arguments" in result
        assert result["legal_arguments"] == arguments

    @pytest.mark.asyncio
    async def test_includes_desired_relief_in_prompt(self) -> None:
        llm = _make_llm()
        llm.generate_structured.return_value = {"arguments": []}

        state = _make_state(desired_relief="Injunction restraining defendant")
        await generate_arguments_node(state, llm)

        call_kwargs = llm.generate_structured.call_args
        prompt_sent = call_kwargs.kwargs.get(
            "prompt", call_kwargs.args[0] if call_kwargs.args else ""
        )
        assert "Injunction" in prompt_sent

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_llm_returns_no_arguments(self) -> None:
        llm = _make_llm()
        llm.generate_structured.return_value = {}

        state = _make_state()
        result = await generate_arguments_node(state, llm)

        assert result["legal_arguments"] == []

    @pytest.mark.asyncio
    async def test_error_handling_returns_error_dict(self) -> None:
        llm = _make_llm()
        llm.generate_structured.side_effect = RuntimeError("LLM service unavailable")

        state = _make_state()
        result = await generate_arguments_node(state, llm)

        assert "error" in result
        assert "LLM error in generate_arguments_node" in result["error"]


# ---------------------------------------------------------------------------
# counter_arguments_node
# ---------------------------------------------------------------------------


class TestCounterArgumentsNode:
    @pytest.mark.asyncio
    async def test_returns_counter_arguments_from_structured_llm(self) -> None:
        counter_args = [
            {
                "title": "Limitation period expired",
                "legal_basis": "Limitation Act, 1963",
                "likely_precedents": [],
                "impact": "high",
                "rebuttal": "Plaintiff was under disability.",
                "rebuttal_precedents": [],
            }
        ]
        llm = _make_llm()
        llm.generate_structured.return_value = {"counter_arguments": counter_args}

        state = _make_state(
            legal_arguments=[{"title": "Breach of Contract"}],
            precedent_map=[{"case_id": "c1"}],
        )
        result = await counter_arguments_node(state, llm)

        assert "counter_arguments" in result
        assert len(result["counter_arguments"]) == 1
        assert result["counter_arguments"][0]["title"] == "Limitation period expired"

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_counter_arguments_key(self) -> None:
        llm = _make_llm()
        llm.generate_structured.return_value = {}

        state = _make_state()
        result = await counter_arguments_node(state, llm)

        assert result["counter_arguments"] == []

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_counter_arguments_is_empty(self) -> None:
        llm = _make_llm()
        llm.generate_structured.return_value = {"counter_arguments": []}

        state = _make_state()
        result = await counter_arguments_node(state, llm)

        assert result["counter_arguments"] == []

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_counter_arguments_not_a_list(self) -> None:
        llm = _make_llm()
        llm.generate_structured.return_value = {"counter_arguments": "not a list"}

        state = _make_state()
        result = await counter_arguments_node(state, llm)

        assert result["counter_arguments"] == []

    @pytest.mark.asyncio
    async def test_error_handling_returns_error_dict(self) -> None:
        llm = _make_llm()
        llm.generate_structured.side_effect = RuntimeError("LLM service unavailable")

        state = _make_state()
        result = await counter_arguments_node(state, llm)

        assert "error" in result
        assert "LLM error in counter_arguments_node" in result["error"]


# ---------------------------------------------------------------------------
# judge_considerations_node
# ---------------------------------------------------------------------------


class TestJudgeConsiderationsNode:
    @pytest.mark.asyncio
    async def test_returns_generic_considerations_when_no_judge_profile(self) -> None:
        llm = _make_llm()
        state = _make_state(judge_profile={}, target_bench="division")

        result = await judge_considerations_node(state, llm)

        assert "judge_considerations" in result
        assert "procedural_suggestions" in result
        assert len(result["judge_considerations"]) >= 1
        assert result["judge_considerations"][0]["source"] == "generic"
        assert "division" in result["judge_considerations"][0]["insight"]
        # LLM should NOT be called for generic case
        llm.generate.assert_not_called()
        llm.generate_structured.assert_not_called()

    @pytest.mark.asyncio
    async def test_generic_considerations_include_bench_type(self) -> None:
        llm = _make_llm()
        state = _make_state(judge_profile={}, target_bench="constitutional")

        result = await judge_considerations_node(state, llm)

        assert "constitutional" in result["judge_considerations"][0]["insight"]

    @pytest.mark.asyncio
    async def test_calls_llm_when_judge_profile_is_set(self) -> None:
        strategic_insights = [
            {"insight": "Judge prefers brief oral arguments.", "basis": "historical data"}
        ]
        procedural_suggestions = ["File written submissions 48 hours in advance."]

        llm = _make_llm()
        llm.generate_structured.return_value = {
            "strategic_insights": strategic_insights,
            "procedural_suggestions": procedural_suggestions,
        }

        judge_profile = {
            "name": "Justice D.Y. Chandrachud",
            "disposal_breakdown": [{"disposal_nature": "Allowed", "count": 42}],
            "top_acts": [{"act": "Indian Contract Act", "count": 10}],
            "total_cases": 72,
            "recent_cases": 18,
        }
        state = _make_state(
            judge_profile=judge_profile,
            legal_arguments=[{"title": "Breach of Contract"}],
        )
        result = await judge_considerations_node(state, llm)

        llm.generate_structured.assert_called_once()
        assert result["judge_considerations"] == strategic_insights
        assert result["procedural_suggestions"] == procedural_suggestions

    @pytest.mark.asyncio
    async def test_returns_empty_lists_when_llm_returns_non_dict(self) -> None:
        llm = _make_llm()
        llm.generate_structured.return_value = "not a dict"

        state = _make_state(
            judge_profile={"name": "Justice X", "disposal_breakdown": [], "top_acts": []}
        )
        result = await judge_considerations_node(state, llm)

        assert result["judge_considerations"] == []
        assert result["procedural_suggestions"] == []

    @pytest.mark.asyncio
    async def test_error_handling_returns_error_dict(self) -> None:
        llm = _make_llm()
        llm.generate_structured.side_effect = RuntimeError("LLM service unavailable")

        state = _make_state(
            judge_profile={"name": "Justice Y", "disposal_breakdown": [], "top_acts": []}
        )
        result = await judge_considerations_node(state, llm)

        assert "error" in result
        assert "LLM error in judge_considerations_node" in result["error"]

    @pytest.mark.asyncio
    async def test_generic_procedural_suggestions_are_non_empty(self) -> None:
        llm = _make_llm()
        state = _make_state(judge_profile={})

        result = await judge_considerations_node(state, llm)

        assert len(result["procedural_suggestions"]) >= 1
        assert all(isinstance(s, str) for s in result["procedural_suggestions"])


# ---------------------------------------------------------------------------
# synthesize_strategy_node
# ---------------------------------------------------------------------------


class TestSynthesizeStrategyNode:
    @pytest.mark.asyncio
    async def test_returns_strategy_memo_and_confidence(self) -> None:
        memo_text = "# Strategy Memo\n\nBased on analysis, recommend pursuing settlement."
        llm = _make_llm()
        llm.generate.return_value = memo_text

        state = _make_state(
            search_results=[{"score": 0.85, "source_query": "breach of contract"}],
            precedent_map=[{"strength": "BINDING"}],
        )
        result = await synthesize_strategy_node(state, llm)

        assert "strategy_memo" in result
        assert "confidence" in result
        assert result["strategy_memo"].startswith(memo_text)
        assert 0.0 <= result["confidence"] <= 1.0

    @pytest.mark.asyncio
    async def test_zero_search_results_gives_zero_confidence(self) -> None:
        llm = _make_llm()
        llm.generate.return_value = "No relevant precedents found."

        state = _make_state(search_results=[], precedent_map=[])
        result = await synthesize_strategy_node(state, llm)

        assert result["confidence"] == 0.0

    @pytest.mark.asyncio
    async def test_many_binding_precedents_raises_confidence(self) -> None:
        llm = _make_llm()
        llm.generate.return_value = "Strong case with binding precedents."

        search_results = [
            {"score": 0.9, "source_query": "breach", "case_id": f"c{i}"} for i in range(10)
        ]
        precedent_map = [{"strength": "BINDING"} for _ in range(10)]

        state = _make_state(
            search_results=search_results,
            precedent_map=precedent_map,
            fact_analysis={"causes_of_action": [{"title": "Breach"}]},
        )
        result = await synthesize_strategy_node(state, llm)

        assert result["confidence"] > 0.0

    @pytest.mark.asyncio
    async def test_includes_all_state_components_in_prompt(self) -> None:
        llm = _make_llm()
        llm.generate.return_value = "Memo."

        state = _make_state(
            case_facts="Plaintiff seeks specific performance.",
            legal_arguments=[{"title": "Section 10 SRA"}],
            counter_arguments=[{"title": "Limitation"}],
            judge_considerations=[{"insight": "Judge favors written submissions"}],
            procedural_suggestions=["File in advance."],
        )
        await synthesize_strategy_node(state, llm)

        call_kwargs = llm.generate.call_args
        prompt_sent = call_kwargs.kwargs.get(
            "prompt", call_kwargs.args[0] if call_kwargs.args else ""
        )
        assert "specific performance" in prompt_sent.lower()

    @pytest.mark.asyncio
    async def test_confidence_is_float_between_0_and_1(self) -> None:
        llm = _make_llm()
        llm.generate.return_value = "Memo text."

        state = _make_state(
            search_results=[{"score": 0.75, "source_query": "q1"}],
            precedent_map=[{"strength": "PERSUASIVE"}],
        )
        result = await synthesize_strategy_node(state, llm)

        assert isinstance(result["confidence"], float)
        assert 0.0 <= result["confidence"] <= 1.0

    @pytest.mark.asyncio
    async def test_error_handling_returns_error_dict(self) -> None:
        llm = _make_llm()
        llm.generate.side_effect = RuntimeError("LLM service unavailable")

        state = _make_state()
        result = await synthesize_strategy_node(state, llm)

        assert "error" in result
        assert "LLM error in synthesize_strategy_node" in result["error"]


# ---------------------------------------------------------------------------
# verify_citations_node
# ---------------------------------------------------------------------------


class TestVerifyCitationsNode:
    @pytest.mark.asyncio
    async def test_appends_warning_for_invalid_uuids(self) -> None:
        uid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        state = _make_state(strategy_memo=f"See case {uid} for details.")

        with patch(
            "app.core.agents.nodes.common.verify_case_ids",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = set()  # All IDs are invalid

            # Mock citation extraction to return empty (no human-readable citations)
            with patch(
                "app.core.agents.nodes.common.extract_citations_from_text",
                return_value=[],
            ):
                db = AsyncMock()
                result = await verify_citations_node(state, db)

        assert "Citation Verification Warning" in result["strategy_memo"]
        assert uid in result["strategy_memo"]

    @pytest.mark.asyncio
    async def test_passes_through_clean_memo_unchanged(self) -> None:
        state = _make_state(strategy_memo="This memo has no UUIDs or citations.")

        with patch(
            "app.core.agents.nodes.common.extract_citations_from_text",
            return_value=[],
        ):
            db = AsyncMock()
            result = await verify_citations_node(state, db)

        assert result["strategy_memo"] == "This memo has no UUIDs or citations."

    @pytest.mark.asyncio
    async def test_empty_memo_returns_empty(self) -> None:
        state = _make_state(strategy_memo="")
        db = AsyncMock()
        result = await verify_citations_node(state, db)

        assert result["strategy_memo"] == ""
        db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_valid_uuid_no_warning(self) -> None:
        uid = "12345678-1234-1234-1234-123456789abc"
        state = _make_state(strategy_memo=f"See case {uid} for details.")

        with patch(
            "app.core.agents.nodes.common.verify_case_ids",
            new_callable=AsyncMock,
        ) as mock_verify:
            mock_verify.return_value = {uid}  # UUID is valid

            with patch(
                "app.core.agents.nodes.common.extract_citations_from_text",
                return_value=[],
            ):
                db = AsyncMock()
                result = await verify_citations_node(state, db)

        assert "Citation Verification Warning" not in result["strategy_memo"]
        assert "Warning" not in result["strategy_memo"]

    @pytest.mark.asyncio
    async def test_unverified_human_citation_appends_warning(self) -> None:
        state = _make_state(strategy_memo="The court relied on (2099) 1 SCC 999 in this matter.")

        with (
            patch(
                "app.core.agents.nodes.common.extract_citations_from_text",
                return_value=["(2099) 1 SCC 999"],
            ),
            patch(
                "app.core.agents.nodes.common.verify_citations_against_db",
                new_callable=AsyncMock,
            ) as mock_verify_db,
            patch(
                "app.core.agents.nodes.common.check_grounding",
                return_value=[],
            ),
        ):
            mock_verify_db.return_value = ([], ["(2099) 1 SCC 999"])

            db = AsyncMock()
            result = await verify_citations_node(state, db)

        assert "Human-Readable Citation Warning" in result["strategy_memo"]
        assert "(2099) 1 SCC 999" in result["strategy_memo"]

    @pytest.mark.asyncio
    async def test_ungrounded_citation_appends_warning(self) -> None:
        state = _make_state(
            strategy_memo="The court relied on (2017) 10 SCC 1 in this matter.",
            search_results=[{"citation": "(2020) 5 SCC 200", "snippet": "different case"}],
        )

        with (
            patch(
                "app.core.agents.nodes.common.extract_citations_from_text",
                return_value=["(2017) 10 SCC 1"],
            ),
            patch(
                "app.core.agents.nodes.common.verify_citations_against_db",
                new_callable=AsyncMock,
            ) as mock_verify_db,
            patch(
                "app.core.agents.nodes.common.check_grounding",
                return_value=["(2017) 10 SCC 1"],
            ),
        ):
            mock_verify_db.return_value = (["(2017) 10 SCC 1"], [])

            db = AsyncMock()
            result = await verify_citations_node(state, db)

        assert "Ungrounded Citation Warning" in result["strategy_memo"]
        assert "(2017) 10 SCC 1" in result["strategy_memo"]

    @pytest.mark.asyncio
    async def test_grounded_verified_citation_no_warning(self) -> None:
        state = _make_state(
            strategy_memo="Relying on (2017) 10 SCC 1.",
            search_results=[{"citation": "(2017) 10 SCC 1", "snippet": ""}],
        )

        with (
            patch(
                "app.core.agents.nodes.common.extract_citations_from_text",
                return_value=["(2017) 10 SCC 1"],
            ),
            patch(
                "app.core.agents.nodes.common.verify_citations_against_db",
                new_callable=AsyncMock,
            ) as mock_verify_db,
            patch(
                "app.core.agents.nodes.common.check_grounding",
                return_value=[],
            ),
        ):
            mock_verify_db.return_value = (["(2017) 10 SCC 1"], [])

            db = AsyncMock()
            result = await verify_citations_node(state, db)

        assert "Warning" not in result["strategy_memo"]
