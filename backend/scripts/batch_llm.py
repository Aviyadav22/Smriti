"""Mock LLM provider that returns pre-fetched Gemini Batch API results.

Used by batch_ingest.py Phase 3 to feed cached metadata extraction results
into the existing ingest_judgment() pipeline without modifications.

The pipeline calls extract_metadata_llm() which calls:
  1. llm.generate_structured_from_pdf() (if hasattr) — our mock returns the cached result
  2. llm.generate_structured() (fallback) — also returns cached result

The cached result dict is the raw JSON from the Gemini Batch API response,
which should match the structure of interactive generate_structured() output.
"""

from __future__ import annotations

from collections.abc import AsyncIterator


class BatchCachedLLM:
    """LLM provider that returns pre-fetched batch results.

    Implements the LLMProvider protocol just enough for extract_metadata_llm():
    - generate_structured_from_pdf() → cached result (pipeline tries first)
    - generate_structured() → cached result (text fallback)
    - generate() / stream() → NotImplementedError (not needed)
    """

    def __init__(self, result: dict) -> None:
        self._result = result

    async def generate_structured_from_pdf(
        self,
        pdf_path: str,
        *,
        prompt: str,
        system: str | None = None,
        output_schema: dict,
        temperature: float = 0.1,
    ) -> dict:
        return self._result

    async def generate_structured(
        self,
        prompt: str,
        *,
        system: str | None = None,
        output_schema: dict,
        temperature: float = 0.1,
    ) -> dict:
        return self._result

    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 8192,
    ) -> str:
        raise NotImplementedError("BatchCachedLLM only supports structured generation")

    async def stream(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.1,
    ) -> AsyncIterator[str]:
        raise NotImplementedError("BatchCachedLLM does not support streaming")
        yield  # pragma: no cover  — makes this a generator
