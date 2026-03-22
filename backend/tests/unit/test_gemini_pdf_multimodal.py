"""Tests for Gemini PDF multimodal metadata extraction."""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.ingestion.metadata import CaseMetadata, extract_metadata_llm


class TestGenerateStructuredFromPdf:
    """Verify GeminiLLM.generate_structured_from_pdf() implementation."""

    @pytest.mark.asyncio
    async def test_reads_pdf_bytes_and_calls_gemini(self):
        """Should read PDF file, create Part, and call generate_content."""
        from app.core.providers.llm.gemini import GeminiLLM

        mock_response = MagicMock()
        mock_response.text = json.dumps({"title": "Test v. State", "court": "Supreme Court of India"})

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        llm = GeminiLLM.__new__(GeminiLLM)
        llm._client = mock_client
        llm._model = "gemini-2.5-pro"

        with patch("pathlib.Path.read_bytes", return_value=b"%PDF-1.4 fake pdf content"):
            result = await llm.generate_structured_from_pdf(
                "/fake/judgment.pdf",
                prompt="Extract metadata",
                system="You are a legal extractor",
                output_schema={"type": "object", "properties": {"title": {"type": "string"}}},
            )

        assert result["title"] == "Test v. State"
        mock_client.aio.models.generate_content.assert_called_once()
        call_args = mock_client.aio.models.generate_content.call_args
        contents = call_args.kwargs["contents"]
        assert len(contents) == 2  # [pdf_part, prompt]

    @pytest.mark.asyncio
    async def test_returns_empty_dict_on_json_error(self):
        """Should return {} when response isn't valid JSON."""
        from app.core.providers.llm.gemini import GeminiLLM

        mock_response = MagicMock()
        mock_response.text = "not json"

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        llm = GeminiLLM.__new__(GeminiLLM)
        llm._client = mock_client
        llm._model = "gemini-2.5-pro"

        with patch("pathlib.Path.read_bytes", return_value=b"%PDF-1.4"):
            result = await llm.generate_structured_from_pdf(
                "/fake/judgment.pdf",
                prompt="Extract",
                output_schema={"type": "object"},
            )

        assert result == {}


class TestExtractMetadataLlmPdfPath:
    """Verify extract_metadata_llm prefers PDF multimodal when available."""

    @pytest.mark.asyncio
    async def test_uses_pdf_when_path_provided(self):
        """When pdf_path is given and LLM has generate_structured_from_pdf, use it."""
        mock_llm = AsyncMock()
        mock_llm.generate_structured_from_pdf = AsyncMock(return_value={
            "title": "PDF Test v. State",
            "court": "Supreme Court of India",
        })
        mock_llm.generate_structured = AsyncMock()

        result = await extract_metadata_llm(
            "some text", mock_llm, pdf_path="/fake/test.pdf"
        )

        mock_llm.generate_structured_from_pdf.assert_called_once()
        mock_llm.generate_structured.assert_not_called()
        assert result.title == "PDF Test v. State"

    @pytest.mark.asyncio
    async def test_falls_back_to_text_when_no_pdf_path(self):
        """When pdf_path is None, should use text-based generate_structured."""
        mock_llm = AsyncMock()
        mock_llm.generate_structured = AsyncMock(return_value={
            "title": "Text Test v. State",
            "court": "Supreme Court of India",
        })

        result = await extract_metadata_llm("some text", mock_llm, pdf_path=None)

        mock_llm.generate_structured.assert_called_once()
        assert result.title == "Text Test v. State"

    @pytest.mark.asyncio
    async def test_falls_back_when_llm_lacks_pdf_method(self):
        """When LLM doesn't have generate_structured_from_pdf, use text."""
        mock_llm = AsyncMock(spec=["generate_structured", "generate", "stream"])
        mock_llm.generate_structured = AsyncMock(return_value={
            "title": "Fallback v. State",
        })

        result = await extract_metadata_llm(
            "some text", mock_llm, pdf_path="/fake/test.pdf"
        )

        mock_llm.generate_structured.assert_called_once()
        assert result.title == "Fallback v. State"


class TestLLMProviderProtocol:
    """Verify the Protocol includes the new method."""

    def test_protocol_has_pdf_method(self):
        from app.core.interfaces.llm import LLMProvider
        assert hasattr(LLMProvider, "generate_structured_from_pdf")
