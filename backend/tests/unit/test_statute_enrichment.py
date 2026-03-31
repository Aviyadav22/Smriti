"""Tests for ingestion-time statute cross-reference enrichment.

Now tests act-level short-code enrichment (post-normalization),
including the BNS/BNSS/BSA temporal guard for pre-2024 cases.
"""

import pytest

from app.core.legal.statute_enrichment import enrich_statute_cross_references


class TestEnrichStatuteCrossReferences:
    """Test bidirectional IPC<->BNS, CRPC<->BNSS, IEA<->BSA enrichment."""

    def test_enrich_adds_bns_for_ipc(self):
        result = enrich_statute_cross_references(["IPC"])
        assert "BNS" in result
        assert "IPC" in result

    def test_enrich_adds_ipc_for_bns(self):
        result = enrich_statute_cross_references(["BNS"])
        assert "IPC" in result
        assert "BNS" in result

    def test_enrich_bidirectional_crpc(self):
        result = enrich_statute_cross_references(["CRPC"])
        assert "BNSS" in result
        assert "CRPC" in result

    def test_enrich_bidirectional_crpc_reverse(self):
        result = enrich_statute_cross_references(["BNSS"])
        assert "CRPC" in result
        assert "BNSS" in result

    def test_enrich_bidirectional_crpc_legacy_input(self):
        """CrPC input (legacy) still gets enriched."""
        result = enrich_statute_cross_references(["CrPC"])
        assert "BNSS" in result
        assert "CrPC" in result

    def test_enrich_bidirectional_iea(self):
        result = enrich_statute_cross_references(["IEA"])
        assert "BSA" in result
        assert "IEA" in result

    def test_enrich_bidirectional_iea_reverse(self):
        result = enrich_statute_cross_references(["BSA"])
        assert "IEA" in result
        assert "BSA" in result

    def test_enrich_no_duplicates(self):
        result = enrich_statute_cross_references(["IPC", "BNS"])
        assert result == ["BNS", "IPC"]
        assert len(result) == len(set(result))

    def test_enrich_preserves_other_acts(self):
        result = enrich_statute_cross_references(["IPC", "ACA"])
        assert result == ["ACA", "BNS", "IPC"]

    def test_enrich_empty_list(self):
        assert enrich_statute_cross_references([]) == []

    def test_enrich_multiple_old_codes(self):
        result = enrich_statute_cross_references(["IPC", "CRPC"])
        assert "BNS" in result
        assert "BNSS" in result
        assert "IPC" in result
        assert "CRPC" in result

    def test_enrich_multiple_new_codes(self):
        result = enrich_statute_cross_references(["BNS", "BNSS"])
        assert "IPC" in result
        assert "CRPC" in result

    def test_non_criminal_acts_unchanged(self):
        acts = ["COI", "ACA", "MVA"]
        result = enrich_statute_cross_references(acts)
        assert result == sorted(acts)

    def test_enrich_uppercase_crpc(self):
        """CRPC (canonical form from normalizer) gets enriched."""
        result = enrich_statute_cross_references(["CRPC"])
        assert "BNSS" in result

    def test_result_is_sorted(self):
        result = enrich_statute_cross_references(["IEA", "IPC", "CRPC"])
        assert result == sorted(result)


class TestTemporalGuard:
    """Test BNS/BNSS/BSA temporal guard for pre-2024 cases."""

    # -- Pre-2024: old codes only, no new codes added --

    def test_pre2024_ipc_no_bns_added(self):
        """Pre-2024 case with IPC should NOT get BNS."""
        result = enrich_statute_cross_references(["IPC"], decision_year=2020)
        assert result == ["IPC"]
        assert "BNS" not in result

    def test_pre2024_crpc_no_bnss_added(self):
        """Pre-2024 case with CRPC should NOT get BNSS."""
        result = enrich_statute_cross_references(["CRPC"], decision_year=2015)
        assert result == ["CRPC"]
        assert "BNSS" not in result

    def test_pre2024_iea_no_bsa_added(self):
        """Pre-2024 case with IEA should NOT get BSA."""
        result = enrich_statute_cross_references(["IEA"], decision_year=2023)
        assert result == ["IEA"]
        assert "BSA" not in result

    def test_pre2024_bns_replaced_with_ipc(self):
        """Pre-2024 case with BNS in input should replace BNS with IPC."""
        result = enrich_statute_cross_references(["BNS"], decision_year=2020)
        assert result == ["IPC"]
        assert "BNS" not in result

    def test_pre2024_bnss_replaced_with_crpc(self):
        """Pre-2024 case with BNSS in input should replace BNSS with CRPC."""
        result = enrich_statute_cross_references(["BNSS"], decision_year=2020)
        assert result == ["CRPC"]
        assert "BNSS" not in result

    def test_pre2024_bsa_replaced_with_iea(self):
        """Pre-2024 case with BSA in input should replace BSA with IEA."""
        result = enrich_statute_cross_references(["BSA"], decision_year=2020)
        assert result == ["IEA"]
        assert "BSA" not in result

    def test_pre2024_multiple_old_codes_no_new(self):
        """Pre-2024 case with IPC + IEA should keep both old, add no new."""
        result = enrich_statute_cross_references(
            ["IPC", "IEA"], decision_year=2010,
        )
        assert result == ["IEA", "IPC"]
        assert "BNS" not in result
        assert "BSA" not in result

    def test_pre2024_mixed_old_and_new_replaces_new(self):
        """Pre-2024 case with IPC + BNS should collapse to just IPC."""
        result = enrich_statute_cross_references(
            ["IPC", "BNS"], decision_year=2020,
        )
        assert result == ["IPC"]

    def test_pre2024_preserves_non_criminal_acts(self):
        """Pre-2024: non-criminal acts are preserved alongside old codes."""
        result = enrich_statute_cross_references(
            ["IPC", "ACA", "BNS"], decision_year=2018,
        )
        assert result == ["ACA", "IPC"]
        assert "BNS" not in result

    def test_pre2024_all_three_new_codes_replaced(self):
        """Pre-2024: all new codes replaced with old equivalents."""
        result = enrich_statute_cross_references(
            ["BNS", "BNSS", "BSA"], decision_year=2020,
        )
        assert result == ["CRPC", "IEA", "IPC"]

    def test_pre2024_uppercase_crpc_kept(self):
        """Pre-2024: CRPC uppercase variant is kept, no BNSS added."""
        result = enrich_statute_cross_references(["CRPC"], decision_year=2020)
        assert result == ["CRPC"]
        assert "BNSS" not in result

    # -- Post-2024: bidirectional enrichment --

    def test_post2024_ipc_gets_bns(self):
        """Post-2024 case with IPC should get both IPC and BNS."""
        result = enrich_statute_cross_references(["IPC"], decision_year=2024)
        assert "BNS" in result
        assert "IPC" in result

    def test_post2024_bns_gets_ipc(self):
        """Post-2024 case with BNS should get both BNS and IPC."""
        result = enrich_statute_cross_references(["BNS"], decision_year=2025)
        assert "IPC" in result
        assert "BNS" in result

    def test_post2024_full_bidirectional(self):
        """Post-2024 case gets full bidirectional enrichment."""
        result = enrich_statute_cross_references(
            ["IPC", "CRPC"], decision_year=2024,
        )
        assert "BNS" in result
        assert "BNSS" in result
        assert "IPC" in result
        assert "CRPC" in result

    # -- decision_year=None: backward compatible bidirectional --

    def test_none_year_bidirectional(self):
        """decision_year=None should behave like pre-change (bidirectional)."""
        result = enrich_statute_cross_references(["IPC"], decision_year=None)
        assert "BNS" in result
        assert "IPC" in result

    def test_no_year_kwarg_bidirectional(self):
        """Omitting decision_year entirely should be bidirectional."""
        result = enrich_statute_cross_references(["IPC"])
        assert "BNS" in result
        assert "IPC" in result

    # -- Edge cases --

    def test_pre2024_empty_list(self):
        """Empty list with pre-2024 year returns empty."""
        assert enrich_statute_cross_references([], decision_year=2020) == []

    def test_pre2024_only_non_criminal(self):
        """Pre-2024 with only non-criminal acts returns them unchanged."""
        result = enrich_statute_cross_references(
            ["COI", "ACA"], decision_year=2020,
        )
        assert result == ["ACA", "COI"]

    def test_boundary_year_2023_is_pre(self):
        """Year 2023 is pre-2024 — no new codes."""
        result = enrich_statute_cross_references(["IPC"], decision_year=2023)
        assert result == ["IPC"]
        assert "BNS" not in result

    def test_boundary_year_2024_is_post(self):
        """Year 2024 is post — bidirectional enrichment."""
        result = enrich_statute_cross_references(["IPC"], decision_year=2024)
        assert "BNS" in result
