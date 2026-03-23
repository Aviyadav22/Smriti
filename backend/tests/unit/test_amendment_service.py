"""Tests for amendment_service: build_lookup() and build_lookup_from_constants().

Verifies that the bidirectional old↔new statute section mapping works correctly
for IPC↔BNS, CrPC↔BNSS, IEA↔BSA — critical for Indian legal research where
lawyers search across pre- and post-July 2024 criminal law statutes.
"""
import pytest

from app.core.legal.amendment_service import (
    AmendmentEntry,
    build_lookup,
    build_lookup_from_constants,
)


class TestBuildLookup:
    """Tests for build_lookup() — bidirectional mapping from AmendmentEntry list."""

    def test_empty_entries(self):
        """Empty input returns empty dicts."""
        old_to_new, new_to_old = build_lookup([])
        assert old_to_new == {}
        assert new_to_old == {}

    def test_single_entry(self):
        """Single amendment entry creates forward and reverse mappings."""
        entries: list[AmendmentEntry] = [
            AmendmentEntry(
                old_act="IPC",
                new_act="BNS",
                old_section="302",
                new_section="103",
                effective_date="2024-07-01",
                notes=None,
            )
        ]
        old_to_new, new_to_old = build_lookup(entries)
        assert old_to_new[("IPC", "302")] == ["103"]
        assert new_to_old[("BNS", "103")] == ["302"]

    def test_multiple_entries_same_act(self):
        """Multiple sections of same act are mapped independently."""
        entries: list[AmendmentEntry] = [
            AmendmentEntry(
                old_act="IPC", new_act="BNS", old_section="302", new_section="103",
                effective_date=None, notes=None,
            ),
            AmendmentEntry(
                old_act="IPC", new_act="BNS", old_section="307", new_section="109",
                effective_date=None, notes=None,
            ),
            AmendmentEntry(
                old_act="IPC", new_act="BNS", old_section="420", new_section="318",
                effective_date=None, notes=None,
            ),
        ]
        old_to_new, new_to_old = build_lookup(entries)

        assert old_to_new[("IPC", "302")] == ["103"]
        assert old_to_new[("IPC", "307")] == ["109"]
        assert old_to_new[("IPC", "420")] == ["318"]
        assert new_to_old[("BNS", "103")] == ["302"]
        assert new_to_old[("BNS", "109")] == ["307"]

    def test_cross_act_mappings(self):
        """Entries from different act pairs coexist correctly."""
        entries: list[AmendmentEntry] = [
            AmendmentEntry(
                old_act="IPC", new_act="BNS", old_section="302", new_section="103",
                effective_date=None, notes=None,
            ),
            AmendmentEntry(
                old_act="CrPC", new_act="BNSS", old_section="438", new_section="482",
                effective_date=None, notes=None,
            ),
            AmendmentEntry(
                old_act="IEA", new_act="BSA", old_section="3", new_section="3",
                effective_date=None, notes=None,
            ),
        ]
        old_to_new, new_to_old = build_lookup(entries)

        assert ("IPC", "302") in old_to_new
        assert ("CrPC", "438") in old_to_new
        assert ("IEA", "3") in old_to_new
        assert ("BNS", "103") in new_to_old
        assert ("BNSS", "482") in new_to_old
        assert ("BSA", "3") in new_to_old


class TestBuildLookupFromConstants:
    """Tests for build_lookup_from_constants() — wired in GAP-1."""

    def test_returns_non_empty_dicts(self):
        """Must return populated dicts from hardcoded constants."""
        old_to_new, new_to_old = build_lookup_from_constants()
        assert len(old_to_new) > 0
        assert len(new_to_old) > 0

    def test_ipc_302_to_bns_103(self):
        """IPC Section 302 (murder) maps to BNS Section 103."""
        old_to_new, _ = build_lookup_from_constants()
        assert "103" in old_to_new[("IPC", "302")]

    def test_bns_103_to_ipc_302(self):
        """BNS Section 103 reverse maps to IPC Section 302."""
        _, new_to_old = build_lookup_from_constants()
        assert "302" in new_to_old[("BNS", "103")]

    def test_crpc_438_to_bnss(self):
        """CrPC Section 438 (anticipatory bail) maps to BNSS equivalent."""
        old_to_new, _ = build_lookup_from_constants()
        assert ("CrPC", "438") in old_to_new

    def test_iea_to_bsa(self):
        """IEA sections map to BSA equivalents."""
        old_to_new, _ = build_lookup_from_constants()
        iea_keys = [k for k in old_to_new if k[0] == "IEA"]
        assert len(iea_keys) > 0, "Expected IEA→BSA mappings"

    def test_consistency_with_centralized_lookups(self):
        """build_lookup_from_constants matches query.py and common.py centralized dicts."""
        old_to_new, new_to_old = build_lookup_from_constants()

        # Import the centralized lookups wired in GAP-1
        from app.core.search.query import _CENTRALIZED_OLD_TO_NEW, _CENTRALIZED_NEW_TO_OLD
        from app.core.agents.nodes.common import _AMENDMENT_OLD_TO_NEW, _AMENDMENT_NEW_TO_OLD

        # All three should have the same data
        assert old_to_new == _CENTRALIZED_OLD_TO_NEW
        assert new_to_old == _CENTRALIZED_NEW_TO_OLD
        assert old_to_new == _AMENDMENT_OLD_TO_NEW
        assert new_to_old == _AMENDMENT_NEW_TO_OLD
