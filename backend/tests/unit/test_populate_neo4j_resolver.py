"""Tests for the party-name fallback in scripts/populate_neo4j.py."""

import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "populate_neo4j", Path(__file__).resolve().parents[2] / "scripts" / "populate_neo4j.py"
)
populate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(populate)


def _index():
    idx = populate.PartyIndex()
    idx.add("a1", "NAGINDAS RAMDAS versus DALPATRAM ICHHARAM & ORS.", 1974)
    idx.add("b1", "STATE OF MAHARASHTRA versus RAMESH KUMAR", 2001)
    idx.add("b2", "STATE OF MAHARASHTRA versus RAMESH KUMAR SHARMA", 2010)
    idx.add("c1", "M/S KAMLA DEVI versus THAKHRATMAL LAND PVT. LTD.", 1964)
    return idx


def test_resolves_v_citation_to_versus_title():
    idx = _index()
    assert idx.resolve("Nagindas Ramdas v. Dalpatram Ichharam and Ors. (1974) 1 SCC 242") == "a1"
    assert idx.resolve("Kamla Devi v. Thakhratmal Land AIR 1964 SC 859") == "c1"


def test_rejects_ambiguous_matches_and_wrong_years():
    idx = _index()
    # Both "RAMESH KUMAR" titles contain the cited name; the year picks one.
    assert idx.resolve("State of Maharashtra v. Ramesh Kumar (2001) 3 SCC 1") == "b1"
    # Without a year both match, so no edge.
    assert idx.resolve("State of Maharashtra v. Ramesh Kumar") is None
    # Year too far from the case's.
    assert idx.resolve("Nagindas Ramdas v. Dalpatram Ichharam (1990) 2 SCC 10") is None


def test_ignores_entries_without_two_parties():
    idx = _index()
    assert idx.resolve("(1932) 1 KB 254") is None
    assert idx.resolve("AIR 1964 SC 859") is None
