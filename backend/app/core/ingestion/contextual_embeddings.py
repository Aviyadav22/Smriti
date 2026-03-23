"""Contextual Retrieval for legal document chunks.

Implements Anthropic's Contextual Retrieval technique: each chunk is prefixed
with a short LLM-generated sentence that situates it within the full document,
improving retrieval relevance without changing the underlying text.
"""

from __future__ import annotations

import asyncio
import logging

from app.core.ingestion.rate_limiter import AsyncRateLimiter
from app.core.interfaces.llm import LLMProvider

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt constants
# ---------------------------------------------------------------------------

CONTEXTUAL_PREFIX_SYSTEM = """\
You are a legal document analyst. Given a chunk from an Indian court judgment and \
metadata about the full document, generate a concise 1-2 sentence context prefix that \
states:
(1) What specific legal question this chunk addresses.
(2) What the court's position is on that question (if discernible from the chunk).
If the chunk is purely factual narration, state what legal issue the facts relate to.
Include the case citation.

Format: "<context prefix>\\n\\n<original chunk text>"
Do NOT summarize or paraphrase the chunk. Only add contextual framing.\
"""

CONTEXTUAL_PREFIX_STATUTE = """You are a legal document analyst. Given a section of an Indian statute, generate a 1-sentence context prefix.

Include: the full act name, which part/chapter this section belongs to, and whether this section was replaced by or replaces another section (if applicable).

Example: "This is Section 302 (Punishment for murder) of the Indian Penal Code, 1860, Chapter XVI (Of Offences Affecting the Human Body), now replaced by Section 103 of Bharatiya Nyaya Sanhita, 2023."
"""


# ---------------------------------------------------------------------------
# Single-chunk contextualisation
# ---------------------------------------------------------------------------


async def generate_contextual_prefix(
    chunk_text: str,
    document_metadata: dict,
    flash_llm: LLMProvider,
    document_type: str = "case_law",
) -> str:
    """Generate a contextual prefix for a single chunk and prepend it.

    Args:
        chunk_text: The raw text of the chunk.
        document_metadata: Metadata about the parent document.
        flash_llm: A fast/cheap LLM provider (e.g. Gemini Flash).
        document_type: Either ``"case_law"`` or ``"statute"``.

    Returns:
        The chunk text with a contextual prefix prepended.  On failure the
        original *chunk_text* is returned unchanged.
    """
    try:
        if document_type == "statute":
            system = CONTEXTUAL_PREFIX_STATUTE
            user = _build_statute_prompt(chunk_text, document_metadata)
        else:
            system = CONTEXTUAL_PREFIX_SYSTEM
            user = _build_case_law_prompt(chunk_text, document_metadata)

        prefix: str = await flash_llm.generate(prompt=user, system=system)
        return f"{prefix.strip()}\n\n{chunk_text}"
    except Exception:
        logger.warning(
            "Failed to generate contextual prefix; returning original chunk",
            exc_info=True,
        )
        return chunk_text


# ---------------------------------------------------------------------------
# Batch contextualisation
# ---------------------------------------------------------------------------


async def batch_contextualize_chunks(
    chunks: list[dict],
    document_metadata: dict,
    flash_llm: LLMProvider,
    document_type: str = "case_law",
    batch_size: int = 10,
    rate_limiter: AsyncRateLimiter | None = None,
) -> list[dict]:
    """Contextualize a list of chunk dicts in parallel batches.

    Each chunk dict **must** contain a ``"text"`` key.  After processing every
    chunk will also have a ``"contextualized_text"`` key holding the prefixed
    version (the original ``"text"`` is preserved for display).

    Args:
        chunks: List of chunk dictionaries with at least a ``"text"`` key.
        document_metadata: Metadata about the parent document.
        flash_llm: A fast/cheap LLM provider.
        document_type: Either ``"case_law"`` or ``"statute"``.
        batch_size: Number of chunks to process concurrently per batch.

    Returns:
        The same list of chunk dicts, each enriched with
        ``"contextualized_text"``.
    """
    batches = [chunks[i : i + batch_size] for i in range(0, len(chunks), batch_size)]

    for batch in batches:

        async def _contextualize_one(chunk_text: str) -> str:
            if rate_limiter:
                await rate_limiter.acquire()
            return await generate_contextual_prefix(
                chunk_text,
                document_metadata,
                flash_llm,
                document_type,
            )

        tasks = [_contextualize_one(chunk["text"]) for chunk in batch]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for chunk, result in zip(batch, results):
            if isinstance(result, Exception):
                logger.warning(
                    "Contextualization failed for chunk; using original text",
                    exc_info=result,
                )
                chunk["contextualized_text"] = chunk["text"]
            else:
                chunk["contextualized_text"] = result

    return chunks


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_case_law_prompt(chunk_text: str, meta: dict) -> str:
    """Build the user prompt for case-law chunks."""
    parts: list[str] = ["Document metadata:"]
    if meta.get("title"):
        parts.append(f"- Case: {meta['title']}")
    if meta.get("citation"):
        parts.append(f"- Citation: {meta['citation']}")
    if meta.get("court"):
        parts.append(f"- Court: {meta['court']}")
    if meta.get("year"):
        parts.append(f"- Year: {meta['year']}")
    if meta.get("section_type"):
        parts.append(f"- Section: {meta['section_type']}")

    parts.append(f"\nChunk text:\n{chunk_text}")
    return "\n".join(parts)


def _build_statute_prompt(chunk_text: str, meta: dict) -> str:
    """Build the user prompt for statute chunks."""
    parts: list[str] = ["Statute metadata:"]
    if meta.get("act_name"):
        parts.append(f"- Act: {meta['act_name']}")
    if meta.get("section_number"):
        parts.append(f"- Section number: {meta['section_number']}")
    if meta.get("section_title"):
        parts.append(f"- Section title: {meta['section_title']}")
    if meta.get("chapter"):
        parts.append(f"- Chapter: {meta['chapter']}")

    parts.append(f"\nSection text:\n{chunk_text}")
    return "\n".join(parts)
