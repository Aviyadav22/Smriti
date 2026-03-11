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

    reporter: str  # SCC, AIR, INSC, SCR, CrLJ, SCALE, MANU, JT, Neutral, etc.
    year: int
    volume: str | None
    page: str
    court: str | None  # for AIR, SCC OnLine, neutral, MANU citations
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

# --- SCC family ---

# (2020) 3 SCC (Cri) 145, (2020) 3 SCC (Supp) 145, (2020) 3 SCC (L&S) 145
# Must be checked BEFORE main SCC_PATTERN to avoid partial matches
SCC_SUB_PATTERN: re.Pattern[str] = re.compile(
    r"[\(\[](\d{4})[\)\]]\s+(\d+)\s+SCC\s+\((\w+(?:&\w+)?)\)\s+(\d+)"
)

# (2020) 3 SCC 145 — also accepts [2020] 3 SCC 145
SCC_PATTERN: re.Pattern[str] = re.compile(
    r"[\(\[](\d{4})[\)\]]\s+(\d+)\s+SCC\s+(\d+)"
)

# 2020 SCC OnLine SC 1234 — case-insensitive for "OnLine" variations
SCC_ONLINE_PATTERN: re.Pattern[str] = re.compile(
    r"(\d{4})\s+SCC\s+[Oo]n\s*[Ll]ine\s+(\w+)\s+(\d+)"
)

# --- AIR ---

# AIR 2020 SC 145 — also matches A.I.R. 2020 SC 145
AIR_PATTERN: re.Pattern[str] = re.compile(
    r"A\.?I\.?R\.?\s+(\d{4})\s+(\w+)\s+(\d+)"
)

# --- Neutral citations (post-2023) ---

# 2023:INSC:1234 — Supreme Court neutral citation
NEUTRAL_SC_PATTERN: re.Pattern[str] = re.compile(r"(\d{4}):INSC:(\d+)")

# 2023:DELHC:1234, 2023:BOMHC:1234 — High Court neutral citations
# Explicit whitelist of known HC codes to avoid false positives
# (derived from courts.py _HIGH_COURTS keys)
_HC_CODES = (
    "DEL|BOM|ALL|CAL|MAD|KAR|KER|GUJ|RAJ|PAT|"
    "PNH|AP|TEL|ORI|JHAR|CG|UTT|HP|JK|JKL|GAU|"
    "TRI|MEG|MAN|SIK|MP|CHH|LAKH"
)
NEUTRAL_HC_PATTERN: re.Pattern[str] = re.compile(
    rf"(\d{{4}}):((?:{_HC_CODES})HC):(\d+)"
)

# --- INSC (space-delimited, legacy) ---

# 2020 INSC 145
INSC_PATTERN: re.Pattern[str] = re.compile(
    r"(\d{4})\s+INSC\s+(\d+)"
)

# --- SCR ---

# [2020] 3 SCR 145
SCR_PATTERN: re.Pattern[str] = re.compile(
    r"\[(\d{4})\]\s+(\d+)\s+SCR\s+(\d+)"
)

# --- CrLJ ---

# 2020 CrLJ 145  (with optional dots in Cr.L.J.)
CRLJ_PATTERN: re.Pattern[str] = re.compile(
    r"(\d{4})\s+Cr\.?L\.?J\.?\s+(\d+)"
)

# --- SCALE ---

# (2020) 3 SCALE 145
SCALE_PATTERN: re.Pattern[str] = re.compile(
    r"\((\d{4})\)\s+(\d+)\s+SCALE\s+(\d+)"
)

# --- MANU ---

# MANU/SC/1234/2020
MANU_PATTERN: re.Pattern[str] = re.compile(r"MANU/(\w+)/(\d+)/(\d{4})")

# --- JT (Judgments Today) ---

# JT 2020 (3) SC 145  OR  (2020) 3 JT (SC) 145
JT_PATTERN: re.Pattern[str] = re.compile(
    r"(?:JT\s+(\d{4})\s+\((\d+)\)\s+(\w+)\s+(\d+)"
    r"|\((\d{4})\)\s+(\d+)\s+JT\s+\((\w+)\)\s+(\d+))"
)

# --- High Court reporters ---

# ILR, MLJ, KLT, BLR, GLR, ALJ, DLT, ALD, CLT, PLR, DRJ, KHC, RLW
# Matches: "2020 ILR 145" or "(2020) 3 ILR 145" or "(2020) ILR 145"
HC_REPORTER_PATTERN: re.Pattern[str] = re.compile(
    r"(?:(\d{4})\s+|\((\d{4})\)\s+(?:\d+\s+)?)"
    r"(ILR|MLJ|KLT|BLR|GLR|ALJ|DLT|ALD|CLT|PLR|DRJ|KHC|RLW)"
    r"\s+(\d+)",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Backward-compat aliases for state reporter patterns
# ---------------------------------------------------------------------------

# These were separate patterns in earlier versions; now unified under
# HC_REPORTER_PATTERN. Keep the names so existing imports don't break.
BLR_PATTERN = HC_REPORTER_PATTERN
KLT_PATTERN = HC_REPORTER_PATTERN
GLR_PATTERN = HC_REPORTER_PATTERN

# ---------------------------------------------------------------------------
# Act / section reference patterns
# ---------------------------------------------------------------------------

# Short-code -> full act name mapping for _SECTION_SHORT_ACT_PATTERN matches
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
    "NI ACT": "Negotiable Instruments Act",
    "FEMA": "Foreign Exchange Management Act",
    "FERA": "Foreign Exchange Regulation Act",
    "RTI ACT": "Right to Information Act",
    "SARFAESI": "Securitisation and Reconstruction of Financial Assets "
                "and Enforcement of Security Interest Act",
    "ARBITRATION ACT": "Arbitration and Conciliation Act",
    "COMPANIES ACT": "Companies Act",
    "SC/ST ACT": "Scheduled Castes and Scheduled Tribes "
                 "(Prevention of Atrocities) Act",
    "DV ACT": "Protection of Women from Domestic Violence Act",
    "MV ACT": "Motor Vehicles Act",
    "TP ACT": "Transfer of Property Act",
    "HMA": "Hindu Marriage Act",
    "LIMITATION ACT": "Limitation Act",
    "TADA": "Terrorist and Disruptive Activities (Prevention) Act",
    "UAPA": "Unlawful Activities (Prevention) Act",
    "PMLA": "Prevention of Money Laundering Act",
    "IBC": "Insolvency and Bankruptcy Code",
    "CGST ACT": "Central Goods and Services Tax Act",
    "SEBI ACT": "Securities and Exchange Board of India Act",
    "EVIDENCE ACT": "Indian Evidence Act",
    "CONTRACT ACT": "Indian Contract Act",
    "ARMS ACT": "Arms Act",
    "CP ACT": "Consumer Protection Act",
    "SRA": "Specific Relief Act",
    "ELECTRICITY ACT": "Electricity Act",
    "LA ACT": "Land Acquisition Act",
    "BR ACT": "Banking Regulation Act",
    "STAMPS ACT": "Indian Stamp Act",
    "REGISTRATION ACT": "Registration Act",
    "IGST ACT": "Integrated Goods and Services Tax Act",
    "SALE OF GOODS ACT": "Sale of Goods Act",
    "WILD LIFE ACT": "Wild Life (Protection) Act",
    "EPA": "Environment (Protection) Act",
}

# Build alternation dynamically from dict keys -- longest first to avoid
# partial matches (e.g. "CGST ACT" before "CP ACT" before "CPC").
_SHORT_ACT_ALTERNATION: str = "|".join(
    re.escape(k).replace(r"\ ", r"\s+")
    for k in sorted(_SHORT_ACT_NAMES.keys(), key=len, reverse=True)
)

# "Section 302 of the Indian Penal Code, 1860"
_SECTION_FULL_ACT_PATTERN: re.Pattern[str] = re.compile(
    r"(?:Sections?|Sec\.?|S\.)\s+([\d\w]+(?:\s*\([^)]+\))*)"
    r"\s+of\s+(?:the\s+)?"
    r"([\w\s]+?)"
    r"(?:,\s*(\d{4}))?(?=\s*[.,;)\]]|\s+and\s|\s+read\s|\s+r/w\s|$)",
    re.IGNORECASE,
)

# "Section 302 IPC" / "Sections 302, 304 and 307 IPC"
# Captures comma/slash/and-separated section lists in group(1)
_SECTION_SHORT_ACT_PATTERN: re.Pattern[str] = re.compile(
    r"(?:Sections?|Sec\.?|S\.)\s+([\d\w]+(?:\s*\([^)]+\))*"
    r"(?:\s*[,/]\s*[\d\w]+(?:\s*\([^)]+\))*)*"
    r"(?:\s+(?:and|&)\s+[\d\w]+(?:\s*\([^)]+\))*)?)"
    r"\s+(" + _SHORT_ACT_ALTERNATION + r")",
    re.IGNORECASE,
)

# "Article 14/19/21 of the Constitution"
_ARTICLE_PATTERN: re.Pattern[str] = re.compile(
    r"(?:Article|Art\.?)\s+([\d\w]+(?:\s*\([^)]+\))*)"
    r"(\s+of\s+(?:the\s+)?Constitution)?",
    re.IGNORECASE,
)

# "Order 39 Rule 1 CPC"
_ORDER_RULE_PATTERN: re.Pattern[str] = re.compile(
    r"Order\s+(\w+)\s+Rule\s+(\d+)"
    r"(?:\s+(?:of\s+(?:the\s+)?)?"
    r"(?:CPC|Code\s+of\s+Civil\s+Procedure|Civil\s+Procedure\s+Code))?",
    re.IGNORECASE,
)


def _parse_section_list(section_str: str) -> list[str]:
    """Parse '302, 304 and 307' into ['302', '304', '307'].

    Splits on commas, slashes, 'and', and '&' separators.
    """
    parts = re.split(r"[,/]\s*|\s+and\s+|\s+&\s+", section_str)
    return [p.strip() for p in parts if p.strip()]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_citations(text: str) -> list[Citation]:
    """Extract all case citations from the given text.

    Scans for SCC (including sub-reporters), SCC OnLine, AIR, INSC,
    neutral citations, SCR, CrLJ, SCALE, MANU, JT, and HC reporter
    citation formats.

    Args:
        text: Judgment or legal text to search.

    Returns:
        De-duplicated list of Citation objects in order of appearance.
    """
    citations: list[Citation] = []
    seen_raw: set[str] = set()

    def _add(citation: Citation) -> None:
        normalized = normalize_citation(citation.raw_text)
        if normalized not in seen_raw:
            seen_raw.add(normalized)
            citations.append(citation)

    # --- SCC sub-reporters --- MUST come before main SCC pattern ---
    # (2020) 3 SCC (Cri) 145
    for match in SCC_SUB_PATTERN.finditer(text):
        sub = match.group(3)
        _add(Citation(
            reporter=f"SCC ({sub})",
            year=int(match.group(1)),
            volume=match.group(2),
            page=match.group(4),
            court=None,
            raw_text=match.group(0),
        ))

    # SCC -- (2020) 3 SCC 145 or [2020] 3 SCC 145
    for match in SCC_PATTERN.finditer(text):
        _add(Citation(
            reporter="SCC",
            year=int(match.group(1)),
            volume=match.group(2),
            page=match.group(3),
            court=None,
            raw_text=match.group(0),
        ))

    # SCC OnLine -- 2020 SCC OnLine SC 1234 (case-insensitive)
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

    # AIR -- AIR 2020 SC 145 or A.I.R. 2020 SC 145
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

    # Neutral SC -- 2023:INSC:1234
    # Process SC first and record spans so HC matching can skip overlaps
    sc_spans: list[tuple[int, int]] = []
    for match in NEUTRAL_SC_PATTERN.finditer(text):
        sc_spans.append((match.start(), match.end()))
        _add(Citation(
            reporter="INSC",
            year=int(match.group(1)),
            volume=None,
            page=match.group(2),
            court="Supreme Court of India",
            raw_text=match.group(0),
        ))

    # Neutral HC -- 2023:DELHC:1234, 2023:BOMHC:1234
    # Skip any match whose position overlaps a previously matched SC span
    for match in NEUTRAL_HC_PATTERN.finditer(text):
        if any(start <= match.start() < end for start, end in sc_spans):
            continue
        court_code = match.group(2)
        _add(Citation(
            reporter="Neutral",
            year=int(match.group(1)),
            volume=None,
            page=match.group(3),
            court=court_code,
            raw_text=match.group(0),
        ))

    # INSC (space-delimited, legacy) -- 2020 INSC 145
    for match in INSC_PATTERN.finditer(text):
        _add(Citation(
            reporter="INSC",
            year=int(match.group(1)),
            volume=None,
            page=match.group(2),
            court="Supreme Court of India",
            raw_text=match.group(0),
        ))

    # SCR -- [2020] 3 SCR 145
    for match in SCR_PATTERN.finditer(text):
        _add(Citation(
            reporter="SCR",
            year=int(match.group(1)),
            volume=match.group(2),
            page=match.group(3),
            court=None,
            raw_text=match.group(0),
        ))

    # CrLJ -- 2020 CrLJ 145
    for match in CRLJ_PATTERN.finditer(text):
        _add(Citation(
            reporter="CrLJ",
            year=int(match.group(1)),
            volume=None,
            page=match.group(2),
            court=None,
            raw_text=match.group(0),
        ))

    # SCALE -- (2020) 3 SCALE 145
    for match in SCALE_PATTERN.finditer(text):
        _add(Citation(
            reporter="SCALE",
            year=int(match.group(1)),
            volume=match.group(2),
            page=match.group(3),
            court=None,
            raw_text=match.group(0),
        ))

    # MANU -- MANU/SC/1234/2020
    for match in MANU_PATTERN.finditer(text):
        _add(Citation(
            reporter="MANU",
            year=int(match.group(3)),
            volume=None,
            page=match.group(2),
            court=match.group(1),
            raw_text=match.group(0),
        ))

    # JT -- JT 2020 (3) SC 145  OR  (2020) 3 JT (SC) 145
    for match in JT_PATTERN.finditer(text):
        if match.group(1) is not None:
            # First alternative: JT 2020 (3) SC 145
            _add(Citation(
                reporter="JT",
                year=int(match.group(1)),
                volume=match.group(2),
                page=match.group(4),
                court=match.group(3),
                raw_text=match.group(0),
            ))
        else:
            # Second alternative: (2020) 3 JT (SC) 145
            _add(Citation(
                reporter="JT",
                year=int(match.group(5)),
                volume=match.group(6),
                page=match.group(8),
                court=match.group(7),
                raw_text=match.group(0),
            ))

    # HC reporters -- ILR, MLJ, KLT, BLR, GLR, ALJ, DLT, ALD, CLT, PLR,
    #                  DRJ, KHC, RLW
    for match in HC_REPORTER_PATTERN.finditer(text):
        year = match.group(1) or match.group(2)
        reporter_name = match.group(3).upper()
        _add(Citation(
            reporter=reporter_name,
            year=int(year),
            volume=None,
            page=match.group(4),
            court=None,
            raw_text=match.group(0),
        ))

    return citations


def extract_acts_cited(text: str) -> list[ActReference]:
    """Extract statutory provision references from the given text.

    Handles patterns like:
    - "Section 302 of the Indian Penal Code, 1860"
    - "Section 302 IPC" / "Sections 302, 304 and 307 IPC"
    - "Article 21 of the Constitution"
    - "Order 39 Rule 1 CPC"

    Args:
        text: Judgment or legal text to search.

    Returns:
        De-duplicated list of ActReference objects in order of appearance.
    """
    references: list[ActReference] = []
    seen_keys: set[str] = set()

    def _add(ref: ActReference) -> None:
        # Dedup key combines act name and section to allow multiple sections
        # from a single raw_text (e.g. "Sections 302, 304 and 307 IPC").
        key = f"{ref.act_name}|{ref.section}|{ref.raw_text}"
        if key not in seen_keys:
            seen_keys.add(key)
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

    # Short form: "Section 302 IPC" / "Sections 302, 304 and 307 IPC"
    for match in _SECTION_SHORT_ACT_PATTERN.finditer(text):
        section_str = match.group(1).strip()
        # Normalize short code: collapse whitespace and upper-case
        short_code = re.sub(r"\s+", " ", match.group(2).strip()).upper()
        act_name = _SHORT_ACT_NAMES.get(short_code, short_code)
        raw = match.group(0).strip()

        # Split comma/and-separated section lists into individual refs
        sections = _parse_section_list(section_str)
        if len(sections) > 1:
            for sec in sections:
                _add(ActReference(
                    act_name=act_name,
                    section=sec,
                    year=None,
                    raw_text=raw,
                ))
        else:
            _add(ActReference(
                act_name=act_name,
                section=section_str,
                year=None,
                raw_text=raw,
            ))

    # Article references: "Article 21 of the Constitution"
    for match in _ARTICLE_PATTERN.finditer(text):
        article = match.group(1).strip()
        has_constitution = match.group(2) is not None
        act_name = "Constitution of India" if has_constitution else "Unknown Act"
        year = 1950 if has_constitution else None
        raw = match.group(0).strip()
        _add(ActReference(
            act_name=act_name,
            section=f"Article {article}",
            year=year,
            raw_text=raw,
        ))

    # Order/Rule references: "Order 39 Rule 1 CPC"
    for match in _ORDER_RULE_PATTERN.finditer(text):
        order = match.group(1)
        rule = match.group(2)
        _add(ActReference(
            act_name="Code of Civil Procedure",
            section=f"Order {order} Rule {rule}",
            year=1908,
            raw_text=match.group(0).strip(),
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

    # Standardize A.I.R. -> AIR
    normalized = re.sub(r"A\.?I\.?R\.?", "AIR", normalized)

    # Standardize SCC OnLine spacing (case-insensitive)
    normalized = re.sub(
        r"SCC\s+[Oo]n\s*[Ll]ine", "SCC OnLine", normalized
    )

    # Ensure consistent bracket style for year in SCC/SCALE
    # Convert [2020] to (2020) for SCC-style citations
    normalized = re.sub(
        r"\[(\d{4})\](\s+\d+\s+SCC\s+)",
        r"(\1)\2",
        normalized,
    )

    return normalized
