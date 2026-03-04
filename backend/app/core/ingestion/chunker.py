"""Legal-aware text chunking for Indian court judgments.

Detects structural sections (FACTS, ARGUMENTS, ANALYSIS, etc.) via regex
patterns and chunks text while respecting section boundaries.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Section:
    """A detected structural section within a judgment."""

    type: str
    start: int
    end: int
    text: str


@dataclass(frozen=True, slots=True)
class Chunk:
    """A text chunk ready for embedding, annotated with section metadata."""

    text: str
    section_type: str  # HEADER, FACTS, ARGUMENTS, ISSUES, ANALYSIS, RATIO, ORDER, FULL
    chunk_index: int
    case_id: str
    page_number: int | None = None


# ---------------------------------------------------------------------------
# Section detection patterns
# ---------------------------------------------------------------------------

# Patterns are tried against line-start positions (after stripping numbering).
# Order matters: we sort matches by position, not by pattern priority.

SECTION_PATTERNS: dict[str, re.Pattern[str]] = {
    "HEADER": re.compile(
        r"(?:"
        r"IN\s+THE\s+SUPREME\s+COURT"
        r"|IN\s+THE\s+HIGH\s+COURT"
        r"|JUDGMENT"
        r"|J\s*U\s*D\s*G\s*M\s*E\s*N\s*T"
        r"|REPORTABLE"
        r"|NON[\s-]*REPORTABLE"
        r")",
        re.IGNORECASE,
    ),
    "FACTS": re.compile(
        r"(?:"
        r"FACTS"
        r"|FACTUAL\s+BACKGROUND"
        r"|THE\s+FACTS"
        r"|BRIEF\s+FACTS"
        r"|FACTUAL\s+MATRIX"
        r"|BACKGROUND\s+FACTS"
        r")",
        re.IGNORECASE,
    ),
    "ARGUMENTS": re.compile(
        r"(?:"
        r"ARGUMENTS"
        r"|SUBMISSIONS"
        r"|CONTENTIONS"
        r"|LEARNED\s+COUNSEL"
        r"|RIVAL\s+(?:SUBMISSIONS|CONTENTIONS)"
        r"|ARGUMENTS\s+(?:ON\s+BEHALF|ADVANCED)"
        r")",
        re.IGNORECASE,
    ),
    "ISSUES": re.compile(
        r"(?:"
        r"ISSUES?\s+FOR\s+DETERMINATION"
        r"|QUESTIONS?\s+FOR\s+CONSIDERATION"
        r"|POINTS?\s+FOR\s+DETERMINATION"
        r"|ISSUES?\s+(?:THAT\s+)?ARISE"
        r"|THE\s+ISSUES?"
        r")",
        re.IGNORECASE,
    ),
    "ANALYSIS": re.compile(
        r"(?:"
        r"ANALYSIS"
        r"|DISCUSSION"
        r"|CONSIDERATION"
        r"|HAVING\s+HEARD"
        r"|I\s+HAVE\s+CONSIDERED"
        r"|WE\s+HAVE\s+CONSIDERED"
        r"|ANALYSIS\s+AND\s+DISCUSSION"
        r"|OUR\s+ANALYSIS"
        r"|REASONING"
        r")",
        re.IGNORECASE,
    ),
    "RATIO": re.compile(
        r"(?:"
        r"RATIO\s+DECIDENDI"
        r"|WE\s+HOLD\s+THAT"
        r"|IN\s+MY\s+CONSIDERED\s+VIEW"
        r"|THE\s+LAW\s+IS"
        r"|WE\s+ARE\s+OF\s+THE\s+(?:CONSIDERED\s+)?VIEW"
        r"|IN\s+VIEW\s+OF\s+THE\s+ABOVE"
        r"|FOR\s+THE\s+(?:AFORESAID|FOREGOING)\s+REASONS"
        r")",
        re.IGNORECASE,
    ),
    "ORDER": re.compile(
        r"(?:"
        r"O\s*R\s*D\s*E\s*R"
        r"|RESULT"
        r"|DISPOSITION"
        r"|THE\s+APPEAL\s+IS"
        r"|IN\s+THE\s+RESULT"
        r"|ACCORDINGLY"
        r"|THE\s+(?:PETITION|WRIT\s+PETITION|APPEAL|SUIT)\s+IS\s+(?:HEREBY\s+)?(?:ALLOWED|DISMISSED)"
        r")",
        re.IGNORECASE,
    ),
}

# ---------------------------------------------------------------------------
# Chunking parameters
# ---------------------------------------------------------------------------

CHUNK_SIZE: int = 2000
CHUNK_OVERLAP: int = 200


# ---------------------------------------------------------------------------
# Section detection
# ---------------------------------------------------------------------------


def detect_judgment_sections(text: str) -> list[Section]:
    """Detect structural sections in a judgment using regex pattern matching.

    Scans the full text for known section headings, sorts matches by their
    character position, and returns non-overlapping ``Section`` objects whose
    ``text`` spans from one heading to the next.

    Args:
        text: Full judgment text.

    Returns:
        Ordered list of ``Section`` objects. May be empty if no patterns
        match (callers should fall back to a single FULL section).
    """
    if not text:
        return []

    # Collect all matches: (start_position, section_type)
    markers: list[tuple[int, str]] = []

    for section_type, pattern in SECTION_PATTERNS.items():
        for match in pattern.finditer(text):
            markers.append((match.start(), section_type))

    if not markers:
        return []

    # Sort by position in the text.
    markers.sort(key=lambda m: m[0])

    # De-duplicate: if the same section_type appears at nearly the same
    # position (within 50 chars), keep only the first occurrence.
    deduped: list[tuple[int, str]] = []
    for pos, stype in markers:
        if deduped and deduped[-1][1] == stype and (pos - deduped[-1][0]) < 50:
            continue
        deduped.append((pos, stype))

    # If the first section does not start at the beginning of the text,
    # prepend a HEADER section covering the preamble.
    if deduped[0][0] > 0:
        deduped.insert(0, (0, "HEADER"))

    # Build Section objects.
    sections: list[Section] = []
    for i, (start, stype) in enumerate(deduped):
        end = deduped[i + 1][0] if i + 1 < len(deduped) else len(text)
        section_text = text[start:end]
        if section_text.strip():  # skip empty sections
            sections.append(Section(type=stype, start=start, end=end, text=section_text))

    return sections


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------


def chunk_judgment(
    text: str,
    sections: list[Section] | None = None,
    case_id: str = "",
) -> list[Chunk]:
    """Chunk judgment text respecting section boundaries.

    Each section is independently split into chunks of ``CHUNK_SIZE``
    characters with ``CHUNK_OVERLAP`` overlap. This preserves section-type
    metadata on every chunk and avoids mixing content from different
    structural parts of the judgment.

    Args:
        text: Full judgment text.
        sections: Pre-detected sections (if ``None``, detection runs
            automatically).
        case_id: UUID or identifier for the parent case.

    Returns:
        Ordered list of ``Chunk`` objects.
    """
    if not text:
        return []

    if sections is None:
        sections = detect_judgment_sections(text)

    # Fallback: treat the entire text as one section.
    if not sections:
        sections = [Section(type="FULL", start=0, end=len(text), text=text)]

    chunks: list[Chunk] = []
    chunk_idx = 0

    for section in sections:
        section_text = section.text
        section_len = len(section_text)

        if section_len == 0:
            continue

        pos = 0
        while pos < section_len:
            end = min(pos + CHUNK_SIZE, section_len)
            chunk_text = section_text[pos:end]

            # Only emit non-empty chunks.
            if chunk_text.strip():
                chunks.append(
                    Chunk(
                        text=chunk_text,
                        section_type=section.type,
                        chunk_index=chunk_idx,
                        case_id=case_id,
                    )
                )
                chunk_idx += 1

            # Advance by (CHUNK_SIZE - CHUNK_OVERLAP) for overlap.
            next_pos = pos + CHUNK_SIZE - CHUNK_OVERLAP

            # If the remaining text after next_pos is smaller than the
            # overlap, we have already captured it -- stop to avoid a
            # near-duplicate trailing chunk.
            if next_pos >= section_len or (section_len - next_pos) <= CHUNK_OVERLAP:
                break

            pos = next_pos

    return chunks
