"""Tests for classify_treatment_llm() — LLM-based citation treatment classifier.

Wired in GAP-2 as Stage 3 fallback in the RAG pipeline treatment checking:
Stage 1: Neo4j graph → Stage 2: Regex heuristic → Stage 3: LLM classifier.
"""
import json
from unittest.mock import AsyncMock

import pytest

from app.core.legal.treatment import (
    CitationTreatment,
    classify_treatment_llm,
)


@pytest.fixture
def mock_llm():
    """Create a mock LLM provider."""
    llm = AsyncMock()
    return llm


class TestClassifyTreatmentLLM:
    """Tests for classify_treatment_llm() — the LLM fallback classifier."""

    @pytest.mark.asyncio
    async def test_overruled_classification(self, mock_llm):
        """Should classify overruled treatment from LLM response."""
        mock_llm.generate.return_value = json.dumps({
            "treatment": "overruled",
            "confidence": 0.92,
        })
        result = await classify_treatment_llm(
            "The earlier decision was expressly overruled by a larger bench.",
            mock_llm,
        )
        assert result is not None
        assert result.treatment == CitationTreatment.OVERRULED
        assert result.confidence == 0.92

    @pytest.mark.asyncio
    async def test_distinguished_classification(self, mock_llm):
        """Should classify distinguished treatment."""
        mock_llm.generate.return_value = json.dumps({
            "treatment": "distinguished",
            "confidence": 0.85,
        })
        result = await classify_treatment_llm(
            "The facts of the present case are distinguishable on the ground that...",
            mock_llm,
        )
        assert result is not None
        assert result.treatment == CitationTreatment.DISTINGUISHED
        assert result.confidence == 0.85

    @pytest.mark.asyncio
    async def test_followed_classification(self, mock_llm):
        """Should classify followed/affirmed treatment."""
        mock_llm.generate.return_value = json.dumps({
            "treatment": "followed",
            "confidence": 0.78,
        })
        result = await classify_treatment_llm(
            "We respectfully follow the ratio laid down in the cited judgment.",
            mock_llm,
        )
        assert result is not None
        assert result.treatment == CitationTreatment.FOLLOWED

    @pytest.mark.asyncio
    async def test_returns_none_on_invalid_treatment(self, mock_llm):
        """Should return None when LLM returns invalid treatment type."""
        mock_llm.generate.return_value = json.dumps({
            "treatment": "invalid_type",
            "confidence": 0.5,
        })
        result = await classify_treatment_llm("some context", mock_llm)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_llm_failure(self, mock_llm):
        """Should return None when LLM call fails."""
        mock_llm.generate.side_effect = ConnectionError("API unavailable")
        result = await classify_treatment_llm("some context", mock_llm)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_malformed_json(self, mock_llm):
        """Should return None when LLM returns non-JSON response."""
        mock_llm.generate.return_value = "This is not JSON"
        result = await classify_treatment_llm("some context", mock_llm)
        assert result is None

    @pytest.mark.asyncio
    async def test_truncates_context_to_1000_chars(self, mock_llm):
        """Should truncate input context to first 1000 chars."""
        mock_llm.generate.return_value = json.dumps({
            "treatment": "affirmed",
            "confidence": 0.7,
        })
        long_text = "x" * 5000
        await classify_treatment_llm(long_text, mock_llm)

        # Check the prompt passed to LLM was truncated
        call_args = mock_llm.generate.call_args
        prompt = call_args.kwargs.get("prompt", call_args.args[0] if call_args.args else "")
        # The prompt includes the prefix text + first 1000 chars of context
        assert len(long_text[:1000]) == 1000
        assert "x" * 1001 not in prompt

    @pytest.mark.asyncio
    async def test_handles_markdown_wrapped_json(self, mock_llm):
        """Should handle LLM response wrapped in markdown code blocks."""
        mock_llm.generate.return_value = '```json\n{"treatment": "doubted", "confidence": 0.65}\n```'
        result = await classify_treatment_llm("some context", mock_llm)
        assert result is not None
        assert result.treatment == CitationTreatment.DOUBTED

    @pytest.mark.asyncio
    async def test_per_incuriam_classification(self, mock_llm):
        """Should classify per incuriam — case decided in ignorance of law."""
        mock_llm.generate.return_value = json.dumps({
            "treatment": "per_incuriam",
            "confidence": 0.88,
        })
        result = await classify_treatment_llm(
            "The judgment was rendered per incuriam as the bench was not made aware of the statutory amendment.",
            mock_llm,
        )
        assert result is not None
        assert result.treatment == CitationTreatment.PER_INCURIAM

    @pytest.mark.asyncio
    async def test_cited_text_truncated_to_200(self, mock_llm):
        """Result cited_text should be first 200 chars of input context."""
        mock_llm.generate.return_value = json.dumps({
            "treatment": "affirmed",
            "confidence": 0.8,
        })
        context = "A" * 500
        result = await classify_treatment_llm(context, mock_llm)
        assert result is not None
        assert len(result.cited_text) == 200

    @pytest.mark.asyncio
    async def test_default_confidence(self, mock_llm):
        """Should use 0.5 default confidence when LLM omits it."""
        mock_llm.generate.return_value = json.dumps({
            "treatment": "explained",
        })
        result = await classify_treatment_llm("some context", mock_llm)
        assert result is not None
        assert result.confidence == 0.5
