"""PDF text extraction with pdfplumber and OCR fallback.

Provides clean, high-quality text extraction from Indian court judgment PDFs.
Includes per-page hybrid extraction (pdfplumber + OCR fallback), Unicode
normalization, header/footer deduplication, and extraction quality assessment.
"""

from __future__ import annotations

import asyncio
import logging
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field

import pdfplumber
from pdfminer.psparser import PSException

try:
    from pdfminer.pdfdocument import PDFPasswordIncorrect
except ImportError:  # pragma: no cover
    PDFPasswordIncorrect = None  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)

# Safety limit: refuse to process PDFs with more pages than this
MAX_PAGES = 5000
MAX_OCR_PAGES = 500

# Patterns that indicate the start of a new judgment
_JUDGMENT_START_PATTERNS = [
    re.compile(r"IN\s+THE\s+SUPREME\s+COURT\s+OF\s+INDIA", re.IGNORECASE),
    re.compile(r"IN\s+THE\s+HIGH\s+COURT\s+OF", re.IGNORECASE),
    re.compile(r"\b(REPORTABLE|NON[\s-]?REPORTABLE)\b", re.IGNORECASE),
    re.compile(r"^\s*(JUDGMENT|ORDER)\s*$", re.IGNORECASE | re.MULTILINE),
    re.compile(r"\b(CIVIL|CRIMINAL)\s+APPEAL\s+NO", re.IGNORECASE),
    re.compile(r"\b(WRIT\s+PETITION|SPECIAL\s+LEAVE\s+PETITION)\b", re.IGNORECASE),
    re.compile(r"\bSLP\s*\(\s*(C|Crl)\s*\)\s*No", re.IGNORECASE),
    re.compile(r"\d{4}:\s*INSC:\s*\d+"),  # Neutral citation
]


_CASE_TITLE_RE = re.compile(r"\bv[s]?\.\s", re.IGNORECASE)


def _strip_leading_judgment_bleed(
    text: str,
    scan_chars: int = 3000,
    min_bleed: int = 100,
) -> str:
    """Remove leading text from a previous judgment that bleeds into this PDF.

    Scans the first ``scan_chars`` characters for case header markers. If the
    earliest marker appears after ``min_bleed`` characters, everything before
    it is considered bleed from a previous judgment and is stripped.

    Safety: only strips when the leading text actually looks like bleed —
    starts mid-sentence (lowercase) or lacks a case title pattern ("v.").
    If the leading text has a proper case title, it's likely a legitimate
    preamble and is preserved.

    Args:
        text: Full extracted text.
        scan_chars: How many chars from the start to scan for markers.
        min_bleed: Minimum chars before marker to consider it bleed (avoids
            stripping legitimate short preambles).  Lowered from 200 to 100
            to catch short reporter preambles in pre-1990 PDFs.

    Returns:
        Text with leading bleed removed, or original text if no bleed detected.
    """
    if len(text) < min_bleed:
        return text

    scan_region = text[:scan_chars]
    earliest_pos = scan_chars  # sentinel

    for pattern in _JUDGMENT_START_PATTERNS:
        match = pattern.search(scan_region)
        if match and match.start() < earliest_pos:
            earliest_pos = match.start()

    if earliest_pos >= min_bleed and earliest_pos < scan_chars:
        candidate = text[:earliest_pos]

        # Safety check: verify the candidate text looks like bleed, not
        # legitimate preamble.  Bleed typically starts mid-sentence
        # (lowercase first character) or lacks a case title pattern.
        first_non_ws = candidate.lstrip()
        starts_mid_sentence = bool(first_non_ws) and first_non_ws[0].islower()
        has_case_title = bool(_CASE_TITLE_RE.search(candidate))

        if starts_mid_sentence or not has_case_title:
            logger.info(
                "Stripped %d chars of leading judgment bleed (marker at pos %d, "
                "mid_sentence=%s, has_title=%s)",
                earliest_pos, earliest_pos, starts_mid_sentence, has_case_title,
            )
            return text[earliest_pos:]
        else:
            logger.debug(
                "Bleed candidate (%d chars) has case title and proper start — "
                "preserving as legitimate preamble",
                earliest_pos,
            )

    return text


# ---------------------------------------------------------------------------
# SCR editorial content stripping
# ---------------------------------------------------------------------------

# SCR lettered margin markers: standalone A-H on a line (column indicators)
_SCR_LETTERED_MARGIN_RE = re.compile(r"^\s*[A-H]\s*$", re.MULTILINE)

# SCR page header: "596 SUPREME COURT REPORTS [2022] 10 S.C.R."
_SCR_PAGE_HEADER_RE = re.compile(
    r"^\s*\d+\s+SUPREME\s+COURT\s+REPORTS\b.*$", re.MULTILINE | re.IGNORECASE
)

# SCR editorial "HELD:" pattern (appears in reporter headnotes, not the judgment)
_SCR_HELD_RE = re.compile(r"\bHELD\s*:", re.IGNORECASE)

# Author judge announcement: "KRISHNA IYER, J.—" or "Per KRISHNA IYER, J."
_AUTHOR_ANNOUNCE_RE = re.compile(
    r"(?:[A-Z][A-Z\s\.]{3,},\s*J\.?\s*[–—-]|"
    r"Per\s+[A-Z][A-Za-z\s\.]+,?\s*J\.?\s*[):\-–—])",
)

# Case intro pattern: "This appeal..." / "The appellant..."
_CASE_INTRO_RE = re.compile(
    r"(?:This\s+(?:appeal|petition|case|writ|matter|reference|review|application)"
    r"|The\s+(?:appellant|petitioner|prosecution|respondent|complainant|facts)"
    r"|Leave\s+granted"
    r"|We\s+have\s+heard"
    r"|By\s+this\s+(?:appeal|petition|writ))\s+",
    re.IGNORECASE,
)

# SCR case title (appears right after reporter bleed)
_SCR_CASE_TITLE_END_RE = re.compile(
    r"\[.*?JJ?\.?\s*\]",  # "[JUDGE1 AND JUDGE2, JJ.]" bench composition
)


def strip_reporter_editorial(
    text: str,
    scan_chars: int = 25_000,
    min_margins: int = 3,
) -> tuple[str, str]:
    """Strip SCR/SCC reporter editorial content (headnotes, catchwords, digests).

    SCR-format PDFs contain reporter-added editorial content BEFORE the actual
    judgment text: structured headnotes with HELD: summaries, lettered page-margin
    indicators (A-H), catchwords, and case references. This function detects and
    removes the editorial block between the case preamble and the judgment body.

    Detection uses lettered margin count (A-H standalone lines) as the primary
    signal — SCR pages consistently have 3+ such indicators.

    The editorial block boundary is identified by (in order of reliability):
    1. Author judge announcement ("NAME, J.—" or "Per NAME, J.")
    2. SCR page header ("NNN SUPREME COURT REPORTS [YEAR]...")
       followed by the actual judgment text
    3. Transition sentence ("Dismissing the appeals, the Court")

    Note: lettered margins (A-H) appear throughout SCR text as page-column
    indicators, NOT just in the editorial section. They cannot be used as
    editorial-end boundaries.

    Args:
        text: Full extracted text from the PDF.
        scan_chars: How many characters from the start to scan.
        min_margins: Minimum lettered margin count to classify as SCR format.

    Returns:
        Tuple of (cleaned_text, stripped_editorial). If no editorial detected,
        stripped_editorial is empty and cleaned_text == text.
    """
    if len(text) < 500:
        return text, ""

    scan_region = text[:scan_chars]

    # Step 1: Detect SCR format via lettered margin count in first 10K chars
    # (first 10K is enough to confirm SCR format without counting margins in
    # the judgment body)
    early_margins = list(_SCR_LETTERED_MARGIN_RE.finditer(text[:10_000]))
    if len(early_margins) < min_margins:
        return text, ""  # Not SCR format

    # Step 2: Find the bench composition line — marks end of case preamble.
    bench_match = _SCR_CASE_TITLE_END_RE.search(scan_region[:2000])
    if not bench_match:
        # No bench line found — can't reliably identify preamble end
        return text, ""

    preamble_end = bench_match.end()
    # Skip trailing whitespace/newlines after bench line
    while preamble_end < len(scan_region) and scan_region[preamble_end] in "\n\r \t":
        preamble_end += 1

    # Step 3: Find where the judgment begins (after editorial content).
    # The editorial typically spans from preamble_end to ~2000-8000 chars.
    # We look for reliable judgment-start markers AFTER the editorial.

    held_match = _SCR_HELD_RE.search(scan_region[preamble_end:])
    held_pos = (preamble_end + held_match.start()) if held_match else preamble_end

    # Minimum: must be after HELD: and at least 500 chars of editorial
    min_judgment_start = max(preamble_end + 500, held_pos + 100)

    judgment_start: int | None = None

    # Strategy a: Author judge announcement (most reliable)
    for match in _AUTHOR_ANNOUNCE_RE.finditer(scan_region):
        if match.start() > min_judgment_start:
            judgment_start = match.start()
            break

    # Strategy b: Transition sentence ("Dismissing/Allowing the appeal...")
    if judgment_start is None:
        _TRANSITION_RE = re.compile(
            r"(?:Dismissing|Allowing|Disposing\s+of|Setting\s+aside|Affirming)"
            r"\s+the\s+(?:appeal|petition|writ|review|case)",
            re.IGNORECASE,
        )
        for match in _TRANSITION_RE.finditer(scan_region):
            if match.start() > min_judgment_start:
                judgment_start = match.start()
                break

    # Strategy c: First SCR page header after sufficient editorial
    if judgment_start is None:
        for match in _SCR_PAGE_HEADER_RE.finditer(scan_region):
            # Must be well after preamble (editorial is at least 1500 chars)
            if match.start() > preamble_end + 1500:
                judgment_start = match.start()
                break

    if judgment_start is None:
        # Could not find a reliable judgment start — don't strip
        logger.debug(
            "SCR format detected (%d margins in first 10K) but no judgment "
            "start found — not stripping editorial",
            len(early_margins),
        )
        return text, ""

    # Sanity: editorial should be at least 300 chars and less than 20K
    editorial_size = judgment_start - preamble_end
    if editorial_size < 300 or editorial_size > 20_000:
        logger.debug(
            "Editorial size %d chars out of expected range (300-20000) — not stripping",
            editorial_size,
        )
        return text, ""

    preamble = text[:preamble_end]
    editorial = text[preamble_end:judgment_start]
    judgment = text[judgment_start:]

    cleaned = preamble.rstrip() + "\n\n" + judgment.lstrip()

    logger.info(
        "Stripped %d chars of SCR editorial content (%d early margins, "
        "preamble ends at %d, judgment starts at %d)",
        len(editorial), len(early_margins), preamble_end, judgment_start,
    )

    return cleaned, editorial


# Characters to strip: zero-width space, BOM, soft hyphen
# Note: ZWNJ (U+200C) and ZWJ (U+200D) are preserved -- they are structurally
# meaningful in Devanagari script (conjunct formation control).
_ZERO_WIDTH_RE = re.compile(r"[\u200B\uFEFF\u00AD]")

# Standalone page numbers on their own line: optional dash, 1-4 digits, optional dash
_PAGE_NUMBER_RE = re.compile(r"^\s*-?\s*\d{1,4}\s*-?\s*$", re.MULTILINE)

# Three or more newlines -> collapse to two
_EXCESS_NEWLINES_RE = re.compile(r"\n{3,}")

# Trailing whitespace per line
_TRAILING_SPACES_RE = re.compile(r"[ \t]+$", re.MULTILINE)

# Terminal punctuation at end of text (ignoring trailing whitespace)
_TERMINAL_PUNCT_RE = re.compile(r"[.?!:]\s*$")

# Common court boilerplate that appears on every page
_BOILERPLATE_PATTERNS = [
    re.compile(r"^\s*REPORTABLE\s*$", re.IGNORECASE),
    re.compile(r"^\s*NON[- ]?REPORTABLE\s*$", re.IGNORECASE),
    re.compile(r"^\s*IN THE SUPREME COURT OF INDIA\s*$", re.IGNORECASE),
    re.compile(r"^\s*Page\s+\d+\s+of\s+\d+\s*$", re.IGNORECASE),
    re.compile(r"^\s*Digitally\s+signed\s+by\b.*$", re.IGNORECASE),
    re.compile(r"^\s*Date:\s*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\s*$", re.IGNORECASE),
    re.compile(r"^\s*ITEM\s+NO\.?\s*", re.IGNORECASE),
    re.compile(r"^\s*WWW\.LIVELAW\.IN\s*$", re.IGNORECASE),
    re.compile(r"^\s*UPON\s+hearing\b.*$", re.IGNORECASE),
]

# Reporter editorial metadata (bylines, result summaries, digest headers)
_EDITORIAL_RE = re.compile(
    r"^\s*(?:†\s*)?Headnotes?\s+prepared\s+by\s*:\s*.*$|"
    r"^\s*(?:†\s*)?Prepared\s+by\s*:\s*.*$|"
    r"^\s*(?:†\s*)?Formatted\s+by\s*:\s*.*$|"
    r"^\s*(?:†\s*)?Compiled\s+by\s*:\s*.*$|"
    r"^\s*Result\s+of\s+the\s+case\s*:.*$|"
    r"^\s*Digest\s*:.*$|"
    r"^\s*Catchwords?\s*:?\s*$|"
    r"^\s*Cases\s+Referred\s*:?\s*$|"
    r"^\s*Cases\s+Cited\s*:?\s*$|"
    r"^\s*Legislation\s+Cited\s*:?\s*$",
    re.IGNORECASE | re.MULTILINE,
)

# Reporter page markers: SCR, SCC, AIR, SCALE, MANU
_REPORTER_PAGE_MARKER_RE = re.compile(
    # SCR: "[2026] 1 S.C.R. 63" or "64 [2026] 1 S.C.R."
    r"^\s*\[?\d{4}\]?\s+\d+\s+S\.?\s*C\.?\s*R\.?\s+\d+\s*$|"
    r"^\s*\d+\s+\[?\d{4}\]?\s+\d+\s+S\.?\s*C\.?\s*R\.?\s*$|"
    # SCC: (2024) 5 SCC 123 or (2024) 5 SCC (Cri) 123
    r"^\s*\(\d{4}\)\s+\d+\s+SCC\s+(?:\([A-Za-z]+\)\s+)?\d+\s*$|"
    # AIR: AIR 2024 SC 123
    r"^\s*AIR\s+\d{4}\s+SC\s+\d+\s*$|"
    # SCALE: (2024) 3 SCALE 456
    r"^\s*\(\d{4}\)\s+\d+\s+SCALE\s+\d+\s*$|"
    # MANU: MANU/SC/1234/2024
    r"^\s*MANU/\w+/\d+/\d{4}\s*$",
    re.MULTILINE,
)

# ---------------------------------------------------------------------------
# First-page reporter preamble stripping
# ---------------------------------------------------------------------------

# Reporter preamble lines commonly found on page 1 only (not repeated on later
# pages, so header/footer dedup misses them).  Stripped before smart join.
_FIRST_PAGE_PREAMBLE_RE = re.compile(
    r"^\s*(?:"
    # SCR header: "SUPREME COURT REPORTS [2022]" / "596 SUPREME COURT REPORTS ..."
    r"(?:\d+\s+)?SUPREME\s+COURT\s+REPORTS\b.*|"
    # SCC Online / SCC header
    r"SCC\s+Online\b.*|"
    # Reporter volume header: "[2024] 1 S.C.R." standalone
    r"\[?\d{4}\]?\s+\d+\s+S\.?\s*C\.?\s*R\.?\s*|"
    # "PETITIONER:" / "RESPONDENT:" labels (reporter formatting, not judgment text)
    r"(?:PETITIONER|RESPONDENT)\s*:\s*$|"
    # "DATE OF JUDGMENT:" / "DATE OF ORDER:" labels
    r"DATE\s+OF\s+(?:JUDGMENT|ORDER)\s*:\s*$|"
    # "BENCH:" label
    r"BENCH\s*:\s*$|"
    # "CITATION:" label
    r"CITATION\s*:\s*$"
    r")\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def _strip_first_page_preamble(text: str, scan_chars: int = 5000) -> str:
    """Remove reporter preamble lines from the first ~5000 chars.

    These lines appear only on page 1 (e.g. "SUPREME COURT REPORTS [2022]")
    and are missed by the 3-page header/footer dedup. Also strips any
    reporter page markers from the first page region.
    """
    if len(text) < 200:
        return text

    head = text[:scan_chars]
    tail = text[scan_chars:]

    original_len = len(head)
    head = _FIRST_PAGE_PREAMBLE_RE.sub("", head)
    # Also strip reporter page markers from first page
    head = _REPORTER_PAGE_MARKER_RE.sub("", head)

    stripped = original_len - len(head)
    if stripped > 0:
        # Collapse any resulting excess blank lines
        head = _EXCESS_NEWLINES_RE.sub("\n\n", head).lstrip("\n")
        logger.info("Stripped %d chars of first-page preamble", stripped)

    return head + tail


# Footnote reference in body text: superscript digits or [1], [2] etc.
_FOOTNOTE_REF_RE = re.compile(r"(?:\[(\d{1,3})\]|(?<!\d)(\d{1,2})(?=\s))")

# Footnote definition at bottom of page: "1. Some footnote text" or "[1] text"
_FOOTNOTE_DEF_RE = re.compile(
    r"^\s*(?:\[(\d{1,3})\]|(\d{1,3})[\.\)])\s+(.+)$",
    re.MULTILINE,
)


@dataclass
class TextQuality:
    """Quality assessment of extracted text."""
    text: str
    char_count: int
    tier: str  # "high", "medium", "low"
    ocr_used: bool
    legal_keyword_count: int
    page_count: int
    page_map: list[dict] = field(default_factory=list)
    ocr_truncated: bool = False
    ocr_total_pages: int = 0
    editorial_stripped: str = ""  # SCR reporter editorial content that was stripped


LEGAL_KEYWORDS = {
    "court", "petitioner", "respondent", "section", "act", "judgment",
    "order", "appeal", "bench", "hon'ble", "advocate", "counsel",
    "article", "constitution", "decree", "plaintiff", "defendant",
    "prosecution", "accused", "bail", "writ", "petition", "tribunal",
    "appellant", "versus", "v.", "vs.", "learned", "disposed",
}


# ---------------------------------------------------------------------------
# Text cleaning utilities
# ---------------------------------------------------------------------------


def clean_extracted_text(text: str) -> str:
    """Clean and normalize extracted PDF text.

    Applies Unicode normalization, removes zero-width characters, deduplicates
    repeated headers/footers, strips page numbers, normalizes dashes and
    whitespace.

    Args:
        text: Raw extracted text from PDF.

    Returns:
        Cleaned text ready for downstream processing.
    """
    if not text:
        return ""

    # 1. Unicode NFKC normalization -- collapse ligatures and compatibility chars
    text = unicodedata.normalize("NFKC", text)

    # 2. Remove zero-width characters and soft hyphens
    text = _ZERO_WIDTH_RE.sub("", text)

    # 2a. Strip control characters (except \n, \t, \r)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)

    # 3. Detect and remove repeated headers/footers
    text = _remove_repeated_headers_footers(text)

    # 4. Remove standalone page numbers
    text = _PAGE_NUMBER_RE.sub("", text)

    # 4a. Remove editorial metadata and reporter page markers
    text = _EDITORIAL_RE.sub("", text)
    text = _REPORTER_PAGE_MARKER_RE.sub("", text)

    # 5. Normalize dashes: em/en dashes between word characters -> hyphen
    #    e.g., "self\u2014defence" -> "self-defence" but preserve "-- " (em dash as punctuation)
    text = re.sub(r"(?<=\w)[\u2013\u2014](?=\w)", "-", text)

    # 6. Collapse excessive newlines and strip trailing spaces per line
    text = _TRAILING_SPACES_RE.sub("", text)
    text = _EXCESS_NEWLINES_RE.sub("\n\n", text)

    return text.strip()


def reattach_footnotes(text: str) -> str:
    """Detect footnote definitions and inline them near their references.

    Indian SC judgments often have footnotes at the end of pages that get
    separated during extraction. This function:
    1. Finds footnote definitions (e.g., "1. See AIR 1978 SC 248")
    2. Removes them from their original location
    3. Inserts them inline as "[Footnote N: text]" after the reference

    Only processes footnotes numbered 1-99 to avoid false positives.
    """
    # Extract footnote definitions
    footnotes: dict[int, str] = {}
    for match in _FOOTNOTE_DEF_RE.finditer(text):
        num = int(match.group(1) or match.group(2))
        if num > 99:
            continue
        fn_text = match.group(3).strip()
        if fn_text and len(fn_text) > 5:  # Skip trivially short "footnotes"
            footnotes[num] = fn_text

    if not footnotes:
        return text

    # Remove footnote definitions from the text
    cleaned = _FOOTNOTE_DEF_RE.sub("", text)

    # Insert footnotes inline where referenced
    for num, fn_text in sorted(footnotes.items()):
        # Look for [N] references and append footnote text
        pattern = re.compile(rf"\[{num}\]")
        replacement = f"[{num}] [Footnote {num}: {fn_text}]"
        cleaned = pattern.sub(replacement, cleaned, count=1)

    return cleaned


def _remove_repeated_headers_footers(text: str) -> str:
    """Remove lines that appear as headers/footers on 3+ pages.

    Splits text into page-like chunks using form-feed or triple-newline
    boundaries, finds lines appearing on 3+ pages, and removes duplicates
    (keeping the first occurrence).
    """
    # Split into page-like segments
    pages = re.split(r"\f|\n{3,}", text)
    if len(pages) < 3:
        # Not enough pages to detect repetition
        return text

    # Count how many pages each stripped line appears on
    line_page_count: Counter[str] = Counter()
    for page in pages:
        # Use a set so each line is counted once per page
        unique_lines = {line.strip() for line in page.splitlines() if line.strip()}
        for line in unique_lines:
            line_page_count[line] += 1

    # Lines appearing on 3+ pages are likely headers/footers
    repeated_lines = {
        line for line, count in line_page_count.items()
        if count >= 3 and len(line) < 200  # short lines only -- not real content
    }

    # Also add common boilerplate patterns
    for page in pages:
        for line in page.splitlines():
            stripped = line.strip()
            for pattern in _BOILERPLATE_PATTERNS:
                if pattern.match(stripped) and stripped:
                    repeated_lines.add(stripped)

    if not repeated_lines:
        return text

    # Remove duplicates but keep first occurrence of each
    seen_repeated: set[str] = set()
    output_lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped in repeated_lines:
            if stripped not in seen_repeated:
                seen_repeated.add(stripped)
                output_lines.append(line)
            # else: skip duplicate header/footer
        else:
            output_lines.append(line)

    return "\n".join(output_lines)


def _remove_repeated_headers_footers_pages(pages: list[str]) -> list[str]:
    """Remove repeated headers/footers from a list of page texts.

    Operates on per-page text list BEFORE smart join, which is more
    reliable than trying to re-split after joining.
    """
    if len(pages) < 3:
        return pages

    # Count how many pages each stripped line appears on
    line_page_count: Counter[str] = Counter()
    for page in pages:
        unique_lines = {line.strip() for line in page.splitlines() if line.strip()}
        for line in unique_lines:
            line_page_count[line] += 1

    # Lines appearing on 3+ pages are likely headers/footers
    repeated_lines = {
        line for line, count in line_page_count.items()
        if count >= 3 and len(line) < 200
    }

    # Also add common boilerplate patterns
    for page in pages:
        for line in page.splitlines():
            stripped = line.strip()
            for pattern in _BOILERPLATE_PATTERNS:
                if pattern.match(stripped) and stripped:
                    repeated_lines.add(stripped)

    if not repeated_lines:
        return pages

    # Remove all occurrences of repeated headers/footers from each page
    # (keep first occurrence globally via tracking)
    seen_repeated: set[str] = set()
    cleaned_pages: list[str] = []
    for page in pages:
        output_lines: list[str] = []
        for line in page.splitlines():
            stripped = line.strip()
            if stripped in repeated_lines:
                if stripped not in seen_repeated:
                    seen_repeated.add(stripped)
                    output_lines.append(line)
                # else: skip duplicate
            else:
                output_lines.append(line)
        cleaned_pages.append("\n".join(output_lines))

    return cleaned_pages


def _smart_page_join(pages: list[str]) -> str:
    """Join page texts with intelligent paragraph continuity detection.

    If a page ends without terminal punctuation and the next page starts
    with a lowercase letter, join with a single space (mid-sentence break).
    Otherwise join with double newline.

    Args:
        pages: List of per-page extracted text strings.

    Returns:
        Combined text with smart joining.
    """
    if not pages:
        return ""
    if len(pages) == 1:
        return pages[0]

    parts: list[str] = [pages[0]]
    for i in range(1, len(pages)):
        prev = pages[i - 1].rstrip()
        curr = pages[i].lstrip()
        if not prev or not curr:
            parts.append(curr)
            continue

        # Hyphenated word rejoining: "juris-\n" + "diction" -> "jurisdiction"
        if prev.endswith("-") and curr and curr[0].islower():
            parts[-1] = parts[-1].rstrip()[:-1]  # remove trailing hyphen from previous
            parts.append(curr)
            continue

        # Check if previous page ends without terminal punctuation
        # AND next page starts with a lowercase letter
        ends_without_punct = not _TERMINAL_PUNCT_RE.search(prev)
        starts_lower = curr[0].islower() if curr else False

        if ends_without_punct and starts_lower:
            # Mid-sentence page break -- join with space
            parts.append(" " + curr)
        else:
            parts.append("\n\n" + curr)

    return "".join(parts)


def _ocr_single_page(file_path: str, page_num: int) -> str:
    """OCR a single page of a PDF. Must be called from a sync context.

    Args:
        file_path: Path to the PDF file.
        page_num: 1-indexed page number.

    Returns:
        OCR text for the page, or empty string on failure.
    """
    try:
        import pytesseract
        from pdf2image import convert_from_path
        from pdf2image.exceptions import PDFPageCountError, PDFSyntaxError
    except ImportError:
        logger.error(
            "pdf2image or pytesseract not installed. "
            "Install with: pip install pdf2image pytesseract"
        )
        return ""

    try:
        images = convert_from_path(
            file_path, dpi=300, first_page=page_num, last_page=page_num
        )
        if not images:
            return ""
        img = images[0]
        try:
            page_text = pytesseract.image_to_string(
                img, config="--oem 3 --psm 6 -l eng+hin"
            )
            return page_text.strip() if page_text else ""
        finally:
            img.close()
    except (OSError, RuntimeError, PDFPageCountError, PDFSyntaxError) as exc:
        logger.warning("OCR failed on page %d of %s: %s", page_num, file_path, exc)
        return ""


# ---------------------------------------------------------------------------
# PDF text extraction (synchronous helpers)
# ---------------------------------------------------------------------------


def _build_page_map(page_texts: list[str], joined_text: str) -> list[dict]:
    """Build a page-number-to-character-offset map.

    Uses fuzzy matching: finds each page's first 50 chars in the joined text
    to handle join transformations (smart_page_join, clean_extracted_text).
    Falls back to sequential estimation if exact match fails.
    """
    page_map: list[dict] = []
    search_start = 0

    for i, page_text in enumerate(page_texts):
        page_num = i + 1
        # Find the start of this page's content in the joined text
        anchor = page_text.strip()[:50]
        if not anchor:
            continue

        pos = joined_text.find(anchor, search_start)
        if pos == -1:
            # Fallback: estimate from previous page's end
            pos = page_map[-1]["char_end"] if page_map else 0

        # Find where this page's content ends
        end_anchor = page_text.strip()[-50:]
        end_pos = joined_text.find(end_anchor, pos)
        if end_pos != -1:
            end_pos += len(end_anchor)
        else:
            # Estimate: pos + original page length (rough)
            end_pos = min(pos + len(page_text), len(joined_text))

        page_map.append({
            "page_number": page_num,
            "char_start": pos,
            "char_end": end_pos,
        })
        search_start = pos + 1

    return page_map


def _extract_pdf_text_sync(file_path: str) -> tuple[str, int, list[dict]]:
    """Synchronous per-page hybrid PDF text extraction.

    For each page, extracts text with pdfplumber. If a page yields fewer
    than 30 characters, falls back to OCR for that specific page.

    Args:
        file_path: Absolute path to the PDF file.

    Returns:
        Tuple of (cleaned joined text, page count, page_map).
    """
    page_texts: list[str] = []
    total_pages = 0
    try:
        with pdfplumber.open(file_path) as pdf:
            if len(pdf.pages) > MAX_PAGES:
                logger.error(
                    "PDF %s has %d pages, exceeds MAX_PAGES=%d",
                    file_path, len(pdf.pages), MAX_PAGES,
                )
                return "", 0, []
            total_pages = len(pdf.pages)
            for page_num, page in enumerate(pdf.pages, start=1):
                page_text = ""
                try:
                    page_text = page.extract_text() or ""
                except (ValueError, TypeError, KeyError) as exc:
                    logger.warning(
                        "pdfplumber failed on page %d/%d of %s: %s",
                        page_num, total_pages, file_path, exc,
                    )

                # If pdfplumber got very little text, try OCR on this page
                if len(page_text.strip()) < 30:
                    logger.debug(
                        "Page %d/%d has < 30 chars, attempting OCR: %s",
                        page_num, total_pages, file_path,
                    )
                    ocr_text = _ocr_single_page(file_path, page_num)
                    if len(ocr_text) > len(page_text.strip()):
                        page_text = ocr_text
                elif page_text.strip():
                    # Alpha-ratio check: catch garbled text that passed the 30-char threshold
                    alpha_count = sum(1 for c in page_text if c.isalpha())
                    alpha_ratio = alpha_count / len(page_text) if page_text else 0
                    if alpha_ratio < 0.5:
                        logger.debug(
                            "Page %d/%d has low alpha ratio (%.2f), attempting OCR: %s",
                            page_num, total_pages, alpha_ratio, file_path,
                        )
                        ocr_text = _ocr_single_page(file_path, page_num)
                        if ocr_text and len(ocr_text) > len(page_text):
                            ocr_alpha = sum(1 for c in ocr_text if c.isalpha()) / len(ocr_text)
                            if ocr_alpha > alpha_ratio:
                                page_text = ocr_text

                if page_text.strip():
                    page_texts.append(page_text.strip())

    except (OSError, PSException, ValueError) as exc:
        logger.error("Failed to open PDF %s: %s", file_path, exc)
        return "", 0, []
    except Exception as exc:
        # Catch PDFPasswordIncorrect (and guard against missing import)
        if PDFPasswordIncorrect is not None and isinstance(exc, PDFPasswordIncorrect):
            logger.warning("Skipping password-protected PDF: %s", file_path)
            return "", 0, []
        # Catch any other PDF corruption / parsing errors gracefully
        logger.error("Corrupt or unreadable PDF %s: %s", file_path, exc)
        return "", 0, []

    # Remove repeated headers/footers on per-page list (before joining)
    page_texts = _remove_repeated_headers_footers_pages(page_texts)
    # Smart join and clean
    result = _smart_page_join(page_texts)
    result = clean_extracted_text(result)
    page_map = _build_page_map(page_texts, result)
    return result, total_pages, page_map


async def extract_pdf_text(file_path: str) -> tuple[str, int, list[dict]]:
    """Extract text from a PDF using pdfplumber with per-page OCR fallback.

    For each page, attempts pdfplumber extraction first. If a page yields
    fewer than 30 characters, falls back to OCR for that specific page.
    Applies Unicode normalization, header/footer deduplication, and
    whitespace cleanup.

    Runs blocking I/O in a thread to avoid blocking the event loop.

    Args:
        file_path: Absolute path to the PDF file.

    Returns:
        Tuple of (cleaned text, page count, page_map). Returns ("", 0, []) on failure.
    """
    return await asyncio.to_thread(_extract_pdf_text_sync, file_path)


async def extract_with_ocr(file_path: str) -> tuple[str, bool, int]:
    """Fallback OCR extraction for scanned PDFs.

    Uses pdf2image to convert pages to images and pytesseract
    for optical character recognition. Processes pages one at a time.
    Uses Tesseract with English + Hindi language support.

    Args:
        file_path: Absolute path to the PDF file.

    Returns:
        Tuple of (text, ocr_truncated, total_pages).
        text: OCR-extracted text, empty string on failure.
        ocr_truncated: True if pages were capped at MAX_OCR_PAGES.
        total_pages: Total pages in the PDF.
    """
    try:
        import pytesseract  # noqa: F401
        from pdf2image import convert_from_path  # noqa: F401
        from pdf2image.exceptions import PDFPageCountError, PDFSyntaxError  # noqa: F401
    except ImportError:
        logger.error(
            "pdf2image or pytesseract not installed. "
            "Install with: pip install pdf2image pytesseract"
        )
        return "", False, 0

    def _ocr_sync() -> tuple[str, bool, int]:
        # Determine page count
        try:
            from pdf2image import pdfinfo_from_path

            info = pdfinfo_from_path(file_path)
            total_pages = info.get("Pages", 0)
        except Exception:
            # Fallback: try pdfplumber for page count
            try:
                with pdfplumber.open(file_path) as pdf:
                    total_pages = len(pdf.pages)
            except Exception as exc:
                logger.error("Cannot determine page count for %s: %s", file_path, exc)
                return "", False, 0

        if total_pages == 0:
            logger.warning("PDF has 0 pages: %s", file_path)
            return "", False, 0

        ocr_page_limit = min(total_pages, MAX_OCR_PAGES)
        truncated = total_pages > MAX_OCR_PAGES
        if truncated:
            logger.warning(
                "PDF %s has %d pages for OCR, truncating to MAX_OCR_PAGES=%d",
                file_path, total_pages, MAX_OCR_PAGES,
            )

        page_texts: list[str] = []
        for page_num in range(1, ocr_page_limit + 1):
            page_text = _ocr_single_page(file_path, page_num)
            if page_text:
                page_texts.append(page_text)

        result = _smart_page_join(page_texts)
        result = clean_extracted_text(result)
        return result, truncated, total_pages

    return await asyncio.to_thread(_ocr_sync)


# ---------------------------------------------------------------------------
# Quality scoring
# ---------------------------------------------------------------------------


def score_text_quality(text: str, ocr_used: bool = False, page_count: int = 0) -> TextQuality:
    """Score the quality of extracted judgment text.

    Tiers:
    - high: >2000 chars, >=3 legal keywords, reasonable alpha ratio
    - medium: >500 chars, >=1 legal keyword
    - low: everything else (flag for manual review)

    Also forces "low" for:
    - Very low chars-per-page (OCR garbage)
    - Very low alphabetic character ratio (<0.4)
    """
    char_count = len(text)
    text_lower = text.lower()
    legal_keyword_count = sum(1 for kw in LEGAL_KEYWORDS if kw in text_lower)

    if char_count > 2000 and legal_keyword_count >= 3:
        tier = "high"
    elif char_count > 500 and legal_keyword_count >= 1:
        tier = "medium"
    else:
        tier = "low"

    # Alpha ratio check: OCR garbage often has <40% alphabetic characters
    if char_count > 0:
        alpha_ratio = sum(c.isalpha() for c in text) / char_count
        if alpha_ratio < 0.4:
            tier = "low"

    # Chars-per-page check: if we know page count and text is suspiciously sparse
    if page_count > 0 and char_count > 0:
        chars_per_page = char_count / page_count
        if chars_per_page < 100:
            tier = "low"

    return TextQuality(
        text=text,
        char_count=char_count,
        tier=tier,
        ocr_used=ocr_used,
        legal_keyword_count=legal_keyword_count,
        page_count=page_count,
    )


def assess_extraction_quality(text: str) -> dict:
    """Assess the quality of extracted text.

    Checks alphabetic character ratio and presence of common legal terms
    to determine if extraction produced usable text.

    Args:
        text: Extracted text to assess.

    Returns:
        Dictionary with alpha_ratio, char_count, quality ("good"/"poor"),
        and has_legal_markers boolean.
    """
    alpha_ratio = sum(c.isalpha() for c in text) / max(len(text), 1)
    has_legal_markers = bool(
        re.search(
            r"(?:Section|Article|Act|Court|Judge|appellant|respondent)",
            text,
            re.IGNORECASE,
        )
    )
    return {
        "alpha_ratio": round(alpha_ratio, 3),
        "char_count": len(text),
        "quality": "good" if alpha_ratio > 0.6 and has_legal_markers else "poor",
        "has_legal_markers": has_legal_markers,
    }


async def extract_and_score(file_path: str) -> TextQuality:
    """Extract text from PDF and return quality-scored result.

    Tries pdfplumber first, falls back to OCR if insufficient text.
    """
    text, page_count, page_map = await extract_pdf_text(file_path)
    ocr_used = False

    ocr_truncated = False
    ocr_total_pages = 0

    if not text or len(text) < 100:
        logger.warning("pdfplumber extraction insufficient, trying OCR: %s", file_path)
        text, ocr_truncated, ocr_total_pages = await extract_with_ocr(file_path)
        ocr_used = True
        page_map = []  # OCR fallback doesn't produce page_map

    # Strip leading bleed from previous judgment (pre-1964 PDFs)
    if text:
        text = _strip_leading_judgment_bleed(text)

    # Strip first-page reporter preamble (missed by 3-page header dedup)
    if text:
        text = _strip_first_page_preamble(text)

    # Strip SCR/SCC reporter editorial content (headnotes with A-H margins)
    editorial_stripped = ""
    if text:
        text, editorial_stripped = strip_reporter_editorial(text)

    if not text:
        text = ""

    quality = score_text_quality(text, ocr_used=ocr_used, page_count=page_count)
    quality.page_map = page_map
    quality.ocr_truncated = ocr_truncated
    quality.ocr_total_pages = ocr_total_pages
    quality.editorial_stripped = editorial_stripped

    if quality.tier == "low":
        logger.warning(
            "Low quality extraction for %s: %d chars, %d legal keywords, ocr=%s",
            file_path, quality.char_count, quality.legal_keyword_count, ocr_used,
        )

    return quality


def extract_tables(file_path: str, *, max_pages: int = MAX_PAGES) -> list[dict]:
    """Extract tables from a PDF using pdfplumber's table detection.

    Returns a list of dicts with:
    - page: page number (1-indexed)
    - headers: list of column headers (first row) or None
    - rows: list of row lists (excluding header)
    - markdown: markdown-formatted table string

    Used to preserve tabular data (schedules, appendices, financial data)
    that would otherwise be lost during text extraction.
    """
    tables: list[dict] = []
    try:
        with pdfplumber.open(file_path) as pdf:
            for page_num, page in enumerate(pdf.pages[:max_pages], start=1):
                page_tables = page.extract_tables()
                if not page_tables:
                    continue
                for raw_table in page_tables:
                    if not raw_table or len(raw_table) < 2:
                        continue
                    # Clean cells: replace None with empty string, strip whitespace
                    cleaned = [
                        [(cell or "").strip() for cell in row]
                        for row in raw_table
                        if row  # skip None rows
                    ]
                    if not cleaned:
                        continue
                    headers = cleaned[0]
                    rows = cleaned[1:]
                    # Convert to markdown
                    md_lines = ["| " + " | ".join(headers) + " |"]
                    md_lines.append("| " + " | ".join("---" for _ in headers) + " |")
                    for row in rows:
                        # Pad row to match header length
                        padded = row + [""] * (len(headers) - len(row))
                        md_lines.append("| " + " | ".join(padded[:len(headers)]) + " |")
                    tables.append({
                        "page": page_num,
                        "headers": headers,
                        "rows": rows,
                        "markdown": "\n".join(md_lines),
                    })
    except Exception as exc:
        logger.warning("Table extraction failed for %s: %s", file_path, exc)

    return tables
