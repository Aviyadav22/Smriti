"""Court-specific formatting profiles for legal document export (DOCX/PDF).

Each profile encodes the margins, fonts, spacing, paper size and other
formatting rules required by a particular Indian court.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CourtProfile:
    """Immutable formatting specification for a single court."""

    court_id: str
    display_name: str
    paper_size: str  # "A4" or "legal"
    font_name: str  # Always "Times New Roman"
    font_size_body: int
    font_size_heading: int
    font_size_quote: int
    line_spacing: float
    margin_top_cm: float
    margin_bottom_cm: float
    margin_left_cm: float
    margin_right_cm: float
    header_format: str
    requires_synopsis: bool
    requires_affidavit: bool
    numbering_style: str  # "arabic" or "roman"
    print_both_sides: bool


# ---------------------------------------------------------------------------
# Court profiles
# ---------------------------------------------------------------------------

COURT_PROFILES: dict[str, CourtProfile] = {
    "supreme_court": CourtProfile(
        court_id="supreme_court",
        display_name="Supreme Court of India",
        paper_size="A4",
        font_name="Times New Roman",
        font_size_body=14,
        font_size_heading=16,
        font_size_quote=12,
        line_spacing=1.5,
        margin_top_cm=2.0,
        margin_bottom_cm=2.0,
        margin_left_cm=4.0,
        margin_right_cm=4.0,
        header_format="IN THE HON'BLE SUPREME COURT OF INDIA",
        requires_synopsis=True,
        requires_affidavit=True,
        numbering_style="arabic",
        print_both_sides=True,
    ),
    "delhi_hc": CourtProfile(
        court_id="delhi_hc",
        display_name="High Court of Delhi",
        paper_size="A4",
        font_name="Times New Roman",
        font_size_body=14,
        font_size_heading=14,
        font_size_quote=11,
        line_spacing=2.0,
        margin_top_cm=2.54,
        margin_bottom_cm=1.91,
        margin_left_cm=3.18,
        margin_right_cm=3.18,
        header_format="IN THE HIGH COURT OF DELHI AT NEW DELHI",
        requires_synopsis=False,
        requires_affidavit=True,
        numbering_style="arabic",
        print_both_sides=False,
    ),
    "bombay_hc": CourtProfile(
        court_id="bombay_hc",
        display_name="High Court of Bombay",
        paper_size="legal",
        font_name="Times New Roman",
        font_size_body=12,
        font_size_heading=14,
        font_size_quote=11,
        line_spacing=1.5,
        margin_top_cm=2.54,
        margin_bottom_cm=2.54,
        margin_left_cm=3.81,
        margin_right_cm=2.54,
        header_format="IN THE HIGH COURT OF JUDICATURE AT BOMBAY",
        requires_synopsis=False,
        requires_affidavit=True,
        numbering_style="arabic",
        print_both_sides=False,
    ),
    "madras_hc": CourtProfile(
        court_id="madras_hc",
        display_name="High Court of Madras",
        paper_size="A4",
        font_name="Times New Roman",
        font_size_body=12,
        font_size_heading=14,
        font_size_quote=11,
        line_spacing=1.5,
        margin_top_cm=2.54,
        margin_bottom_cm=2.54,
        margin_left_cm=2.54,
        margin_right_cm=2.54,
        header_format="IN THE HIGH COURT OF JUDICATURE AT MADRAS",
        requires_synopsis=False,
        requires_affidavit=True,
        numbering_style="arabic",
        print_both_sides=False,
    ),
    "karnataka_hc": CourtProfile(
        court_id="karnataka_hc",
        display_name="High Court of Karnataka",
        paper_size="A4",
        font_name="Times New Roman",
        font_size_body=12,
        font_size_heading=14,
        font_size_quote=11,
        line_spacing=1.5,
        margin_top_cm=2.54,
        margin_bottom_cm=2.54,
        margin_left_cm=2.54,
        margin_right_cm=2.54,
        header_format="IN THE HIGH COURT OF KARNATAKA AT BENGALURU",
        requires_synopsis=False,
        requires_affidavit=True,
        numbering_style="arabic",
        print_both_sides=False,
    ),
    "calcutta_hc": CourtProfile(
        court_id="calcutta_hc",
        display_name="High Court at Calcutta",
        paper_size="A4",
        font_name="Times New Roman",
        font_size_body=12,
        font_size_heading=14,
        font_size_quote=11,
        line_spacing=1.5,
        margin_top_cm=2.54,
        margin_bottom_cm=2.54,
        margin_left_cm=2.54,
        margin_right_cm=2.54,
        header_format="IN THE HIGH COURT AT CALCUTTA",
        requires_synopsis=False,
        requires_affidavit=True,
        numbering_style="arabic",
        print_both_sides=False,
    ),
    "nclt": CourtProfile(
        court_id="nclt",
        display_name="National Company Law Tribunal",
        paper_size="A4",
        font_name="Times New Roman",
        font_size_body=12,
        font_size_heading=14,
        font_size_quote=11,
        line_spacing=1.5,
        margin_top_cm=2.54,
        margin_bottom_cm=2.54,
        margin_left_cm=2.54,
        margin_right_cm=2.54,
        header_format="BEFORE THE NATIONAL COMPANY LAW TRIBUNAL, {bench} BENCH",
        requires_synopsis=False,
        requires_affidavit=True,
        numbering_style="arabic",
        print_both_sides=False,
    ),
    "default": CourtProfile(
        court_id="default",
        display_name="Default Court",
        paper_size="A4",
        font_name="Times New Roman",
        font_size_body=12,
        font_size_heading=14,
        font_size_quote=11,
        line_spacing=1.5,
        margin_top_cm=2.54,
        margin_bottom_cm=2.54,
        margin_left_cm=2.54,
        margin_right_cm=2.54,
        header_format="IN THE COURT OF {court}",
        requires_synopsis=False,
        requires_affidavit=True,
        numbering_style="arabic",
        print_both_sides=False,
    ),
}

# ---------------------------------------------------------------------------
# Alias map  (lower-cased at lookup time)
# ---------------------------------------------------------------------------

_COURT_ALIASES: dict[str, str] = {
    "supreme court": "supreme_court",
    "sc": "supreme_court",
    "sci": "supreme_court",
    "delhi high court": "delhi_hc",
    "delhi hc": "delhi_hc",
    "dhc": "delhi_hc",
    "bombay high court": "bombay_hc",
    "bombay hc": "bombay_hc",
    "bhc": "bombay_hc",
    "mumbai high court": "bombay_hc",
    "madras high court": "madras_hc",
    "madras hc": "madras_hc",
    "mhc": "madras_hc",
    "chennai high court": "madras_hc",
    "karnataka high court": "karnataka_hc",
    "karnataka hc": "karnataka_hc",
    "khc": "karnataka_hc",
    "bangalore high court": "karnataka_hc",
    "bengaluru high court": "karnataka_hc",
    "calcutta high court": "calcutta_hc",
    "calcutta hc": "calcutta_hc",
    "chc": "calcutta_hc",
    "kolkata high court": "calcutta_hc",
    "nclt": "nclt",
    "nclat": "nclt",
    "national company law tribunal": "nclt",
}


def get_court_profile(court_name: str) -> CourtProfile:
    """Return the formatting profile for *court_name*.

    Lookup order:
    1. Exact match against ``COURT_PROFILES`` keys.
    2. Case-insensitive match against ``_COURT_ALIASES``.
    3. Falls back to the ``"default"`` profile.
    """
    if not court_name:
        return COURT_PROFILES["default"]

    # Exact key match
    if court_name in COURT_PROFILES:
        return COURT_PROFILES[court_name]

    # Alias lookup (case-insensitive)
    alias_key = court_name.strip().lower()
    court_id = _COURT_ALIASES.get(alias_key)
    if court_id is not None:
        return COURT_PROFILES[court_id]

    return COURT_PROFILES["default"]
