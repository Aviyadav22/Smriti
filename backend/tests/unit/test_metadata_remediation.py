"""Unit tests for metadata remediation: synthesis fallbacks and targeted re-extraction."""

import json
from unittest.mock import AsyncMock

import pytest

from app.core.ingestion.metadata import (
    CaseMetadata,
    reextract_missing_fields,
    synthesize_case_description,
    synthesize_outcome_summary,
)


class TestSynthesizeCaseDescription:
    """Tests for synthesize_case_description()."""

    def test_all_fields_produces_full_description(self):
        meta = CaseMetadata(
            title="State of UP v. Ram Kumar",
            case_type="Criminal Appeal",
            ratio_decidendi="The confession was not voluntary. It was obtained under duress.",
            disposal_nature="Allowed",
        )
        result = synthesize_case_description(meta)
        assert result is not None
        assert "Criminal Appeal" in result
        assert "State of UP v. Ram Kumar" in result
        assert "confession was not voluntary" in result
        assert "allowed" in result
        assert len(result) <= 500

    def test_only_title_returns_none(self):
        meta = CaseMetadata(title="State of UP v. Ram Kumar")
        result = synthesize_case_description(meta)
        assert result is None

    def test_no_title_returns_none(self):
        meta = CaseMetadata(
            ratio_decidendi="Some ratio",
            disposal_nature="Dismissed",
        )
        result = synthesize_case_description(meta)
        assert result is None

    def test_title_plus_disposal_produces_description(self):
        meta = CaseMetadata(
            title="ABC Corp v. DEF Ltd",
            disposal_nature="Dismissed",
        )
        result = synthesize_case_description(meta)
        assert result is not None
        assert "dismissed" in result
        assert "ABC Corp" in result

    def test_title_plus_headnotes_uses_proposition(self):
        headnotes = json.dumps([{"proposition": "The right to fair trial is a fundamental right."}])
        meta = CaseMetadata(
            title="State v. Accused",
            headnotes=headnotes,
        )
        result = synthesize_case_description(meta)
        assert result is not None
        assert "fair trial" in result

    def test_long_ratio_truncated(self):
        meta = CaseMetadata(
            title="Test Case",
            ratio_decidendi="A " * 300,  # 600 chars
            disposal_nature="Allowed",
        )
        result = synthesize_case_description(meta)
        assert result is not None
        assert len(result) <= 500

    def test_empty_headnotes_json_falls_through(self):
        meta = CaseMetadata(
            title="Test Case",
            headnotes="[]",
            disposal_nature="Allowed",
        )
        result = synthesize_case_description(meta)
        assert result is not None
        # Should still produce from disposal, not headnotes
        assert "allowed" in result


class TestSynthesizeOutcomeSummary:
    """Tests for synthesize_outcome_summary()."""

    def test_disposal_nature_produces_template(self):
        meta = CaseMetadata(
            case_type="Criminal Appeal",
            disposal_nature="Dismissed",
        )
        result = synthesize_outcome_summary(meta, "")
        assert result is not None
        assert "criminal appeal" in result.lower()
        assert "dismissed" in result.lower()

    def test_disposal_with_ratio_appends_ratio(self):
        meta = CaseMetadata(
            disposal_nature="Allowed",
            ratio_decidendi="The conviction was unsustainable in law. Further analysis follows.",
        )
        result = synthesize_outcome_summary(meta, "")
        assert result is not None
        assert "allowed" in result.lower()
        assert "conviction was unsustainable" in result

    def test_no_disposal_regex_from_text_tail(self):
        meta = CaseMetadata()
        text = "x " * 2000 + "In view of the above, the appeal is dismissed. No costs."
        result = synthesize_outcome_summary(meta, text)
        assert result is not None
        assert "dismissed" in result.lower()

    def test_no_disposal_no_match_returns_none(self):
        meta = CaseMetadata()
        text = "This is a judgment with no clear operative order."
        result = synthesize_outcome_summary(meta, text)
        assert result is None

    def test_regex_captures_partly_allowed(self):
        meta = CaseMetadata()
        text = "x " * 2000 + "The petition is partly allowed. Costs to be borne."
        result = synthesize_outcome_summary(meta, text)
        assert result is not None
        assert "partly allowed" in result.lower()

    def test_empty_text_returns_none(self):
        meta = CaseMetadata()
        result = synthesize_outcome_summary(meta, "")
        assert result is None

    def test_disposal_caps_at_300_chars(self):
        meta = CaseMetadata(
            disposal_nature="Dismissed",
            ratio_decidendi="A " * 300,
        )
        result = synthesize_outcome_summary(meta, "")
        assert result is not None
        assert len(result) <= 300

    def test_no_case_type_uses_generic_label(self):
        meta = CaseMetadata(disposal_nature="Allowed")
        result = synthesize_outcome_summary(meta, "")
        assert result is not None
        assert "case" in result.lower()


class TestReextractMissingFields:
    """Tests for reextract_missing_fields()."""

    @pytest.mark.asyncio
    async def test_successful_reextraction_sets_field(self):
        meta = CaseMetadata(title="Test")
        llm = AsyncMock()
        llm.generate_structured.return_value = {
            "case_description": "A case about property dispute.",
        }
        result = await reextract_missing_fields(
            meta, "Some text", llm, ["case_description"],
        )
        assert result.case_description == "A case about property dispute."

    @pytest.mark.asyncio
    async def test_llm_failure_returns_metadata_unchanged(self):
        meta = CaseMetadata(title="Test")
        llm = AsyncMock()
        llm.generate_structured.side_effect = RuntimeError("LLM error")
        result = await reextract_missing_fields(
            meta, "Some text", llm, ["case_description"],
        )
        assert result.case_description is None
        assert result.title == "Test"

    @pytest.mark.asyncio
    async def test_existing_field_not_overwritten(self):
        meta = CaseMetadata(
            title="Test",
            case_description="Original description",
        )
        llm = AsyncMock()
        llm.generate_structured.return_value = {
            "case_description": "New description from LLM",
        }
        result = await reextract_missing_fields(
            meta, "Some text", llm, ["case_description"],
        )
        assert result.case_description == "Original description"

    @pytest.mark.asyncio
    async def test_llm_returns_empty_dict(self):
        meta = CaseMetadata(title="Test")
        llm = AsyncMock()
        llm.generate_structured.return_value = {}
        result = await reextract_missing_fields(
            meta, "Some text", llm, ["outcome_summary"],
        )
        assert result.outcome_summary is None

    @pytest.mark.asyncio
    async def test_outcome_uses_text_tail(self):
        meta = CaseMetadata()
        llm = AsyncMock()
        llm.generate_structured.return_value = {
            "outcome_summary": "Appeal dismissed.",
        }
        long_text = "x" * 10000
        await reextract_missing_fields(
            meta, long_text, llm, ["outcome_summary"],
        )
        # Verify the prompt sent to LLM contains only the tail
        call_args = llm.generate_structured.call_args
        prompt = call_args.args[0] if call_args.args else call_args.kwargs.get("prompt", "")
        assert len(prompt) < 6000  # 5000 text + prompt prefix

    @pytest.mark.asyncio
    async def test_both_fields_uses_head_and_tail(self):
        meta = CaseMetadata()
        llm = AsyncMock()
        llm.generate_structured.return_value = {
            "case_description": "A dispute case.",
            "outcome_summary": "Dismissed.",
        }
        long_text = "x" * 10000
        result = await reextract_missing_fields(
            meta, long_text, llm, ["case_description", "outcome_summary"],
        )
        assert result.case_description == "A dispute case."
        assert result.outcome_summary == "Dismissed."

    @pytest.mark.asyncio
    async def test_llm_returns_null_value(self):
        meta = CaseMetadata()
        llm = AsyncMock()
        llm.generate_structured.return_value = {"outcome_summary": None}
        result = await reextract_missing_fields(
            meta, "text", llm, ["outcome_summary"],
        )
        assert result.outcome_summary is None
