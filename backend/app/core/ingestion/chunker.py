"""Legal-aware text chunking for Indian court judgments.

Detects structural sections (FACTS, ARGUMENTS, ANALYSIS, etc.) via regex
patterns and chunks text while respecting section boundaries.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

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
    section_type: str  # HEADER, FACTS, ARGUMENTS, ISSUES, ANALYSIS, RATIO, ORDER, DISSENT, CONCURRENCE, PRELIMINARY, EVIDENCE, STATUTORY, DIRECTIONS, TOC, EDITORIAL, PER_CURIAM, PROCEDURAL, JUDGMENT_START, FULL
    chunk_index: int
    case_id: str
    page_number: int | None = None
    para_start: int | None = None
    para_end: int | None = None
    opinion_author: str | None = None
    legal_signal: float = 0.0  # V3: signal phrase density (higher = more likely a holding)


# ---------------------------------------------------------------------------
# V3: Legal signal scoring
# ---------------------------------------------------------------------------

_LEGAL_SIGNAL_PHRASES: tuple[str, ...] = (
    "held that", "we hold", "in our opinion", "it is well settled",
    "the ratio", "we are of the view", "the principle",
    "we approve", "we overrule", "we distinguish",
    "the question is answered", "the appeal is allowed",
    "the appeal is dismissed", "we are of the considered view",
    "in our considered opinion", "we accordingly hold",
)


_LEGAL_SIGNAL_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(p) for p in _LEGAL_SIGNAL_PHRASES) + r")\b"
)


def _compute_legal_signal(text: str) -> float:
    """Compute legal signal density: count of signal phrases per 1000 chars."""
    if not text:
        return 0.0
    text_lower = text.lower()
    count = len(_LEGAL_SIGNAL_RE.findall(text_lower))
    return round(count / len(text) * 1000, 2)


# ---------------------------------------------------------------------------
# Paragraph number detection
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Per-judge opinion author detection
# ---------------------------------------------------------------------------

_OPINION_AUTHOR_RE = re.compile(
    r'^[ \t]*(?:\[?\(?Per[ \t]+)?'              # optional "Per" with optional bracket/paren
    r'([A-Z][A-Za-z.]+(?:[ \t]+[A-Za-z.]+)*)'  # judge name (initials + surname, single line)
    r',?[ \t]*(?:C\.?J\.?I\.?|J\.?)[ \t]*'     # J. or CJI
    r'(?:\)?\]?)[ \t]*$',                       # optional closing bracket/paren
    re.MULTILINE,
)


def _detect_opinion_authors(text: str) -> list[tuple[int, str]]:
    """Detect per-judge opinion boundaries in the full text.

    Scans for judge name headers like ``D.Y. CHANDRACHUD, J.`` or
    ``[Per S. RAVINDRA BHAT, J.]`` and returns their positions.

    Returns:
        List of ``(position, judge_name)`` tuples sorted by position.
    """
    authors: list[tuple[int, str]] = []
    for match in _OPINION_AUTHOR_RE.finditer(text):
        name = match.group(1).strip()
        # Clean up: collapse whitespace, remove trailing comma
        name = re.sub(r'\s+', ' ', name).strip().rstrip(',')
        if name and len(name) > 2:  # Skip very short matches
            authors.append((match.start(), name))
    return sorted(authors, key=lambda x: x[0])


_PARA_NUM_PATTERN = re.compile(
    r"^\s*(?:\((\d+)\)|\[(\d+)\]|(\d+)[\.\)]|(?:Para\.?\s*(\d+)))\s",
    re.MULTILINE,
)


def _detect_paragraph_range(text: str) -> tuple[int | None, int | None]:
    """Detect the range of paragraph numbers in a chunk of text.

    Indian SC judgments use numbered paragraphs in various formats:
    '1. The appellant...', '(1) The facts...', '[1] Held...', 'Para 1 ...'
    """
    matches = _PARA_NUM_PATTERN.findall(text)
    if not matches:
        return None, None
    # Each match is a tuple of capture groups; extract the non-empty one
    nums = [int(g) for groups in matches for g in groups if g]
    if not nums:
        return None, None
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
        r"|REPORTABLE"
        r"|NON[\s-]*REPORTABLE"
        r")",
        re.IGNORECASE,
    ),
    # JUDGMENT marker starts the judgment body — separate from HEADER
    # so it doesn't create a second bloated HEADER mid-document.
    "JUDGMENT_START": re.compile(
        r"(?:"
        r"JUDGMENT"
        r"|J\s*U\s*D\s*G\s*M\s*E\s*N\s*T"
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
    "PRELIMINARY": re.compile(
        r"(?:PRELIMINARY|BACKGROUND(?!\s+FACTS))",
        re.IGNORECASE,
    ),
    "EVIDENCE": re.compile(
        r"(?:EVIDENCE\s+ON\s+RECORD|APPRECIATION\s+OF\s+EVIDENCE|OCULAR\s+EVIDENCE"
        r"|DOCUMENTARY\s+EVIDENCE|MEDICAL\s+EVIDENCE|ORAL\s+EVIDENCE)",
        re.IGNORECASE,
    ),
    "STATUTORY": re.compile(
        r"(?:STATUTORY\s+FRAMEWORK|RELEVANT\s+PROVISIONS|STATUTORY\s+PROVISIONS|THE\s+LAW)",
        re.IGNORECASE,
    ),
    "TOC": re.compile(
        r"(?:"
        r"TABLE\s+OF\s+CONTENTS"
        r"|INDEX"
        r"|CONTENTS"
        r"|LIST\s+OF\s+(?:DATES|EVENTS)"
        r"|SYNOPSIS"
        r"|HEADNOTE"
        r"|HEAD\s*NOTE"
        r")",
        re.IGNORECASE,
    ),
    "EDITORIAL": re.compile(
        r"(?:"
        r"EDITOR(?:'S)?\s+NOTE"
        r"|EDITORIAL\s+NOTE"
        r"|CATCHWORDS"
        r"|CATCH\s+WORDS"
        r"|CITATOR"
        r"|REPORTER'?S?\s+NOTE"
        r"|SUMMARY\s+OF\s+THE\s+CASE"
        r"|BENCH\s*:\s*"
        r")",
        re.IGNORECASE,
    ),
    "DIRECTIONS": re.compile(
        r"(?:DIRECTIONS?\s+(?:ISSUED)?|RELIEF\s+GRANTED)",
        re.IGNORECASE,
    ),
    "PER_CURIAM": re.compile(
        r"(?:PER\s+CURIAM|BY\s+THE\s+COURT)",
        re.IGNORECASE,
    ),
}

# ---------------------------------------------------------------------------
# Chunking parameters
# ---------------------------------------------------------------------------

CHUNK_SIZE: int = 2000
CHUNK_OVERLAP: int = 200
# Dense legal sections get smaller, more focused chunks
_DENSE_SECTIONS: frozenset[str] = frozenset({"ANALYSIS", "RATIO", "ORDER", "DISSENT", "CONCURRENCE"})
_DENSE_CHUNK_SIZE: int = 1200
_DENSE_CHUNK_OVERLAP: int = 300

# All valid section types produced by the chunker.  Used to validate
# section labels and prevent typos from creating unfilterable chunks.
VALID_SECTION_TYPES: frozenset[str] = frozenset({
    "HEADER", "JUDGMENT_START", "FACTS", "ARGUMENTS", "ISSUES",
    "ANALYSIS", "RATIO", "ORDER", "DISSENT", "CONCURRENCE",
    "PRELIMINARY", "EVIDENCE", "STATUTORY", "TOC", "EDITORIAL",
    "DIRECTIONS", "PER_CURIAM", "PROCEDURAL", "FULL",
})


# ---------------------------------------------------------------------------
# Heading position check
# ---------------------------------------------------------------------------


def _is_heading_position(text: str, match_start: int) -> bool:
    """Check if a match is at a line-start heading position, not mid-sentence."""
    # Find the start of the line containing this match
    line_start = text.rfind('\n', 0, match_start)
    line_start = line_start + 1 if line_start != -1 else 0

    # Find the end of the line
    line_end = text.find('\n', match_start)
    if line_end == -1:
        line_end = len(text)
    line_length = line_end - line_start

    # Headings are short lines; body text is long
    if line_length > 100:
        return False

    # Text between line start and match should be empty or only numbering/whitespace
    prefix = text[line_start:match_start].strip()
    if not prefix:
        return True
    # Allow Roman numerals, digits, letters with dots: "I.", "1.", "A)", "(a)"
    return bool(re.match("^(?:[IVXLC]+[\\.\\):]|[0-9]+[\\.\\):]|[A-Z][\\.\\)]|\\([a-zA-Z0-9]+\\))\\s*$", prefix))


# ---------------------------------------------------------------------------
# Break-point detection for sentence-boundary-aware chunking
# ---------------------------------------------------------------------------

_LEGAL_ABBREVS_RE = re.compile(
    r'\b(?:vs?|Dr|Mr|Mrs|Smt|Hon|Ld|Sr|Jr|No|Art|Sec|Vol|Ch|'
    r'Ltd|Pvt|Govt|Ors|Anr|St|viz|'
    r'I\.?P\.?C|Cr\.?P\.?C|C\.?P\.?C|B\.?N\.?S|S\.?C\.?C|'
    r'A\.?I\.?R|N\.?C\.?L\.?T|I\.?B\.?C|[A-Z])\.$'
)


def _is_abbreviation(text: str, period_pos: int) -> bool:
    """Check if the period at *period_pos* belongs to a legal abbreviation."""
    # Look at the preceding text (up to 10 chars before the period)
    preceding = text[max(0, period_pos - 10):period_pos + 1]
    return _LEGAL_ABBREVS_RE.search(preceding) is not None


def _find_break_point(text: str, start: int, end: int, min_chunk: int = 500) -> int:
    """Find best break point near end, preferring paragraph > sentence > word."""
    if end >= len(text):
        return end
    search_start = max(start + min_chunk, end - 400)
    # Try paragraph break
    para = text.rfind('\n\n', search_start, end)
    if para != -1:
        return para + 2
    # Try sentence break (abbreviation-aware)
    for sep in ['. ', '.\n', ';\n', '?\n', '!\n']:
        search_pos = end
        while True:
            sent = text.rfind(sep, search_start, search_pos)
            if sent == -1:
                break
            # For period-based separators, check abbreviation
            if sep.startswith('.') and _is_abbreviation(text, sent):
                search_pos = sent  # skip this one, keep searching earlier
                continue
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

    # De-duplicate markers by proximity: same type within 50 chars = dedup;
    # different types within 20 chars = dedup; different types beyond 20 = keep.
    deduped: list[tuple[int, str]] = []
    for pos, stype in markers:
        if deduped:
            prev_pos, prev_type = deduped[-1]
            dist = pos - prev_pos
            if stype == prev_type and dist < 50:
                continue  # Same type, close together = dedup
            if stype != prev_type and dist < 20:
                continue  # Different types, very close = dedup
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

    # ── Post-processing: split bloated HEADER and fix mislabeled sections ──

    sections = _split_bloated_header(sections, text)
    sections = _fix_mislabeled_sections(sections)

    return sections


# Maximum HEADER size before we split it — SCR editorial headnotes
# often inflate HEADER to 5-20K chars
_MAX_HEADER_CHARS = 3000

# SCR lettered margin markers (page column indicators)
_SCR_MARGIN_RE = re.compile(r"^\s*[A-H]\s*$", re.MULTILINE)

# SCR HELD: pattern in editorial headnotes
_SCR_HELD_RE = re.compile(r"\bHELD\s*:", re.IGNORECASE)

# Bench composition pattern: "[JUDGE1 AND JUDGE2, JJ.]"
_BENCH_RE = re.compile(r"\[.*?JJ?\.?\s*\]")

# Testimony indicators for section mislabeling check
_TESTIMONY_KEYWORDS = {
    "cross-examination", "cross examination", "pw-", "dw-",
    "witness stated", "witness deposed", "deposed that",
    "under examination", "it is wrong to suggest",
}


def _split_bloated_header(
    sections: list[Section], text: str
) -> list[Section]:
    """Split a bloated HEADER section into HEADER + EDITORIAL.

    SCR-formatted cases have reporter editorial content (headnotes with
    lettered A-H margins, HELD: summaries) that inflates the HEADER section
    to 5-20K chars.  This function detects SCR editorial content within an
    oversized HEADER and splits it off into a separate EDITORIAL section,
    leaving HEADER as just the case preamble (title, bench, date).
    """
    if not sections or sections[0].type != "HEADER":
        return sections
    header = sections[0]
    if len(header.text) <= _MAX_HEADER_CHARS:
        return sections  # HEADER is a reasonable size

    header_text = header.text

    # Detect SCR editorial markers in the header
    margins = list(_SCR_MARGIN_RE.finditer(header_text[:15_000]))
    held = _SCR_HELD_RE.search(header_text[:5000])

    if len(margins) < 2 and not held:
        # Not SCR format — don't split, but still cap the header display
        # by inserting an EDITORIAL section after the bench line
        bench = _BENCH_RE.search(header_text[:2000])
        if bench:
            split_pos = bench.end()
            # Skip trailing whitespace
            while split_pos < len(header_text) and header_text[split_pos] in "\n\r \t":
                split_pos += 1
            if split_pos < len(header_text) - 200:
                new_header = Section(
                    type="HEADER",
                    start=header.start,
                    end=header.start + split_pos,
                    text=header_text[:split_pos],
                )
                new_editorial = Section(
                    type="EDITORIAL",
                    start=header.start + split_pos,
                    end=header.end,
                    text=header_text[split_pos:],
                )
                return [new_header, new_editorial] + sections[1:]
        return sections

    # SCR format detected — find the split point
    # The editorial starts after the bench/date line
    bench = _BENCH_RE.search(header_text[:2000])
    if bench:
        split_pos = bench.end()
        while split_pos < len(header_text) and header_text[split_pos] in "\n\r \t":
            split_pos += 1
    elif held:
        # No bench pattern — split at HELD: position (fallback)
        split_pos = max(held.start() - 50, 0)  # A bit before HELD:
    else:
        # Split at first margin
        split_pos = margins[0].start()

    if split_pos >= len(header_text) - 200:
        return sections  # Nothing meaningful to split

    new_header = Section(
        type="HEADER",
        start=header.start,
        end=header.start + split_pos,
        text=header_text[:split_pos],
    )
    new_editorial = Section(
        type="EDITORIAL",
        start=header.start + split_pos,
        end=header.end,
        text=header_text[split_pos:],
    )
    return [new_header, new_editorial] + sections[1:]


def _fix_mislabeled_sections(sections: list[Section]) -> list[Section]:
    """Fix sections whose content doesn't match their label.

    - TOC starting with "Headnotes" → relabel as EDITORIAL (SCR reporter content)
    - ORDER starting with "ORDER AND APPEARANCES" → relabel as PROCEDURAL
    - ARGUMENTS containing witness testimony → relabel as EVIDENCE
    - Very small non-primary sections (<100 chars) → merge into previous
    """
    fixed: list[Section] = []
    for sec in sections:
        # TOC containing SCR reporter headnotes → EDITORIAL
        if sec.type == "TOC":
            stripped = sec.text.lstrip()
            if stripped[:20].upper().startswith("HEADNOTE"):
                sec = Section(
                    type="EDITORIAL",
                    start=sec.start,
                    end=sec.end,
                    text=sec.text,
                )

        # ORDER that's actually an appearance/jurisdiction block → PROCEDURAL
        if sec.type == "ORDER":
            stripped = sec.text.lstrip()
            upper_start = stripped[:60].upper()
            if ("ORDER AND APPEARANCES" in upper_start
                    or "APPELLATE JURISDICTION" in upper_start
                    or "ORIGINAL JURISDICTION" in upper_start):
                sec = Section(
                    type="PROCEDURAL",
                    start=sec.start,
                    end=sec.end,
                    text=sec.text,
                )

        # ARGUMENTS containing witness testimony → EVIDENCE
        if sec.type == "ARGUMENTS":
            sample = sec.text[:3000].lower()
            testimony_hits = sum(
                1 for kw in _TESTIMONY_KEYWORDS if kw in sample
            )
            if testimony_hits >= 2:
                sec = Section(
                    type="EVIDENCE",
                    start=sec.start,
                    end=sec.end,
                    text=sec.text,
                )

        # Merge tiny sections into previous (only for non-primary types)
        _PRIMARY_TYPES = {"HEADER", "FACTS", "ARGUMENTS", "ANALYSIS", "RATIO", "ORDER",
                          "DISSENT", "CONCURRENCE", "EVIDENCE", "ISSUES", "EDITORIAL",
                          "PROCEDURAL", "JUDGMENT_START"}
        if (fixed and len(sec.text.strip()) < 100
                and sec.type not in _PRIMARY_TYPES):
            prev = fixed[-1]
            merged = Section(
                type=prev.type,
                start=prev.start,
                end=sec.end,
                text=text_between(prev, sec),
            )
            fixed[-1] = merged
            continue

        fixed.append(sec)
    return fixed


def text_between(s1: Section, s2: Section) -> str:
    """Combine text from two adjacent sections."""
    return s1.text + s2.text


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

    # Detect per-judge opinion boundaries in the full text.
    opinion_authors = _detect_opinion_authors(text)

    chunks: list[Chunk] = []
    chunk_idx = 0

    for section in sections:
        section_text = section.text
        section_len = len(section_text)

        if section_len == 0:
            continue

        # Validate section type against known set
        if section.type not in VALID_SECTION_TYPES:
            logger.warning(
                "Unknown section type %r in case %s — normalizing to FULL",
                section.type, case_id,
            )
            section = Section(
                type="FULL", start=section.start, end=section.end, text=section.text,
            )

        # Section-aware chunk sizing
        effective_chunk_size = _DENSE_CHUNK_SIZE if section.type in _DENSE_SECTIONS else CHUNK_SIZE
        effective_overlap = _DENSE_CHUNK_OVERLAP if section.type in _DENSE_SECTIONS else CHUNK_OVERLAP

        pos = 0
        while pos < section_len:
            raw_end = min(pos + effective_chunk_size, section_len)
            end = _find_break_point(section_text, pos, raw_end)
            chunk_text = section_text[pos:end]

            # Only emit non-empty chunks.
            if chunk_text.strip():
                para_start, para_end = _detect_paragraph_range(chunk_text)

                # Determine which opinion author covers this chunk.
                chunk_pos_in_text = section.start + pos
                current_author = None
                for author_pos, author_name in opinion_authors:
                    if author_pos <= chunk_pos_in_text:
                        current_author = author_name
                    else:
                        break

                signal = _compute_legal_signal(chunk_text)
                chunks.append(
                    Chunk(
                        text=chunk_text,
                        section_type=section.type,
                        chunk_index=chunk_idx,
                        case_id=case_id,
                        para_start=para_start,
                        para_end=para_end,
                        opinion_author=current_author,
                        legal_signal=signal,
                    )
                )
                chunk_idx += 1

            # Advance by (actual_chunk_len - effective_overlap) for overlap.
            actual_chunk_len = end - pos
            next_pos = pos + max(actual_chunk_len - effective_overlap, 1)

            # Snap overlap start to nearest sentence boundary to avoid mid-word fragments
            # Search forward for a period-space that isn't an abbreviation
            search_pos = next_pos
            while search_pos < next_pos + 100:
                snap = section_text.find('. ', search_pos)
                if snap == -1 or snap >= next_pos + 100:
                    break
                if not _is_abbreviation(section_text, snap):
                    next_pos = snap + 2
                    break
                search_pos = snap + 2  # skip this abbreviation, keep searching

            # If the remaining text after next_pos is smaller than the
            # overlap, we have already captured it -- stop to avoid a
            # near-duplicate trailing chunk.
            if next_pos >= section_len or (section_len - next_pos) <= effective_overlap:
                break

            pos = next_pos

    return chunks
