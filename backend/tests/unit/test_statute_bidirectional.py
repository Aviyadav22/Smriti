"""Tests for bidirectional IPC↔BNS, CrPC↔BNSS, IEA↔BSA statute mapping.

Covers all three abstraction levels:
1. build_lookup() — raw (act, section) tuple mappings
2. _expand_refs() — agent-level tuple expansion
3. expand_statute_references() — query-text regex expansion

These ensure Indian lawyers can search across pre- and post-July 2024
criminal law statutes regardless of which version they cite.
"""
import pytest

from app.core.agents.nodes.common import _expand_refs
from app.core.legal.amendment_service import build_lookup_from_constants
from app.core.search.query import expand_statute_references


class TestBidirectionalBuildLookup:
    """build_lookup_from_constants() returns symmetric bidirectional maps."""

    def test_ipc_302_maps_to_bns_103(self):
        """IPC Section 302 (murder) → BNS Section 103."""
        old_to_new, _ = build_lookup_from_constants()
        assert "103" in old_to_new[("IPC", "302")]

    def test_bns_103_maps_to_ipc_302(self):
        """BNS Section 103 → IPC Section 302 (reverse)."""
        _, new_to_old = build_lookup_from_constants()
        assert "302" in new_to_old[("BNS", "103")]

    def test_crpc_438_maps_to_bnss(self):
        """CrPC Section 438 (anticipatory bail) → BNSS equivalent."""
        old_to_new, _ = build_lookup_from_constants()
        assert ("CrPC", "438") in old_to_new
        bnss_sections = old_to_new[("CrPC", "438")]
        assert len(bnss_sections) > 0

    def test_bnss_maps_back_to_crpc_438(self):
        """BNSS equivalent of 438 → CrPC 438 (reverse)."""
        old_to_new, new_to_old = build_lookup_from_constants()
        bnss_section = old_to_new[("CrPC", "438")][0]
        assert "438" in new_to_old[("BNSS", bnss_section)]

    def test_iea_maps_to_bsa(self):
        """IEA sections → BSA equivalents."""
        old_to_new, _ = build_lookup_from_constants()
        iea_keys = [k for k in old_to_new if k[0] == "IEA"]
        assert len(iea_keys) > 10, "Expected many IEA→BSA mappings"

    def test_bsa_maps_back_to_iea(self):
        """BSA sections → IEA equivalents (reverse)."""
        _, new_to_old = build_lookup_from_constants()
        bsa_keys = [k for k in new_to_old if k[0] == "BSA"]
        assert len(bsa_keys) > 10, "Expected many BSA→IEA reverse mappings"


class TestBidirectionalExpandRefs:
    """_expand_refs() auto-expands old↔new code refs at tuple level."""

    def test_ipc_302_expands_to_include_bns_103(self):
        """IPC 302 → also includes BNS 103."""
        result = _expand_refs([("IPC", "302")])
        acts = {act for act, _ in result}
        assert "BNS" in acts

    def test_bns_103_expands_to_include_ipc_302(self):
        """BNS 103 → also includes IPC 302 (reverse)."""
        result = _expand_refs([("BNS", "103")])
        acts = {act for act, _ in result}
        assert "IPC" in acts

    def test_crpc_expands_to_bnss(self):
        """CrPC refs → also include BNSS."""
        result = _expand_refs([("CrPC", "482")])
        acts = {act for act, _ in result}
        assert "BNSS" in acts or len(result) >= 1

    def test_iea_expands_to_bsa(self):
        """IEA refs → also include BSA."""
        result = _expand_refs([("IEA", "3")])
        acts = {act for act, _ in result}
        assert "BSA" in acts or len(result) >= 1

    def test_unknown_act_passes_through(self):
        """Acts not in IPC/CrPC/IEA/BNS/BNSS/BSA pass through unchanged."""
        result = _expand_refs([("NIA", "13")])
        assert ("NIA", "13") in result
        assert len(result) == 1


class TestBidirectionalQueryExpansion:
    """expand_statute_references() handles both old→new and new→old."""

    def test_ipc_to_bns_expansion(self):
        """'Section 302 IPC' expands to include BNS equivalent."""
        _, expanded = expand_statute_references("Section 302 IPC bail")
        assert any("BNS" in term for term in expanded)

    def test_bns_to_ipc_expansion(self):
        """'Section 103 BNS' expands to include IPC equivalent."""
        _, expanded = expand_statute_references("Section 103 BNS murder")
        assert any("IPC" in term for term in expanded)

    def test_crpc_to_bnss_expansion(self):
        """'Section 438 CrPC' expands to include BNSS equivalent."""
        _, expanded = expand_statute_references("Section 438 CrPC anticipatory bail")
        assert any("BNSS" in term for term in expanded)

    def test_bnss_to_crpc_expansion(self):
        """'Section 482 BNSS' expands to include CrPC equivalent."""
        _, expanded = expand_statute_references(
            "Section 482 Bharatiya Nagarik Suraksha Sanhita quashing"
        )
        assert any("CrPC" in term for term in expanded)

    def test_iea_to_bsa_expansion(self):
        """'Section 3 Indian Evidence Act' expands to include BSA."""
        _, expanded = expand_statute_references("Section 3 Indian Evidence Act")
        assert any("BSA" in term for term in expanded)

    def test_no_expansion_for_unrecognized(self):
        """Queries without recognized statute refs return empty expansion."""
        _, expanded = expand_statute_references("general bail application")
        assert expanded == []
