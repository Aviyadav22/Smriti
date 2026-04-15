"""Tests for opposing document parser."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from app.core.drafting.document_parser import (
    RESPONSE_TYPE_MAP,
    OpposingDocAnalysis,
    build_response_context,
    parse_opposing_document,
)


class TestResponseTypeMap:
    def test_plaint_maps_to_written_statement(self) -> None:
        assert RESPONSE_TYPE_MAP["plaint"] == "written_statement"

    def test_legal_notice_maps_to_reply(self) -> None:
        assert RESPONSE_TYPE_MAP["legal_notice"] == "reply_to_notice"

    def test_order_maps_to_appeal(self) -> None:
        assert RESPONSE_TYPE_MAP["order"] == "appeal"

    def test_bail_rejection_maps_to_bail_application(self) -> None:
        assert RESPONSE_TYPE_MAP["bail_rejection_order"] == "bail_application"

    def test_charge_sheet_maps_to_quashing(self) -> None:
        assert RESPONSE_TYPE_MAP["charge_sheet"] == "quashing_petition_482"

    def test_show_cause_notice_maps_to_reply(self) -> None:
        assert RESPONSE_TYPE_MAP["show_cause_notice"] == "reply_to_notice"

    def test_demand_notice_maps_to_reply(self) -> None:
        assert RESPONSE_TYPE_MAP["demand_notice"] == "reply_to_notice"


class TestParseOpposingDocument:
    @pytest.mark.asyncio
    async def test_parses_plaint_structure(self) -> None:
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = json.dumps(
            {
                "doc_type": "plaint",
                "parties": {"petitioner": "Suresh Sharma", "respondent": "Rajesh Kumar"},
                "court": "District Court, Karol Bagh",
                "case_number": "CS 123/2025",
                "date": "01.03.2025",
                "facts": ["Defendant sold goods on forged invoices", "Loss of Rs. 25 lakhs"],
                "reliefs_claimed": ["Recovery of Rs. 25 lakhs", "Interest at 18%"],
                "legal_provisions": ["Section 420 IPC", "Section 468 IPC"],
                "precedents_cited": ["Ram v. Shyam (2020) 5 SCC 100"],
                "key_arguments": ["Forged invoices constitute cheating"],
            }
        )

        result = await parse_opposing_document("Full plaint text here...", mock_llm)
        assert result.doc_type == "plaint"
        assert result.suggested_response_type == "written_statement"
        assert len(result.facts) == 2
        assert result.parties["petitioner"] == "Suresh Sharma"

    @pytest.mark.asyncio
    async def test_parses_order_structure(self) -> None:
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = json.dumps(
            {
                "doc_type": "order",
                "parties": {"petitioner": "State", "respondent": "Accused"},
                "court": "Sessions Court, Patiala House",
                "case_number": "SC 45/2025",
                "date": "15.02.2025",
                "facts": ["Bail was rejected"],
                "reliefs_claimed": [],
                "legal_provisions": ["Section 439 CrPC"],
                "precedents_cited": [],
                "key_arguments": [],
            }
        )

        result = await parse_opposing_document("Order text...", mock_llm)
        assert result.doc_type == "order"
        assert result.suggested_response_type == "appeal"

    @pytest.mark.asyncio
    async def test_handles_empty_text(self) -> None:
        mock_llm = AsyncMock()
        result = await parse_opposing_document("", mock_llm)
        assert result.doc_type == "unknown"
        mock_llm.generate.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_whitespace_only_text(self) -> None:
        mock_llm = AsyncMock()
        result = await parse_opposing_document("   \n\t  ", mock_llm)
        assert result.doc_type == "unknown"
        mock_llm.generate.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_llm_failure(self) -> None:
        mock_llm = AsyncMock()
        mock_llm.generate.side_effect = RuntimeError("LLM down")
        result = await parse_opposing_document("Some text", mock_llm)
        assert result.doc_type == "unknown"

    @pytest.mark.asyncio
    async def test_handles_invalid_json(self) -> None:
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "Not valid JSON at all"
        result = await parse_opposing_document("Some text", mock_llm)
        assert result.doc_type == "unknown"

    @pytest.mark.asyncio
    async def test_handles_json_in_code_fence(self) -> None:
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = '```json\n{"doc_type": "plaint"}\n```'
        result = await parse_opposing_document("Some text", mock_llm)
        assert result.doc_type == "plaint"

    @pytest.mark.asyncio
    async def test_truncates_long_text(self) -> None:
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = json.dumps({"doc_type": "plaint"})
        long_text = "A" * 50000
        await parse_opposing_document(long_text, mock_llm)
        prompt = mock_llm.generate.call_args.kwargs.get("prompt", "")
        assert len(prompt) < 45000  # Truncated

    @pytest.mark.asyncio
    async def test_stores_raw_text_truncated(self) -> None:
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = json.dumps({"doc_type": "plaint"})
        text = "B" * 10000
        result = await parse_opposing_document(text, mock_llm)
        assert len(result.raw_text) == 5000

    @pytest.mark.asyncio
    async def test_unknown_doc_type_has_no_suggested_response(self) -> None:
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = json.dumps({"doc_type": "unknown"})
        result = await parse_opposing_document("Some text", mock_llm)
        assert result.suggested_response_type == ""


class TestBuildResponseContext:
    def test_swaps_parties_for_response(self) -> None:
        analysis = OpposingDocAnalysis(
            parties={"petitioner": "Alice", "respondent": "Bob"},
        )
        ctx = build_response_context(analysis)
        assert ctx["respondent_details"] == "Alice"
        assert ctx["petitioner_details"] == "Bob"

    def test_builds_plaintiff_claims_from_facts(self) -> None:
        analysis = OpposingDocAnalysis(
            facts=["Fact one", "Fact two", "Fact three"],
        )
        ctx = build_response_context(analysis)
        assert "plaintiff_claims" in ctx
        assert "1. Fact one" in ctx["plaintiff_claims"]
        assert "3. Fact three" in ctx["plaintiff_claims"]

    def test_builds_impugned_order_for_appeals(self) -> None:
        analysis = OpposingDocAnalysis(
            doc_type="order",
            court="Delhi High Court",
            case_number="WP(C) 1234/2024",
            date="12.01.2025",
        )
        ctx = build_response_context(analysis)
        assert "impugned_order_details" in ctx
        assert "12.01.2025" in ctx["impugned_order_details"]
        assert ctx["lower_court_name"] == "Delhi High Court"

    def test_empty_analysis_returns_empty_context(self) -> None:
        analysis = OpposingDocAnalysis()
        ctx = build_response_context(analysis)
        assert isinstance(ctx, dict)
        assert len(ctx) == 0

    def test_sets_court_and_case_number(self) -> None:
        analysis = OpposingDocAnalysis(
            court="Bombay High Court",
            case_number="WP 100/2025",
        )
        ctx = build_response_context(analysis)
        assert ctx["court_name"] == "Bombay High Court"
        assert ctx["suit_number"] == "WP 100/2025"
        assert ctx["main_case_number"] == "WP 100/2025"

    def test_opposing_reliefs_joined(self) -> None:
        analysis = OpposingDocAnalysis(
            reliefs_claimed=["Rs 10 lakh damages", "Permanent injunction"],
        )
        ctx = build_response_context(analysis)
        assert "opposing_reliefs" in ctx
        assert "Rs 10 lakh damages" in ctx["opposing_reliefs"]
        assert "Permanent injunction" in ctx["opposing_reliefs"]

    def test_opposing_provisions_comma_separated(self) -> None:
        analysis = OpposingDocAnalysis(
            legal_provisions=["Section 420 IPC", "Section 468 IPC"],
        )
        ctx = build_response_context(analysis)
        assert ctx["opposing_provisions"] == "Section 420 IPC, Section 468 IPC"

    def test_no_impugned_order_for_non_order_type(self) -> None:
        analysis = OpposingDocAnalysis(
            doc_type="plaint",
            court="District Court",
            case_number="CS 1/2025",
            date="01.01.2025",
        )
        ctx = build_response_context(analysis)
        assert "impugned_order_details" not in ctx
        assert "lower_court_name" not in ctx
