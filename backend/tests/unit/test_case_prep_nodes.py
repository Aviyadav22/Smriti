"""Tests for Case Prep Agent node functions."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.agents.nodes.case_prep_nodes import (
    _parse_json_list,
    build_argument_order_node,
    deep_precedent_search_node,
    generate_strategy_memo_node,
    load_analysis_node,
    prioritize_issues_node,
    verify_citations_node,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(**overrides) -> dict:
    """Create a minimal CasePrepState dict with defaults."""
    base = {
        "document_id": "doc-001",
        "analysis": {},
        "prioritized_issues": [],
        "argument_order": [],
        "strategy_points": [],
        "enhanced_memo": "",
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


def _make_db_with_analysis_row(row_dict: dict) -> AsyncMock:
    """Create a mock AsyncSession that returns a single analysis row."""
    mock_mapping = MagicMock()
    mock_mapping.first.return_value = row_dict

    mock_result = MagicMock()
    mock_result.mappings.return_value = mock_mapping

    db = AsyncMock()
    db.execute.return_value = mock_result
    return db


def _make_db_no_results() -> AsyncMock:
    """Create a mock AsyncSession that returns no rows."""
    mock_mapping = MagicMock()
    mock_mapping.first.return_value = None

    mock_result = MagicMock()
    mock_result.mappings.return_value = mock_mapping

    db = AsyncMock()
    db.execute.return_value = mock_result
    return db


# ---------------------------------------------------------------------------
# load_analysis_node
# ---------------------------------------------------------------------------


class TestLoadAnalysisNode:
    @pytest.mark.asyncio
    async def test_loads_analysis_from_db(self) -> None:
        row = {
            "issues": json.dumps([{"title": "Issue 1", "description": "Desc 1"}]),
            "parties": json.dumps({"petitioner": "A", "respondent": "B"}),
            "key_facts": json.dumps(["Fact 1", "Fact 2"]),
            "relief_sought": "Injunction",
            "counter_arguments": json.dumps([{"argument": "counter 1"}]),
            "research_memo": "Memo text here",
        }
        db = _make_db_with_analysis_row(row)
        state = _make_state(document_id="doc-123")

        result = await load_analysis_node(state, db)

        assert "analysis" in result
        analysis = result["analysis"]
        assert len(analysis["issues"]) == 1
        assert analysis["issues"][0]["title"] == "Issue 1"
        assert analysis["parties"]["petitioner"] == "A"
        assert analysis["relief_sought"] == "Injunction"
        assert analysis["research_memo"] == "Memo text here"

    @pytest.mark.asyncio
    async def test_returns_error_when_not_found(self) -> None:
        db = _make_db_no_results()
        state = _make_state(document_id="nonexistent")

        result = await load_analysis_node(state, db)

        assert "analysis" in result
        assert "error" in result["analysis"]
        assert result["analysis"]["issues"] == []

    @pytest.mark.asyncio
    async def test_handles_dict_fields_already_parsed(self) -> None:
        """Fields that are already dicts/lists should pass through."""
        row = {
            "issues": [{"title": "Issue A", "description": "Desc A"}],
            "parties": {"petitioner": "X"},
            "key_facts": ["Fact"],
            "relief_sought": None,
            "counter_arguments": [],
            "research_memo": "",
        }
        db = _make_db_with_analysis_row(row)
        state = _make_state()

        result = await load_analysis_node(state, db)
        assert result["analysis"]["issues"][0]["title"] == "Issue A"


# ---------------------------------------------------------------------------
# prioritize_issues_node
# ---------------------------------------------------------------------------


class TestPrioritizeIssuesNode:
    @pytest.mark.asyncio
    async def test_returns_prioritized_issues_sorted(self) -> None:
        llm = _make_llm()
        llm.generate_structured.return_value = {
            "prioritized_issues": [
                {
                    "title": "Issue B",
                    "description": "Low priority",
                    "strength_score": 3,
                    "relevance_score": 4,
                    "trend_score": 3,
                    "strategic_value": 2,
                    "composite_score": 3.0,
                    "reasoning": "Weak precedent",
                },
                {
                    "title": "Issue A",
                    "description": "High priority",
                    "strength_score": 9,
                    "relevance_score": 8,
                    "trend_score": 7,
                    "strategic_value": 8,
                    "composite_score": 8.0,
                    "reasoning": "Strong precedent",
                },
            ]
        }

        state = _make_state(analysis={
            "issues": [
                {"title": "Issue A", "description": "High priority"},
                {"title": "Issue B", "description": "Low priority"},
            ],
            "parties": {"petitioner": "X"},
            "relief_sought": "Damages",
        })

        result = await prioritize_issues_node(state, llm)

        assert "prioritized_issues" in result
        issues = result["prioritized_issues"]
        assert len(issues) == 2
        # Should be sorted by composite_score descending
        assert issues[0]["title"] == "Issue A"
        assert issues[0]["composite_score"] == 8.0
        assert issues[1]["title"] == "Issue B"

    @pytest.mark.asyncio
    async def test_empty_issues_returns_empty(self) -> None:
        llm = _make_llm()
        state = _make_state(analysis={"issues": []})

        result = await prioritize_issues_node(state, llm)
        assert result["prioritized_issues"] == []
        llm.generate_structured.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_passes_prompt_with_issues(self) -> None:
        llm = _make_llm()
        llm.generate_structured.return_value = {"prioritized_issues": []}

        state = _make_state(analysis={
            "issues": [{"title": "Test Issue", "description": "A test"}],
            "parties": {},
            "relief_sought": None,
        })

        await prioritize_issues_node(state, llm)

        call_kwargs = llm.generate_structured.call_args
        prompt = call_kwargs.kwargs.get("prompt", "")
        assert "Test Issue" in prompt


# ---------------------------------------------------------------------------
# deep_precedent_search_node
# ---------------------------------------------------------------------------


class TestDeepPrecedentSearchNode:
    @pytest.mark.asyncio
    async def test_searches_top_3_issues(self) -> None:
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
            FakeItem(case_id="c1", score=0.9, title="Case One"),
        ]

        graph_store = AsyncMock()
        graph_store.get_neighbors.return_value = {"center": "c1", "neighbors": []}

        with patch(
            "app.core.agents.nodes.case_prep_nodes.hybrid_search",
            new_callable=AsyncMock,
        ) as mock_search, patch(
            "app.core.agents.nodes.case_prep_nodes.enrich_results_with_ratio",
            new_callable=AsyncMock,
            side_effect=lambda results, db, **kw: results,
        ):
            mock_search.return_value = mock_response

            state = _make_state(prioritized_issues=[
                {"title": "Issue 1", "description": "Desc 1", "composite_score": 9},
                {"title": "Issue 2", "description": "Desc 2", "composite_score": 7},
                {"title": "Issue 3", "description": "Desc 3", "composite_score": 5},
                {"title": "Issue 4", "description": "Desc 4", "composite_score": 3},
            ])
            llm = _make_llm()

            result = await deep_precedent_search_node(
                state, llm, AsyncMock(), AsyncMock(), AsyncMock(), graph_store, AsyncMock()
            )

            # Should search only top 3
            assert mock_search.await_count == 3

        assert "messages" in result
        msg = result["messages"][0]
        assert msg["type"] == "deep_precedents"
        assert len(msg["data"]) == 3

    @pytest.mark.asyncio
    async def test_empty_prioritized_issues(self) -> None:
        state = _make_state(prioritized_issues=[])
        result = await deep_precedent_search_node(
            state, _make_llm(), AsyncMock(), AsyncMock(), AsyncMock(), AsyncMock(), AsyncMock()
        )
        assert result["messages"][0]["data"] == []

    @pytest.mark.asyncio
    async def test_merges_graph_neighbors(self) -> None:
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
            FakeItem(case_id="c1", score=0.9, title="Case One"),
        ]

        graph_store = AsyncMock()
        # Use the ACTUAL Neo4j return format: {"center": ..., "neighbors": [{"node": {...}, "relationship": ...}]}
        graph_store.get_neighbors.return_value = {
            "center": "c1",
            "neighbors": [
                {"node": {"id": "c2", "title": "Neighbor Case", "citation": "SCC 2"}, "relationship": "CITES"},
                {"node": {"id": "c1", "title": "Case One"}, "relationship": "CITES"},  # duplicate - should be filtered
            ]
        }

        with patch(
            "app.core.agents.nodes.case_prep_nodes.hybrid_search",
            new_callable=AsyncMock,
        ) as mock_search, patch(
            "app.core.agents.nodes.case_prep_nodes.enrich_results_with_ratio",
            new_callable=AsyncMock,
            side_effect=lambda results, db, **kw: results,
        ):
            mock_search.return_value = mock_response

            state = _make_state(prioritized_issues=[
                {"title": "Issue 1", "description": "Desc 1"},
            ])

            result = await deep_precedent_search_node(
                state, _make_llm(), AsyncMock(), AsyncMock(), AsyncMock(),
                graph_store, AsyncMock(),
            )

        findings = result["messages"][0]["data"]
        assert len(findings) == 1
        issue_results = findings[0]["results"]
        # c1 from search + c2 from graph (c1 duplicate filtered)
        assert len(issue_results) == 2
        case_ids = {r.get("case_id") for r in issue_results}
        assert "c1" in case_ids
        assert "c2" in case_ids

    @pytest.mark.asyncio
    async def test_graph_neighbor_metadata_extracted_correctly(self) -> None:
        """Verify metadata (title, citation, court) is correctly extracted from nested Neo4j format."""
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
            FakeItem(case_id="c1", score=0.9, title="Case One"),
        ]

        graph_store = AsyncMock()
        graph_store.get_neighbors.return_value = {
            "center": "c1",
            "neighbors": [
                {
                    "node": {
                        "id": "c2",
                        "title": "State of Punjab v. Singh",
                        "citation": "(2023) 5 SCC 100",
                        "court": "Supreme Court of India",
                        "year": 2023,
                    },
                    "relationship": "CITES",
                },
            ],
        }

        with patch(
            "app.core.agents.nodes.case_prep_nodes.hybrid_search",
            new_callable=AsyncMock,
        ) as mock_search, patch(
            "app.core.agents.nodes.case_prep_nodes.enrich_results_with_ratio",
            new_callable=AsyncMock,
            side_effect=lambda results, db, **kw: results,
        ):
            mock_search.return_value = mock_response

            state = _make_state(prioritized_issues=[
                {"title": "Issue 1", "description": "Desc 1"},
            ])

            result = await deep_precedent_search_node(
                state, _make_llm(), AsyncMock(), AsyncMock(), AsyncMock(),
                graph_store, AsyncMock(),
            )

        findings = result["messages"][0]["data"]
        issue_results = findings[0]["results"]
        # Find the graph-sourced result
        graph_results = [r for r in issue_results if r.get("source") == "citation_graph"]
        assert len(graph_results) == 1
        gr = graph_results[0]
        assert gr["case_id"] == "c2"
        assert gr["title"] == "State of Punjab v. Singh"
        assert gr["citation"] == "(2023) 5 SCC 100"
        assert gr["court"] == "Supreme Court of India"
        assert gr["year"] == 2023
        assert gr["score"] == 0.0
        assert gr["source"] == "citation_graph"


# ---------------------------------------------------------------------------
# build_argument_order_node
# ---------------------------------------------------------------------------


class TestBuildArgumentOrderNode:
    @pytest.mark.asyncio
    async def test_returns_ordered_arguments(self) -> None:
        ordered = [
            {
                "position": 1,
                "issue_title": "Jurisdiction",
                "role": "primary",
                "rationale": "Must establish first",
                "preliminary": True,
            },
            {
                "position": 2,
                "issue_title": "Merits",
                "role": "primary",
                "rationale": "Core argument",
                "preliminary": False,
            },
        ]
        llm = _make_llm()
        llm.generate.return_value = json.dumps(ordered)

        state = _make_state(
            prioritized_issues=[
                {"title": "Jurisdiction", "composite_score": 8},
                {"title": "Merits", "composite_score": 9},
            ],
            messages=[{"type": "deep_precedents", "data": []}],
        )

        result = await build_argument_order_node(state, llm)

        assert "argument_order" in result
        assert len(result["argument_order"]) == 2
        assert result["argument_order"][0]["position"] == 1

    @pytest.mark.asyncio
    async def test_fallback_when_llm_returns_unparseable(self) -> None:
        llm = _make_llm()
        llm.generate.return_value = "I cannot generate a proper JSON response."

        state = _make_state(
            prioritized_issues=[
                {"title": "Issue A", "composite_score": 8},
                {"title": "Issue B", "composite_score": 5},
            ],
        )

        result = await build_argument_order_node(state, llm)

        # Should fall back to ordering by prioritized issues
        assert len(result["argument_order"]) == 2
        assert result["argument_order"][0]["issue_title"] == "Issue A"
        assert result["argument_order"][0]["role"] == "primary"

    @pytest.mark.asyncio
    async def test_empty_prioritized_issues_and_unparseable(self) -> None:
        llm = _make_llm()
        llm.generate.return_value = "No issues to order."

        state = _make_state(prioritized_issues=[])

        result = await build_argument_order_node(state, llm)
        assert result["argument_order"] == []


# ---------------------------------------------------------------------------
# generate_strategy_memo_node
# ---------------------------------------------------------------------------


class TestGenerateStrategyMemoNode:
    @pytest.mark.asyncio
    async def test_generates_memo(self) -> None:
        llm = _make_llm()
        llm.generate.return_value = "# Strategy Memo\n\nThis is the strategy."

        state = _make_state(
            analysis={
                "parties": {"petitioner": "A", "respondent": "B"},
                "relief_sought": "Injunction",
                "counter_arguments": [{"arg": "c1"}],
            },
            prioritized_issues=[{"title": "Issue 1", "composite_score": 8}],
            argument_order=[{"position": 1, "issue_title": "Issue 1"}],
            messages=[{"type": "deep_precedents", "data": [{"issue_title": "Issue 1", "results": []}]}],
        )

        result = await generate_strategy_memo_node(state, llm)

        assert "enhanced_memo" in result
        assert "Strategy Memo" in result["enhanced_memo"]

    @pytest.mark.asyncio
    async def test_handles_missing_analysis_fields(self) -> None:
        llm = _make_llm()
        llm.generate.return_value = "Memo with defaults."

        state = _make_state(analysis={})

        result = await generate_strategy_memo_node(state, llm)
        assert result["enhanced_memo"] == "Memo with defaults."

    @pytest.mark.asyncio
    async def test_passes_precedent_findings_to_prompt(self) -> None:
        llm = _make_llm()
        llm.generate.return_value = "Memo."

        state = _make_state(
            analysis={"parties": {}, "relief_sought": None, "counter_arguments": []},
            messages=[
                {"type": "deep_precedents", "data": [{"issue_title": "X", "results": [{"case_id": "c1"}]}]}
            ],
        )

        await generate_strategy_memo_node(state, llm)

        call_kwargs = llm.generate.call_args
        prompt = call_kwargs.kwargs.get("prompt", "")
        assert "c1" in prompt


# ---------------------------------------------------------------------------
# verify_citations_node
# ---------------------------------------------------------------------------


class TestVerifyCitationsNode:
    @pytest.mark.asyncio
    async def test_no_uuids_returns_unchanged_memo(self) -> None:
        state = _make_state(enhanced_memo="This memo has no UUIDs.")
        db = AsyncMock()
        result = await verify_citations_node(state, db)
        assert result["enhanced_memo"] == "This memo has no UUIDs."

    @pytest.mark.asyncio
    async def test_valid_uuids_no_warning(self) -> None:
        uid = "12345678-1234-1234-1234-123456789abc"
        state = _make_state(enhanced_memo=f"See case {uid} for details.")

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [(uid,)]
        db = AsyncMock()
        db.execute.return_value = mock_result

        result = await verify_citations_node(state, db)
        assert "Warning" not in result["enhanced_memo"]

    @pytest.mark.asyncio
    async def test_invalid_uuids_appends_warning(self) -> None:
        uid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        state = _make_state(enhanced_memo=f"See case {uid} for details.")

        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        db = AsyncMock()
        db.execute.return_value = mock_result

        result = await verify_citations_node(state, db)
        assert "Citation Verification Warning" in result["enhanced_memo"]
        assert uid in result["enhanced_memo"]

    @pytest.mark.asyncio
    async def test_empty_memo_returns_empty(self) -> None:
        state = _make_state(enhanced_memo="")
        db = AsyncMock()
        result = await verify_citations_node(state, db)
        assert result["enhanced_memo"] == ""


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
