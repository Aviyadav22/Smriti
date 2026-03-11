"""Tests for extract_metadata_llm retry logic (G9).

Verifies that the LLM extraction function retries on transient errors,
does NOT retry on non-transient errors (ValueError, KeyError, RuntimeError),
and returns empty CaseMetadata on all failures.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.core.ingestion.metadata import CaseMetadata, extract_metadata_llm


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


class TestExtractMetadataLLMRetry:
    """G9: Tests for extract_metadata_llm retry logic."""

    @pytest.mark.asyncio
    async def test_successful_extraction_no_retry(self, mock_llm):
        """When LLM succeeds on first try, no retries should occur."""
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
    async def test_retries_on_transient_error(self, mock_llm):
        """Transient errors (generic Exception) should trigger retries."""
        mock_llm.generate_structured.side_effect = [
            ConnectionError("Network timeout"),
            ConnectionError("Network timeout"),
            {"title": "Test Case", "year": 2023},
        ]

        with patch("app.core.ingestion.metadata.asyncio.sleep", new_callable=AsyncMock):
            result = await extract_metadata_llm(_SAMPLE_TEXT, mock_llm, max_retries=3)

        assert result.title == "Test Case"
        assert mock_llm.generate_structured.call_count == 3

    @pytest.mark.asyncio
    async def test_no_retry_on_value_error(self, mock_llm):
        """ValueError should NOT trigger retries — returns empty CaseMetadata immediately."""
        mock_llm.generate_structured.side_effect = ValueError("Invalid schema")

        result = await extract_metadata_llm(_SAMPLE_TEXT, mock_llm, max_retries=3)

        assert result.title is None  # Empty CaseMetadata
        assert mock_llm.generate_structured.call_count == 1

    @pytest.mark.asyncio
    async def test_no_retry_on_key_error(self, mock_llm):
        """KeyError should NOT trigger retries."""
        mock_llm.generate_structured.side_effect = KeyError("missing_key")

        result = await extract_metadata_llm(_SAMPLE_TEXT, mock_llm, max_retries=3)

        assert result.title is None
        assert mock_llm.generate_structured.call_count == 1

    @pytest.mark.asyncio
    async def test_no_retry_on_runtime_error(self, mock_llm):
        """RuntimeError should NOT trigger retries."""
        mock_llm.generate_structured.side_effect = RuntimeError("schema mismatch")

        result = await extract_metadata_llm(_SAMPLE_TEXT, mock_llm, max_retries=3)

        assert result.title is None
        assert mock_llm.generate_structured.call_count == 1

    @pytest.mark.asyncio
    async def test_exhausted_retries_returns_empty(self, mock_llm):
        """After exhausting all retries, should return empty CaseMetadata."""
        mock_llm.generate_structured.side_effect = ConnectionError("Timeout")

        with patch("app.core.ingestion.metadata.asyncio.sleep", new_callable=AsyncMock):
            result = await extract_metadata_llm(_SAMPLE_TEXT, mock_llm, max_retries=3)

        assert result.title is None
        assert result.court is None
        assert mock_llm.generate_structured.call_count == 3

    @pytest.mark.asyncio
    async def test_exponential_backoff_timing(self, mock_llm):
        """Retries should use exponential backoff: 1s, 2s, 4s, etc."""
        mock_llm.generate_structured.side_effect = ConnectionError("Timeout")

        with patch(
            "app.core.ingestion.metadata.asyncio.sleep", new_callable=AsyncMock
        ) as mock_sleep:
            await extract_metadata_llm(_SAMPLE_TEXT, mock_llm, max_retries=3)

        # Backoff: 2^0=1s, 2^1=2s (only 2 sleeps for 3 attempts, last attempt doesn't sleep)
        assert mock_sleep.call_count == 2
        mock_sleep.assert_any_call(1)  # 2^0
        mock_sleep.assert_any_call(2)  # 2^1

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

        assert isinstance(result.headnotes, str)  # JSON string, not list
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
