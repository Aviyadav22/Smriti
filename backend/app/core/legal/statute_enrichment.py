"""Ingestion-time statute cross-reference enrichment.

Adds bidirectional old-law <-> new-law references to acts_cited metadata
so that Pinecone filter queries find cases regardless of which statute
version was originally cited.

Works with canonical short codes (IPC, BNS, CRPC, BNSS, IEA, BSA) as
produced by normalize_acts_cited_list().

Temporal guard (BNS/BNSS/BSA effective July 2024):
- Pre-2024 cases: new codes are replaced with old equivalents; no new codes added.
- Post-2024 / unknown year: bidirectional enrichment (backward compatible).
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Act-level equivalence map (short code <-> short code)
# ---------------------------------------------------------------------------
_ACT_CODE_EQUIVALENTS: dict[str, str] = {
    "IPC": "BNS",
    "BNS": "IPC",
    "CrPC": "BNSS",
    "BNSS": "CRPC",
    "CRPC": "BNSS",
    "IEA": "BSA",
    "BSA": "IEA",
}

# New criminal codes (effective 1 July 2024)
_NEW_CODES: set[str] = {"BNS", "BNSS", "BSA"}

# Old criminal codes they replaced
_OLD_CODES: set[str] = {"IPC", "CrPC", "CRPC", "IEA"}

# Map from new code -> canonical old equivalent (for pre-2024 replacement)
_NEW_TO_OLD: dict[str, str] = {
    "BNS": "IPC",
    "BNSS": "CRPC",
    "BSA": "IEA",
}


def enrich_statute_cross_references(
    acts_cited: list[str],
    *,
    decision_year: int | None = None,
) -> list[str]:
    """Add act-level cross-references for old<->new criminal statutes.

    For each recognized short code (IPC, CrPC, IEA, BNS, BNSS, BSA),
    adds the equivalent old/new statute short code so that search filters
    match regardless of which version was originally cited.

    Temporal guard:
        - ``decision_year < 2024``: new codes (BNS/BNSS/BSA) in the input
          are replaced with their old equivalents, and no new codes are added.
        - ``decision_year >= 2024`` or ``None``: bidirectional enrichment
          (backward compatible).

    Examples:
        # No year / post-2024 — bidirectional
        ["IPC", "CRPC"] -> ["BNS", "BNSS", "CRPC", "IPC"]
        ["BNS"]         -> ["BNS", "IPC"]

        # Pre-2024 — old codes only
        ["IPC"], year=2020         -> ["IPC"]
        ["BNS", "IPC"], year=2020  -> ["IPC"]

    Args:
        acts_cited: List of canonical act short codes from metadata.
        decision_year: Year the judgment was decided. When provided and
            < 2024, new codes are suppressed.

    Returns:
        Deduplicated, sorted list of act short codes.
    """
    if not acts_cited:
        return []

    pre_2024 = decision_year is not None and decision_year < 2024

    if pre_2024:
        # Replace any new codes with their old equivalents, then skip
        # adding any new-code cross-references.
        enriched: set[str] = set()
        for code in acts_cited:
            if code in _NEW_CODES:
                enriched.add(_NEW_TO_OLD[code])
            else:
                enriched.add(code)
        # No cross-reference enrichment for old->new in pre-2024 cases
        return sorted(enriched)

    # Post-2024 or unknown year: bidirectional enrichment
    enriched = set(acts_cited)

    for code in acts_cited:
        equivalent = _ACT_CODE_EQUIVALENTS.get(code)
        if equivalent:
            enriched.add(equivalent)

    return sorted(enriched)
