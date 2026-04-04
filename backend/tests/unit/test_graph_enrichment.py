"""Tests for Neo4j enrichment from PostgreSQL metadata.

Tests cover:
- enrich_neo4j_from_postgres: writes correct properties, handles missing fields
- create_issue_topic_nodes: creates IssueTopic nodes and CLASSIFIED_AS edges
- create_statute_section_nodes: creates StatuteSection nodes and INTERPRETS edges
"""

from __future__ import annotations

from unittest.mock import AsyncMock, call

import pytest

from scripts.compute_graph_analytics import (
    _extract_headnote_text,
    create_issue_topic_nodes,
    create_statute_section_nodes,
    enrich_neo4j_from_postgres,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_graph_store() -> AsyncMock:
    store = AsyncMock()
    store.query = AsyncMock(return_value=[])
    return store


# ---------------------------------------------------------------------------
# _extract_headnote_text
# ---------------------------------------------------------------------------


class TestExtractHeadnoteText:
    def test_none_returns_empty(self) -> None:
        assert _extract_headnote_text(None) == ""

    def test_empty_list(self) -> None:
        assert _extract_headnote_text([]) == ""

    def test_list_of_dicts_proposition(self) -> None:
        headnotes = [{"proposition": "The court held that..."}]
        assert _extract_headnote_text(headnotes) == "The court held that..."

    def test_list_of_dicts_text_key(self) -> None:
        headnotes = [{"text": "Some headnote text"}]
        assert _extract_headnote_text(headnotes) == "Some headnote text"

    def test_list_of_strings(self) -> None:
        headnotes = ["First headnote", "Second headnote"]
        assert _extract_headnote_text(headnotes) == "First headnote"

    def test_json_string_parsed(self) -> None:
        import json
        headnotes = json.dumps([{"proposition": "Parsed from JSON"}])
        assert _extract_headnote_text(headnotes) == "Parsed from JSON"

    def test_plain_string_fallback(self) -> None:
        assert _extract_headnote_text("just a string") == "just a string"

    def test_truncates_to_500(self) -> None:
        long_text = "x" * 600
        headnotes = [{"proposition": long_text}]
        result = _extract_headnote_text(headnotes)
        assert len(result) == 500

    def test_dict_headnote(self) -> None:
        headnotes = {"headnote": "Single dict headnote"}
        assert _extract_headnote_text(headnotes) == "Single dict headnote"


# ---------------------------------------------------------------------------
# enrich_neo4j_from_postgres
# ---------------------------------------------------------------------------


class TestEnrichNeo4jFromPostgres:
    @pytest.mark.asyncio()
    async def test_empty_rows_returns_zero(self, mock_graph_store: AsyncMock) -> None:
        result = await enrich_neo4j_from_postgres(mock_graph_store, [])
        assert result == 0
        mock_graph_store.query.assert_not_called()

    @pytest.mark.asyncio()
    async def test_writes_correct_properties(self, mock_graph_store: AsyncMock) -> None:
        pg_rows = [
            {
                "id": "case-001",
                "jurisdiction": "Supreme Court of India",
                "coram_size": 3,
                "is_reportable": True,
                "opinion_type": "majority",
                "issue_classification": ["criminal_law.murder", "criminal_law.bail"],
                "primary_legal_issue": "Whether the accused is guilty of murder",
                "fact_pattern_summary": "The accused was charged with murder",
                "headnotes": [{"proposition": "Murder requires intent"}],
            }
        ]

        result = await enrich_neo4j_from_postgres(mock_graph_store, pg_rows)

        assert result == 1
        mock_graph_store.query.assert_called_once()
        call_args = mock_graph_store.query.call_args
        params = call_args.kwargs.get("params") or call_args[1].get("params")
        batch = params["rows"]
        assert len(batch) == 1

        row = batch[0]
        assert row["id"] == "case-001"
        assert row["jurisdiction"] == "Supreme Court of India"
        assert row["coram_size"] == 3
        assert row["is_reportable"] is True
        assert row["opinion_type"] == "majority"
        assert "criminal_law.murder" in row["issue_tags"]
        assert "criminal_law.bail" in row["issue_tags"]
        assert row["primary_legal_issue"] == "Whether the accused is guilty of murder"
        assert row["fact_pattern_summary"] == "The accused was charged with murder"
        assert row["headnote_text"] == "Murder requires intent"

    @pytest.mark.asyncio()
    async def test_handles_missing_fields(self, mock_graph_store: AsyncMock) -> None:
        pg_rows = [{"id": "case-002"}]

        result = await enrich_neo4j_from_postgres(mock_graph_store, pg_rows)

        assert result == 1
        call_args = mock_graph_store.query.call_args
        params = call_args.kwargs.get("params") or call_args[1].get("params")
        row = params["rows"][0]
        assert row["jurisdiction"] == ""
        assert row["coram_size"] == 0
        assert row["is_reportable"] is False
        assert row["opinion_type"] == ""
        assert row["issue_tags"] == ""
        assert row["primary_legal_issue"] == ""
        assert row["fact_pattern_summary"] == ""
        assert row["headnote_text"] == ""

    @pytest.mark.asyncio()
    async def test_truncates_long_fields(self, mock_graph_store: AsyncMock) -> None:
        pg_rows = [
            {
                "id": "case-003",
                "primary_legal_issue": "x" * 300,
                "fact_pattern_summary": "y" * 600,
            }
        ]

        await enrich_neo4j_from_postgres(mock_graph_store, pg_rows)

        call_args = mock_graph_store.query.call_args
        params = call_args.kwargs.get("params") or call_args[1].get("params")
        row = params["rows"][0]
        assert len(row["primary_legal_issue"]) == 200
        assert len(row["fact_pattern_summary"]) == 500

    @pytest.mark.asyncio()
    async def test_batches_large_input(self, mock_graph_store: AsyncMock) -> None:
        pg_rows = [{"id": f"case-{i}"} for i in range(1200)]

        result = await enrich_neo4j_from_postgres(mock_graph_store, pg_rows)

        assert result == 1200
        # 1200 / 500 = 3 batches (500 + 500 + 200)
        assert mock_graph_store.query.call_count == 3

    @pytest.mark.asyncio()
    async def test_normalizes_issue_tags(self, mock_graph_store: AsyncMock) -> None:
        """Variant tags should be normalized to canonical forms."""
        pg_rows = [
            {
                "id": "case-norm",
                "issue_classification": ["criminal.murder", "fundamental_rights.article_21"],
            }
        ]

        await enrich_neo4j_from_postgres(mock_graph_store, pg_rows)

        call_args = mock_graph_store.query.call_args
        params = call_args.kwargs.get("params") or call_args[1].get("params")
        row = params["rows"][0]
        assert "criminal_law.murder" in row["issue_tags"]
        assert "constitutional_law.article_21" in row["issue_tags"]


# ---------------------------------------------------------------------------
# create_issue_topic_nodes
# ---------------------------------------------------------------------------


class TestCreateIssueTopicNodes:
    @pytest.mark.asyncio()
    async def test_empty_rows_returns_zero(self, mock_graph_store: AsyncMock) -> None:
        result = await create_issue_topic_nodes(mock_graph_store, [])
        assert result == 0

    @pytest.mark.asyncio()
    async def test_creates_topic_nodes_and_edges(self, mock_graph_store: AsyncMock) -> None:
        pg_rows = [
            {
                "id": "case-001",
                "issue_classification": ["criminal_law.murder", "criminal_law.bail"],
            }
        ]

        result = await create_issue_topic_nodes(mock_graph_store, pg_rows)

        assert result == 2
        mock_graph_store.query.assert_called_once()
        call_args = mock_graph_store.query.call_args
        params = call_args.kwargs.get("params") or call_args[1].get("params")
        batch = params["rows"]
        assert len(batch) == 2

        # Verify first row
        assert batch[0]["case_id"] == "case-001"
        assert batch[0]["tag"] == "criminal_law.murder"
        assert batch[0]["category"] == "Criminal Law"
        assert batch[0]["subtopic"] == "murder"

        # Verify second row
        assert batch[1]["tag"] == "criminal_law.bail"
        assert batch[1]["subtopic"] == "bail"

    @pytest.mark.asyncio()
    async def test_skips_cases_without_tags(self, mock_graph_store: AsyncMock) -> None:
        pg_rows = [
            {"id": "case-no-tags", "issue_classification": None},
            {"id": "case-empty", "issue_classification": []},
        ]

        result = await create_issue_topic_nodes(mock_graph_store, pg_rows)
        assert result == 0
        mock_graph_store.query.assert_not_called()

    @pytest.mark.asyncio()
    async def test_normalizes_variant_tags(self, mock_graph_store: AsyncMock) -> None:
        pg_rows = [
            {"id": "case-v", "issue_classification": ["criminal.murder"]},
        ]

        result = await create_issue_topic_nodes(mock_graph_store, pg_rows)

        assert result == 1
        call_args = mock_graph_store.query.call_args
        params = call_args.kwargs.get("params") or call_args[1].get("params")
        assert params["rows"][0]["tag"] == "criminal_law.murder"

    @pytest.mark.asyncio()
    async def test_unknown_tag_gets_other_category(self, mock_graph_store: AsyncMock) -> None:
        pg_rows = [
            {"id": "case-u", "issue_classification": ["unknown_area.something"]},
        ]

        await create_issue_topic_nodes(mock_graph_store, pg_rows)

        call_args = mock_graph_store.query.call_args
        params = call_args.kwargs.get("params") or call_args[1].get("params")
        assert params["rows"][0]["category"] == "Other"

    @pytest.mark.asyncio()
    async def test_cypher_contains_merge_classified_as(self, mock_graph_store: AsyncMock) -> None:
        pg_rows = [{"id": "c1", "issue_classification": ["criminal_law.murder"]}]

        await create_issue_topic_nodes(mock_graph_store, pg_rows)

        cypher = mock_graph_store.query.call_args.args[0]
        assert "MERGE (t:IssueTopic" in cypher
        assert "CLASSIFIED_AS" in cypher


# ---------------------------------------------------------------------------
# create_statute_section_nodes
# ---------------------------------------------------------------------------


class TestCreateStatuteSectionNodes:
    @pytest.mark.asyncio()
    async def test_empty_rows_returns_zero(self, mock_graph_store: AsyncMock) -> None:
        result = await create_statute_section_nodes(mock_graph_store, [])
        assert result == 0

    @pytest.mark.asyncio()
    async def test_creates_statute_nodes_and_edges(self, mock_graph_store: AsyncMock) -> None:
        statute_rows = [
            {
                "case_id": "case-001",
                "section": "Section 302",
                "act": "Indian Penal Code",
                "interpretation_summary": "Murder is punishable with death or life imprisonment",
            }
        ]

        result = await create_statute_section_nodes(mock_graph_store, statute_rows)

        assert result == 1
        mock_graph_store.query.assert_called_once()
        call_args = mock_graph_store.query.call_args
        params = call_args.kwargs.get("params") or call_args[1].get("params")
        batch = params["rows"]

        assert batch[0]["case_id"] == "case-001"
        assert batch[0]["section"] == "Section 302"
        assert batch[0]["act"] == "Indian Penal Code"
        assert batch[0]["section_id"] == "indian_penal_code_section_302"
        assert "Murder is punishable" in batch[0]["interpretation"]

    @pytest.mark.asyncio()
    async def test_section_id_normalization(self, mock_graph_store: AsyncMock) -> None:
        statute_rows = [
            {
                "case_id": "c1",
                "section": "Section 34, 120B",
                "act": "Indian Penal Code",
                "interpretation_summary": "",
            }
        ]

        await create_statute_section_nodes(mock_graph_store, statute_rows)

        call_args = mock_graph_store.query.call_args
        params = call_args.kwargs.get("params") or call_args[1].get("params")
        sid = params["rows"][0]["section_id"]
        assert " " not in sid
        assert "," not in sid
        assert sid == "indian_penal_code_section_34_120b"

    @pytest.mark.asyncio()
    async def test_skips_empty_section_and_act(self, mock_graph_store: AsyncMock) -> None:
        statute_rows = [
            {"case_id": "c1", "section": "", "act": "", "interpretation_summary": ""},
            {"case_id": "c2", "section": None, "act": None, "interpretation_summary": None},
        ]

        result = await create_statute_section_nodes(mock_graph_store, statute_rows)
        assert result == 0
        mock_graph_store.query.assert_not_called()

    @pytest.mark.asyncio()
    async def test_truncates_interpretation(self, mock_graph_store: AsyncMock) -> None:
        statute_rows = [
            {
                "case_id": "c1",
                "section": "S.302",
                "act": "IPC",
                "interpretation_summary": "z" * 600,
            }
        ]

        await create_statute_section_nodes(mock_graph_store, statute_rows)

        call_args = mock_graph_store.query.call_args
        params = call_args.kwargs.get("params") or call_args[1].get("params")
        assert len(params["rows"][0]["interpretation"]) == 500

    @pytest.mark.asyncio()
    async def test_cypher_contains_merge_interprets(self, mock_graph_store: AsyncMock) -> None:
        statute_rows = [
            {"case_id": "c1", "section": "S.1", "act": "Act", "interpretation_summary": ""},
        ]

        await create_statute_section_nodes(mock_graph_store, statute_rows)

        cypher = mock_graph_store.query.call_args.args[0]
        assert "MERGE (s:StatuteSection" in cypher
        assert "INTERPRETS" in cypher

    @pytest.mark.asyncio()
    async def test_batches_large_input(self, mock_graph_store: AsyncMock) -> None:
        statute_rows = [
            {"case_id": f"c-{i}", "section": f"S.{i}", "act": "IPC", "interpretation_summary": ""}
            for i in range(1100)
        ]

        result = await create_statute_section_nodes(mock_graph_store, statute_rows)

        assert result == 1100
        # 1100 / 500 = 3 batches (500 + 500 + 100)
        assert mock_graph_store.query.call_count == 3
