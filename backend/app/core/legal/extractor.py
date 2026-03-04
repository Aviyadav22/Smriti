"""Citation and statutory reference extraction from Indian legal texts.

Provides regex-based extraction of case citations (SCC, AIR, INSC, SCR, etc.)
and act/section references from judgment text.
"""

import re
from dataclasses import dataclass

from app.core.legal.courts import AIR_COURT_CODES

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Citation:
    """A parsed case citation reference."""

    reporter: str  # SCC, AIR, INSC, SCR, CrLJ, SCALE
    year: int
    volume: str | None
    page: str
    court: str | None  # for AIR citations
    raw_text: str


@dataclass(frozen=True, slots=True)
class ActReference:
    """A parsed statutory provision reference."""

    act_name: str
    section: str
    year: int | None
    raw_text: str


# ---------------------------------------------------------------------------
# Compiled regex patterns — module-level constants
# ---------------------------------------------------------------------------

# (2020) 3 SCC 145
SCC_PATTERN: re.Pattern[str] = re.compile(
    r"\((\d{4})\)\s+(\d+)\s+SCC\s+(\d+)"
)

# 2020 SCC OnLine SC 1234
SCC_ONLINE_PATTERN: re.Pattern[str] = re.compile(
    r"(\d{4})\s+SCC\s+OnLine\s+(\w+)\s+(\d+)"
)

# AIR 2020 SC 145
AIR_PATTERN: re.Pattern[str] = re.compile(
    r"AIR\s+(\d{4})\s+(\w+)\s+(\d+)"
)

# 2020 INSC 145
INSC_PATTERN: re.Pattern[str] = re.compile(
    r"(\d{4})\s+INSC\s+(\d+)"
)

# [2020] 3 SCR 145
SCR_PATTERN: re.Pattern[str] = re.compile(
    r"\[(\d{4})\]\s+(\d+)\s+SCR\s+(\d+)"
)

# 2020 CrLJ 145  (with optional dots in Cr.L.J.)
CRLJ_PATTERN: re.Pattern[str] = re.compile(
    r"(\d{4})\s+Cr\.?L\.?J\.?\s+(\d+)"
)

# (2020) 3 SCALE 145
SCALE_PATTERN: re.Pattern[str] = re.compile(
    r"\((\d{4})\)\s+(\d+)\s+SCALE\s+(\d+)"
)

# ---------------------------------------------------------------------------
# Act / section reference patterns
# ---------------------------------------------------------------------------

# "Section 302 of the Indian Penal Code, 1860"
_SECTION_FULL_ACT_PATTERN: re.Pattern[str] = re.compile(
    r"(?:Section|Sec\.?|S\.)\s+([\d\w]+(?:\s*\(\d+\))?)"
    r"\s+of\s+(?:the\s+)?"
    r"([\w\s]+?)"
    r"(?:,\s*(\d{4}))?(?=\s*[.,;)\]]|\s+and\s|\s+read\s|\s+r/w\s|$)",
    re.IGNORECASE,
)

# "Section 302 IPC" / "Article 21 Constitution"
_SECTION_SHORT_ACT_PATTERN: re.Pattern[str] = re.compile(
    r"(?:Section|Sec\.?|S\.)\s+([\d\w]+(?:\s*\(\d+\))?)"
    r"\s+(IPC|CrPC|CPC|BNS|BNSS|BSA|IT\s+Act|NDPS\s+Act|POCSO\s+Act)",
    re.IGNORECASE,
)

# "Article 14/19/21 of the Constitution"
_ARTICLE_PATTERN: re.Pattern[str] = re.compile(
    r"(?:Article|Art\.?)\s+([\d\w]+(?:\s*\(\d+\))?)"
    r"(?:\s+of\s+(?:the\s+)?Constitution)?",
    re.IGNORECASE,
)

# Short-code → full act name mapping for _SECTION_SHORT_ACT_PATTERN matches
_SHORT_ACT_NAMES: dict[str, str] = {
    "IPC": "Indian Penal Code",
    "CRPC": "Code of Criminal Procedure",
    "CPC": "Code of Civil Procedure",
    "BNS": "Bharatiya Nyaya Sanhita",
    "BNSS": "Bharatiya Nagarik Suraksha Sanhita",
    "BSA": "Bharatiya Sakshya Adhiniyam",
    "IT ACT": "Information Technology Act",
    "NDPS ACT": "Narcotic Drugs and Psychotropic Substances Act",
    "POCSO ACT": "Protection of Children from Sexual Offences Act",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_citations(text: str) -> list[Citation]:
    """Extract all case citations from the given text.

    Scans for SCC, SCC OnLine, AIR, INSC, SCR, CrLJ, and SCALE citation
    formats.

    Args:
        text: Judgment or legal text to search.

    Returns:
        De-duplicated list of Citation objects in order of appearance.
    """
    citations: list[Citation] = []
    seen_raw: set[str] = set()

    def _add(citation: Citation) -> None:
        if citation.raw_text not in seen_raw:
            seen_raw.add(citation.raw_text)
            citations.append(citation)

    # SCC — (2020) 3 SCC 145
    for match in SCC_PATTERN.finditer(text):
        _add(Citation(
            reporter="SCC",
            year=int(match.group(1)),
            volume=match.group(2),
            page=match.group(3),
            court=None,
            raw_text=match.group(0),
        ))

    # SCC OnLine — 2020 SCC OnLine SC 1234
    for match in SCC_ONLINE_PATTERN.finditer(text):
        court_code = match.group(2)
        _add(Citation(
            reporter="SCC OnLine",
            year=int(match.group(1)),
            volume=None,
            page=match.group(3),
            court=AIR_COURT_CODES.get(court_code, court_code),
            raw_text=match.group(0),
        ))

    # AIR — AIR 2020 SC 145
    for match in AIR_PATTERN.finditer(text):
        court_code = match.group(2)
        _add(Citation(
            reporter="AIR",
            year=int(match.group(1)),
            volume=None,
            page=match.group(3),
            court=AIR_COURT_CODES.get(court_code, court_code),
            raw_text=match.group(0),
        ))

    # INSC — 2020 INSC 145
    for match in INSC_PATTERN.finditer(text):
        _add(Citation(
            reporter="INSC",
            year=int(match.group(1)),
            volume=None,
            page=match.group(2),
            court="Supreme Court of India",
            raw_text=match.group(0),
        ))

    # SCR — [2020] 3 SCR 145
    for match in SCR_PATTERN.finditer(text):
        _add(Citation(
            reporter="SCR",
            year=int(match.group(1)),
            volume=match.group(2),
            page=match.group(3),
            court=None,
            raw_text=match.group(0),
        ))

    # CrLJ — 2020 CrLJ 145
    for match in CRLJ_PATTERN.finditer(text):
        _add(Citation(
            reporter="CrLJ",
            year=int(match.group(1)),
            volume=None,
            page=match.group(2),
            court=None,
            raw_text=match.group(0),
        ))

    # SCALE — (2020) 3 SCALE 145
    for match in SCALE_PATTERN.finditer(text):
        _add(Citation(
            reporter="SCALE",
            year=int(match.group(1)),
            volume=match.group(2),
            page=match.group(3),
            court=None,
            raw_text=match.group(0),
        ))

    return citations


def extract_acts_cited(text: str) -> list[ActReference]:
    """Extract statutory provision references from the given text.

    Handles patterns like:
    - "Section 302 of the Indian Penal Code, 1860"
    - "Section 302 IPC"
    - "Article 21 of the Constitution"

    Args:
        text: Judgment or legal text to search.

    Returns:
        De-duplicated list of ActReference objects in order of appearance.
    """
    references: list[ActReference] = []
    seen_raw: set[str] = set()

    def _add(ref: ActReference) -> None:
        if ref.raw_text not in seen_raw:
            seen_raw.add(ref.raw_text)
            references.append(ref)

    # Full form: "Section 302 of the Indian Penal Code, 1860"
    for match in _SECTION_FULL_ACT_PATTERN.finditer(text):
        section = match.group(1).strip()
        act_name = match.group(2).strip()
        year_str = match.group(3)
        year = int(year_str) if year_str else None
        _add(ActReference(
            act_name=act_name,
            section=section,
            year=year,
            raw_text=match.group(0).strip(),
        ))

    # Short form: "Section 302 IPC"
    for match in _SECTION_SHORT_ACT_PATTERN.finditer(text):
        section = match.group(1).strip()
        short_code = match.group(2).strip().upper()
        act_name = _SHORT_ACT_NAMES.get(short_code, short_code)
        _add(ActReference(
            act_name=act_name,
            section=section,
            year=None,
            raw_text=match.group(0).strip(),
        ))

    # Article references: "Article 21 of the Constitution"
    for match in _ARTICLE_PATTERN.finditer(text):
        article = match.group(1).strip()
        raw = match.group(0).strip()
        _add(ActReference(
            act_name="Constitution of India",
            section=f"Article {article}",
            year=1950,
            raw_text=raw,
        ))

    return references


def normalize_citation(citation: str) -> str:
    """Normalize a citation string to a canonical format.

    Standardizes spacing, punctuation, and reporter abbreviations to
    produce a consistent citation form suitable for deduplication and
    comparison.

    Args:
        citation: Raw citation string.

    Returns:
        Normalized citation string.
    """
    # Collapse multiple spaces
    normalized = re.sub(r"\s+", " ", citation.strip())

    # Standardize CrLJ variations
    normalized = re.sub(r"Cr\.?L\.?J\.?", "CrLJ", normalized)

    # Standardize SCC OnLine spacing
    normalized = re.sub(r"SCC\s+On\s*Line", "SCC OnLine", normalized)

    # Ensure consistent bracket style for year in SCC/SCALE
    # Convert [2020] to (2020) for SCC-style citations
    normalized = re.sub(
        r"\[(\d{4})\](\s+\d+\s+SCC\s+)",
        r"(\1)\2",
        normalized,
    )

    return normalized
