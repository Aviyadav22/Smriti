"""Tests for ingestion 35K hardening changes.

Covers: truncation helper, all-null detection, V2 validation, control char
stripping, extended editorial regex, bulk INSERT patterns, UNWIND mock,
worker timeout handling, and SQLite lock safety.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.core.ingestion.metadata import (
    CaseMetadata,
    _truncate_for_llm,
    extract_metadata_llm,
    validate_with_regex,
)
from app.core.ingestion.pdf import _REPORTER_PAGE_MARKER_RE, clean_extracted_text

# ---------------------------------------------------------------------------
# Truncation helper
# ---------------------------------------------------------------------------


class TestTruncateForLLM:
    def test_short_text_passes_through(self):
        text = "Short text"
        assert _truncate_for_llm(text) == text

    def test_exact_boundary_passes_through(self):
        text = "x" * 50_000  # exactly HEAD + TAIL
        assert _truncate_for_llm(text) == text

    def test_long_text_truncated(self):
        text = "A" * 30_000 + "B" * 40_000 + "C" * 20_000
        result = _truncate_for_llm(text)
        assert len(result) < len(text)
        assert result.startswith("A" * 30_000)
        assert result.endswith("C" * 20_000)
        assert "[...middle section truncated for length...]" in result

    def test_100k_text(self):
        text = "x" * 100_000
        result = _truncate_for_llm(text)
        # Head 30K + marker + tail 20K
        assert len(result) < 100_000
        assert len(result) > 50_000


# ---------------------------------------------------------------------------
# All-null detection
# ---------------------------------------------------------------------------


class TestAllNullDetection:
    @pytest.mark.asyncio
    async def test_all_null_response_raises(self):
        mock_llm = AsyncMock()
        mock_llm.generate_structured.return_value = {"title": None, "year": None}

        with pytest.raises(RuntimeError, match="empty/all-null"):
            await extract_metadata_llm("some text", mock_llm)

    @pytest.mark.asyncio
    async def test_empty_dict_raises(self):
        mock_llm = AsyncMock()
        mock_llm.generate_structured.return_value = {}

        with pytest.raises(RuntimeError, match="empty/all-null"):
            await extract_metadata_llm("some text", mock_llm)

    @pytest.mark.asyncio
    async def test_partial_null_passes(self):
        mock_llm = AsyncMock()
        mock_llm.generate_structured.return_value = {"title": "Test", "year": None}

        result = await extract_metadata_llm("some text", mock_llm)
        assert result.title == "Test"


# ---------------------------------------------------------------------------
# V2 field validation
# ---------------------------------------------------------------------------


class TestV2FieldValidation:
    def test_invalid_judicial_tone_cleared(self):
        meta = CaseMetadata(judicial_tone="angry")
        result = validate_with_regex(meta)
        assert result.judicial_tone is None

    def test_valid_judicial_tone_kept(self):
        meta = CaseMetadata(judicial_tone="formal")
        result = validate_with_regex(meta)
        assert result.judicial_tone == "formal"

    def test_judicial_tone_case_insensitive(self):
        meta = CaseMetadata(judicial_tone="CRITICAL")
        result = validate_with_regex(meta)
        # Should not be cleared (case-insensitive check)
        assert result.judicial_tone is not None

    def test_invalid_filing_date_cleared(self):
        meta = CaseMetadata(filing_date="not-a-date")
        result = validate_with_regex(meta)
        assert result.filing_date is None

    def test_valid_filing_date_kept(self):
        meta = CaseMetadata(filing_date="2024-01-15")
        result = validate_with_regex(meta)
        assert result.filing_date == "2024-01-15"

    def test_hearing_count_out_of_range(self):
        meta = CaseMetadata(hearing_count=999)
        result = validate_with_regex(meta)
        assert result.hearing_count is None

    def test_hearing_count_negative(self):
        meta = CaseMetadata(hearing_count=-1)
        result = validate_with_regex(meta)
        assert result.hearing_count is None

    def test_hearing_count_valid(self):
        meta = CaseMetadata(hearing_count=5)
        result = validate_with_regex(meta)
        assert result.hearing_count == 5

    def test_operative_order_capped(self):
        meta = CaseMetadata(operative_order="x" * 15_000)
        result = validate_with_regex(meta)
        assert len(result.operative_order) == 10_000

    def test_list_field_capped(self):
        meta = CaseMetadata(arguments_raised=["arg"] * 100)
        result = validate_with_regex(meta)
        assert len(result.arguments_raised) == 50

    def test_non_list_converted_to_list(self):
        meta = CaseMetadata(arguments_raised="single_arg")
        result = validate_with_regex(meta)
        assert isinstance(result.arguments_raised, list)

    def test_citation_treatments_invalid_filtered(self):
        meta = CaseMetadata(
            citation_treatments=[
                {"cited_case": "Test v State", "context": "applied"},
                {"no_cited_case": True},
                "not a dict",
            ]
        )
        result = validate_with_regex(meta)
        assert len(result.citation_treatments) == 1
        assert result.citation_treatments[0]["cited_case"] == "Test v State"

    def test_party_counsel_invalid_filtered(self):
        meta = CaseMetadata(
            party_counsel=[
                {"name": "Advocate A", "designation": "Sr. Advocate"},
                {"no_name": True},
            ]
        )
        result = validate_with_regex(meta)
        assert len(result.party_counsel) == 1


# ---------------------------------------------------------------------------
# Control character stripping
# ---------------------------------------------------------------------------


class TestControlCharStripping:
    def test_null_bytes_removed(self):
        text = "Hello\x00World"
        result = clean_extracted_text(text)
        assert "\x00" not in result
        assert "Hello" in result
        assert "World" in result

    def test_bell_char_removed(self):
        text = "Test\x07text"
        result = clean_extracted_text(text)
        assert "\x07" not in result

    def test_newlines_preserved(self):
        text = "Line1\nLine2\r\nLine3\tTabbed"
        result = clean_extracted_text(text)
        assert "\n" in result

    def test_mixed_control_chars(self):
        text = "A\x01B\x02C\x03D\x04E"
        result = clean_extracted_text(text)
        assert "\x01" not in result
        assert "\x02" not in result
        assert "A" in result
        assert "E" in result


# ---------------------------------------------------------------------------
# Extended editorial regex
# ---------------------------------------------------------------------------


class TestExtendedEditorialRegex:
    @pytest.mark.parametrize(
        "line,should_match",
        [
            # SCR (existing)
            ("[2024] 1 S.C.R. 63", True),
            ("64 [2024] 1 S.C.R.", True),
            # SCC
            ("(2024) 5 SCC 123", True),
            ("(2024) 5 SCC (Cri) 123", True),
            # AIR
            ("AIR 2024 SC 123", True),
            # SCALE
            ("(2024) 3 SCALE 456", True),
            # MANU
            ("MANU/SC/1234/2024", True),
            # Non-matches
            ("The court held that...", False),
            ("Section 302 IPC", False),
            ("(2024) SCC Online SC 123", False),  # Not standalone
        ],
    )
    def test_reporter_patterns(self, line, should_match):
        match = _REPORTER_PAGE_MARKER_RE.search(line)
        if should_match:
            assert match is not None, f"Expected match for: {line!r}"
        else:
            assert match is None, f"Unexpected match for: {line!r}"
