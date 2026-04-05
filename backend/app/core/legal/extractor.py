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
    confidence: float = 1.0  # 0.0-1.0; higher = more reliable format


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
# \s* (not \s+) to handle no-space OCR artifacts like (2020)3SCC145
SCC_PATTERN: re.Pattern[str] = re.compile(
    r"[\(\[](\d{4})[\)\]]\s*(\d+)\s*SCC\s+(\d+)"
)

# 2020 SCC OnLine SC 1234 — case-insensitive for "OnLine" variations
SCC_ONLINE_PATTERN: re.Pattern[str] = re.compile(
    r"(\d{4})\s+SCC\s+[Oo]n\s*[Ll]ine\s+(\w+)\s+(\d+)"
)

# --- AIR ---

# AIR 2020 SC 145 — also matches A.I.R. 2020 SC 145
# Restrict court code to known AIR_COURT_CODES to avoid false positives
_AIR_CODES = "|".join(re.escape(k) for k in AIR_COURT_CODES.keys())
AIR_PATTERN: re.Pattern[str] = re.compile(
    rf"A\.?I\.?R\.?\s+(\d{{4}})\s+({_AIR_CODES})\s+(\d+)"
)

# --- Neutral citations (post-2023) ---

# 2023:INSC:1234 — Supreme Court neutral citation
NEUTRAL_SC_PATTERN: re.Pattern[str] = re.compile(r"(\d{4}):INSC:(\d+)")

# 2023:DELHC:1234, 2023:BOMHC:1234 — High Court neutral citations
# Explicit whitelist of known HC codes to avoid false positives
# (derived from courts.py _HIGH_COURTS keys)
_HC_CODES = (
    "DEL|BOM|ALL|CAL|MAD|KAR|KER|GUJ|RAJ|PAT|"
    "PNH|PH|AP|TEL|ORI|JHAR|CG|UTT|HP|JK|JKL|GAU|"
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
    r"[(\[](\d{4})[)\]]\s+(\d+)\s+SCR\s+(\d+)"
)

# Bare SCR format (pre-1970): "3 SCR 150" or "3 S.C.R. 150"
SCR_BARE_PATTERN: re.Pattern[str] = re.compile(
    r"(\d{1,2})\s+S\.?C\.?R\.?\s+(\d+)"
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

# ILR, MLJ, KLT, BLR, GLR, ALJ, DLT, ALD, CLT, PLR, DRJ, KHC, RLW,
# LNIND, CDJ, BomLR, CalWN, WLC, JLJ, AIJEL, CriLJ, FLR, GujLR, MPLJ, OLR, WLR
# Matches: "2020 ILR 145" or "(2020) 3 ILR 145" or "(2020) ILR 145"
HC_REPORTER_PATTERN: re.Pattern[str] = re.compile(
    r"(?:(\d{4})\s+|\((\d{4})\)\s+(?:\d+\s+)?)"
    r"(ILR|MLJ|KLT|BLR|GLR|ALJ|DLT|ALD|CLT|PLR|DRJ|KHC|RLW"
    r"|LNIND|CDJ|BomLR|CalWN|WLC|JLJ|AIJEL|CriLJ|FLR|GujLR|MPLJ|OLR|WLR)"
    r"\s+(\d+)",
    re.IGNORECASE,
)

# --- LiveLaw ---

# 2024 LiveLaw (SC) 123
LIVELAW_PATTERN: re.Pattern[str] = re.compile(
    r"(\d{4})\s+LiveLaw\s+\((\w+)\)\s+(\d+)", re.IGNORECASE
)

# --- ITR (Income Tax Reports) ---

# [2020] 123 ITR 456 or (2020) 123 ITR 456
ITR_PATTERN: re.Pattern[str] = re.compile(
    r"[\[\(](\d{4})[\]\)]\s+(\d+)\s+ITR\s+(\d+)"
)

# --- Taxmann ---

# [2020] 123 taxmann.com 456
TAXMANN_PATTERN: re.Pattern[str] = re.compile(
    r"[\[\(](\d{4})[\]\)]\s+(\d+)\s+taxmann\.com\s+(\d+)", re.IGNORECASE
)

# --- Name-based citations ---

# Matches "X v. Y" or "X vs. Y" or "X versus Y" style case names when preceded
# by contextual phrasing like "in", "decision in", "case of", "relied on", etc.
# Captures party names (2+ word sequences) separated by v./vs./versus.
# Requires at least 2 words on each side to reduce false positives.
NAME_CITATION_PATTERN: re.Pattern[str] = re.compile(
    r"(?:(?:in|decision\s+in|case\s+of|relied\s+on|referred\s+to|overruled\s+in|"
    r"followed\s+in|distinguished\s+in|held\s+in|observed\s+in|reported\s+in)"
    r"\s+)"
    r"((?:[A-Z][a-zA-Z.']+(?:\s+(?:of|the|&|and)\s+)?)+)"  # petitioner name
    r"\s+(?:v\.?s?\.?|versus)\s+"
    r"((?:[A-Z][a-zA-Z.']+(?:\s+(?:of|the|&|and)\s+)?)+)"  # respondent name
    r"(?:\s*\(supra\))?",
    re.MULTILINE,
)


# --- Company Cases ---

# (2020) 123 CompCas 456
COMP_CAS_PATTERN: re.Pattern[str] = re.compile(
    r"[\(\[](\d{4})[\)\]]\s+(\d+)\s+Comp\s*Cas\s+(\d+)", re.IGNORECASE
)

# --- LLJ (Labour Law Journal) ---

# 2020 LLJ 123
LLJ_PATTERN: re.Pattern[str] = re.compile(
    r"(\d{4})\s+LLJ\s+(\d+)"
)

# --- Generic catch-all for unknown reporter formats ---

# Matches: "2020 XYZ 145" or "(2020) 3 XYZ 145" where XYZ is 2-6 letter abbreviation.
# Runs LAST in extract_citations() to avoid duplicating known patterns.
# Capped at 10 matches per document.
GENERIC_REPORTER_PATTERN: re.Pattern[str] = re.compile(
    r"(?:(\d{4})\s+|\((\d{4})\)\s+(?:\d+\s+)?)"
    r"([A-Z][A-Za-z]{1,5})"
    r"\s+(\d+)"
)

# Common English words to exclude from catch-all matches
_CATCH_ALL_STOPWORDS: frozenset[str] = frozenset({
    "THE", "AND", "FOR", "NOT", "BUT", "WAS", "HAS", "HAD",
    "ARE", "HIS", "HER", "ITS", "ANY", "ALL", "MAY", "CAN",
    "ACT", "THAT", "THIS", "WITH", "FROM", "BEEN", "HAVE",
    "ALSO", "SUCH", "UPON", "INTO", "OVER", "SAID", "CASE",
    "COURT", "ORDER", "UNDER", "SHALL", "STATE", "INDIA",
    "WHICH", "WHERE", "WOULD", "COULD", "SHOULD",
})

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
    "I.P.C.": "Indian Penal Code",
    "Penal Code": "Indian Penal Code",
    "CRPC": "Code of Criminal Procedure",
    "CrPC": "Code of Criminal Procedure",
    "Cr.P.C.": "Code of Criminal Procedure",
    "Criminal Procedure Code": "Code of Criminal Procedure",
    "CPC": "Code of Civil Procedure",
    "C.P.C.": "Code of Civil Procedure",
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
    "Evidence Act": "Indian Evidence Act",
    "CONTRACT ACT": "Indian Contract Act",
    "Contract Act": "Indian Contract Act",
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
    "RERA": "Real Estate (Regulation and Development) Act",
    "COMPETITION ACT": "Competition Act",
    "CUSTOMS ACT": "Customs Act",
    "RBI ACT": "Reserve Bank of India Act",
    "POSH ACT": "Prevention of Sexual Harassment at Workplace Act",
    "JJ ACT": "Juvenile Justice (Care and Protection of Children) Act",
    "MCOCA": "Maharashtra Control of Organised Crime Act",
    "COFEPOSA": "Conservation of Foreign Exchange and Prevention of Smuggling Activities Act",
    "ESI ACT": "Employees' State Insurance Act",
    "ID ACT": "Industrial Disputes Act",
    "GRATUITY ACT": "Payment of Gratuity Act",
    "MW ACT": "Minimum Wages Act",
    "RENT ACT": "Rent Control Act",
    "IT ACT 2000": "Information Technology Act",
    # --- [A3] Criminal (added) ---
    "NIA ACT": "National Investigation Agency Act",
    "EXPLOSIVES ACT": "Explosives Act",
    "NSA": "National Security Act",
    # --- [A3] Commercial ---
    "PARTNERSHIP ACT": "Indian Partnership Act",
    "LLP ACT": "Limited Liability Partnership Act",
    "MSMED ACT": "Micro, Small and Medium Enterprises Development Act",
    "INSURANCE ACT": "Insurance Act",
    "SGST ACT": "State Goods and Services Tax Act",
    "CENTRAL EXCISE ACT": "Central Excise Act",
    "NEGOTIABLE INSTRUMENTS ACT": "Negotiable Instruments Act",
    "SARFAESI ACT": "Securitisation and Reconstruction of Financial Assets "
                    "and Enforcement of Security Interest Act",
    # --- [A3] Family ---
    "HSA": "Hindu Succession Act",
    "SMA": "Special Marriage Act",
    "GWA": "Guardians and Wards Act",
    "HINDU ADOPTION ACT": "Hindu Adoptions and Maintenance Act",
    "MUSLIM PERSONAL LAW ACT": "Muslim Personal Law (Shariat) Application Act",
    # --- [A3] Labor ---
    "FACTORIES ACT": "Factories Act",
    "EPF ACT": "Employees' Provident Funds and Miscellaneous Provisions Act",
    "PW ACT": "Payment of Wages Act",
    "TU ACT": "Trade Unions Act",
    "WC ACT": "Workmen's Compensation Act",
    "CODE ON WAGES": "Code on Wages",
    "CODE ON SOCIAL SECURITY": "Code on Social Security",
    "CODE ON INDUSTRIAL RELATIONS": "Code on Industrial Relations",
    "OSH CODE": "Occupational Safety, Health and Working Conditions Code",
    # --- [A3] Tax ---
    "INCOME TAX ACT": "Income Tax Act",
    "STAMP ACT": "Indian Stamp Act",
    "BENAMI ACT": "Prohibition of Benami Property Transactions Act",
    "BLACK MONEY ACT": "Black Money (Undisclosed Foreign Income and Assets) Act",
    # --- [A3] Constitutional/Admin ---
    "LOKPAL ACT": "Lokpal and Lokayuktas Act",
    "CONTEMPT ACT": "Contempt of Courts Act",
    "CAT ACT": "Administrative Tribunals Act",
    # --- [A3] Property ---
    "EASEMENTS ACT": "Indian Easements Act",
    "RFCTLARR ACT": "Right to Fair Compensation and Transparency in Land Acquisition Act",
    # --- [A3] Environmental ---
    "FOREST ACT": "Indian Forest Act",
    "FC ACT": "Forest Conservation Act",
    "WATER ACT": "Water (Prevention and Control of Pollution) Act",
    "AIR ACT": "Air (Prevention and Control of Pollution) Act",
    "NGT ACT": "National Green Tribunal Act",
    # --- [A3] Technology ---
    "DPDP ACT": "Digital Personal Data Protection Act",
    "AADHAAR ACT": "Aadhaar (Targeted Delivery of Financial Assistance and Other Subsidies, Benefits and Services) Act",
    # --- [SA3] High-frequency act aliases ---
    "LA": "Limitation Act",
    "PCA": "Prevention of Corruption Act",
    "PC ACT": "Prevention of Corruption Act",
    "GCA": "General Clauses Act",
    "LARR": "Right to Fair Compensation and Transparency in Land Acquisition, "
            "Rehabilitation and Resettlement Act",
    "LAA": "Land Acquisition Act",
    "MVA": "Motor Vehicles Act",
    "CPA": "Consumer Protection Act",
    "CONSUMER ACT": "Consumer Protection Act",
    "DPA": "Dowry Prohibition Act",
    "NHA": "National Highways Act",
    "POCSO": "Protection of Children from Sexual Offences Act",
    "LSA": "Legal Services Authorities Act",
    "POTA": "Prevention of Terrorism Act",
    "RPA": "Representation of the People Act",
    "MMDRA": "Mines and Minerals (Development and Regulation) Act",
    "MACT": "Motor Accident Claims Tribunal Act",
    "FA": "Foreigners Act",
    # --- [SA3b] Aliases discovered in blind spot check ---
    "RFCTLARR ACT": "Right to Fair Compensation and Transparency in Land Acquisition, "
                    "Rehabilitation and Resettlement Act",
    "CIVIL PROCEDURE CODE": "Code of Civil Procedure",
    "CRIMINAL PROCEDURE CODE": "Code of Criminal Procedure",
    "WILD LIFE ACT": "Wild Life (Protection) Act",
    "WILDLIFE ACT": "Wild Life (Protection) Act",
    "ENVIRONMENT PROTECTION ACT": "Environment (Protection) Act",
    "GWA": "Guardians and Wards Act",
    "SEBI ACT": "Securities and Exchange Board of India Act",
    "RBI ACT": "Reserve Bank of India Act",
    "GRATUITY ACT": "Payment of Gratuity Act",
    "CAT ACT": "Administrative Tribunals Act",
    "WC ACT": "Employees' Compensation Act",
    "RPwD Act": "Rights of Persons with Disabilities Act",
    "RPWD ACT": "Rights of Persons with Disabilities Act",
    "EPA": "Environment (Protection) Act",
    "INDIAN SUCCESSION ACT": "Indian Succession Act",
    "INDIAN REGISTRATION ACT": "Registration Act",
    "RP ACT": "Representation of the People Act",
    "FERA": "Foreign Exchange Regulation Act",
    # --- [SA7] Display-name entries (short code → full name) ---
    "COI": "Constitution of India",
    "IEA": "Indian Evidence Act",
    "ICA": "Indian Contract Act",
    "TPA": "Transfer of Property Act",
    "ACA": "Arbitration and Conciliation Act",
    "ITA": "Income Tax Act",
    "SOGA": "Sale of Goods Act",
    "CA2013": "Companies Act",
    "IPA": "Indian Partnership Act",
}

# Reverse mapping: full act name → preferred short code (for DB lookups).
# Built from _SHORT_ACT_NAMES — uses the SHORTEST key that maps to each
# full name, preferring keys without dots (e.g. "IPC" over "I.P.C.").
_FULL_TO_SHORT: dict[str, str] = {}
for _short, _full in _SHORT_ACT_NAMES.items():
    _full_lower = _full.lower()
    existing = _FULL_TO_SHORT.get(_full_lower)
    if existing is None or (len(_short) < len(existing)) or ("." in existing and "." not in _short):
        _FULL_TO_SHORT[_full_lower] = _short
# Add "Constitution of India" → "COI" for Article references
_FULL_TO_SHORT["constitution of india"] = "COI"

# Year each act was enacted — used for human-readable display names.
_ACT_YEARS: dict[str, int] = {
    "IPC": 1860, "BNS": 2023, "CRPC": 1973, "BNSS": 2023,
    "CPC": 1908, "IEA": 1872, "BSA": 2023, "COI": 1950,
    "ICA": 1872, "TPA": 1882, "ACA": 1996, "IBC": 2016,
    "PMLA": 2002, "NDPS ACT": 1985, "NI ACT": 1881, "UAPA": 1967,
    "IT ACT": 2000, "ITA": 1961, "SARFAESI": 2002, "FEMA": 1999,
    "RERA": 2016, "HMA": 1955, "HSA": 1956, "DV ACT": 2005,
    "LA": 1963, "PCA": 1988, "GCA": 1897, "MVA": 1988,
    "CPA": 2019, "DPA": 1961, "RPA": 1951,
    "COMPETITION ACT": 2002, "CONTEMPT ACT": 1971,
    "REGISTRATION ACT": 1908, "STAMP ACT": 1899,
    "FACTORIES ACT": 1948, "ID ACT": 1947, "CGST ACT": 2017,
    "EASEMENTS ACT": 1882, "SOGA": 1930, "BENAMI ACT": 1988,
    "JJ ACT": 2015, "DPDP ACT": 2023, "LLP ACT": 2008,
    "LOKPAL ACT": 2013, "AADHAAR ACT": 2016, "CA2013": 2013,
    "NIA ACT": 2008, "ARMS ACT": 1959,
    "LIMITATION ACT": 1963, "ARBITRATION ACT": 1996,
    "COMPANIES ACT": 2013, "POCSO ACT": 2012, "RTI ACT": 2005,
    "TADA": 1987, "SC/ST ACT": 1989, "TP ACT": 1882,
    "MV ACT": 1988, "LAA": 1894, "IPA": 1932,
    "INSURANCE ACT": 1938, "CE ACT": 1944,
    "MW ACT": 1948, "EPF ACT": 1952, "SMA": 1954,
    "NHA": 1956, "EC ACT": 1923, "TU ACT": 1926,
    "PW ACT": 1936, "AT ACT": 1985, "GW ACT": 1890,
    "WLP ACT": 1972, "MSMED ACT": 2006, "POCSO": 2012,
    "BR ACT": 1949, "CUSTOMS ACT": 1962, "EP ACT": 1986,
    "FC ACT": 1980, "LARR": 2013, "ESI ACT": 1948,
    "HSA": 1956,
}


def get_act_display_name(short_code: str) -> str:
    """Return a human-readable display name for an act short code.

    Looks up the full name from ``_SHORT_ACT_NAMES`` and appends the
    enactment year from ``_ACT_YEARS`` when available.

    Falls back to ``short_code`` itself if not found.

    Examples:
        "IPC" → "Indian Penal Code, 1860"
        "XYZ" → "XYZ"
    """
    upper = short_code.strip().upper()
    full_name = _SHORT_ACT_NAMES.get(upper)
    if full_name is None:
        return short_code
    year = _ACT_YEARS.get(upper)
    if year is not None:
        return f"{full_name}, {year}"
    return full_name


def get_acts_cited_display(short_codes: list[str] | None) -> list[dict[str, str]]:
    """Convert list of short codes to display objects.

    Returns: [{"code": "IPC", "name": "Indian Penal Code, 1860"}, ...]
    """
    return [
        {"code": code, "name": get_act_display_name(code)}
        for code in short_codes
    ] if short_codes else []


def normalize_act_name(raw: str) -> str:
    """Map an act name (full or short) to the canonical short code used in the statute DB.

    Always returns the SHORTEST key that maps to the same full act name,
    so "Limitation Act" → "LA" (not "LIMITATION ACT"), and
    "Negotiable Instruments Act" → "NI ACT" (not "NEGOTIABLE INSTRUMENTS ACT").

    Examples:
        "Indian Penal Code" → "IPC"
        "IPC" → "IPC"
        "Constitution of India" → "COI"
        "Limitation Act" → "LA"
        "Negotiable Instruments Act" → "NI ACT"
    """
    stripped = raw.strip()
    upper = stripped.upper()
    # Direct short-code match — but prefer the shortest alias for the same full name.
    # E.g., "LIMITATION ACT" is a valid key, but "LA" maps to the same full name
    # and is shorter. We want "LA".
    if upper in _SHORT_ACT_NAMES:
        full_name = _SHORT_ACT_NAMES[upper]
        # Check if a shorter key maps to the same full name
        shortest = _FULL_TO_SHORT.get(full_name.lower())
        if shortest and len(shortest) < len(upper):
            return shortest
        return upper
    # Full-name reverse lookup (case-insensitive)
    short = _FULL_TO_SHORT.get(stripped.lower())
    if short:
        return short
    # Partial match: try stripping ", YYYY" year suffix
    no_year = re.sub(r",?\s*\d{4}\s*$", "", stripped)
    short = _FULL_TO_SHORT.get(no_year.lower())
    if short:
        return short
    return stripped


# ---------------------------------------------------------------------------
# Acts-cited normalization & garbage filter
# ---------------------------------------------------------------------------

_ACTS_CITED_BLOCKLIST: frozenset[str] = frozenset({
    "unknown act", "act", "code", "the act", "said act", "that act",
    "same act", "this act", "the code", "india", "protocols",
    "society", "principal act", "erstwhile act", "new act", "old act",
    "subsequently", "accordingly", "therefore", "however", "moreover",
    "state", "method",
    # Single letters/fragments
    "cr", "m", "s", "p", "r", "a",
    # State names
    "maharashtra", "rajasthan", "gujarat", "uttar pradesh", "karnataka",
    "punjab", "haryana", "bihar", "kerala", "tamil nadu", "andhra pradesh",
    "telangana", "madhya pradesh", "west bengal", "odisha", "assam",
    "nct of delhi", "delhi", "goa", "jharkhand", "chhattisgarh",
    "uttarakhand", "himachal pradesh", "jammu and kashmir",
    "tripura", "meghalaya", "manipur", "mizoram", "nagaland",
    "arunachal pradesh", "sikkim", "puducherry", "chandigarh",
    "ladakh", "lakshadweep",
})

# Patterns to strip "Section X of " or "Article X of " prefix
_SECTION_OF_PATTERN: re.Pattern[str] = re.compile(
    r"^(?:Sections?|Sec\.?|Ss\.|S\.)\s+[\d\w]+(?:\s*\([^)]+\))*"
    r"(?:\s+(?:read\s+with|r/w|r\.w\.)\s+(?:Sections?|Sec\.?|Ss\.|S\.)\s+[\d\w]+(?:\s*\([^)]+\))*)?"
    r"\s+(?:of\s+(?:the\s+)?)?",
    re.IGNORECASE,
)

_ARTICLE_OF_PATTERN: re.Pattern[str] = re.compile(
    r"^(?:Article|Art\.?)\s+[\d]+[A-Za-z]?(?:\s*\(\d+\))?(?:\s*\([a-z]\))?"
    r"\s+(?:of\s+(?:the\s+)?)?",
    re.IGNORECASE,
)

# "Section 302 r/w Section 34 IPC" — extract act at end
_SECTION_RW_SHORT_PATTERN: re.Pattern[str] = re.compile(
    r"^(?:Sections?|Sec\.?|Ss\.|S\.)\s+[\d\w]+(?:\s*\([^)]+\))*"
    r"\s+(?:read\s+with|r/w|r\.w\.)\s+"
    r"(?:Sections?|Sec\.?|Ss\.|S\.)?\s*[\d\w]+(?:\s*\([^)]+\))*"
    r"\s+(.+)$",
    re.IGNORECASE,
)

# "Section 302 IPC" — extract act code after section number
_SECTION_SHORT_EXTRACT: re.Pattern[str] = re.compile(
    r"^(?:Sections?|Sec\.?|Ss\.|S\.)\s+[\d\w]+(?:\s*\([^)]+\))*"
    r"(?:\s*[,/]\s*[\d\w]+(?:\s*\([^)]+\))*)*"
    r"(?:\s+(?:and|&)\s+[\d\w]+(?:\s*\([^)]+\))*)?"
    r"\s+(.+)$",
    re.IGNORECASE,
)


def _is_valid_act_citation(name: str) -> bool:
    """Return True if name looks like a real act citation, not garbage."""
    stripped = name.strip()
    # Known short codes or full names are always valid regardless of length
    if stripped.upper() in _SHORT_ACT_NAMES:
        return True
    if stripped.lower() in _FULL_TO_SHORT:
        return True
    if len(stripped) < 3:
        return False
    # Sentence fragments: real act names are rarely >60 chars (known codes exit early above)
    if len(stripped) > 60:
        return False
    # Contains multiple spaces + lowercase words = likely a sentence, not an act name
    if len(stripped.split()) > 10:
        return False
    lower = stripped.lower()
    if lower in _ACTS_CITED_BLOCKLIST:
        return False
    # Year-only: "2013"
    if re.match(r"^\d{4}$", stripped):
        return False
    # "1996 Act" pattern
    if re.match(r"^\d{4}\s*Act$", stripped, re.IGNORECASE):
        return False
    # Contains newlines (should have been cleaned)
    if "\n" in stripped or "\r" in stripped:
        return False
    # CPC procedural refs like "Order VII Rule 11" are not act names
    if re.match(r"^Order\s+\w+\s+Rule\s+\d+", stripped, re.IGNORECASE):
        return False
    # Standalone section/article/chapter/part references are not act names
    # Catches: "Section 95", "Article 21", "Chapter III of Part III", "Part II"
    if re.match(
        r"^(?:Sections?|Sec\.?|Articles?|Art\.?|Chapter|Part)\s+[\dIVXLCDM]+",
        stripped,
        re.IGNORECASE,
    ):
        return False
    # Digit glued to text end: "Madras5", "Part III 57" (but not known codes like "CA2013")
    if re.search(r"[a-zA-Z]\d+$", stripped):
        return False
    # Trailing standalone digit: "West Bengal 4", "India13"
    if re.search(r"\s\d{1,3}$", stripped):
        return False
    # Standalone incomplete references: "Act of", "Act in", "Code of", "Erstwhile Act"
    if re.match(
        r"^(?:Act|Code|Statute|Erstwhile\s+Act|Principal\s+Act)\s*(?:of|in|to|by|as|the)?\s*$",
        stripped,
        re.IGNORECASE,
    ):
        return False
    # Single-letter prefix: "F Act in case of death", "E Consumer Protection Act defines..."
    if re.match(r"^[A-Z]\s+", stripped) and len(stripped.split()) > 2:
        return False
    # Isolated single letter in the middle: "Arbitration A Act", "Maharashtra G Act"
    # (OCR noise inserting a stray letter into an otherwise valid name)
    if re.search(r"\b[A-Z]\b", stripped) and re.search(r"\s[A-Z]\s", stripped):
        # Allow known patterns like "Type A Act" or "Schedule A"
        if not re.search(r"(?:Type|Schedule|Class|Category|Form|Part|Appendix)\s+[A-Z]\b", stripped):
            return False
    # Starts with lowercase letter → sentence fragment, never an act name
    if stripped[0].islower():
        return False
    # OCR garbage: contains digit clusters mixed with letters mid-word
    # "Mah11Tashlra", "Central 7956 Provinces", "A0t"
    if re.search(r"[a-zA-Z]\d+[a-zA-Z]", stripped):
        return False
    # Standalone 2-3 letter gibberish with mixed case: "A0t", "Sri _"
    if re.search(r"[_~`]", stripped):
        return False
    # Bare "Act " at start → never a real act name (acts are "X Act", not "Act X")
    # Catches: "Act and", "Act must be", "Act stands quashed", "Act referred to above"
    if re.match(r"^Act\s+", stripped):
        return False
    # "[Year] Code" without full name → "1973 Code", "1898 Code" are sentence fragments
    if re.match(r"^\d{4}\s+Code$", stripped, re.IGNORECASE):
        return False
    # "[Year] [single-letter] Act" → paragraph/margin markers: "1956 H Act", "1961 B Act"
    if re.match(r"^\d{4}\s+[A-Z]\s+Act$", stripped):
        return False
    # Standalone numbers (1-3 digits) → "139", "272", "420" are section numbers, not acts
    if re.match(r"^\d{1,3}$", stripped):
        return False
    # Starts with "[number] of" → section reference without "Section" prefix
    # Catches: "13 of the Consumer Protection Act", "24 of the Act"
    if re.match(r"^\d{1,4}\s+of\s+", stripped, re.IGNORECASE):
        return False
    # Trailing " and" or " but" or " or" → sentence fragment cut-off
    # Catches: "SARFAESI Act and", "NI Act and", "Evidence Act but"
    if re.search(r"\s+(?:and|but|or)$", stripped, re.IGNORECASE):
        return False
    # "[Year] [Act/Code] [word...]" where the continuation is a sentence fragment
    # Catches: "1996 Act for setting aside", "1894 Act in accordance with law"
    # But NOT: "2019 Amendment Act" (legitimate)
    if re.match(r"^\d{4}\s+(?:Act|Code)\s+\w", stripped):
        return False
    # "[Number] [word]..." patterns that are clearly not acts
    # Catches: "16 March", "60 years", "12 levels", "22 species"
    if re.match(r"^\d{1,4}\s+(?:March|April|May|June|July|August|September|October|November|December|January|February|years?|months?|days?|levels?|species|bodies|houses?|candidates|complainants|appellants|individuals|lanes?|acres|marks|departments|ministries)\b", stripped, re.IGNORECASE):
        return False
    # Entries starting with "[number] [uppercase word]" that look like footnotes/references
    # Catches: "1 For short", "1 Hereinafter", "3 Central Bureau", "4 lane"
    if re.match(r"^\d{1,2}\s+(?:For|Hereinafter|Central|Reproduced|Supra)\b", stripped):
        return False
    # "[Act Name] [verb/preposition]..." pattern — catches "Act mandates...",
    # "IPC declares...", "Customs Act speaks of...", "BNSS of cancellation..."
    # Real act citations don't continue with verbs or sentence fragments.
    if re.match(
        r"^(?:.*?\b(?:Act|Code)\b|IPC|CRPC|CrPC|CPC|BNS|BNSS|BSA|IEA|POCSO|PMLA|"
        r"NI Act|SARFAESI|IBC|NDPS|FEMA|RERA|SEBI|FA|LA|TADA|"
        r"\d{4}\s+Act)\s+"
        r"(?:mandates?|enables?|confers?|enacts?|prescribes?|stipulates?|declares?|"
        r"prohibits?|authorizes?|imposes?|contemplates?|empowers?|recognizes?|"
        r"requires?|specifies?|permits?|signifies?|invit\w+|pray\w+|seek\w+|"
        r"satisfies|acknowledges?|overrides?|operates?|covers?|concerns?|"
        r"allocat\w+|raises?|speak\w+|bars?|makes?\b|pertains?|"
        r"in\s+(?:the|regard|relation|isolation|terms|view|essential|August|connection)|"
        r"of\s+(?:cancellation|all|certain|this|the|its|\d{4})|"
        r"gets?\s+attracted|along\s+with|for\s+(?:the|her|his|public|determining|granting|"
        r"possession|pronouncing|disclos|being|checking)|"
        r"being\s+|while\s+|whereas\s+|inasmuch\s+|"
        r"to\s+(?:undergo|provide|advise|extend|meet|fix|grant|secure|ask|do|"
        r"apply|decide|determine|lodge|file|get|place|regulate|condone|"
        r"adopt|enforce|implement|interpret|invoke|maintain|examine)|"
        r"referred\s+to\s+|as\s+(?:amended|extracted|noted|quoted|discussed|unconstitutional|void|such)|"
        r"stands?\s+(?:quashed|satisfied|excluded|fulfilled|duly|revived|repealed|unamended|attracted)|"
        r"came\s+(?:for|to\s+be)|on\s+(?:the\s+basis|being|levy|such|6th|26th|30|1st)|"
        r"within\s+(?:a\s+period|the\s+(?:pension|territorial|prescribed)|three|ten|60|12)|"
        r"challenging\s+|claiming\s+|alleging\s+|citing\s+|assailing\s+|"
        r"at\s+(?:all|the\s+(?:start|Principal|enhanced)|once|11)|"
        r"(?:remain|give|lend|need|carry|lay|cast)s?\s+)",
        stripped,
        re.IGNORECASE,
    ):
        return False
    # Sentence fragments: real act names never contain verbs/conjunctions/prepositions
    # Catches: "IPC is concerned", "shall also apply", "Evidence Act is not relevant",
    #          "those candidates who went ahead", "empowers the resolution professional",
    #          "Erstwhile Act which governed the field", "how accused"
    if re.search(
        r"\b(is|are|was|were|shall|should|will|would|has|have|had|not|cannot|can|must|need|"
        r"dismissed|concerned|relevant|applied|applicable|lodged|set aside|"
        r"at this stage|without insisting|outlines the|"
        # Verbs commonly found in LLM-hallucinated fragments
        r"went|governed|governs|empowers|empowered|include|includes|included|including|"
        r"filed|alleged|contended|submitted|argued|claimed|stated|held|observed|"
        r"directed|ordered|granted|rejected|made|passed|enacted|given|may|"
        r"dealt|dealing|deals|provides|provided|providing|compared|hold|holds|holding|"
        r"mandates?|enables?|confers?|enacts?|prescribes?|stipulates?|declares?|"
        r"prohibits?|authorizes?|contemplates?|signifies?|acknowledges?|"
        r"recognizes?|requires?|specifies?|satisfies|permits?|covers?|"
        r"operates?|overrides?|inviting|praying|seeking|allocating|raising|"
        # Pronouns/relative words that never appear in act names
        r"those|who|ahead|how|which|that|these|whose|whom|"
        # Prepositions/conjunctions unlikely in act names (common in sentences)
        r"against|upon|between|about|into|since|also|only|merely|even|before|after|by|any|as well|"
        r"whether|whereby|herein|thereof|therein|thereupon|thereto|"
        # Legal context words that indicate sentence fragments
        r"respect|punishable|nature|scenario|plainly|"
        r"declarant|accused|petitioner|respondent|appellant|"
        r"citizens?|community|society|population|people|person|"
        r"dated|amount|deposit|cash|suit|"
        # Additional verbs/adjectives found in remaining garbage
        r"defines?|stands?|vested?|lays?\s+down|carves?|casts?|"
        r"remained?|uses?\b|employs?|creates?|adopts?|saves?|"
        r"combines?|recognises?|accords?|affords?|brings?|"
        r"ceased?|repealed?|amended?|dilutes?|revives?|revived?|"
        r"applies?|attracted?|depends?|entails?|posits?|"
        r"warrants?|obliges?|lends?|fails?|arises?|arrives?|"
        r"surfaces?|interdicts?|elucidates?|enumerates?|"
        # Sentence-ending words
        r"supra|hereinabove|hereinafter|aforesaid|whereunder|nugatory|"
        r"expeditiously|sparingly|efficacious|inefficacious|unconstitutional|"
        r"ultra\s+vires|suo\s+motu|forthwith|mandatorily|"
        # Party-role words (party names leaking into acts_cited)
        r"plaintiff|defendant|complainant|prosecution|defence|"
        # OCR-specific words that appear in garbled fragments
        r"judgment|judgement|lordship|lordships|honour|"
        r"question|consideration|contention|submission|argument)\b",
        stripped,
        re.IGNORECASE,
    ):
        return False
    # Ends with a preposition — always a sentence fragment, never a valid act name
    # "Foreigners Act on", "Customs Act be", "Code of Civil Procedure from"
    if re.search(
        r"\s+(?:on|be|from|with|for|at|by|to|in|as|is|if|so|no|do|an|up|it)$",
        stripped,
        re.IGNORECASE,
    ):
        return False
    # Contains "v." or "v " or "versus" — it's a case name, not an act
    if re.search(r"\bv\.?\s|\bversus\b|\bv$", stripped, re.IGNORECASE):
        return False
    # All-caps sentence fragments: "COURT In accordance...", "STATE OF MYSORE..."
    # Real act names in all-caps are short codes (already matched above);
    # long all-caps strings with prepositions are sentence fragments
    if stripped.isupper() and len(stripped.split()) > 3:
        return False
    # Starts with all-caps non-act word: "COURT ...", "CRIMINAL ..."
    if re.match(
        r"^(?:COURT|CRIMINAL|STATE|CIVIL|CHIEF|LEARNED|HONOURABLE|HON'BLE)\s+",
        stripped,
    ):
        return False
    # "Code i", "Scheduled Tribes i" — truncated entries ending in single letter
    if re.search(r"\s[a-z]$", stripped):
        return False
    # Bare "The" or "The [non-Act word]" — not an act name
    if stripped.lower() == "the":
        return False
    if re.match(r"^The\s+(?!.*\bAct\b|.*\bCode\b|.*\bRules?\b|.*\bOrder\b)", stripped):
        return False
    # "[Act Name] bv/bY/hv [words]" — OCR-corrupted "by" followed by sentence fragment
    if re.search(r"\b(?:bv|hv|hy)\b", stripped, re.IGNORECASE):
        return False
    # "[Name] Act No. [N] of" — incomplete statutory reference
    if re.search(r"\bAct\s+No\.\s*\d+\s+of\s*$", stripped, re.IGNORECASE):
        return False
    # "[Year] [Name] Act" where year is in the middle — suspicious pattern
    # Real: "Motor Vehicles Act, 1939" (year at end). Garbage: "Motor Vehicles 1959 Act"
    if re.match(r"^[A-Z][\w\s]+\d{4}\s+Act\s*$", stripped):
        return False
    # Act name ending with Roman numerals + "of" pattern: "Travancore Act XIV of"
    # These are incomplete statute references (missing the year)
    if re.match(r".+\b[IVXLC]+\s+of\s*$", stripped):
        return False
    # Act name ending with year fragment: "Travancore Act XIV of 1124 M"
    if re.search(r"\d{3,4}\s+[A-Z]$", stripped):
        return False
    return True


# ---------------------------------------------------------------------------
# Cases-cited discriminator (GAN architecture: this is the Discriminator)
# ---------------------------------------------------------------------------

# Regex for bare reporter references (no case name attached)
_BARE_REPORTER_RE: re.Pattern[str] = re.compile(
    r"^[\[\(]?\d{4}[\]\)]?\s+"                    # year prefix
    r"(?:"
    r"\d+\s+SCC(?:\s+\([^)]+\))?\s+\d+"           # (2020) 3 SCC 145
    r"|SCC\s+OnLine\s+\w+\s+\d+"                   # 2020 SCC OnLine SC 145
    r"|AIR\s+\w+\s+\d+"                            # AIR 2020 SC 145
    r"|INSC\s+\d+"                                 # 2020 INSC 145
    r"|\d+\s+SCR\s+\d+"                            # [2020] 3 SCR 145
    r"|CrLJ\s+\d+"                                 # 2020 CrLJ 145
    r"|\d+\s+SCALE\s+\d+"                          # (2020) 3 SCALE 145
    r"|LiveLaw\s+\(\w+\)\s+\d+"                    # 2024 LiveLaw (SC) 123
    r"|\d+\s+ITR\s+\d+"                            # [2020] 123 ITR 456
    r"|\d+\s+taxmann\.com\s+\d+"                   # [2020] 123 taxmann.com 456
    r"|\d+\s+CompCas\s+\d+"                        # (2020) 123 CompCas 456
    r"|LLJ\s+\d+"                                  # 2020 LLJ 123
    r"|\d+\s+JT\s+(?:\(\w+\)\s+)?\d+"             # JT 2020 (3) SC 145
    r")",
    re.IGNORECASE,
)

# Neutral citation format: 2023:INSC:1234 or 2023:DELHC:1234
_BARE_NEUTRAL_RE: re.Pattern[str] = re.compile(
    r"^\d{4}:[A-Z]{2,10}:\d+$"
)

# MANU format: MANU/SC/1234/2020
_BARE_MANU_RE: re.Pattern[str] = re.compile(
    r"^MANU/\w+/\d+/\d{4}$", re.IGNORECASE,
)

# HC reporters (bare): "2020 ILR 145", "(2020) 3 BLR 145"
_BARE_HC_REPORTER_RE: re.Pattern[str] = re.compile(
    r"^[\[\(]?\d{4}[\]\)]?\s+(?:\d+\s+)?(?:ILR|MLJ|KLT|BLR|GLR|ALJ|DLT|ALD|CLT|PLR|"
    r"DRJ|KHC|RLW|AIOL|AILJ|APLJ|GUJLH|KLTI|PLJR|WLN|MPWN|ELT|STR|STC|ECR)\s+\d+",
    re.IGNORECASE,
)


def is_bare_citation_ref(text: str) -> bool:
    """Return True if text is a bare reporter reference with no case name.

    Bare refs like '(2020) 3 SCC 145' are valid citation references but not
    useful as cases_cited entries (which should be 'Party v. Party, Reporter').
    These are separated into citation_refs for graph linking.
    """
    stripped = text.strip()
    if _BARE_REPORTER_RE.match(stripped):
        return True
    if _BARE_NEUTRAL_RE.match(stripped):
        return True
    if _BARE_MANU_RE.match(stripped):
        return True
    if _BARE_HC_REPORTER_RE.match(stripped):
        return True
    return False


def _is_valid_case_citation(text: str) -> bool:
    """Discriminator: return True if text is a valid named case citation.

    Validates that a cases_cited entry looks like a real case reference
    (e.g., 'Laxman v. State of Maharashtra, (2002) 6 SCC 710') and not
    garbage, sentence fragments, or OCR noise.

    This is the Discriminator in the GAN architecture — it rejects bad
    candidates from the Generator (LLM + regex extraction).
    """
    stripped = text.strip()

    # Too short to be a case citation
    if len(stripped) < 5:
        return False

    # Too long — likely a sentence fragment or paragraph
    if len(stripped) > 300:
        return False

    # Contains newlines (should have been cleaned)
    if "\n" in stripped or "\r" in stripped:
        return False

    # Bare docket/petition numbers: "5095 Of 2025", "1040 of 2022"
    if re.match(r"^\d{2,5}\s+[Oo]f\s+\d{4}$", stripped):
        return False

    # Bare year: "2013", "1995"
    if re.match(r"^\d{4}$", stripped):
        return False

    # Page number artifacts: "1173 El\n3", "1620 MT\n4", "1952 It 1"
    if re.match(r"^\d{3,4}\s+[A-Z][a-z]\s*\d*$", stripped):
        return False

    # Starts with lowercase — sentence fragment, not a case name
    if stripped[0].islower():
        return False

    # OCR garbage: contains underscores, tildes, backticks
    if re.search(r"[_~`]", stripped):
        return False

    # Pure numbers with spaces: "1 2 3 4"
    if re.match(r"^[\d\s]+$", stripped):
        return False

    # Section/Article references mistakenly in cases_cited
    if re.match(
        r"^(?:Sections?|Sec\.?|Articles?|Art\.?|Order|Rule|Clause)\s+",
        stripped,
        re.IGNORECASE,
    ):
        return False

    # Act names mistakenly in cases_cited
    if re.search(r"\b(?:Act|Code|Rules?|Regulations?),?\s+\d{4}\s*$", stripped) and "v." not in stripped.lower():
        return False

    return True


def classify_case_citations(
    raw_list: list[str],
) -> tuple[list[str], list[str]]:
    """Split cases_cited into named citations and bare reporter refs.

    This is the core GAN merge step: the Discriminator classifies each
    candidate from the Generator into:
    - named_citations: entries with case names (kept in cases_cited)
    - bare_refs: reporter references without names (stored separately)

    Returns:
        (named_citations, bare_refs) — both sorted and deduplicated.
    """
    named: list[str] = []
    bare: list[str] = []
    seen_named: set[str] = set()
    seen_bare: set[str] = set()

    for entry in raw_list:
        if not entry or not isinstance(entry, str):
            continue
        cleaned = re.sub(r"\s+", " ", entry).strip()
        if not cleaned:
            continue

        # First: discriminator validity check
        if not _is_valid_case_citation(cleaned):
            continue

        # Second: classify as named or bare
        if is_bare_citation_ref(cleaned):
            norm = cleaned.lower()
            if norm not in seen_bare:
                seen_bare.add(norm)
                bare.append(cleaned)
        else:
            norm = cleaned.lower()
            if norm not in seen_named:
                seen_named.add(norm)
                named.append(cleaned)

    return sorted(named), sorted(bare)


def _repair_ocr_act_name(text: str) -> str:
    """Attempt to repair common OCR corruptions in act names.

    Fixes:
    - Space-broken words: "Cen tral" -> "Central", "Con tract" -> "Contract"
    - Letter corruptions: "Cootract" -> "Contract", "lnciia" -> "India"
    - Digit corruptions in years: "z959" -> "1959"
    """
    _SPACE_BREAK_FIXES: dict[str, str] = {
        "Cen tral": "Central", "Con tract": "Contract",
        "Govern ment": "Government", "Limi tation": "Limitation",
        "Consti tution": "Constitution", "Regu lation": "Regulation",
        "Admini stration": "Administration", "Proba tion": "Probation",
        "Arbi tration": "Arbitration", "Compen sation": "Compensation",
        "Acqui sition": "Acquisition", "Preven tion": "Prevention",
        "Protec tion": "Protection", "Infor mation": "Information",
        "Repre sentation": "Representation", "Proce dure": "Procedure",
        "Insol vency": "Insolvency", "Crimi nal": "Criminal",
        "Sched uled": "Scheduled", "Offi cers": "Officers",
        "Offend ers": "Offenders", "Amend ment": "Amendment",
        "Munici pal": "Municipal", "Elec tricity": "Electricity",
    }
    for broken, fixed in _SPACE_BREAK_FIXES.items():
        text = text.replace(broken, fixed)

    _LETTER_FIXES: dict[str, str] = {
        "Cootract": "Contract", "Cede": "Code", "Ptobation": "Probation",
        "Linlitation": "Limitation", "Offendets": "Offenders",
        "Offeuders": "Offenders", "lnciia": "India", "lndia": "India",
        "Iudia": "India", "Iadian": "Indian", "Peuai": "Penal",
        "Evideoce": "Evidence", "Crimiual": "Criminal",
        "Cousumer": "Consumer", "Represeutation": "Representation",
    }
    for garbled, correct in _LETTER_FIXES.items():
        if garbled in text:
            text = text.replace(garbled, correct)

    # Fix digit corruptions in years (z959 -> 1959, l960 -> 1960)
    text = re.sub(r"\b[zZlI](\d{3})\b", r"1\1", text)
    text = re.sub(r"\b(\d)[oO](\d{2})\b", r"\g<1>0\2", text)

    return text


def normalize_acts_cited_list(raw_acts: list[str]) -> list[str]:
    """Normalize a list of raw acts_cited strings to canonical short codes.

    Handles:
    - "Section 302 of Indian Penal Code, 1860" -> "IPC"
    - "Article 21 of Constitution of India" -> "COI"
    - "Indian Penal Code" -> "IPC"
    - "IPC" -> "IPC" (already normalized)
    - "Code of Criminal\\nProcedure" -> "CrPC" (newline-broken)
    - OCR space-breaks: "Cen tral Sales Tax Act" -> "Central Sales Tax Act"
    - OCR corruptions: "Cootract Act" -> "Contract Act" -> "ICA"
    - Filters garbage: "Unknown Act", "M", state names, etc.

    Returns sorted, deduplicated list of canonical short codes.
    """
    result: set[str] = set()

    for raw in raw_acts:
        if not raw or not isinstance(raw, str):
            continue

        # Step 1: Replace newlines with spaces, strip, then repair OCR
        cleaned = re.sub(r"[\r\n]+", " ", raw).strip()
        if not cleaned:
            continue
        cleaned = _repair_ocr_act_name(cleaned)

        # Step 2: Try to extract act name from various patterns
        act_name: str | None = None

        # Try "Section X r/w Section Y ActCode" first
        rw_match = _SECTION_RW_SHORT_PATTERN.match(cleaned)
        if rw_match:
            act_name = rw_match.group(1).strip()
        else:
            # Try "Section X of [Act Name]"
            sec_match = _SECTION_OF_PATTERN.match(cleaned)
            if sec_match:
                act_name = cleaned[sec_match.end():].strip()
            else:
                # Try "Article X of [Act Name]"
                art_match = _ARTICLE_OF_PATTERN.match(cleaned)
                if art_match:
                    act_name = cleaned[art_match.end():].strip()
                else:
                    # Try "Section 302 IPC" (section + short code)
                    short_match = _SECTION_SHORT_EXTRACT.match(cleaned)
                    if short_match:
                        act_name = short_match.group(1).strip()
                    else:
                        # No pattern match — use entire string
                        act_name = cleaned

        if not act_name:
            continue

        # Step 3: Strip trailing ", YYYY" year suffix before normalization
        act_name = re.sub(r",?\s*\d{4}\s*$", "", act_name).strip()
        if not act_name:
            continue

        # Step 4: Normalize via existing function
        normalized = normalize_act_name(act_name)

        # Step 4b: If the result is itself a long short-code that has a
        # shorter alias (e.g. "LIMITATION ACT" -> "LA"), prefer the shorter.
        if normalized.upper() in _SHORT_ACT_NAMES:
            full_name = _SHORT_ACT_NAMES[normalized.upper()]
            shorter = _FULL_TO_SHORT.get(full_name.lower())
            if shorter and len(shorter) < len(normalized):
                normalized = shorter

        # Step 5: Garbage filter
        if _is_valid_act_citation(normalized):
            result.add(normalized)

    # Step 6: Canonical dedup — collapse variant short codes
    # "CRPC", "CR.P.C.", "CrPC", "Cr.P.C." all map to same full name → pick canonical
    # Build upper-case lookup once (handles mixed-case keys like "Cr.P.C.")
    _upper_lookup: dict[str, str] = {k.upper(): v for k, v in _SHORT_ACT_NAMES.items()}
    canonical: set[str] = set()
    for entry in result:
        full_name = _upper_lookup.get(entry.upper())
        if full_name:
            canon = _FULL_TO_SHORT.get(full_name.lower(), entry)
            canonical.add(canon)
        else:
            canonical.add(entry)
    return sorted(canonical)


# Build alternation dynamically from dict keys -- longest first to avoid
# partial matches (e.g. "CGST ACT" before "CP ACT" before "CPC").
_SHORT_ACT_ALTERNATION: str = "|".join(
    re.escape(k).replace(r"\ ", r"\s+")
    for k in sorted(_SHORT_ACT_NAMES.keys(), key=len, reverse=True)
)

# "Section 302 of the Indian Penal Code, 1860"
# Act name boundary: stop at year, punctuation, or common non-act-name words.
# Allows "/" in act names (SC/ST Act) and matches known abbreviations (IBC, LARR).
_SECTION_FULL_ACT_PATTERN: re.Pattern[str] = re.compile(
    r"(?:Sections?|Sec\.?|Ss\.|S\.)\s*([\d\w]+(?:\s*\([^)]+\))*)"
    r"\s+of\s+(?:the\s+)?"
    r"([\w\s/]+?(?:Act|Code|Sanhita|Adhiniyam|Constitution|Rules|Regulations|Order|IBC|LARR|PMLA|UAPA|NDPS|POCSO|FEMA|RERA|SARFAESI|CGST|IGST))"
    r"(?:,\s*(\d{4}))?(?=\s*[.,;:)\]\"']|\s+(?:for|in|under|to|which|where|is|shall|was|has|and|read|r/w|that|as|if|or|provides?|requires?|causes?|bars?|grants?|allows?|permits?|prohibits?)\s|$)",
    re.IGNORECASE,
)

# "Section 302 IPC" / "Sections 302, 304 and 307 IPC" / "Sections 302-304 IPC"
# Captures comma/slash/and-separated section lists (including ranges) in group(1)
# A "section token" is a number/word optionally followed by parenthetical,
# optionally forming a range with - / – / "to".
_SEC_TOKEN = r"[\d\w]+(?:\s*\([^)]+\))*"
_SEC_RANGE = rf"{_SEC_TOKEN}(?:\s*[-–]\s*\d+|\s+to\s+\d+)?"
_SECTION_SHORT_ACT_PATTERN: re.Pattern[str] = re.compile(
    r"(?:Sections?|Sec\.?|Ss\.|S\.)\s*(" + _SEC_RANGE +
    r"(?:\s*[,/]\s*" + _SEC_RANGE + r")*"
    r"(?:\s+(?:and|&)\s+" + _SEC_RANGE + r")?)"
    r"\s+(" + _SHORT_ACT_ALTERNATION + r")",
    re.IGNORECASE,
)

# "Article 14/19/21 of the Constitution" — handles sub-clauses like 19(1)(a), 368A
# Also handles "Article 21 read with Article 14" via _ARTICLE_READ_WITH_PATTERN
_ARTICLE_PATTERN: re.Pattern[str] = re.compile(
    r"(?:Article|Art\.?)\s+([\d]+[A-Za-z]?(?:\s*\(\d+\))?(?:\s*\([a-z]\))?)"
    r"(\s+of\s+(?:the\s+)?Constitution)?",
    re.IGNORECASE,
)

# "Article 21 read with Article 14" / "Art. 19(1)(a) r/w Art. 21"
_ARTICLE_READ_WITH_PATTERN: re.Pattern[str] = re.compile(
    r"(?:Article|Art\.?)\s+([\d]+[A-Za-z]?(?:\s*\(\d+\))?(?:\s*\([a-z]\))?)"
    r"\s+(?:read\s+with|r/w|r\.w\.)\s+"
    r"(?:Article|Art\.?)\s+([\d]+[A-Za-z]?(?:\s*\(\d+\))?(?:\s*\([a-z]\))?)"
    r"(\s+of\s+(?:the\s+)?Constitution)?",
    re.IGNORECASE,
)

# "Section 302 read with Section 34 IPC" / "Section 302 r/w Section 34 IPC"
_READ_WITH_PATTERN: re.Pattern[str] = re.compile(
    r"(?:Sections?|Sec\.?|Ss\.|S\.)\s*([\d\w]+(?:\s*\([^)]+\))*)"
    r"\s+(?:read\s+with|r/w|r\.w\.)\s+"
    r"(?:Sections?|Sec\.?|Ss\.|S\.)?\s*([\d\w]+(?:\s*\([^)]+\))*)"
    r"\s+(" + _SHORT_ACT_ALTERNATION + r")",
    re.IGNORECASE,
)

# "Order 39 Rule 1 CPC"
_ORDER_RULE_PATTERN: re.Pattern[str] = re.compile(
    r"Order\s+(\w+)\s+Rule\s+(\d+)"
    r"(?:\s+(?:of\s+(?:the\s+)?)?"
    r"(?:CPC|Code\s+of\s+Civil\s+Procedure|Civil\s+Procedure\s+Code))?",
    re.IGNORECASE,
)

# "Regulation 3 of SEBI (LODR) Regulations, 2015" or "Regulation 3 of SEBI Act"
_REGULATION_PATTERN: re.Pattern[str] = re.compile(
    r"Regulations?\s+(\d+[A-Za-z]?(?:\s*\(\d+\))?(?:\s*\([a-z]\))?)"
    r"\s+(?:of\s+(?:the\s+)?)?"
    r"(" + _SHORT_ACT_ALTERNATION + r")"
    r"(?:\s+Regulations?)?(?:,?\s+\d{4})?",
    re.IGNORECASE,
)

# "Schedule I/II/III of the Act" or "First/Second/Third Schedule"
_SCHEDULE_PATTERN: re.Pattern[str] = re.compile(
    r"(?:(?:First|Second|Third|Fourth|Fifth|Sixth|Seventh|Eighth|Ninth|Tenth)"
    r"|(?:Schedule\s+(?:[IVX]+|\d+)))"
    r"(?:\s+Schedule)?"
    r"(?:\s+(?:of|to)\s+(?:the\s+)?"
    r"(" + _SHORT_ACT_ALTERNATION + r"(?:,?\s+\d{4})?))?",
    re.IGNORECASE,
)

# "Clause 49 of the Listing Agreement" / "Clause (a) of Section 10"
_CLAUSE_PATTERN: re.Pattern[str] = re.compile(
    r"Clause\s+(\d+[A-Za-z]?|\([a-z]\))"
    r"\s+(?:of\s+(?:the\s+)?)?"
    r"(" + _SHORT_ACT_ALTERNATION + r"(?:,?\s+\d{4})?)",
    re.IGNORECASE,
)

# "Form 26AS" / "Form No. 16"
_FORM_PATTERN: re.Pattern[str] = re.compile(
    r"Form\s+(?:No\.?\s+)?(\w+)"
    r"(?:\s+(?:of|under)\s+(?:the\s+)?"
    r"(" + _SHORT_ACT_ALTERNATION + r"(?:,?\s+\d{4})?))?",
    re.IGNORECASE,
)


def _parse_section_list(section_str: str) -> list[str]:
    """Parse '302, 304 and 307' into ['302', '304', '307'].

    Also expands ranges like '302-304' or '302 to 307'.
    Splits on commas, slashes, 'and', and '&' separators.
    """
    parts = re.split(r"[,/]\s*|\s+and\s+|\s+&\s+", section_str)
    result: list[str] = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        # Check for range: "302-304" or "302–304" (en-dash)
        range_match = re.match(r'^(\d+)\s*[-–]\s*(\d+)$', p)
        if not range_match:
            # Check for "302 to 307"
            range_match = re.match(r'^(\d+)\s+to\s+(\d+)$', p, re.IGNORECASE)
        if range_match:
            start, end = int(range_match.group(1)), int(range_match.group(2))
            if end > start and (end - start) <= 20:  # sanity limit
                result.extend(str(i) for i in range(start, end + 1))
                continue
        result.append(p)
    return result


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
    seen_spans: set[tuple[int, int]] = set()

    def _add(citation: Citation, match: re.Match | None = None) -> None:
        normalized = normalize_citation(citation.raw_text)
        if normalized not in seen_raw:
            seen_raw.add(normalized)
            citations.append(citation)
        if match is not None:
            seen_spans.add((match.start(), match.end()))

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
            confidence=0.9,
        ), match)

    # SCC -- (2020) 3 SCC 145 or [2020] 3 SCC 145
    for match in SCC_PATTERN.finditer(text):
        _add(Citation(
            reporter="SCC",
            year=int(match.group(1)),
            volume=match.group(2),
            page=match.group(3),
            court=None,
            raw_text=match.group(0),
            confidence=0.9,
        ), match)

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
            confidence=0.9,
        ), match)

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
            confidence=0.9,
        ), match)

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
            confidence=0.95,
        ), match)

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
            confidence=0.95,
        ), match)

    # INSC (space-delimited, legacy) -- 2020 INSC 145
    for match in INSC_PATTERN.finditer(text):
        _add(Citation(
            reporter="INSC",
            year=int(match.group(1)),
            volume=None,
            page=match.group(2),
            court="Supreme Court of India",
            raw_text=match.group(0),
            confidence=0.95,
        ), match)

    # SCR -- [2020] 3 SCR 145
    for match in SCR_PATTERN.finditer(text):
        _add(Citation(
            reporter="SCR",
            year=int(match.group(1)),
            volume=match.group(2),
            page=match.group(3),
            court=None,
            raw_text=match.group(0),
            confidence=0.9,
        ), match)

    # Bare SCR -- 3 SCR 150 (pre-1970, no year bracket)
    for match in SCR_BARE_PATTERN.finditer(text):
        m_start, m_end = match.start(), match.end()
        if any(not (m_end <= s_start or m_start >= s_end) for s_start, s_end in seen_spans):
            continue
        _add(Citation(
            reporter="SCR",
            year=None,
            volume=match.group(1),
            page=match.group(2),
            court=None,
            raw_text=match.group(0),
            confidence=0.7,
        ), match)

    # CrLJ -- 2020 CrLJ 145
    for match in CRLJ_PATTERN.finditer(text):
        _add(Citation(
            reporter="CrLJ",
            year=int(match.group(1)),
            volume=None,
            page=match.group(2),
            court=None,
            raw_text=match.group(0),
            confidence=0.8,
        ), match)

    # SCALE -- (2020) 3 SCALE 145
    for match in SCALE_PATTERN.finditer(text):
        _add(Citation(
            reporter="SCALE",
            year=int(match.group(1)),
            volume=match.group(2),
            page=match.group(3),
            court=None,
            raw_text=match.group(0),
            confidence=0.8,
        ), match)

    # MANU -- MANU/SC/1234/2020
    for match in MANU_PATTERN.finditer(text):
        _add(Citation(
            reporter="MANU",
            year=int(match.group(3)),
            volume=None,
            page=match.group(2),
            court=match.group(1),
            raw_text=match.group(0),
            confidence=0.8,
        ), match)

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
                confidence=0.8,
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
                confidence=0.8,
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
            confidence=0.8,
        ), match)

    # LiveLaw -- 2024 LiveLaw (SC) 123
    for match in LIVELAW_PATTERN.finditer(text):
        _add(Citation(
            reporter="LiveLaw",
            year=int(match.group(1)),
            volume=None,
            page=match.group(3),
            court=match.group(2),
            raw_text=match.group(0),
            confidence=0.8,
        ), match)

    # ITR -- [2020] 123 ITR 456
    for match in ITR_PATTERN.finditer(text):
        _add(Citation(
            reporter="ITR",
            year=int(match.group(1)),
            volume=match.group(2),
            page=match.group(3),
            court=None,
            raw_text=match.group(0),
            confidence=0.8,
        ), match)

    # Taxmann -- [2020] 123 taxmann.com 456
    for match in TAXMANN_PATTERN.finditer(text):
        _add(Citation(
            reporter="Taxmann",
            year=int(match.group(1)),
            volume=match.group(2),
            page=match.group(3),
            court=None,
            raw_text=match.group(0),
            confidence=0.8,
        ), match)

    # Company Cases -- (2020) 123 CompCas 456
    for match in COMP_CAS_PATTERN.finditer(text):
        _add(Citation(
            reporter="CompCas",
            year=int(match.group(1)),
            volume=match.group(2),
            page=match.group(3),
            court=None,
            raw_text=match.group(0),
            confidence=0.8,
        ), match)

    # LLJ -- 2020 LLJ 123
    for match in LLJ_PATTERN.finditer(text):
        _add(Citation(
            reporter="LLJ",
            year=int(match.group(1)),
            volume=None,
            page=match.group(2),
            court=None,
            raw_text=match.group(0),
            confidence=0.8,
        ), match)

    # Name-based citations -- "in Kesavananda Bharati v. State of Kerala"
    for match in NAME_CITATION_PATTERN.finditer(text):
        petitioner_name = match.group(1).strip().rstrip(".")
        respondent_name = match.group(2).strip().rstrip(".")
        case_name = f"{petitioner_name} v. {respondent_name}"
        _add(Citation(
            reporter="NameCitation",
            year=0,  # Unknown from name alone
            volume=None,
            page="0",
            court=None,
            raw_text=case_name,
            confidence=0.3,
        ), match)

    # --- Catch-all for unknown reporters --- runs LAST, skips known spans ---
    catch_all_count = 0
    for match in GENERIC_REPORTER_PATTERN.finditer(text):
        if catch_all_count >= 10:
            break
        # Skip if this span overlaps any already-matched span
        m_start, m_end = match.start(), match.end()
        if any(
            not (m_end <= s_start or m_start >= s_end)
            for s_start, s_end in seen_spans
        ):
            continue
        year = match.group(1) or match.group(2)
        reporter_name = match.group(3)
        if reporter_name.upper() in _CATCH_ALL_STOPWORDS:
            continue
        _add(Citation(
            reporter="Unknown",
            year=int(year),
            volume=None,
            page=match.group(4),
            court=None,
            raw_text=match.group(0),
            confidence=0.2,
        ), match)
        catch_all_count += 1

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
        # Semantic dedup: same act+section is only emitted once regardless
        # of differing raw_text (e.g. "Section 302 IPC" vs "S. 302 IPC").
        key = f"{ref.act_name}|{ref.section}"
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

    # Read with: "Section 302 read with Section 34 IPC"
    for match in _READ_WITH_PATTERN.finditer(text):
        section1 = match.group(1).strip()
        section2 = match.group(2).strip()
        short_code = re.sub(r"\s+", " ", match.group(3).strip()).upper()
        act_name = _SHORT_ACT_NAMES.get(short_code, short_code)
        raw = match.group(0).strip()
        _add(ActReference(act_name=act_name, section=section1, year=None, raw_text=raw))
        _add(ActReference(act_name=act_name, section=section2, year=None, raw_text=raw))

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

    # Article "read with" references: "Article 21 read with Article 14"
    for match in _ARTICLE_READ_WITH_PATTERN.finditer(text):
        article1 = match.group(1).strip()
        article2 = match.group(2).strip()
        has_constitution = match.group(3) is not None
        act_name = "Constitution of India"
        year = 1950
        raw = match.group(0).strip()
        _add(ActReference(act_name=act_name, section=f"Article {article1}", year=year, raw_text=raw))
        _add(ActReference(act_name=act_name, section=f"Article {article2}", year=year, raw_text=raw))

    # Article references: "Article 21 of the Constitution"
    for match in _ARTICLE_PATTERN.finditer(text):
        article = match.group(1).strip()
        has_constitution = match.group(2) is not None
        # In Indian legal context, bare "Article N" for N <= 395 means Constitution
        article_num = None
        try:
            num_match = re.match(r'(\d+)', article)
            article_num = int(num_match.group(1)) if num_match else None
        except (ValueError, AttributeError):
            pass

        if has_constitution or (article_num is not None and 1 <= article_num <= 395):
            act_name = "Constitution of India"
            year = 1950
        else:
            act_name = "Unknown Act"
            year = None

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

    # Regulation references: "Regulation 3 of SEBI (LODR) Regulations"
    for match in _REGULATION_PATTERN.finditer(text):
        reg_num = match.group(1).strip()
        act_raw = match.group(2).strip()
        short_code = re.sub(r"\s+", " ", act_raw).upper()
        # Strip trailing ", YYYY" and "REGULATIONS"
        short_code = re.sub(r",?\s*\d{4}\s*$", "", short_code).strip()
        short_code = re.sub(r"\s+REGULATIONS?\s*$", "", short_code).strip()
        act_name = _SHORT_ACT_NAMES.get(short_code, act_raw)
        _add(ActReference(
            act_name=act_name,
            section=f"Regulation {reg_num}",
            year=None,
            raw_text=match.group(0).strip(),
        ))

    # Clause references: "Clause 49 of the Listing Agreement"
    for match in _CLAUSE_PATTERN.finditer(text):
        clause_num = match.group(1).strip()
        act_raw = match.group(2).strip()
        short_code = re.sub(r"\s+", " ", act_raw).upper()
        short_code = re.sub(r",?\s*\d{4}\s*$", "", short_code).strip()
        act_name = _SHORT_ACT_NAMES.get(short_code, act_raw)
        _add(ActReference(
            act_name=act_name,
            section=f"Clause {clause_num}",
            year=None,
            raw_text=match.group(0).strip(),
        ))

    return references


def normalize_citation(citation: str) -> str:
    """Normalize a citation string to a canonical format.

    Performs structural canonicalization:
    1. Collapse whitespace
    2. Standardize reporter abbreviations (CrLJ, AIR, SCC OnLine)
    3. Standardize bracket styles ([] -> () for SCC)
    4. Normalize neutral citation separators (colon-delimited)
    5. Standardize MANU path separators
    6. Remove trailing periods and punctuation from citations
    7. Normalize "v." / "vs." / "versus" in party name citations

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

    # Standardize neutral citation separators: spaces around colons
    # "2023 : INSC : 1234" -> "2023:INSC:1234"
    normalized = re.sub(r"(\d{4})\s*:\s*(\w+)\s*:\s*(\d+)", r"\1:\2:\3", normalized)

    # Normalize MANU path separators: "MANU / SC / 1234 / 2020" -> "MANU/SC/1234/2020"
    normalized = re.sub(r"MANU\s*/\s*(\w+)\s*/\s*(\d+)\s*/\s*(\d{4})", r"MANU/\1/\2/\3", normalized)

    # Normalize "vs." / "versus" -> "v." in party name citations
    normalized = re.sub(r"\bvs\.?\b", "v.", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\bversus\b", "v.", normalized, flags=re.IGNORECASE)

    # Remove trailing period that isn't part of an abbreviation
    normalized = re.sub(r"(\d)\.\s*$", r"\1", normalized)

    # Normalize ITR/Taxmann bracket style: [2020] -> (2020)
    normalized = re.sub(
        r"\[(\d{4})\](\s+\d+\s+(?:ITR|taxmann\.com)\s+)",
        r"(\1)\2",
        normalized,
        flags=re.IGNORECASE,
    )

    return normalized
