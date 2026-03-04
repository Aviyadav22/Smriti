"""Indian court hierarchy, name normalization, and AIR court code mappings.

Covers the Supreme Court, all 25 High Courts, district-level courts, and key
tribunals / specialized bodies.
"""

from typing import Final

# ---------------------------------------------------------------------------
# Short-name → canonical full name mapping
# ---------------------------------------------------------------------------

# Supreme Court
_SUPREME_COURT: Final[dict[str, str]] = {
    "SC": "Supreme Court of India",
    "SCI": "Supreme Court of India",
    "SupremeCourt": "Supreme Court of India",
    "INSC": "Supreme Court of India",
}

# 25 High Courts
_HIGH_COURTS: Final[dict[str, str]] = {
    # Allahabad
    "AllHC": "High Court of Allahabad",
    "AllahabadHC": "High Court of Allahabad",
    # Bombay
    "BomHC": "High Court of Bombay",
    "BombayHC": "High Court of Bombay",
    # Calcutta
    "CalHC": "High Court of Calcutta",
    "CalcuttaHC": "High Court of Calcutta",
    # Madras
    "MadHC": "High Court of Madras",
    "MadrasHC": "High Court of Madras",
    # Delhi
    "DelHC": "High Court of Delhi",
    "DelhiHC": "High Court of Delhi",
    # Karnataka
    "KarHC": "High Court of Karnataka",
    "KarnatakaHC": "High Court of Karnataka",
    # Kerala
    "KerHC": "High Court of Kerala",
    "KeralaHC": "High Court of Kerala",
    # Gujarat
    "GujHC": "High Court of Gujarat",
    "GujaratHC": "High Court of Gujarat",
    # Rajasthan
    "RajHC": "High Court of Rajasthan",
    "RajasthanHC": "High Court of Rajasthan",
    # Patna
    "PatHC": "High Court of Patna",
    "PatnaHC": "High Court of Patna",
    # Punjab & Haryana
    "P&HHC": "High Court of Punjab and Haryana",
    "PunjabHaryanaHC": "High Court of Punjab and Haryana",
    "PHHC": "High Court of Punjab and Haryana",
    # Andhra Pradesh
    "APHC": "High Court of Andhra Pradesh",
    "AndhraHC": "High Court of Andhra Pradesh",
    # Telangana
    "TelHC": "High Court of Telangana",
    "TelanganaHC": "High Court of Telangana",
    # Orissa (officially Odisha since 2011, but judiciary retains "Orissa")
    "OriHC": "High Court of Orissa",
    "OrissaHC": "High Court of Orissa",
    # Jharkhand
    "JharHC": "High Court of Jharkhand",
    "JharkhandHC": "High Court of Jharkhand",
    # Chhattisgarh
    "CGHC": "High Court of Chhattisgarh",
    "ChhattisgarhHC": "High Court of Chhattisgarh",
    # Uttarakhand
    "UttHC": "High Court of Uttarakhand",
    "UttarakhandHC": "High Court of Uttarakhand",
    # Himachal Pradesh
    "HPHC": "High Court of Himachal Pradesh",
    "HimachalHC": "High Court of Himachal Pradesh",
    # Jammu & Kashmir and Ladakh
    "JKHC": "High Court of Jammu & Kashmir and Ladakh",
    "JKLadakhHC": "High Court of Jammu & Kashmir and Ladakh",
    "JKLHC": "High Court of Jammu & Kashmir and Ladakh",
    # Gauhati
    "GauHC": "High Court of Gauhati",
    "GauhatiHC": "High Court of Gauhati",
    # Tripura
    "TriHC": "High Court of Tripura",
    "TripuraHC": "High Court of Tripura",
    # Meghalaya
    "MegHC": "High Court of Meghalaya",
    "MeghalayaHC": "High Court of Meghalaya",
    # Manipur
    "ManHC": "High Court of Manipur",
    "ManipurHC": "High Court of Manipur",
    # Sikkim
    "SikHC": "High Court of Sikkim",
    "SikkimHC": "High Court of Sikkim",
}

# Key tribunals & specialized bodies
_TRIBUNALS: Final[dict[str, str]] = {
    "NCLT": "National Company Law Tribunal",
    "NCLAT": "National Company Law Appellate Tribunal",
    "SAT": "Securities Appellate Tribunal",
    "CAT": "Central Administrative Tribunal",
    "ITAT": "Income Tax Appellate Tribunal",
    "CESTAT": "Customs, Excise and Service Tax Appellate Tribunal",
    "NGT": "National Green Tribunal",
    "TDSAT": "Telecom Disputes Settlement Appellate Tribunal",
    "AFT": "Armed Forces Tribunal",
    "NCDRC": "National Consumer Disputes Redressal Commission",
    "SCDRC": "State Consumer Disputes Redressal Commission",
    "DFC": "District Consumer Forum",
}

# Unified lookup — merge all dictionaries
COURT_NAME_MAP: Final[dict[str, str]] = {
    **_SUPREME_COURT,
    **_HIGH_COURTS,
    **_TRIBUNALS,
}

# ---------------------------------------------------------------------------
# AIR court code → canonical full name
# ---------------------------------------------------------------------------

AIR_COURT_CODES: Final[dict[str, str]] = {
    "SC": "Supreme Court of India",
    "All": "High Court of Allahabad",
    "Bom": "High Court of Bombay",
    "Cal": "High Court of Calcutta",
    "Del": "High Court of Delhi",
    "Mad": "High Court of Madras",
    "Kar": "High Court of Karnataka",
    "Ker": "High Court of Kerala",
    "Guj": "High Court of Gujarat",
    "Raj": "High Court of Rajasthan",
    "Pat": "High Court of Patna",
    "P&H": "High Court of Punjab and Haryana",
    "AP": "High Court of Andhra Pradesh",
    "Ori": "High Court of Orissa",
    "Jhar": "High Court of Jharkhand",
    "CG": "High Court of Chhattisgarh",
    "Utt": "High Court of Uttarakhand",
    "HP": "High Court of Himachal Pradesh",
    "J&K": "High Court of Jammu & Kashmir and Ladakh",
    "Gau": "High Court of Gauhati",
    "Tri": "High Court of Tripura",
    "Meg": "High Court of Meghalaya",
    "Man": "High Court of Manipur",
    "Sik": "High Court of Sikkim",
    "Tel": "High Court of Telangana",
}

# ---------------------------------------------------------------------------
# Reverse lookups — canonical name → court level
# ---------------------------------------------------------------------------

_COURT_LEVEL_MAP: Final[dict[str, str]] = {}

# Build programmatically to avoid repetition
for _name in _SUPREME_COURT.values():
    _COURT_LEVEL_MAP[_name] = "supreme"

for _name in _HIGH_COURTS.values():
    _COURT_LEVEL_MAP[_name] = "high"

for _name in _TRIBUNALS.values():
    _COURT_LEVEL_MAP[_name] = "tribunal"

# Also map the AIR code values (same canonical names, but ensures coverage)
for _name in AIR_COURT_CODES.values():
    if _name not in _COURT_LEVEL_MAP:
        if "Supreme" in _name:
            _COURT_LEVEL_MAP[_name] = "supreme"
        elif "High Court" in _name:
            _COURT_LEVEL_MAP[_name] = "high"

# District-level keywords for heuristic matching
_DISTRICT_KEYWORDS: Final[list[str]] = [
    "district",
    "sessions",
    "civil judge",
    "magistrate",
    "munsif",
    "small causes",
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def normalize_court_name(name: str) -> str:
    """Resolve a short name, AIR code, or alias to the canonical full name.

    Lookup order:
    1. Exact match in COURT_NAME_MAP (abbreviation → full name)
    2. Exact match in AIR_COURT_CODES
    3. Case-insensitive search across all maps
    4. Return the input unchanged if no match is found

    Args:
        name: Short name, abbreviation, or AIR court code.

    Returns:
        Canonical full court name, or the original string if unrecognized.
    """
    # 1. Direct lookup in abbreviation map
    if name in COURT_NAME_MAP:
        return COURT_NAME_MAP[name]

    # 2. Direct lookup in AIR codes
    if name in AIR_COURT_CODES:
        return AIR_COURT_CODES[name]

    # 3. Case-insensitive fallback across all maps
    name_lower = name.lower().strip()
    for key, value in COURT_NAME_MAP.items():
        if key.lower() == name_lower:
            return value
    for key, value in AIR_COURT_CODES.items():
        if key.lower() == name_lower:
            return value

    # 4. Check if input is already a canonical name
    if name in _COURT_LEVEL_MAP:
        return name

    return name


def get_court_level(court: str) -> str:
    """Determine the hierarchy level of a court.

    Args:
        court: Court name — may be a short code, AIR code, or full canonical
            name.

    Returns:
        One of ``"supreme"``, ``"high"``, ``"district"``, ``"tribunal"``, or
        ``"unknown"`` if the court cannot be classified.
    """
    # Normalize first so we work with canonical names
    canonical = normalize_court_name(court)

    # Direct lookup
    if canonical in _COURT_LEVEL_MAP:
        return _COURT_LEVEL_MAP[canonical]

    # Heuristic: check for district-level keywords
    canonical_lower = canonical.lower()
    for keyword in _DISTRICT_KEYWORDS:
        if keyword in canonical_lower:
            return "district"

    # Heuristic: common patterns
    if "high court" in canonical_lower:
        return "high"
    if "supreme court" in canonical_lower:
        return "supreme"
    if "tribunal" in canonical_lower or "commission" in canonical_lower:
        return "tribunal"

    return "unknown"
