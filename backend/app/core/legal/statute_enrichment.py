"""Ingestion-time statute cross-reference enrichment.

Adds bidirectional old-law <-> new-law references to acts_cited metadata
so that Pinecone filter queries find cases regardless of which statute
version was originally cited.
"""

from __future__ import annotations

import re

from app.core.legal.constants import (
    CRPC_TO_BNSS_MAP,
    EVIDENCE_TO_BSA_MAP,
    IPC_TO_BNS_MAP,
)

# Mapping: (old_name_patterns, old_full_name, new_full_name, forward_map)
_ENRICHMENT_RULES: list[tuple[list[str], str, str, dict[str, str]]] = [
    (
        ["Indian Penal Code", "IPC", "I.P.C."],
        "Indian Penal Code",
        "Bharatiya Nyaya Sanhita",
        IPC_TO_BNS_MAP,
    ),
    (
        ["Code of Criminal Procedure", "CrPC", "Cr.P.C."],
        "Code of Criminal Procedure",
        "Bharatiya Nagarik Suraksha Sanhita",
        CRPC_TO_BNSS_MAP,
    ),
    (
        ["Indian Evidence Act", "Evidence Act", "IEA"],
        "Indian Evidence Act",
        "Bharatiya Sakshya Adhiniyam",
        EVIDENCE_TO_BSA_MAP,
    ),
]

# Pre-compute reverse maps and new-name patterns
_REVERSE_RULES: list[tuple[list[str], str, str, dict[str, str]]] = []
for _old_patterns, _old_name, _new_name, _fwd_map in _ENRICHMENT_RULES:
    _rev_map = {v: k for k, v in _fwd_map.items()}
    _REVERSE_RULES.append(([_new_name], _new_name, _old_name, _rev_map))

# Section extraction regex: "Section 302", "Section 65B", "Section 3(5)"
_SECTION_RE = re.compile(r"Section\s+([\w()]+)", re.IGNORECASE)


def enrich_statute_cross_references(acts_cited: list[str]) -> list[str]:
    """Add cross-references for old<->new criminal statutes.

    For each IPC/CrPC/IEA reference with a section number, adds the
    corresponding BNS/BNSS/BSA equivalent and vice versa.

    Args:
        acts_cited: List of act reference strings from metadata.

    Returns:
        Deduplicated, sorted list with both old and new statute references.
    """
    if not acts_cited:
        return []

    enriched: set[str] = set(acts_cited)

    for entry in acts_cited:
        entry_upper = entry.upper()

        # Try forward rules (old -> new)
        for name_patterns, _old_name, new_name, fwd_map in _ENRICHMENT_RULES:
            if any(p.upper() in entry_upper for p in name_patterns):
                section_match = _SECTION_RE.search(entry)
                if section_match:
                    section = section_match.group(1)
                    mapped = fwd_map.get(section) or fwd_map.get(section.upper())
                    if mapped:
                        enriched.add(f"{new_name}, Section {mapped}")
                break

        # Try reverse rules (new -> old)
        for name_patterns, _new_name, old_name, rev_map in _REVERSE_RULES:
            if any(p.upper() in entry_upper for p in name_patterns):
                section_match = _SECTION_RE.search(entry)
                if section_match:
                    section = section_match.group(1)
                    mapped = rev_map.get(section) or rev_map.get(section.upper())
                    if mapped:
                        enriched.add(f"{old_name}, Section {mapped}")
                break

    return sorted(enriched)
