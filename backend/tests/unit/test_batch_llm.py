"""Tests for BatchCachedLLM mock provider."""

import pytest

from scripts.batch_llm import BatchCachedLLM


class TestBatchCachedLLM:
    """Verify the mock LLM returns cached results correctly."""

    @pytest.fixture
    def sample_result(self) -> dict:
        return {
            "title": "State of Maharashtra v. Doe",
            "citation": "(2023) 5 SCC 123",
            "court": "Supreme Court of India",
            "judge": ["A.K. Sharma", "B.R. Patel"],
            "year": 2023,
            "ratio_decidendi": "The court held...",
            "acts_cited": ["Indian Penal Code, 1860"],
        }

    @pytest.fixture
    def llm(self, sample_result: dict) -> BatchCachedLLM:
        return BatchCachedLLM(result=sample_result)

    @pytest.mark.asyncio
    async def test_generate_structured_from_pdf_returns_cached(self, llm, sample_result):
        result = await llm.generate_structured_from_pdf(
            "/fake/path.pdf",
            prompt="Extract metadata",
            system="You are an expert",
            output_schema={"type": "object"},
        )
        assert result == sample_result

    @pytest.mark.asyncio
    async def test_generate_structured_returns_cached(self, llm, sample_result):
        result = await llm.generate_structured(
            "Extract metadata from this text...",
            system="You are an expert",
            output_schema={"type": "object"},
        )
        assert result == sample_result

    @pytest.mark.asyncio
    async def test_generate_raises_not_implemented(self, llm):
        with pytest.raises(NotImplementedError):
            await llm.generate(prompt="hello")

    @pytest.mark.asyncio
    async def test_stream_raises_not_implemented(self, llm):
        with pytest.raises(NotImplementedError):
            async for _ in llm.stream(prompt="hello"):
                pass

    def test_has_generate_structured_from_pdf_attribute(self, llm):
        """Pipeline checks hasattr(llm, 'generate_structured_from_pdf') to decide PDF path."""
        assert hasattr(llm, "generate_structured_from_pdf")
        assert callable(llm.generate_structured_from_pdf)

    @pytest.mark.asyncio
    async def test_empty_result_passes_through(self):
        """Empty dict from batch should pass through — pipeline handles validation."""
        llm = BatchCachedLLM(result={})
        result = await llm.generate_structured_from_pdf(
            "/fake.pdf",
            prompt="x",
            system="y",
            output_schema={},
        )
        assert result == {}
