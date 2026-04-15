"""RAPTOR-style hierarchical section summarizer for ingestion.

[Q3] Generates Level-1 section summaries during ingestion to give the
research agent macro-level judgment context without full documents.

Three-level hierarchy per judgment:
  Level 0: Original chunks (existing, 2000-char, section-tagged)
  Level 1: Section summaries (1 per section type) — generated here
  Level 2: Full judgment summary (ratio_decidendi in cases table)
"""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.core.interfaces import LLMProvider

logger = logging.getLogger(__name__)

SECTION_SUMMARY_SYSTEM = (
    "You are a legal analyst. Summarize this section of an Indian court "
    "judgment in 2-4 sentences.\n"
    "Preserve: key legal principles, case names cited, statute sections "
    "referenced, and the court's reasoning.\n"
    "Do NOT paraphrase quotes — if a specific holding is important, "
    "include the exact phrasing."
)

# Minimum content length to warrant a summary
_MIN_SECTION_LENGTH = 200


async def generate_section_summaries(
    case_id: str,
    sections: list[dict],
    flash_llm: LLMProvider,
) -> list[dict]:
    """Generate Level-1 summaries for each section of a judgment.

    Parameters
    ----------
    case_id:
        The UUID of the case in our database.
    sections:
        List of dicts with keys ``section_type`` and ``content``
        (from the case_sections table).
    flash_llm:
        Flash LLM instance for cheap/fast generation.

    Returns
    -------
    list[dict]
        Each dict has: case_id, section_type, summary_text, summary_level.
    """
    eligible = [s for s in sections if len(s.get("content", "")) >= _MIN_SECTION_LENGTH]
    if not eligible:
        return []

    tasks = [
        flash_llm.generate(
            prompt=(
                f"Section type: {section['section_type']}\n\n"
                f"{section['content'][:8000]}"
            ),
            system=SECTION_SUMMARY_SYSTEM,
        )
        for section in eligible
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    summaries: list[dict] = []
    for section, result in zip(eligible, results, strict=False):
        if isinstance(result, Exception):
            logger.warning(
                "Section summary failed for %s/%s: %s",
                case_id, section["section_type"], result,
            )
            continue
        summaries.append({
            "case_id": case_id,
            "section_type": section["section_type"],
            "summary_text": result.strip(),
            "summary_level": 1,
        })

    return summaries


def build_pinecone_summary_vectors(
    case_id: str,
    summaries: list[dict],
    embeddings: list[list[float]],
    base_metadata: dict[str, Any] | None = None,
) -> list[dict]:
    """Build Pinecone upsert records for Level-1 summary vectors.

    Parameters
    ----------
    case_id:
        The case UUID.
    summaries:
        Output of ``generate_section_summaries()``.
    embeddings:
        Embedding vectors for each summary_text (same order).
    base_metadata:
        Common metadata fields (title, citation, court, year, etc.).

    Returns
    -------
    list[dict]
        Pinecone-ready records: {id, values, metadata}.
    """
    records: list[dict] = []
    meta_base = base_metadata or {}

    for summary, embedding in zip(summaries, embeddings, strict=False):
        vector_id = f"{case_id}_summary_{summary['section_type']}"
        metadata = {
            **meta_base,
            "document_type": "case_law",
            "vector_type": "summary",
            "summary_level": summary["summary_level"],
            "section_type": summary["section_type"],
            "case_id": case_id,
            "text": summary["summary_text"],
        }
        records.append({
            "id": vector_id,
            "values": embedding,
            "metadata": metadata,
        })

    return records
