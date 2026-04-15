"""Tests for extract_metadata_llm (G9).

Verifies that the LLM extraction function:
- Succeeds on first try
- Does NOT retry internally (retries handled by pipeline-level tenacity)
- Returns empty CaseMetadata on non-transient errors (ValueError, KeyError)
- Propagates transient errors for pipeline-level retry
"""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.core.ingestion.metadata import extract_metadata_llm

_SAMPLE_TEXT = (
    "IN THE SUPREME COURT OF INDIA\n"
    "CIVIL APPELLATE JURISDICTION\n"
    "Petitioner: John Doe v. Respondent: State of Maharashtra\n"
    "The court held that the appeal is dismissed under Section 302 IPC.\n"
) * 10


@pytest.fixture
def mock_llm():
    """Create a mock LLM provider."""
    return AsyncMock()


class TestExtractMetadataLLM:
    """Tests for extract_metadata_llm single-attempt logic."""

    @pytest.mark.asyncio
    async def test_successful_extraction(self, mock_llm):
        """When LLM succeeds, return populated CaseMetadata."""
        mock_llm.generate_structured.return_value = {
            "title": "John Doe v. State of Maharashtra",
            "court": "Supreme Court of India",
            "year": 2023,
        }

        result = await extract_metadata_llm(_SAMPLE_TEXT, mock_llm)

        assert result.title == "John Doe v. State of Maharashtra"
        assert result.court == "Supreme Court of India"
        assert mock_llm.generate_structured.call_count == 1

    @pytest.mark.asyncio
    async def test_transient_error_propagates(self, mock_llm):
        """Transient errors propagate to pipeline-level retry."""
        mock_llm.generate_structured.side_effect = ConnectionError("Network timeout")

        with pytest.raises(ConnectionError):
            await extract_metadata_llm(_SAMPLE_TEXT, mock_llm)

        assert mock_llm.generate_structured.call_count == 1

    @pytest.mark.asyncio
    async def test_runtime_error_propagates(self, mock_llm):
        """RuntimeError (empty output) propagates to pipeline-level retry."""
        mock_llm.generate_structured.return_value = {}

        with pytest.raises(RuntimeError, match="empty/all-null"):
            await extract_metadata_llm(_SAMPLE_TEXT, mock_llm)

    @pytest.mark.asyncio
    async def test_all_null_response_raises(self, mock_llm):
        """All-null response raises RuntimeError for pipeline retry."""
        mock_llm.generate_structured.return_value = {"title": None, "year": None}

        with pytest.raises(RuntimeError, match="empty/all-null"):
            await extract_metadata_llm(_SAMPLE_TEXT, mock_llm)

    @pytest.mark.asyncio
    async def test_no_retry_on_value_error(self, mock_llm):
        """ValueError returns empty CaseMetadata immediately (non-retryable)."""
        mock_llm.generate_structured.side_effect = ValueError("Invalid schema")

        result = await extract_metadata_llm(_SAMPLE_TEXT, mock_llm)

        assert result.title is None
        assert mock_llm.generate_structured.call_count == 1

    @pytest.mark.asyncio
    async def test_no_retry_on_key_error(self, mock_llm):
        """KeyError returns empty CaseMetadata immediately (non-retryable)."""
        mock_llm.generate_structured.side_effect = KeyError("missing_key")

        result = await extract_metadata_llm(_SAMPLE_TEXT, mock_llm)

        assert result.title is None
        assert mock_llm.generate_structured.call_count == 1

    @pytest.mark.asyncio
    async def test_headnotes_list_converted_to_json(self, mock_llm):
        """When LLM returns headnotes as a list, it should be JSON-serialized."""
        mock_llm.generate_structured.return_value = {
            "title": "Test Case",
            "headnotes": [
                {"proposition": "Right to privacy", "acts_sections": "Article 21"},
            ],
        }

        result = await extract_metadata_llm(_SAMPLE_TEXT, mock_llm)

        assert isinstance(result.headnotes, str)
        assert "Right to privacy" in result.headnotes

    @pytest.mark.asyncio
    async def test_unknown_fields_filtered_out(self, mock_llm):
        """Fields not in CaseMetadata should be silently dropped."""
        mock_llm.generate_structured.return_value = {
            "title": "Test Case",
            "unknown_field": "should be dropped",
            "another_unknown": 42,
        }

        result = await extract_metadata_llm(_SAMPLE_TEXT, mock_llm)

        assert result.title == "Test Case"
        assert not hasattr(result, "unknown_field")
