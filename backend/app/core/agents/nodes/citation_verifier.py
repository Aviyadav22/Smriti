"""Human-readable citation verification for agent memos.

Extracts Indian legal citations (SCC, AIR, SCC OnLine, INSC, SCR, CrLJ, SCALE,
BLR, KLT, GLR, JT) from LLM-generated text, verifies them against the database,
and checks whether they are grounded in the search results that the agent actually
retrieved.

This closes the hallucination gap where an LLM writes a plausible-looking citation
like "(2023) 5 SCC 123" that was never in the search results and may not exist.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import sqlalchemy
import sqlalchemy.exc
from sqlalchemy import text

from app.core.legal.extractor import (
    AIR_PATTERN,
    BLR_PATTERN,
    CRLJ_PATTERN,
    GLR_PATTERN,
    HC_REPORTER_PATTERN,
    INSC_PATTERN,
    JT_PATTERN,
    KLT_PATTERN,
    MANU_PATTERN,
    NEUTRAL_HC_PATTERN,
    NEUTRAL_SC_PATTERN,
    SCALE_PATTERN,
    SCC_ONLINE_PATTERN,
    SCC_PATTERN,
    SCC_SUB_PATTERN,
    SCR_PATTERN,
    extract_citations,
    normalize_citation,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# All citation patterns we scan for, in order
_CITATION_PATTERNS = [
    SCC_ONLINE_PATTERN,  # must come before SCC_PATTERN to avoid partial match
    SCC_SUB_PATTERN,  # [H24] SCC (Cri), SCC (S), etc. — before SCC_PATTERN
    SCC_PATTERN,
    AIR_PATTERN,
    NEUTRAL_SC_PATTERN,  # [H24] 2024:INSC:123 neutral citation
    NEUTRAL_HC_PATTERN,  # [H24] 2024:DHC:1234:DB neutral HC citation
    INSC_PATTERN,
    SCR_PATTERN,
    CRLJ_PATTERN,
    SCALE_PATTERN,
    MANU_PATTERN,  # [H24] MANU/SC/1234/2024
    HC_REPORTER_PATTERN,  # [H24] ILR, DLT, BomLR, MLJ, etc.
    BLR_PATTERN,
    KLT_PATTERN,
    GLR_PATTERN,
    JT_PATTERN,
]


def extract_citations_from_text(text_content: str) -> list[str]:
    """Extract all human-readable citation strings from text.

    Uses the compiled regex patterns from ``app.core.legal.extractor`` so
    that the patterns are maintained in a single place.

    Args:
        text_content: Memo or other text to scan.

    Returns:
        De-duplicated list of raw citation strings in order of appearance.
    """
    citations = extract_citations(text_content)
    # Return raw_text strings, preserving order, de-duplicated
    seen: set[str] = set()
    result: list[str] = []
    for c in citations:
        normalized = normalize_citation(c.raw_text)
        if normalized not in seen:
            seen.add(normalized)
            result.append(c.raw_text)
    return result


async def verify_citations_against_db(
    citations: list[str],
    db: AsyncSession,
) -> tuple[list[str], list[str]]:
    """Check each citation against the database.

    Looks up each citation in both ``cases.citation`` and
    ``case_citation_equivalents.citation_text`` using ILIKE for
    fuzzy matching (handles minor whitespace / punctuation differences).

    Args:
        citations: List of raw citation strings to verify.
        db: Async database session.

    Returns:
        Tuple of (verified, unverified) citation lists.
    """
    if not citations:
        return [], []

    verified: list[str] = []
    unverified: list[str] = []

    for citation in citations:
        normalized = normalize_citation(citation)
        # Use ILIKE with the normalized form for flexible matching
        like_pattern = f"%{normalized}%"

        try:
            # Check cases.citation
            result = await db.execute(
                text("SELECT 1 FROM cases WHERE citation ILIKE :pattern LIMIT 1"),
                {"pattern": like_pattern},
            )
            if result.first() is not None:
                verified.append(citation)
                continue

            # Check case_citation_equivalents.citation_text
            result = await db.execute(
                text(
                    "SELECT 1 FROM case_citation_equivalents "
                    "WHERE citation_text ILIKE :pattern LIMIT 1"
                ),
                {"pattern": like_pattern},
            )
            if result.first() is not None:
                verified.append(citation)
                continue

            unverified.append(citation)
        except (sqlalchemy.exc.SQLAlchemyError, ConnectionError, TimeoutError):
            logger.warning(
                "DB lookup failed for citation '%s', treating as unverified",
                citation,
                exc_info=True,
            )
            unverified.append(citation)

    return verified, unverified


def check_grounding(
    memo_citations: list[str],
    search_result_citations: list[str],
) -> list[str]:
    """Find citations in the memo that were NOT in the search results.

    A citation that appears in the memo but was never returned by the
    search pipeline may have been hallucinated from the LLM's training
    data.  This is the most dangerous kind of hallucination for a lawyer.

    Args:
        memo_citations: Citations extracted from the LLM-generated memo.
        search_result_citations: Citations extracted from search result
            snippets / metadata that the agent actually retrieved.

    Returns:
        List of memo citations that are ungrounded (not in search results).
    """
    # Normalize search result citations for comparison
    search_normalized: set[str] = {normalize_citation(c) for c in search_result_citations}

    ungrounded: list[str] = []
    for citation in memo_citations:
        if normalize_citation(citation) not in search_normalized:
            ungrounded.append(citation)

    return ungrounded
