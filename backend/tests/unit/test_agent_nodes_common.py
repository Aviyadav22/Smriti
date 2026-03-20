"""Tests for agent node common utilities."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.agents.nodes.common import (
    enrich_results_with_ratio,
    format_search_results_for_llm,
    verify_case_ids,
)


# ---------------------------------------------------------------------------
# format_search_results_for_llm
# ---------------------------------------------------------------------------


class TestFormatSearchResultsForLlm:
    def test_empty_results_returns_no_results_message(self) -> None:
        assert format_search_results_for_llm([]) == "No results found."

    def test_single_result_formatted_correctly(self) -> None:
        results = [
            {
                "title": "State v. Sharma",
                "citation": "(2023) 5 SCC 100",
                "court": "Supreme Court of India",
                "year": 2023,
                "snippet": "The court held that fundamental rights are paramount.",
            }
        ]
        output = format_search_results_for_llm(results)
        assert "[1]" in output
        assert "State v. Sharma" in output
        assert "(2023) 5 SCC 100" in output
        assert "Supreme Court of India" in output
        assert "2023" in output
        assert "fundamental rights are paramount" in output

    def test_multiple_results_numbered(self) -> None:
        results = [
            {"title": f"Case {i}", "citation": f"cite-{i}", "court": "SC", "year": 2020, "snippet": "x"}
            for i in range(3)
        ]
        output = format_search_results_for_llm(results)
        assert "[1]" in output
        assert "[2]" in output
        assert "[3]" in output

    def test_snippet_truncated_to_max_len(self) -> None:
        long_snippet = "A" * 1000
        results = [{"title": "T", "snippet": long_snippet}]
        output = format_search_results_for_llm(results, max_snippet_len=50)
        # The snippet in output should be at most 50 chars of A
        assert "A" * 50 in output
        assert "A" * 51 not in output

    def test_missing_fields_use_defaults(self) -> None:
        results = [{}]
        output = format_search_results_for_llm(results)
        assert "Untitled" in output
        assert "No citation" in output
        assert "Unknown" in output

    def test_none_snippet_handled(self) -> None:
        results = [{"title": "T", "snippet": None}]
        output = format_search_results_for_llm(results)
        assert "T" in output


# ---------------------------------------------------------------------------
# format_search_results_for_llm — enriched fields
# ---------------------------------------------------------------------------


class TestFormatSearchResultsEnriched:
    def test_includes_ratio_field(self) -> None:
        results = [
            {
                "title": "State v. Kumar",
                "citation": "(2022) 3 SCC 50",
                "court": "Supreme Court of India",
                "year": 2022,
                "snippet": "Brief passage.",
                "ratio": "The principle of natural justice must be followed in all quasi-judicial proceedings.",
            }
        ]
        output = format_search_results_for_llm(results)
        assert "Ratio Decidendi:" in output
        assert "natural justice" in output

    def test_includes_bench_type(self) -> None:
        results = [
            {
                "title": "Union v. Rao",
                "citation": "(2021) 1 SCC 200",
                "court": "Supreme Court of India",
                "year": 2021,
                "snippet": "Some text.",
                "bench_type": "division",
            }
        ]
        output = format_search_results_for_llm(results)
        assert "Division Bench" in output
        assert "Supreme Court of India (Division Bench)" in output

    def test_no_ratio_still_works(self) -> None:
        results = [
            {
                "title": "A v. B",
                "citation": "(2020) 2 SCC 10",
                "court": "High Court",
                "year": 2020,
                "snippet": "The court observed something.",
            }
        ]
        output = format_search_results_for_llm(results)
        assert "Ratio Decidendi:" not in output
        assert "Relevant Passage:" in output
        assert "The court observed something." in output


# ---------------------------------------------------------------------------
# enrich_results_with_ratio
# ---------------------------------------------------------------------------


class TestEnrichResultsWithRatio:
    @pytest.mark.asyncio
    async def test_enriches_results_with_ratio(self) -> None:
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            ("case-1", "Natural justice applies to all tribunals.", "division"),
        ]
        db = AsyncMock()
        db.execute.return_value = mock_result

        results = [{"case_id": "case-1", "title": "Test Case"}]
        enriched = await enrich_results_with_ratio(results, db)

        assert enriched[0]["ratio"] == "Natural justice applies to all tribunals."
        assert enriched[0]["bench_type"] == "division"

    @pytest.mark.asyncio
    async def test_enriches_bench_type(self) -> None:
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            ("case-2", "", "constitutional"),
        ]
        db = AsyncMock()
        db.execute.return_value = mock_result

        results = [{"case_id": "case-2", "title": "Bench Case"}]
        enriched = await enrich_results_with_ratio(results, db)

        assert enriched[0]["bench_type"] == "constitutional"

    @pytest.mark.asyncio
    async def test_empty_results_returns_empty(self) -> None:
        db = AsyncMock()
        enriched = await enrich_results_with_ratio([], db)
        assert enriched == []
        db.execute.assert_not_called()


# ---------------------------------------------------------------------------
# verify_case_ids
# ---------------------------------------------------------------------------


class TestVerifyCaseIds:
    @pytest.mark.asyncio
    async def test_empty_list_returns_empty_set(self) -> None:
        db = AsyncMock()
        result = await verify_case_ids([], db)
        assert result == set()
        db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_existing_ids(self) -> None:
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("id-1",), ("id-3",)]
        db = AsyncMock()
        db.execute.return_value = mock_result

        result = await verify_case_ids(["id-1", "id-2", "id-3"], db)
        assert result == {"id-1", "id-3"}
        db.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_matches_returns_empty_set(self) -> None:
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        db = AsyncMock()
        db.execute.return_value = mock_result

        result = await verify_case_ids(["id-999"], db)
        assert result == set()


# ---------------------------------------------------------------------------
# [V3] _extract_statute_refs
# ---------------------------------------------------------------------------


class TestExtractStatuteRefs:
    def test_extracts_section_ipc(self) -> None:
        from app.core.agents.nodes.common import _extract_statute_refs

        refs = _extract_statute_refs("punishment under Section 302 IPC")
        assert ("IPC", "302") in refs

    def test_extracts_section_bns(self) -> None:
        from app.core.agents.nodes.common import _extract_statute_refs

        refs = _extract_statute_refs("Section 103 BNS applies here")
        assert ("BNS", "103") in refs

    def test_extracts_article(self) -> None:
        from app.core.agents.nodes.common import _extract_statute_refs

        refs = _extract_statute_refs("violates Article 21 of the Constitution")
        assert ("COI", "21") in refs

    def test_extracts_multiple(self) -> None:
        from app.core.agents.nodes.common import _extract_statute_refs

        refs = _extract_statute_refs(
            "Section 302 IPC read with Section 34 IPC and Article 21"
        )
        assert ("IPC", "302") in refs
        assert ("IPC", "34") in refs
        assert ("COI", "21") in refs

    def test_no_refs_returns_empty(self) -> None:
        from app.core.agents.nodes.common import _extract_statute_refs

        refs = _extract_statute_refs("general principle of natural justice")
        assert refs == []

    def test_case_insensitive(self) -> None:
        from app.core.agents.nodes.common import _extract_statute_refs

        refs = _extract_statute_refs("section 302 ipc")
        assert ("IPC", "302") in refs


# ---------------------------------------------------------------------------
# [V3] _expand_refs
# ---------------------------------------------------------------------------


class TestExpandRefs:
    def test_expands_old_to_new(self) -> None:
        from app.core.agents.nodes.common import _expand_refs

        refs = [("IPC", "302")]
        expanded = _expand_refs(refs)
        assert ("IPC", "302") in expanded
        assert ("BNS", "103") in expanded

    def test_expands_new_to_old(self) -> None:
        from app.core.agents.nodes.common import _expand_refs

        refs = [("BNS", "103")]
        expanded = _expand_refs(refs)
        assert ("BNS", "103") in expanded
        assert ("IPC", "302") in expanded

    def test_no_mapping_returns_original(self) -> None:
        from app.core.agents.nodes.common import _expand_refs

        refs = [("COI", "21")]
        expanded = _expand_refs(refs)
        assert ("COI", "21") in expanded
        assert len(expanded) == 1

    def test_crpc_to_bnss(self) -> None:
        from app.core.agents.nodes.common import _expand_refs

        refs = [("CrPC", "41")]
        expanded = _expand_refs(refs)
        assert ("CrPC", "41") in expanded
        # CrPC 41 maps to BNSS 35
        assert ("BNSS", "35") in expanded


# ---------------------------------------------------------------------------
# [V3] statute_lookup_node
# ---------------------------------------------------------------------------


class TestStatuteLookupNode:
    @pytest.mark.asyncio
    async def test_extracts_and_fetches_statutes(self) -> None:
        from app.core.agents.nodes.common import statute_lookup_node

        mock_db = AsyncMock()
        mock_embedder = AsyncMock()
        mock_vector_store = AsyncMock()
        mock_vector_store.search.return_value = []

        state = {
            "rewritten_query": "punishment for murder under Section 302 IPC",
            "key_entities": ["Section 302 IPC"],
        }

        with patch(
            "app.core.agents.nodes.common._fetch_statute_from_db",
            new_callable=AsyncMock,
            return_value=[{
                "act_short_name": "IPC",
                "section_number": "302",
                "section_title": "Punishment for murder",
                "section_text": "Whoever commits murder...",
                "is_repealed": True,
                "replaced_by": "BNS, Section 103",
                "new_code_text": "Whoever commits murder...",
            }],
        ):
            result = await statute_lookup_node(
                state, mock_db, mock_embedder, mock_vector_store
            )

        assert "statute_context" in result
        assert len(result["statute_context"]) >= 1
        assert result["statute_context"][0]["act_short_name"] == "IPC"

    @pytest.mark.asyncio
    async def test_empty_query_no_refs(self) -> None:
        from app.core.agents.nodes.common import statute_lookup_node

        mock_db = AsyncMock()
        mock_embedder = AsyncMock()
        mock_vector_store = AsyncMock()
        mock_vector_store.search.return_value = []

        state = {
            "rewritten_query": "general principle of natural justice",
            "key_entities": ["natural justice"],
        }

        with patch(
            "app.core.agents.nodes.common._fetch_statute_from_db",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await statute_lookup_node(
                state, mock_db, mock_embedder, mock_vector_store
            )

        assert "statute_context" in result
        assert isinstance(result["statute_context"], list)

    @pytest.mark.asyncio
    async def test_semantic_results_merged(self) -> None:
        """Pinecone semantic results should be merged if not already in DB results."""
        from app.core.agents.nodes.common import statute_lookup_node

        mock_db = AsyncMock()
        mock_embedder = AsyncMock()
        mock_embedder.embed_text.return_value = [0.1] * 1536
        mock_vector_store = AsyncMock()
        mock_vector_store.search.return_value = [
            {
                "metadata": {
                    "act_short_name": "CPC",
                    "section_number": "9",
                    "section_title": "Courts to try all civil suits",
                    "text": "The Courts shall...",
                },
                "score": 0.85,
            }
        ]

        state = {
            "rewritten_query": "jurisdiction of civil courts Section 9 CPC",
            "key_entities": [],
        }

        with patch(
            "app.core.agents.nodes.common._fetch_statute_from_db",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await statute_lookup_node(
                state, mock_db, mock_embedder, mock_vector_store
            )

        assert any(
            s["act_short_name"] == "CPC" and s["section_number"] == "9"
            for s in result["statute_context"]
        )
