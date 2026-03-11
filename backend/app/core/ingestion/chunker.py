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
    section_type: str  # HEADER, FACTS, ARGUMENTS, ISSUES, ANALYSIS, RATIO, ORDER, DISSENT, CONCURRENCE, FULL
    chunk_index: int
    case_id: str
    page_number: int | None = None
    para_start: int | None = None
    para_end: int | None = None


# ---------------------------------------------------------------------------
# Paragraph number detection
# ---------------------------------------------------------------------------

_PARA_NUM_PATTERN = re.compile(r"^\s*(\d+)\.\s+", re.MULTILINE)


def _detect_paragraph_range(text: str) -> tuple[int | None, int | None]:
    """Detect the range of paragraph numbers in a chunk of text.

    Indian SC judgments use numbered paragraphs: '1. The appellant...', '2. The facts...'
    """
    matches = _PARA_NUM_PATTERN.findall(text)
    if not matches:
        return None, None
    nums = [int(m) for m in matches]
    return min(nums), max(nums)


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
        r"FACTS\s+OF\s+THE\s+CASE"
        r"|MATERIAL\s+FACTS"
        r"|CASE\s+OF\s+THE\s+(?:APPELLANT|PETITIONER|PROSECUTION)"
        r"|FACTUAL\s+BACKGROUND"
        r"|THE\s+FACTS"
        r"|BRIEF\s+FACTS"
        r"|FACTUAL\s+MATRIX"
        r"|BACKGROUND\s+FACTS"
        r"|FACTS"
        r")",
        re.IGNORECASE,
    ),
    "ARGUMENTS": re.compile(
        r"(?:"
        r"SUBMISSIONS\s+OF\s+THE\s+PARTIES"
        r"|SUBMISSIONS\s+ON\s+BEHALF\s+OF"
        r"|HEARD\s+(?:LEARNED\s+)?COUNSEL"
        r"|RIVAL\s+(?:SUBMISSIONS|CONTENTIONS)"
        r"|ARGUMENTS\s+(?:ON\s+BEHALF|ADVANCED)"
        r"|ARGUMENTS"
        r"|SUBMISSIONS"
        r"|CONTENTIONS"
        r"|LEARNED\s+COUNSEL"
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
        r"ANALYSIS\s+AND\s+DISCUSSION"
        r"|OUR\s+ANALYSIS"
        r"|ANALYSIS"
        r"|DISCUSSION"
        r"|CONSIDERATION"
        r"|HAVING\s+HEARD"
        r"|I\s+HAVE\s+CONSIDERED"
        r"|WE\s+HAVE\s+CONSIDERED"
        r"|REASONING"
        r")",
        re.IGNORECASE,
    ),
    "RATIO": re.compile(
        r"(?:"
        r"RATIO\s+DECIDENDI"
        r"|CONCLUSION"
        r"|FINDINGS\s+AND\s+CONCLUSION"
        r"|FINDINGS"
        r"|WE\s+(?:ACCORDINGLY\s+)?HOLD"
        r")",
        re.IGNORECASE,
    ),
    "ORDER": re.compile(
        r"(?:"
        r"O\s*R\s*D\s*E\s*R"
        r"|FINAL\s+ORDER"
        r"|DISPOSITION"
        r"|IN\s+THE\s+RESULT"
        r"|THE\s+(?:PETITION|WRIT\s+PETITION|APPEAL|SUIT|SLP)\s+IS\s+(?:HEREBY\s+)?(?:ALLOWED|DISMISSED|DISPOSED)"
        r")",
        re.IGNORECASE,
    ),
    "DISSENT": re.compile(
        r"(?:"
        r"DISSENTING\s+(?:OPINION|JUDGMENT|VIEW)"
        r"|PER\s+.*?\s*\(?\s*DISSENTING\s*\)?"
        r"|MINORITY\s+(?:VIEW|OPINION|JUDGMENT)"
        r")",
        re.IGNORECASE,
    ),
    "CONCURRENCE": re.compile(
        r"(?:"
        r"CONCURRING\s+(?:OPINION|JUDGMENT|VIEW)"
        r"|PER\s+.*?\s*\(?\s*CONCURRING\s*\)?"
        r"|SEPARATE\s+(?:BUT\s+CONCURRING\s+)?OPINION"
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
# Heading position check
# ---------------------------------------------------------------------------


def _is_heading_position(text: str, match_start: int) -> bool:
    """Check if a match is at a line-start heading position, not mid-sentence."""
    # Find the start of the line containing this match
    line_start = text.rfind('\n', 0, match_start)
    line_start = line_start + 1 if line_start != -1 else 0

    # Text between line start and match should be empty or only numbering/whitespace
    prefix = text[line_start:match_start].strip()
    if not prefix:
        return True
    # Allow Roman numerals, digits, letters with dots: "I.", "1.", "A)", "(a)"
    if re.match(r'^(?:[IVXLC]+[\.\):]|[0-9]+[\.\):]|[A-Z][\.\)]|\([a-zA-Z0-9]+\))\s*$', prefix):
        return True
    return False


# ---------------------------------------------------------------------------
# Break-point detection for sentence-boundary-aware chunking
# ---------------------------------------------------------------------------


def _find_break_point(text: str, start: int, end: int, min_chunk: int = 500) -> int:
    """Find best break point near end, preferring paragraph > sentence > word."""
    if end >= len(text):
        return end
    search_start = max(start + min_chunk, end - 400)
    # Try paragraph break
    para = text.rfind('\n\n', search_start, end)
    if para != -1:
        return para + 2
    # Try sentence break
    for sep in ['. ', '.\n', ';\n', '?\n', '!\n']:
        sent = text.rfind(sep, search_start, end)
        if sent != -1:
            return sent + len(sep)
    # Try word break
    word = text.rfind(' ', search_start, end)
    if word != -1:
        return word + 1
    return end


# ---------------------------------------------------------------------------
# Section detection
# ---------------------------------------------------------------------------


def detect_judgment_sections(text: str) -> list[Section]:
    """Detect structural sections in a judgment using regex pattern matching.

    Scans the full text for known section headings, sorts matches by their
    character position, and returns non-overlapping ``Section`` objects whose
    ``text`` spans from one heading to the next.

    Only matches at heading positions (line-start) are considered, preventing
    mid-sentence false positives.

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
            if _is_heading_position(text, match.start()):
                markers.append((match.start(), section_type))

    if not markers:
        return []

    # Sort by position in the text.
    markers.sort(key=lambda m: m[0])

    # De-duplicate: drop ANY marker within 50 chars of the previous,
    # regardless of type, to avoid spurious section splits (cross-type
    # proximity dedup).
    deduped: list[tuple[int, str]] = []
    for pos, stype in markers:
        if deduped and (pos - deduped[-1][0]) < 50:
            continue  # Drop any marker too close to previous, regardless of type
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

    Uses intelligent break-point detection that prefers paragraph boundaries
    over sentence boundaries over word boundaries.

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
            raw_end = min(pos + CHUNK_SIZE, section_len)
            end = _find_break_point(section_text, pos, raw_end)
            chunk_text = section_text[pos:end]

            # Only emit non-empty chunks.
            if chunk_text.strip():
                para_start, para_end = _detect_paragraph_range(chunk_text)
                chunks.append(
                    Chunk(
                        text=chunk_text,
                        section_type=section.type,
                        chunk_index=chunk_idx,
                        case_id=case_id,
                        para_start=para_start,
                        para_end=para_end,
                    )
                )
                chunk_idx += 1

            # Advance by (actual_chunk_len - CHUNK_OVERLAP) for overlap.
            actual_chunk_len = end - pos
            next_pos = pos + max(actual_chunk_len - CHUNK_OVERLAP, 1)

            # If the remaining text after next_pos is smaller than the
            # overlap, we have already captured it -- stop to avoid a
            # near-duplicate trailing chunk.
            if next_pos >= section_len or (section_len - next_pos) <= CHUNK_OVERLAP:
                break

            pos = next_pos

    return chunks
