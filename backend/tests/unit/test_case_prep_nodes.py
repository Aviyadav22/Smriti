"""Tests for Case Prep Agent node functions."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.agents.case_prep import route_after_load
from app.core.agents.nodes.common import safe_json_parse_list
from app.core.agents.nodes.case_prep_nodes import (
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
        "enhanced_memo": "",
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

        # Top-level error key must be set
        assert "error" in result
        assert "nonexistent" in result["error"]
        assert "upload and analyze" in result["error"]
        # Analysis should still have empty defaults
        assert "analysis" in result
        assert result["analysis"]["issues"] == []
        assert result["analysis"]["parties"] == {}
        assert result["analysis"]["key_facts"] == []
        assert result["analysis"]["relief_sought"] is None
        assert result["analysis"]["counter_arguments"] == []
        assert result["analysis"]["research_memo"] == ""

    @pytest.mark.asyncio
    async def test_no_error_key_when_analysis_exists(self) -> None:
        """When a row IS found, no top-level error key should be returned."""
        row = {
            "issues": "[]",
            "parties": "{}",
            "key_facts": "[]",
            "relief_sought": None,
            "counter_arguments": "[]",
            "research_memo": "",
        }
        db = _make_db_with_analysis_row(row)
        state = _make_state(document_id="doc-ok")

        result = await load_analysis_node(state, db)

        assert "error" not in result
        assert "analysis" in result

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
        assert result["enhanced_memo"].startswith("Memo with defaults.")

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

    @pytest.mark.asyncio
    async def test_human_citation_unverified_appends_warning(self) -> None:
        """A human-readable citation not in the DB should trigger a warning."""
        state = _make_state(
            enhanced_memo="The court relied on (2099) 1 SCC 999 in this matter."
        )

        no_match = MagicMock()
        no_match.first.return_value = None
        db = AsyncMock()
        db.execute.return_value = no_match

        result = await verify_citations_node(state, db)
        assert "Human-Readable Citation Warning" in result["enhanced_memo"]
        assert "(2099) 1 SCC 999" in result["enhanced_memo"]

    @pytest.mark.asyncio
    async def test_human_citation_verified_no_warning(self) -> None:
        """A human-readable citation found in the DB should NOT trigger a warning."""
        state = _make_state(
            enhanced_memo="The court relied on (2017) 10 SCC 1 in this matter.",
            messages=[
                {"type": "deep_precedents", "data": [
                    {"issue_title": "X", "results": [{"citation": "(2017) 10 SCC 1", "snippet": ""}]}
                ]}
            ],
        )

        match_result = MagicMock()
        match_result.first.return_value = (1,)
        db = AsyncMock()
        db.execute.return_value = match_result

        result = await verify_citations_node(state, db)
        assert "Human-Readable Citation Warning" not in result["enhanced_memo"]

    @pytest.mark.asyncio
    async def test_ungrounded_citation_appends_warning(self) -> None:
        """A citation in memo but not in search results should trigger ungrounded warning."""
        state = _make_state(
            enhanced_memo="The court relied on (2017) 10 SCC 1 in this matter.",
            messages=[
                {"type": "deep_precedents", "data": [
                    {"issue_title": "X", "results": [{"citation": "(2020) 5 SCC 200", "snippet": ""}]}
                ]}
            ],
        )

        match_result = MagicMock()
        match_result.first.return_value = (1,)
        db = AsyncMock()
        db.execute.return_value = match_result

        result = await verify_citations_node(state, db)
        assert "Ungrounded Citation Warning" in result["enhanced_memo"]
        assert "(2017) 10 SCC 1" in result["enhanced_memo"]

    @pytest.mark.asyncio
    async def test_grounded_citation_no_ungrounded_warning(self) -> None:
        """A citation present in both memo and search results should not be flagged."""
        state = _make_state(
            enhanced_memo="The court relied on (2017) 10 SCC 1 in this matter.",
            messages=[
                {"type": "deep_precedents", "data": [
                    {"issue_title": "X", "results": [{"citation": "(2017) 10 SCC 1", "snippet": ""}]}
                ]}
            ],
        )

        match_result = MagicMock()
        match_result.first.return_value = (1,)
        db = AsyncMock()
        db.execute.return_value = match_result

        result = await verify_citations_node(state, db)
        assert "Ungrounded Citation Warning" not in result["enhanced_memo"]


# ---------------------------------------------------------------------------
# safe_json_parse_list helper
# ---------------------------------------------------------------------------


class TestParseJsonList:
    def test_valid_json_array(self) -> None:
        assert safe_json_parse_list('[{"a": 1}]') == [{"a": 1}]

    def test_json_in_code_fence(self) -> None:
        raw = '```json\n[{"a": 1}]\n```'
        assert safe_json_parse_list(raw) == [{"a": 1}]

    def test_empty_array(self) -> None:
        assert safe_json_parse_list("[]") == []

    def test_garbage_returns_empty(self) -> None:
        assert safe_json_parse_list("no json here at all") == []


# ---------------------------------------------------------------------------
# route_after_load
# ---------------------------------------------------------------------------


class TestRouteAfterLoad:
    def test_routes_to_end_when_error_set(self) -> None:
        state = _make_state(error="No analysis found for document abc.")
        result = route_after_load(state)
        assert result == "__end__"

    def test_routes_to_prioritize_when_no_error(self) -> None:
        state = _make_state()
        result = route_after_load(state)
        assert result == "prioritize"

    def test_routes_to_prioritize_when_error_is_empty_string(self) -> None:
        state = _make_state(error="")
        result = route_after_load(state)
        assert result == "prioritize"


# ---------------------------------------------------------------------------
# Issue Score Labeling (Task 10)
# ---------------------------------------------------------------------------


class TestIssueScoreLabeling:
    """Tests for Task 10: AI-estimated score labeling."""

    @pytest.mark.asyncio
    async def test_prioritize_adds_score_note(self) -> None:
        """prioritize_issues_node should add score_note to each issue."""
        llm = _make_llm()
        llm.generate_structured.return_value = {
            "prioritized_issues": [
                {"title": "Issue 1", "composite_score": 8, "legal_strength": 7},
                {"title": "Issue 2", "composite_score": 5, "legal_strength": 4},
            ]
        }

        state = _make_state(analysis={
            "issues": [
                {"title": "Issue 1", "description": "test"},
                {"title": "Issue 2", "description": "test 2"},
            ],
            "parties": {},
            "relief_sought": "Damages",
        })

        result = await prioritize_issues_node(state, llm)
        issues = result["prioritized_issues"]
        assert len(issues) == 2
        for issue in issues:
            assert "score_note" in issue
            assert "AI-estimated" in issue["score_note"]

    @pytest.mark.asyncio
    async def test_deep_search_updates_score_note_no_results(self) -> None:
        """Issues with no matching precedents get a warning score_note."""
        state = _make_state(
            prioritized_issues=[
                {"title": "Unmatched Issue", "composite_score": 8, "legal_strength": 6,
                 "score_note": "AI-estimated"},
            ],
        )

        result = await deep_precedent_search_node(
            state, _make_llm(), AsyncMock(), AsyncMock(), AsyncMock(), AsyncMock(), AsyncMock()
        )

        issues = result["prioritized_issues"]
        assert len(issues) == 1
        # No precedent findings match this issue title, so score_note warns
        assert "No supporting precedents found" in issues[0]["score_note"]

    @pytest.mark.asyncio
    async def test_deep_search_boosts_legal_strength_with_binding(self) -> None:
        """3+ binding (Supreme Court) precedents should boost legal_strength."""
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
            FakeItem(case_id=f"c{i}", score=0.9, title=f"Case {i}",
                     court="Supreme Court of India")
            for i in range(4)
        ]

        graph_store = AsyncMock()
        graph_store.get_neighbors.return_value = {"center": "c0", "neighbors": []}

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
                {"title": "Constitutional validity", "description": "Art 14 challenge",
                 "composite_score": 8, "legal_strength": 6,
                 "score_note": "AI-estimated"},
            ])

            result = await deep_precedent_search_node(
                state, _make_llm(), AsyncMock(), AsyncMock(), AsyncMock(),
                graph_store, AsyncMock(),
            )

        issues = result["prioritized_issues"]
        assert issues[0]["legal_strength"] == 7  # boosted from 6 to 7
        assert "Validated" in issues[0]["score_note"]
        assert "binding precedents found" in issues[0]["score_note"]

    @pytest.mark.asyncio
    async def test_deep_search_partial_validation(self) -> None:
        """3+ results but fewer than 3 binding should give partial validation."""
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
            FakeItem(case_id="c1", score=0.9, court="Supreme Court of India"),
            FakeItem(case_id="c2", score=0.8, court="High Court of Delhi"),
            FakeItem(case_id="c3", score=0.7, court="High Court of Bombay"),
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
                {"title": "Contract breach", "description": "Breach of contract",
                 "composite_score": 7, "legal_strength": 5,
                 "score_note": "AI-estimated"},
            ])

            result = await deep_precedent_search_node(
                state, _make_llm(), AsyncMock(), AsyncMock(), AsyncMock(),
                graph_store, AsyncMock(),
            )

        issues = result["prioritized_issues"]
        assert "Partially validated" in issues[0]["score_note"]
        assert issues[0]["legal_strength"] == 5  # not boosted (only 1 binding)

    @pytest.mark.asyncio
    async def test_deep_search_limited_validation(self) -> None:
        """Fewer than 3 total results should give limited validation."""
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
            FakeItem(case_id="c1", score=0.9, court="High Court of Delhi"),
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
                {"title": "Tort claim", "description": "Negligence",
                 "composite_score": 6, "legal_strength": 4,
                 "score_note": "AI-estimated"},
            ])

            result = await deep_precedent_search_node(
                state, _make_llm(), AsyncMock(), AsyncMock(), AsyncMock(),
                graph_store, AsyncMock(),
            )

        issues = result["prioritized_issues"]
        assert "Limited validation" in issues[0]["score_note"]

    @pytest.mark.asyncio
    async def test_deep_search_returns_prioritized_issues_in_result(self) -> None:
        """deep_precedent_search_node should include prioritized_issues in its return dict."""
        state = _make_state(prioritized_issues=[
            {"title": "Issue X", "composite_score": 5, "legal_strength": 5,
             "score_note": "AI-estimated"},
        ])

        result = await deep_precedent_search_node(
            state, _make_llm(), AsyncMock(), AsyncMock(), AsyncMock(), AsyncMock(), AsyncMock()
        )

        assert "prioritized_issues" in result
        assert "messages" in result
