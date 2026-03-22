"""Ingestion-time statute cross-reference enrichment.

Adds bidirectional old-law <-> new-law references to acts_cited metadata
so that Pinecone filter queries find cases regardless of which statute
version was originally cited.

Works with canonical short codes (IPC, BNS, CrPC, BNSS, IEA, BSA) as
produced by normalize_acts_cited_list().
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Act-level equivalence map (short code <-> short code)
# ---------------------------------------------------------------------------
_ACT_CODE_EQUIVALENTS: dict[str, str] = {
    "IPC": "BNS",
    "BNS": "IPC",
    "CrPC": "BNSS",
    "BNSS": "CrPC",
    "CRPC": "BNSS",  # uppercase variant used by normalize_acts_cited_list
    "IEA": "BSA",
    "BSA": "IEA",
}


def enrich_statute_cross_references(acts_cited: list[str]) -> list[str]:
    """Add act-level cross-references for old<->new criminal statutes.

    For each recognized short code (IPC, CrPC, IEA, BNS, BNSS, BSA),
    adds the equivalent old/new statute short code so that search filters
    match regardless of which version was originally cited.

    Examples:
        ["IPC", "CrPC"] -> ["BNS", "BNSS", "CrPC", "IPC"]
        ["BNS"]         -> ["BNS", "IPC"]
        ["IPC", "ACA"]  -> ["ACA", "BNS", "IPC"]

    Args:
        acts_cited: List of canonical act short codes from metadata.

    Returns:
        Deduplicated, sorted list with both old and new statute codes.
    """
    if not acts_cited:
        return []

    enriched: set[str] = set(acts_cited)

    for code in acts_cited:
        equivalent = _ACT_CODE_EQUIVALENTS.get(code)
        if equivalent:
            enriched.add(equivalent)

    return sorted(enriched)
