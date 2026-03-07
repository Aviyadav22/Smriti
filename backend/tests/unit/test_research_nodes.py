"""Tests for Research Agent node functions."""
from __future__ import annotations

import json
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.agents.confidence import calculate_confidence
from app.core.agents.nodes.research_nodes import (
    _parse_json_list,
    classify_query_node,
    decompose_query_node,
    detect_contradictions_node,
    gather_results_node,
    parallel_search_node,
    synthesize_memo_node,
    verify_citations_node,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(**overrides) -> dict:
    """Create a minimal ResearchState dict with defaults."""
    base = {
        "query": "Is Section 498A IPC constitutional?",
        "sub_queries": [],
        "search_results": [],
        "cross_references": [],
        "contradictions": [],
        "draft_memo": "",
        "confidence": 0.0,
        "messages": [],
        "iteration": 0,
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
# classify_query_node
# ---------------------------------------------------------------------------


class TestClassifyQueryNode:
    @pytest.mark.asyncio
    async def test_returns_classification_in_messages(self) -> None:
        classification = {
            "topic": "criminal",
            "complexity": "moderate",
            "key_entities": ["Section 498A", "IPC"],
            "search_hints": ["dowry harassment", "cruelty by husband"],
        }
        llm = _make_llm()
        llm.generate_structured.return_value = classification

        state = _make_state()
        result = await classify_query_node(state, llm)

        assert "messages" in result
        assert len(result["messages"]) == 1
        msg = result["messages"][0]
        assert msg["type"] == "classification"
        assert msg["data"] == classification

    @pytest.mark.asyncio
    async def test_passes_query_as_prompt(self) -> None:
        llm = _make_llm()
        llm.generate_structured.return_value = {"topic": "civil", "complexity": "simple", "key_entities": [], "search_hints": []}

        state = _make_state(query="limitation period for civil suits")
        await classify_query_node(state, llm)

        call_kwargs = llm.generate_structured.call_args
        assert "limitation period for civil suits" in call_kwargs.kwargs.get("prompt", call_kwargs.args[0] if call_kwargs.args else "")


# ---------------------------------------------------------------------------
# decompose_query_node
# ---------------------------------------------------------------------------


class TestDecomposeQueryNode:
    @pytest.mark.asyncio
    async def test_returns_sub_queries(self) -> None:
        llm = _make_llm()
        llm.generate_structured.return_value = {
            "sub_queries": [
                {"query": "Section 498A IPC provisions", "aspect": "statutory", "rationale": "Need the statute text"},
                {"query": "498A constitutional validity Supreme Court", "aspect": "precedent", "rationale": "Key rulings"},
            ]
        }

        state = _make_state(
            messages=[{"type": "classification", "data": {"topic": "criminal", "complexity": "moderate"}}]
        )
        result = await decompose_query_node(state, llm)

        assert "sub_queries" in result
        assert len(result["sub_queries"]) == 2
        assert result["sub_queries"][0] == "Section 498A IPC provisions"

    @pytest.mark.asyncio
    async def test_empty_sub_queries_returns_empty_list(self) -> None:
        llm = _make_llm()
        llm.generate_structured.return_value = {"sub_queries": []}

        state = _make_state()
        result = await decompose_query_node(state, llm)
        assert result["sub_queries"] == []

    @pytest.mark.asyncio
    async def test_includes_user_feedback_in_prompt(self) -> None:
        """When user_feedback with step='plan' exists, the prompt sent to the LLM must contain it."""
        llm = _make_llm()
        llm.generate_structured.return_value = {
            "sub_queries": [{"query": "criminal law 498A", "aspect": "criminal", "rationale": "r"}]
        }

        state = _make_state(
            messages=[
                {"type": "classification", "data": {"topic": "criminal", "complexity": "moderate"}},
                {"type": "user_feedback", "step": "plan", "content": "Focus on criminal law only"},
            ]
        )
        result = await decompose_query_node(state, llm)

        # Verify the LLM received the feedback in the prompt
        call_kwargs = llm.generate_structured.call_args
        prompt_sent = call_kwargs.kwargs.get("prompt", call_kwargs.args[0] if call_kwargs.args else "")
        assert "Focus on criminal law only" in prompt_sent

    @pytest.mark.asyncio
    async def test_no_user_feedback_prompt_unchanged(self) -> None:
        """Without user_feedback, the prompt should NOT contain feedback instructions."""
        llm = _make_llm()
        llm.generate_structured.return_value = {
            "sub_queries": [{"query": "test", "aspect": "general", "rationale": "r"}]
        }

        state = _make_state(
            messages=[{"type": "classification", "data": {"topic": "criminal"}}]
        )
        await decompose_query_node(state, llm)

        call_kwargs = llm.generate_structured.call_args
        prompt_sent = call_kwargs.kwargs.get("prompt", call_kwargs.args[0] if call_kwargs.args else "")
        assert "user has reviewed" not in prompt_sent

    @pytest.mark.asyncio
    async def test_ignores_feedback_for_other_steps(self) -> None:
        """user_feedback with step != 'plan' should be ignored by decompose_query_node."""
        llm = _make_llm()
        llm.generate_structured.return_value = {
            "sub_queries": [{"query": "test", "aspect": "general", "rationale": "r"}]
        }

        state = _make_state(
            messages=[
                {"type": "classification", "data": {"topic": "criminal"}},
                {"type": "user_feedback", "step": "findings", "content": "This should be ignored"},
            ]
        )
        await decompose_query_node(state, llm)

        call_kwargs = llm.generate_structured.call_args
        prompt_sent = call_kwargs.kwargs.get("prompt", call_kwargs.args[0] if call_kwargs.args else "")
        assert "This should be ignored" not in prompt_sent

    @pytest.mark.asyncio
    async def test_handles_missing_classification_gracefully(self) -> None:
        llm = _make_llm()
        llm.generate_structured.return_value = {
            "sub_queries": [{"query": "test query", "aspect": "general", "rationale": "r"}]
        }

        state = _make_state(messages=[])
        result = await decompose_query_node(state, llm)
        assert len(result["sub_queries"]) == 1


# ---------------------------------------------------------------------------
# parallel_search_node
# ---------------------------------------------------------------------------


class TestParallelSearchNode:
    @pytest.mark.asyncio
    async def test_runs_search_for_each_sub_query(self) -> None:
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
            FakeItem(case_id="c1", score=0.9, title="Case One", snippet="snippet one"),
        ]

        with patch("app.core.agents.nodes.research_nodes.hybrid_search", new_callable=AsyncMock) as mock_search, \
             patch("app.core.agents.nodes.research_nodes.enrich_results_with_ratio", new_callable=AsyncMock) as mock_enrich:
            mock_search.return_value = mock_response
            mock_enrich.side_effect = lambda results, db: results

            state = _make_state(sub_queries=["query A", "query B"])
            llm = _make_llm()
            embedder = AsyncMock()
            vector_store = AsyncMock()
            reranker = AsyncMock()
            db = AsyncMock()

            result = await parallel_search_node(state, llm, embedder, vector_store, reranker, db)

            assert mock_search.await_count == 2
            assert "search_results" in result
            # 2 sub-queries each returning 1 result
            assert len(result["search_results"]) == 2
            assert result["search_results"][0]["case_id"] == "c1"
            assert result["search_results"][0]["source_query"] == "query A"

    @pytest.mark.asyncio
    async def test_empty_sub_queries_returns_empty(self) -> None:
        state = _make_state(sub_queries=[])
        result = await parallel_search_node(state, _make_llm(), AsyncMock(), AsyncMock(), AsyncMock(), AsyncMock())
        assert result == {"search_results": []}

    @pytest.mark.asyncio
    async def test_handles_search_failure_gracefully(self) -> None:
        with patch("app.core.agents.nodes.research_nodes.hybrid_search", new_callable=AsyncMock) as mock_search:
            mock_search.side_effect = RuntimeError("search down")

            state = _make_state(sub_queries=["q1"])
            result = await parallel_search_node(state, _make_llm(), AsyncMock(), AsyncMock(), AsyncMock(), AsyncMock())
            assert result["search_results"] == []


# ---------------------------------------------------------------------------
# gather_results_node
# ---------------------------------------------------------------------------


class TestGatherResultsNode:
    @pytest.mark.asyncio
    async def test_identifies_cross_references(self) -> None:
        results = [
            {"case_id": "c1", "score": 0.9, "title": "Case 1", "citation": "SCC 1", "source_query": "q1"},
            {"case_id": "c1", "score": 0.8, "title": "Case 1", "citation": "SCC 1", "source_query": "q2"},
            {"case_id": "c2", "score": 0.7, "title": "Case 2", "citation": "SCC 2", "source_query": "q1"},
        ]
        state = _make_state(search_results=results)
        result = await gather_results_node(state)

        assert "cross_references" in result
        assert len(result["cross_references"]) == 1
        assert result["cross_references"][0]["case_id"] == "c1"
        assert result["cross_references"][0]["match_count"] == 2

    @pytest.mark.asyncio
    async def test_no_cross_references_when_unique(self) -> None:
        results = [
            {"case_id": "c1", "score": 0.9, "source_query": "q1"},
            {"case_id": "c2", "score": 0.8, "source_query": "q2"},
        ]
        state = _make_state(search_results=results)
        result = await gather_results_node(state)
        assert result["cross_references"] == []

    @pytest.mark.asyncio
    async def test_empty_results(self) -> None:
        state = _make_state(search_results=[])
        result = await gather_results_node(state)
        assert result["cross_references"] == []

    @pytest.mark.asyncio
    async def test_cross_refs_sorted_by_match_count(self) -> None:
        results = [
            {"case_id": "c1", "score": 0.9, "title": "C1", "source_query": "q1"},
            {"case_id": "c1", "score": 0.8, "title": "C1", "source_query": "q2"},
            {"case_id": "c2", "score": 0.7, "title": "C2", "source_query": "q1"},
            {"case_id": "c2", "score": 0.6, "title": "C2", "source_query": "q2"},
            {"case_id": "c2", "score": 0.5, "title": "C2", "source_query": "q3"},
        ]
        state = _make_state(search_results=results)
        result = await gather_results_node(state)
        assert len(result["cross_references"]) == 2
        assert result["cross_references"][0]["case_id"] == "c2"  # 3 matches > 2


# ---------------------------------------------------------------------------
# detect_contradictions_node
# ---------------------------------------------------------------------------


class TestDetectContradictionsNode:
    @pytest.mark.asyncio
    async def test_parses_contradictions_from_llm(self) -> None:
        contradictions = [
            {
                "case_a": "Case Alpha",
                "case_b": "Case Beta",
                "description": "Different holdings on bail",
                "resolution": "Case Alpha is binding (larger bench)",
            }
        ]
        llm = _make_llm()
        llm.generate.return_value = json.dumps(contradictions)

        state = _make_state(search_results=[
            {"title": "Case Alpha", "citation": "SCC 1", "court": "SC", "year": 2020, "snippet": "bail granted"},
            {"title": "Case Beta", "citation": "SCC 2", "court": "SC", "year": 2021, "snippet": "bail denied"},
        ])
        result = await detect_contradictions_node(state, llm)

        assert len(result["contradictions"]) == 1
        assert result["contradictions"][0]["case_a"] == "Case Alpha"

    @pytest.mark.asyncio
    async def test_empty_results_returns_empty(self) -> None:
        state = _make_state(search_results=[])
        result = await detect_contradictions_node(state, _make_llm())
        assert result["contradictions"] == []

    @pytest.mark.asyncio
    async def test_handles_llm_returning_no_contradictions(self) -> None:
        llm = _make_llm()
        llm.generate.return_value = "[]"

        state = _make_state(search_results=[{"title": "T", "snippet": "s"}])
        result = await detect_contradictions_node(state, llm)
        assert result["contradictions"] == []


# ---------------------------------------------------------------------------
# synthesize_memo_node
# ---------------------------------------------------------------------------


class TestSynthesizeMemoNode:
    @pytest.mark.asyncio
    async def test_returns_memo_and_confidence(self) -> None:
        llm = _make_llm()
        llm.generate.return_value = "# Research Memo\n\nThis is the synthesized memo."

        state = _make_state(
            search_results=[{"title": f"C{i}", "snippet": "s", "case_id": f"id{i}"} for i in range(5)],
            cross_references=[{"case_id": "id1", "title": "C1", "citation": "X", "match_count": 2}],
            contradictions=[],
        )
        result = await synthesize_memo_node(state, llm)

        assert "draft_memo" in result
        assert "confidence" in result
        assert "Research Memo" in result["draft_memo"]
        assert 0.0 < result["confidence"] <= 1.0

    @pytest.mark.asyncio
    async def test_zero_results_gives_zero_confidence(self) -> None:
        llm = _make_llm()
        llm.generate.return_value = "No findings."

        state = _make_state(search_results=[], cross_references=[], contradictions=[])
        result = await synthesize_memo_node(state, llm)
        assert result["confidence"] == 0.0

    @pytest.mark.asyncio
    async def test_many_results_high_confidence(self) -> None:
        llm = _make_llm()
        llm.generate.return_value = "Memo text."

        state = _make_state(
            search_results=[{"title": f"C{i}", "snippet": "s", "score": 0.9} for i in range(15)],
            sub_queries=["q1", "q2", "q3"],
            cross_references=[
                {"case_id": f"id{i}", "title": f"C{i}", "citation": "X", "match_count": 3}
                for i in range(5)
            ],
            contradictions=[],
        )
        result = await synthesize_memo_node(state, llm)
        assert result["confidence"] >= 0.6

    @pytest.mark.asyncio
    async def test_precedent_strengths_populated_from_results(self) -> None:
        """When results have bench_type and court, calculate_confidence receives non-empty precedent_strengths."""
        llm = _make_llm()
        llm.generate.return_value = "Memo with SC precedents."

        state = _make_state(
            search_results=[
                {
                    "title": "Kesavananda Bharati",
                    "snippet": "basic structure",
                    "score": 0.95,
                    "case_id": "id1",
                    "court": "Supreme Court of India",
                    "bench_type": "constitutional",
                },
                {
                    "title": "Maneka Gandhi",
                    "snippet": "right to travel",
                    "score": 0.90,
                    "case_id": "id2",
                    "court": "Supreme Court of India",
                    "bench_type": "division",
                },
                {
                    "title": "No Bench Info",
                    "snippet": "unknown bench",
                    "score": 0.80,
                    "case_id": "id3",
                    "court": "Supreme Court of India",
                    # No bench_type -- should be skipped
                },
            ],
            cross_references=[],
            contradictions=[],
        )

        with patch("app.core.agents.nodes.research_nodes.calculate_confidence", wraps=calculate_confidence) as spy:
            result = await synthesize_memo_node(state, llm)

            spy.assert_called_once()
            call_kwargs = spy.call_args
            strengths = call_kwargs.kwargs.get("precedent_strengths") or call_kwargs[1].get("precedent_strengths", [])
            # If called positionally:
            if not strengths and call_kwargs.args:
                strengths = call_kwargs.args[2]  # 3rd positional arg

            assert len(strengths) == 2, f"Expected 2 strengths (skipping result with no bench_type), got {strengths}"
            assert all(s in ("BINDING", "PERSUASIVE", "DISTINGUISHABLE", "OVERRULED") for s in strengths)

    @pytest.mark.asyncio
    async def test_sc_constitutional_bench_yields_binding(self) -> None:
        """A Supreme Court constitutional bench result should produce BINDING strength."""
        llm = _make_llm()
        llm.generate.return_value = "Memo."

        state = _make_state(
            search_results=[
                {
                    "title": "Constitution Bench Case",
                    "snippet": "text",
                    "score": 0.95,
                    "case_id": "id1",
                    "court": "Supreme Court of India",
                    "bench_type": "constitutional",
                },
            ],
            cross_references=[],
            contradictions=[],
        )

        with patch("app.core.agents.nodes.research_nodes.calculate_confidence", wraps=calculate_confidence) as spy:
            await synthesize_memo_node(state, llm)

            call_kwargs = spy.call_args
            strengths = call_kwargs.kwargs.get("precedent_strengths") or call_kwargs[1].get("precedent_strengths", [])
            if not strengths and call_kwargs.args:
                strengths = call_kwargs.args[2]

            assert strengths == ["BINDING"]

    @pytest.mark.asyncio
    async def test_confidence_higher_with_binding_precedents(self) -> None:
        """Confidence with BINDING precedents should be higher than the default 0.3 authority."""
        llm = _make_llm()
        llm.generate.return_value = "Memo."

        # Results with bench_type for real precedent strengths
        results_with_bench = [
            {"title": f"C{i}", "snippet": "s", "score": 0.85, "case_id": f"id{i}",
             "court": "Supreme Court of India", "bench_type": "constitutional"}
            for i in range(5)
        ]
        state_with = _make_state(
            search_results=results_with_bench,
            cross_references=[],
            contradictions=[],
        )
        result_with = await synthesize_memo_node(state_with, llm)

        # Results without bench_type (falls back to authority=0.3)
        results_without_bench = [
            {"title": f"C{i}", "snippet": "s", "score": 0.85, "case_id": f"id{i}"}
            for i in range(5)
        ]
        state_without = _make_state(
            search_results=results_without_bench,
            cross_references=[],
            contradictions=[],
        )
        result_without = await synthesize_memo_node(state_without, llm)

        # BINDING (1.0) > default (0.3), so confidence should be higher
        assert result_with["confidence"] > result_without["confidence"]


# ---------------------------------------------------------------------------
# verify_citations_node
# ---------------------------------------------------------------------------


class TestVerifyCitationsNode:
    @pytest.mark.asyncio
    async def test_no_uuids_returns_unchanged_memo(self) -> None:
        state = _make_state(draft_memo="This memo has no UUIDs.")
        db = AsyncMock()
        result = await verify_citations_node(state, db)
        assert result["draft_memo"] == "This memo has no UUIDs."

    @pytest.mark.asyncio
    async def test_valid_uuids_no_warning(self) -> None:
        uid = "12345678-1234-1234-1234-123456789abc"
        state = _make_state(draft_memo=f"See case {uid} for details.")

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [(uid,)]
        db = AsyncMock()
        db.execute.return_value = mock_result

        result = await verify_citations_node(state, db)
        assert "Warning" not in result["draft_memo"]

    @pytest.mark.asyncio
    async def test_invalid_uuids_appends_warning(self) -> None:
        uid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        state = _make_state(draft_memo=f"See case {uid} for details.")

        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        db = AsyncMock()
        db.execute.return_value = mock_result

        result = await verify_citations_node(state, db)
        assert "Citation Verification Warning" in result["draft_memo"]
        assert uid in result["draft_memo"]

    @pytest.mark.asyncio
    async def test_empty_memo_returns_empty(self) -> None:
        state = _make_state(draft_memo="")
        db = AsyncMock()
        result = await verify_citations_node(state, db)
        assert result["draft_memo"] == ""


# ---------------------------------------------------------------------------
# _parse_json_list helper
# ---------------------------------------------------------------------------


class TestParseJsonList:
    def test_valid_json_array(self) -> None:
        assert _parse_json_list('[{"a": 1}]') == [{"a": 1}]

    def test_json_in_code_fence(self) -> None:
        raw = '```json\n[{"a": 1}]\n```'
        assert _parse_json_list(raw) == [{"a": 1}]

    def test_empty_array(self) -> None:
        assert _parse_json_list("[]") == []

    def test_garbage_returns_empty(self) -> None:
        assert _parse_json_list("no json here at all") == []

    def test_json_with_surrounding_text(self) -> None:
        raw = 'Here are the results:\n[{"x": 1}]\nEnd.'
        assert _parse_json_list(raw) == [{"x": 1}]
